"""Guns page projection: broadside shell weight, honest unknowns, no reverse inference.

These tests guard the discipline in the long-task SPS-pages contract:

  * 齐射弹重 = 单发弹丸质量（声明值）× 单舷炮数，与「全舰弹药携带量」分开；
  * 不得用账本质量反推单发弹丸质量；未知不写 0，未知 → 结果未知 + 诊断；
  * 单发弹丸质量取自既有声明（counted_ammunition_mass 模型的
    inputs.projectile_mass_kg + input_provenance.projectile_mass_kg.{source,estimate}），
    不另设一份 fact，避免与账本弹药模型出现第二来源而分歧。
"""
from pathlib import Path
import copy
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import analysis, loading, project_store  # noqa: E402


QM = Path(__file__).resolve().parents[1] / "cases/projects/queen_mary_1913.project.json"


class GunsPageRowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = project_store.load(QM)
        cls.state = loading.resolve_loading(cls.project, "normal-engineering")

    def _guns(self, project=None):
        result = analysis.compute_project(
            self.project if project is None else project,
            "normal-engineering", {"stages": ["loading", "systems"]})
        self.assertEqual(result["stages"]["systems"]["status"], "completed")
        return result["stages"]["systems"]["data"]["page_rows"]

    def test_broadside_equals_single_shell_times_broadside_count(self):
        views = self._guns()
        for battery in ("main", "secondary"):
            g = views[f"weapons.{battery}"]["guns"]
            shell = g["shell_mass_kg"]["value"]
            self.assertIsNotNone(shell, "%s shell mass must be declared" % battery)
            self.assertAlmostEqual(g["broadside_mass_kg"], g["broadside_guns"] * shell)
            self.assertAlmostEqual(g["per_gun_shell_kg"], g["rounds_per_gun"] * shell)
            # the broadside shell weight is distinct from the ship-wide outfit
            self.assertNotEqual(g["broadside_mass_kg"], g["ship_wide_ammunition_t"])

    def test_broadside_excludes_charge_and_outfit(self):
        g = self._guns()["weapons.main"]["guns"]
        # 8 guns × 635.029318 kg shell only; the 492 t outfit includes charge and
        # all 80 rounds per gun, so it is far larger than one broadside of shells.
        self.assertAlmostEqual(g["broadside_mass_kg"], 8 * 635.029318)
        self.assertGreater(g["ship_wide_ammunition_t"], g["broadside_mass_kg"] / 1000.0)

    def test_missing_shell_mass_makes_broadside_unknown(self):
        project = copy.deepcopy(self.project)
        battery = project["systems"]["weapons"]["main"]
        # Remove the declared single projectile mass (the counted_ammunition_mass
        # model). The selected-ledger mass stays bound, so the systems stage is
        # unaffected; only the broadside/per-gun shell weights become unknown.
        battery["mass_models"] = [m for m in battery["mass_models"]
                                 if m.get("method") != "counted_ammunition_mass"]
        g = self._guns(project)["weapons.main"]["guns"]
        self.assertEqual(g["status"], "unavailable")
        self.assertIsNone(g["broadside_mass_kg"])
        self.assertIsNone(g["per_gun_shell_kg"])
        self.assertIsNone(g["shell_mass_kg"]["value"])
        codes = {d["code"] for d in g["diagnostics"]}
        self.assertIn("page_rows.guns_shell_mass_unknown", codes)
        # the ledger mass is still reported honestly, not reverse-inferred
        self.assertIsNotNone(g["ledger_mass_t"])

    def test_missing_broadside_count_makes_broadside_unknown(self):
        project = copy.deepcopy(self.project)
        project["systems"]["weapons"]["main"].pop("broadside_guns", None)
        g = self._guns(project)["weapons.main"]["guns"]
        self.assertIsNone(g["broadside_mass_kg"])
        codes = {d["code"] for d in g["diagnostics"]}
        self.assertIn("page_rows.guns_broadside_count_unknown", codes)

    def test_qm_reports_unknown_without_reverse_inferred_projectile_mass(self):
        g = self._guns()["weapons.torpedo"]["guns"]
        # torpedo has no counted_ammunition_mass model -> projectile mass unknown
        self.assertIsNone(g["shell_mass_kg"]["value"])
        self.assertIsNone(g["broadside_mass_kg"])
        codes = {d["code"] for d in g["diagnostics"]}
        self.assertIn("page_rows.guns_shell_mass_unknown", codes)
        # the projectile mass is NOT reverse-inferred from the 62 t ledger mass
        self.assertNotIn("page_rows.guns_projectile_from_ledger", codes)
        self.assertIsNotNone(g["ledger_mass_t"])

    def test_guns_view_attached_for_every_weapons_leaf(self):
        views = self._guns()
        for leaf in ("main", "secondary", "torpedo", "misc_weight"):
            self.assertIn("guns", views[f"weapons.{leaf}"], "missing guns view for %s" % leaf)


if __name__ == "__main__":
    unittest.main()
