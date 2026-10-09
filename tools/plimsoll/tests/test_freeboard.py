# -*- coding: utf-8 -*-
"""Freeboard 页：加权平均干舷 / 甲板浸没角 的解析对照与 QM 模型推得值校验。"""
import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import freeboard as FB  # noqa: E402


def analytic_case():
    """两段：40% 段 fb 6→5（均值 5.5）、60% 段 fb 5→4（均值 4.5）；L=100，B=20。
    加权平均 = (40×5.5 + 60×4.5)/100 = 4.9 m。"""
    return {
        "schema": "plimsoll-freeboard-1",
        "lwl_m": 100.0, "beam_m": 20.0,
        "segments": [
            {"id": "fore", "kind": "forecastle", "length_pct_lwl": 40.0,
             "fb_fore_m": 6.0, "fb_aft_m": 5.0, "source": "解析"},
            {"id": "aft", "kind": "quarterdeck", "length_pct_lwl": 60.0,
             "fb_fore_m": 5.0, "fb_aft_m": 4.0, "source": "解析"},
        ],
    }


def queen_mary_case():
    p = os.path.join(PKG, "cases", "queen_mary_1913_freeboard.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class TestFromDepth(unittest.TestCase):
    def test_definition(self):
        self.assertAlmostEqual(FB.from_depth(15.0, 8.5)["values"]["freeboard_m"], 6.5, places=9)

    def test_draught_beyond_depth_raises(self):
        with self.assertRaises(ValueError):
            FB.from_depth(10.0, 12.0)


class TestCompute(unittest.TestCase):
    def test_weighted_average_exact(self):
        r = FB.compute(analytic_case())
        self.assertAlmostEqual(r["values"]["average_freeboard_m"], 4.9, places=9)

    def test_segment_lengths_exact(self):
        r = FB.compute(analytic_case())
        self.assertAlmostEqual(r["segments"][0]["length_m"], 40.0, places=9)
        self.assertAlmostEqual(r["segments"][1]["length_m"], 60.0, places=9)

    def test_deck_immersion_angle_exact(self):
        """Earliest endpoint contact: first segment min(6,5)/10."""
        r = FB.compute(analytic_case())
        expect = math.degrees(math.atan(5.0 / 10.0))
        self.assertAlmostEqual(r["segments"][0]["deck_immersion_deg"], expect, places=9)
        self.assertAlmostEqual(r["values"]["deck_immersion_min_deg"],
                               math.degrees(math.atan(4.0 / 10.0)), places=9)

    def test_pct_not_full_warns(self):
        c = analytic_case()
        c["segments"][1]["length_pct_lwl"] = 50.0
        r = FB.compute(c)
        self.assertTrue(any("≠ 100" in w for w in r["warnings"]))
        self.assertAlmostEqual(r["values"]["covered_pct_lwl"], 90.0, places=9)

    def test_negative_freeboard_raises(self):
        c = analytic_case()
        c["segments"][0]["fb_aft_m"] = -1.0
        with self.assertRaises(ValueError):
            FB.compute(c)

    def test_low_immersion_angle_warns(self):
        """Low deck contact is disclosed without implying a GZ cutoff."""
        c = analytic_case()
        c["segments"] = [{"id": "low", "kind": "fore", "length_pct_lwl": 100.0,
                          "fb_fore_m": 1.0, "fb_aft_m": 1.0, "source": "解析"}]
        r = FB.compute(c)
        self.assertTrue(any("接水代理角" in w for w in r["warnings"]))

    def test_bad_kind_and_duplicate_raise(self):
        c = analytic_case()
        c["segments"][0]["kind"] = "poop"
        with self.assertRaises(ValueError):
            FB.compute(c)
        c = analytic_case()
        c["segments"][1]["id"] = "fore"
        with self.assertRaises(ValueError):
            FB.compute(c)

    def test_trace_discipline(self):
        for t in FB.compute(queen_mary_case())["trace"]:
            self.assertIn("formula", t)
            self.assertIn("source", t)
            self.assertIn("estimate", t)


class TestQueenMaryModelDerived(unittest.TestCase):
    """QM 的干舷是模型推得（无外部文献源），锚在生成器输出上。"""

    @classmethod
    def setUpClass(cls):
        cls.case = queen_mary_case()
        cls.r = FB.compute(cls.case)

    def test_two_segments_cover_full_length(self):
        self.assertEqual([s["id"] for s in self.r["segments"]], ["forecastle", "quarterdeck"])
        self.assertAlmostEqual(self.r["values"]["covered_pct_lwl"], 100.0, places=1)

    def test_all_estimate(self):
        """无外部文献源 → 每个分段都必须标 estimate。"""
        for s in self.r["segments"]:
            self.assertTrue(s["estimate"])

    def test_freeboard_bands(self):
        seg = {s["id"]: s for s in self.r["segments"]}
        self.assertAlmostEqual(seg["forecastle"]["fb_mean_m"], 8.90, places=2)
        self.assertAlmostEqual(seg["quarterdeck"]["fb_mean_m"], 7.12, places=2)
        self.assertTrue(6.0 < self.r["values"]["average_freeboard_m"] < 9.0)

    def test_main_deck_freeboard_from_model_depth(self):
        """模型 Hull z[-9.90, 5.10] → 型深 15.0；正常吃水 8.5 → 主甲板干舷 6.5 m。"""
        self.assertAlmostEqual(FB.from_depth(15.0, 8.5)["values"]["freeboard_m"], 6.5, places=9)

    def test_immersion_angles_exact(self):
        """Use each input segment's lowest endpoint and the B/2 proxy."""
        seg = {s["id"]: s for s in self.r["segments"]}
        half = self.case["beam_m"] / 2.0
        self.assertAlmostEqual(seg["forecastle"]["deck_immersion_deg"],
                               math.degrees(math.atan(min(self.case["segments"][0]["fb_fore_m"], self.case["segments"][0]["fb_aft_m"]) / half)),
                               places=9)
        self.assertAlmostEqual(seg["quarterdeck"]["deck_immersion_deg"],
                               math.degrees(math.atan(min(self.case["segments"][1]["fb_fore_m"], self.case["segments"][1]["fb_aft_m"]) / half)),
                               places=9)

    def test_immersion_angle_below_gz_peak(self):
        """Model-derived deck contact remains distinct from downflooding."""
        self.assertLess(self.r["values"]["deck_immersion_min_deg"], 40.0)
        self.assertGreater(self.r["values"]["deck_immersion_min_deg"], 10.0)


if __name__ == "__main__":
    unittest.main()
