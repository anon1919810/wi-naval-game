"""Lab queue isolation, owner guards and actual bounded-core execution."""
import copy
import json
from pathlib import Path

import pytest

CASES = Path(__file__).resolve().parents[3] / "tools/plimsoll/cases/damage_lab"


@pytest.fixture
def lab_inputs(alice):
    project = json.loads((CASES / "synthetic-rig.project.json").read_text(encoding="utf-8"))
    response = alice.post("/api/projects/import", json={"project": project})
    assert response.status_code == 201
    experiment = json.loads((CASES / "machinery-hit.experiment.json").read_text(encoding="utf-8"))
    return response.json()["project_id"], experiment


def queue(alice, inputs, **changes):
    pid, experiment = inputs
    body = dict(revision=1, condition_id="normal", experiment=experiment)
    body.update(changes)
    return alice.post(f"/api/projects/{pid}/damage-lab-runs", json=body)


def test_real_worker_result_and_exports(alice, lab_inputs, worker_once):
    queued = queue(alice, lab_inputs)
    assert queued.status_code == 202, queued.text
    rid = queued.json()["id"]
    assert worker_once()
    read = alice.get(f"/api/damage-lab-runs/{rid}")
    assert read.status_code == 200
    result = read.json()["result"]
    assert result["schema"] == "plimsoll-damage-lab-result-1"
    assert result["status"] == "completed"
    assert result["request_fingerprint"] == queued.json()["request_fingerprint"]
    assert result["core_analysis"]["stages"]["flooding"]["data"]["timeline"]
    assert alice.get(f"/api/damage-lab-runs/{rid}/export?format=json").json() == result
    assert result["request_fingerprint"] in alice.get(f"/api/damage-lab-runs/{rid}/export?format=csv").text
    assert alice.get(f"/api/damage-lab-runs/{rid}/export?format=pdf").status_code == 422


def test_owner_and_kind_isolation(alice, bob, lab_inputs, run_id):
    pid, _ = lab_inputs
    queued = queue(alice, lab_inputs)
    assert queued.status_code == 202
    rid = queued.json()["id"]
    for prefix in ("/api/damage-lab-runs", "/api/runs"):
        assert bob.get(f"{prefix}/{rid}").status_code == 404
        assert bob.post(f"{prefix}/{rid}/cancel", json={}).status_code == 404
        assert bob.get(f"{prefix}/{rid}/export?format=json").status_code == 404
    assert alice.get(f"/api/runs/{rid}").status_code == 404
    assert alice.post(f"/api/runs/{rid}/cancel", json={}).status_code == 404
    assert alice.get(f"/api/damage-lab-runs/{run_id}").status_code == 404
    assert alice.get(f"/api/projects/{pid}/runs").json() == []
    assert len(alice.get(f"/api/projects/{pid}/damage-lab-runs").json()) == 1
    assert bob.get(f"/api/projects/{pid}/damage-lab-runs").status_code == 404


def test_shared_limit_cancel_and_invalid_admission(alice, lab_inputs, worker_once):
    pid, experiment = lab_inputs
    candidate = copy.deepcopy(experiment)
    candidate["impact"]["severity"] = True
    assert queue(alice, lab_inputs, experiment=candidate).status_code == 422
    assert queue(alice, lab_inputs, revision=2).status_code == 409
    first = queue(alice, lab_inputs)
    assert first.status_code == 202
    assert queue(alice, lab_inputs).status_code == 429
    assert alice.post(f"/api/projects/{pid}/runs", json={"revision": 1, "condition_id": "normal",
                       "options": {"stages": ["loading"]}}).status_code == 429
    rid = first.json()["id"]
    assert alice.post(f"/api/damage-lab-runs/{rid}/cancel", json={}).json()["status"] == "canceled"
    assert worker_once() is False
    assert alice.get(f"/api/damage-lab-runs/{rid}/export?format=json").status_code == 409


def test_setup_unknowns_demo_and_write_guards(alice, bob, lab_inputs):
    pid, _ = lab_inputs
    setup = alice.get(f"/api/projects/{pid}/damage-lab-setup")
    assert setup.status_code == 200
    assert setup.json()["experiment"]["crew_groups"][0]["personnel"] is None
    assert bob.get(f"/api/projects/{pid}/damage-lab-setup").status_code == 404
    assert alice.get("/api/damage-lab-demo").json()["project"]["id"] == "damage-lab-synthetic-vessel"
    assert queue(alice, lab_inputs).status_code == 202
    alice.headers.pop("X-CSRF-Token")
    assert queue(alice, lab_inputs).status_code == 403


def test_preview_validates_json_without_queuing(alice, lab_inputs):
    pid, experiment = lab_inputs
    path = f"/api/projects/{pid}/damage-lab-preview"
    body = dict(revision=1, condition_id="normal", experiment=experiment)
    accepted = alice.post(path, json=body)
    assert accepted.status_code == 200
    assert accepted.json()["experiment"] == experiment
    assert alice.get(f"/api/projects/{pid}/damage-lab-runs").json() == []
    malformed = copy.deepcopy(body)
    malformed["experiment"]["modules"][0]["role"] = None
    assert alice.post(path, json=malformed).status_code == 422
    alice.headers["Origin"] = "https://untrusted.invalid"
    assert queue(alice, lab_inputs).status_code == 403


@pytest.mark.parametrize("missing", ["length_m", "permeability", "source", "estimate"])
def test_incomplete_imported_layout_is_unavailable_not_http_500(alice, missing):
    project = json.loads((CASES / "synthetic-rig.project.json").read_text(encoding="utf-8"))
    del project["compartments"][0][missing]
    imported = alice.post("/api/projects/import", json={"project": project})
    assert imported.status_code == 201, imported.text
    pid = imported.json()["project_id"]
    response = alice.get(f"/api/projects/{pid}/damage-lab-setup")
    assert response.status_code == 200
    assert response.json()["experiment"] is None
    assert response.json()["diagnostics"][0]["path"].endswith("." + missing)
    experiment = json.loads((CASES / "machinery-hit.experiment.json").read_text(encoding="utf-8"))
    preview = alice.post(f"/api/projects/{pid}/damage-lab-preview", json={
        "revision": 1, "condition_id": "normal", "experiment": experiment})
    assert preview.status_code == 422
    assert preview.json()["detail"][0]["path"].endswith("." + missing)
    assert alice.get(f"/api/projects/{pid}/damage-lab-runs").json() == []
