"""Native SpringSharp import: one first-class design, the original bytes archived.

A `.sship` / `.dat` file read with ``native=true`` is not mapped into a legacy
projection. The pure codec reads the original 3.0 *and* 2.0 layouts, and the
accepted native initializer turns the source into one authoritative
``ship_design`` with its own condition, projection and reconciled ledger. The
original bytes are still archived verbatim as the evidence.

What these tests pin is the minimum gap: a source import creates a native project
directly, with complete original parameters, an automatic ledger, and no legacy
physical placeholder row. The omitted flag keeps the legacy mapping path exactly
as it always was, so the two readers can be told apart and neither is changed by
the other.

The 3.0 fixture is the real encoded synthetic declaration
``tools/plimsoll/tests/fixtures/sps3b3-synthetic.json`` written back through the
codec. The 2.0 fixture is built the way the core's own legacy test builds it:
the fresh-window record block, truncated to the 136-record legacy layout, with
the legacy stern checkbox at index 16 set true.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plimsoll import sps_file_io
from plimsoll_web.models import CalculationRun, Project, ProjectRevision


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tools" / "plimsoll" / "tests" / "fixtures" / "sps3b3-synthetic.json"

PREVIEW = "/api/projects/sship-preview"
IMPORT = "/api/projects/sship-import"
NATIVE_METHOD = "native-sship-import-v1"
SHIP_NAME = "Synthetic armour and layout import; no real vessel"


def declaration() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8-sig"))


def real_source() -> bytes:
    return sps_file_io.dumps(declaration())


def legacy_2_0_source() -> bytes:
    records = list(sps_file_io.DEFAULT_RECORDS[:136])
    records[16] = "True"
    return ("SpringSharp Version 2.0\n" + "\n".join(records) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def request_body(data: bytes, *, native, filename: str = "test.sship", **extra) -> dict:
    body = {"filename": filename, "content_base64": base64.b64encode(data).decode("ascii")}
    if native is not None:
        body["native"] = native
    body.update(extra)
    return body


def preview(browser, data: bytes, *, native: bool, filename: str = "test.sship") -> dict:
    response = browser.post(PREVIEW, json=request_body(data, native=native, filename=filename))
    assert response.status_code == 200, response.text
    return response.json()


def save(browser, data: bytes, *, native: bool = True, name: str | None = None,
         filename: str = "test.sship", source_sha256: str | None = None):
    extra = {"source_sha256": digest(data) if source_sha256 is None else source_sha256}
    if name is not None:
        extra["name"] = name
    return browser.post(IMPORT, json=request_body(data, native=native, filename=filename, **extra))


def table_sizes(engine) -> dict[str, int]:
    with Session(engine) as db:
        return {
            "projects": db.scalar(select(func.count()).select_from(Project)),
            "revisions": db.scalar(select(func.count()).select_from(ProjectRevision)),
            "runs": db.scalar(select(func.count()).select_from(CalculationRun)),
        }


def codes(response) -> set[str]:
    return {item.get("code") for item in response.json()["detail"]}


# --- a native preview describes the source, not a projection -----------------

def test_native_preview_reports_the_source_and_the_two_counts(alice):
    data = real_source()
    answer = preview(alice, data, native=True, filename="Test Ship.sship")
    migration = answer["migration"]

    assert migration["method_version"] == NATIVE_METHOD
    # The two counts are kept apart: the canonical design fields and the raw block.
    assert migration["parameter_count"] == 222
    assert migration["raw_record_count"] == 280
    assert migration["source"]["filename"] == "Test Ship.sship"
    assert migration["source"]["sha256"] == digest(data)
    assert migration["source"]["version"] == "3.0"
    assert migration["source"]["header"] == "SpringSharp Version 3.0"
    assert migration["source"]["encoding"] == "utf-8"
    assert migration["source"]["byte_length"] == len(data)

    # A native answer is not the legacy projection: no disposition table and no
    # 142/80 counts, and never a second copy of the document.
    assert "fields" not in migration
    assert "counts" not in migration
    assert "project" not in answer
    assert answer["name"] == SHIP_NAME


def test_native_preview_writes_nothing(alice, engine):
    before = table_sizes(engine)
    assert before == {"projects": 0, "revisions": 0, "runs": 0}

    assert preview(alice, real_source(), native=True)["migration"]["parameter_count"] == 222
    assert table_sizes(engine) == before


# --- a native import creates a native project directly -----------------------

def test_native_import_creates_a_native_project_at_revision_one(alice, engine):
    response = save(alice, real_source(), name="  迁移的测试舰  ")
    assert response.status_code == 201, response.text
    view = response.json()

    assert view["revision"] == 1
    project = view["project"]
    assert project["schema"] == "plimsoll-project-1"
    assert project["ship_design"]["schema"] == "plimsoll-ship-design-1"
    assert project["ship_design"]["condition_id"]
    assert isinstance(project["ship_design"]["parameters"], dict)
    # No legacy declaration survives beside a native one.
    assert "sps_3b3_design" not in project
    assert project["geometry"] is None
    assert project["name"] == "迁移的测试舰"
    assert table_sizes(engine) == {"projects": 1, "revisions": 1, "runs": 0}


def test_native_import_archives_the_original_bytes_and_provenance(alice):
    data = real_source()
    view = save(alice, data, filename="Test Ship.sship").json()
    archive = view["project"]["migration"]

    assert archive["schema"] == "plimsoll-sship-migration-1"
    assert archive["source"]["filename"] == "Test Ship.sship"
    assert archive["source"]["sha256"] == digest(data)
    assert archive["source"]["version"] == "3.0"
    assert archive["source"]["header"] == "SpringSharp Version 3.0"
    assert archive["source"]["encoding"] == "utf-8"
    assert archive["source"]["byte_length"] == len(data)
    assert base64.b64decode(archive["original_base64"], validate=True) == data
    assert archive["raw_fields"] == sps_file_io.read(data)["raw_records"]
    assert len(archive["raw_fields"]) == 280
    assert archive["notes"] == declaration()["notes"]


def test_the_archived_bytes_still_read_through_from_migration(alice):
    """The archive is the evidence the future migration reader will re-read."""
    data = real_source()
    archive = save(alice, data).json()["project"]["migration"]
    assert sps_file_io.from_migration(archive) == sps_file_io.loads(data)


def test_native_import_creates_no_legacy_placeholder_or_manual_mass(alice):
    project = save(alice, real_source()).json()["project"]

    groups = project.get("weight_groups") or []
    items = [item for group in groups if isinstance(group, dict)
             for item in (group.get("items") or []) if isinstance(item, dict)]
    assert items, "a native import must carry its own ledger"
    assert all(str(item.get("id", "")).startswith("sd-") for item in items)
    assert "misc.unknown" not in json.dumps(project)
    # The only condition is the design's own; no imported working placeholder.
    assert [c["id"] for c in project["loading_conditions"]] == [
        project["ship_design"]["condition_id"]]


def test_a_native_run_completes_the_design_without_geometry_or_cg(alice, worker_once):
    view = save(alice, real_source()).json()
    project_id = view["project_id"]
    condition = view["project"]["ship_design"]["condition_id"]

    queued = alice.post(f"/api/projects/{project_id}/runs", json={
        "revision": 1, "condition_id": condition, "options": {}})
    assert queued.status_code == 202, queued.text
    assert worker_once()
    result = alice.get(f"/api/runs/{queued.json()['id']}").json()

    assert result["status"] in ("completed", "partial"), result
    stages = result["result"]["stages"]
    assert stages["ship_design"]["requested"] is True
    assert stages["ship_design"]["status"] == "completed"
    assert stages["geometry"]["status"] == "not_requested"
    assert stages["loading"]["status"] == "not_requested"


def test_the_source_name_is_kept_when_no_name_is_confirmed(alice):
    view = save(alice, real_source()).json()
    assert view["project"]["name"] == SHIP_NAME


# --- the legacy 2.0 layout is accepted natively ------------------------------

def test_a_legacy_2_0_source_is_accepted_natively(alice):
    data = legacy_2_0_source()
    migration = preview(alice, data, native=True, filename="old.dat")["migration"]

    assert migration["source"]["version"] == "2.0"
    assert migration["source"]["header"] == "SpringSharp Version 2.0"
    assert migration["raw_record_count"] == 136
    assert migration["parameter_count"] == 222
    # The native answer never invents a 2.0 source-line index.
    assert "fields" not in migration

    project = save(alice, data, filename="old.dat").json()["project"]
    assert project["ship_design"]["schema"] == "plimsoll-ship-design-1"
    assert project["migration"]["source"]["version"] == "2.0"
    assert project["migration"]["raw_fields"] == sps_file_io.read(data)["raw_records"]
    assert len(project["migration"]["raw_fields"]) == 136
    # The source version is archived, not claimed as physical viability.
    assert project["geometry"] is None
    assert "misc.unknown" not in json.dumps(project)


def test_a_1x_header_is_refused_exactly_as_the_codec_refuses_it(alice, engine):
    before = table_sizes(engine)
    response = alice.post(PREVIEW, json=request_body(
        b"SpringStyle Version 1.1\n", native=True))

    assert response.status_code == 422
    assert codes(response) == {"sship.version_unsupported"}
    assert {item["path"] for item in response.json()["detail"]} == {"$.header"}
    assert table_sizes(engine) == before


# --- the legacy reader is untouched when the flag is omitted -----------------

def test_the_legacy_reader_is_unchanged_when_native_is_omitted(alice):
    data = real_source()

    omitted = alice.post(PREVIEW, json=request_body(data, native=None))
    assert omitted.status_code == 200, omitted.text
    migration = omitted.json()["migration"]
    assert len(migration["fields"]) == 280
    assert migration["counts"] == {"mapped": 142, "preserved": 80,
                                   "duplicate": 25, "reserved": 33}
    assert "parameter_count" not in migration

    explicit_false = alice.post(PREVIEW, json=request_body(data, native=False))
    assert explicit_false.json()["migration"]["counts"]["mapped"] == 142

    # The legacy path still rejects a 2.0 layout; only the native reader accepts it.
    legacy = alice.post(PREVIEW, json=request_body(legacy_2_0_source(), native=None))
    assert legacy.status_code == 422


def test_a_stale_digest_cannot_be_saved_natively(alice, engine):
    before = table_sizes(engine)
    response = save(alice, real_source(), source_sha256=hashlib.sha256(b"nothing").hexdigest())

    assert response.status_code == 409
    assert codes(response) == {"sship.source_mismatch"}
    assert table_sizes(engine) == before
    assert alice.get("/api/projects").json() == []
