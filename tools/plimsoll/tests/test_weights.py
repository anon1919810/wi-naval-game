# -*- coding: utf-8 -*-
"""L2 重量分组：合成引擎 + Queen Mary 装甲组实数据 的验收测试。"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import weights as W  # noqa: E402


def analytic_case():
    return {
        "schema": "plimsoll-weights-1",
        "datum": "keel",
        "groups": [
            {"id": "a", "items": [
                {"id": "x", "mass_t": 100.0, "kg_m": 2.0, "source": "解析"},
                {"id": "y", "mass_t": 300.0, "kg_m": 6.0, "source": "解析"},
            ]},
            {"id": "b", "items": [
                {"id": "z", "mass_t": 100.0, "kg_m": 10.0, "source": "解析"},
            ]},
        ],
        "reference": {"displacement_normal_t": 500.0},
    }


def queen_mary_case():
    p = os.path.join(PKG, "cases", "queen_mary_1913_weights.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class TestSynthesis(unittest.TestCase):
    def test_weighted_kg_is_exact(self):
        """合成 KG = Σ(m·kg)/Σm，解析对照 100·2+300·6+100·10 = 3000 / 500 = 6.0。"""
        r = W.synthesize(analytic_case())
        self.assertAlmostEqual(r["values"]["total_mass_t"], 500.0, places=9)
        self.assertAlmostEqual(r["values"]["kg_m"], 6.0, places=9)

    def test_group_subtotals(self):
        r = W.synthesize(analytic_case())
        g = {x["id"]: x for x in r["groups"]}
        self.assertAlmostEqual(g["a"]["mass_t"], 400.0, places=9)
        self.assertAlmostEqual(g["a"]["kg_m"], 5.0, places=9)   # (200+1800)/400
        self.assertAlmostEqual(g["b"]["mass_t"], 100.0, places=9)

    def test_wrong_datum_raises(self):
        """基准必须是 keel —— 本项目被坐标基准咬过三次，这里是第三道闸。"""
        c = analytic_case(); c["datum"] = "waterline"
        with self.assertRaises(ValueError):
            W.synthesize(c)

    def test_duplicate_item_id_raises(self):
        c = analytic_case()
        c["groups"][1]["items"][0]["id"] = "x"
        with self.assertRaises(ValueError):
            W.synthesize(c)

    def test_bad_mass_or_kg_raises(self):
        for patch in ({"mass_t": 0}, {"mass_t": -1}, {"kg_m": -1}, {"mass_t": None}):
            c = analytic_case()
            c["groups"][0]["items"][0].update(patch)
            with self.assertRaises(ValueError):
                W.synthesize(c)

    def test_empty_case_gives_zero_and_warning_not_zero_kg(self):
        c = analytic_case()
        c["groups"] = [{"id": "e", "items": []}]
        r = W.synthesize(c)
        self.assertEqual(r["values"]["total_mass_t"], 0.0)
        self.assertIsNone(r["values"]["kg_m"])
        self.assertTrue(any("为空" in w for w in r["warnings"]))

    def test_trace_discipline(self):
        """铁律：每个 trace 项都带 formula/source/estimate。"""
        r = W.synthesize(queen_mary_case())
        for t in r["trace"]:
            self.assertIn("formula", t)
            self.assertIn("source", t)
            self.assertIn("estimate", t)


class TestQueenMaryArmour(unittest.TestCase):
    """装甲组是几何推得的实数据，断言锚在源数据上（假绿教训）。"""

    @classmethod
    def setUpClass(cls):
        cls.case = queen_mary_case()
        cls.r = W.synthesize(cls.case)

    def test_armour_mass_anchored(self):
        """装甲合计 ≈ 6820.7 t —— 锚在生成器的输出上，改动生成器必须显式改这里。"""
        g = {x["id"]: x for x in self.r["groups"]}["armour"]
        self.assertAlmostEqual(g["mass_t"], 6820.7, delta=1.0)

    def test_armour_fraction_in_historical_band(self):
        """史实带：狮级/玛丽王后级装甲占排水量 22–28%。超出即包围盒/厚度有错。"""
        cov = self.r["values"]["coverage_pct"]
        self.assertTrue(22.0 < cov < 28.0, "装甲占比 %.1f%% 超出史实带" % cov)

    def test_armour_kg_plausible(self):
        """装甲合成重心应在水线附近（自龙骨 8–12 m）。"""
        g = {x["id"]: x for x in self.r["groups"]}["armour"]
        self.assertTrue(8.0 < g["kg_m"] < 12.0, "装甲 KG %.2f m 不合理" % g["kg_m"])

    def test_coverage_below_95_warns(self):
        """v0 只有装甲组：必须警告『此 KG 不能当全船 KG 用』。"""
        self.assertTrue(any("不能当全船 KG" in w for w in self.r["warnings"]))

    def test_empty_groups_listed(self):
        ids = {g["id"] for g in self.r["groups"] if g["items"] == 0}
        self.assertEqual(ids, {"armament", "machinery", "hull_outfit"})

    def test_gm_refuses_incomplete_weights(self):
        """残缺重量组算 GM 必须被拒 —— 这是本模块最重要的行为。"""
        with self.assertRaises(ValueError):
            W.gm_from_km(self.case, 13.41)


class TestGmFromKm(unittest.TestCase):
    def test_gm_arithmetic(self):
        c = analytic_case()          # 500 t 全覆盖 500 t 参考 → 允许算 GM
        r = W.gm_from_km(c, 8.0, free_surface_m=0.5)
        self.assertAlmostEqual(r["values"]["kg_eff_m"], 6.5, places=9)
        self.assertAlmostEqual(r["values"]["gm_m"], 1.5, places=9)

    def test_gm_includes_fsc_term(self):
        c = analytic_case()
        a = W.gm_from_km(c, 8.0, free_surface_m=0.0)["values"]["gm_m"]
        b = W.gm_from_km(c, 8.0, free_surface_m=0.5)["values"]["gm_m"]
        self.assertAlmostEqual(a - b, 0.5, places=9)


if __name__ == "__main__":
    unittest.main()
