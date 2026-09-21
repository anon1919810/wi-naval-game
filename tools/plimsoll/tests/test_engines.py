# -*- coding: utf-8 -*-
"""Engines 页：功率换算 / 燃料构成 / 续航 / 量级校核 的解析对照与 QM 锚值。"""
import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import engines as E  # noqa: E402


def analytic_case():
    return {
        "schema": "plimsoll-engines-1",
        "displacement_normal_t": 10000.0,
        "lwl_m": 120.0,
        "shafts": 2,
        "power_design_shp": 10000.0,
        "max_speed_kn": 20.0,
        "coal_t": 800.0,
        "oil_t": 200.0,
        "range_nm": 4000.0,
        "range_at_speed_kn": 12.0,
        "engine_weight_t": 500.0,
    }


def queen_mary_case():
    p = os.path.join(PKG, "cases", "queen_mary_1913_engines.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class TestCompute(unittest.TestCase):
    def test_power_conversion_exact(self):
        """kW = shp × 0.7457（1 hp = 745.7 W，精确）。"""
        r = E.compute(analytic_case())
        self.assertAlmostEqual(r["values"]["power_design_kw"], 7457.0, places=9)

    def test_fuel_split_exact(self):
        r = E.compute(analytic_case())
        self.assertAlmostEqual(r["values"]["bunker_total_t"], 1000.0, places=9)
        self.assertAlmostEqual(r["values"]["pct_coal"], 80.0, places=9)

    def test_admiralty_coeff_exact(self):
        """C = Δ^(2/3)·V³ / P = 10000^(2/3) × 8000 / 10000。"""
        r = E.compute(analytic_case())
        expect = (10000.0 ** (2.0 / 3.0)) * 20.0 ** 3 / 10000.0
        self.assertAlmostEqual(r["values"]["admiralty_coeff"], expect, places=9)

    def test_froude_at_max(self):
        r = E.compute(analytic_case())
        fn = next(t["value"] for t in r["trace"] if t["key"] == "froude_at_max")
        self.assertAlmostEqual(fn, (20.0 * E.KNOT_MPS) / math.sqrt(E.G * 120.0), places=9)

    def test_missing_speed_and_fuel_warn(self):
        """巡航速度本就没给 → 必须警告而不是静默当 0。"""
        r = E.compute(analytic_case())      # analytic_case 未给 cruise_speed_kn
        self.assertIsNone(r["values"]["cruise_speed_kn"])
        self.assertTrue(any("cruise_speed_kn" in w for w in r["warnings"]))
        c2 = analytic_case()
        del c2["coal_t"], c2["oil_t"]
        self.assertTrue(any("Bunker" in w for w in E.compute(c2)["warnings"]))

    def test_bad_shafts_raise(self):
        for bad in (0, -2, 2.5, "4"):
            c = analytic_case()
            c["shafts"] = bad
            with self.assertRaises(ValueError):
                E.compute(c)

    def test_resistance_and_weight_are_known_gaps(self):
        """阻力必须点名"未实现"（PLAN 7.3），主机重量缺则置空。"""
        r = E.compute(analytic_case())
        self.assertTrue(any("Holtrop" in w for w in r["warnings"]))
        c = analytic_case()
        del c["engine_weight_t"]
        self.assertTrue(any("Engine weight" in w for w in E.compute(c)["warnings"]))

    def test_trace_discipline(self):
        for t in E.compute(queen_mary_case())["trace"]:
            self.assertIn("formula", t)
            self.assertIn("source", t)
            self.assertIn("estimate", t)


class TestSpsView(unittest.TestCase):
    def test_missing_resistance_stays_none(self):
        v = E.sps_view(E.compute(queen_mary_case()))
        self.assertIsNone(v["friction_resistance_kN"])
        self.assertIsNone(v["wave_resistance_kN"])
        self.assertIsNone(v["engine_weight_t"])
        self.assertIn("displacement_factor", v["_not_implemented"])


class TestQueenMary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = E.compute(queen_mary_case())

    def test_power_anchored(self):
        """75,000 shp = 55,927.5 kW；试航 83,000 shp = 61,893.1 kW。"""
        self.assertEqual(self.r["values"]["power_design_shp"], 75000)
        self.assertAlmostEqual(self.r["values"]["power_design_kw"], 75000 * 0.7457, places=6)
        self.assertAlmostEqual(self.r["values"]["power_trial_kw"], 83000 * 0.7457, places=6)

    def test_fuel_anchored(self):
        """煤 3,600 + 油 1,170 = 4,770 t；%Coal = 75.47%。"""
        self.assertAlmostEqual(self.r["values"]["bunker_total_t"], 4770.0, places=9)
        self.assertAlmostEqual(self.r["values"]["pct_coal"], 100.0 * 3600.0 / 4770.0, places=6)

    def test_range_and_shafts(self):
        self.assertEqual(self.r["values"]["shafts"], 4)
        self.assertEqual(self.r["values"]["range_nm"], 5610.0)
        self.assertEqual(self.r["values"]["range_at_speed_kn"], 10.0)

    def test_admiralty_coeff_in_plausible_band(self):
        """海军部系数 248 落在军舰常见 200–300 量级 —— 功率/航速/排水量自洽。"""
        self.assertTrue(150.0 < self.r["values"]["admiralty_coeff"] < 400.0,
                        "C=%.0f 超出量级" % self.r["values"]["admiralty_coeff"])

    def test_cruise_speed_and_engine_weight_are_gaps(self):
        self.assertIsNone(self.r["values"]["cruise_speed_kn"])
        self.assertIsNone(self.r["values"]["engine_weight_t"])


class TestResistanceIntegration(unittest.TestCase):
    """Engines 页与 resistance.py 的接口（可选传入，不破坏原来的诚实留白）。"""

    def test_without_resistance_stays_none(self):
        v = E.sps_view(E.compute(queen_mary_case()))
        self.assertIsNone(v["friction_resistance_kN"])
        self.assertIsNone(v["wave_resistance_kN"])
        self.assertIn("friction_resistance", v["_not_implemented"])
        self.assertIsNone(v["_resistance_source"])

    def test_with_resistance_filled_and_attributed(self):
        v = E.sps_view(E.compute(queen_mary_case()),
                       resistance={"speed_kn": 28.1, "friction_kN": 1209.0,
                                   "residual_kN": 959.0})
        self.assertAlmostEqual(v["friction_resistance_kN"], 1209.0, places=9)
        self.assertAlmostEqual(v["wave_resistance_kN"], 959.0, places=9)
        self.assertAlmostEqual(v["resistance_at_speed_kn"], 28.1, places=9)
        self.assertEqual(v["_not_implemented"], ["displacement_factor"])
        self.assertIn("resistance.py", v["_resistance_source"])


if __name__ == "__main__":
    unittest.main()
