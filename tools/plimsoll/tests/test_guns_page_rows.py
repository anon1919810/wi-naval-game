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

    def test_declared_projectile_fact_reports_broadside_without_ledger_mass(self):
        """A no-model battery may declare a sourced shell mass for reporting only."""
        project = copy.deepcopy(self.project)
        battery = project["systems"]["weapons"]["secondary"]
        battery["mass_models"] = [m for m in battery["mass_models"]
                                  if m.get("method") != "counted_ammunition_mass"]
        baseline = self._guns()["weapons.secondary"]["guns"]
        battery["facts"] = {"projectile_mass_kg": dict(
            value=45.0, source="NavWeaps 6-inch shell converted with 0.45359237 kg/lb", estimate=True)}
        g = self._guns(project)["weapons.secondary"]["guns"]
        self.assertAlmostEqual(g["shell_mass_kg"]["value"], 45.0)
        self.assertEqual(g["shell_mass_kg"]["origin"], "declared_projectile_mass_kg_fact")
        self.assertAlmostEqual(g["broadside_mass_kg"], g["broadside_guns"] * 45.0)
        self.assertNotIn("page_rows.guns_shell_mass_unknown",
                         {d["code"] for d in g["diagnostics"]})
        # Reporting only: the ledger battery mass is untouched by the declaration,
        # so removing the model leaves the outfit exactly as the ledger reports it
        # and no ammunition mass was derived from the declared shell value.
        self.assertEqual(g["ship_wide_ammunition_t"], baseline["ship_wide_ammunition_t"])
        self.assertEqual(g["ledger_mass_t"], baseline["ledger_mass_t"])
        self.assertLess(g["broadside_mass_kg"] / 1000.0, g["ship_wide_ammunition_t"])
        # The declared value is echoed separately from the resolved shell mass.
        self.assertAlmostEqual(g["declared_projectile_mass_kg"]["value"], 45.0)
        self.assertEqual(g["declared_projectile_mass_kg"]["source"],
                         "NavWeaps 6-inch shell converted with 0.45359237 kg/lb")

    def test_incomplete_projectile_fact_stays_unknown(self):
        for patch in ({"value": 45.0}, {"value": 45.0, "source": "s"},
                      {"value": None, "source": "s", "estimate": True},
                      {"value": 45.0, "source": "s", "estimate": None}):
            with self.subTest(patch=patch):
                project = copy.deepcopy(self.project)
                battery = project["systems"]["weapons"]["secondary"]
                battery["mass_models"] = [m for m in battery["mass_models"]
                                         if m.get("method") != "counted_ammunition_mass"]
                battery["facts"] = {"projectile_mass_kg": dict(patch)}
                g = self._guns(project)["weapons.secondary"]["guns"]
                self.assertIsNone(g["shell_mass_kg"]["value"])
                self.assertIn("page_rows.guns_shell_mass_unknown",
                              {d["code"] for d in g["diagnostics"]})

    def test_ammunition_model_remains_the_shell_mass_authority(self):
        """A declared fact must not override or duplicate the model that drives mass."""
        project = copy.deepcopy(self.project)
        battery = project["systems"]["weapons"]["main"]
        model_mass = next(m for m in battery["mass_models"]
                          if m.get("method") == "counted_ammunition_mass")["inputs"]["projectile_mass_kg"]
        battery["facts"] = {"projectile_mass_kg": dict(value=999.0, source="contradicting", estimate=False)}
        g = self._guns(project)["weapons.main"]["guns"]
        self.assertEqual(g["shell_mass_kg"]["origin"], "counted_ammunition_mass_model")
        self.assertAlmostEqual(g["shell_mass_kg"]["value"], model_mass)
        # The declared fact is still reported, clearly separate from the authority.
        self.assertAlmostEqual(g["declared_projectile_mass_kg"]["value"], 999.0)

    def test_structured_source_counts_as_declared_provenance(self):
        """The contract accepts a structured source object; it must not read unknown."""
        for source in ({"publication": "NavWeaps", "conversion": "kg/lb"},
                       {"publication": "NavWeaps"}):
            with self.subTest(source=source):
                project = copy.deepcopy(self.project)
                battery = project["systems"]["weapons"]["secondary"]
                battery["mass_models"] = [m for m in battery["mass_models"]
                                         if m.get("method") != "counted_ammunition_mass"]
                battery["facts"] = {"projectile_mass_kg": dict(value=45.0, source=source, estimate=False)}
                g = self._guns(project)["weapons.secondary"]["guns"]
                self.assertAlmostEqual(g["shell_mass_kg"]["value"], 45.0)
                self.assertEqual(g["shell_mass_kg"]["source"], source)
                self.assertNotIn("page_rows.guns_shell_mass_unknown",
                                 {d["code"] for d in g["diagnostics"]})

    def test_nested_structured_source_counts_as_declared_provenance(self):
        """The validator treats a nonempty source object as opaque provenance."""
        source = {"citation": {"title": "Naval Annual", "page": 12}}
        project = copy.deepcopy(self.project)
        battery = project["systems"]["weapons"]["secondary"]
        battery["mass_models"] = [m for m in battery["mass_models"]
                                 if m.get("method") != "counted_ammunition_mass"]
        battery["facts"] = {"projectile_mass_kg": dict(value=45.0, source=source, estimate=True)}
        g = self._guns(project)["weapons.secondary"]["guns"]
        self.assertAlmostEqual(g["shell_mass_kg"]["value"], 45.0)
        self.assertEqual(g["shell_mass_kg"]["source"], source)
        self.assertNotIn("page_rows.guns_shell_mass_unknown",
                         {d["code"] for d in g["diagnostics"]})

    def test_empty_structured_source_is_unknown_provenance(self):
        for source in ({}, "", "   ", None):
            with self.subTest(source=source):
                project = copy.deepcopy(self.project)
                battery = project["systems"]["weapons"]["secondary"]
                battery["mass_models"] = [m for m in battery["mass_models"]
                                         if m.get("method") != "counted_ammunition_mass"]
                battery["facts"] = {"projectile_mass_kg": dict(value=45.0, source=source, estimate=False)}
                g = self._guns(project)["weapons.secondary"]["guns"]
                self.assertIsNone(g["shell_mass_kg"]["value"])
                self.assertIn("page_rows.guns_shell_mass_unknown",
                              {d["code"] for d in g["diagnostics"]})

    def test_ambiguous_ammunition_models_block_the_fact_fallback(self):
        """More than one ammunition model is ambiguous: stay unknown, do not guess."""
        project = copy.deepcopy(self.project)
        battery = project["systems"]["weapons"]["secondary"]
        model = next(m for m in battery["mass_models"]
                     if m.get("method") == "counted_ammunition_mass")
        duplicate = dict(model, id=model["id"] + "-duplicate")
        battery["mass_models"] = [m for m in battery["mass_models"]
                                 if m.get("method") != "counted_ammunition_mass"] + [model, duplicate]
        battery["facts"] = {"projectile_mass_kg": dict(value=45.0, source="declared", estimate=True)}
        g = self._guns(project)["weapons.secondary"]["guns"]
        self.assertIsNone(g["shell_mass_kg"]["value"])
        self.assertIn("page_rows.guns_shell_mass_unknown",
                      {d["code"] for d in g["diagnostics"]})

    def test_guns_view_without_page_rows_for_a_new_battery(self):
        """A battery built from a reporting fact alone still exposes a guns view."""
        project = copy.deepcopy(self.project)
        # A battery under construction owns exactly one ledger item of its own.
        project["weight_groups"].append(dict(id="tertiary", label="Tertiary", items=[
            dict(id="tertiary-guns", mass_t=90.0, x_m=0.0, y_m=0.0, kg_m=1.0,
                 source="fixture", estimate=False)]))
        project["systems"]["weapons"]["battery_3"] = {
            "installed_guns": 4, "broadside_guns": 2, "rounds_per_gun": 60,
            "weight_item_ids": ["tertiary-guns"],
            "facts": {"projectile_mass_kg": dict(value=30.0, source="declared 6-inch shell", estimate=False)},
        }
        views = self._guns(project)
        self.assertIn("guns", views["weapons.battery_3"])
        g = views["weapons.battery_3"]["guns"]
        self.assertEqual(g["installed_guns"], 4)
        self.assertAlmostEqual(g["broadside_mass_kg"], 60.0)
        self.assertAlmostEqual(g["ledger_mass_t"], 90.0)
        # No ammunition ledger row was invented, so the outfit stays unknown.
        self.assertIsNone(g["ship_wide_ammunition_t"])
        # No page rows are invented for a battery that declares none.
        self.assertNotIn("rows", views["weapons.battery_3"])


if __name__ == "__main__":
    unittest.main()
