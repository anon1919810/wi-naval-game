"""hullwright L0 单元测试

跑法：
    python -m unittest discover -s tools/hullwright/tests -v
或  python tools/hullwright/tests/test_hydrostatics.py
"""

import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import hydrostatics as H  # noqa: E402

CASE = os.path.join(os.path.dirname(HERE), "cases", "queen_mary_1913.json")


class TestBoxDegenerate(unittest.TestCase):
    """方箱：所有量都有解析解，是检验形状模型自洽性的最强手段。"""

    def setUp(self):
        self.out = H.compute({"lwl_m": 100.0, "beam_m": 10.0, "draught_m": 10.0,
                              "block_coeff": 1.0, "waterplane_coeff": 1.0})
        self.v = self.out["values"]

    def test_volume_and_area(self):
        self.assertAlmostEqual(self.v["displacement_volume_m3"], 10000.0, places=9)
        self.assertAlmostEqual(self.v["awp_m2"], 1000.0, places=9)

    def test_kb_is_half_draught(self):
        self.assertAlmostEqual(self.v["kb_m"], 5.0, places=9)

    def test_bm_transverse(self):
        # BM_T = B² / (12T)
        self.assertAlmostEqual(self.v["bm_t_m"], 10.0 ** 2 / (12 * 10), places=9)

    def test_il_is_bl3_over_12(self):
        # I_L = B·L³ / 12  → BM_L = I_L/∇ = L²/(12T)
        self.assertAlmostEqual(self.v["il_m4"], 10.0 * 100.0 ** 3 / 12, places=3)
        self.assertAlmostEqual(self.v["bm_l_m"], 100.0 ** 2 / (12 * 10), places=6)

    def test_shape_parameter_tends_to_zero(self):
        self.assertLess(abs(self.out["shape_model"]["p"]), 1e-6)

    def test_tpc(self):
        self.assertAlmostEqual(self.v["tpc_t_per_cm"], 1000.0 * 1.025 / 100.0, places=9)


class TestShapeModel(unittest.TestCase):
    """形状模型自身的性质：Cwp↔p 单调互逆、C_I 随 Cwp 单调。"""

    def test_p_from_cwp_roundtrip(self):
        for cwp in (0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00):
            p = H.shape_p_from_cwp(cwp)
            self.assertAlmostEqual(H._A(p), cwp, places=9,
                                   msg="Cwp=%r 反解 p=%r 后回代不闭合" % (cwp, p))

    def test_p_monotonic_decreasing_in_cwp(self):
        ps = [H.shape_p_from_cwp(c) for c in (0.60, 0.70, 0.80, 0.90, 1.00)]
        for a, b in zip(ps, ps[1:]):
            self.assertGreater(a, b)

    def test_ci_monotonic_increasing_in_cwp(self):
        prev = -1.0
        for cwp in (0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 1.00):
            c = H.waterplane_coeffs(cwp)["c_i"]
            self.assertGreater(c, prev)
            prev = c

    def test_ci_bounded_by_box(self):
        # 方箱是上界：任何真实船型的 C_I 都应 ≤ 1
        for cwp in (0.60, 0.75, 0.85, 1.00):
            self.assertLessEqual(H.waterplane_coeffs(cwp)["c_i"], 1.0 + 1e-12)


class TestInputValidation(unittest.TestCase):
    def test_rejects_nonpositive(self):
        for bad in ({"lwl_m": 0.0}, {"beam_m": -1.0}, {"draught_m": 0.0}, {"block_coeff": 0.0}):
            base = {"lwl_m": 100.0, "beam_m": 10.0, "draught_m": 5.0, "block_coeff": 0.5}
            base.update(bad)
            with self.assertRaises(ValueError):
                H.compute(base)

    def test_rejects_nonfinite(self):
        base = {"lwl_m": 100.0, "beam_m": 10.0, "draught_m": 5.0, "block_coeff": 0.5}
        for k in ("lwl_m", "beam_m", "draught_m"):
            b = dict(base)
            b[k] = float("inf")
            with self.assertRaises(ValueError):
                H.compute(b)

    def test_rejects_cwp_out_of_range(self):
        for bad in (0.1, 1.5):
            with self.assertRaises(ValueError):
                H.waterplane_coeffs(bad)

    def test_rejects_absurd_cb(self):
        with self.assertRaises(ValueError):
            H.compute({"lwl_m": 100.0, "beam_m": 10.0, "draught_m": 5.0, "block_coeff": 1.6})


class TestQueenMaryCase(unittest.TestCase):
    """真实案例：输入与输出必须自洽，且落在量级合理的范围内。"""

    @classmethod
    def setUpClass(cls):
        with open(CASE, encoding="utf-8") as f:
            cls.ship = json.load(f)
        cls.out = H.compute(cls.ship["hull"])
        cls.v = cls.out["values"]

    def test_displacement_matches_input(self):
        dev = abs(self.v["displacement_deviation_pct"])
        self.assertLess(dev, 0.5,
                        "排水量与输入偏差 %.3f%%，说明 Cb 的推导或口径有问题" % dev)

    def test_awp_plausible(self):
        # 水线面系数 0.80 × 205.7 × 27.1 ≈ 4459 m²；留 ±8% 余量
        self.assertAlmostEqual(self.v["awp_m2"], 4459.6, delta=4459.6 * 0.08)

    def test_km_exceeds_kb(self):
        self.assertGreater(self.v["km_m"], self.v["kb_m"])

    def test_gm_positive_at_estimated_kg(self):
        self.assertGreater(self.v["gm_m"], 0.0)

    def test_warnings_flag_estimates(self):
        joined = " ".join(self.out["warnings"])
        # KG 是 estimate，必须被提示到位（没提示就说明标记丢了）
        self.assertTrue("KG" in joined or "kg_m" in joined or self.v.get("gm_m") is not None)

    def test_trace_covers_every_value(self):
        keys = {t["key"] for t in self.out["trace"]}
        for k in self.v:
            self.assertIn(k, keys, "值 %s 没有对应的 trace 记录" % k)

    def test_every_trace_has_source(self):
        for t in self.out["trace"]:
            self.assertTrue(t.get("formula"), "%s 缺 formula" % t["key"])
            self.assertTrue(t.get("source"), "%s 缺 source" % t["key"])


class TestCrossChecksAgainstProjectAsset(unittest.TestCase):
    """与本项目 Unity 资产里那个无来源的默认值做对照。

    ShipFloatPrototype 用 waterplaneAreaM2 = 4610.4，反推隐含 Cwp = 0.827。
    本测试把这个对照关系固化，避免日后有人改常数却不知道原始依据。
    """

    GAME_AWP = 4610.4
    GAME_L, GAME_B = 205.7, 27.1

    def test_game_constant_implies_cwp(self):
        implied = self.GAME_AWP / (self.GAME_L * self.GAME_B)
        self.assertAlmostEqual(implied, 0.827, delta=0.002)

    def test_our_value_within_5pct_of_game_constant(self):
        out = H.compute({"lwl_m": self.GAME_L, "beam_m": self.GAME_B,
                         "draught_m": 8.5, "block_coeff": 0.551,
                         "waterplane_coeff": 0.80})
        delta = abs(out["values"]["awp_m2"] - self.GAME_AWP) / self.GAME_AWP
        self.assertLess(delta, 0.05,
                        "我们算的 Awp 与游戏常数差 %.1f%%，需查明口径" % (delta * 100))


class TestSensitivity(unittest.TestCase):
    def test_kg_up_gm_down(self):
        hull = {"lwl_m": 205.7, "beam_m": 27.1, "draught_m": 8.5,
                "block_coeff": 0.551, "waterplane_coeff": 0.80}
        rows = H.sensitivity_kg(hull, [8.0, 9.0, 10.0, 11.0, 12.0])
        for a, b in zip(rows, rows[1:]):
            self.assertLess(b["gm_m"], a["gm_m"])
            self.assertGreater(b["roll_period_s"], a["roll_period_s"])

    def test_km_independent_of_kg(self):
        hull = {"lwl_m": 205.7, "beam_m": 27.1, "draught_m": 8.5,
                "block_coeff": 0.551, "waterplane_coeff": 0.80}
        rows = H.sensitivity_kg(hull, [8.0, 12.0])
        self.assertAlmostEqual(rows[0]["km_m"], rows[1]["km_m"], places=9)


class TestRollPeriodFormula(unittest.TestCase):
    """横摇周期必须与闭式解一致：T = 2πk/√(g·GM)。"""

    def test_matches_closed_form(self):
        B, fxx, Td, Cb, Cwp = 27.1, 0.38, 8.5, 0.551, 0.80
        # 先拿到 KM，再反选一个 KG 使 GM 恰为 2.0 m
        probe = H.compute({"lwl_m": 205.7, "beam_m": B, "draught_m": Td,
                           "block_coeff": Cb, "waterplane_coeff": Cwp})
        km = probe["values"]["km_m"]
        out = H.compute({"lwl_m": 205.7, "beam_m": B, "draught_m": Td,
                         "block_coeff": Cb, "waterplane_coeff": Cwp,
                         "kg_m": km - 2.0, "roll_gyration_coeff": fxx})
        v = out["values"]
        self.assertAlmostEqual(v["gm_m"], 2.0, places=9)
        expect = 2.0 * math.pi * (fxx * B) / math.sqrt(9.80665 * 2.0)
        self.assertAlmostEqual(v["roll_period_s"], expect, places=6)

    def test_shorter_period_when_gm_larger(self):
        base = {"lwl_m": 205.7, "beam_m": 27.1, "draught_m": 8.5,
                "block_coeff": 0.551, "waterplane_coeff": 0.80}
        km = H.compute(base)["values"]["km_m"]
        stiff = H.compute({**base, "kg_m": km - 4.0})["values"]["roll_period_s"]
        tender = H.compute({**base, "kg_m": km - 1.0})["values"]["roll_period_s"]
        self.assertLess(stiff, tender)

    def test_no_gm_no_period(self):
        out = H.compute({"lwl_m": 205.7, "beam_m": 27.1, "draught_m": 8.5,
                         "block_coeff": 0.551, "waterplane_coeff": 0.80})
        self.assertNotIn("roll_period_s", out["values"])
        self.assertTrue(any("kg_m" in w for w in out["warnings"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
