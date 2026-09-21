# -*- coding: utf-8 -*-
"""Armour 页：SPS 表视图 + 解析对照 + Queen Mary 锚值 + 与 L2 装甲组一致性的验收测试。"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PKG))
sys.path.insert(0, PKG)

import armour as A    # noqa: E402
import weights as W   # noqa: E402


def analytic_case():
    """单行解析对照：100 m × 5 m × 229 mm × 7850 kg/m³ = 898.825 t。"""
    return {
        "schema": "plimsoll-armour-1",
        "rho_kg_m3": 7850.0,
        "rows": [
            {"id": "belt_x", "group": "main", "thickness_mm": 229,
             "length_m": 100.0, "height_m": 5.0, "source": "解析"},
        ],
    }


def queen_mary_case():
    p = os.path.join(PKG, "cases", "queen_mary_1913_armour.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def queen_mary_weights():
    p = os.path.join(PKG, "cases", "queen_mary_1913_weights.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class TestCompute(unittest.TestCase):
    def test_weight_from_length_height_exact(self):
        """SPS 口径：W = L×H×t×ρ，解析对照 100·5·0.229·7850/1000 = 898.825 t。"""
        r = A.compute(analytic_case())
        self.assertAlmostEqual(r["values"]["total_armour_t"], 898.825, places=9)
        self.assertAlmostEqual(r["rows"][0]["weight_t"], 898.825, places=9)

    def test_area_path_matches_lh_path(self):
        """给 area_m2 与给 L×H（面积相等）必须同重——两条口径的一致性。"""
        c1 = analytic_case()
        c1["rows"][0]["area_m2"] = 500.0
        del c1["rows"][0]["length_m"], c1["rows"][0]["height_m"]
        a = A.compute(analytic_case())["values"]["total_armour_t"]
        b = A.compute(c1)["values"]["total_armour_t"]
        self.assertAlmostEqual(a, b, places=9)

    def test_duplicate_row_id_raises(self):
        c = analytic_case()
        c["rows"].append(dict(c["rows"][0]))
        with self.assertRaises(ValueError):
            A.compute(c)

    def test_bad_group_raises(self):
        c = analytic_case()
        c["rows"][0]["group"] = "main_belt"
        with self.assertRaises(ValueError):
            A.compute(c)

    def test_bad_thickness_raises(self):
        for v in (0, -229, None, "229"):
            c = analytic_case()
            c["rows"][0]["thickness_mm"] = v
            with self.assertRaises(ValueError):
                A.compute(c)

    def test_missing_geometry_raises(self):
        c = analytic_case()
        del c["rows"][0]["length_m"], c["rows"][0]["height_m"]
        with self.assertRaises(ValueError):
            A.compute(c)

    def test_bad_rho_raises(self):
        c = analytic_case()
        c["rho_kg_m3"] = 0
        with self.assertRaises(ValueError):
            A.compute(c)

    def test_group_totals_sum_to_total(self):
        r = A.compute(queen_mary_case())
        self.assertAlmostEqual(sum(r["groups"].values()),
                               r["values"]["total_armour_t"], places=9)

    def test_trace_discipline(self):
        """铁律：每个 trace 项都带 formula/source/estimate。"""
        r = A.compute(queen_mary_case())
        for t in r["trace"]:
            self.assertIn("formula", t)
            self.assertIn("source", t)
            self.assertIn("estimate", t)


class TestSpsView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sps = A.sps_table(A.compute(queen_mary_case()))

    def test_five_belt_rows_in_sps_order(self):
        self.assertEqual([b["row"] for b in self.sps["belts"]],
                         ["main", "ends", "upper", "bulge", "torpedo_bulkhead"])

    def test_bulge_is_none_not_zero(self):
        """QM 无防雷凸舱：Bulge 行必须是 None + 警告，不冒充 0。"""
        bulge = [b for b in self.sps["belts"] if b["row"] == "bulge"][0]
        self.assertIsNone(bulge["weight_t"])
        r = A.compute(queen_mary_case())
        self.assertTrue(any("bulge" in w for w in r["warnings"]))

    def test_deck_has_two_layers(self):
        ids = [d["id"] for d in self.sps["armour_deck"]]
        self.assertEqual(ids, ["deck_armour", "deck_lower"])

    def test_total_equals_sum_of_view_groups(self):
        parts = (sum(b["weight_t"] for b in self.sps["belts"] if b["weight_t"])
                 + sum(d["weight_t"] for d in self.sps["armour_deck"])
                 + sum(x["weight_t"] for x in self.sps["barbettes_turrets"])
                 + sum(x["weight_t"] for x in self.sps["conning_tower"])
                 + sum(x["weight_t"] for x in self.sps["other"]))
        self.assertAlmostEqual(parts, self.sps["total_armour_t"], places=6)


class TestQueenMary(unittest.TestCase):
    """锚在源数据上：改动生成器/选面规则必须显式改这里。"""

    @classmethod
    def setUpClass(cls):
        cls.case = queen_mary_case()
        cls.r = A.compute(cls.case)

    def test_total_anchored(self):
        """装甲合计 ≈ 6820.7 t（与 L2 装甲组同源）。"""
        self.assertAlmostEqual(self.r["values"]["total_armour_t"], 6820.7, delta=1.0)

    def test_consistent_with_weights_armour_group(self):
        """与 weights.py 装甲组一致性：两处独立计算必须吻合（允许入档舍入差）。"""
        w = W.synthesize(queen_mary_weights())
        wm = [g for g in w["groups"] if g["id"] == "armour"][0]["mass_t"]
        self.assertAlmostEqual(self.r["values"]["total_armour_t"], wm, delta=0.5)

    def test_fraction_in_historical_band(self):
        """史实带：狮级装甲占正常排水量 22–28%。"""
        frac = 100.0 * self.r["values"]["total_armour_t"] / 26770.0
        self.assertTrue(22.0 < frac < 28.0, "装甲占比 %.1f%% 超出史实带" % frac)

    def test_thicknesses_match_armour_zones(self):
        """逐区厚度必须与 armour_zones.json 一致（wiki 来源不被静默改动）。"""
        with open(os.path.join(REPO, "queen_mary_v3", "armour_zones.json"),
                  encoding="utf-8") as f:
            zj = json.load(f)
        zmm = dict(zip(zj["zone_ids"], zj["zone_mm"]))
        for row in self.r["rows"]:
            self.assertEqual(row["thickness_mm"], float(zmm[row["id"]]))

    def test_main_belt_is_229_and_heaviest_belt(self):
        belts = {b["row"]: b for b in A.sps_table(self.r)["belts"]}
        self.assertEqual(belts["main"]["thickness_mm"], 229.0)
        self.assertEqual(belts["ends"]["thickness_mm"], 102.0)
        self.assertEqual(belts["upper"]["thickness_mm"], 152.0)
        self.assertEqual(belts["torpedo_bulkhead"]["thickness_mm"], 102.0)
        self.assertTrue(belts["main"]["weight_t"] > belts["upper"]["weight_t"])
        self.assertTrue(belts["main"]["weight_t"] > belts["ends"]["weight_t"])

    def test_all_rows_estimate(self):
        """几何推得的面积一律 estimate；trace 同步。"""
        self.assertEqual(self.r["values"]["n_estimate_rows"], self.r["values"]["rows"])
        for row in self.r["rows"]:
            self.assertTrue(row["estimate"])

    def test_turret_armour_known_gap(self):
        """诚实缺口：turret_face 无选面对象，炮塔装甲未计入——案例里必须写明。"""
        self.assertNotIn("turret", self.r["groups"])
        self.assertIn("炮塔装甲未计入", self.case["_note"])


if __name__ == "__main__":
    unittest.main()
