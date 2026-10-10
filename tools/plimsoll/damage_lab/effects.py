"""Transparent, estimated gameplay rules; no hydraulic or medical formulas."""
import math


def exposure(impact, bounds):
    distance = math.sqrt(sum(max(0, abs(p-c)-s/2)**2 for p, c, s in
        zip(impact["position_m"], bounds["center_m"], bounds["size_m"])))
    radius = impact["radius_m"]
    return impact["severity"] * (max(0, 1-distance/radius) if radius else float(distance == 0))


def product(values):
    if any(v == 0 for v in values):
        return 0.0
    return None if any(v is None for v in values) else math.prod(values)


def refresh(state, experiment):
    powers = []
    for module, definition in zip(state["modules"], experiment["modules"]):
        groups = [g for g in state["crew_groups"] if g["module_id"] == module["id"]]
        required = definition["required_staff"]
        available = None if any(g["available"] is None for g in groups) else sum(g["available"] for g in groups)
        staffing = 1.0 if not required else None if available is None else min(1.0, available/required)
        module["staffing_availability"] = staffing
        module["effective_availability"] = product([module["mechanical_integrity"], module["flooding_availability"], staffing])
        module["status"] = ("unknown" if module["effective_availability"] is None else
            "disabled" if module["effective_availability"] == 0 else "damaged" if module["effective_availability"] < 1 else "available")
        nominal = definition["nominal_shaft_power_kw"]
        power = 0.0 if module["effective_availability"] == 0 else None if nominal is None or module["effective_availability"] is None else nominal * module["effective_availability"]
        module["available_shaft_power_kw"] = power
        powers.append(power)
    state["capabilities"] = {"shaft_power_kw": None if any(p is None for p in powers) else math.fsum(powers),
                            "known_shaft_power_subtotal_kw": math.fsum(p for p in powers if p is not None),
                            "estimate": True, "source": experiment["rules"]["source"]}


def initial_state(experiment):
    state = dict(time_s=0.0, event_index=-1, ship=None, compartments=[], modules=[], crew_groups=[])
    for row in experiment["modules"]:
        state["modules"].append(dict(id=row["id"], label=row["label"], compartment_id=row["compartment_id"],
            mechanical_integrity=row["initial_integrity"], flooding_availability=1.0, causes=[]))
    for row in experiment["crew_groups"]:
        n = row["personnel"]
        state["crew_groups"].append(dict(id=row["id"], label=row["label"], compartment_id=row["compartment_id"],
            module_id=row["module_id"], initial_personnel=n, available=n, incapacitated=None if n is None else 0,
            dead=None if n is None else 0, evacuated=None if n is None else 0,
            location=row["compartment_id"], casualty_location=row["compartment_id"],
            evacuated_location=None, evacuation_triggered=False, causes=[]))
    refresh(state, experiment)
    return state
