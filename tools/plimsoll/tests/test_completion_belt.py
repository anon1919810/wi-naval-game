"""A declared protected-span study is separate from the armour mass ledger."""

import json
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import analysis, project_io, project_store  # noqa: E402


class MinimumBeltStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = project_store.load(Path(__file__).resolve().parents[1]
                                         / "cases/projects/queen_mary_1913.project.json")

    def _project(self, complete):
        project = json.loads(json.dumps(self.project))
        project["systems"]["armour"]["fixed"]["minimum_main_belt"] = {
            "protected_compartment_ids": ["engine-room-fixture", "boiler-room-fixture",
                                          "forward-magazine-fixture"],
            "aft_margin_m": 5.0, "fore_margin_m": 7.0,
            "inventory_complete": complete,
            "source": "declared engineering study of three model compartments",
            "estimate": True,
        }
        return project

    def _study(self, project):
        result = analysis.compute_project(project, "normal-engineering",
                                          {"stages": ["loading", "systems"]})
        self.assertEqual(result["stages"]["systems"]["status"], "completed")
        return result["stages"]["systems"]["data"]["page_rows"]["armour.fixed"]["minimum_main_belt"]

    def test_complete_inventory_gives_sourced_continuous_protected_span(self):
        study = self._study(self._project(True))
        self.assertEqual(study["status"], "completed")
        self.assertAlmostEqual(study["length_m"], 143.75, places=8)
        self.assertEqual(study["method"], "declared_compartment_extent_envelope_v1")
        self.assertTrue(study["estimate"])
        self.assertEqual(len(study["protected_compartments"]), 3)

    def test_incomplete_inventory_keeps_final_length_unknown(self):
        study = self._study(self._project(False))
        self.assertEqual(study["status"], "unavailable")
        self.assertIsNone(study["length_m"])
        self.assertAlmostEqual(study["declared_span_m"], 131.75, places=8)

    def test_belt_study_is_projected_without_any_armour_page_rows(self):
        """The study depends on compartment geometry, not on armour rows."""
        project = self._project(True)
        del project["systems"]["armour"]["fixed"]["page_rows"]
        result = analysis.compute_project(project, "normal-engineering",
                                          {"stages": ["loading", "systems"]})
        data = result["stages"]["systems"]["data"]
        self.assertEqual(result["stages"]["systems"]["status"], "completed")
        # Available at the documented independent path...
        study = data["minimum_main_belt"]
        self.assertEqual(study["status"], "completed")
        self.assertAlmostEqual(study["length_m"], 143.75, places=8)
        # ...and not hidden behind a page-row view that does not exist.
        self.assertNotIn("armour.fixed", data.get("page_rows") or {})

    def test_belt_study_paths_agree_when_page_rows_exist(self):
        data = analysis.compute_project(self._project(True), "normal-engineering",
                                        {"stages": ["loading", "systems"]})["stages"]["systems"]["data"]
        self.assertEqual(data["minimum_main_belt"]["length_m"],
                         data["page_rows"]["armour.fixed"]["minimum_main_belt"]["length_m"])

    def test_absent_study_reports_its_reason_in_both_paths(self):
        project = self._project(True)
        del project["systems"]["armour"]["fixed"]["minimum_main_belt"]
        data = analysis.compute_project(project, "normal-engineering",
                                        {"stages": ["loading", "systems"]})["stages"]["systems"]["data"]
        for study in (data["minimum_main_belt"],
                      data["page_rows"]["armour.fixed"]["minimum_main_belt"]):
            self.assertEqual(study["status"], "unavailable")
            self.assertIsNone(study["length_m"])
            self.assertEqual(study["reason"], "no protected-compartment study declared")

    def test_unknown_compartment_is_rejected_before_calculation(self):
        project = self._project(True)
        project["systems"]["armour"]["fixed"]["minimum_main_belt"]["protected_compartment_ids"] = ["ghost"]
        with self.assertRaises(project_io.ProjectValidationError):
            project_io.normalize_project(project)

    def test_armour_group_subtotals_use_declared_rows_without_double_counting(self):
        result = analysis.compute_project(self.project, "normal-engineering",
                                          {"stages": ["systems"]})
        view = result["stages"]["systems"]["data"]["page_rows"]["armour.fixed"]
        by_group = view["groups"]
        self.assertAlmostEqual(by_group["belts"]["weight_t"], sum(
            row["weight_t"] for row in view["rows"] if row["group"] == "belts"))
        self.assertAlmostEqual(sum(group["weight_t"] for group in by_group.values()),
                               view["values"]["ledger_leaf_mass_t"])


if __name__ == "__main__":
    unittest.main()
