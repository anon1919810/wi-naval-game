# -*- coding: utf-8 -*-
"""阻力与功率（7.3 v0）：摩擦线解析对照、四维插值、试航反解。"""
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import resistance as R  # noqa: E402


def synth_table():
    """合成四维表：值 = 10·Cp + B/T + 1000·∇/L³ + 10·Fn（**对四个自变量都线性**）。
    多线性插值对线性函数应精确 —— 用它锚住插值不写错。"""
    cps = [0.50, 0.70]
    bts = [2.0, 3.0]
    vols = [0.002, 0.003]
    fns = [0.20, 0.30]

    def f(cp, bt, v, fn):
        return 10.0 * cp + bt + 1000.0 * v + 10.0 * fn

    grid = [[[[f(cp, bt, v, fn) for fn in fns] for v in vols] for bt in bts] for cp in cps]
    return {"axes": {"cp": cps, "bt": bts, "volumetric": vols, "fn": fns},
            "grid_order": ["cp", "bt", "volumetric", "fn"], "cr": grid,
            "source": "合成表（测试用）"}


class TestSchoenherr(unittest.TestCase):
    def test_exact_at_1e9(self):
        """Cf = 0.4631 / (lg 1e9)^2.6 = 0.4631 / 9^2.6。"""
        self.assertAlmostEqual(R.schoenherr_cf(1e9)["values"]["cf"],
                               0.4631 / (9.0 ** 2.6), places=12)

    def test_too_small_raises(self):
        with self.assertRaises(ValueError):
            R.schoenherr_cf(1e4)

    def test_out_of_range_warns(self):
        self.assertTrue(R.schoenherr_cf(1e12)["warnings"])

    def test_agrees_with_ittc1957(self):
        """两条摩擦线在实船雷诺数量级应相差 <3%（QM Rn≈2.6e9：实测 −0.3%）。"""
        rn = 2.592e9
        a = R.schoenherr_cf(rn)["values"]["cf"]
        b = R.ittc1957_cf(rn)
        self.assertLess(abs(a - b) / b, 0.03)


class TestFrictionResistance(unittest.TestCase):
    def test_definition_exact(self):
        v, L, S, nu, rho = 10.0, 100.0, 2000.0, 1e-6, 1025.0
        cf = R.schoenherr_cf(v * L / nu)["values"]["cf"]
        r = R.friction_resistance(v, L, S, nu=nu, rho=rho)
        self.assertAlmostEqual(r["values"]["rn"], 1e9, places=6)
        self.assertAlmostEqual(r["values"]["rf_n"],
                               0.5 * rho * S * cf * v * v, places=6)

    def test_roughness_adds_delta_cf(self):
        a = R.friction_resistance(10.0, 100.0, 2000.0, nu=1e-6, delta_cf=0.0)
        b = R.friction_resistance(10.0, 100.0, 2000.0, nu=1e-6,
                                  delta_cf=R.DELTA_CF_TAYLOR)
        self.assertAlmostEqual(b["values"]["cf_total"],
                               a["values"]["cf"] + R.DELTA_CF_TAYLOR, places=12)
        self.assertGreater(b["values"]["rf_n"], a["values"]["rf_n"])

    def test_bad_inputs_raise(self):
        for kw in ({"v_mps": 0}, {"l_wl_m": -1}, {"s_m2": 0}, {"nu": 0}):
            args = dict(v_mps=10.0, l_wl_m=100.0, s_m2=2000.0, nu=1e-6)
            args.update(kw)
            with self.assertRaises(ValueError):
                R.friction_resistance(**args)


class TestResidualTable(unittest.TestCase):
    def test_missing_table_gives_none_and_warns(self):
        """没图谱就置空 —— **绝不照抄 OCR 乱码**。"""
        r = R.residual_from_table(None, 0.6, 3.0, 0.002, 0.3)
        self.assertIsNone(r["values"]["cr"])
        self.assertTrue(any("OCR" in w for w in r["warnings"]))

    def test_node_exact(self):
        t = synth_table()
        r = R.residual_from_table(t, 0.50, 2.0, 0.002, 0.20)
        self.assertAlmostEqual(r["values"]["cr"],
                               10 * 0.50 + 2.0 + 1000 * 0.002 + 10 * 0.20, places=9)

    def test_linear_function_interpolated_exactly(self):
        """多线性插值对线性函数必须精确（中点也精确）。"""
        t = synth_table()
        cp, bt, v, fn = 0.60, 2.5, 0.0025, 0.25
        r = R.residual_from_table(t, cp, bt, v, fn)
        self.assertAlmostEqual(r["values"]["cr"],
                               10 * cp + bt + 1000 * v + 10 * fn, places=9)

    def test_outside_grid_clips_and_warns(self):
        """越界**不外推**（外推 = 静默编数据），只截断并警告。"""
        t = synth_table()
        r = R.residual_from_table(t, 0.90, 2.5, 0.0025, 0.25)
        self.assertTrue(any("截断" in w for w in r["warnings"]))
        self.assertAlmostEqual(r["values"]["cr"],
                               R.residual_from_table(t, 0.70, 2.5, 0.0025, 0.25)["values"]["cr"],
                               places=9)


class TestPowerAndBacksolve(unittest.TestCase):
    def test_effective_power_exact(self):
        r = R.effective_power(1_000_000.0, 10.0)
        self.assertAlmostEqual(r["values"]["pe_kw"], 10000.0, places=9)
        self.assertAlmostEqual(r["values"]["pe_shp"], 10000.0 / R.HP_TO_KW, places=6)

    def test_residual_force_definition(self):
        rr = R.residual_force(0.002, 10.0, 2000.0)
        self.assertAlmostEqual(rr["values"]["rr_n"],
                               0.5 * R.RHO_SEA * 2000.0 * 0.002 * 100.0, places=6)

    def test_backsolve_arithmetic(self):
        """SHP 10000 @ 20 kn、QPC 0.5、Rf 已知 → R_total = P/V，Rr = R_total − Rf。"""
        v_kn = 20.0
        v = v_kn * R.KNOT_MPS
        pe_w = 10000.0 * R.HP_TO_KW * 1000.0 * 0.5
        rf = 300_000.0
        r = R.implied_residual_from_trial(10000.0, v_kn, rf, 2000.0, qpc=0.5)
        self.assertAlmostEqual(r["values"]["pe_kw"], pe_w / 1000.0, places=6)
        self.assertAlmostEqual(r["values"]["r_total_n"], pe_w / v, places=3)
        self.assertAlmostEqual(r["values"]["rr_n"], pe_w / v - rf, places=3)

    def test_qpc_assumption_is_flagged(self):
        r = R.implied_residual_from_trial(83000.0, 28.1, 1.2e6, 6407.9, qpc=0.55)
        self.assertTrue(any("QPC" in w and "无来源" in w for w in r["warnings"]))


class TestQueenMaryTrial(unittest.TestCase):
    """QM 试航：83,000 shp → 28.1 kn（Navypedia）。"""

    @classmethod
    def setUpClass(cls):
        v = 28.1 * R.KNOT_MPS
        cls.fr = R.friction_resistance(v, 213.4, 6407.9,
                                       nu=R.NU_SEA_15C, delta_cf=R.DELTA_CF_TAYLOR)
        cls.imp = R.implied_residual_from_trial(83000.0, 28.1, cls.fr["values"]["rf_n"],
                                                6407.9, qpc=0.55)

    def test_reynolds_and_friction_band(self):
        """Rn ≈ 2.6e9；含粗糙度附加的 Rf 约 1.2 MN（量级锚）。"""
        self.assertAlmostEqual(self.fr["values"]["rn"], 2.592e9, delta=5e7)
        self.assertTrue(1000.0 < self.fr["values"]["rf_kN"] < 1400.0,
                        "Rf=%.0f kN 超出量级" % self.fr["values"]["rf_kN"])

    def test_implied_cr_plausible(self):
        """反解 Cr ≈ 1.7e-3，落在细瘦高速船的合理量级（1e-3 – 4e-3）。"""
        cr = self.imp["values"]["cr_implied"]
        self.assertTrue(1e-3 < cr < 4e-3, "Cr=%.5f 不在合理量级" % cr)

    def test_residual_share_sane(self):
        """剩余阻力占总阻力 30%–70%（摩擦不能吃掉全部，也不能只剩零头）。"""
        share = self.imp["values"]["rr_n"] / self.imp["values"]["r_total_n"]
        self.assertTrue(0.3 < share < 0.7, "剩余占比 %.2f 不合理" % share)

    def test_trace_discipline(self):
        for t in self.fr["trace"] + self.imp["trace"]:
            self.assertIn("formula", t)
            self.assertIn("source", t)
            self.assertIn("estimate", t)


if __name__ == "__main__":
    unittest.main()
