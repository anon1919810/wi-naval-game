"""Weapons page projection: torpedo / mines / depth charges / misc zones.

These tests guard the discipline in the long-task SPS-pages contract for the
Weapons page (W2):

  * 鱼雷主行质量等于账本 weapons.torpedo（账本是唯一质量权威）；
  * 五个杂项位置分区（hull_below / hull_above / on_deck / above_deck / void）
    无数据 → 未知（weight_t 为 None、mass_status 为 no_ledger_binding），
    绝不按排水量或其他总量倒填；
  * 仅计数的行（torpedo_secondary / mines / depth_charges）不计入质量合计；
  * 杂项分区一旦声明质量（typed.mass_t），即如实出值，但仍是声明输入、
    不因此生成账本质量（weight_t 仍未知）。

Unknown is never zero; nothing is reverse-inferred from displacement.
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


class WeaponsPageRowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = project_store.load(QM)
        cls.state = loading.resolve_loading(cls.project, "normal-engineering")

    def _systems(self, project=None):
        result = analysis.compute_project(
            self.project if project is None else project,
            "normal-engineering", {"stages": ["loading", "systems"]})
        self.assertEqual(result["stages"]["systems"]["status"], "completed")
        return result["stages"]["systems"]["data"]

    @staticmethod
    def _rows_by_name(view):
        return {row["row"]: row for row in (view.get("rows") or [])}

    def test_torpedo_main_row_mass_equals_ledger(self):
        data = self._systems()
        view = data["page_rows"]["weapons.torpedo"]
        rows = self._rows_by_name(view)
        main = rows["torpedo_main"]
        leaf = data["systems"]["weapons.torpedo"]
        self.assertIsNotNone(main["weight_t"], "torpedo_main must bind the torpedo ledger items")
        self.assertAlmostEqual(main["weight_t"], float(leaf["ledger_mass_t"]))
        self.assertEqual(main["mass_status"], "ledger_bound")
        # The declared rows total must match the ledger leaf mass (no leakage).
        self.assertTrue(view["values"]["matches_ledger_mass"])

    def test_misc_zones_unknown_without_reverse_inference(self):
        data = self._systems()
        view = data["page_rows"]["weapons.misc_weight"]
        rows = self._rows_by_name(view)
        zone_ids = ("hull_below", "hull_above", "on_deck", "above_deck", "void")
        for zid in zone_ids:
            self.assertIn(zid, rows, "missing misc zone row %r" % zid)
            row = rows[zid]
            # No ledger binding -> weight stays unknown, never zero, never derived.
            self.assertIsNone(row["weight_t"])
            self.assertEqual(row["mass_status"], "no_ledger_binding")
            self.assertIsNone((row.get("typed") or {}).get("mass_t"))
        summary = view["weapons"]
        self.assertEqual(summary["misc_zone_mass_declared_count"], 0)
        self.assertEqual(summary["misc_zone_mass_unknown_count"], 5)
        codes = {d["code"] for d in (view.get("diagnostics") or [])}
        self.assertIn("page_rows.weapons_misc_zone_unknown", codes)
        # Explicitly: no diagnostic may claim a displacement-derived mass.
        self.assertNotIn("page_rows.misc_zone_from_displacement", codes)
        # And no numeric mass was fabricated anywhere for these zones.
        for zid in zone_ids:
            self.assertIsNone(rows[zid]["weight_t"])

    def test_count_only_rows_excluded_from_total(self):
        data = self._systems()
        view = data["page_rows"]["weapons.torpedo"]
        rows = self._rows_by_name(view)
        for rid in ("torpedo_secondary", "mines", "depth_charges"):
            self.assertIn(rid, rows)
            row = rows[rid]
            self.assertEqual(row["item_ids"], [])
            self.assertIsNone(row["weight_t"], "%s is count-only and carries no mass" % rid)
        # The only mass that enters the total is the ledger-bound torpedo_main.
        main = rows["torpedo_main"]
        self.assertIsNotNone(main["weight_t"])
        self.assertAlmostEqual(view["values"]["declared_rows_total_t"], main["weight_t"])

    def test_misc_zone_declared_mass_reported_and_not_reverse_filled(self):
        project = copy.deepcopy(self.project)
        leaf = project["systems"]["weapons"]["misc_weight"]
        leaf["page_rows"][0]["typed"]["mass_t"] = 12.5  # declare hull_below mass
        data = self._systems(project)
        view = data["page_rows"]["weapons.misc_weight"]
        rows = self._rows_by_name(view)
        self.assertAlmostEqual((rows["hull_below"].get("typed") or {}).get("mass_t"), 12.5)
        # A declared misc mass is a declared input; it does NOT invent a ledger mass.
        self.assertIsNone(rows["hull_below"]["weight_t"])
        self.assertEqual(rows["hull_below"]["mass_status"], "no_ledger_binding")
        summary = view["weapons"]
        self.assertEqual(summary["misc_zone_mass_declared_count"], 1)
        self.assertEqual(summary["misc_zone_mass_unknown_count"], 4)
        # The four still-unknown zones still trigger the honest diagnostic.
        codes = {d["code"] for d in (view.get("diagnostics") or [])}
        self.assertIn("page_rows.weapons_misc_zone_unknown", codes)


if __name__ == "__main__":
    unittest.main()
