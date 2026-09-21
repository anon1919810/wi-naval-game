# -*- coding: utf-8 -*-
"""Guns 页：SPS Weights 表 + 解析对照 + Queen Mary 锚值 的验收测试。"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import guns as G  # noqa: E402


def analytic_case():
    """单列解析对照：4 门 × 10 t + 2 座 × 50 t；弹 100 lb；齐射 4 门；储弹 10 发、装药 20 lb。"""
    return {
        "schema": "plimsoll-guns-1",
        "batteries": [{
            "id": "b1", "column": "main",
            "guns": 4, "gun_weight_t": 10.0,
            "mounts": 2, "mount_weight_t": 50.0,
            "shell_lb": 100.0, "charge_lb": 20.0,
            "rounds_per_gun": 10, "broadside_guns": 4,
        }],
    }


def queen_mary_case():
    p = os.path.join(PKG, "cases", "queen_mary_1913_guns.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class TestCompute(unittest.TestCase):
    def test_totals_exact(self):
        """Guns=40, Mounts=100, Total=140；Magazine=4×10×(45.359+9.072)/1000 t。"""
        r = G.compute(analytic_case())
        v = r["values"]
        self.assertAlmostEqual(v["guns_t"], 40.0, places=9)
        self.assertAlmostEqual(v["mounts_t"], 100.0, places=9)
        self.assertAlmostEqual(v["total_t"], 140.0, places=9)
        mag = 4 * 10 * (100.0 + 20.0) * G.LB_TO_KG / 1000.0
        self.assertAlmostEqual(v["magazine_t"], mag, places=9)

    def test_broadside_conversion_exact(self):
        """齐射 = 单舷门数 × 弹重；lb→kg = ×0.45359237（国际磅定义，精确）。"""
        r = G.compute(analytic_case())
        self.assertAlmostEqual(r["values"]["broadside_lb"], 400.0, places=9)
        self.assertAlmostEqual(r["values"]["broadside_kg"], 400.0 * 0.45359237, places=9)

    def test_broadside_exceeds_guns_raises(self):
        c = analytic_case()
        c["batteries"][0]["broadside_guns"] = 5
        with self.assertRaises(ValueError):
            G.compute(c)

    def test_duplicate_column_raises(self):
        c = analytic_case()
        c["batteries"].append(dict(c["batteries"][0]))
        with self.assertRaises(ValueError):
            G.compute(c)

    def test_bad_column_raises(self):
        c = analytic_case()
        c["batteries"][0]["column"] = "first"
        with self.assertRaises(ValueError):
            G.compute(c)

    def test_missing_mount_weight_gives_none_not_zero(self):
        """缺炮座重量：Mounts/Total 部分给出 + 警告，**不冒充 0**。"""
        c = analytic_case()
        del c["batteries"][0]["mounts"], c["batteries"][0]["mount_weight_t"]
        r = G.compute(c)
        self.assertIsNone(r["batteries"]["main"]["mounts_t"])
        self.assertAlmostEqual(r["values"]["total_t"], 40.0, places=9)
        self.assertTrue(any("Mounts" in w for w in r["warnings"]))

    def test_missing_rounds_magazine_none_and_warns(self):
        c = analytic_case()
        del c["batteries"][0]["rounds_per_gun"]
        r = G.compute(c)
        self.assertIsNone(r["batteries"]["main"]["magazine_t"])
        self.assertTrue(any("Magazine" in w for w in r["warnings"]))

    def test_charge_missing_magazine_shells_only_and_warns(self):
        c = analytic_case()
        del c["batteries"][0]["charge_lb"]
        r = G.compute(c)
        mag = 4 * 10 * 100.0 * G.LB_TO_KG / 1000.0
        self.assertAlmostEqual(r["values"]["magazine_t"], mag, places=9)
        self.assertTrue(any("装药" in w for w in r["warnings"]))

    def test_trace_discipline(self):
        """铁律：每个 trace 项都带 formula/source/estimate。"""
        r = G.compute(queen_mary_case())
        for t in r["trace"]:
            self.assertIn("formula", t)
            self.assertIn("source", t)
            self.assertIn("estimate", t)


class TestSpsView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = G.sps_table(G.compute(queen_mary_case()))

    def test_row_order_matches_sps(self):
        self.assertEqual([r["row"] for r in self.table],
                         ["Guns", "Mounts", "Armour", "Total",
                          "Broadside lbs", "Broadside kg", "Magazine"])

    def test_columns_main_and_2nd(self):
        self.assertEqual(self.table[0]["main"], 608.816)  # 8 × 76.102


class TestQueenMary(unittest.TestCase):
    """锚在外部文献值上：改数值必须显式改这里（并回写出处）。"""

    @classmethod
    def setUpClass(cls):
        cls.case = queen_mary_case()
        cls.r = G.compute(cls.case)
        cls.main = cls.r["batteries"]["main"]
        cls.sec = cls.r["batteries"]["2nd"]

    def test_main_guns_anchored(self):
        self.assertEqual(self.main["guns"], 8)
        self.assertAlmostEqual(self.main["guns_t"], 8 * 76.102, places=9)

    def test_main_mounts_anchored_estimate(self):
        self.assertAlmostEqual(self.main["mounts_t"], 4 * 600.0, places=9)
        self.assertTrue(self.main["estimate"])  # BII* 未单列，沿用 Mark II —— estimate

    def test_main_broadside_anchored(self):
        """四塔全中线，单舷 8 门：11,200 lb = 5,080.23 kg。"""
        self.assertAlmostEqual(self.main["broadside_lb"], 11200.0, places=9)
        self.assertAlmostEqual(self.main["broadside_kg"], 5080.2345, places=4)

    def test_main_magazine_design_outfit(self):
        """设计口径 80 发/门：640 × (1400+297) lb → 492.638 t。"""
        self.assertAlmostEqual(self.main["magazine_t"], 492.638, places=2)

    def test_secondary_anchored(self):
        self.assertEqual(self.sec["guns"], 16)
        self.assertAlmostEqual(self.sec["guns_t"], 16 * 2.134, places=9)
        self.assertAlmostEqual(self.sec["broadside_lb"], 16 * 31.0, places=9)
        self.assertAlmostEqual(self.sec["magazine_t"], 16 * 150 * 31.0 * G.LB_TO_KG / 1000.0,
                               places=2)

    def test_armour_row_is_known_gap(self):
        """炮塔装甲重是已知缺口：Armour 行置 None + 警告，不冒充 0。"""
        self.assertIsNone(self.r["values"]["armour_t"])
        self.assertTrue(any("Armour" in w for w in self.r["warnings"]))

    def test_armament_weight_plausible(self):
        """武备合计（Guns+Mounts）占正常排水量 10–13%（狮级口径）。"""
        frac = 100.0 * self.r["values"]["total_t"] / 26770.0
        self.assertTrue(10.0 < frac < 13.0, "武备占比 %.1f%% 超出合理带" % frac)


if __name__ == "__main__":
    unittest.main()
