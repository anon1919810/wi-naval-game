"""Serializable request validation and identity, without numerical execution."""
import copy
import hashlib
import json
import math

try:
    from . import project_io, geometry_analysis, stability
except ImportError:
    import project_io, geometry_analysis, stability

STAGES = ("loading", "systems", "l0", "geometry", "equilibrium", "hydrostatics", "gz", "deck",
          "hydrostatic_curve", "bonjean", "resistance", "propulsion", "endurance", "historical", "flooding")
DEFAULT_STAGES = ("loading", "systems", "l0", "geometry", "equilibrium", "hydrostatics", "deck", "propulsion")
VERSIONS = {"coordinator": "selected-loading-analysis-2", "geometry": geometry_analysis.METHOD_VERSION,
            "stability": stability.METHOD_VERSION, "request": "plimsoll-analysis-request-1"}


class AnalysisInputError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = copy.deepcopy(diagnostics)
        super().__init__("; ".join(d["message"] for d in diagnostics if d.get("blocking")))


def diagnostic(code, message, path="$", blocking=True):
    return dict(code=code, severity="error" if blocking else "warning", message=message,
                path=path, blocking=blocking)


def reject(message, path="$.options", code="analysis.request_invalid"):
    raise AnalysisInputError([diagnostic(code, message, path)])


def json_copy(value, path):
    try:
        text = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)
        text.encode("utf-8")
        return json.loads(text)
    except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError) as error:
        reject(f"requires finite serializable JSON: {error}", path)


def obj(value, allowed, path):
    if not isinstance(value, dict):
        reject("must be an object", path)
    if value.keys() - set(allowed):
        reject("unsupported fields: " + repr(sorted(value.keys() - set(allowed))), path)


def number(value, path, positive=False):
    try:
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid or positive and value <= 0:
        reject("requires a finite nonboolean " + ("positive " if positive else "") + "number", path)
    return float(value)


def grid(value, path, positive=False, limit=201):
    if not isinstance(value, list) or not 1 <= len(value) <= limit:
        reject(f"requires 1..{limit} explicitly supplied samples", path)
    result = [number(v, f"{path}[{i}]", positive) for i, v in enumerate(value)]
    if any(b <= a for a, b in zip(result, result[1:])):
        reject("samples must be strictly increasing", path)
    return result


def equilibrium_options(value, path="$.options.equilibrium"):
    obj(value, {"rho_t_m3", "heel_bounds_deg", "trim_bounds_deg", "heel_deg", "target_trim_deg",
                "max_iterations", "initial", "liquid_loads"}, path)
    result = copy.deepcopy(value)
    result["rho_t_m3"] = number(result.get("rho_t_m3", 1.025), path + ".rho_t_m3", True)
    for key, default in (("heel_bounds_deg", [-85, 85]), ("trim_bounds_deg", [-45, 45])):
        bounds = grid(result.get(key, default), path + "." + key, limit=2)
        if len(bounds) != 2 or not -89 < bounds[0] < bounds[1] < 89:
            reject("bounds must be two ordered angles strictly inside (-89,89)", path + "." + key)
        result[key] = bounds
    count = result.setdefault("max_iterations", 50)
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 1000:
        reject("max_iterations must be an integer in [1,1000]", path + ".max_iterations")
    initial = result.setdefault("initial", {"heel_deg": 0, "trim_deg": 0})
    obj(initial, {"heel_deg", "trim_deg"}, path + ".initial")
    for key in ("heel_deg", "trim_deg"):
        initial[key] = number(initial.get(key, 0), path + ".initial." + key)
        bounds = result[key.replace("_deg", "_bounds_deg")]
        if not bounds[0] <= initial[key] <= bounds[1]:
            reject("initial angle outside declared bounds", path + ".initial." + key)
    if "heel_deg" in result:
        angle = number(result["heel_deg"], path + ".heel_deg")
        if not result["heel_bounds_deg"][0] <= angle <= result["heel_bounds_deg"][1]:
            reject("prescribed heel outside declared bounds", path + ".heel_deg")
    if "target_trim_deg" in result:
        target = number(result["target_trim_deg"], path + ".target_trim_deg")
        if not result["trim_bounds_deg"][0] <= target <= result["trim_bounds_deg"][1]:
            reject("target trim outside declared bounds", path + ".target_trim_deg")
    if not isinstance(result.setdefault("liquid_loads", []), list):
        reject("liquid_loads must be an array", path + ".liquid_loads")
    return result


def normalize(project, condition_id, options=None):
    try:
        snapshot = project_io.normalize_project(project)
    except project_io.ProjectValidationError as error:
        raise AnalysisInputError(error.diagnostics) from error
    if not isinstance(condition_id, str) or condition_id not in {c["id"] for c in snapshot["loading_conditions"]}:
        reject("condition_id must identify an existing loading condition", "$.condition_id")
    supplied = {} if options is None else json_copy(options, "$.options")
    obj(supplied, {"stages", "equilibrium", "gz_angles_deg", "hydrostatic_waterlines_above_keel_m",
                  "bonjean_waterlines_above_keel_m", "resistance", "endurance_scenario_id", "flooding"}, "$.options")
    stages = supplied.get("stages", list(DEFAULT_STAGES))
    if (not isinstance(stages, list) or not stages or any(not isinstance(s, str) or s not in STAGES for s in stages)
            or len(set(stages)) != len(stages)):
        reject("stages must be a nonempty array of unique supported names", "$.options.stages")
    result = {"stages": [s for s in STAGES if s in stages],
              "equilibrium": equilibrium_options(supplied.get("equilibrium", {}))}
    for key, stage in (("gz_angles_deg", "gz"), ("hydrostatic_waterlines_above_keel_m", "hydrostatic_curve"),
                       ("bonjean_waterlines_above_keel_m", "bonjean")):
        result[key] = grid(supplied.get(key), "$.options." + key) if supplied.get(key) is not None or stage in stages else None
    for key in ("resistance", "endurance_scenario_id", "flooding"):
        result[key] = supplied.get(key)
    if "resistance" in stages and result["resistance"] is None:
        reject("requested resistance requires explicit scenario and speeds", "$.options.resistance")
    if result["resistance"] is not None:
        res = result["resistance"]
        obj(res, {"scenario_id", "scenario", "speeds_kn", "qpc_override", "mode",
                  "fixed_shaft_power_kw"}, "$.options.resistance")
        res.setdefault("mode", "predict_power")
        if res["mode"] not in ("predict_power", "fixed_power"):
            reject("mode must be predict_power or fixed_power", "$.options.resistance.mode")
        if ("scenario_id" in res) == ("scenario" in res):
            reject("choose exactly one scenario_id or scenario", "$.options.resistance")
        res["speeds_kn"] = grid(res.get("speeds_kn"), "$.options.resistance.speeds_kn", True)
        if res["mode"] == "fixed_power":
            if len(res["speeds_kn"]) < 2 or "qpc_override" not in res:
                reject("fixed power needs at least two bracketing speeds and one explicit QPC",
                       "$.options.resistance")
            res["fixed_shaft_power_kw"] = number(
                res.get("fixed_shaft_power_kw"), "$.options.resistance.fixed_shaft_power_kw", True)
        elif "fixed_shaft_power_kw" in res:
            reject("fixed_shaft_power_kw requires fixed_power mode",
                   "$.options.resistance.fixed_shaft_power_kw")
        if "scenario_id" in res:
            matches = [s for s in snapshot.get("resistance_scenarios", []) if s["id"] == res["scenario_id"]]
            if not matches:
                reject("unknown resistance scenario ID", "$.options.resistance.scenario_id")
            scenario = copy.deepcopy(matches[0])
        else:
            scenario = res["scenario"]
        checked = copy.deepcopy(snapshot)
        checked["resistance_scenarios"] = [scenario]
        if "qpc_override" in res:
            checked["resistance_scenarios"][0] = {**scenario, "qpc": res["qpc_override"]}
        try:
            project_io.normalize_project(checked)
        except project_io.ProjectValidationError as error:
            raise AnalysisInputError(error.diagnostics) from error
        count = 1 if "qpc_override" in res else len(scenario.get("qpc_sensitivity", {}).get("values", [None]))
        if len(res["speeds_kn"]) * count > 1000:
            reject("speed x QPC samples exceed request work limit 1000", "$.options.resistance")
        density = scenario.get("inputs", {}).get("density_kg_m3")
        if density is not None and not math.isclose(density, result["equilibrium"]["rho_t_m3"] * 1000, rel_tol=1e-10, abs_tol=1e-10):
            reject("scenario fluid density conflicts with selected equilibrium density", "$.options.resistance")
    if "endurance" in stages or result["endurance_scenario_id"] is not None:
        if result["endurance_scenario_id"] not in [s["id"] for s in snapshot.get("endurance_scenarios", [])]:
            reject("requested endurance requires an existing scenario ID", "$.options.endurance_scenario_id")
    if "flooding" in stages and result["flooding"] is None:
        reject("requested flooding requires an explicit scenario", "$.options.flooding")
    if result["flooding"] is not None:
        flood = result["flooding"]
        obj(flood, {"scenario", "options"}, "$.options.flooding")
        if not isinstance(flood.get("scenario"), dict):
            reject("flooding scenario must be an object", "$.options.flooding.scenario")
        opts = flood.setdefault("options", {})
        obj(opts, {"equilibrium", "gravity_m_s2", "max_steps", "max_step_halvings",
                   "remaining_gz_angles_deg", "remaining_gz_snapshot"}, "$.options.flooding.options")
        steps = opts.setdefault("max_steps", 10000)
        if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 100000:
            reject("max_steps must be an integer in [1,100000]", "$.options.flooding.options.max_steps")
        opts.setdefault("max_step_halvings", 40)
        opts.setdefault("gravity_m_s2", 9.80665)
        opts.setdefault("remaining_gz_snapshot", "final")
        if "equilibrium" in opts and equilibrium_options(opts["equilibrium"]) != result["equilibrium"]:
            reject("flooding must use the same equilibrium options", "$.options.flooding.options.equilibrium")
        halvings = opts["max_step_halvings"]
        if isinstance(halvings, bool) or not isinstance(halvings, int) or not 0 <= halvings <= 60:
            reject("max_step_halvings must be an integer in [0,60]", "$.options.flooding.options.max_step_halvings")
        opts["gravity_m_s2"] = number(opts["gravity_m_s2"], "$.options.flooding.options.gravity_m_s2", True)
        if opts["remaining_gz_snapshot"] not in ("final", "each_state"):
            reject("remaining_gz_snapshot must be final or each_state", "$.options.flooding.options.remaining_gz_snapshot")
        opts["equilibrium"] = {k: copy.deepcopy(v) for k, v in result["equilibrium"].items() if k != "liquid_loads"}
        sea = flood["scenario"].get("sea", {})
        if not isinstance(sea, dict):
            reject("sea must be an object", "$.options.flooding.scenario.sea")
        sea_density = sea.get("fluid_density_t_m3")
        if sea_density is not None and sea_density != result["equilibrium"]["rho_t_m3"]:
            reject("flooding sea density conflicts with selected equilibrium density", "$.options.flooding.scenario.sea")
        if "remaining_gz_angles_deg" in opts:
            opts["remaining_gz_angles_deg"] = grid(opts["remaining_gz_angles_deg"], "$.options.flooding.options.remaining_gz_angles_deg")
            rows = steps + 1 if opts["remaining_gz_snapshot"] == "each_state" else 1
            if rows * len(opts["remaining_gz_angles_deg"]) > 20000:
                reject("remaining GZ samples exceed request work limit 20000", "$.options.flooding.options")
    request = dict(schema="plimsoll-analysis-request-1", condition_id=condition_id, options=result)
    digest = hashlib.sha256(json.dumps(dict(project=snapshot, request=request, methods=VERSIONS),
        sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    return snapshot, request, digest
