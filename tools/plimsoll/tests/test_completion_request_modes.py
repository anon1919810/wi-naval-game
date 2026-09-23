"""Fixed-power and target-trim requests change calculation, not merely labels."""

from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import analysis, project_store  # noqa: E402


class RequestModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1] / "cases/projects"
        cls.box = project_store.load(root / "analytic_box.project.json")
        cls.generic = project_store.load(root / "generic_steamer.project.json")

    def test_trim_target_reports_required_moment_without_changing_free_equilibrium(self):
        free = analysis.compute_project(self.box, "loaded", {"stages": ["equilibrium"]})
        target = analysis.compute_project(self.box, "loaded", {
            "stages": ["equilibrium"], "equilibrium": {"target_trim_deg": 1.0}})
        eq = target["stages"]["equilibrium"]["data"]
        self.assertAlmostEqual(eq["trim_deg"], free["stages"]["equilibrium"]["data"]["trim_deg"])
        study = eq["trim_target_study"]
        self.assertEqual(study["status"], "completed")
        self.assertAlmostEqual(study["target_trim_deg"], 1.0)
        self.assertGreater(abs(study["required_longitudinal_moment_kNm"]), 0.01)
        self.assertNotEqual(target["request_fingerprint"], free["request_fingerprint"])

    def test_fixed_power_finds_speed_only_inside_supplied_bracket(self):
        base = {"stages": ["resistance"], "resistance": {
            "scenario_id": "holtrop-trim-study", "speeds_kn": [12.0, 20.0],
            "qpc_override": {"value": 0.55, "source": "declared test QPC", "estimate": True}}}
        middle = {"stages": ["resistance"], "resistance": {**base["resistance"], "speeds_kn": [16.0]}}
        predicted = analysis.compute_project(self.generic, "loaded", middle)
        target_power = predicted["stages"]["resistance"]["data"]["power_rows"][0]["shaft_power_kw"]
        self.assertIsNotNone(target_power)
        fixed = analysis.compute_project(self.generic, "loaded", {**base,
            "resistance": {**base["resistance"], "mode": "fixed_power",
                           "fixed_shaft_power_kw": target_power}})
        study = fixed["stages"]["resistance"]["data"]["fixed_power_study"]
        self.assertAlmostEqual(study["speed_kn"], 16.0, delta=0.03)
        self.assertFalse(study["model_applicable"])  # generic trim proxy remains non-primary
        self.assertNotEqual(fixed["request_fingerprint"], predicted["request_fingerprint"])


if __name__ == "__main__":
    unittest.main()
