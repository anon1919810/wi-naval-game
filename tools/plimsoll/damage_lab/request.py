"""Strict admission, geometry ownership and immutable experiment identity."""
import copy
import hashlib
import json
import math

from .. import _analysis_request, _flooding_kernel as flooding_kernel, flooding, loading, project_io, tank_geometry

SCHEMA = "plimsoll-damage-lab-request-1"
METHOD = "localized-game-aftermath-1"
META = {"source": "declared gameplay layout placeholder; not historical calibration", "estimate": True}
TOLERANCE_M = 1e-6


class LabInputError(ValueError):
    def __init__(self, message, path="$", code="damage_lab.input_invalid"):
        self.diagnostics = [dict(code=code, path=path, message=message, severity="error", blocking=True)]
        super().__init__(message)


def reject(message, path="$" ):
    raise LabInputError(message, path)


def obj(value, keys, path):
    if not isinstance(value, dict):
        reject("requires an object", path)
    if value.keys() - set(keys):
        reject("unsupported fields: " + repr(sorted(value.keys() - set(keys))), path)


def text(value, path):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        reject("requires a nonempty string of at most 200 characters", path)
    return value


def number(value, path, low=0, high=1e12, integer=False):
    try:
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid or not low <= value <= high or integer and not isinstance(value, int):
        reject(f"requires a finite nonboolean {'integer' if integer else 'number'} in [{low},{high}]", path)
    return int(value) if integer else float(value)


def metadata(record, path):
    source = record.get("source")
    if not (isinstance(source, str) and source.strip() or isinstance(source, dict) and source):
        reject("requires nonempty source metadata", path + ".source")
    if not isinstance(record.get("estimate"), bool):
        reject("requires boolean estimate metadata", path + ".estimate")


def vector(value, path, positive=False):
    if not isinstance(value, list) or len(value) != 3:
        reject("requires exactly three coordinates", path)
    result = [number(v, f"{path}[{i}]", 0 if positive else -1e6, 1e6) for i, v in enumerate(value)]
    if positive and min(result) <= 0:
        reject("box sizes must be positive", path)
    return result


def box(value, path):
    obj(value, {"center_m", "size_m"}, path)
    return {"center_m": vector(value.get("center_m"), path + ".center_m"),
            "size_m": vector(value.get("size_m"), path + ".size_m", True)}


def compartment_box(compartment):
    return {"center_m": [compartment["x_m"], compartment["y_m"],
        compartment["keel_to_bottom_m"] + compartment["height_m"] / 2],
        "size_m": [compartment["length_m"], compartment["beam_m"], compartment["height_m"]]}


def supported_compartments(project):
    """The lab requires more geometry than the general project import contract."""
    rows = project.get("compartments", [])
    if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
        reject("requires 1..64 explicitly declared project compartments", "$.project.compartments")
    rooms = {}
    for index, room in enumerate(rows):
        path = f"$.project.compartments[{index}]"
        if not isinstance(room, dict):
            reject("requires a rectangular compartment record", path)
        identity = text(room.get("id"), path + ".id")
        if identity in rooms:
            reject("duplicate compartment identifier", path + ".id")
        if "label" in room:
            text(room["label"], path + ".label")
        for key in ("length_m", "beam_m", "height_m"):
            if number(room.get(key), path + "." + key, 0, 1e6) <= 0:
                reject("compartment dimensions must be positive", path + "." + key)
        for key in ("x_m", "y_m", "keel_to_bottom_m"):
            number(room.get(key), path + "." + key, -1e6, 1e6)
        number(room.get("permeability"), path + ".permeability", 0, 1)
        metadata(room, path)
        box(compartment_box(room), path)
        rooms[identity] = room
    return rooms


def point_inside(point, bounds):
    return all(abs(p-c) <= s/2 + TOLERANCE_M for p, c, s in zip(point, bounds["center_m"], bounds["size_m"]))


def on_face(point, bounds):
    return point_inside(point, bounds) and any(abs(abs(p-c)-s/2) <= TOLERANCE_M
        for p, c, s in zip(point, bounds["center_m"], bounds["size_m"]))


def shared_face(point, a, b):
    """A real facing bulkhead with positive overlap, rather than coincident corners."""
    for axis in range(3):
        ca, cb = a["center_m"][axis], b["center_m"][axis]
        sa, sb = a["size_m"][axis], b["size_m"][axis]
        for sign in (-1, 1):
            face = ca + sign * sa / 2
            if abs(face - (cb - sign * sb / 2)) > TOLERANCE_M or abs(point[axis] - face) > TOLERANCE_M:
                continue
            overlap = [min(a["center_m"][j]+a["size_m"][j]/2, b["center_m"][j]+b["size_m"][j]/2)
                       - max(a["center_m"][j]-a["size_m"][j]/2, b["center_m"][j]-b["size_m"][j]/2)
                       for j in range(3) if j != axis]
            if min(overlap) > TOLERANCE_M and point_inside(point, a) and point_inside(point, b):
                return True
    return False


def contained(inner, outer):
    return all(abs(a-b)+sa/2 <= sb/2 + TOLERANCE_M for a, b, sa, sb in
               zip(inner["center_m"], outer["center_m"], inner["size_m"], outer["size_m"]))


def records(value, path, limit=100):
    if not isinstance(value, list) or len(value) > limit:
        reject(f"requires an array with at most {limit} entries", path)
    seen = set()
    for i, row in enumerate(value):
        p = f"{path}[{i}]"
        if not isinstance(row, dict):
            reject("requires a record", p)
        identity = text(row.get("id"), p + ".id")
        if identity in seen:
            reject("duplicate identifier", p + ".id")
        seen.add(identity)
        metadata(row, p)
    return value


def default_experiment(project):
    """Explicit estimated equipment placeholders; never invent crew or ship rooms."""
    project = project_io.normalize_project(project)
    rooms = list(supported_compartments(project).values())
    modules, groups = [], []
    for room in rooms:
        bounds = compartment_box(room)
        bounds["size_m"] = [s * .35 for s in bounds["size_m"]]
        mid = "equipment:" + room["id"]
        modules.append(dict(id=mid, label=room.get("label", room["id"]) + " / equipment proxy",
            role="declared_equipment", compartment_id=room["id"], box=bounds, weight_item_ids=[],
            required_staff=6, initial_integrity=1, nominal_shaft_power_kw=None, **META))
        groups.append(dict(id="watch:" + room["id"], label="Duty group / " + room["id"],
            compartment_id=room["id"], module_id=mid, station_box=copy.deepcopy(bounds), personnel=None, **META))
    return dict(schema="plimsoll-damage-lab-experiment-1", duration_s=10, time_step_s=1,
        modules=modules, crew_groups=groups, initial_water_m3={r["id"]: 0 for r in rooms},
        impact=dict(position_m=copy.deepcopy(modules[0]["box"]["center_m"]), severity=.5, radius_m=2, **META),
        breaches=[], remaining_gz_angles_deg=[0, 10, 20],
        rules=dict(casualty_fraction=.4, fatal_fraction=.25, module_flood_threshold=.5,
                   evacuate_fill_fraction=.3, **META), **META)


def normalize_request(project, condition_id, experiment):
    try:
        snapshot, _, _ = _analysis_request.normalize(project, condition_id, {"stages": ["loading"]})
        document = json.loads(json.dumps(experiment, ensure_ascii=False, allow_nan=False))
    except (ValueError, TypeError, OverflowError, RecursionError) as error:
        if hasattr(error, "diagnostics"):
            raise
        reject("requires finite serializable JSON: " + str(error))
    p = "$.experiment"
    obj(document, {"schema", "source", "estimate", "duration_s", "time_step_s", "initial_water_m3",
        "modules", "crew_groups", "impact", "breaches", "rules", "remaining_gz_angles_deg"}, p)
    if document.get("schema") != "plimsoll-damage-lab-experiment-1":
        reject("unsupported experiment schema", p + ".schema")
    metadata(document, p)
    document["duration_s"] = number(document.get("duration_s"), p + ".duration_s", 0, 60)
    document["time_step_s"] = number(document.get("time_step_s"), p + ".time_step_s", 1e-6, 60)
    if document["duration_s"] / document["time_step_s"] > 120:
        reject("at most 120 nominal flooding steps", p + ".time_step_s")
    rooms = supported_compartments(snapshot)
    if snapshot.get("geometry", {}).get("kind") != "offsets":
        reject("requires explicit inline hull offsets for the 3D/core laboratory", "$.project.geometry")
    bounds = {rid: box(compartment_box(r), "$.project.compartments." + rid) for rid, r in rooms.items()}
    water = document.get("initial_water_m3")
    obj(water, rooms, p + ".initial_water_m3")
    if water.keys() != rooms.keys():
        reject("declare initial added water for every compartment", p + ".initial_water_m3")
    for rid, room in rooms.items():
        capacity = math.prod(bounds[rid]["size_m"]) * room["permeability"]
        water[rid] = number(water[rid], p + ".initial_water_m3." + rid, 0, capacity)
    modules = records(document.get("modules"), p + ".modules")
    if not modules:
        reject("requires at least one declared module", p + ".modules")
    ledger = loading.resolve_loading(snapshot, condition_id)
    item_ids = {item["id"] for item in ledger["effective_items"]}
    ownership = {token for item in ledger["effective_items"] if item["mass_t"] != 0
                 for token in (item["id"], *item.get("includes", []))}
    if ownership & {"lab-water:" + rid for rid in rooms}:
        reject("added lab water is already owned by the base loading ledger", "$.project.weight_groups")
    for i, row in enumerate(modules):
        path = f"{p}.modules[{i}]"
        obj(row, {"id", "label", "role", "compartment_id", "box", "weight_item_ids", "required_staff",
                  "initial_integrity", "nominal_shaft_power_kw", "source", "estimate"}, path)
        text(row.get("label"), path + ".label")
        text(row.get("role"), path + ".role")
        if not isinstance(row.get("compartment_id"), str) or row["compartment_id"] not in rooms:
            reject("unknown compartment", path + ".compartment_id")
        row["box"] = box(row.get("box"), path + ".box")
        if not contained(row["box"], bounds[row["compartment_id"]]):
            reject("module box must be inside its compartment", path + ".box")
        links = row.get("weight_item_ids")
        if not isinstance(links, list) or any(not isinstance(v, str) or v not in item_ids for v in links) or len(set(links)) != len(links):
            reject("weight links must uniquely identify selected ledger items", path + ".weight_item_ids")
        row["required_staff"] = number(row.get("required_staff"), path + ".required_staff", 0, 100000, True)
        row["initial_integrity"] = number(row.get("initial_integrity"), path + ".initial_integrity", 0, 1)
        row.setdefault("nominal_shaft_power_kw", None)
        if row.get("nominal_shaft_power_kw") is not None:
            row["nominal_shaft_power_kw"] = number(row["nominal_shaft_power_kw"], path + ".nominal_shaft_power_kw")
    mids = {r["id"]: r for r in modules}
    for i, row in enumerate(records(document.get("crew_groups"), p + ".crew_groups")):
        path = f"{p}.crew_groups[{i}]"
        obj(row, {"id", "label", "compartment_id", "module_id", "station_box", "personnel", "source", "estimate"}, path)
        text(row.get("label"), path + ".label")
        if not isinstance(row.get("compartment_id"), str) or row["compartment_id"] not in rooms:
            reject("unknown compartment", path + ".compartment_id")
        row.setdefault("module_id", None)
        row.setdefault("personnel", None)
        mid = row.get("module_id")
        if mid is not None and (not isinstance(mid, str) or mid not in mids or mids[mid]["compartment_id"] != row["compartment_id"]):
            reject("one crew group may staff one module in its compartment", path + ".module_id")
        row["station_box"] = box(row.get("station_box"), path + ".station_box")
        if not contained(row["station_box"], bounds[row["compartment_id"]]):
            reject("station box must be inside its compartment", path + ".station_box")
        if row.get("personnel") is not None:
            row["personnel"] = number(row["personnel"], path + ".personnel", 0, 100000, True)
    impact = document.get("impact")
    obj(impact, {"position_m", "severity", "radius_m", "source", "estimate"}, p + ".impact")
    metadata(impact, p + ".impact")
    impact["position_m"] = vector(impact.get("position_m"), p + ".impact.position_m")
    impact["severity"] = number(impact.get("severity"), p + ".impact.severity", 0, 1)
    impact["radius_m"] = number(impact.get("radius_m"), p + ".impact.radius_m", 0, 1000)
    rules = document.get("rules")
    rule_keys = ("casualty_fraction", "fatal_fraction", "module_flood_threshold", "evacuate_fill_fraction")
    obj(rules, {*rule_keys, "source", "estimate"}, p + ".rules")
    metadata(rules, p + ".rules")
    for key in rule_keys:
        rules[key] = number(rules.get(key), p + ".rules." + key, 0, 1)
    for i, row in enumerate(records(document.get("breaches"), p + ".breaches", 64)):
        path = f"{p}.breaches[{i}]"
        obj(row, {"id", "from_id", "to_id", "position_m", "area_m2", "discharge_coefficient", "source", "estimate"}, path)
        a, b = row.get("from_id"), row.get("to_id")
        if not isinstance(a, str) or not isinstance(b, str) or a == b or a not in {*rooms, "sea"} or b not in {*rooms, "sea"}:
            reject("breach endpoints must resolve distinct compartments or sea", path)
        row["position_m"] = vector(row.get("position_m"), path + ".position_m")
        if not all(on_face(row["position_m"], bounds[rid]) for rid in (a, b) if rid != "sea"):
            reject("breach must lie on the compartment boundary/shared face", path + ".position_m")
        if a != "sea" and b != "sea" and not shared_face(row["position_m"], bounds[a], bounds[b]):
            reject("internal breach requires opposing shared compartment faces", path + ".position_m")
        row["area_m2"] = number(row.get("area_m2"), path + ".area_m2", 0, 1000)
        row["discharge_coefficient"] = number(row.get("discharge_coefficient"), path + ".discharge_coefficient", 0, 1)
    angles = document.get("remaining_gz_angles_deg")
    if not isinstance(angles, list) or not 1 <= len(angles) <= 21:
        reject("requires 1..21 GZ angles", p + ".remaining_gz_angles_deg")
    document["remaining_gz_angles_deg"] = [number(v, p + ".remaining_gz_angles_deg", -80, 80) for v in angles]
    if any(b <= a for a, b in zip(angles, angles[1:])):
        reject("GZ angles must be strictly increasing", p + ".remaining_gz_angles_deg")
    versions = {"damage_lab": METHOD, **_analysis_request.VERSIONS, "flooding": flooding.METHOD_VERSION,
                "hydraulics": flooding_kernel.METHOD_VERSION, "liquid_geometry": tank_geometry.METHOD_VERSION}
    request = dict(schema=SCHEMA, condition_id=condition_id, experiment=document, method_versions=versions)
    encoded = json.dumps(dict(project=snapshot, request=request), sort_keys=True, ensure_ascii=False,
                         allow_nan=False, separators=(",", ":")).encode("utf-8")
    return snapshot, request, hashlib.sha256(encoded).hexdigest()
