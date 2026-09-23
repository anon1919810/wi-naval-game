"""A sourced rotating-armour subcomponent never becomes a second ship weight."""

import copy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import analysis, project_io, project_store  # noqa: E402


class RotatingArmourComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = project_store.load(Path(__file__).resolve().parents[1]
                                      / "cases/projects/queen_mary_1913.project.json")

    def declared(self, mass=400.0):
        project = copy.deepcopy(self.base)
        project["systems"]["weapons"]["main"]["rotating_armour_component"] = {
            "mount_weight_item_id": "main-mounts", "mass_t": mass,
            "source": "synthetic independently declared component fixture", "estimate": True,
        }
        return project

    def report(self, project):
        return analysis.compute_project(project, "normal-engineering",
                                        {"stages": ["loading", "systems"]})

    def component(self, report):
        return report["stages"]["systems"]["data"]["page_rows"]["weapons.main"]["rotating_armour_component"]

    def test_unknown_queen_mary_component_stays_unknown(self):
        component = self.component(self.report(self.base))
        self.assertEqual(component["status"], "unavailable")
        self.assertIsNone(component["rotating_armour_mass_t"])

    def test_sourced_component_is_subtracted_from_selected_mount_not_added_to_ship(self):
        original = self.report(self.base)
        project = self.declared()
        revised = self.report(project)
        component = self.component(revised)
        mounts = next(row for row in revised["stages"]["systems"]["data"]["page_rows"]["weapons.main"]["rows"]
                      if row["row"] == "mounts")
        self.assertEqual(component["status"], "completed")
        self.assertEqual(component["rotating_armour_mass_t"], 400.0)
        self.assertAlmostEqual(component["other_mount_mass_t"], mounts["weight_t"] - 400.0)
        self.assertEqual(component["mount_mass_t"], mounts["weight_t"])
        self.assertTrue(component["estimate"])
        self.assertEqual(original["stages"]["loading"]["data"]["values"]["total_mass_t"],
                         revised["stages"]["loading"]["data"]["values"]["total_mass_t"])
        self.assertEqual(original["stages"]["systems"]["data"]["systems"]["armour.fixed"]["ledger_mass_t"],
                         revised["stages"]["systems"]["data"]["systems"]["armour.fixed"]["ledger_mass_t"])
        with TemporaryDirectory() as folder:
            path = Path(folder) / "component.project.json"
            project_store.save(path, project)
            self.assertEqual(self.component(self.report(project_store.load(path)))["rotating_armour_mass_t"], 400.0)

    def test_selected_loading_smaller_than_component_is_unavailable(self):
        project = self.declared()
        project["loading_conditions"][0]["overrides"]["main-mounts"] = {"mass_t": 300.0}
        report = self.report(project)
        component = self.component(report)
        self.assertEqual(component["status"], "unavailable")
        self.assertEqual(component["mount_mass_t"], 300.0)
        self.assertEqual(component["declared_rotating_armour_mass_t"], 400.0)
        self.assertIsNone(component["other_mount_mass_t"])
        self.assertIn("exceeds", component["reason"])
        self.assertEqual(component["diagnostics"][0]["code"], "page_rows.rotating_armour_exceeds_mount")
        self.assertEqual(component["diagnostics"][0]["path"],
                         "$.systems.weapons.main.rotating_armour_component.mass_t")
        self.assertIn("page_rows.rotating_armour_exceeds_mount",
                      {row["code"] for row in report["diagnostics"]})
        near = self.declared(mass=300.0 + 1e-10)
        near["loading_conditions"][0]["overrides"]["main-mounts"] = {"mass_t": 300.0}
        self.assertEqual(self.component(self.report(near))["status"], "unavailable")

    def test_malformed_declaration_is_rejected_but_unknown_mass_is_allowed(self):
        for change in ({"mount_weight_item_id": "main-guns"}, {"mass_t": -1.0},
                       {"source": None}, {"estimate": None}):
            with self.subTest(change=change):
                project = self.declared()
                project["systems"]["weapons"]["main"]["rotating_armour_component"].update(change)
                with self.assertRaises(project_io.ProjectValidationError):
                    project_io.normalize_project(project)
        project = self.declared()
        project["systems"]["weapons"]["main"]["page_rows"] = None
        with self.assertRaises(project_io.ProjectValidationError):
            project_io.normalize_project(project)
        component = self.component(self.report(self.declared(mass=None)))
        self.assertEqual(component["status"], "unavailable")
        self.assertIsNone(component["rotating_armour_mass_t"])


if __name__ == "__main__":
    unittest.main()
