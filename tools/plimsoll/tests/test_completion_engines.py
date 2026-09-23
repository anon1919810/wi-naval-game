"""Engine and variable-load views stay bound to selected loading groups."""

from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import analysis, project_store  # noqa: E402


class EngineCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = project_store.load(Path(__file__).resolve().parents[1]
                                         / "cases/projects/queen_mary_1913.project.json")

    def test_engine_view_uses_selected_machinery_and_variable_groups(self):
        totals = []
        for condition in ("normal-engineering", "deep-engineering"):
            result = analysis.compute_project(self.project, condition,
                                              {"stages": ["propulsion"]})
            data = result["stages"]["propulsion"]["data"]
            view = data["engine_page"]
            self.assertEqual(view["boilers_count"], 42)
            self.assertEqual(view["transmission"], "direct-drive turbine")
            self.assertAlmostEqual(view["machinery_mass_t"],
                result["stages"]["systems"]["data"]["systems"]["propulsion"]["ledger_mass_t"])
            group_rows = {r["id"]: r for r in result["stages"]["loading"]["data"]["groups"]}
            self.assertAlmostEqual(view["variable_load_t"], sum(
                group_rows[g]["total_mass_t"] for g in ("fuel", "water", "other_loads")))
            self.assertEqual(view["variable_group_ids"], ["fuel", "water", "other_loads"])
            totals.append(view["variable_load_t"])
            self.assertGreater(view["coal_share_of_declared_fuel_pct"], 0)
        self.assertGreater(totals[1], totals[0])


if __name__ == "__main__":
    unittest.main()
