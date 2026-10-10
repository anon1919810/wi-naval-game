"""One known hit, estimated aftermath, and the real coupled flooding core."""
import copy
import math
import time

from .. import analysis
from .effects import exposure, initial_state, refresh
from .request import METHOD, normalize_request


def flooding_scenario(project, experiment):
    tank_ids = {r["id"]: "lab-water:" + r["id"] for r in project["compartments"]}
    tanks = []
    for room in project["compartments"]:
        tanks.append({k: copy.deepcopy(room[k]) for k in ("length_m", "beam_m", "height_m", "x_m", "y_m", "keel_to_bottom_m", "permeability", "source", "estimate")})
        tanks[-1].update(id=tank_ids[room["id"]], free_surface=True, fluid_density_t_m3=1.025,
                         initial_volume_m3=experiment["initial_water_m3"][room["id"]])
    connections = []
    for row in experiment["breaches"]:
        x, y, z = row["position_m"]
        connections.append(dict(id=row["id"], **{"from": tank_ids.get(row["from_id"], "sea"), "to": tank_ids.get(row["to_id"], "sea")},
            x_m=x, y_m=y, z_m=z, area_m2=row["area_m2"], discharge_coefficient=row["discharge_coefficient"],
            fluid_density_t_m3=1.025, open=True, source=row["source"], estimate=row["estimate"]))
    return dict(schema="plimsoll-flooding-scenario-1", id="damage-lab-single-hit", source=experiment["source"], estimate=experiment["estimate"],
        duration_s=experiment["duration_s"], time_step_s=experiment["time_step_s"], tanks=tanks, connections=connections,
        sea=dict(id="sea", fluid_density_t_m3=1.025, source="declared seawater density for gameplay experiment", estimate=True))


def run_experiment(project, condition_id, experiment, *, cancel_check=None):
    if cancel_check is not None and not callable(cancel_check):
        raise ValueError("cancel_check must be callable")
    started = time.perf_counter()
    snapshot, request, fingerprint = normalize_request(project, condition_id, experiment)
    experiment = request["experiment"]
    state = initial_state(experiment)
    events, snapshots = [], [copy.deepcopy(state)]

    def event(kind, target_id, message, time_s=0.0):
        index = len(events)
        events.append(dict(index=index, time_s=time_s, kind=kind, target_id=target_id, message=message))
        state.update(time_s=time_s, event_index=index)
        refresh(state, experiment)
        snapshots.append(copy.deepcopy(state))

    for row, definition in zip(state["modules"], experiment["modules"]):
        loss = exposure(experiment["impact"], definition["box"])
        row["mechanical_integrity"] = max(0, definition["initial_integrity"]-loss)
        if loss:
            row["causes"].append("localized_game_impact")
        event("module_impact", row["id"], f"Gameplay exposure {loss:.3f}; equipment mass remains in the loading ledger")
    for row, definition in zip(state["crew_groups"], experiment["crew_groups"]):
        n = definition["personnel"]
        influence = exposure(experiment["impact"], definition["station_box"])
        if n is not None:
            affected = math.floor(n*influence*experiment["rules"]["casualty_fraction"])
            dead = math.floor(affected*experiment["rules"]["fatal_fraction"])
            row.update(available=n-affected, incapacitated=affected-dead, dead=dead)
        if influence:
            row["causes"].append("estimated_game_casualties")
        event("crew_impact", row["id"], "Declared gameplay casualty estimate" if n is not None else "Personnel unknown; casualty counts remain unknown")
    scenario = flooding_scenario(snapshot, experiment)
    core = analysis.compute_project(snapshot, condition_id, dict(stages=["flooding"],
        flooding=dict(scenario=scenario, options=dict(max_steps=240, remaining_gz_angles_deg=experiment["remaining_gz_angles_deg"],
                                                    remaining_gz_snapshot="final"))), cancel_check=cancel_check)
    native = core["stages"]["flooding"].get("data") or {}
    rooms = {r["id"]: r for r in snapshot["compartments"]}
    for row in native.get("timeline", []):
        state["ship"] = copy.deepcopy(row)
        state["compartments"] = [dict(id=rid, volume_m3=row["volumes_m3"]["lab-water:"+rid],
            capacity_m3=r["length_m"]*r["beam_m"]*r["height_m"]*r["permeability"],
            fill_fraction=row["volumes_m3"]["lab-water:"+rid]/(r["length_m"]*r["beam_m"]*r["height_m"]*r["permeability"]))
            for rid, r in rooms.items() if r["permeability"] > 0]
        fills = {c["id"]: c["fill_fraction"] for c in state["compartments"]}
        for module in state["modules"]:
            if fills.get(module["compartment_id"], 0) >= experiment["rules"]["module_flood_threshold"] and fills.get(module["compartment_id"], 0) > 0:
                module["flooding_availability"] = 0
                if "flood_disable" not in module["causes"]:
                    module["causes"].append("flood_disable")
        for group in state["crew_groups"]:
            if fills.get(group["compartment_id"], 0) >= experiment["rules"]["evacuate_fill_fraction"] and fills.get(group["compartment_id"], 0) > 0:
                group["evacuation_triggered"] = True
                if group["available"] is not None:
                    group["evacuated"] += group["available"]
                    group["available"] = 0
                group["evacuated_location"] = "abstract-assembly"
                if "scripted_flood_evacuation" not in group["causes"]:
                    group["causes"].append("scripted_flood_evacuation")
        event("accepted_ship_state", None, "Accepted core flooding/equilibrium state", row["time_s"])
    return dict(schema="plimsoll-damage-lab-result-1", status=core["status"], project_id=snapshot["id"], condition_id=condition_id,
        method_version=METHOD, method_versions=request["method_versions"], request=request, request_fingerprint=fingerprint,
        project_fingerprint=core["project_fingerprint"], input_fingerprint=core["input_fingerprint"], input_snapshot=snapshot,
        core_analysis=core, events=events, snapshots=snapshots, final_state=copy.deepcopy(state),
        validity={**core["validity"], "gameplay_estimate": True, "historical_validated": None}, diagnostics=core["diagnostics"],
        elapsed_wall_seconds=time.perf_counter()-started, simulated_duration_s=state["time_s"],
        assumptions=["Localized normalized gameplay damage; no penetration, blast-pressure or medical injury calculation",
                     "Base loading excludes the added water owned by lab tanks; users must declare water ownership correctly",
                     "Single hit; fixed declared compartment-to-sea/shared-face hydraulic proxies",
                     "Scripted crew evacuation to an abstract assembly location; no pathfinding",
                     "No structural failure, fire, speed prediction or real-time performance claim"])
