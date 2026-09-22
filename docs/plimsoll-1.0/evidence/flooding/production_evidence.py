"""Emit Task 6 production refinement and selected mutation evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
TESTS = ROOT / "tools" / "plimsoll" / "tests"
sys.path.insert(0, str(TESTS))

import test_flooding as fixture


answer = fixture.oracle()["coupled_heave"]
rows = []
for dt in fixture.DT_SEQUENCE:
    result = fixture.flooding.simulate_flooding(
        fixture.box_project(), "normal", fixture.scenario(dt=dt), options={})
    influx = result["final_state"]["volumes_m3"]["centre"] - 8.0
    draft = result["final_state"]["equilibrium"]["waterline_above_keel_m"]
    rows.append({
        "dt_s": dt,
        "influx_m3": influx,
        "influx_abs_error_m3": abs(influx-answer["net_sea_inflow_m3"]),
        "draft_m": draft,
        "draft_abs_error_m": abs(draft-answer["final_draft_m"]),
        "heel_deg": result["final_state"]["equilibrium"]["heel_deg"],
        "trim_deg": result["final_state"]["equilibrium"]["trim_deg"],
        "volume_residual_m3": result["volume_conservation_error_m3"],
        "mass_residual_t": result["mass_conservation_error_t"],
        "accepted_steps": len(result["timeline"])-1,
    })

original_loads = fixture.flooding._liquid_loads
fixture.flooding._liquid_loads = lambda tanks, volumes: []
try:
    omitted_mass = fixture.flooding.simulate_flooding(
        fixture.box_project(), "normal", fixture.scenario(dt=0.125), options={})
finally:
    fixture.flooding._liquid_loads = original_loads

omitted_mass_influx = omitted_mass["final_state"]["volumes_m3"]["centre"] - 8.0
print(json.dumps({
    "oracle": {
        "influx_m3": answer["net_sea_inflow_m3"],
        "draft_m": answer["final_draft_m"],
    },
    "production_refinement": rows,
    "selected_mutant_omit_floodwater_mass": {
        "status": omitted_mass["status"],
        "influx_m3": omitted_mass_influx,
        "draft_m": omitted_mass["final_state"]["equilibrium"]["waterline_above_keel_m"],
        "relative_influx_error": (
            abs(omitted_mass_influx-answer["net_sea_inflow_m3"])
            / answer["net_sea_inflow_m3"]),
        "would_pass_predeclared_one_percent_bound": (
            abs(omitted_mass_influx-answer["net_sea_inflow_m3"])
            / answer["net_sea_inflow_m3"] < 0.01),
    },
}, indent=2, sort_keys=True))
