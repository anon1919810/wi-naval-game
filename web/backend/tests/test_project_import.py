"""Restoring a project backup: validate, preview, then save as a new project.

A backup is input only. Importing must therefore never touch an existing
project — not the reader's own, not another account's — and must never restore
runs, fingerprints or caches. These tests pin that: the preview endpoint writes
nothing at all, the save endpoint mints a fresh identity, and every rejection
leaves the library exactly as it was.
"""

from __future__ import annotations

import copy
import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plimsoll_web.models import CalculationRun, Project, ProjectRevision


PREVIEW = "/api/projects/import-preview"
IMPORT = "/api/projects/import"


def backup(project: dict) -> dict:
    """A canonical backup document that is not yet anybody's project."""
    document = copy.deepcopy(project)
    document["id"] = "backup-source-id-0000"
    document["revision"] = 7
    return document


def table_sizes(engine) -> dict[str, int]:
    with Session(engine) as db:
        return {
            "projects": db.scalar(select(func.count()).select_from(Project)),
            "revisions": db.scalar(select(func.count()).select_from(ProjectRevision)),
            "runs": db.scalar(select(func.count()).select_from(CalculationRun)),
        }


def codes(response) -> set[str]:
    return {item.get("code") for item in response.json()["detail"]}


def paths(response) -> set[str]:
    return {item.get("path") for item in response.json()["detail"]}


def flooding_scenario(identity: str) -> dict:
    """A complete damage scenario, so its presence is what is being counted."""
    return {
        "schema": "plimsoll-flooding-scenario-1", "id": identity, "label": "Single hole",
        "duration_s": 60.0, "time_step_s": 0.5, "source": "declared damage case", "estimate": False,
        "sea": {"id": "sea", "fluid_density_t_m3": 1.025, "source": "declared sea", "estimate": False},
        "tanks": [{"id": "room", "length_m": 10.0, "beam_m": 6.0, "height_m": 3.0, "x_m": 1.0,
                   "y_m": 0.0, "keel_to_bottom_m": 0.5, "permeability": 0.9, "free_surface": True,
                   "fluid_density_t_m3": 1.025, "initial_volume_m3": 0.0,
                   "source": "declared compartment", "estimate": False}],
        "connections": [{"id": "sea-hole", "from": "sea", "to": "room", "x_m": 0.0, "y_m": 0.0,
                         "z_m": 0.2, "area_m2": 0.05, "discharge_coefficient": 0.6,
                         "fluid_density_t_m3": 1.025, "open": True,
                         "source": "declared aperture", "estimate": False}],
    }


# --- preview is a read, and says only what a reader needs ------------------

def test_preview_describes_the_backup_without_returning_the_document(alice, saved_document):
    response = alice.post(PREVIEW, json={"project": backup(saved_document)})
    assert response.status_code == 200
    preview = response.json()
    assert preview["source_id"] == "backup-source-id-0000"
    assert preview["name"] == saved_document["name"]
    assert preview["source_revision"] == 7
    assert preview["geometry_kind"] == "offsets"
    assert preview["counts"] == {"loading_conditions": 2, "weight_groups": 9, "weight_items": 2,
                                 "damage_scenarios": 0, "compartments": 1, "openings": 2}
    assert isinstance(preview["diagnostics"], list)
    # The whole normalized document is deliberately absent from a preview.
    assert "project" not in preview
    assert "hull" not in json.dumps(preview, ensure_ascii=False)


def test_preview_of_a_bare_draft_reports_no_geometry(alice):
    created = alice.post("/api/projects", json={"template": None, "name": "草稿"})
    preview = alice.post(PREVIEW, json={"project": backup(created.json()["project"])}).json()
    assert preview["geometry_kind"] is None
    assert preview["counts"] == {"loading_conditions": 0, "weight_groups": 0, "weight_items": 0,
                                 "damage_scenarios": 0, "compartments": 0, "openings": 0}


def test_preview_writes_nothing(alice, engine):
    created = alice.post("/api/projects", json={"template": "queen_mary_1913", "name": "HMS Queen Mary"})
    assert created.status_code == 201
    before = table_sizes(engine)
    assert before == {"projects": 1, "revisions": 1, "runs": 0}
    assert alice.post(PREVIEW, json={"project": created.json()["project"]}).status_code == 200
    assert table_sizes(engine) == before
    # Even a preview of a document that no project holds leaves nothing behind.
    assert alice.post(PREVIEW, json={"project": backup(created.json()["project"])}).status_code == 200
    assert table_sizes(engine) == before


def test_preview_counts_every_section_a_reader_is_asked_to_confirm(alice, saved_document):
    document = backup(saved_document)
    document["weight_groups"] = [
        {"id": "structure", "label": "结构", "required": True, "items": [
            {"id": "steel", "label": "船体钢", "mass_t": 2100, "x_m": 0, "y_m": 0,
             "kg_m": None, "source": "shipyard plan", "estimate": False},
            {"id": "outfit", "label": "舾装", "mass_t": 0, "x_m": None, "y_m": None,
             "kg_m": 0, "source": None, "estimate": None},
        ]},
        {"id": "stores", "label": "物料", "required": False, "items": []},
    ]
    document["loading_conditions"] = [
        {"id": "loaded", "label": "满载", "reference_displacement_t": 4000, "overrides": {}},
        {"id": "ballast", "label": "压载", "reference_displacement_t": None, "overrides": {}},
    ]
    document["compartments"] = [{"id": "hold-1"}, {"id": "hold-2"}]
    document["openings"] = [{"id": "hatch-1"}]
    document["opening_definition"] = "supplied"
    document["flooding_scenarios"] = [flooding_scenario("flooding_1")]

    preview = alice.post(PREVIEW, json={"project": document}).json()
    assert preview["counts"] == {"loading_conditions": 2, "weight_groups": 2, "weight_items": 2,
                                 "damage_scenarios": 1, "compartments": 2, "openings": 1}


def test_preview_reports_canonical_warnings_with_their_field_paths(alice, saved_document):
    document = backup(saved_document)
    document["weight_groups"][0]["items"][0]["estimate"] = None
    document["weight_groups"][0]["items"][0]["mass_t"] = None
    preview = alice.post(PREVIEW, json={"project": document}).json()
    reported = {item["path"] for item in preview["diagnostics"]}
    assert "$.weight_groups[0].items[0].estimate" in reported
    assert "$.weight_groups[0].items[0].mass_t" in reported
    assert all({"code", "severity", "path", "message"} <= set(item) for item in preview["diagnostics"])
    assert all(item["severity"] == "warning" for item in preview["diagnostics"])


@pytest.mark.parametrize("break_field,code,path,broken", [
    ("id", "id.invalid", "$.id", ""),
    ("id", "id.invalid", "$.id", {"nested": "object"}),
    ("revision", "revision.invalid", "$.revision", "seven"),
    ("revision", "revision.invalid", "$.revision", -1),
])
def test_malformed_source_identity_fails_before_it_can_be_replaced(
    alice, project_id, saved_document, engine, break_field, code, path, broken,
):
    document = backup(saved_document)
    document[break_field] = broken
    before = table_sizes(engine)
    for endpoint in (PREVIEW, IMPORT):
        response = alice.post(endpoint, json={"project": document})
        assert response.status_code == 422
        assert code in codes(response)
        assert path in paths(response)
    assert table_sizes(engine) == before
    # The reader's own project is untouched by a rejected backup.
    assert alice.get(f"/api/projects/{project_id}").json()["revision"] == 1


def test_a_source_revision_is_reported_as_written_not_as_saved(alice, saved_document):
    document = backup(saved_document)
    document["revision"] = 42
    assert alice.post(PREVIEW, json={"project": document}).json()["source_revision"] == 42
    view = alice.post(IMPORT, json={"project": document}).json()
    # A backup of revision 42 is restored as a fresh project at revision 1.
    assert view["revision"] == 1
    assert view["project"]["revision"] == 1


def test_preview_rejects_a_schema_it_does_not_recognise(alice, saved_document):
    document = backup(saved_document)
    document["schema"] = "plimsoll-project-2"
    response = alice.post(PREVIEW, json={"project": document})
    assert response.status_code == 422
    assert "schema.unsupported" in codes(response)
    assert "$.schema" in paths(response)


def test_both_endpoints_reject_extra_request_fields(alice, saved_document):
    for endpoint in (PREVIEW, IMPORT):
        response = alice.post(endpoint, json={"project": backup(saved_document), "template": "analytic_box"})
        assert response.status_code == 422


# --- saving restores input, under a new identity ----------------------------

def test_import_saves_a_new_project_owned_by_the_reader(alice, saved_document):
    response = alice.post(IMPORT, json={"project": backup(saved_document), "name": "  恢复的解析方箱  "})
    assert response.status_code == 201
    view = response.json()
    assert view["revision"] == 1
    assert view["project"]["name"] == "恢复的解析方箱"
    assert view["project"]["id"] == view["project_id"]
    assert view["project"]["revision"] == 1
    assert view["project"]["schema"] == "plimsoll-project-1"
    # The backup's own identity is reported by the preview, never reused.
    assert view["project_id"] != "backup-source-id-0000"
    assert any(item["project_id"] == view["project_id"] for item in alice.get("/api/projects").json())
    assert alice.get(f"/api/projects/{view['project_id']}").json()["project"] == view["project"]


def test_import_keeps_the_source_name_when_none_is_confirmed(alice, saved_document):
    document = backup(saved_document)
    document["name"] = "备份里的名字"
    view = alice.post(IMPORT, json={"project": document}).json()
    assert view["project"]["name"] == "备份里的名字"


def test_import_preserves_input_flags_inline_geometry_and_unknown_fields(alice, saved_document):
    document = backup(saved_document)
    document["hull"].update({"length_m": 90, "beam_m": 20, "draft_m": 0, "loa_m": None})
    document["weight_groups"] = [{
        "id": "lightship", "label": "空船", "required": True,
        "items": [{
            "id": "steel", "label": "船体钢", "mass_t": 2100, "x_m": 0, "y_m": 0, "kg_m": None,
            "source": "1909 shipyard list", "estimate": False, "uncertainty": {"mass_t": [2000, 2200]},
            "includes": ["hull-structure"], "studio_note": "kept verbatim",
        }],
    }]
    document["loading_conditions"] = [
        {"id": "loaded", "label": "满载", "reference_displacement_t": None,
         "overrides": {"steel": {"mass_t": 0}}},
    ]
    document["geometry"] = {"kind": "offsets", "source": "plan", "estimate": True,
                            "keel_offset_m": None, "offsets": {"stations": [
                                {"x_m": 0, "half_breadths_m": [5, 4]}, {"x_m": 10, "half_breadths_m": [5, 4]},
                            ]}}
    document["studio_metadata"] = {"drafting": {"checked_by": "restoration"}}
    document["sources"] = {"hull": "1909 shipyard list"}

    view = alice.post(IMPORT, json={"project": document}).json()
    saved = view["project"]
    assert saved["hull"] == document["hull"]
    assert saved["weight_groups"][0]["items"][0] == document["weight_groups"][0]["items"][0]
    assert saved["loading_conditions"] == document["loading_conditions"]
    assert saved["geometry"] == document["geometry"]
    assert saved["studio_metadata"] == {"drafting": {"checked_by": "restoration"}}
    assert saved["sources"] == document["sources"]
    # Only the top-level identity, revision and name are allowed to change.
    assert (saved["id"], saved["revision"]) == (view["project_id"], 1)


def test_import_of_a_large_inline_geometry_backup(alice):
    created = alice.post("/api/projects", json={"template": "queen_mary_1913", "name": "HMS Queen Mary"})
    assert created.status_code == 201
    document = backup(created.json()["project"])
    assert len(json.dumps(document, ensure_ascii=False).encode("utf-8")) > 1_000_000

    preview = alice.post(PREVIEW, json={"project": document})
    assert preview.status_code == 200
    assert preview.json()["geometry_kind"] == "offsets"
    assert preview.json()["counts"]["weight_items"] > 0

    view = alice.post(IMPORT, json={"project": document}).json()
    assert view["project"]["geometry"]["kind"] == "offsets"
    assert len(view["project"]["geometry"]["offsets"]["stations"]) == len(
        document["geometry"]["offsets"]["stations"])
    assert len(json.dumps(view["project"], ensure_ascii=False).encode("utf-8")) > 1_000_000


# --- an existing project is never the target -------------------------------

def test_import_never_writes_over_the_readers_own_project(alice, project_id, saved_document):
    original = alice.get(f"/api/projects/{project_id}").json()
    document = backup(saved_document)
    document["id"] = project_id
    document["name"] = "被覆盖的名字"
    document["revision"] = 9

    view = alice.post(IMPORT, json={"project": document}).json()
    assert view["project_id"] != project_id
    assert view["project"]["name"] == "被覆盖的名字"
    assert alice.get(f"/api/projects/{project_id}").json() == original
    assert alice.get(f"/api/projects/{view['project_id']}").json()["revision"] == 1


def test_import_of_a_foreign_project_id_creates_a_private_copy(alice, bob, project_id, saved_document):
    original = alice.get(f"/api/projects/{project_id}").json()
    document = backup(saved_document)
    document["id"] = project_id

    assert bob.post(PREVIEW, json={"project": document}).status_code == 200
    view = bob.post(IMPORT, json={"project": document}).json()
    assert view["project_id"] != project_id
    assert bob.get(f"/api/projects/{view['project_id']}").status_code == 200
    assert bob.get(f"/api/projects/{project_id}").status_code == 404
    assert all(item["project_id"] != project_id for item in bob.get("/api/projects").json())
    # The other account's project is exactly as it was.
    assert alice.get(f"/api/projects/{project_id}").json() == original


def test_two_imports_of_one_backup_are_two_separate_projects(alice, project_id, saved_document):
    document = backup(saved_document)
    listed = len(alice.get("/api/projects").json())
    first = alice.post(IMPORT, json={"project": document}).json()
    second = alice.post(IMPORT, json={"project": document}).json()
    assert first["project_id"] != second["project_id"]
    assert len(alice.get("/api/projects").json()) == listed + 2


# --- rejections leave no orphan --------------------------------------------

@pytest.mark.parametrize("mutate,label", [
    (lambda document: document.pop("schema"), "schema"),
    (lambda document: document.update({"loading_conditions": "many"}), "loading_conditions"),
    (lambda document: document.update({"result": {"stages": {}}}), "result"),
    (lambda document: document.update({"input_fingerprint": "a" * 64}), "fingerprint"),
    (lambda document: document.update({"geometry": {"kind": "offsets_reference",
                                                    "reference": {"path": "../../secrets.txt"}}}), "external"),
    (lambda document: document.update({"weight_groups": [[]]}), "weight_groups"),
])
def test_rejected_backups_create_no_project(alice, saved_document, engine, mutate, label):
    document = backup(saved_document)
    mutate(document)
    before = table_sizes(engine)
    listed = alice.get("/api/projects").json()
    for endpoint in (PREVIEW, IMPORT):
        assert alice.post(endpoint, json={"project": document}).status_code == 422, label
    assert table_sizes(engine) == before
    assert alice.get("/api/projects").json() == listed


def test_analysis_report_json_is_refused_rather_than_turned_into_input(alice):
    report = {"schema": "plimsoll-analysis-1", "status": "completed", "project_id": "p1",
              "input_snapshot": {"schema": "plimsoll-project-1", "id": "p1", "name": "报告里的快照",
                                 "revision": 2, "hull": {}, "geometry": None,
                                 "loading_conditions": [], "weight_groups": []},
              "stages": {}}
    response = alice.post(IMPORT, json={"project": report})
    assert response.status_code == 422
    assert "schema.unsupported" in codes(response)
    assert "$.schema" in paths(response)
    assert alice.get("/api/projects").json() == []


def test_reserved_result_fields_are_named_not_stripped(alice, saved_document):
    document = backup(saved_document)
    document["cache_key"] = "stale"
    response = alice.post(PREVIEW, json={"project": document})
    assert response.status_code == 422
    assert "project.result_field_reserved" in codes(response)
    assert "$.cache_key" in paths(response)


def test_a_top_level_array_is_refused(alice):
    for endpoint in (PREVIEW, IMPORT):
        assert alice.post(endpoint, json={"project": [{"schema": "plimsoll-project-1"}]}).status_code == 422


# --- names ------------------------------------------------------------------

def test_a_whitespace_only_name_is_refused(alice, saved_document, engine):
    before = table_sizes(engine)
    response = alice.post(IMPORT, json={"project": backup(saved_document), "name": "　 \n "})
    assert response.status_code == 422
    assert table_sizes(engine) == before


def test_a_maximum_length_name_is_accepted(alice, saved_document):
    name = "舰" * 200
    view = alice.post(IMPORT, json={"project": backup(saved_document), "name": name}).json()
    assert view["project"]["name"] == name


def test_an_over_length_name_is_refused(alice, saved_document, engine):
    before = table_sizes(engine)
    response = alice.post(IMPORT, json={"project": backup(saved_document), "name": "舰" * 201})
    assert response.status_code == 422
    assert table_sizes(engine) == before


def test_a_null_name_is_read_as_no_name_rather_than_the_text_null(alice, saved_document, engine):
    before = table_sizes(engine)
    view = alice.post(IMPORT, json={"project": backup(saved_document), "name": None}).json()
    assert view["project"]["name"] == saved_document["name"]
    assert table_sizes(engine)["projects"] == before["projects"] + 1


def test_a_long_source_name_is_reported_then_must_be_renamed_before_saving(alice, engine):
    """A backup whose own name exceeds the stored bound can still be read.

    The reader is shown exactly what the file contains so they can decide what
    to call the restored project; saving it under that name unchanged is refused
    before a single row is written, because the stored column cannot hold it.
    """
    document = backup({"schema": "plimsoll-project-1", "id": "backup", "name": "舰" * 260,
                       "revision": 3, "hull": {"length_m": 90, "beam_m": 20, "draft_m": 4},
                       "geometry": None, "opening_definition": "unknown",
                       "weight_groups": [], "loading_conditions": []})
    before = table_sizes(engine)
    preview = alice.post(PREVIEW, json={"project": document})
    assert preview.status_code == 200
    assert preview.json()["name"] == "舰" * 260

    assert alice.post(IMPORT, json={"project": document}).status_code == 422
    assert alice.post(IMPORT, json={"project": document, "name": None}).status_code == 422
    assert table_sizes(engine) == before

    # Confirming a name that does fit saves the project with all its input.
    view = alice.post(IMPORT, json={"project": document, "name": " 恢复的长名舰船 "}).json()
    assert view["project"]["name"] == "恢复的长名舰船"
    assert view["project"]["hull"] == document["hull"]
    assert view["project"]["revision"] == 1


def test_a_maximum_length_source_name_is_saved_unchanged(alice, engine):
    document = backup({"schema": "plimsoll-project-1", "id": "backup", "name": "舰" * 200,
                       "revision": 1, "hull": {"length_m": 90, "beam_m": 20, "draft_m": 4},
                       "geometry": None, "opening_definition": "unknown",
                       "weight_groups": [], "loading_conditions": []})
    view = alice.post(IMPORT, json={"project": document}).json()
    assert view["project"]["name"] == "舰" * 200


# --- the existing protections, on both new endpoints ------------------------

@pytest.mark.parametrize("endpoint", (PREVIEW, IMPORT))
def test_import_requires_a_signed_in_owner(client, engine, saved_document, endpoint):
    before = table_sizes(engine)
    response = client.post(endpoint, json={"project": backup(saved_document)})
    assert response.status_code == 401
    assert table_sizes(engine) == before


@pytest.mark.parametrize("endpoint", (PREVIEW, IMPORT))
def test_import_requires_the_readers_csrf_token(alice, engine, saved_document, endpoint):
    before = table_sizes(engine)
    response = alice.post(endpoint, json={"project": backup(saved_document)},
                          headers={"X-CSRF-Token": ""})
    assert response.status_code == 403
    assert table_sizes(engine) == before


@pytest.mark.parametrize("endpoint", (PREVIEW, IMPORT))
def test_import_requires_a_trusted_origin(alice, engine, saved_document, endpoint):
    before = table_sizes(engine)
    response = alice.post(endpoint, json={"project": backup(saved_document)},
                          headers={"Origin": "http://evil.example"})
    assert response.status_code == 403
    assert table_sizes(engine) == before


@pytest.mark.parametrize("endpoint", (PREVIEW, IMPORT))
def test_import_over_eight_mib_is_refused(alice, engine, saved_document, endpoint):
    document = backup(saved_document)
    document["hull"]["note"] = "x" * (8 * 1024 * 1024)
    payload = json.dumps({"project": document})
    assert len(payload.encode("utf-8")) > 8 * 1024 * 1024
    before = table_sizes(engine)
    response = alice.post(endpoint, content=payload, headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert table_sizes(engine) == before


def test_import_starts_no_calculation_and_leaves_no_run(alice, project_id, saved_document, engine):
    view = alice.post(IMPORT, json={"project": backup(saved_document)}).json()
    assert table_sizes(engine) == {"projects": 2, "revisions": 2, "runs": 0}
    assert alice.get(f"/api/projects/{view['project_id']}/runs").json() == []
    assert alice.get(f"/api/projects/{view['project_id']}").json()["revision"] == 1