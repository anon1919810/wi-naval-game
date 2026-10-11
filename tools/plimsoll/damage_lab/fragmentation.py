"""Bounded representative rays in rectangular rooms; normalized game estimates."""
import math
import random

METHOD = "compartment-fragment-rays-1"
EPS = 1e-6


def face_axis(point, bounds):
    axes = [i for i, (p, c, s) in enumerate(zip(point, bounds["center_m"], bounds["size_m"]))
            if abs(abs(p - c) - s / 2) <= EPS]
    return axes[0] if len(axes) == 1 else None


def interface_area(a, b, axis):
    return math.prod(min(a["center_m"][j] + a["size_m"][j] / 2,
                         b["center_m"][j] + b["size_m"][j] / 2)
                     - max(a["center_m"][j] - a["size_m"][j] / 2,
                           b["center_m"][j] - b["size_m"][j] / 2)
                     for j in range(3) if j != axis)


def normalize_detonation(document, rooms):
    """Admit an explicit origin and boundary responses, retaining provenance."""
    from .request import (compartment_box, metadata, number, obj, on_face, point_inside,
                          records, reject, shared_face, vector)
    det = document["detonation"]
    path = "$.experiment.detonation"
    obj(det, {"position_m", "fragment_count", "seed", "boundaries", "source", "estimate"}, path)
    metadata(det, path)
    det["position_m"] = vector(det.get("position_m"), path + ".position_m")
    det["fragment_count"] = number(det.get("fragment_count"), path + ".fragment_count", 32, 512, True)
    det["seed"] = number(det.get("seed"), path + ".seed", 0, 2**32 - 1, True)
    boxes = {rid: compartment_box(room) for rid, room in rooms.items()}
    for i, a in enumerate(boxes.values()):
        for b in list(boxes.values())[i + 1:]:
            if all(min(a["center_m"][j] + a["size_m"][j] / 2, b["center_m"][j] + b["size_m"][j] / 2)
                   - max(a["center_m"][j] - a["size_m"][j] / 2, b["center_m"][j] - b["size_m"][j] / 2) > EPS
                   for j in range(3)):
                reject("fragment tracing requires nonoverlapping room interiors", "$.project.compartments")
    origins = [rid for rid, bounds in boxes.items() if all(abs(p-c) < s/2-EPS
               for p, c, s in zip(det["position_m"], bounds["center_m"], bounds["size_m"]))]
    if len(origins) != 1:
        reject("detonation must be strictly inside one declared compartment", path + ".position_m")
    if det["fragment_count"] * (len(rooms) + len(document["modules"]) + len(document["crew_groups"])) > 65536:
        reject("reduce fragment count/layout to at most 65536 ray-target checks", path + ".fragment_count")
    faces = set()
    for i, wall in enumerate(records(det.get("boundaries"), path + ".boundaries", 64)):
        p = f"{path}.boundaries[{i}]"
        obj(wall, {"id", "from_id", "to_id", "position_m", "transmission", "breach_threshold",
                   "max_breach_area_m2", "discharge_coefficient", "source", "estimate"}, p)
        a, b = wall.get("from_id"), wall.get("to_id")
        if not isinstance(a, str) or a not in rooms or not isinstance(b, str) or b not in {*rooms, "sea"} or a == b:
            reject("boundary requires a room and a distinct adjacent room or declared sea", p)
        wall["position_m"] = vector(wall.get("position_m"), p + ".position_m")
        point = wall["position_m"]
        axis = face_axis(point, boxes[a])
        if axis is None or not on_face(point, boxes[a]):
            reject("boundary point must lie inside exactly one rectangular face, away from edges", p + ".position_m")
        if b != "sea":
            if not shared_face(point, boxes[a], boxes[b]):
                reject("internal boundary requires opposing shared faces", p + ".position_m")
            area = interface_area(boxes[a], boxes[b], axis)
            face = tuple(sorted((a, b)))
        else:
            sign = 1 if point[axis] > boxes[a]["center_m"][axis] else -1
            # Any positive adjacent overlap makes this face an internal/mixed face,
            # not a declared whole-face sea proxy.
            for rid, other in boxes.items():
                if rid == a:
                    continue
                opposite = other["center_m"][axis] - sign * other["size_m"][axis] / 2
                overlap = all(min(boxes[a]["center_m"][j]+boxes[a]["size_m"][j]/2, other["center_m"][j]+other["size_m"][j]/2)
                              - max(boxes[a]["center_m"][j]-boxes[a]["size_m"][j]/2, other["center_m"][j]-other["size_m"][j]/2) > EPS
                              for j in range(3) if j != axis)
                if abs(point[axis] - opposite) <= EPS and overlap:
                    reject("a face adjoining another room cannot be declared as sea", p + ".to_id")
            area = math.prod(s for j, s in enumerate(boxes[a]["size_m"]) if j != axis)
            face = (a, "sea", axis, sign)
        if face in faces:
            reject("duplicate physical boundary response", p)
        faces.add(face)
        for key in ("transmission", "breach_threshold", "discharge_coefficient"):
            wall[key] = number(wall.get(key), p + "." + key, 0, 1)
        wall["max_breach_area_m2"] = number(wall.get("max_breach_area_m2"), p + ".max_breach_area_m2", 0, min(area, 1000))
        if wall["max_breach_area_m2"] > 0:
            for breach in document["breaches"]:
                if {breach["from_id"], breach["to_id"]} == {a, b} and abs(breach["position_m"][axis] - point[axis]) <= EPS:
                    reject("manual breach duplicates a boundary configured to generate a breach", p)
        if any(breach["id"] == "fragment:" + wall["id"] for breach in document["breaches"]):
            reject("manual breach identifier collides with generated breach", p + ".id")
    return det


def ray_interval(origin, direction, bounds):
    """Intersect a unit ray with an AABB, including origins inside the box."""
    lo, hi = -math.inf, math.inf
    for p, d, c, s in zip(origin, direction, bounds["center_m"], bounds["size_m"]):
        if abs(d) < 1e-12:
            if abs(p-c) > s/2:
                return None
        else:
            a, b = (c-s/2-p)/d, (c+s/2-p)/d
            lo, hi = max(lo, min(a, b)), min(hi, max(a, b))
    return (lo, hi) if hi >= max(0, lo) else None


def directions(count, seed):
    """Rotate equal-area spherical samples using a frozen seed."""
    rng = random.Random(seed)
    angles = [rng.random() * 2 * math.pi for _ in range(3)]
    for i in range(count):
        z = 1 - 2 * (i + .5) / count
        radius, angle = math.sqrt(max(0, 1-z*z)), i * math.pi * (3-math.sqrt(5))
        point = [radius*math.cos(angle), radius*math.sin(angle), z]
        for axis, angle in enumerate(angles):
            a, b = (axis+1) % 3, (axis+2) % 3
            point[a], point[b] = point[a]*math.cos(angle)-point[b]*math.sin(angle), point[a]*math.sin(angle)+point[b]*math.cos(angle)
        yield point


def trace_fragments(project, experiment, *, cancel_check=None):
    """Trace fixed boundaries once; new holes affect only subsequent hydraulics."""
    from .request import compartment_box, point_inside
    det = experiment["detonation"]
    origin, count = det["position_m"], det["fragment_count"]
    severity, reach = experiment["impact"]["severity"], experiment["impact"]["radius_m"]
    boxes = {r["id"]: compartment_box(r) for r in project["compartments"]}
    origin_room = next(rid for rid, box in boxes.items() if point_inside(origin, box))
    module_exposure = {m["id"]: 0.0 for m in experiment["modules"]}
    crew_exposure = {g["id"]: 0.0 for g in experiment["crew_groups"]}
    loads = {w["id"]: 0.0 for w in det["boundaries"]}
    targets = [("module", m, m["box"], module_exposure) for m in experiment["modules"]]
    targets += [("crew", g, g["station_box"], crew_exposure) for g in experiment["crew_groups"]]
    traces, canceled = [], False
    point_at = lambda direction, distance: [p+d*distance for p, d in zip(origin, direction)]
    if severity > 0 and reach > 0:
        for index, direction in enumerate(directions(count, det["seed"])):
            if cancel_check is not None and cancel_check():
                canceled = True
                break
            room, distance, transmission = origin_room, 0.0, 1.0
            segments, hits, visited = [], [], set()
            termination, blocked_by = "range", None
            for _ in range(len(boxes) + 1):
                interval = ray_interval(origin, direction, boxes[room])
                end = min(reach, interval[1])
                start_point, end_point = point_at(direction, distance), point_at(direction, end)
                segments.append(dict(from_m=start_point, to_m=end_point, compartment_id=room, transmission=transmission))
                for kind, target, box, totals in targets:
                    identity = (kind, target["id"])
                    if target["compartment_id"] != room or identity in visited:
                        continue
                    intersect = ray_interval(origin, direction, box)
                    if intersect is not None and intersect[1] >= distance-EPS and max(distance, intersect[0], 0) <= end+EPS:
                        hit_distance = max(distance, intersect[0], 0)
                        contribution = severity/count * transmission * max(0, 1-hit_distance/reach)
                        totals[target["id"]] += contribution
                        hits.append(dict(kind=kind, id=target["id"], position_m=point_at(direction, hit_distance), exposure=contribution))
                        visited.add(identity)
                if end >= reach-EPS:
                    break
                probe = point_at(direction, end + EPS*4)
                neighbor = next((rid for rid, box in boxes.items() if rid != room and point_inside(probe, box)), None)
                wall = None
                for candidate in det["boundaries"]:
                    endpoints = {candidate["from_id"], candidate["to_id"]}
                    matches = endpoints == {room, neighbor} if neighbor else candidate["from_id"] == room and candidate["to_id"] == "sea"
                    axis = face_axis(candidate["position_m"], boxes[candidate["from_id"]])
                    if matches and abs(end_point[axis] - candidate["position_m"][axis]) <= EPS:
                        wall = candidate
                        break
                through = wall["transmission"] if wall else 0.0
                if wall:
                    loads[wall["id"]] += severity/count * transmission * max(0, 1-end/reach) * (1-through)
                segments[-1]["boundary_id"] = wall["id"] if wall else None
                segments[-1]["boundary_transmission"] = through
                transmission *= through
                if transmission == 0:
                    termination, blocked_by = "sealed_boundary", wall["id"] if wall else "undeclared:" + room
                    break
                if neighbor is None:
                    segments.append(dict(from_m=end_point, to_m=point_at(direction, reach), compartment_id="sea", transmission=transmission))
                    termination = "declared_sea_exit"
                    break
                room, distance = neighbor, end
            traces.append(dict(index=index, direction=direction, segments=segments, hits=hits,
                               termination=termination, blocked_by=blocked_by))
    generated, responses = [], []
    for wall in det["boundaries"]:
        load, threshold = loads[wall["id"]], wall["breach_threshold"]
        area = wall["max_breach_area_m2"] * max(0, min(1, (load-threshold)/(1-threshold))) if threshold < 1 and not canceled else 0.0
        responses.append({**wall, "absorbed_exposure": load, "generated_area_m2": area})
        if area > 0:
            generated.append(dict(id="fragment:" + wall["id"], from_id=wall["from_id"], to_id=wall["to_id"],
                position_m=wall["position_m"][:], area_m2=area, discharge_coefficient=wall["discharge_coefficient"],
                source={"method": METHOD, "boundary_id": wall["id"], "declared_response_source": wall["source"]}, estimate=True))
    for totals in (module_exposure, crew_exposure):
        for key, value in totals.items():
            totals[key] = 0.0 if canceled else min(severity, max(0, value))
    return dict(method_version=METHOD, position_m=origin[:], compartment_id=origin_room, canceled=canceled,
        seed=det["seed"], fragment_count=count, traces=traces, module_exposure=module_exposure,
        crew_exposure=crew_exposure, boundaries=responses, generated_breaches=generated,
        estimate=True, source=det["source"])
