"""Selected-loading studies must use the actual equilibrium and deck points."""

import json
import math
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import analysis, project_store  # noqa: E402


class GeometryCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = project_store.load(Path(__file__).resolve().parents[1]
                                         / "cases/projects/queen_mary_1913.project.json")
        cls.box = project_store.load(Path(__file__).resolve().parents[1]
                                     / "cases/projects/analytic_box.project.json")

    def test_deck_segment_exposes_selected_endpoint_clearances_and_percent(self):
        result = analysis.compute_project(self.project, "normal-engineering",
                                          {"stages": ["deck"]})
        data = result["stages"]["deck"]["data"]
        points = {row["id"]: row for row in data["points"]}
        segment = data["profile"]["segments"][0]
        self.assertAlmostEqual(segment["aft_clearance_m"],
                               points["aft-centre"]["normal_clearance_m"])
        self.assertAlmostEqual(segment["fore_clearance_m"],
                               points["fore-centre"]["normal_clearance_m"])
        self.assertAlmostEqual(segment["length_pct"],
                               100 * segment["length_m"] / data["profile"]["reference_length_m"])

    def test_loaded_roll_uses_selected_gm_and_declared_gyration(self):
        project = json.loads(json.dumps(self.box))
        project["hull"]["roll_gyration_coeff"] = 0.38
        project["hull"].setdefault("sources", {})["roll_gyration_coeff"] = "declared study coefficient"
        result = analysis.compute_project(project, "loaded",
                                          {"stages": ["hydrostatics"]})
        data = result["stages"]["hydrostatics"]["data"]
        study = data["loaded_roll"]
        self.assertEqual(study["status"], "completed")
        gm = data["values"]["gm_t_m"]
        beam = data["values"]["waterline_beam_body_y_m"]
        self.assertAlmostEqual(study["period_s"],
                               2 * math.pi * 0.38 * beam / math.sqrt(9.80665 * gm))
        self.assertEqual(study["source"], "declared study coefficient")

    def test_missing_gyration_does_not_inherit_l0_default(self):
        result = analysis.compute_project(self.project, "normal-engineering",
                                          {"stages": ["hydrostatics"]})
        study = result["stages"]["hydrostatics"]["data"]["loaded_roll"]
        self.assertEqual(study["status"], "unavailable")
        self.assertIsNone(study["period_s"])

    def test_design_and_selected_length_beam_ratios_keep_distinct_definitions(self):
        result = analysis.compute_project(self.box, "loaded", {"stages": ["l0", "hydrostatics"]})
        design = result["stages"]["l0"]["data"]["hull_ratios"]
        selected = result["stages"]["hydrostatics"]["data"]["selected_length_beam_ratio"]
        self.assertAlmostEqual(design["design_lwl_over_beam"],
                               self.box["hull"]["lwl_m"] / self.box["hull"]["beam_m"])
        self.assertIsNotNone(selected["value"])
        self.assertNotEqual(design["method"], selected["method"])


if __name__ == "__main__":
    unittest.main()
