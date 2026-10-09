"""Owned project CRUD, immutable revisions, and source-safe templates."""

import copy
import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from plimsoll_web.models import ProjectRevision


def test_create_and_reopen_empty_or_template(alice):
    empty = alice.post("/api/projects", json={"template": None, "name": "草稿"})
    assert empty.status_code == 201
    empty_id = empty.json()["project_id"]
    opened = alice.get(f"/api/projects/{empty_id}").json()
    assert opened["project"]["schema"] == "plimsoll-project-1"
    assert opened["project"]["loading_conditions"] == []
    assert opened["revision"] == 1
    assert any(item["project_id"] == empty_id for item in alice.get("/api/projects").json())


def test_other_user_cannot_read_modify_or_delete(alice, bob, project_id, saved_document):
    assert bob.get(f"/api/projects/{project_id}").status_code == 404
    assert all(item["project_id"] != project_id for item in bob.get("/api/projects").json())
    assert bob.put(f"/api/projects/{project_id}", json={"base_revision": 1, "project": saved_document}).status_code == 404
    assert bob.request("DELETE", f"/api/projects/{project_id}", json={}).status_code == 404
    assert alice.get(f"/api/projects/{project_id}").status_code == 200


def test_stale_save_preserves_newer_revision(alice, project_id, saved_document, engine):
    changed = copy.deepcopy(saved_document)
    changed["name"] = "新名称"
    a = alice.put(f"/api/projects/{project_id}", json={"base_revision": 1, "project": changed})
    b = alice.put(f"/api/projects/{project_id}", json={"base_revision": 1, "project": saved_document})
    assert a.status_code == 200 and a.json()["revision"] == 2
    assert b.status_code == 409 and b.json()["current_revision"] == 2
    assert alice.get(f"/api/projects/{project_id}").json()["project"]["name"] == "新名称"
    with Session(engine) as db:
        revisions = db.scalars(select(ProjectRevision).order_by(ProjectRevision.revision)).all()
        assert [revision.revision for revision in revisions] == [1, 2]
        assert revisions[0].document["name"] == saved_document["name"]


def test_queen_mary_large_inline_geometry_round_trips(alice):
    created = alice.post("/api/projects", json={"template": "queen_mary_1913", "name": "HMS Queen Mary"})
    assert created.status_code == 201
    opened = alice.get(f"/api/projects/{created.json()['project_id']}").json()
    assert opened["project"]["geometry"]["kind"] == "offsets"
    assert len(json.dumps(opened["project"], ensure_ascii=False).encode("utf-8")) > 1_000_000
    assert opened["project"]["id"] == created.json()["project_id"]


def test_invalid_project_or_external_geometry_does_not_change_revision(alice, project_id, saved_document):
    invalid = copy.deepcopy(saved_document)
    invalid["schema"] = "wrong"
    assert alice.put(f"/api/projects/{project_id}", json={"base_revision": 1, "project": invalid}).status_code == 422
    external = copy.deepcopy(saved_document)
    external["geometry"] = {"kind": "offsets_reference", "reference": {"path": "../../secrets.txt"}}
    assert alice.put(f"/api/projects/{project_id}", json={"base_revision": 1, "project": external}).status_code == 422
    assert alice.get(f"/api/projects/{project_id}").json()["revision"] == 1


@pytest.mark.parametrize('path', ('systems', 'systems.armour', 'systems.armour.fixed'))
@pytest.mark.parametrize('invalid', ([], [{}]))
def test_invalid_extension_shape_cannot_create_a_revision(alice, project_id, saved_document, path, invalid):
    document = copy.deepcopy(saved_document)
    cursor = document
    parts = path.split('.')
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor[parts[-1]] = invalid
    response = alice.put(f'/api/projects/{project_id}',
                         json={'base_revision': 1, 'project': document})
    assert response.status_code == 422
    assert any(diagnostic['path'] == '$.' + path for diagnostic in response.json()['detail'])
    assert alice.get(f'/api/projects/{project_id}').json()['revision'] == 1


def test_project_request_over_eight_mib_is_rejected(alice, project_id, saved_document):
    huge = copy.deepcopy(saved_document)
    huge["name"] = "x" * (8 * 1024 * 1024)
    payload = json.dumps({"base_revision": 1, "project": huge})
    response = alice.put(
        f"/api/projects/{project_id}", content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert alice.get(f"/api/projects/{project_id}").json()["revision"] == 1


def test_owner_can_delete_project(alice, project_id, engine):
    assert alice.request("DELETE", f"/api/projects/{project_id}", json={}).status_code == 204
    assert alice.get(f"/api/projects/{project_id}").status_code == 404
    with Session(engine) as db:
        assert db.scalars(select(ProjectRevision)).all() == []
