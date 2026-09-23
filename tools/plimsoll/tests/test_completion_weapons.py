"""Completion checks for selected-ledger weapon page projections."""

from pathlib import Path
import copy
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import analysis, project_io, project_store  # noqa: E402


class WeaponCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "cases/projects/queen_mary_1913.project.json"
        cls.project = project_store.load(path)

    def _views(self, project=None):
        result = analysis.compute_project(
            self.project if project is None else project,
            "normal-engineering", {"stages": ["loading", "systems"]})
        self.assertEqual(result["stages"]["systems"]["status"], "completed")
        return result["stages"]["systems"]["data"]["page_rows"]

    def test_gun_mount_ammunition_rows_use_selected_ledger_once(self):
        views = self._views()
        for battery in ("main", "secondary"):
            projection = views[f"weapons.{battery}"]
            self.assertTrue(projection["values"]["matches_ledger_mass"])
            self.assertEqual(projection["values"]["uncovered_item_ids"], [])
            by_name = {row["row"]: row for row in projection["rows"]}
            self.assertEqual(set(by_name), {"guns", "mounts", "ammunition"})
            self.assertTrue(all(by_name[name]["weight_t"] is not None for name in by_name))
            self.assertTrue(all(by_name[name]["sources"] for name in by_name))
        self.assertIn("rotating gunhouse armour", " ".join(
            views["weapons.main"]["rows"][1]["model_boundaries"]))

    def test_broadside_uses_projectile_mass_not_ammunition_outfit_mass(self):
        views = self._views()
        main = views["weapons.main"]["broadside"]
        secondary = views["weapons.secondary"]["broadside"]
        self.assertAlmostEqual(main["projectile_mass_kg"], 1400 * 0.45359237)
        self.assertAlmostEqual(main["mass_kg"], 8 * 1400 * 0.45359237)
        self.assertAlmostEqual(secondary["mass_kg"], 8 * 31 * 0.45359237)
        self.assertNotEqual(main["mass_kg"] / 1000,
                            views["weapons.main"]["rows"][2]["weight_t"])

    def test_five_misc_zones_have_unknown_mass_without_ledger_bindings(self):
        projection = self._views()["weapons.misc_weight"]
        rows = projection["rows"]
        self.assertEqual([row["row"] for row in rows], [
            "hull_below", "hull_above", "on_deck", "above_deck", "void"])
        for row in rows:
            self.assertIsNone(row["weight_t"])
            self.assertEqual(row["mass_status"], "no_ledger_binding")
            self.assertEqual(row["typed_status"], "partial_unknown")
        self.assertIsNone(projection["values"]["matches_ledger_mass"])
        self.assertNotIn("page_rows.mass_mismatch",
                         {d["code"] for d in projection["diagnostics"]})

    def test_repeated_torpedo_mine_and_depth_rows_preserve_typed_inputs(self):
        project = copy.deepcopy(self.project)
        rows = project["systems"]["weapons"]["torpedo"]["page_rows"]
        rows.extend([
            dict(row="torpedo_third", weight_item_ids=[], typed=dict(tubes=1, carried=3,
                diameter_mm=450, length_m=5.2, arrangement="stern"), source="test fixture", estimate=True),
            dict(row="mine_group_2", weight_item_ids=[], typed=dict(count=12, reloads=0,
                kind="moored", unit_weight_kg=80, arrangement="stern rails"), source="test fixture", estimate=True),
            dict(row="depth_group_2", weight_item_ids=[], typed=dict(count=4, reloads=8,
                kind="depth charge", unit_weight_kg=100, arrangement="quarterdeck"), source="test fixture", estimate=True),
        ])
        self.assertFalse([d for d in project_io.validate_project(project) if d["blocking"]])
        projected = self._views(project)["weapons.torpedo"]
        by_row = {row["row"]: row for row in projected["rows"]}
        self.assertEqual(by_row["torpedo_third"]["typed"]["diameter_mm"], 450)
        self.assertEqual(by_row["mine_group_2"]["typed"]["count"], 12)
        self.assertEqual(by_row["depth_group_2"]["typed"]["reloads"], 8)
        self.assertIsNone(by_row["mine_group_2"]["weight_t"])

    def test_typed_row_rejects_invalid_counts_and_unsupported_fields(self):
        project = copy.deepcopy(self.project)
        rows = project["systems"]["weapons"]["torpedo"]["page_rows"]
        rows.append(dict(row="mine_group_2", weight_item_ids=[],
            typed=dict(count=-2, imaginary=99), source="test fixture", estimate=True))
        errors = [d for d in project_io.validate_project(project) if d["blocking"]]
        self.assertTrue(any("typed" in d["path"] for d in errors))


if __name__ == "__main__":
    unittest.main()
