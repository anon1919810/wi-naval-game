"""Saved-snapshot jobs, status propagation, owner checks, and unchanged exports."""

from datetime import timedelta
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plimsoll import analysis
from plimsoll_web.models import CalculationRun, ProjectRevision, utc_now


def queue(alice, project_id, **changes):
    body = {"revision": 1, "condition_id": "loaded", "options": {"stages": ["loading"]}}
    body.update(changes)
    return alice.post(f"/api/projects/{project_id}/runs", json=body)


def test_queued_run_freezes_saved_revision_and_request(alice, project_id, engine, worker_once):
    queued = queue(alice, project_id)
    assert queued.status_code == 202
    run_id = queued.json()["id"]
    with Session(engine) as db:
        row = db.get(CalculationRun, uuid.UUID(run_id))
        revision = db.get(ProjectRevision, (row.project_id, 1))
        assert row.input_snapshot == revision.document
        assert row.request["options"]["stages"] == ["loading"]
        assert len(row.request_fingerprint) == 64
    assert worker_once() is True
    finished = alice.get(f"/api/runs/{run_id}").json()
    assert finished["status"] == "completed"
    assert finished["result"]["request_fingerprint"] == row.request_fingerprint
    assert finished["result"]["schema"] == "plimsoll-analysis-1"


def test_other_user_cannot_read_cancel_or_export(alice, bob, run_id, project_id):
    assert bob.get(f"/api/runs/{run_id}").status_code == 404
    assert bob.post(f"/api/runs/{run_id}/cancel", json={}).status_code == 404
    assert bob.get(f"/api/runs/{run_id}/export?format=json").status_code == 404
    assert bob.get(f"/api/projects/{project_id}/runs").status_code == 404
    assert bob.post(f"/api/projects/{project_id}/runs", json={
        "revision": 1, "condition_id": "loaded", "options": {"stages": ["loading"]},
    }).status_code == 404


def test_invalid_condition_options_revision_and_unsaved_payload_are_rejected(alice, project_id, saved_document):
    assert queue(alice, project_id, condition_id="not-a-condition").status_code == 422
    assert queue(alice, project_id, options={"stages": ["not-a-stage"]}).status_code == 422
    assert queue(alice, project_id, project=saved_document).status_code == 422
    assert alice.put(f"/api/projects/{project_id}", json={"base_revision": 1, "project": saved_document}).status_code == 200
    assert queue(alice, project_id, revision=1).status_code == 409


def test_active_limit_and_cancel_before_claim(alice, project_id, worker_once):
    first = queue(alice, project_id)
    assert first.status_code == 202
    assert queue(alice, project_id).status_code == 429
    run_id = first.json()["id"]
    assert alice.post(f"/api/runs/{run_id}/cancel", json={}).json()["status"] == "canceled"
    assert worker_once() is False
    assert alice.get(f"/api/runs/{run_id}").json()["result"] is None


def test_export_uses_stored_result_without_recompute(alice, run_id, monkeypatch):
    monkeypatch.setattr(analysis, "compute_project", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("recomputed")))
    document = alice.get(f"/api/runs/{run_id}/export?format=json")
    csv = alice.get(f"/api/runs/{run_id}/export?format=csv")
    assert document.status_code == csv.status_code == 200
    assert document.json()["schema"] == "plimsoll-analysis-1"
    fingerprint = document.json()["request_fingerprint"]
    assert fingerprint in csv.text
    assert alice.get(f"/api/runs/{run_id}/export?format=pdf").status_code == 422


def test_partial_result_is_visible_without_safety_claim(alice, run_id, engine):
    with Session(engine) as db:
        row = db.get(CalculationRun, uuid.UUID(run_id))
        result = json.loads(json.dumps(row.result))
        result["status"] = "partial"
        result["stages"]["loading"]["status"] = "model_limit"
        result["stages"]["loading"]["reason"] = "outside method range"
        row.result = result
        row.status = "partial"
        db.commit()
    read = alice.get(f"/api/runs/{run_id}").json()
    assert read["status"] == "partial"
    assert read["result"]["stages"]["loading"]["status"] == "model_limit"
    assert read["result"]["stages"]["loading"]["reason"] == "outside method range"


def test_expired_worker_lease_becomes_failed(alice, project_id, engine):
    run_id = queue(alice, project_id).json()["id"]
    with Session(engine) as db:
        row = db.get(CalculationRun, uuid.UUID(run_id))
        row.status = "running"
        row.lease_expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    read = alice.get(f"/api/runs/{run_id}").json()
    assert read["status"] == "failed"
    assert read["result"] is None
    assert read["error"]["code"] == "run.worker_lost"
    assert queue(alice, project_id).status_code == 202


def test_expired_lease_is_recovered_before_new_enqueue(alice, project_id, engine):
    run_id = queue(alice, project_id).json()["id"]
    with Session(engine) as db:
        row = db.get(CalculationRun, uuid.UUID(run_id))
        row.status = "running"
        row.lease_expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    assert queue(alice, project_id).status_code == 202
    assert alice.get(f"/api/runs/{run_id}").json()["status"] == "failed"


def test_only_one_claim_of_queued_run(alice, project_id, engine):
    run_id = queue(alice, project_id).json()["id"]
    from plimsoll_web.worker import claim_next_run
    with Session(engine) as db:
        claimed = claim_next_run(db)
        assert claimed.id == uuid.UUID(run_id)
        db.commit()
    with Session(engine) as db:
        assert claim_next_run(db) is None


def test_running_cancel_sets_worker_visible_flag(alice, project_id, engine):
    run_id = queue(alice, project_id).json()["id"]
    from plimsoll_web.worker import claim_next_run
    with Session(engine) as db:
        claim_next_run(db)
        db.commit()
    response = alice.post(f"/api/runs/{run_id}/cancel", json={})
    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["cancel_requested"] is True
    with Session(engine) as db:
        assert db.get(CalculationRun, uuid.UUID(run_id)).cancel_requested is True
