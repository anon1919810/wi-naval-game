"""Independent acceptance tests for the strict core verification report unit.

Scope: :mod:`plimsoll.verification_report` only. These tests do not build cases,
oracles or a runner; they pin the canonical report contract, the destination
ownership rules, the exclusive directory lock and the derived-format-before-
authoritative-JSON publication protocol.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import pytest  # noqa: E402

from plimsoll import verification_report as vr  # noqa: E402


SHA_A = "a" * 64
SHA_B = "b" * 64
RUN_A = "11111111-2222-4333-8444-555555555555"
RUN_B = "99999999-8888-4777-8666-555555555555"


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

def source_files():
    return [
        {"module": "plimsoll.hull", "path": "C:/pkg/plimsoll/hull.py",
         "sha256": SHA_A},
        {"module": "plimsoll.verification_report",
         "path": "C:/pkg/plimsoll/verification_report.py", "sha256": SHA_B},
    ]


def test_lock_metadata_failure_retains_io_cause_and_unknown_lock(tmp_path, monkeypatch):
    def failed_fstat(descriptor):
        raise OSError(5, "injected lock metadata failure")
    monkeypatch.setattr(vr.os, "fstat", failed_fstat)
    with pytest.raises(vr.PublishError, match="lock metadata failure"):
        with vr.output_session(tmp_path):
            pytest.fail("failed lock metadata must prevent calculations")
    lock = tmp_path / vr.LOCK_NAME
    assert lock.exists()
    assert lock.read_bytes() == b""
    # Identity was unavailable, so an unknown lock is left for explicit recovery.
    assert not any(p.name.endswith(".tmp") for p in tmp_path.iterdir())


def a_check(name="volume_error", passed=True, required=True, measured=-1.25e-06,
            expected=0.0, tolerance=1e-09, unit="m3", reason=None):
    return {"name": name, "passed": passed, "required": required,
            "measured": measured, "expected": expected, "tolerance": tolerance,
            "unit": unit, "reason": reason}


def a_row(case_id="scale-tank-1", state="passed", assertion_passed=True,
          reason=None, checks=None):
    return {"id": case_id, "state": state,
            "assertion_passed": assertion_passed, "reason": reason,
            "checks": [a_check()] if checks is None else checks}


def a_report(cases=None, *, run_id=RUN_A, generation=0, state="complete",
             suite="quick", requested=None, consistent=True,
             input_manifest=SHA_A, **extra):
    rows = [a_row()] if cases is None else list(cases)
    report = {
        "schema": vr.SCHEMA,
        "run_id": run_id,
        "generation": generation,
        "state": state,
        "suite": suite,
        "requested_case_ids": [row["id"] for row in rows] if requested is None
        else list(requested),
        "cases": rows,
        "source_identity": {
            "files": source_files(),
            "method_versions": {"stationed_hull": "hull-1"},
            "consistent": consistent,
        },
        "input_manifest_sha256": input_manifest,
    }
    report.update(extra)
    return report


@pytest.fixture()
def out_dir(tmp_path):
    directory = tmp_path / "evidence"
    directory.mkdir()
    return directory


def read_strict(path: Path):
    """Reader-side strict JSON: reject NaN/Infinity tokens and 1e309 overflow."""
    def constant(name):
        raise AssertionError(f"non-finite JSON token {name} in {path}")

    def number(text):
        value = float(text)
        if value in (float("inf"), float("-inf")) or value != value:
            raise AssertionError(f"non-finite JSON number {text} in {path}")
        return value

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=constant,
                      parse_float=number)


def csv_lines(path: Path):
    return path.read_text(encoding="utf-8").splitlines()


def read_csv_report(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    identity = lines[1].rstrip("\r\n")
    rows = list(csv.DictReader(io.StringIO("".join(lines[2:]), newline="")))
    return identity, rows


def assert_no_temporary_files(directory: Path, *, keep=()):
    leaked = sorted(p.name for p in directory.iterdir()
                    if p.name.startswith(vr.TEMP_PREFIX)
                    and p.name not in set(keep))
    assert leaked == []


def assert_no_lock(directory: Path):
    assert not (directory / vr.LOCK_NAME).exists()


# --------------------------------------------------------------------------
# 1. positive report shapes
# --------------------------------------------------------------------------

def test_valid_complete_report_validates_and_exits_zero():
    report = a_report()
    vr.validate_report(report)
    assert vr.exit_code_for(report) == 0


def test_valid_partial_report_validates_but_does_not_exit_zero():
    report = a_report(state="partial",
                      generation=2,
                      cases=[a_row("scale-tank-1"),
                             a_row("mirror-tank-port", state="pending",
                                   assertion_passed=False,
                                   reason="not started yet", checks=[])])
    vr.validate_report(report)
    assert vr.exit_code_for(report) == 1


def test_expected_model_boundary_row_passes_without_physical_badge():
    boundary = a_row(
        case_id="flood-pair-300s-0p125",
        checks=[
            a_check(name="status_flag_matches", unit="",
                    measured="model-limit", expected="model-limit"),
            a_check(name="model_limit_detected", unit=""),
            a_check(name="external_measurement_available", passed=False,
                    required=False, measured=None, expected=None, tolerance=None,
                    unit="", reason="no external experimental input"),
        ],
    )
    report = a_report([boundary], raw_solver={
        "flood-pair-300s-0p125": {"model_applicable": False,
                                  "stop_reason": "model-limit"}})
    vr.validate_report(report)
    # The boundary assertion itself passes: no physical/numerical badge is
    # inferred from the unavailable external measurement.
    assert vr.exit_code_for(report) == 0
    assert report["raw_solver"]["flood-pair-300s-0p125"]["model_applicable"] is False


def test_unknown_optional_fields_are_allowed():
    report = a_report(metadata={"started_utc": "2026-10-10T00:00:00Z",
                               "nested": {"elapsed_s": [0.1, 0.2]}},
                      time_total_s=1.25, performance={"median_s": 1.0})
    vr.validate_report(report)


def test_pending_and_not_started_rows_are_legal_shapes():
    report = a_report(
        cases=[a_row("a", state="pending", assertion_passed=False,
                     reason="queued", checks=[]),
               a_row("b", state="not_started", assertion_passed=False,
                     reason="total deadline reached", checks=[])],
        state="partial")
    vr.validate_report(report)
    assert vr.exit_code_for(report) == 1


# --------------------------------------------------------------------------
# 2. schema / flag rejection
# --------------------------------------------------------------------------

def test_wrong_schema_rejected():
    report = a_report()
    report["schema"] = "plimsoll-analysis-1"
    with pytest.raises(ValueError):
        vr.validate_report(report)


@pytest.mark.parametrize("field", [
    "schema", "run_id", "generation", "state", "suite",
    "requested_case_ids", "cases", "source_identity", "input_manifest_sha256",
])
def test_missing_top_level_field_rejected(field):
    report = a_report()
    del report[field]
    with pytest.raises(ValueError):
        vr.validate_report(report)


@pytest.mark.parametrize("field", [
    "id", "state", "assertion_passed", "reason", "checks",
])
def test_missing_row_field_rejected(field):
    report = a_report([a_row()])
    del report["cases"][0][field]
    with pytest.raises(ValueError):
        vr.validate_report(report)


@pytest.mark.parametrize("field", [
    "name", "passed", "required", "measured", "expected", "tolerance",
    "unit", "reason",
])
def test_missing_check_field_rejected(field):
    check = a_check()
    del check[field]
    with pytest.raises(ValueError):
        vr.validate_report(a_report([a_row(checks=[check])]))


def test_boolean_flags_must_be_exact_bool():
    for path, value in (("assertion_passed", 1),
                        ("assertion_passed", "true"),
                        ("source_consistent", 1)):
        report = a_report()
        if path == "source_consistent":
            report["source_identity"]["consistent"] = value
        else:
            report["cases"][0][path] = value
        with pytest.raises(ValueError):
            vr.validate_report(report)
    report = a_report()
    report["cases"][0]["checks"][0]["required"] = "yes"
    with pytest.raises(ValueError):
        vr.validate_report(report)


def test_generation_must_be_nonnegative_int_and_not_bool():
    for value in (True, -1, 1.0, "0", None):
        report = a_report()
        report["generation"] = value
        with pytest.raises(ValueError):
            vr.validate_report(report)


def test_run_id_must_be_a_uuid_string():
    for value in ("", "not-a-uuid", 17, None):
        report = a_report()
        report["run_id"] = value
        with pytest.raises(ValueError):
            vr.validate_report(report)


def test_state_and_suite_enumerations():
    report = a_report()
    report["state"] = "done"
    with pytest.raises(ValueError):
        vr.validate_report(report)
    report = a_report()
    report["suite"] = "nightly"
    with pytest.raises(ValueError):
        vr.validate_report(report)


def test_row_state_enumeration():
    row = a_row(state="not-run")
    with pytest.raises(ValueError):
        vr.validate_report(a_report([row]))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"),
                                   1e309])
def test_non_finite_numbers_rejected_anywhere(value):
    report = a_report(metadata={"performance": {"elapsed_s": value}})
    with pytest.raises(ValueError):
        vr.validate_report(report)
    report = a_report([a_row(checks=[a_check(measured=value)])])
    with pytest.raises(ValueError):
        vr.validate_report(report)


def test_non_json_values_rejected():
    report = a_report(raw_solver={"hull": object()})
    with pytest.raises(ValueError):
        vr.validate_report(report)
    report = a_report()
    report["cases"][0]["checks"][0]["measured"] = {1: "int key"}
    with pytest.raises(ValueError):
        vr.validate_report(report)


def test_circular_structure_rejected():
    report = a_report()
    report["metadata"] = {}
    report["metadata"]["self"] = report["metadata"]
    with pytest.raises(ValueError):
        vr.validate_report(report)


def test_source_identity_requirements():
    report = a_report()
    report["source_identity"]["files"] = []
    with pytest.raises(ValueError):
        vr.validate_report(report)
    report = a_report()
    report["source_identity"]["files"][0]["sha256"] = "abc"
    with pytest.raises(ValueError):
        vr.validate_report(report)
    report = a_report()
    report["source_identity"]["files"][0]["path"] = ""
    with pytest.raises(ValueError):
        vr.validate_report(report)
    report = a_report()
    report["source_identity"]["consistent"] = None
    with pytest.raises(ValueError):
        vr.validate_report(report)
    report = a_report()
    report["input_manifest_sha256"] = SHA_A.upper()
    with pytest.raises(ValueError):
        vr.validate_report(report)


# --------------------------------------------------------------------------
# 3. row coverage
# --------------------------------------------------------------------------

def test_empty_case_list_rejected():
    with pytest.raises(ValueError):
        vr.validate_report(a_report([], requested=[]))


def test_empty_requested_list_rejected():
    report = a_report([a_row()], requested=[])
    with pytest.raises(ValueError):
        vr.validate_report(report)


def test_duplicate_requested_ids_rejected():
    report = a_report([a_row("a"), a_row("b")], requested=["a", "b", "a"])
    with pytest.raises(ValueError):
        vr.validate_report(report)


def test_duplicate_rows_rejected():
    report = a_report([a_row("a"), a_row("a", checks=[a_check(name="other")])])
    with pytest.raises(ValueError):
        vr.validate_report(report)


def test_missing_row_rejected():
    report = a_report([a_row("a")], requested=["a", "b"])
    with pytest.raises(ValueError):
        vr.validate_report(report)


def test_unrequested_extra_row_rejected():
    report = a_report([a_row("a"), a_row("c")], requested=["a"])
    with pytest.raises(ValueError):
        vr.validate_report(report)


# --------------------------------------------------------------------------
# 4. honest failure evidence
# --------------------------------------------------------------------------

@pytest.mark.parametrize("state", ["failed", "timeout", "error"])
def test_worker_failure_rows_require_an_explicit_reason(state):
    with pytest.raises(ValueError):
        vr.validate_report(a_report([a_row(state=state, assertion_passed=False,
                                          checks=[])]))
    row = a_row(state=state, assertion_passed=False,
                reason=f"worker {state}", checks=[])
    report = a_report([row], state="partial")
    vr.validate_report(report)
    assert vr.exit_code_for(report) == 1


def test_unavailable_measurement_requires_a_reason():
    check = a_check(passed=None, measured=None, tolerance=None)
    failed_row = a_row(checks=[check], state="failed",
                       assertion_passed=False, reason="case failed")
    with pytest.raises(ValueError):
        vr.validate_report(a_report([failed_row]))
    check["reason"] = "residual missing for level 3"
    vr.validate_report(a_report([a_row(checks=[check], state="failed",
                                       assertion_passed=False,
                                       reason="case failed")]))


def test_failed_check_requires_a_reason():
    check = a_check(passed=False)
    failed_row = a_row(checks=[check], state="failed",
                       assertion_passed=False, reason="case failed")
    with pytest.raises(ValueError):
        vr.validate_report(a_report([failed_row]))
    check["reason"] = "measured 1.4e-3 exceeds tolerance 1e-9"
    vr.validate_report(a_report([a_row(checks=[check], state="failed",
                                       assertion_passed=False,
                                       reason="case failed")]))


@pytest.mark.parametrize("mutation", [
    {"state": "partial"},
    {"consistent": False},
    {"assertion_passed": False},
    {"required_check_fails": True},
    {"required_check_none": True},
    {"no_required_checks": True},
    {"no_checks": True},
])
def test_exit_code_is_never_falsely_zero(mutation):
    report = a_report()
    if "state" in mutation:
        report["state"] = mutation["state"]
    if "consistent" in mutation:
        report["source_identity"]["consistent"] = mutation["consistent"]
    if mutation.get("assertion_passed") is False:
        report["cases"][0]["assertion_passed"] = False
    if mutation.get("required_check_fails"):
        report["cases"][0]["checks"][0].update(
            passed=False, reason="drift", measured=1.5)
    if mutation.get("required_check_none"):
        report["cases"][0]["checks"][0].update(
            passed=None, measured=None, tolerance=None, reason="not computed")
    if mutation.get("no_required_checks"):
        report["cases"][0]["checks"][0]["required"] = False
    if mutation.get("no_checks"):
        report["cases"][0]["checks"] = []
    assert vr.exit_code_for(report) == 1


def test_self_asserted_top_level_pass_is_not_trusted():
    report = a_report()
    report["passed"] = True
    report["status"] = "PASS"
    assert vr.exit_code_for(report) == 0
    # ... but a failing required check cannot be hidden by any self-assertion.
    report = a_report()
    report["cases"][0]["checks"][0]["passed"] = False
    report["cases"][0]["checks"][0]["reason"] = "real failure"
    report["passed"] = True
    assert vr.exit_code_for(report) == 1


def test_malformed_reports_exit_one_not_raise():
    for bad in (None, [], "report", 5, {"schema": "other"},
                {"schema": vr.SCHEMA}):
        assert vr.exit_code_for(bad) == 1


def test_invalid_report_is_never_written(tmp_path):
    directory = tmp_path / "evidence"
    directory.mkdir()
    report = a_report()
    report["cases"][0]["assertion_passed"] = "yes"
    with pytest.raises(ValueError):
        vr.write_report(report, directory)
    assert list(directory.iterdir()) == []


# --------------------------------------------------------------------------
# 5. rendering of the three formats
# --------------------------------------------------------------------------

def test_write_report_returns_exact_paths_and_identical_identity(out_dir):
    report = a_report(generation=3, state="partial",
                      cases=[a_row("scale-tank-1"),
                             a_row("mirror-tank-port", state="pending",
                                   assertion_passed=False, reason="queued",
                                   checks=[])])
    paths = vr.write_report(report, out_dir)
    assert set(paths) == {"json", "csv", "md"}
    for key, path in paths.items():
        assert isinstance(path, Path)
        assert path.parent == out_dir
        assert path.is_file()
    assert paths["json"].name == "core-verification.json"
    assert paths["csv"].name == "core-verification.csv"
    assert paths["md"].name == "core-verification.md"

    published = read_strict(paths["json"])
    assert published["run_id"] == RUN_A
    assert published["generation"] == 3

    csv_header = csv_lines(paths["csv"])[0]
    markdown_header = csv_lines(paths["md"])[0]
    assert csv_header == vr.CSV_MARKER
    assert markdown_header == vr.MARKDOWN_MARKER
    for text in (paths["csv"].read_text(encoding="utf-8"),
                 paths["md"].read_text(encoding="utf-8")):
        assert RUN_A in text
        assert "generation: 3" in text or "generation=3" in text
        assert "partial" in text


def test_csv_carries_check_facts_and_reasons_with_newlines(out_dir):
    reason = "line one\nline two, with comma | and \\ backslash"
    report = a_report([
        a_row("scale-tank-1", checks=[a_check(reason=reason,
                                             measured=-1.25e-06,
                                             expected=0.0, tolerance=1e-09,
                                             unit="m3")])])
    paths = vr.write_report(report, out_dir)
    identity, rows = read_csv_report(paths["csv"])
    assert f"run_id={RUN_A}" in identity and "generation=0" in identity
    data = [row for row in rows if row.get("case_id") == "scale-tank-1"]
    assert data, rows
    check = data[0]
    assert check["unit"] == "m3"
    assert json.loads(check["measured"]) == -1.25e-06
    assert json.loads(check["expected"]) == 0.0
    assert json.loads(check["tolerance"]) == 1e-09
    assert check["check_passed"] == "true"
    assert check["check_required"] == "true"
    assert check["check_reason"] == reason


def test_markdown_escapes_cells_reversibly(out_dir):
    reason = "bad | pipe \\\\ backslash\nnewline\rcr"
    report = a_report([a_row("scale-tank-1", checks=[a_check(reason=reason)])])
    paths = vr.write_report(report, out_dir)
    text = paths["md"].read_text(encoding="utf-8")
    assert "|" in text  # the table separator survives
    body = [line for line in text.splitlines()
            if "scale-tank-1" in line and "volume_error" in line]
    assert body, text
    cell = body[0]
    assert "&#124;" in cell and "&#92;" in cell and "&#10;" in cell
    assert "&#13;" in cell
    assert "\r" not in cell
    # unescaping the entities returns the original reason exactly
    restored = (cell.replace("&#92;", "\\").replace("&#124;", "|")
                .replace("&#13;", "\r").replace("&#10;", "\n"))
    assert reason in restored


def test_signed_negative_errors_are_retained_in_every_format(out_dir):
    report = a_report([a_row("flood-single-60s-0p5", checks=[
        a_check(name="volume_conservation", measured=-4.5e-10, expected=0.0,
                tolerance=1e-09, unit="m3"),
        a_check(name="mass_conservation", measured=-2.25e-11, expected=0.0,
                tolerance=1e-10, unit="t"),
    ])])
    paths = vr.write_report(report, out_dir)
    published = read_strict(paths["json"])
    measured = [check["measured"] for check in published["cases"][0]["checks"]]
    assert measured == [-4.5e-10, -2.25e-11]
    assert all(value < 0 for value in measured)
    csv_text = paths["csv"].read_text(encoding="utf-8")
    assert "-4.5e-10" in csv_text and "-2.25e-11" in csv_text
    md_text = paths["md"].read_text(encoding="utf-8")
    assert "-4.5e-10" in md_text and "-2.25e-11" in md_text


def test_missing_values_are_rendered_as_null_not_zero(out_dir):
    report = a_report([a_row("a", state="failed", assertion_passed=False,
                             reason="worker crashed", checks=[
                                 a_check(name="residual", passed=None,
                                         measured=None, expected=None,
                                         tolerance=None, unit="1",
                                         reason="non-finite solver output")])],
                      state="partial")
    paths = vr.write_report(report, out_dir)
    published = read_strict(paths["json"])
    check = published["cases"][0]["checks"][0]
    assert check["measured"] is None and check["passed"] is None
    assert vr.exit_code_for(published) == 1
    assert "null" in paths["csv"].read_text(encoding="utf-8")


def test_every_requested_case_appears_in_the_derived_formats(out_dir):
    rows = [a_row("a", state="timeout", assertion_passed=False,
                  reason="case deadline 180 s exceeded", checks=[]),
            a_row("b", state="not_started", assertion_passed=False,
                  reason="total deadline reached", checks=[]),
            a_row("c")]
    report = a_report(rows, state="partial")
    paths = vr.write_report(report, out_dir)
    for path in (paths["csv"], paths["md"]):
        text = path.read_text(encoding="utf-8")
        for case_id in ("a", "b", "c"):
            assert case_id in text
    assert vr.exit_code_for(read_strict(paths["json"])) == 1


# --------------------------------------------------------------------------
# 6. destination ownership
# --------------------------------------------------------------------------

def test_relative_output_dir_rejected():
    with pytest.raises(ValueError):
        vr.write_report(a_report(), Path("relative/evidence"))


def test_preexisting_user_files_are_rejected_and_preserved(out_dir):
    sentinel = out_dir / "notes.txt"
    sentinel.write_bytes(b"unrelated user bytes\n")
    targets = {
        vr.JSON_NAME: b'{"schema": "something-else", "cases": []}\n',
        vr.CSV_NAME: b"project_id,value\nA,1\n",
        vr.MD_NAME: b"# my own notes\n",
    }
    for name, payload in targets.items():
        path = out_dir / name
        path.write_bytes(payload)
        with pytest.raises(ValueError):
            vr.write_report(a_report(), out_dir)
        assert path.read_bytes() == payload
    assert sentinel.read_bytes() == b"unrelated user bytes\n"
    assert_no_temporary_files(out_dir)


def test_wrong_schema_report_is_not_adopted(out_dir):
    path = out_dir / vr.JSON_NAME
    path.write_bytes(json.dumps({"schema": "plimsoll-core-verification-0",
                                 "run_id": RUN_A}).encode("utf-8"))
    with pytest.raises(ValueError):
        vr.write_report(a_report(), out_dir)
    assert json.loads(path.read_text(encoding="utf-8"))["schema"] == \
        "plimsoll-core-verification-0"


def test_input_project_json_is_refused_with_a_clear_reason(out_dir):
    path = out_dir / vr.JSON_NAME
    project = {"schema": "plimsoll-project-1", "vessel": {"name": "analytic"}}
    path.write_bytes(json.dumps(project).encode("utf-8"))
    with pytest.raises(ValueError, match="project"):
        vr.write_report(a_report(), out_dir)
    assert json.loads(path.read_text(encoding="utf-8"))["schema"] == \
        "plimsoll-project-1"


def test_malformed_ownership_markers_are_refused(out_dir):
    broken = out_dir / vr.CSV_NAME
    broken.write_bytes(b"not,our,header\n1,2,3\n")
    with pytest.raises(ValueError):
        vr.write_report(a_report(), out_dir)
    assert broken.read_bytes() == b"not,our,header\n1,2,3\n"
    md = out_dir / vr.MD_NAME
    md.write_bytes(b"<!-- plimsoll-core-verification-1 --> \xff\xfe truncated")
    with pytest.raises(ValueError):
        vr.write_report(a_report(), out_dir)
    assert md.read_bytes().startswith(b"<!-- plimsoll-core-verification-1 -->")


def test_every_fixed_name_is_preflighted_before_the_first_write(out_dir,
                                                                 monkeypatch):
    calls = []
    real = os.replace

    def spy(src, dst, *args, **kwargs):
        calls.append(str(dst))
        return real(src, dst, *args, **kwargs)

    monkeypatch.setattr(vr.os, "replace", spy)
    (out_dir / vr.JSON_NAME).write_bytes(b"user json\n")
    (out_dir / vr.CSV_NAME).write_bytes(b"user csv\n")
    (out_dir / vr.MD_NAME).write_bytes(b"user md\n")
    with pytest.raises(ValueError) as error:
        vr.write_report(a_report(), out_dir)
    message = str(error.value)
    assert vr.JSON_NAME in message and vr.CSV_NAME in message
    assert vr.MD_NAME in message
    assert calls == []
    assert_no_temporary_files(out_dir)


def test_unrelated_files_survive_a_successful_publication(out_dir):
    sentinel = out_dir / "sentinel.bin"
    sentinel.write_bytes(bytes(range(256)))
    stray_tmp = out_dir / (vr.TEMP_PREFIX + "someone-else.tmp")
    stray_tmp.write_bytes(b"not ours\n")
    paths = vr.write_report(a_report(), out_dir)
    assert sentinel.read_bytes() == bytes(range(256))
    assert stray_tmp.read_bytes() == b"not ours\n"
    for path in paths.values():
        assert path.is_file()
    assert_no_temporary_files(out_dir, keep=(stray_tmp.name,))
    assert_no_lock(out_dir)


def test_own_reports_are_updatable_including_partial_and_other_generation(out_dir):
    first = a_report(generation=0, state="partial", run_id=RUN_A)
    vr.write_report(first, out_dir)
    second = a_report(generation=1, state="complete", run_id=RUN_B,
                      cases=[a_row("scale-tank-1"), a_row("mirror-tank-port")])
    vr.write_report(second, out_dir)
    published = vr.read_published(out_dir)
    assert published["report"]["run_id"] == RUN_B
    assert published["passing"] is True
    assert published["identity_match"] is True


def test_mixed_generation_derived_files_are_not_read_as_a_pass(out_dir):
    vr.write_report(a_report(generation=1, state="partial"), out_dir)
    stale_csv = (out_dir / vr.CSV_NAME).read_bytes()
    stale_md = (out_dir / vr.MD_NAME).read_bytes()
    vr.write_report(a_report(generation=2, state="complete"), out_dir)
    # Restore only the derived formats: the authoritative JSON is new, the
    # derived formats are one generation behind.
    (out_dir / vr.CSV_NAME).write_bytes(stale_csv)
    (out_dir / vr.MD_NAME).write_bytes(stale_md)
    published = vr.read_published(out_dir)
    assert published["report"]["generation"] == 2
    assert published["report"]["state"] == "complete"
    assert vr.exit_code_for(published["report"]) == 0
    assert published["identity_match"] is False
    assert published["passing"] is False


def test_stale_run_id_in_derived_files_is_not_read_as_a_pass(out_dir):
    vr.write_report(a_report(run_id=RUN_B), out_dir)
    stale_csv = (out_dir / vr.CSV_NAME).read_bytes()
    stale_md = (out_dir / vr.MD_NAME).read_bytes()
    vr.write_report(a_report(run_id=RUN_A), out_dir)
    # same generation, different run: identity must be compared on run_id too
    (out_dir / vr.CSV_NAME).write_bytes(stale_csv)
    (out_dir / vr.MD_NAME).write_bytes(stale_md)
    published = vr.read_published(out_dir)
    assert published["report"]["run_id"] == RUN_A
    assert published["identity_match"] is False
    assert published["passing"] is False


def test_reader_probe_rejects_incomplete_authoritative_json(out_dir):
    vr.write_report(a_report(state="partial", generation=4), out_dir)
    published = vr.read_published(out_dir)
    assert published["exit_code"] == 1
    assert published["passing"] is False
    assert published["present"] is True


def test_reader_probe_rejects_missing_derived_file(out_dir):
    vr.write_report(a_report(), out_dir)
    (out_dir / vr.CSV_NAME).unlink()
    published = vr.read_published(out_dir)
    assert published["present"] is False
    assert published["passing"] is False


# --------------------------------------------------------------------------
# 7. symlink / junction / reparse rejection
# --------------------------------------------------------------------------

def _is_reparse(path: Path) -> bool:
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def test_symlinked_report_file_is_rejected(out_dir, monkeypatch):
    victim = out_dir / "victim.json"
    victim.write_bytes(b"untouched\n")
    link = out_dir / vr.JSON_NAME
    try:
        os.symlink(victim, link)
    except (OSError, NotImplementedError, AttributeError) as error:
        pytest.skip(f"symlink creation unsupported here: {error}")
    with pytest.raises(ValueError):
        vr.write_report(a_report(), out_dir)
    assert victim.read_bytes() == b"untouched\n"


def test_symlinked_output_directory_is_rejected(out_dir):
    real = out_dir / "real"
    real.mkdir()
    link = out_dir / "linked"
    try:
        os.symlink(real, link, target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError) as error:
        pytest.skip(f"directory symlink unsupported here: {error}")
    with pytest.raises(ValueError):
        vr.write_report(a_report(), link)
    with pytest.raises(ValueError):
        with vr.output_session(link):
            pass
    assert list(real.iterdir()) == []


def test_junction_ancestor_is_rejected(out_dir):
    target = out_dir / "target"
    target.mkdir()
    junction = out_dir / "junction"
    if _is_reparse(junction) if junction.exists() else False:
        pytest.skip("unexpected pre-existing reparse point")
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True, text=True)
    if result.returncode != 0 or not junction.exists():
        pytest.skip(f"junction creation unsupported here: {result.stderr}")
    nested = junction / "nested"
    with pytest.raises(ValueError):
        vr.write_report(a_report(), nested)
    with pytest.raises(ValueError):
        with vr.output_session(nested):
            pass
    assert list(target.iterdir()) == []


# --------------------------------------------------------------------------
# 8. exclusive output session
# --------------------------------------------------------------------------

HOLDER_SCRIPT = """
import os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from plimsoll import verification_report as vr

directory = Path(sys.argv[2])
with vr.output_session(directory):
    (directory / 'pid.txt').write_text(str(os.getpid()), encoding='utf-8')
    (directory / 'held.txt').write_text('first process bytes', encoding='utf-8')
    (directory / 'ready.txt').write_text('ready', encoding='utf-8')
    time.sleep(float(sys.argv[3]))
(directory / 'done.txt').write_text('released', encoding='utf-8')
"""


def test_real_concurrent_owner_fails_fast(out_dir):
    holder = subprocess.Popen(
        [sys.executable, "-B", "-c", HOLDER_SCRIPT, str(TOOLS), str(out_dir),
         "6"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8")
    try:
        ready = out_dir / "ready.txt"
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            if ready.exists():
                break
            if holder.poll() is not None:
                pytest.fail(f"holder died: {holder.communicate()}")
            time.sleep(0.05)
        assert ready.exists(), "holder never reached the barrier"
        lock = out_dir / vr.LOCK_NAME
        lock_bytes = lock.read_bytes()
        lock_owner = json.loads(lock_bytes.decode("utf-8"))
        # This interpreter is launched through a venv shim, so the owner pid
        # is the one the holder reports for itself, not Popen.pid.
        holder_pid = int((out_dir / "pid.txt").read_text(encoding="utf-8"))
        assert lock_owner["pid"] == holder_pid
        assert holder_pid != os.getpid()
        assert lock_owner["schema"] == vr.LOCK_SCHEMA

        held = (out_dir / "held.txt").read_bytes()
        with pytest.raises(ValueError):
            with vr.output_session(out_dir):
                pytest.fail("the second owner must not enter")
        with pytest.raises(ValueError):
            vr.write_report(a_report(), out_dir)
        assert (out_dir / "held.txt").read_bytes() == held
        assert lock.read_bytes() == lock_bytes
        assert_no_temporary_files(out_dir)
    finally:
        holder.wait(timeout=60)
    assert holder.returncode == 0
    assert (out_dir / "done.txt").exists()
    assert_no_lock(out_dir)
    with vr.output_session(out_dir) as held_directory:
        assert Path(held_directory) == out_dir
    assert_no_lock(out_dir)


def test_foreign_lock_file_is_never_deleted(out_dir):
    foreign = out_dir / vr.LOCK_NAME
    foreign.write_bytes(b'{"pid": 999999, "token": "other"}\n')
    with pytest.raises(ValueError):
        with vr.output_session(out_dir):
            pass
    assert foreign.read_bytes() == b'{"pid": 999999, "token": "other"}\n'


def test_stale_lock_fails_explicitly_without_liveness_guessing(out_dir):
    stale = out_dir / vr.LOCK_NAME
    stale.write_bytes(json.dumps({"schema": vr.LOCK_SCHEMA, "pid": 999999,
                                  "token": str(uuid.uuid4())}).encode("utf-8"))
    with pytest.raises(ValueError) as error:
        with vr.output_session(out_dir):
            pass
    assert str(vr.LOCK_NAME) in str(error.value)
    assert stale.exists()


def test_same_process_second_session_is_rejected(out_dir):
    with vr.output_session(out_dir):
        with pytest.raises(ValueError):
            with vr.output_session(out_dir):
                pass
        vr.write_report(a_report(), out_dir)
    assert_no_lock(out_dir)
    assert (out_dir / vr.JSON_NAME).is_file()


def test_session_preflights_ownership_before_any_calculation(out_dir):
    (out_dir / vr.JSON_NAME).write_bytes(b"user json\n")
    ran = []
    with pytest.raises(ValueError):
        with vr.output_session(out_dir):
            ran.append(True)
    assert ran == []
    assert_no_lock(out_dir)
    assert (out_dir / vr.JSON_NAME).read_bytes() == b"user json\n"


def test_session_preflight_failure_still_releases_the_lock(out_dir):
    (out_dir / vr.MD_NAME).write_bytes(b"user md\n")
    for _ in range(2):
        with pytest.raises(ValueError):
            with vr.output_session(out_dir):
                pass
    assert_no_lock(out_dir)


# --------------------------------------------------------------------------
# 9. publication order and failure isolation
# --------------------------------------------------------------------------

class _Collector:
    def __init__(self, calls):
        self.calls = calls

    @property
    def targets(self):
        return [str(dst) for _, dst in self.calls]

    def assert_same_directory_temporaries(self, directory):
        for src, dst in self.calls:
            assert src.parent == directory, (src, dst)
            assert src.name.startswith(vr.TEMP_PREFIX), src


@contextlib.contextmanager
def replace_spy(monkeypatch, fail_for=None):
    calls = []
    real = os.replace

    def spy(src, dst, *args, **kwargs):
        calls.append((Path(src), Path(dst)))
        if fail_for is not None and str(dst).endswith(fail_for):
            raise OSError(5, "injected replace failure", str(dst))
        return real(src, dst, *args, **kwargs)

    monkeypatch.setattr(vr.os, "replace", spy)
    yield _Collector(calls)


def test_publication_order_is_csv_then_markdown_then_json(out_dir, monkeypatch):
    with replace_spy(monkeypatch) as spy:
        vr.write_report(a_report(), out_dir)
    assert [Path(target).name for target in spy.targets] == [
        vr.CSV_NAME, vr.MD_NAME, vr.JSON_NAME]
    spy.assert_same_directory_temporaries(out_dir)


def test_every_snapshot_republishes_in_the_same_order(out_dir, monkeypatch):
    with replace_spy(monkeypatch) as spy:
        with vr.output_session(out_dir):
            for generation in range(3):
                state = "complete" if generation == 2 else "partial"
                vr.write_report(a_report(generation=generation, state=state),
                                out_dir)
    assert [Path(target).name for target in spy.targets] == [
        vr.CSV_NAME, vr.MD_NAME, vr.JSON_NAME] * 3


def test_authoritative_json_is_replaced_last_for_every_generation(
        out_dir, monkeypatch):
    observed = []
    real = os.replace

    def spy(src, dst, *args, **kwargs):
        if str(dst).endswith(vr.JSON_NAME):
            current = out_dir / vr.JSON_NAME
            previous = (json.loads(current.read_text(encoding="utf-8"))
                        ["generation"] if current.exists() else None)
            observed.append(previous)
        return real(src, dst, *args, **kwargs)

    monkeypatch.setattr(vr.os, "replace", spy)
    with vr.output_session(out_dir):
        for generation in range(3):
            vr.write_report(a_report(generation=generation,
                                     state="complete" if generation == 2
                                     else "partial"), out_dir)
    # At every JSON replacement the authoritative file still held the previous
    # generation: the JSON is never promoted before the derived pair.
    assert observed == [None, 0, 1]


def test_partial_then_final_publication_identity_and_probe(out_dir):
    with vr.output_session(out_dir) as directory:
        vr.write_report(a_report(generation=0, state="partial",
                                 cases=[a_row("a", state="pending",
                                              assertion_passed=False,
                                              reason="queued", checks=[])]),
                        directory)
        published = vr.read_published(directory)
        assert published["report"]["state"] == "partial"
        assert published["identity_match"] is True
        assert published["passing"] is False
        partial_bytes = {name: (directory / name).read_bytes() for name in
                         (vr.JSON_NAME, vr.CSV_NAME, vr.MD_NAME)}
        vr.write_report(a_report(generation=1, state="partial",
                                 cases=[a_row("a"),
                                        a_row("b", state="pending",
                                              assertion_passed=False,
                                              reason="queued", checks=[])]),
                        directory)
        published = vr.read_published(directory)
        assert published["report"]["generation"] == 1
        assert published["passing"] is False
        vr.write_report(a_report(generation=2, state="complete",
                                 cases=[a_row("a"), a_row("b")]), directory)
    published = vr.read_published(out_dir)
    assert published["report"]["state"] == "complete"
    assert published["report"]["generation"] == 2
    assert published["exit_code"] == 0
    assert published["passing"] is True
    assert published["identity_match"] is True
    assert (out_dir / vr.JSON_NAME).read_bytes() != partial_bytes[vr.JSON_NAME]


def test_json_replace_failure_keeps_previous_authoritative_bytes(
        out_dir, monkeypatch):
    vr.write_report(a_report(generation=1, state="partial"), out_dir)
    previous = {name: (out_dir / name).read_bytes()
                for name in (vr.JSON_NAME, vr.CSV_NAME, vr.MD_NAME)}
    with replace_spy(monkeypatch, fail_for=vr.JSON_NAME):
        with pytest.raises(ValueError):
            vr.write_report(a_report(generation=2, state="complete"), out_dir)
    # the authoritative JSON still reports the previous partial generation
    assert (out_dir / vr.JSON_NAME).read_bytes() == previous[vr.JSON_NAME]
    published = vr.read_published(out_dir)
    assert published["report"]["generation"] == 1
    assert published["report"]["state"] == "partial"
    assert published["exit_code"] == 1
    assert published["passing"] is False
    assert_no_temporary_files(out_dir)
    assert_no_lock(out_dir)


def test_markdown_replace_failure_leaves_json_untouched(out_dir, monkeypatch):
    vr.write_report(a_report(generation=1, state="partial"), out_dir)
    previous = {name: (out_dir / name).read_bytes()
                for name in (vr.JSON_NAME, vr.CSV_NAME, vr.MD_NAME)}
    with replace_spy(monkeypatch, fail_for=vr.MD_NAME):
        with pytest.raises(ValueError):
            vr.write_report(a_report(generation=2, state="complete"), out_dir)
    assert (out_dir / vr.MD_NAME).read_bytes() == previous[vr.MD_NAME]
    assert (out_dir / vr.JSON_NAME).read_bytes() == previous[vr.JSON_NAME]
    # the already replaced derived file is newer; readers must reject the mix
    published = vr.read_published(out_dir)
    assert published["identity_match"] is False
    assert published["passing"] is False
    assert_no_temporary_files(out_dir)


def test_csv_replace_failure_leaves_every_target_untouched(out_dir, monkeypatch):
    vr.write_report(a_report(), out_dir)
    previous = {name: (out_dir / name).read_bytes()
                for name in (vr.JSON_NAME, vr.CSV_NAME, vr.MD_NAME)}
    with replace_spy(monkeypatch, fail_for=vr.CSV_NAME):
        with pytest.raises(ValueError):
            vr.write_report(a_report(generation=9, run_id=RUN_B), out_dir)
    for name, payload in previous.items():
        assert (out_dir / name).read_bytes() == payload
    assert_no_temporary_files(out_dir)


@contextlib.contextmanager
def failing_stream(monkeypatch, stage):
    """Inject a failure at the exact stdlib call the writer uses."""
    real_factory = tempfile.NamedTemporaryFile
    hits = []

    class _Stream:
        def __init__(self, stream):
            self._stream = stream
            self.name = stream.name

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._stream.close()
            return False

        def write(self, data):
            hits.append("write")
            raise OSError(28, "injected write failure", self.name)

        def flush(self):
            hits.append("flush")
            return self._stream.flush()

        def fileno(self):
            hits.append("fileno")
            return self._stream.fileno()

    def factory(*args, **kwargs):
        stream = real_factory(*args, **kwargs)
        if stage == "write":
            return _Stream(stream)
        if stage == "flush":
            raise OSError(28, "injected flush failure", "factory")
        return stream

    monkeypatch.setattr(vr.tempfile, "NamedTemporaryFile", factory)
    yield _Collector(hits)


def test_write_failure_preserves_bytes_and_cleans_only_own_temporary(
        out_dir, monkeypatch):
    vr.write_report(a_report(), out_dir)
    previous = {name: (out_dir / name).read_bytes()
                for name in (vr.JSON_NAME, vr.CSV_NAME, vr.MD_NAME)}
    foreign_tmp = out_dir / (vr.TEMP_PREFIX + "other-run.tmp")
    foreign_tmp.write_bytes(b"another process's temporary\n")
    with failing_stream(monkeypatch, "write") as hits:
        with pytest.raises(ValueError):
            vr.write_report(a_report(generation=2), out_dir)
    assert "write" in hits.calls
    # The writer takes the created file's identity from its own descriptor
    # before writing, so the only descriptor access is that one; what matters
    # is that a failed write is never followed by a flush (the fsync stage).
    assert "flush" not in hits.calls
    assert hits.calls == ["fileno", "write"]
    for name, payload in previous.items():
        assert (out_dir / name).read_bytes() == payload
    assert foreign_tmp.read_bytes() == b"another process's temporary\n"
    leaked = [p.name for p in out_dir.iterdir()
              if p.name.startswith(vr.TEMP_PREFIX)
              and p.name != foreign_tmp.name]
    assert leaked == []


def test_fsync_failure_preserves_bytes_and_cleans_temporary(out_dir,
                                                            monkeypatch):
    vr.write_report(a_report(), out_dir)
    previous = {name: (out_dir / name).read_bytes()
                for name in (vr.JSON_NAME, vr.CSV_NAME, vr.MD_NAME)}
    real_fsync = os.fsync
    hits = []

    def spy(fd):
        hits.append(fd)
        raise OSError(5, "injected fsync failure")

    monkeypatch.setattr(vr.os, "fsync", spy)
    with pytest.raises(ValueError):
        vr.write_report(a_report(generation=2), out_dir)
    assert hits, "the product must fsync its temporary file"
    assert vr.os.fsync is spy
    monkeypatch.setattr(vr.os, "fsync", real_fsync)
    for name, payload in previous.items():
        assert (out_dir / name).read_bytes() == payload
    assert_no_temporary_files(out_dir)


def test_temporary_creation_failure_is_reported_without_partial_output(
        out_dir, monkeypatch):
    def factory(*args, **kwargs):
        raise OSError(13, "injected temporary creation failure")

    monkeypatch.setattr(vr.tempfile, "NamedTemporaryFile", factory)
    with pytest.raises(ValueError):
        vr.write_report(a_report(), out_dir)
    assert list(out_dir.iterdir()) == []


def test_publication_error_keeps_the_primary_cause_and_names_progress(
        out_dir, monkeypatch):
    with replace_spy(monkeypatch, fail_for=vr.MD_NAME):
        with pytest.raises(ValueError) as error:
            vr.write_report(a_report(), out_dir)
    message = str(error.value)
    assert vr.CSV_NAME in message and vr.JSON_NAME in message


def test_no_temporary_files_leak_on_success(out_dir):
    with vr.output_session(out_dir):
        for generation in range(3):
            vr.write_report(a_report(generation=generation), out_dir)
    assert_no_temporary_files(out_dir)
    assert_no_lock(out_dir)
    remaining = sorted(p.name for p in out_dir.iterdir())
    assert remaining == [vr.CSV_NAME, vr.JSON_NAME, vr.MD_NAME]


def test_session_body_failure_still_releases_the_lock(out_dir):
    with pytest.raises(RuntimeError):
        with vr.output_session(out_dir):
            raise RuntimeError("calculation crashed")
    assert_no_lock(out_dir)
    # the directory is immediately reusable
    with vr.output_session(out_dir):
        pass
    assert_no_lock(out_dir)


def test_written_json_is_strictly_parseable_with_rejecting_readers(out_dir):
    vr.write_report(a_report(), out_dir)
    text = (out_dir / vr.JSON_NAME).read_text(encoding="utf-8")
    assert "NaN" not in text and "Infinity" not in text
    parsed = read_strict(out_dir / vr.JSON_NAME)
    assert parsed["schema"] == vr.SCHEMA


def test_two_runs_in_one_directory_do_not_confuse_the_reader(out_dir):
    with vr.output_session(out_dir) as directory:
        vr.write_report(a_report(run_id=RUN_A, generation=0, state="partial"),
                        directory)
    with vr.output_session(out_dir) as directory:
        vr.write_report(a_report(run_id=RUN_B, generation=0, state="complete"),
                        directory)
    published = vr.read_published(out_dir)
    assert published["report"]["run_id"] == RUN_B
    assert published["identity_match"] is True
    assert published["passing"] is True
