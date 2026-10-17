"""Native ship design integration: stage, staging defaults, exports and save.

These tests exercise the bounded integration this unit owns — the native
``ship_design`` analysis stage, the native/legacy stage defaults, the saved-export
preference order and the project-level validation that refuses a conflicting
direct edit — against the real pure core, never a stub kernel.
"""
import copy
import json
from pathlib import Path

import pytest

from plimsoll import _analysis_request, analysis, exports, loading, project_io, ship_design, sps_file_io

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).parent / "fixtures" / "sps3b3-synthetic.json"
BOX = ROOT / "tools" / "plimsoll" / "cases" / "projects" / "analytic_box.project.json"


def source_design():
    return json.loads(FIXTURE.read_text(encoding="utf-8-sig"))


def native_project(design=None):
    draft = project_io.new_project("Native integration", project_id="00000000-0000-0000-0000-00000000aa01")
    reply = ship_design.initialize(draft, source_design() if design is None else design)
    assert reply["status"] != "unavailable", reply["diagnostics"]
    return project_io.normalize_project(reply["project"])


def analytic_box():
    return json.loads(BOX.read_text(encoding="utf-8-sig"))


def test_stage_defaults_are_native_then_legacy_then_physical():
    native = native_project()
    assert analysis.compute_project(native, "design-normal")["request"]["options"]["stages"] == ["ship_design"]

    legacy = analytic_box()
    legacy["sps_3b3_design"] = source_design()
    legacy = project_io.normalize_project(legacy)
    request = _analysis_request.normalize(legacy, "loaded")[1]
    assert request["options"]["stages"] == ["sps_compat"]

    plain = project_io.normalize_project(analytic_box())
    assert _analysis_request.normalize(plain, "loaded")[1]["options"]["stages"] == list(_analysis_request.DEFAULT_STAGES)


def test_native_stage_skips_loading_and_needs_no_geometry_or_cg(monkeypatch):
    native = native_project()
    assert native["geometry"] is None
    monkeypatch.setattr(loading, "resolve_loading",
                        lambda *a, **k: pytest.fail("the native stage invoked physical loading"))
    result = analysis.compute_project(native, "design-normal")
    assert result["stages"]["loading"]["status"] == "not_requested"
    assert result["stages"]["geometry"]["status"] == "not_requested"
    stage = result["stages"]["ship_design"]
    assert stage["requested"] is True and stage["status"] == "completed", stage
    assert isinstance(stage["data"]["source_design"], dict)
    assert isinstance(stage["data"]["report"], dict)


def test_native_stage_names_requested_and_basis_conditions_separately():
    native = native_project()
    native["loading_conditions"].append(
        {"id": "deep-study", "label": "deep-study", "reference_displacement_t": None, "overrides": {}})
    native = project_io.normalize_project(native)
    data = analysis.compute_project(native, "deep-study")["stages"]["ship_design"]["data"]
    assert data["condition_id"] == "deep-study"
    assert data["basis_condition_id"] == "design-normal"
    assert data["balance"]["basis_condition_id"] == "design-normal"


def test_explicit_design_balance_is_not_a_second_authority_for_a_native_project():
    native = native_project()
    result = analysis.compute_project(native, "design-normal",
                                      {"stages": ["ship_design", "design_balance"]})
    envelope = result["stages"]["design_balance"]
    assert envelope["status"] == "unavailable"
    assert envelope["data"] is None
    assert any(d.get("code") == "analysis.design_balance_native_owned" for d in envelope["diagnostics"])


def native_saved_result():
    return analysis.compute_project(native_project(), "design-normal")


def legacy_saved_result():
    legacy = analytic_box()
    legacy["sps_3b3_design"] = source_design()
    return analysis.compute_project(project_io.normalize_project(legacy), "loaded")


def test_saved_exports_prefer_the_frozen_native_stage(monkeypatch):
    result = native_saved_result()
    data = result["stages"]["ship_design"]["data"]
    assert isinstance(data["report"], dict) and isinstance(data["source_design"], dict)
    native_text = exports.serialize_report(result, "txt")
    # A competing legacy stage must never outrank the native stage.
    result["stages"]["sps_compat"] = legacy_saved_result()["stages"]["sps_compat"]
    assert exports.serialize_report(result, "txt") == native_text

    monkeypatch.setattr(analysis, "compute_project",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("export recomputed the project")))
    assert exports.serialize_report(result, "txt") == native_text
    data["report"]["text"] = "Frozen report 中文\n"
    assert exports.serialize_report(result, "txt") == "Frozen report 中文\n"
    assert exports.serialize_report(result, "ssr").startswith("{\\rtf1")
    data["source_design"]["parameters"]["ship_name"] = "frozen-name"
    assert sps_file_io.loads(exports.serialize_report(result, "sship").encode())["parameters"]["ship_name"] == "frozen-name"
    assert json.loads(exports.serialize_report(result, "json"))["schema"] == "plimsoll-analysis-1"


def test_native_export_accepts_a_pending_binding_partial_stage():
    result = native_saved_result()
    stage = result["stages"]["ship_design"]
    stored = stage["data"]["report"]["text"]
    # A pending ledger binding keeps the stage partial but never withholds the
    # frozen report or the source declaration.
    stage["status"] = "partial"
    assert exports.serialize_report(result, "txt") == stored
    assert sps_file_io.loads(exports.serialize_report(result, "sship").encode())["parameters"]["length_waterline"] == 180
    # A stage that produced no usable payload is refused, never silently served.
    stage["status"] = "failed"
    with pytest.raises(ValueError):
        exports.serialize_report(result, "txt")


def test_saved_exports_fall_back_to_legacy_and_refuse_a_missing_stage():
    legacy = legacy_saved_result()
    assert exports.serialize_report(legacy, "txt") == legacy["stages"]["sps_compat"]["data"]["report"]["text"]
    assert sps_file_io.loads(exports.serialize_report(legacy, "sship").encode())["parameters"]["length_waterline"] == 180
    with pytest.raises(ValueError):
        exports.serialize_report({"schema": "plimsoll-analysis-1", "stages": {}}, "txt")


def test_projection_conflict_dual_declaration_and_malformed_native_are_refused():
    native = native_project()
    edited = copy.deepcopy(native)
    key = next(k for k in ("lwl_m", "beam_m", "loa_m") if edited["hull"].get(k) is not None)
    edited["hull"][key] = edited["hull"][key] + 3.0
    with pytest.raises(project_io.ProjectValidationError) as error:
        project_io.normalize_project(edited)
    assert any(d["code"] == "extension.ship_design.projection_conflict" for d in error.value.diagnostics)

    dual = copy.deepcopy(native)
    dual["sps_3b3_design"] = source_design()
    with pytest.raises(project_io.ProjectValidationError) as error:
        project_io.normalize_project(dual)
    assert any(d["code"] == "extension.ship_design.dual_declaration" for d in error.value.diagnostics)

    malformed = project_io.new_project("malformed", project_id="00000000-0000-0000-0000-00000000bb02")
    malformed["ship_design"] = {"schema": "wrong"}
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(malformed)

    # An explicit null is a missing declaration with no active overlay, not a defect.
    missing = project_io.new_project("missing", project_id="00000000-0000-0000-0000-00000000cc03")
    missing["ship_design"] = None
    project_io.normalize_project(missing)
