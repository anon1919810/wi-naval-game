"""Deck coverage is an explicit plan-area study, independent of armour mass."""

import copy
import csv
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import analysis, exports, project_io, project_store  # noqa: E402


class DeckCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = project_store.load(Path(__file__).resolve().parents[1]
                                      / "cases/projects/queen_mary_1913.project.json")

    def project_with_study(self, covered=1200.0, reference=2000.0):
        project = copy.deepcopy(self.base)
        project["systems"]["armour"]["fixed"]["deck_coverage"] = {
            "covered_plan_area_m2": {"value": covered, "source": "synthetic plan-area fixture", "estimate": True},
            "reference_plan_area_m2": {"value": reference, "source": "synthetic plan-area fixture", "estimate": True},
        }
        return project

    def study(self, project):
        result = analysis.compute_project(project, "normal-engineering", {"stages": ["systems"]})
        return result["stages"]["systems"]["data"]["deck_coverage"]

    def test_sourced_plan_areas_calculate_without_changing_mass(self):
        original = analysis.compute_project(self.base, "normal-engineering", {"stages": ["loading", "systems"]})
        project = self.project_with_study()
        revised = analysis.compute_project(project, "normal-engineering", {"stages": ["loading", "systems"]})
        study = revised["stages"]["systems"]["data"]["deck_coverage"]
        self.assertEqual(study["status"], "completed")
        self.assertAlmostEqual(study["coverage_pct"], 60.0)
        self.assertEqual(study["method"], "declared_protected_plan_area_ratio_v1")
        self.assertEqual(study["covered_plan_area_m2"], 1200.0)
        self.assertTrue(study["estimate"])
        self.assertEqual(original["stages"]["loading"]["data"]["values"]["total_mass_t"],
                         revised["stages"]["loading"]["data"]["values"]["total_mass_t"])
        with TemporaryDirectory() as folder:
            path = Path(folder) / "deck-coverage.project.json"
            project_store.save(path, project)
            self.assertAlmostEqual(self.study(project_store.load(path))["coverage_pct"], 60.0)

    def test_missing_area_stays_unknown(self):
        self.assertEqual(self.study(self.base)["status"], "unavailable")
        study = self.study(self.project_with_study(covered=None))
        self.assertEqual(study["status"], "unavailable")
        self.assertIsNone(study["coverage_pct"])
        self.assertIn("covered_plan_area_m2", study["reason"])

    def test_zero_coverage_is_known_zero_not_unknown(self):
        study = self.study(self.project_with_study(covered=0.0))
        self.assertEqual(study["status"], "completed")
        self.assertEqual(study["coverage_pct"], 0.0)

    def test_json_and_csv_export_the_computed_result(self):
        report = analysis.compute_project(self.project_with_study(), "normal-engineering",
                                          {"stages": ["systems"]})
        json_report = json.loads(exports.serialize_report(report, "json"))
        self.assertEqual(json_report["stages"]["systems"]["data"]["deck_coverage"]["coverage_pct"], 60.0)
        rows = list(csv.DictReader(StringIO(exports.serialize_report(report, "csv"))))
        path = '$["stages"]["systems"]["data"]["deck_coverage"]["coverage_pct"]'
        self.assertEqual([row["value"] for row in rows if row["path"] == path], ["60.0"])

    def test_invalid_area_or_missing_source_is_rejected(self):
        for covered, reference in ((2100.0, 2000.0), (-1.0, 2000.0), (10.0, 0.0)):
            with self.subTest(covered=covered, reference=reference):
                with self.assertRaises(project_io.ProjectValidationError):
                    project_io.normalize_project(self.project_with_study(covered, reference))
        project = self.project_with_study()
        project["systems"]["armour"]["fixed"]["deck_coverage"]["covered_plan_area_m2"]["source"] = None
        with self.assertRaises(project_io.ProjectValidationError):
            project_io.normalize_project(project)
        project = self.project_with_study()
        project["systems"]["armour"]["fixed"]["deck_coverage"]["covered_plan_area_m2"] = 12.0
        with self.assertRaises(project_io.ProjectValidationError):
            project_io.normalize_project(project)


if __name__ == "__main__":
    unittest.main()
