"""Actual canonical selected loads exercise the same coordinator as CLI cases."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis
import loading

CASES = Path(__file__).resolve().parents[1] / "cases" / "projects"


class CanonicalAnalysisTests(unittest.TestCase):
    def test_four_real_nonzero_trim_conditions_bind_holtrop_and_selected_fuel(self):
        for filename in ("queen_mary_1913.project.json", "generic_steamer.project.json"):
            project = json.loads((CASES / filename).read_text(encoding="utf-8"))
            volumes, fuels = [], []
            for condition in project["loading_conditions"]:
                with self.subTest(project=filename, condition=condition["id"]):
                    state = loading.resolve_loading(project, condition["id"])
                    result = analysis.compute_project(project, condition["id"], dict(
                        stages=["resistance", "endurance", "deck"],
                        resistance=dict(scenario_id="holtrop-trim-study", speeds_kn=[18]),
                        endurance_scenario_id="steady-cruise-study"))
                    if filename == "queen_mary_1913.project.json":
                        self.assertEqual(result["stages"]["resistance"]["status"], "unavailable")
                        # The source project explicitly stores this condition's
                        # derived study; compute must never invent the choice.
                        result = analysis.compute_project(project, condition["id"], dict(
                            stages=["resistance", "endurance", "deck"],
                            resistance=dict(scenario_id="holtrop-support-" + condition["id"], speeds_kn=[18]),
                            endurance_scenario_id="steady-cruise-study"))
                    eq = result["stages"]["equilibrium"]["data"]
                    self.assertTrue(eq["converged"])
                    self.assertGreater(abs(eq["trim_deg"]), .5)
                    self.assertEqual(eq["input_fingerprint"], result["input_fingerprint"])
                    self.assertAlmostEqual(eq["volume_m3"]*1.025, state["values"]["total_mass_t"], delta=state["values"]["total_mass_t"]*1e-8)
                    resistance = result["stages"]["resistance"]["data"]
                    self.assertEqual(result["stages"]["resistance"]["status"], "completed")
                    self.assertFalse(resistance["validity"]["model_applicable"])
                    self.assertEqual(resistance["selected_plane"]["p"], eq["p"])
                    self.assertEqual(result["stages"]["endurance"]["status"], "completed")
                    volumes.append(resistance["selected_volume_m3"])
                    fuels.append(result["stages"]["propulsion"]["data"]["values"]["coal_t"])
            if len(volumes) == 2:
                self.assertGreater(volumes[1], volumes[0])
                self.assertGreater(fuels[1], fuels[0])


if __name__ == "__main__":
    unittest.main()
