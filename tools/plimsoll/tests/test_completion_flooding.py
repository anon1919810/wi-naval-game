"""Nonzero Queen Mary proxy flooding acceptance, separate from timing evidence."""

import copy
import json
from pathlib import Path
import sys
import time
import unittest

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import flooding  # noqa: E402


class QueenMaryFloodingCompletionTests(unittest.TestCase):
    def test_connected_generic_stops_at_numerical_hydraulic_equilibrium(self):
        cases = Path(__file__).resolve().parents[1] / "cases/projects"
        project = json.loads((cases / "generic_flooding_box.project.json").read_text(encoding="utf-8"))
        presets = json.loads((cases / "damage-presets.json").read_text(encoding="utf-8"))
        preset = next(item for item in presets["presets"] if item["id"] == "generic-two-connected")
        start = time.perf_counter()
        result = flooding.simulate_flooding(project, preset["condition_id"],
            preset["scenario"], {"max_steps": 100,
                                  "cancel_check": lambda _state: time.perf_counter()-start > 30})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["stop_reason"], "hydraulic_equilibrium_tolerance")
        self.assertLess(result["final_state"]["time_s"], 60)
        self.assertLessEqual(result["terminal_max_head_difference_m"],
                             result["terminal_head_tolerance_m"])
        self.assertLess(abs(result["mass_conservation_error_t"]), 1e-8)

    def test_ten_second_flood_preserves_mass_and_reports_residual_stability(self):
        cases = Path(__file__).resolve().parents[1] / "cases/projects"
        project = json.loads((cases / "queen_mary_1913.project.json").read_text(encoding="utf-8"))
        presets = json.loads((cases / "damage-presets.json").read_text(encoding="utf-8"))
        preset = next(item for item in presets["presets"] if item["id"] == "queen-mary-single-proxy")
        scenario = copy.deepcopy(preset["scenario"])
        scenario["duration_s"] = 10.0
        result = flooding.simulate_flooding(project, preset["condition_id"], scenario,
                                            {"remaining_gz_angles_deg": [0, 5, 10]})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["stop_reason"], "scheduled_completion")
        self.assertEqual(result["timeline"][-1]["time_s"], 10.0)
        self.assertGreater(result["final_state"]["total_onboard_water_mass_t"], 0)
        for state in result["timeline"]:
            self.assertLess(abs(state["mass_conservation_error_t"]), 1e-8)
            self.assertLess(abs(state["volume_conservation_error_m3"]), 1e-8)
        self.assertIsNotNone(result["remaining_gz"])
        self.assertEqual([row["angle_deg"] for row in result["remaining_gz"]["rows"]],
                         [0, 5, 10])
        self.assertFalse(result["validity"]["historical_validated"])


if __name__ == "__main__":
    unittest.main()
