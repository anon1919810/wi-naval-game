"""Native ship design web routes: auth, purity, creation, save and frozen exports.

These tests drive the real routes against the real pure core and the real encoded
source bytes: a fresh ``ship_design`` template runs without geometry or a CG, a
source import adapts actual bytes, a conflicting direct save is refused, and a
saved native run's exports stay frozen and owner-scoped.
"""
import base64
import json
from pathlib import Path

from plimsoll import analysis, sps_file_io

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tools" / "plimsoll" / "tests" / "fixtures" / "sps3b3-synthetic.json"


def declaration():
    return json.loads(FIXTURE.read_text(encoding="utf-8-sig"))


def real_source_base64():
    return base64.b64encode(sps_file_io.dumps(declaration())).decode()


def create_native(alice, name="原生设计"):
    created = alice.post("/api/projects", json={"template": "ship_design", "name": name})
    assert created.status_code == 201, created.text
    return created.json()


def adapted_native(alice, view, filename="source.sship"):
    imported = alice.post("/api/design/import-preview", json={
        "project": view["project"], "filename": filename, "content_base64": real_source_base64()})
    assert imported.status_code == 200, imported.text
    return imported.json()["project"]


def test_design_routes_require_auth_csrf_and_origin(client, alice):
    assert client.get("/api/design/catalog").status_code == 401
    catalog = alice.get("/api/design/catalog")
    assert catalog.status_code == 200 and catalog.json()["fields"]

    draft = alice.post("/api/projects", json={"template": None, "name": "空白"}).json()["project"]
    token = alice.headers.pop("X-CSRF-Token")
    try:
        assert alice.post("/api/design/initialize", json={"project": draft}).status_code == 403
    finally:
        alice.headers["X-CSRF-Token"] = token
    assert alice.post("/api/design/initialize", json={"project": draft},
                      headers={"Origin": "http://evil.example"}).status_code == 403


def test_native_initialize_and_preview_are_pure(alice, project_id):
    before = alice.get(f"/api/projects/{project_id}").json()

    initialized = alice.post("/api/design/initialize", json={"project": before["project"]})
    assert initialized.status_code == 200, initialized.text
    reply = initialized.json()
    assert reply["project"]["ship_design"]["schema"] == "plimsoll-ship-design-1"
    assert reply["project"]["ship_design"]["condition_id"]
    assert isinstance(reply["design"]["parameters"], dict)

    previewed = alice.post("/api/design/preview", json={
        "project": reply["project"],
        "command": {"kind": "set_parameter", "name": "ship_name", "value": "预览名称"}})
    assert previewed.status_code == 200, previewed.text
    assert previewed.json()["design"]["parameters"]["ship_name"] == "预览名称"
    assert previewed.json()["project"]["ship_design"]["parameters"]["ship_name"] == "预览名称"

    assert alice.get(f"/api/projects/{project_id}").json() == before


def test_source_import_preview_reads_real_encoded_bytes(alice, project_id):
    before = alice.get(f"/api/projects/{project_id}").json()
    imported = alice.post("/api/design/import-preview", json={
        "project": before["project"], "filename": "test.sship", "content_base64": real_source_base64()})
    assert imported.status_code == 200, imported.text
    reply = imported.json()
    assert reply["project"]["ship_design"]["schema"] == "plimsoll-ship-design-1"
    assert reply["design"]["parameters"]["length_waterline"] == 180

    broken = alice.post("/api/design/import-preview", json={
        "project": before["project"], "filename": "test.sship", "content_base64": "not base64!!"})
    assert broken.status_code == 422
    assert alice.get(f"/api/projects/{project_id}").json() == before


def test_fresh_native_project_runs_without_geometry_or_cg(alice, worker_once):
    view = create_native(alice, "全新原生")
    project_id = view["project_id"]
    project = view["project"]
    assert project["ship_design"]["schema"] == "plimsoll-ship-design-1"
    assert project["geometry"] is None
    conditions = [c for c in project["loading_conditions"] if "definition" not in c]
    assert conditions and conditions[0]["id"] == project["ship_design"]["condition_id"]

    queued = alice.post(f"/api/projects/{project_id}/runs", json={
        "revision": 1, "condition_id": conditions[0]["id"], "options": {}})
    assert queued.status_code == 202, queued.text
    assert worker_once()
    result = alice.get(f"/api/runs/{queued.json()['id']}").json()
    assert result["status"] in ("completed", "partial"), result
    stages = result["result"]["stages"]
    assert stages["loading"]["status"] == "not_requested"
    assert stages["geometry"]["status"] == "not_requested"
    assert stages["ship_design"]["requested"] is True


def test_protected_projection_and_dual_declaration_saves_are_refused(alice):
    view = create_native(alice, "受保护设计")
    project_id = view["project_id"]
    adapted = adapted_native(alice, view)
    assert alice.put(f"/api/projects/{project_id}", json={
        "base_revision": 1, "project": adapted}).status_code == 200

    current = alice.get(f"/api/projects/{project_id}").json()
    project, revision = current["project"], current["revision"]
    key = next(k for k in ("lwl_m", "beam_m", "loa_m") if project["hull"].get(k) is not None)
    project["hull"][key] = project["hull"][key] + 3.0
    conflicted = alice.put(f"/api/projects/{project_id}", json={
        "base_revision": revision, "project": project})
    assert conflicted.status_code == 422, conflicted.text
    assert any(d["code"] == "extension.ship_design.projection_conflict" for d in conflicted.json()["detail"])

    dual = alice.get(f"/api/projects/{project_id}").json()["project"]
    dual["sps_3b3_design"] = declaration()
    assert alice.put(f"/api/projects/{project_id}", json={
        "base_revision": revision, "project": dual}).status_code == 422

    malformed = alice.get(f"/api/projects/{project_id}").json()["project"]
    malformed["ship_design"] = {"schema": "wrong"}
    assert alice.put(f"/api/projects/{project_id}", json={
        "base_revision": revision, "project": malformed}).status_code == 422


def test_native_run_exports_are_owned_and_frozen(alice, bob, worker_once, monkeypatch):
    view = create_native(alice, "原生运行")
    project_id = view["project_id"]
    adapted = adapted_native(alice, view)
    assert alice.put(f"/api/projects/{project_id}", json={
        "base_revision": 1, "project": adapted}).status_code == 200

    condition = adapted["ship_design"]["condition_id"]
    queued = alice.post(f"/api/projects/{project_id}/runs", json={
        "revision": 2, "condition_id": condition, "options": {}})
    assert queued.status_code == 202, queued.text
    run_id = queued.json()["id"]
    assert worker_once()
    result = alice.get(f"/api/runs/{run_id}").json()
    assert result["status"] == "completed", result
    assert result["result"]["stages"]["ship_design"]["status"] == "completed"
    assert bob.get(f"/api/runs/{run_id}").status_code == 404

    project = alice.get(f"/api/projects/{project_id}").json()["project"]
    project["ship_design"]["parameters"]["ship_name"] = "New revision only"
    assert alice.put(f"/api/projects/{project_id}", json={
        "base_revision": 2, "project": project}).status_code == 200

    monkeypatch.setattr(analysis, "compute_project",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("export recomputed")))
    for format in ("txt", "rtf", "ssr", "sship"):
        assert bob.get(f"/api/runs/{run_id}/export?format={format}").status_code == 404
        response = alice.get(f"/api/runs/{run_id}/export?format={format}")
        assert response.status_code == 200, response.text
        assert "New revision only" not in response.text
        if format in ("ssr", "rtf"):
            assert response.text.startswith("{\\rtf1")
        if format == "sship":
            assert sps_file_io.loads(response.content)["parameters"]["length_waterline"] == 180
