"""Reading a SpringSharp 3.0 source file through the workspace API.

A `.sship` file is somebody's ship, not a Plimsoll backup: 280 positional
fields in the order the original 3b3 writer used, then an operator's notes. The
workspace therefore offers two authenticated endpoints in front of the one core
importer — a preview that describes the file, and a save that re-reads the very
same bytes before it writes anything.

What these tests pin is the boundary, not the mapping. A preview writes no rows
and returns no converted project; a save is refused unless the bytes it was
given still hash to the digest the reader was last shown; a rejected request
leaves the library exactly as it was; the saved project is a fresh owned UUID at
revision 1 that carries the original bytes, all 280 fields and the notes as an
archive; and a SpringSharp request is behind exactly the same origin, CSRF and
body middleware as any other write.

The fixtures below are synthetic and labelled as such. They are built against
the recovered 3b3 field positions in chat
outputs/Plimsoll-sship-migration-2026-10-15/format-evidence.json, where field
index ``i`` is the ``i + 2``-th line of the file. No real ship file is involved
and none is claimed.
"""

from __future__ import annotations

import base64
import hashlib
import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plimsoll import project_io
from plimsoll_web.models import CalculationRun, Project, ProjectRevision


PREVIEW = "/api/projects/sship-preview"
IMPORT = "/api/projects/sship-import"

FIELD_COUNT = 280
HEADER = "SpringSharp Version 3.0"
COMMA_HEADER = "SpringSharp Version 3,0"
LEGACY_HEADER = "SpringSharp Version 2.0"
NOTES = "first operator note\r\nsecond operator note"
MIB = 1024 * 1024

# Recovered 3b3 positions, named here so the fixture is readable.
SHIP_NAME, SHIP_COUNTRY, SHIP_TYPE = 0, 1, 2
HULL_SCALE, LWL, MOULDED_BEAM, DRAUGHT_NORM, BLOCK_NORM = 3, 13, 14, 15, 17
BEAM_AT_BULGES = 127

#: The browser's bound on the raw source, restated here so the endpoint's own
#: bound is not taken on trust.
MAX_RAW_BYTES = MIB


def fields(values: dict[int, str] | None = None) -> list[str]:
    """280 positional records, the ones a real file always states, and blanks.

    Every other position is left empty, which is unknown rather than zero. A
    fixture that filled all 280 would assert the core's entire registry; this one
    states only the fields the design names as mapped.
    """
    records = [""] * FIELD_COUNT
    records[SHIP_NAME] = "SYNTHETIC TEST SHIP"
    records[SHIP_COUNTRY] = "Testland"
    records[SHIP_TYPE] = "Test Cruiser"
    records[HULL_SCALE] = "0"          # feet; 1 would be metres
    records[LWL] = "300"
    records[MOULDED_BEAM] = "40"
    records[DRAUGHT_NORM] = "15"
    records[BLOCK_NORM] = "0.55"
    records[BEAM_AT_BULGES] = "42"
    for index, raw in (values or {}).items():
        records[index] = raw
    return records


def sship_bytes(*, header: str = HEADER, values: dict[int, str] | None = None,
                notes: str | None = NOTES, count: int = FIELD_COUNT) -> bytes:
    """A synthetic SpringSharp 3.0 file: header, 280 records, notes tail."""
    records = fields(values)[:count]
    lines = [header, *records]
    if notes is not None:
        lines.extend(notes.split("\r\n"))
    return "\r\n".join(lines).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def send(browser, endpoint: str, data: bytes, filename: str = "test.sship",
         headers: dict[str, str] | None = None, **extra):
    body = {"filename": filename, "content_base64": base64.b64encode(data).decode("ascii")}
    body.update(extra)
    return browser.post(endpoint, json=body, headers=headers)


def preview_of(browser, data: bytes, filename: str = "test.sship") -> dict:
    response = send(browser, PREVIEW, data, filename)
    assert response.status_code == 200, response.text
    return response.json()


def save(browser, data: bytes, *, source_sha256: str | None = None,
         filename: str = "test.sship", **extra):
    return send(browser, IMPORT, data, filename,
                source_sha256=digest(data) if source_sha256 is None else source_sha256,
                **extra)


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


SYNTHETIC = sship_bytes()


# --- a preview describes the file and writes nothing -------------------------

def test_preview_describes_a_supported_file_without_returning_a_project(alice):
    preview = preview_of(alice, SYNTHETIC, "Test Ship.sship")

    # The standard backup preview: identity, shape and counts, and never a second
    # copy of a document that may be a megabyte long.
    assert preview["source_id"]
    assert preview["name"] == "SYNTHETIC TEST SHIP"
    # The source draft has never been saved anywhere, so it carries the canonical
    # default revision; the saved project is what becomes revision 1.
    assert preview["source_revision"] == 0
    assert preview["geometry_kind"] is None
    assert set(preview["counts"]) == {"loading_conditions", "weight_groups", "weight_items",
                                     "damage_scenarios", "compartments", "openings"}
    assert isinstance(preview["diagnostics"], list)
    assert "project" not in preview

    migration = preview["migration"]
    assert migration["method_version"]
    assert set(migration) == {"method_version", "source", "fields", "counts",
                              "diagnostics", "limitations"}
    assert isinstance(migration["diagnostics"], list)
    assert isinstance(migration["limitations"], list)


def test_preview_reports_the_exact_bytes_that_were_sent(alice):
    preview = preview_of(alice, SYNTHETIC)
    source = preview["migration"]["source"]

    assert source["filename"] == "test.sship"
    assert source["sha256"] == digest(SYNTHETIC)
    assert len(source["sha256"]) == 64
    assert source["byte_length"] == len(SYNTHETIC)
    assert source["header"] == HEADER
    assert source["version"].startswith("3")
    assert source["decimal_separator"] == "."
    assert "utf" in source["encoding"].lower()


def test_preview_lists_every_field_with_its_own_line_and_raw_text(alice):
    preview = preview_of(alice, SYNTHETIC)
    listed = preview["migration"]["fields"]

    assert len(listed) == FIELD_COUNT
    assert [item["index"] for item in listed] == list(range(FIELD_COUNT))
    source_lines = SYNTHETIC.decode("utf-8").split("\r\n")
    for field in listed:
        assert set(field) == {"index", "line", "name", "raw", "disposition",
                              "destinations", "reason"}
        # Line 1 is the header, so field i is line i + 2.
        assert field["line"] == field["index"] + 2
        assert field["raw"] == source_lines[field["line"] - 1]
        assert isinstance(field["name"], str) and field["name"]
        assert field["disposition"] in {"mapped", "preserved", "duplicate", "reserved"}
        assert isinstance(field["destinations"], list)
        # Every field says what became of it; the words are the core's own.
        assert field["reason"] is not None

    assert listed[SHIP_NAME]["raw"] == "SYNTHETIC TEST SHIP"
    assert listed[SHIP_NAME]["destinations"] == ["$.name"]
    assert isinstance(listed[SHIP_NAME]["reason"], str)
    assert listed[LWL]["disposition"] == "mapped"
    # 247..279 were padding in the original reader, never parameters.
    assert [field["disposition"] for field in listed[247:]] == ["reserved"] * 33


def test_the_field_counts_add_up_to_the_two_hundred_and_eighty_fields(alice):
    counts = preview_of(alice, SYNTHETIC)["migration"]["counts"]
    dispositions = {name: count for name, count in counts.items() if name != "total"}
    assert set(dispositions) == {"mapped", "preserved", "duplicate", "reserved"}
    assert sum(dispositions.values()) == FIELD_COUNT
    assert dispositions["reserved"] == 33


def test_preview_writes_nothing(alice, engine):
    before = table_sizes(engine)
    assert before == {"projects": 0, "revisions": 0, "runs": 0}

    assert send(alice, PREVIEW, SYNTHETIC).status_code == 200
    assert table_sizes(engine) == before


def test_a_comma_decimal_header_is_also_supported(alice):
    data = sship_bytes(header=COMMA_HEADER, values={BLOCK_NORM: "0,55"})
    preview = preview_of(alice, data)
    source = preview["migration"]["source"]

    assert source["header"] == COMMA_HEADER
    assert source["decimal_separator"] == ","
    # The same text means the same thing under either separator.
    assert preview["name"] == "SYNTHETIC TEST SHIP"


def test_a_legacy_version_is_refused_with_diagnostics(alice, engine):
    before = table_sizes(engine)
    response = send(alice, PREVIEW, sship_bytes(header=LEGACY_HEADER))

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail and all({"code", "severity", "path", "message"} <= set(item) for item in detail)
    assert any("version" in str(item["code"]).lower() for item in detail)
    assert paths(response) == {"$.header"}
    assert table_sizes(engine) == before


def test_a_file_that_stops_before_the_two_hundred_and_eighty_fields_is_refused(alice, engine):
    before = table_sizes(engine)
    response = send(alice, PREVIEW, sship_bytes(notes=None, count=FIELD_COUNT - 1))

    assert response.status_code == 422
    assert codes(response)
    assert table_sizes(engine) == before


# --- the request itself ------------------------------------------------------

def test_base64_that_is_not_base64_is_refused(alice, engine):
    before = table_sizes(engine)
    response = alice.post(PREVIEW, json={"filename": "test.sship",
                                         "content_base64": "this is not base64 !!"})
    assert response.status_code == 422
    assert table_sizes(engine) == before


def test_a_source_over_one_mebibyte_is_refused_as_too_large(alice, engine):
    before = table_sizes(engine)
    oversized = sship_bytes(notes="x" * (MAX_RAW_BYTES + 1))
    assert len(oversized) > MAX_RAW_BYTES

    for endpoint, extra in ((PREVIEW, {}), (IMPORT, {"source_sha256": digest(oversized)})):
        response = send(alice, endpoint, oversized, **extra)
        assert response.status_code == 413
    assert table_sizes(engine) == before


def test_an_envelope_over_the_raw_bound_is_refused_before_it_is_decoded(alice, engine):
    """The encoded form is bounded on its own, so nothing large is decoded."""
    before = table_sizes(engine)
    encoded_bound = 4 * ((MAX_RAW_BYTES + 2) // 3)
    response = alice.post(PREVIEW, json={
        "filename": "test.sship", "content_base64": "A" * (encoded_bound + 4)})

    assert response.status_code == 413
    assert table_sizes(engine) == before


def test_a_filename_is_a_bare_name_and_never_a_path(alice, engine):
    before = table_sizes(engine)
    for filename in ("../../secrets.sship", "C:\\Windows\\System32\\ship.sship",
                     "folder/ship.sship", "..", ""):
        response = send(alice, PREVIEW, SYNTHETIC, filename)
        assert response.status_code == 422, filename
    assert table_sizes(engine) == before


def test_both_endpoints_refuse_extra_request_fields(alice, engine):
    before = table_sizes(engine)
    fields_ = {
        "project": {"schema": "plimsoll-project-1"},
        "mapping": {"hull.length_m": 91.44},
        "counts": {"weight_items": 9},
    }
    for key, value in fields_.items():
        assert send(alice, PREVIEW, SYNTHETIC, **{key: value}).status_code == 422, key
        assert save(alice, SYNTHETIC, **{key: value}).status_code == 422, key
    assert table_sizes(engine) == before


def test_a_digest_that_is_not_a_digest_is_refused_by_the_request_shape(alice, engine):
    before = table_sizes(engine)
    for value in ("", "not-a-digest", digest(SYNTHETIC).upper(), digest(SYNTHETIC) + "0"):
        response = save(alice, SYNTHETIC, source_sha256=value)
        assert response.status_code == 422, value
    assert table_sizes(engine) == before


@pytest.mark.parametrize("endpoint", (PREVIEW, IMPORT))
def test_a_ship_source_requires_a_signed_in_owner(client, engine, endpoint):
    before = table_sizes(engine)
    extra = {"source_sha256": digest(SYNTHETIC)} if endpoint == IMPORT else {}
    response = client.post(endpoint, json={
        "filename": "test.sship", "content_base64": base64.b64encode(SYNTHETIC).decode(), **extra})
    assert response.status_code == 401
    assert table_sizes(engine) == before


@pytest.mark.parametrize("endpoint", (PREVIEW, IMPORT))
def test_a_ship_source_requires_the_readers_csrf_token(alice, engine, endpoint):
    before = table_sizes(engine)
    response = send(alice, endpoint, SYNTHETIC, headers={"X-CSRF-Token": ""},
                    **({"source_sha256": digest(SYNTHETIC)} if endpoint == IMPORT else {}))
    assert response.status_code == 403
    assert table_sizes(engine) == before


@pytest.mark.parametrize("endpoint", (PREVIEW, IMPORT))
def test_a_ship_source_requires_a_trusted_origin(alice, engine, endpoint):
    before = table_sizes(engine)
    response = send(alice, endpoint, SYNTHETIC, headers={"Origin": "http://evil.example"},
                    **({"source_sha256": digest(SYNTHETIC)} if endpoint == IMPORT else {}))
    assert response.status_code == 403
    assert table_sizes(engine) == before


@pytest.mark.parametrize("endpoint", (PREVIEW, IMPORT))
def test_a_ship_source_over_eight_mib_is_refused_by_the_same_middleware(alice, engine, endpoint):
    before = table_sizes(engine)
    payload = "A" * (8 * MIB)
    extra = {"source_sha256": digest(SYNTHETIC)} if endpoint == IMPORT else {}
    body = {"filename": "test.sship", "content_base64": payload, **extra}
    response = alice.post(endpoint, content=json.dumps(body),
                          headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert table_sizes(engine) == before


# --- saving the source -------------------------------------------------------

def test_saving_creates_a_new_project_owned_by_the_reader(alice, engine):
    response = save(alice, SYNTHETIC, name="  迁移的测试舰  ")
    assert response.status_code == 201
    view = response.json()

    assert view["revision"] == 1
    assert view["project"]["id"] == view["project_id"]
    assert view["project"]["revision"] == 1
    assert view["project"]["name"] == "迁移的测试舰"
    assert view["project"]["schema"] == "plimsoll-project-1"
    assert view["project_id"] in {item["project_id"] for item in alice.get("/api/projects").json()}
    assert table_sizes(engine) == {"projects": 1, "revisions": 1, "runs": 0}


def test_the_saved_project_keeps_the_original_file_exactly_as_it_was(alice):
    view = save(alice, SYNTHETIC, filename="Test Ship.sship").json()
    archive = view["project"]["migration"]

    assert archive["source"]["sha256"] == digest(SYNTHETIC)
    assert base64.b64decode(archive["original_base64"], validate=True) == SYNTHETIC
    assert archive["raw_fields"] == fields()
    notes = archive["notes"]
    assert "first operator note" in notes and "second operator note" in notes
    # Evidence, not computed results: nothing about the new project was invented.
    assert view["project"]["geometry"] is None


def test_the_archive_survives_the_canonical_round_trip(alice):
    """Export and reimport is the existing JSON flow; it must carry the archive."""
    view = save(alice, SYNTHETIC).json()
    exported = alice.get(f"/api/projects/{view['project_id']}").json()["project"]

    restored = project_io.normalize_project({**exported, "id": "backup", "revision": 4})
    assert restored["migration"]["source"]["sha256"] == digest(SYNTHETIC)
    assert base64.b64decode(restored["migration"]["original_base64"], validate=True) == SYNTHETIC


def test_the_source_name_is_kept_when_no_name_is_confirmed(alice):
    view = save(alice, SYNTHETIC).json()
    assert view["project"]["name"] == "SYNTHETIC TEST SHIP"


def test_a_blank_confirmed_name_is_refused(alice, engine):
    before = table_sizes(engine)
    for name in ("   ", "　 \n "):
        assert save(alice, SYNTHETIC, name=name).status_code == 422
    assert table_sizes(engine) == before


def test_a_stale_digest_cannot_be_saved(alice, engine):
    """The bytes are reparsed and rehashed; a preview of another file cannot ride along."""
    other = sship_bytes(values={SHIP_NAME: "SYNTHETIC SECOND SHIP"})
    stale = preview_of(alice, other)["migration"]["source"]["sha256"]
    before = table_sizes(engine)

    response = save(alice, SYNTHETIC, source_sha256=stale)

    assert response.status_code == 409
    assert codes(response) == {"sship.source_mismatch"}
    assert table_sizes(engine) == before
    assert alice.get("/api/projects").json() == []


def test_a_digest_of_something_that_was_never_previewed_is_refused(alice, engine):
    before = table_sizes(engine)
    response = save(alice, SYNTHETIC, source_sha256=hashlib.sha256(b"nothing").hexdigest())

    assert response.status_code == 409
    assert codes(response) == {"sship.source_mismatch"}
    assert table_sizes(engine) == before


def test_a_save_is_bound_to_its_own_bytes_not_to_the_last_preview(alice):
    """Content binding, not a session: the digest the reader holds names the file."""
    first = sship_bytes(values={SHIP_NAME: "SYNTHETIC FIRST SHIP"})
    second = sship_bytes(values={SHIP_NAME: "SYNTHETIC SECOND SHIP"})
    preview_of(alice, first)
    preview_of(alice, second)

    view = save(alice, first, source_sha256=digest(first)).json()
    assert view["project"]["migration"]["source"]["sha256"] == digest(first)
    assert view["project"]["name"] == "SYNTHETIC FIRST SHIP"


def test_two_saves_of_one_source_are_two_separate_projects(alice, engine):
    first = save(alice, SYNTHETIC).json()
    second = save(alice, SYNTHETIC).json()

    assert first["project_id"] != second["project_id"]
    assert len(alice.get("/api/projects").json()) == 2
    assert table_sizes(engine)["revisions"] == 2


def test_an_imported_project_is_private_to_its_reader(alice, bob, project_id, engine):
    original = alice.get(f"/api/projects/{project_id}").json()

    view = save(alice, SYNTHETIC).json()
    assert bob.get(f"/api/projects/{view['project_id']}").status_code == 404
    assert all(item["project_id"] != view["project_id"] for item in bob.get("/api/projects").json())
    # A SpringSharp source is input only: nothing of the reader's is overwritten.
    assert alice.get(f"/api/projects/{project_id}").json() == original


def test_an_import_starts_no_calculation(alice, engine):
    view = save(alice, SYNTHETIC).json()
    assert alice.get(f"/api/projects/{view['project_id']}/runs").json() == []
    assert table_sizes(engine)["runs"] == 0