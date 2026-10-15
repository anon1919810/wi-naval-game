"""Behavioral guards and real-process containment of offline verification."""
import copy
import json
import math
from pathlib import Path
import sys
import time

import pytest

from plimsoll import verification as v
from plimsoll.verification_cases import build_cases
from plimsoll.verification_report import exit_code_for, validate_report


@pytest.fixture(scope="module")
def control():
    case = build_cases("quick")[1]
    row = v.execute_case(case)
    assert row["assertion_passed"] is True, row
    return case, row


def test_actual_positive_control_and_literal_inputs(control):
    case, row = control
    assert row["id"] == case["id"]
    assert row["state"] == "passed"
    assert row["call_audit"]
    assert all(c["unchanged"] is True for c in row["call_audit"])
    assert row["source_consistent"] is True
    assert row["raw"]["solved"]["converged"] is True
    json.dumps(row, allow_nan=False)


@pytest.mark.parametrize("path,bad", [
    ("converged", False), ("converged", None), ("converged", 1),
    ("validity.complete", False), ("validity.model_applicable", "true"),
    ("mode", "prescribed_heel"),
    ("residuals.scaled.volume", math.nan),
    ("residuals.scaled.volume", math.inf),
    ("residuals.scaled.volume", 1e-3),
    ("residuals.scaled.longitudinal", None),
])
def test_raw_guard_rejects_false_missing_nonboolean_nonfinite(control, path, bad):
    raw = copy.deepcopy(control[1]["raw"]["solved"])
    parts = path.split(".")
    owner = raw
    for part in parts[:-1]:
        owner = owner[part]
    owner[parts[-1]] = bad
    assert v._equilibrium_problems(raw)


@pytest.mark.parametrize("path", ["converged", "validity", "residuals"])
def test_missing_required_evidence_is_rejected(control, path):
    raw = copy.deepcopy(control[1]["raw"]["solved"])
    del raw[path]
    assert v._equilibrium_problems(raw)


@pytest.mark.parametrize("field,bad", [("method_version", "foreign-method"),
                                       ("input_fingerprint", "0" * 64)])
def test_equilibrium_return_belongs_to_measured_request(control, field, bad):
    raw = copy.deepcopy(control[1]["raw"]["solved"])
    fingerprint = raw["input_fingerprint"]
    raw[field] = bad
    assert v._equilibrium_problems(raw, expected_fingerprint=fingerprint)


@pytest.mark.parametrize("fault", ["case", "checks", "raw", "required", "tolerance", "unit", "expected",
                                   "case_bool_alias", "audit_digest", "identity_required", "identity_passed", "raw_request"])
def test_parent_rejects_signed_row_without_declared_evidence(control, fault):
    case, actual = control
    row = copy.deepcopy(actual)
    if fault == "case":
        del row["case"]
    elif fault == "checks":
        row["checks"] = [{"name": "unrelated", "passed": True, "required": True}]
    elif fault == "raw":
        del row["raw"]
    elif fault == "required":
        row["checks"][0]["required"] = False
    elif fault == "tolerance":
        row["checks"][0]["tolerance"] = 1000.
    elif fault == "unit":
        row["checks"][0]["unit"] = "foreign-unit"
    elif fault == "expected":
        row["checks"][0]["expected"] = "substituted expectation"
    elif fault == "case_bool_alias":
        row["case"]["inputs"]["scale_factor"] = True
    elif fault == "audit_digest":
        row["call_audit"][0]["after_sha256"] = "0" * 64
    elif fault in ("identity_required", "identity_passed"):
        guard = next(check for check in row["checks"] if check["name"] == "source_and_input_identity")
        guard["required" if fault == "identity_required" else "passed"] = False
    else:
        del row["raw"]["request"]
        row["raw"]["solved"].pop("input_fingerprint", None)
    with pytest.raises(ValueError):
        v._validate_worker_row(row, case, row["source_before"])


def test_parent_accepts_actual_complete_evidence(control):
    case, row = control
    v._validate_worker_row(row, case, row["source_before"])


def test_mesh_transport_request_is_bound_to_actual_call():
    case = next(c for c in build_cases("quick") if c["id"] == "mesh-sta161-vert128")
    row = v.execute_case(case)
    assert row["assertion_passed"] is True, row["reason"]
    v._validate_worker_row(row, case, row["source_before"])
    row["raw"]["request_loading"]["input_fingerprint"] = "0" * 64
    row["raw"]["solved"]["input_fingerprint"] = "0" * 64
    with pytest.raises(ValueError, match="sealed"):
        v._validate_worker_row(row, case, row["source_before"])


def test_rejection_keeps_nonfinite_reason_and_strict_json(control, monkeypatch):
    raw = copy.deepcopy(control[1]["raw"]["solved"])
    raw["residuals"]["scaled"]["volume"] = math.nan
    monkeypatch.setattr(v.stability, "solve_loaded_equilibrium", lambda *a, **k: raw)
    row = v.execute_case(control[0])
    assert row["assertion_passed"] is False
    assert "finite" in json.dumps(row).lower()
    json.dumps(row, allow_nan=False)


def test_per_call_mutation_cannot_be_hidden_by_later_restore():
    payload = {"x": [1.0]}
    audit = []
    def mutate(obj):
        obj["x"][0] = 2.0
        return {}
    def restore(obj):
        obj["x"][0] = 1.0
        return {}
    v._checked_call(mutate, [payload], {}, audit)
    v._checked_call(restore, [payload], {}, audit)
    assert payload == {"x": [1.0]}
    assert len(audit) == 2 and not all(c["unchanged"] for c in audit)
    assert audit[0]["before_sha256"] != audit[0]["after_sha256"]


def test_call_mutation_is_recorded_even_when_function_raises():
    audit = []
    def bad(obj):
        obj["x"] = 2
        raise RuntimeError("intentional")
    with pytest.raises(RuntimeError):
        v._checked_call(bad, [{"x": 1}], {}, audit)
    assert audit[0]["unchanged"] is False


def test_bound_hull_receiver_is_sealed(monkeypatch):
    from plimsoll.geometry import StationedHull
    hull = StationedHull([[0., [[-1., 0.], [1., 0.], [1., 2.], [-1., 2.]]],
                          [.5, [[-1., 0.], [1., 0.], [1., 2.], [-1., 2.]]],
                          [1., [[-1., 0.], [1., 0.], [1., 2.], [-1., 2.]]]])
    def bad(self, *args):
        self.stations = []
        return {}
    monkeypatch.setattr(StationedHull, "integrate", bad)
    audit = []
    v._checked_call(hull.integrate, [0., 1., 0.], {}, audit)
    assert audit[0]["unchanged"] is False


@pytest.fixture(scope="module")
def flood_control():
    case = next(c for c in build_cases("all") if c["kind"] == "flooding.control_cancel")
    row = v.execute_case(case)
    assert row["assertion_passed"] is True, row["reason"]
    return case, row["raw"]


@pytest.mark.parametrize("fault", ["top_conservation", "dt", "initial_time", "final_state", "numeric_flag", "model_flag"])
def test_actual_flooding_result_guards(flood_control, fault):
    case, actual = flood_control
    raw = copy.deepcopy(actual)
    if fault == "top_conservation": raw["volume_conservation_error_m3"] = 10.
    elif fault == "dt": raw["timeline"][1]["actual_dt_s"] = 100.
    elif fault == "initial_time": raw["timeline"][0]["time_s"] = .01
    elif fault == "final_state": raw["final_state"]["time_s"] += .1
    elif fault == "numeric_flag": raw["validity"]["numerical_convergence"] = 1
    else: raw["validity"]["model_applicable"] = None
    assert v._flooding_problems(case, raw)


@pytest.mark.parametrize("fault", ["water_total", "water_mass", "volume_error", "mass_error",
                                   "sea_exchange", "edge_transfer", "initial_volume", "status", "input_identity",
                                   "initial_total", "edge_identity", "edge_endpoint", "edge_mass"])
def test_accepted_flooding_ledger_is_recomputed(flood_control, fault):
    case, actual = flood_control
    raw = copy.deepcopy(actual)
    state = raw["timeline"][1]
    if fault == "water_total": state["total_onboard_water_volume_m3"] += 1.
    elif fault == "water_mass": state["total_onboard_water_mass_t"] += 1.
    elif fault == "volume_error": state["volume_conservation_error_m3"] = -1.
    elif fault == "mass_error": state["mass_conservation_error_t"] = -1.
    elif fault == "sea_exchange": state["sea_exchange_m3"] += 1.
    elif fault == "edge_transfer": state["edge_transfers"][0]["transfer_m3"] += 1.
    elif fault == "initial_volume": raw["timeline"][0]["volumes_m3"]["centre"] += 1.
    elif fault == "status": raw["status"] = "completed"
    elif fault == "input_identity": raw["input_fingerprint"] = "0" * 64
    elif fault == "initial_total": raw["initial_total_water_volume_m3"] += 1.
    elif fault == "edge_identity": state["edge_transfers"][0]["connection_id"] = "undeclared-edge"
    elif fault == "edge_endpoint": state["edge_transfers"][0]["from"] = "foreign-sea"
    else: state["edge_transfers"][0]["transfer_t"] = -1.
    assert v._flooding_problems(case, raw)


def test_requested_liquid_status_cannot_disappear(control):
    raw = copy.deepcopy(control[1]["raw"]["solved"])
    raw.pop("liquids", None)
    assert v._equilibrium_problems(raw, expected_liquids=["declared-tank"])


def test_reverse_signed_transfers_are_valid_and_mass_is_bound():
    case = next(c for c in build_cases("all") if c["id"] == "flooding-control-head-starboard-to-port")
    row = v.execute_case(case)
    assert row["assertion_passed"] is True, row["reason"]
    assert row["raw"]["timeline"][1]["edge_transfers"][0]["transfer_m3"] < 0
    corrupt = copy.deepcopy(row["raw"])
    corrupt["timeline"][1]["edge_transfers"][0]["transfer_t"] = -1.
    assert v._flooding_problems(case, corrupt)


def _fake_command(tmp_path, behavior):
    script = tmp_path / "test worker.py"
    script.write_text('''import json, os, sys, time
from pathlib import Path
from plimsoll._verification_worker import perform, atomic_write
request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
result = Path(sys.argv[2])
behavior = sys.argv[3]
if behavior == "stall":
    while True: time.sleep(1)
if behavior == "raise": raise RuntimeError("intentional worker failure")
response = perform(request)
if behavior == "signature": response["case_sha256"] = "0" * 64
if behavior == "badjson": result.write_text("{oops", encoding="utf-8")
else: atomic_write(result, response)
''', encoding="utf-8")
    return lambda request, result: [sys.executable, "-B", str(script), str(request), str(result), behavior]


@pytest.mark.parametrize("behavior,expected", [("stall", "timeout"), ("raise", "error"),
                                               ("signature", "error"), ("badjson", "error")])
def test_real_worker_failure_survives_in_report(tmp_path, monkeypatch, behavior, expected):
    monkeypatch.setattr(v, "build_cases", lambda suite: build_cases("quick")[1:2])
    monkeypatch.setattr(v, "_worker_command", _fake_command(tmp_path, behavior))
    snapshots = []
    start = time.monotonic()
    report = v.run_verification(case_timeout_s=1.5, total_timeout_s=4, checkpoint=snapshots.append)
    assert time.monotonic() - start < 8
    assert snapshots[0]["cases"][0]["state"] == "pending"
    assert report["cases"][0]["state"] == expected, report
    assert report["cases"][0]["worker"]["reaped"] is True
    assert isinstance(report["cases"][0]["worker"]["returncode"], int)
    assert exit_code_for(report) == 1
    validate_report(report)


def test_total_deadline_preserves_previous_result_and_not_started(tmp_path, monkeypatch):
    selected = build_cases("quick")[0:3]
    monkeypatch.setattr(v, "build_cases", lambda suite: selected)
    ordinary = v._worker_command
    stalled = _fake_command(tmp_path, "stall")
    count = 0
    def command(request, result):
        nonlocal count
        count += 1
        return ordinary(request, result) if count == 1 else stalled(request, result)
    monkeypatch.setattr(v, "_worker_command", command)
    snapshots = []
    report = v.run_verification(case_timeout_s=10, total_timeout_s=2.5, checkpoint=snapshots.append)
    assert report["cases"][0]["state"] == "passed", report
    assert report["cases"][1]["state"] == "timeout"
    assert report["cases"][2]["state"] == "not_started"
    assert len(report["cases"]) == len(selected)
    assert exit_code_for(report) == 1
    assert all(s["generation"] == i for i, s in enumerate(snapshots))


@pytest.mark.parametrize("name,value", [("case_timeout_s", 0), ("case_timeout_s", True),
                                      ("total_timeout_s", math.inf), ("total_timeout_s", -1)])
def test_invalid_limits_are_usage_errors(name, value):
    with pytest.raises(ValueError):
        v.run_verification(**{name: value})


def test_real_worker_positive_control(tmp_path, monkeypatch):
    monkeypatch.setattr(v, "build_cases", lambda suite: build_cases("quick")[1:2])
    report = v.run_verification()
    validate_report(report)
    assert exit_code_for(report) == 0, report
    assert report["cases"][0]["worker"]["reaped"] is True
    assert report["cases"][0]["source_consistent"] is True
