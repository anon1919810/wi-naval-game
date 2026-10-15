"""Explicit offline verification; public kernels run in bounded child processes.

File hashes identify disk sources, not arbitrary in-memory monkeypatches.
Call seals detect net input changes at each public-call boundary, not a change
restored inside the same call. JSON retains every raw result and signed error.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import uuid

from . import battery_armour, geometry, geometry_analysis, stability, small_angle_stability, tank_geometry, flooding
from .verification_cases import build_cases
from . import verification_oracles as oracle

METHOD_VERSION = "offline-core-verification-1"
PACKAGE = Path(__file__).resolve().parent


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(",", ":"))


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _source_identity():
    # Fixed package scope includes private kernel dependencies, runner, worker,
    # reporter and bundled README. Tests, docs and cached bytecode are excluded.
    files = [{"module": "plimsoll." + p.stem, "path": str(p),
              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(PACKAGE.glob("*.py"))]
    guide = PACKAGE / "CLI_README.md"
    files.append({"module": "plimsoll.CLI_README", "path": str(guide),
                  "sha256": hashlib.sha256(guide.read_bytes()).hexdigest()})
    versions = {m.__name__: getattr(m, "METHOD_VERSION", None)
                for m in (stability, geometry_analysis, small_angle_stability, tank_geometry,
                          flooding, flooding.kernel, oracle, battery_armour)}
    versions[__name__] = METHOD_VERSION
    return {"files": files, "method_versions": versions, "consistent": True}


def _loaded_origins():
    origins = []
    names = {p.stem for p in PACKAGE.glob("*.py")} - {"__main__", "__init__"}
    for name, module in sorted(list(sys.modules.items())):
        spec_name = getattr(getattr(module, "__spec__", None), "name", "") or ""
        if name.startswith("plimsoll.") or name == "plimsoll" or name in names or (name == "__main__" and spec_name.startswith("plimsoll.")):
            path = getattr(module, "__file__", None)
            if path is not None:
                origins.append({"module": name, "path": str(Path(path).resolve())})
    return origins


def _origin_problems(origins):
    return ["loaded source outside measured package: " + o["path"] for o in origins
            if not Path(o["path"]).is_absolute() or not Path(o["path"]).resolve().is_relative_to(PACKAGE)]


def _audit_value(value):
    if callable(value):
        return {"callback": value.__module__ + "." + value.__qualname__}
    if isinstance(value, dict):
        return {k: _audit_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_audit_value(v) for v in value]
    return value


def _checked_call(function, args, kwargs, audit):
    receiver = getattr(function, "__self__", None)
    def payload():
        value = {"args": args, "kwargs": kwargs}
        if isinstance(receiver, geometry.StationedHull):
            value["receiver_stations"] = receiver.stations
        return _audit_value(value)
    before = payload()
    # Take a real snapshot; args may be mutated by the callable.
    before = json.loads(_json(before))
    start = time.perf_counter()
    try:
        return function(*args, **kwargs)
    finally:
        after = payload()
        audit.append({"function": function.__module__ + "." + function.__qualname__,
                      "request": before, "before_sha256": _digest(before),
                      "after_sha256": _digest(after), "unchanged": before == after,
                      "elapsed_s": time.perf_counter() - start})


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _nonfinite_paths(value, path="$"):
    if isinstance(value, float) and not math.isfinite(value):
        return [path]
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in _nonfinite_paths(v, path + "." + str(k))]
    if isinstance(value, (tuple, list)):
        return [p for i, v in enumerate(value) for p in _nonfinite_paths(v, path + f"[{i}]")]
    return []


def _safe(value):
    # Only after raw guards, for a reportable failure. Never impute zero.
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_safe(v) for v in value]
    return value


def _equilibrium_problems(raw, expected_mode="free", expected_fingerprint=None, expected_liquids=None):
    if not isinstance(raw, dict):
        return ["equilibrium must be an object"]
    problems = ["nonfinite equilibrium: " + p for p in _nonfinite_paths(raw)]
    if raw.get("method_version") != stability.METHOD_VERSION:
        problems.append("equilibrium method_version differs from measured method")
    if expected_fingerprint is not None and raw.get("input_fingerprint") != expected_fingerprint:
        problems.append("equilibrium input fingerprint differs from supplied loading")
    if raw.get("converged") is not True:
        problems.append("converged must be exact true")
    validity = raw.get("validity", {})
    if not isinstance(validity, dict):
        validity = {}
    for key in ("complete", "model_applicable"):
        if validity.get(key) is not True:
            problems.append("validity." + key + " must be exact true")
    residuals = raw.get("residuals", {}).get("scaled", {}) if isinstance(raw.get("residuals"), dict) else {}
    keys = ("volume", "longitudinal", "transverse") if expected_mode == "free" else ("volume", "longitudinal")
    if raw.get("mode") != expected_mode:
        problems.append("equilibrium mode differs from request")
    for key in keys:
        v = residuals.get(key) if isinstance(residuals, dict) else None
        if not _finite(v) or abs(v) > 1e-6:
            problems.append("missing/nonfinite/excess residual: " + key)
    for key in ("volume_m3", "waterline_d_m", "waterline_above_keel_m", "p", "q", "heel_deg", "trim_deg", "gz_m"):
        if not _finite(raw.get(key)):
            problems.append("missing/nonfinite equilibrium quantity: " + key)
    for key in ("buoyancy_centre_m", "buoyancy_centre_keel_m"):
        if not isinstance(raw.get(key), (list, tuple)) or len(raw[key]) != 3 or not all(_finite(v) for v in raw[key]):
            problems.append("missing/nonfinite centre: " + key)
    effective = raw.get("effective_loading", {})
    if not isinstance(effective, dict) or not _finite(effective.get("total_mass_t")) or effective["total_mass_t"] <= 0:
        problems.append("missing/nonfinite/invalid effective mass")
    else:
        for key in ("cg_m", "cg_keel_m"):
            if not isinstance(effective.get(key), (tuple, list)) or len(effective[key]) != 3 or not all(_finite(v) for v in effective[key]):
                problems.append("missing/nonfinite effective " + key)
    liquids = raw.get("liquids", [])
    if expected_liquids is not None:
        if not isinstance(raw.get("liquids"), list) or sorted(liquid.get("tank_id", "") for liquid in liquids) != sorted(expected_liquids):
            problems.append("liquid status evidence differs from requested tanks")
    for liquid in liquids:
        if liquid.get("converged") is not True or liquid.get("applicability", {}).get("status") != "applicable":
            problems.append("liquid state convergence/applicability missing or false")
    return problems


def _check(name, passed, measured=None, expected=None, tolerance=None, unit="", required=True, reason=None):
    return {"name": name, "passed": passed, "required": required, "measured": measured,
            "expected": expected, "tolerance": tolerance, "unit": unit,
            "reason": reason if passed is not True else None}


def _loading(mass, cg):
    return {"complete_mass": True, "complete_cg": True, "input_fingerprint": _digest([mass, cg]),
            "project_id": "verification", "condition_id": "declared", "diagnostics": [],
            "values": {"total_mass_t": mass, "lcg_m": cg[0], "tcg_m": cg[1], "kg_m": cg[2]}}


def _box_geometry(spec):
    l, b, h, z = (spec[k] for k in ("length_m", "beam_m", "depth_m", "keel_offset_m"))
    section = [[-b / 2, z], [b / 2, z], [b / 2, z + h], [-b / 2, z + h]]
    return {"kind": "offsets", "keel_offset_m": z, "source": {"kind": "declared_analytic_prism"},
            "estimate": False, "offsets": {"schema": "plimsoll-section-polygons-1",
                                          "stations": [[-l / 2 + l * i / 20, copy.deepcopy(section)] for i in range(21)]}}


def _column_cg(tank, volume, p, q):
    l, b = tank["length_m"], tank["beam_m"]
    mean = volume / (tank.get("permeability", 1.0) * l * b)
    if abs(p) * l / 2 + abs(q) * b / 2 >= min(mean, tank["height_m"] - mean):
        raise ValueError("independent column target leaves uncut domain")
    return [tank["x_m"] + p * l * l / (12 * mean), tank["y_m"] + q * b * b / (12 * mean),
            tank["keel_to_bottom_m"] + mean / 2 + (p * p * l * l + q * q * b * b) / (24 * mean)]


def _transform_sample(case, audit):
    inputs = case["inputs"]
    spec = inputs["box"]
    ref = oracle._box_reference(spec)["quantities"]
    hull = _box_geometry(spec)
    cg = list(ref["cg_keel_m"]["value"])
    mass = ref["mass_t"]["value"]
    options = {"rho_t_m3": spec["rho_t_m3"]}
    tank = inputs.get("liquid_tank")
    if case["kind"] == "transform.datum":
        tank = {"id": "datum-liquid", "length_m": 8.0, "beam_m": 4.0, "height_m": 4.0,
                "x_m": 2.0, "y_m": 1.0, "keel_to_bottom_m": inputs["tank_keel_to_bottom_m"], "permeability": 1.0}
    liquid = None
    if tank and (inputs.get("load_state") == "liquid_loaded" or case["kind"] == "transform.datum"):
        fraction = inputs.get("liquid_volume_fraction", 0.5)
        volume = tank["length_m"] * tank["beam_m"] * tank["height_m"] * fraction
        liquid_mass = volume * spec["rho_t_m3"]
        liquid_cg = _column_cg(tank, volume, spec["p"], spec["q"])
        cg = [(mass * a - liquid_mass * b) / (mass - liquid_mass) for a, b in zip(cg, liquid_cg)]
        mass -= liquid_mass
        options["liquid_loads"] = [{"tank": copy.deepcopy(tank), "volume_m3": volume,
                                    "fluid_density_t_m3": spec["rho_t_m3"]}]
        liquid = _checked_call(tank_geometry.liquid_state, [tank, volume],
                               {"heel_deg": math.degrees(math.atan(spec["q"])),
                                "trim_deg": math.degrees(math.atan(spec["p"]))}, audit)
    state = _loading(mass, cg)
    measures = _checked_call(geometry_analysis.measures_at_plane, [hull, {"p": spec["p"], "q": spec["q"],
                             "waterline_d_m": spec["draft_m"] + spec["keel_offset_m"]}],
                             {"rho_t_m3": spec["rho_t_m3"]}, audit)
    solved = _checked_call(stability.solve_loaded_equilibrium, [hull, state, options], {}, audit)
    heads = None
    if case["kind"] == "transform.datum":
        node = {**tank, "fluid_density_t_m3": spec["rho_t_m3"], "source": {"kind": "analytic_datum_control"}, "estimate": False}
        edge = {"id": "datum-head", "from_node_id": "sea", "to_node_id": tank["id"],
                "centre_m": [tank["x_m"], tank["y_m"], inputs["aperture_z_keel_m"]], "area_m2": .1, "discharge_coefficient": .6,
                "fluid_density_t_m3": spec["rho_t_m3"], "open": True, "source": {"kind": "analytic_datum_control"}, "estimate": False}
        heads = _checked_call(flooding.kernel.evaluate_flows, [[node], {tank["id"]: volume}, [edge]],
            {"attitude": {"heel_deg": math.degrees(math.atan(spec["q"])), "trim_deg": math.degrees(math.atan(spec["p"])),
                          "geometry_keel_offset_m": spec["keel_offset_m"]},
             "sea": {"id": "sea", "surface_offset_m": (spec["draft_m"] + spec["keel_offset_m"]) / math.sqrt(1 + spec["p"] ** 2 + spec["q"] ** 2),
                     "fluid_density_t_m3": spec["rho_t_m3"], "source": {"kind": "analytic_datum_control"}, "estimate": False}}, audit)
    return {"measures": measures, "solved": solved, "liquid": liquid,
            "datum_heads": heads,
            "reference": ref, "request": {"geometry": hull, "loading": state, "options": options}}


def _counterpart(case):
    other = copy.deepcopy(case)
    spec = other["inputs"]["box"]
    if case["kind"] == "transform.scale_linear":
        factor = other["inputs"]["scale_factor"]
        for key in ("length_m", "beam_m", "depth_m", "draft_m", "cg_z_m", "keel_offset_m", "cg_offset_y_m"):
            spec[key] /= factor
        if "liquid_tank" in other["inputs"]:
            for key in ("length_m", "beam_m", "height_m", "x_m", "y_m", "keel_to_bottom_m"):
                other["inputs"]["liquid_tank"][key] /= factor
        other["inputs"]["scale_factor"] = 1.0
    elif case["kind"] == "transform.mirror":
        if other["inputs"]["mirrored"]:
            spec["q"] *= -1
            spec["cg_offset_y_m"] *= -1
            other["inputs"]["liquid_tank"]["y_m"] *= -1
            other["inputs"]["mirrored"] = False
    else:
        spec["cg_z_m"] -= spec["keel_offset_m"]
        spec["keel_offset_m"] = 0.0
        other["inputs"]["keel_offset_m"] = 0.0
    return other


def _maximum_difference(a, b):
    if isinstance(a, (list, tuple)):
        return max(_maximum_difference(x, y) for x, y in zip(a, b))
    return abs(a - b)


def _transform(case, audit):
    actual = _transform_sample(case, audit)
    base = _transform_sample(_counterpart(case), audit)
    raw = {**actual, "counterpart": base}
    problems = _equilibrium_problems(actual["solved"], expected_fingerprint=actual["request"]["loading"]["input_fingerprint"],
        expected_liquids=[load["tank"]["id"] for load in actual["request"]["options"].get("liquid_loads", [])])
    problems += _equilibrium_problems(base["solved"], expected_fingerprint=base["request"]["loading"]["input_fingerprint"],
        expected_liquids=[load["tank"]["id"] for load in base["request"]["options"].get("liquid_loads", [])])
    if actual["measures"].get("status") != "completed" or base["measures"].get("status") != "completed":
        problems.append("selected plane measures unavailable")
    if problems:
        return raw, {}, problems
    s, bs = actual["solved"], base["solved"]
    m, bm = actual["measures"]["values"], base["measures"]["values"]
    factor = case["inputs"].get("scale_factor", 1.0)
    mirrored = case["inputs"].get("mirrored", False)
    shift = case["inputs"]["box"]["keel_offset_m"]
    powers = {"volume_m3": 3, "displacement_t": 3, "awp_m2": 2,
              "awp_projected_xy_m2": 2, "it_m4": 4, "il_m4": 4, "waterplane_product_m4": 4}
    law_errors = {k: abs(m[k] - bm[k] * factor ** power * (-1 if mirrored and k == "waterplane_product_m4" else 1))
                  / max(abs(bm[k] * factor ** power), 1e-30) for k, power in powers.items()}
    target_cb = [bm["lcb_m"] * factor, bm["tcb_m"] * factor * (-1 if mirrored else 1), bm["kb_m"] * factor]
    cb_error = _maximum_difference([m["lcb_m"], m["tcb_m"], m["kb_m"]], target_cb)
    targets = {"volume_m3": bs["volume_m3"] * factor ** 3,
               "waterline_d_m": bs["waterline_d_m"] * factor + shift,
               "buoyancy_centre_m": [bs["buoyancy_centre_m"][0] * factor,
                    bs["buoyancy_centre_m"][1] * factor * (-1 if mirrored else 1), bs["buoyancy_centre_m"][2] * factor + shift],
               "cg_m": [bs["effective_loading"]["cg_m"][0] * factor,
                    bs["effective_loading"]["cg_m"][1] * factor * (-1 if mirrored else 1), bs["effective_loading"]["cg_m"][2] * factor + shift]}
    solved_errors = {k: _maximum_difference(s["effective_loading"][k] if k == "cg_m" else s[k], expected)
                     for k, expected in targets.items()}
    solved_ok = solved_errors["volume_m3"] / abs(targets["volume_m3"]) <= 1e-6 and max(v for k, v in solved_errors.items() if k != "volume_m3") <= 1e-5
    angle_error = max(abs(s["trim_deg"] - bs["trim_deg"]), abs(s["heel_deg"] - bs["heel_deg"] * (-1 if mirrored else 1)))
    liquid_ok = True
    if actual["liquid"]:
        la, lb = actual["liquid"], base["liquid"]
        target = [lb["centroid_m"][0] * factor, lb["centroid_m"][1] * factor * (-1 if mirrored else 1), lb["centroid_m"][2] * factor]
        liquid_ok = la.get("converged") is True and lb.get("converged") is True and la.get("applicability", {}).get("status") == "applicable"
        liquid_ok &= _maximum_difference(la["centroid_m"], target) <= 1e-7 and abs(la["volume_m3"] - lb["volume_m3"] * factor ** 3) <= abs(la["volume_m3"]) * 1e-8
    metrics = {"law_relative_errors": law_errors, "direct_centroid_law_error_m": cb_error,
               "solved_law_errors": solved_errors, "angle_law_error_deg": angle_error,
               "continuous_cb_difference_m": [m["lcb_m"] - actual["reference"]["buoyancy_centre_keel_m"]["value"][0],
                      m["tcb_m"] - actual["reference"]["buoyancy_centre_keel_m"]["value"][1],
                      m["kb_m"] - actual["reference"]["buoyancy_centre_keel_m"]["value"][2]]}
    head_ok = True
    if actual["datum_heads"] is not None:
        aa, bb = actual["datum_heads"], base["datum_heads"]
        head_ok = aa.get("status") == "applicable" and bb.get("status") == "applicable"
        aedge, bedge = aa["edges"][0], bb["edges"][0]
        # The public head/flow fields are independently evaluated with the
        # actual geometry datum; bottom/aperture inputs remain keel-relative.
        differences = {k: abs(aedge[k] - bedge[k]) for k in ("from_head_m", "to_head_m", "flow_m3_s")}
        metrics["datum_head_flow_differences"] = differences
        head_ok &= max(differences.values()) <= 1e-7
    passed = {"status_flag_matches": True, "scaled_residual_within_limit": True,
              "volume_relative_vs_reference": abs(m["volume_m3"] / actual["reference"]["volume_m3"]["value"] - 1) <= 1e-8,
              "buoyancy_axis_vs_reference": cb_error <= 1e-7,
              "scale_exponent_law": max(law_errors.values()) <= 1e-8 and solved_ok and liquid_ok,
              "angles_invariant": angle_error <= 1e-5,
              "mirror_invariant_volume": solved_ok and max(law_errors.values()) <= 1e-8,
              "mirror_invariant_longitudinal": solved_ok and angle_error <= 1e-5,
              "mirror_reverses_transverse": solved_ok and cb_error <= 1e-7 and angle_error <= 1e-5 and liquid_ok and abs(s["gz_m"] + bs["gz_m"]) <= 1e-5,
              "keel_relative_invariants": solved_ok and cb_error <= 1e-7 and angle_error <= 1e-5 and liquid_ok and head_ok,
              "absolute_shift_applied": solved_ok}
    return raw, {"passed": passed, "metrics": metrics}, []


def _mesh(case, reference, audit):
    i = case["inputs"]
    a, b, c = i["semi_axes_m"]
    n, nv = i["stations"], i["section_vertices"]
    table = []
    for j in range(n):
        x = -a * math.cos(math.pi * j / (n - 1))
        r = math.sqrt(max(0.0, 1.0 - (x / a) ** 2))
        table.append([x, [[b * r * math.cos(2 * math.pi * k / nv), i["centre_z_m"] + c * r * math.sin(2 * math.pi * k / nv)] for k in range(nv)]])
    hull = {"kind": "offsets", "keel_offset_m": 0.0, "source": {"kind": "analytic_ellipsoid"}, "estimate": False,
            "offsets": {"schema": "plimsoll-section-polygons-1", "stations": table}}
    # Seal the explicit station table across the legacy object's public call.
    stationed = geometry.StationedHull(copy.deepcopy(table))
    direct = _checked_call(stationed.integrate, [math.atan(i["q"]), i["waterline_d_m"], math.atan(i["p"])], {}, audit)
    q = reference["quantities"]
    expected_v, expected_cb = q["volume_m3"]["value"], q["buoyancy_centre_m"]["value"]
    v_error = abs(direct["volume"] / expected_v - 1.0)
    cb_error = [abs(x - y) for x, y in zip([direct["xlcb"], direct["yb"], direct["zb"]], expected_cb)]
    raw = {"direct": direct, "request_geometry": hull}
    metrics = {"volume_relative_error": v_error, "buoyancy_axis_absolute_error_m": cb_error}
    passed = {"status_flag_matches": direct["volume"] > 0, "all_states_finite": not _nonfinite_paths(direct),
              "analytic_volume_relative_error": _finite(v_error)}
    problems = []
    if i["solve_equilibrium"]:
        state = _loading(q["mass_t"]["value"], q["free_equilibrium_cg_m"]["value"])
        solved = _checked_call(stability.solve_loaded_equilibrium, [hull, state, {"rho_t_m3": i["rho_t_m3"]}], {}, audit)
        raw["solved"] = solved
        raw["request_loading"] = state
        raw["request_options"] = {"rho_t_m3": i["rho_t_m3"]}
        problems = _equilibrium_problems(solved, expected_fingerprint=state["input_fingerprint"], expected_liquids=[])
        passed.update(equilibrium_converged_flag=not problems, scaled_residual_within_limit=not problems)
        if not problems:
            metrics["solved_volume_relative_error"] = abs(solved["volume_m3"] / expected_v - 1.0)
            metrics["solved_buoyancy_axis_absolute_error_m"] = [abs(x - y) for x, y in zip(solved["buoyancy_centre_m"], expected_cb)]
            metrics["draft_absolute_error_m"] = abs(solved["waterline_d_m"] - i["waterline_d_m"])
            metrics["slope_absolute_error"] = max(abs(solved["p"] - i["p"]), abs(solved["q"] - i["q"]))
            passed.update(analytic_volume_within_finest_limit=max(v_error, metrics["solved_volume_relative_error"]) <= 1e-3,
                          analytic_buoyancy_axis_within_finest_limit=max(cb_error + metrics["solved_buoyancy_axis_absolute_error_m"]) <= .01,
                          analytic_draft_within_finest_limit=metrics["draft_absolute_error_m"] <= .01,
                          analytic_slope_within_finest_limit=metrics["slope_absolute_error"] <= 1e-4)
    return raw, {"passed": passed, "metrics": metrics}, problems


def _flood_options(case):
    i = case["inputs"]
    return {"max_steps": i["max_steps"], "max_step_halvings": i["max_step_halvings"], "gravity_m_s2": i["gravity_m_s2"]}


def _flooding_problems(case, raw):
    if not isinstance(raw, dict):
        return ["flooding result must be an object"]
    problems = ["nonfinite flooding: " + p for p in _nonfinite_paths(raw)]
    i = case["inputs"]
    project = flooding.project_io.normalize_project(i["project"])
    loading = flooding.loading.resolve_loading(project, i["condition_id"])
    # These fixtures already declare the normalized, source-complete scenario.
    # Use its supplied bytes, never the returned scenario, for request identity.
    fingerprint = flooding._input_fingerprint(project, i["condition_id"], i["scenario"],
                                               flooding._validate_options(_flood_options(case)))
    if raw.get("input_fingerprint") != fingerprint or raw.get("project_fingerprint") != loading["project_fingerprint"]:
        problems.append("flooding result identity differs from declared request")
    if _digest(raw.get("scenario")) != _digest(i["scenario"]) or _digest(raw.get("loading")) != _digest(loading):
        problems.append("flooding returned scenario/loading differs from supplied input")
    if raw.get("method_version") != flooding.METHOD_VERSION or raw.get("kernel_method_version") != flooding.kernel.METHOD_VERSION:
        problems.append("flooding method versions differ from measured methods")
    timeline = raw.get("timeline")
    if not isinstance(timeline, list) or not timeline:
        return problems + ["missing accepted timeline"]
    validity = raw.get("validity", {})
    if not isinstance(validity, dict):
        validity = {}
    expected_status = case["expected"]["status"]
    if raw.get("status") != expected_status or raw.get("stop_reason") != case["expected"]["reason"]:
        problems.append("flooding status/reason differs from declared expectation")
    if validity.get("numerical_convergence") is not True:
        problems.append("numerical_convergence must be exact true")
    for key, expected in (("complete", expected_status == "completed"), ("model_applicable", expected_status != "model_limit")):
        if validity.get(key) is not expected:
            problems.append("validity." + key + " must match declared status with exact bool")
    if raw.get("final_state") != timeline[-1]:
        problems.append("final_state disagrees with last accepted timeline state")
    if timeline[0].get("time_s") != 0.0 or timeline[0].get("actual_dt_s") != 0.0:
        problems.append("timeline must begin with accepted t=0 and dt=0")
    if case["kind"] == "flooding.control_cancel" and timeline[-1].get("time_s") != i["cancel_time_s"]:
        problems.append("cancellation differs from declared accepted time")
    if case["expected"]["stop_class"] == "scheduled_completion" and timeline[-1].get("time_s") != i["duration_s"]:
        problems.append("scheduled completion differs from requested time")
    for key in ("volume_conservation_error_m3", "mass_conservation_error_t",
                "cumulative_sea_exchange_m3", "cumulative_sea_exchange_t"):
        if not _finite(raw.get(key)) or raw.get(key) != timeline[-1].get(key):
            problems.append("top-level final field disagrees with last state: " + key)
    if case["expected"]["stop_class"] == "hydraulic_equilibrium_tolerance":
        tolerance, head = raw.get("terminal_head_tolerance_m"), raw.get("terminal_max_head_difference_m")
        if tolerance != flooding.HYDRAULIC_HEAD_TOLERANCE_M or not _finite(head) or not 0 <= head <= tolerance:
            problems.append("hydraulic-equilibrium stop lacks finite head within declared tolerance")
    last_time = -1.0
    for index, state in enumerate(timeline):
        problems.extend(f"state {index}: " + p for p in _equilibrium_problems(state.get("equilibrium", {}), expected_fingerprint=loading["input_fingerprint"]))
        t = state.get("time_s")
        if not _finite(t) or not last_time < t <= case["inputs"]["duration_s"]:
            problems.append("accepted times not finite/strictly increasing/bounded")
        last_time = t if _finite(t) else last_time
        dt = state.get("actual_dt_s")
        if index > 0 and (not _finite(dt) or dt <= 0.0 or not _finite(t) or abs(dt - (t - timeline[index - 1]["time_s"])) > 1e-12 * max(1.0, abs(t))):
            problems.append("accepted dt disagrees with adjacent times")
        if not isinstance(state.get("volumes_m3"), dict) or not state["volumes_m3"]:
            problems.append("missing accepted volumes")
        for key in ("volume_conservation_error_m3", "mass_conservation_error_t", "actual_dt_s"):
            if not _finite(state.get(key)):
                problems.append("missing/nonfinite timeline " + key)
    if not problems:
        problems.extend(_flood_ledger_problems(case, raw, loading))
    return problems


def _flood_ledger_problems(case, raw, loading):
    """Recompute signed transfers against the declared network at every step."""
    i, timeline = case["inputs"], raw["timeline"]
    tanks = {tank["id"]: tank for tank in i["scenario"]["tanks"]}
    densities = {key: tank["fluid_density_t_m3"] for key, tank in tanks.items()}
    sea_id = i["scenario"]["sea"]["id"]
    sea_density = i["scenario"]["sea"]["fluid_density_t_m3"]
    connections = {edge["id"]: edge for edge in i["scenario"]["connections"]}
    previous = {key: tank["initial_volume_m3"] for key, tank in tanks.items()}
    initial_v = math.fsum(previous.values())
    initial_m = math.fsum(previous[key] * densities[key] for key in tanks)
    v_tol = max(1e-9, 1e-10 * i["declared_transferred_volume_scale_m3"])
    m_tol = max(1e-9, 1e-10 * i["declared_mass_scale_t"])
    problems = []
    def near(actual, expected, tolerance):
        return _finite(actual) and abs(actual - expected) <= tolerance
    if not near(raw.get("initial_total_water_volume_m3"), initial_v, v_tol) or not near(raw.get("initial_total_water_mass_t"), initial_m, m_tol):
        problems.append("initial totals differ from supplied tank volumes")
    cumulative_v, cumulative_m = 0.0, 0.0
    for index, state in enumerate(timeline):
        prefix = f"state {index}: "
        volumes, transfers = state.get("volumes_m3"), state.get("edge_transfers")
        if not isinstance(volumes, dict) or set(volumes) != set(tanks) or not all(_finite(value) for value in volumes.values()):
            problems.append(prefix + "accepted volume nodes differ from declared tanks")
            continue
        if not isinstance(transfers, list):
            problems.append(prefix + "missing accepted edge transfers")
            continue
        expected_volumes, step_v, step_m, seen = dict(previous), 0.0, 0.0, set()
        for transfer in transfers:
            edge = connections.get(transfer.get("connection_id"))
            if edge is None or edge["id"] in seen or not edge["open"] or transfer.get("from") != edge["from"] or transfer.get("to") != edge["to"]:
                problems.append(prefix + "transfer identity/endpoints differ from declared open network")
                continue
            seen.add(edge["id"])
            amount, mass, flow = transfer.get("transfer_m3"), transfer.get("transfer_t"), transfer.get("flow_m3_s")
            if not all(_finite(value) for value in (amount, mass, flow)):
                problems.append(prefix + "nonfinite transfer quantities")
                continue
            # Public transfers retain the declared orientation. A reverse flow
            # is negative in volume, mass and flow; it is not a capacity error.
            if not near(amount, flow * state["actual_dt_s"], v_tol) or not near(mass, amount * edge["fluid_density_t_m3"], m_tol):
                problems.append(prefix + "transfer volume/mass/flow disagreement")
            if edge["from"] in tanks:
                expected_volumes[edge["from"]] -= amount
            elif edge["from"] == sea_id:
                step_v += amount
                step_m += amount * sea_density
            else:
                problems.append(prefix + "unknown donor node")
            if edge["to"] in tanks:
                expected_volumes[edge["to"]] += amount
            elif edge["to"] == sea_id:
                step_v -= amount
                step_m -= amount * sea_density
            else:
                problems.append(prefix + "unknown receiver node")
        cumulative_v += step_v
        cumulative_m += step_m
        total_v = math.fsum(volumes.values())
        total_m = math.fsum(volumes[key] * densities[key] for key in tanks)
        errors = {"volume_conservation_error_m3": (total_v - initial_v - cumulative_v, v_tol),
                  "mass_conservation_error_t": (total_m - initial_m - cumulative_m, m_tol),
                  "total_onboard_water_volume_m3": (total_v, v_tol), "total_onboard_water_mass_t": (total_m, m_tol),
                  "sea_exchange_m3": (step_v, v_tol), "sea_exchange_t": (step_m, m_tol),
                  "cumulative_sea_exchange_m3": (cumulative_v, v_tol), "cumulative_sea_exchange_t": (cumulative_m, m_tol)}
        for key, (expected, tolerance) in errors.items():
            if not near(state.get(key), expected, tolerance):
                problems.append(prefix + "recomputed ledger disagrees with " + key)
        if abs(errors["volume_conservation_error_m3"][0]) > v_tol or abs(errors["mass_conservation_error_t"][0]) > m_tol:
            problems.append(prefix + "recomputed conservation exceeds declared tolerance")
        if any(not near(volumes[key], expected_volumes[key], v_tol) for key in tanks):
            problems.append(prefix + "accepted volumes disagree with signed transfers")
        if any(not 0 <= volumes[key] <= tanks[key]["length_m"] * tanks[key]["beam_m"] * tanks[key]["height_m"] * tanks[key]["permeability"] for key in tanks):
            problems.append(prefix + "accepted tank volume outside capacity")
        liquid_rows = state.get("tanks")
        if not isinstance(liquid_rows, list) or sorted(row.get("tank_id", "") for row in liquid_rows) != sorted(tanks):
            problems.append(prefix + "missing liquid-state evidence for declared tanks")
        else:
            for liquid in liquid_rows:
                if liquid.get("converged") is not True or liquid.get("applicability", {}).get("status") != "applicable":
                    problems.append(prefix + "liquid state convergence/applicability missing")
        effective = state["equilibrium"]["effective_loading"]
        if not near(effective.get("total_mass_t"), loading["values"]["total_mass_t"] + total_m, m_tol):
            problems.append(prefix + "effective mass disagrees with supplied load and water ledger")
        previous = volumes
    return problems


def _flood(case, reference, audit):
    i = case["inputs"]
    options = _flood_options(case)
    if case["kind"] == "flooding.control_cancel":
        def cancel(state):
            return state["time_s"] >= i["cancel_time_s"]
        options["cancel_check"] = cancel
    raw = _checked_call(flooding.simulate_flooding, [i["project"], i["condition_id"], i["scenario"], options], {}, audit)
    problems = _flooding_problems(case, raw)
    if problems:
        return raw, {}, problems
    timeline = raw["timeline"]
    spec = i["reference_spec"]
    pair = i["scenario_name"] == "two_tank_asymmetric_free_float"
    trace = oracle.two_tank_trajectory(spec, spec["integration_step_s"]) if pair else None
    volume_error, draft_error, angle_error, minimum = 0.0, 0.0, 0.0, math.inf
    previous, reversals = None, []
    capacities = {t["id"]: t["length_m"] * t["beam_m"] * t["height_m"] * t["permeability"] for t in i["scenario"]["tanks"]}
    bounds = True
    for state in timeline:
        t = state["time_s"]
        if pair:
            ref = trace["model"].state(trace["transfer_at_time"](t))
            expected = dict(zip(("port", "starboard"), ref["volumes_m3"]))
        else:
            if case["kind"] == "flooding.control_model_boundary":
                t = min(t, reference["quantities"]["capacity_time_s"]["value"])
            ref = oracle.single_sea_coupled_state(spec, t)
            expected = {"centre": ref["tank_volume_m3"]}
        eq = state["equilibrium"]
        volume_error = max(volume_error, max(abs(state["volumes_m3"][k] - expected[k]) for k in expected))
        draft_error = max(draft_error, abs(eq["waterline_above_keel_m"] - ref["draft_m"]))
        angle_error = max(angle_error, abs(eq["heel_deg"] - ref["heel_deg"]), abs(eq["trim_deg"] - ref["trim_deg"]))
        bounds &= set(state["volumes_m3"]) == set(capacities) and all(_finite(v) and 0 <= v <= capacities[k] for k, v in state["volumes_m3"].items())
        if pair:
            transfer = trace["model"].direction * (spec["initial_volumes_m3"][0] - state["volumes_m3"]["port"])
            if previous is not None and transfer < previous - 1e-12:
                reversals.append(state["time_s"])
            previous = transfer
        minimum = min(minimum, state["time_s"])
    volume_scale = i["declared_transferred_volume_scale_m3"]
    mass_scale = i["declared_mass_scale_t"]
    signed_v = [state["volume_conservation_error_m3"] for state in timeline]
    signed_m = [state["mass_conservation_error_t"] for state in timeline]
    v_tol = max(1e-9, 1e-10 * volume_scale)
    m_tol = max(1e-9, 1e-10 * mass_scale)
    vt = case["tolerances"]["production"]["transfer_volume_tolerance_m3"]
    final = timeline[-1]
    metrics = {"max_trajectory_volume_error_m3": volume_error, "max_trajectory_draft_error_m": draft_error,
               "max_trajectory_angle_error_deg": angle_error, "signed_volume_conservation_errors_m3": signed_v,
               "signed_mass_conservation_errors_t": signed_m, "max_abs_volume_conservation_m3": max(map(abs, signed_v)),
               "max_abs_mass_conservation_t": max(map(abs, signed_m)), "accepted_time_s": final["time_s"],
               "requested_time_s": i["duration_s"], "accepted_steps": len(timeline) - 1, "reversed_transfer_times_s": reversals}
    if "plateau_time_s" in reference["quantities"]:
        metrics["stop_time_difference_from_exact_event_s"] = final["time_s"] - reference["quantities"]["plateau_time_s"]["value"]
    passed = {"status_flag_matches": raw.get("status") == case["expected"]["status"],
              "stop_reason_matches": raw.get("stop_reason") == case["expected"]["reason"],
              "numerical_convergence_is_true": True, "all_states_finite": True, "time_monotone": True,
              "last_accepted_state_present": True, "tank_volume_within_capacity": bool(bounds),
              "final_volume_vs_reference": volume_error <= vt, "final_draft_vs_reference": draft_error <= .001,
              "final_angle_vs_reference": None, "scaled_residual_within_limit": True,
              "volume_conservation": max(map(abs, signed_v)) <= v_tol,
              "mass_conservation": max(map(abs, signed_m)) <= m_tol,
              "transfer_never_reverses_direction": not reversals}
    if case["kind"] == "flooding.control_cancel":
        passed["last_accepted_state_present"] &= final["time_s"] == i["cancel_time_s"]
    if case["expected"]["stop_class"] == "scheduled_completion":
        passed["last_accepted_state_present"] &= final["time_s"] == i["duration_s"]
    return raw, {"passed": passed, "metrics": metrics}, []


def execute_case(case: dict) -> dict:
    """Execute one declared case, keeping raw solver state separate from assertions."""
    initial = copy.deepcopy(case)
    source = _source_identity()
    start = time.perf_counter()
    audit, problems = [], []
    raw, outcome, reference = {}, {}, {}
    try:
        reference = oracle.reference_for(case)
        controls = reference["evidence"]["controls"]
        if not controls or any(c.get("within_budget") is not True for c in controls):
            problems.append("independent reference precision controls failed/missing")
        if case["kind"].startswith("transform."):
            raw, outcome, guards = _transform(case, audit)
        elif case["family"] == "mesh":
            raw, outcome, guards = _mesh(case, reference, audit)
        else:
            raw, outcome, guards = _flood(case, reference, audit)
        problems.extend(guards)
    except Exception as error:
        problems.append(type(error).__name__ + ": " + str(error))
    origins = _loaded_origins()
    problems.extend(_origin_problems(origins))
    after = _source_identity()
    consistent = source == after
    if not consistent:
        problems.append("source files/method versions changed during case")
    if case != initial or any(c["unchanged"] is not True for c in audit):
        problems.append("public call mutated input")
    nonfinite = _nonfinite_paths(raw)
    problems.extend("nonfinite raw result: " + p for p in nonfinite)
    checks = []
    for declared in case["expected"]["checks"]:
        passed = outcome.get("passed", {}).get(declared["name"])
        required = declared["required"]
        if problems and required:
            passed = False
        reason = "; ".join(problems) if problems else ("diagnostic only; no justified acceptance threshold" if not required and passed is None else "declared check failed or unavailable")
        checks.append(_check(declared["name"], passed, outcome.get("metrics"), declared["description"],
                             declared.get("tolerance"), declared.get("unit", ""), required, reason))
    checks.append(_check("source_and_input_identity", not problems, {"problems": problems}, "unchanged measured sources and per-call inputs", reason="; ".join(problems)))
    okay = not problems and all(c["passed"] is True for c in checks if c["required"])
    failed = [c["name"] for c in checks if c["required"] and c["passed"] is not True]
    return _safe({"id": case["id"], "state": "passed" if okay else "failed", "assertion_passed": bool(okay),
                  "reason": None if okay else "; ".join(problems + failed), "checks": checks,
                  "case": initial, "raw": raw, "reference": reference, "metrics": outcome.get("metrics", {}),
                  "call_audit": audit, "source_before": source, "source_after": after,
                  "source_consistent": consistent, "loaded_origins": origins,
                  "nonfinite_raw_paths": nonfinite, "elapsed_s": time.perf_counter() - start})


def _worker_command(request_path, result_path):
    return [sys.executable, "-P", "-B", "-m", "plimsoll._verification_worker", str(request_path), str(result_path)]


def _validate_worker_row(row, case, source):
    if row.get("id") != case["id"] or _digest(row.get("case")) != _digest(case):
        raise ValueError("worker case declaration mismatch")
    if _digest(row.get("source_before")) != _digest(source) or _digest(row.get("source_after")) != _digest(source):
        raise ValueError("worker measured source identity mismatch")
    declared = {c["name"]: c for c in case["expected"]["checks"]}
    checks = row.get("checks", [])
    names = [c.get("name") for c in checks]
    if len(names) != len(set(names)) or set(names) != set(declared) | {"source_and_input_identity"}:
        raise ValueError("worker omitted or substituted declared checks")
    for check in checks:
        if check["name"] in declared:
            expected = declared[check["name"]]
            if check.get("required") is not expected["required"] or any(
                _digest(check.get(field)) != _digest(value) for field, value in
                (("tolerance", expected.get("tolerance")), ("unit", expected.get("unit", "")), ("expected", expected["description"]))):
                raise ValueError("worker changed a predeclared requirement/tolerance/unit")
        elif check.get("required") is not True:
            raise ValueError("worker identity guard must remain required")
    if row.get("state") == "passed" or row.get("assertion_passed") is True:
        if next(check for check in checks if check["name"] == "source_and_input_identity").get("passed") is not True:
            raise ValueError("worker passing row has a failed identity guard")
        if row.get("source_consistent") is not True or not row.get("call_audit") or not all(
            c.get("unchanged") is True and c.get("before_sha256") == c.get("after_sha256") == _digest(c.get("request"))
            for c in row["call_audit"]):
            raise ValueError("worker passing row lacks unchanged source/input evidence")
        origins = row.get("loaded_origins")
        if not isinstance(origins, list) or not origins or _origin_problems(origins):
            raise ValueError("worker loaded origin mismatch")
        if row.get("nonfinite_raw_paths") or _nonfinite_paths(row.get("raw")):
            raise ValueError("worker passing row contains nonfinite raw evidence")
        raw = row.get("raw", {})
        problems = []
        if case["family"] == "flooding":
            problems = _flooding_problems(case, raw)
        elif case["kind"].startswith("transform."):
            for sample in (raw, raw.get("counterpart", {})):
                request = sample.get("request", {})
                if not all(isinstance(request.get(key), dict) for key in ("geometry", "loading", "options")) or not isinstance(request["loading"].get("input_fingerprint"), str):
                    raise ValueError("worker lacks sealed transform request")
                expected_call = {"args": [request["geometry"], request["loading"], request["options"]], "kwargs": {}}
                if not any(c.get("function") == "plimsoll.stability.solve_loaded_equilibrium" and _digest(c["request"]) == _digest(expected_call) for c in row["call_audit"]):
                    raise ValueError("returned transform request differs from actual sealed call")
                problems.extend(_equilibrium_problems(sample.get("solved", {}),
                    expected_fingerprint=request["loading"]["input_fingerprint"],
                    expected_liquids=[load["tank"]["id"] for load in request["options"].get("liquid_loads", [])]))
        else:
            if not isinstance(raw.get("request_geometry"), dict) or not all(_finite(raw.get("direct", {}).get(key)) for key in ("volume", "xlcb", "yb", "zb")):
                raise ValueError("worker lacks finite mesh measurements and geometry")
            if case["inputs"]["solve_equilibrium"]:
                state = raw.get("request_loading", {})
                if not isinstance(state.get("input_fingerprint"), str):
                    raise ValueError("worker lacks sealed mesh loading")
                options = {"rho_t_m3": case["inputs"]["rho_t_m3"]}
                expected_call = {"args": [raw["request_geometry"], state, options], "kwargs": {}}
                if _digest(raw.get("request_options")) != _digest(options) or not any(
                    c.get("function") == "plimsoll.stability.solve_loaded_equilibrium" and _digest(c["request"]) == _digest(expected_call)
                    for c in row["call_audit"]):
                    raise ValueError("returned mesh request differs from actual sealed call")
                problems = _equilibrium_problems(raw.get("solved", {}), expected_fingerprint=state["input_fingerprint"], expected_liquids=[])
        if problems:
            raise ValueError("worker passing raw evidence rejected: " + "; ".join(problems))


def _pending(case, state="pending", reason="awaiting explicit execution"):
    return {"id": case["id"], "state": state, "assertion_passed": False, "reason": reason,
            "checks": [_check(c["name"], None, expected=c["description"], tolerance=c.get("tolerance"),
                              unit=c.get("unit", ""), required=c["required"], reason=reason) for c in case["expected"]["checks"]]}


def _positive_limit(value, name):
    if not _finite(value) or value <= 0:
        raise ValueError(name + " must be a positive finite number")
    return float(value)


def _read_strict(path):
    def bad(token):
        raise ValueError("nonfinite token " + token)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate object key " + key)
            result[key] = value
        return result
    result = json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=bad, object_pairs_hook=pairs)
    _json(result)  # also rejects a finite token that overflowed, e.g. 1e999
    return result


def run_verification(suite="quick", *, case_timeout_s=180.0, total_timeout_s=1800.0, checkpoint=None):
    """Parent-owned sequential case/total limits; initial partial before spawning."""
    case_timeout_s = _positive_limit(case_timeout_s, "case_timeout_s")
    total_timeout_s = _positive_limit(total_timeout_s, "total_timeout_s")
    started = time.monotonic()
    cases = build_cases(suite)
    source = _source_identity()
    report = {"schema": "plimsoll-core-verification-1", "run_id": str(uuid.uuid4()),
              "generation": 0, "state": "partial", "suite": suite,
              "requested_case_ids": [c["id"] for c in cases], "cases": [_pending(c) for c in cases],
              "source_identity": source, "input_manifest_sha256": _digest(cases),
              "runtime": {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
                          "processor": platform.processor(), "source_meaning": "measured package files on disk plus actual loaded origins; not a cryptographic attestation of in-memory callables"},
              "limits": {"case_timeout_s": case_timeout_s, "total_timeout_s": total_timeout_s}}
    def publish():
        report["elapsed_s"] = time.monotonic() - started
        if checkpoint is not None:
            checkpoint(copy.deepcopy(report))
    publish()
    with tempfile.TemporaryDirectory(prefix="plimsoll-verify-") as temporary:
        scratch = Path(temporary)
        for index, case in enumerate(cases):
            case_started = time.monotonic()
            remaining = total_timeout_s - (time.monotonic() - started)
            if remaining <= 0:
                report["cases"][index] = _pending(case, "not_started", "total deadline exhausted before spawn")
            elif _source_identity() != source:
                report["source_identity"]["consistent"] = False
                report["cases"][index] = _pending(case, "not_started", "measured source identity changed before spawn")
            else:
                row = _pending(case, "error", "worker did not return a valid response")
                request_path, result_path = scratch / f"{index}-request.json", scratch / f"{index}-result.json"
                request = {"schema": "plimsoll-verification-worker-1", "run_id": report["run_id"], "case": case,
                           "case_sha256": _digest(case), "source_sha256": _digest(source)}
                request_path.write_text(_json(request), encoding="utf-8")
                environment = os.environ.copy()
                environment["PYTHONPATH"] = str(PACKAGE.parent)
                environment["PYTHONIOENCODING"] = "utf-8"
                process = None
                worker_started = case_started
                log = scratch / f"{index}-stderr.txt"
                try:
                    with log.open("wb") as stderr:
                        process = subprocess.Popen(_worker_command(request_path, result_path), cwd=scratch,
                                                   env=environment, stdout=subprocess.DEVNULL, stderr=stderr)
                        limit = min(case_timeout_s - (time.monotonic() - case_started), total_timeout_s - (time.monotonic() - started))
                        try:
                            if limit <= 0:
                                raise subprocess.TimeoutExpired(process.args, limit)
                            process.wait(timeout=limit)
                            if time.monotonic() - case_started > case_timeout_s or time.monotonic() - started > total_timeout_s:
                                raise subprocess.TimeoutExpired(process.args, limit)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                            row = _pending(case, "timeout", "parent terminated and reaped worker at case/total deadline")
                        else:
                            if process.returncode != 0:
                                raise RuntimeError("worker exited " + str(process.returncode))
                            response = _read_strict(result_path)
                            for key in ("schema", "run_id", "case_sha256", "source_sha256"):
                                if response.get(key) != request[key]:
                                    raise ValueError("worker response signature mismatch: " + key)
                            row = response["row"]
                            _validate_worker_row(row, case, source)
                            from .verification_report import validate_report
                            probe = copy.deepcopy(report)
                            probe["cases"][index] = row
                            validate_report(probe)
                            if time.monotonic() - case_started > case_timeout_s or time.monotonic() - started > total_timeout_s:
                                row = _pending(case, "timeout", "deadline exhausted before accepting worker evidence")
                except Exception as error:
                    row = _pending(case, "error", type(error).__name__ + ": " + str(error))
                finally:
                    if process is not None:
                        if process.poll() is None:
                            process.kill()
                        process.wait()
                        row["worker"] = {"pid": process.pid, "returncode": process.returncode, "reaped": True,
                                         "elapsed_s": time.monotonic() - worker_started,
                                         "stderr": log.read_text(encoding="utf-8", errors="replace")[:8192]}
                        progress = result_path.with_suffix(".progress.json")
                        if progress.exists():
                            try:
                                row["worker"]["progress"] = _read_strict(progress)
                            except (OSError, ValueError):
                                row["worker"]["progress_error"] = "worker progress was not readable strict JSON"
                report["cases"][index] = row
            report["generation"] += 1
            publish()
    if _source_identity() != source:
        report["source_identity"]["consistent"] = False
    report["state"] = "complete"
    report["generation"] += 1
    publish()
    # Publication time counts toward the total budget. If the final evidence
    # itself crosses the limit, replace any passing snapshot with a failure.
    if time.monotonic() - started > total_timeout_s and all(r["assertion_passed"] is True for r in report["cases"]):
        row = report["cases"][-1]
        row.update(state="timeout", assertion_passed=False, reason="total deadline exhausted during final verification/publication")
        row["checks"].append(_check("total_deadline", False, time.monotonic() - started, total_timeout_s, unit="s", reason=row["reason"]))
        report["generation"] += 1
        publish()
    return report
