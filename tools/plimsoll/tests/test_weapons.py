# -*- coding: utf-8 -*-
"""Weapons 页：鱼雷清单 / 水雷深弹 / Misc weight 五分区 的解析对照与 QM 锚值。"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import weapons as WP  # noqa: E402


def analytic_case():
    """4 管 / 8 枚 / 战斗部 200 kg / 单雷全重 1.5 t；水雷 0（显式）、杂项两区。"""
    return {
        "schema": "plimsoll-weapons-1",
        "displacement_normal_t": 10000.0,
        "torpedo_batteries": [{
            "id": "tt", "tubes": 4, "carried": 8, "diameter_mm": 533.0,
            "length_m": 7.0, "warhead_kg": 200.0, "unit_weight_t": 1.5,
            "arrangement": "beam", "source": "解析",
        }],
        "mines": {"count": 0, "source": "解析：不装备"},
        "depth_charges": {"count": 0, "source": "解析：不装备"},
        "misc_weight": {
            "hull_below_water": {"mass_t": 100.0, "source": "解析"},
            "on_deck": {"mass_t": 50.0, "source": "解析"},
        },
    }


def queen_mary_case():
    p = os.path.join(PKG, "cases", "queen_mary_1913_weapons.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class TestTorpedoes(unittest.TestCase):
    def test_analytic(self):
        r = WP.torpedoes(analytic_case())
        self.assertEqual(r["values"]["tubes_total"], 4)
        self.assertEqual(r["values"]["carried_total"], 8)
        self.assertAlmostEqual(r["values"]["explosive_total_t"], 8 * 200.0 / 1000.0, places=9)
        self.assertAlmostEqual(r["batteries"][0]["weight_total_t"], 12.0, places=9)

    def test_missing_unit_weight_is_none_not_explosive(self):
        """单雷全重缺 → 总重置 None，**不能用装药重冒充**（差一个数量级）。"""
        c = analytic_case()
        del c["torpedo_batteries"][0]["unit_weight_t"]
        r = WP.torpedoes(c)
        self.assertIsNone(r["batteries"][0]["weight_total_t"])
        self.assertAlmostEqual(r["values"]["explosive_total_t"], 1.6, places=9)
        self.assertTrue(any("单雷全重" in w for w in r["warnings"]))

    def test_missing_length_warns(self):
        c = analytic_case()
        del c["torpedo_batteries"][0]["length_m"]
        self.assertTrue(any("雷长" in w for w in WP.torpedoes(c)["warnings"]))

    def test_bad_counts_raise(self):
        for bad in (-1, 1.5, "2"):
            c = analytic_case()
            c["torpedo_batteries"][0]["tubes"] = bad
            with self.assertRaises(ValueError):
                WP.torpedoes(c)

    def test_empty_batteries_raises(self):
        c = analytic_case()
        c["torpedo_batteries"] = []
        with self.assertRaises(ValueError):
            WP.torpedoes(c)


class TestOrdnance(unittest.TestCase):
    def test_explicit_zero_is_zero(self):
        r = WP.ordnance(analytic_case())
        self.assertEqual(r["values"]["mines"]["count"], 0)
        self.assertTrue(any("不装备" in w for w in r["warnings"]))

    def test_missing_is_none_not_zero(self):
        """没给 = 没数据（None），不是 0 —— 0 是史实断言，必须显式。"""
        c = analytic_case()
        del c["depth_charges"]
        r = WP.ordnance(c)
        self.assertIsNone(r["values"]["depth_charges"])
        self.assertTrue(any("不是 0" in w for w in r["warnings"]))


class TestMiscWeight(unittest.TestCase):
    def test_zone_total_and_pct(self):
        r = WP.misc_weight(analytic_case())
        self.assertAlmostEqual(r["values"]["misc_total_t"], 150.0, places=9)
        self.assertAlmostEqual(r["values"]["misc_pct_displacement"], 1.5, places=9)

    def test_missing_zone_excluded_not_zero(self):
        r = WP.misc_weight(analytic_case())
        z = {x["zone"]: x["mass_t"] for x in r["zones"]}
        self.assertIsNone(z["above_deck"])
        self.assertAlmostEqual(r["values"]["misc_total_t"], 150.0, places=9)

    def test_high_share_warns(self):
        c = analytic_case()
        c["misc_weight"]["hull_below_water"]["mass_t"] = 5000.0
        self.assertTrue(any("偏高" in w for w in WP.misc_weight(c)["warnings"]))

    def test_l2_bridge_warning_present(self):
        """分区重量没有 kg_m —— 必须警告不能直接喂给 L2 合成 KG。"""
        self.assertTrue(any("kg_m" in w for w in WP.misc_weight(analytic_case())["warnings"]))


class TestQueenMary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = queen_mary_case()
        cls.r = WP.torpedoes(cls.case)

    def test_tubes_and_carried_anchored(self):
        self.assertEqual(self.r["values"]["tubes_total"], 2)
        self.assertEqual(self.r["values"]["carried_total"], 14)

    def test_explosive_total_anchored(self):
        """14 枚 × 181 kg = 2.534 t（战斗部装药，不是鱼雷全重）。"""
        self.assertAlmostEqual(self.r["values"]["explosive_total_t"], 14 * 181.0 / 1000.0, places=9)

    def test_unit_weight_is_known_gap(self):
        self.assertIsNone(self.r["batteries"][0]["weight_total_t"])
        self.assertTrue(any("单雷全重" in w for w in self.r["warnings"]))

    def test_ordnance_and_misc_are_gaps(self):
        """水雷/深弹/Misc weight 无数据 → 全 None，不是 0。"""
        o = WP.ordnance(self.case)
        self.assertIsNone(o["values"]["mines"])
        self.assertIsNone(o["values"]["depth_charges"])
        m = WP.misc_weight(self.case)
        self.assertAlmostEqual(m["values"]["misc_total_t"], 0.0, places=9)
        self.assertTrue(all(z["mass_t"] is None for z in m["zones"]))


class TestSpsView(unittest.TestCase):
    def test_aggregates(self):
        v = WP.sps_view(queen_mary_case())
        self.assertEqual(v["tubes_total"], 2)
        self.assertEqual(v["carried_total"], 14)
        self.assertIsNone(v["mines"])
        self.assertEqual(len(v["misc_weight"]), 5)

    def test_trace_discipline(self):
        for t in WP.misc_weight(analytic_case())["trace"] \
                + WP.torpedoes(analytic_case())["trace"]:
            self.assertIn("formula", t)
            self.assertIn("source", t)
            self.assertIn("estimate", t)


if __name__ == "__main__":
    unittest.main()
