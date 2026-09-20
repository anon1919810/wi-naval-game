"""Plimsoll · L1 几何法单元测试

跑法：
    python -m unittest discover -s tools/plimsoll/tests -v
或  python tools/plimsoll/tests/test_geometric.py

测试分三类：
  1. **解析解验证**（方箱）—— 几何积分必须逐位复现闭式解
  2. **与 L0 交叉验证** —— 同一形状假设下，两条独立路径必须一致
  3. 数值性质 —— 收敛性、单调性、边界
"""

import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import geometry as G          # noqa: E402
import geometric as M         # noqa: E402
import hydrostatics as H      # noqa: E402

RHO = 1.025


def make_box(L, B, T, depth, n=81):
    """方箱：每站剖面都是 z∈[0,depth]、y∈[−B/2,B/2] 的矩形。"""
    st = []
    for i in range(n):
        x = -0.5 * L * math.cos(math.pi * i / (n - 1))
        st.append((x, [(B / 2, 0.0), (B / 2, depth), (-B / 2, depth), (-B / 2, 0.0)]))
    return G.StationedHull(st, name="box")


class TestBoxAnalytic(unittest.TestCase):
    """方箱是唯一有完整闭式解的船型，用它钉死几何积分。"""

    L, B, T, DEPTH = 100.0, 10.0, 5.0, 30.0

    def setUp(self):
        self.hull = make_box(self.L, self.B, self.T, self.DEPTH)
        self.gh = M.hydrostatics_upright(self.hull, self.T)

    def test_volume_exact(self):
        self.assertAlmostEqual(self.gh["volume_m3"], self.L * self.B * self.T, places=6)

    def test_kb_exact(self):
        self.assertAlmostEqual(self.gh["kb_m"], self.T / 2, places=9)

    def test_awp_exact(self):
        self.assertAlmostEqual(self.gh["awp_m2"], self.L * self.B, places=6)

    def test_it_exact(self):
        self.assertAlmostEqual(self.gh["it_m4"], self.L * self.B ** 3 / 12, places=6)

    def test_bm_exact(self):
        self.assertAlmostEqual(self.gh["bm_t_m"], self.B ** 2 / (12 * self.T), places=9)

    def test_km_exact(self):
        expect = self.T / 2 + self.B ** 2 / (12 * self.T)
        self.assertAlmostEqual(self.gh["km_m"], expect, places=9)


class TestBoxGZAnalytic(unittest.TestCase):
    """方箱大角稳性的闭式解。

    推导：横倾 φ、等体积（对直壁箱体，中线处水线恒为 z=T）时
        y_B = BM·tanφ ,  z_B = T/2 + tan²φ·B²/(24T)
    代入 GZ = y_B·cosφ + (z_B − KG)·sinφ 得

        GZ(φ) = GM·sinφ + (B²/(24T))·sin³φ / cos²φ ,   GM = B²/(12T) + T/2 − KG

    注意：常见的「GM·sinφ」只是小角展开；另一个常见写法 BM·sinφ·cosφ + (T/2−KG)·sinφ
    是**错的**（它假设 y_B = BM·sinφ，而实际是 BM·tanφ）。本测试用前者。
    """

    L, B, T, DEPTH, KG = 100.0, 10.0, 5.0, 30.0, 3.0

    @classmethod
    def setUpClass(cls):
        cls.hull = make_box(cls.L, cls.B, cls.T, cls.DEPTH)
        cls.vol = cls.L * cls.B * cls.T
        cls.bm = cls.B ** 2 / (12 * cls.T)
        cls.gm = cls.bm + cls.T / 2 - cls.KG

    def _exact(self, deg):
        phi = math.radians(deg)
        return (self.gm * math.sin(phi)
                + (self.B ** 2 / (24 * self.T)) * math.sin(phi) ** 3 / math.cos(phi) ** 2)

    def _geometric(self, deg):
        phi = math.radians(deg)
        _, r = M.solve_equilibrium(self.hull, phi, self.vol)
        return r["yb"] * math.cos(phi) + (r["zb"] - self.KG) * math.sin(phi)

    def test_gz_matches_closed_form(self):
        for deg in (0, 5, 10, 20, 30, 40):
            with self.subTest(angle=deg):
                self.assertAlmostEqual(self._geometric(deg), self._exact(deg), places=4,
                                       msg="%d° 处几何法与闭式解不符" % deg)

    def test_gz_is_zero_upright(self):
        self.assertAlmostEqual(self._geometric(0), 0.0, places=9)

    def test_righting_arm_matches_closed_form_at_small_angle(self):
        # 小角度处 GZ/sinφ → GM。用 5° 会混入二阶项，故这里直接与闭式解比。
        for deg in (0.1, 1.0, 5.0):
            with self.subTest(angle=deg):
                self.assertAlmostEqual(self._geometric(deg), self._exact(deg), places=6)

    def test_initial_slope_tends_to_gm(self):
        # 斜率在 φ→0 时趋于 GM。二阶项系数为 B²/(24T)，1° 时已约 2.5e-4，
        # 故必须用 <0.1° 才能验到 1e-4 量级。
        for deg in (0.1, 0.05):
            slope = self._geometric(deg) / math.sin(math.radians(deg))
            self.assertAlmostEqual(slope, self.gm, places=4,
                                   msg="%s° 处斜率偏离 GM 超过 1e-4" % deg)

    def test_volume_constant_across_heel(self):
        for deg in (0, 10, 30):
            _, r = M.solve_equilibrium(self.hull, math.radians(deg), self.vol)
            self.assertAlmostEqual(r["volume"], self.vol, places=3,
                                   msg="%d° 处没有保持等体积" % deg)


class TestCrossCheckWithL0(unittest.TestCase):
    """同一形状假设下，几何法（L1）与参数化法（L0）必须一致。

    L1 是"算出来的"，L0 是"按假设凑的"；两者对不上就说明有一边错了。
    """

    L, B, T, Cb, Cwp = 205.7, 27.1, 8.5, 0.551, 0.80

    @classmethod
    def setUpClass(cls):
        cls.hull = G.make_reference_hull(cls.L, cls.B, cls.T, cls.Cb, cls.Cwp)
        cls.l1 = M.hydrostatics_upright(cls.hull, cls.T)
        cls.l0 = H.compute({"lwl_m": cls.L, "beam_m": cls.B, "draught_m": cls.T,
                            "block_coeff": cls.Cb, "waterplane_coeff": cls.Cwp})["values"]

    def test_volume_agrees(self):
        d = abs(self.l1["volume_m3"] - self.l0["displacement_volume_m3"]) / self.l0["displacement_volume_m3"]
        self.assertLess(d, 1e-3, "体积相对差 %.4f%%，超出 0.1%%" % (d * 100))

    def test_awp_agrees(self):
        d = abs(self.l1["awp_m2"] - self.l0["awp_m2"]) / self.l0["awp_m2"]
        self.assertLess(d, 1e-3)

    def test_bm_agrees(self):
        d = abs(self.l1["bm_t_m"] - self.l0["bm_t_m"]) / self.l0["bm_t_m"]
        self.assertLess(d, 1e-3, "BM_T 相对差 %.4f%%" % (d * 100))

    def test_kb_morrish_difference_is_documented(self):
        """KB 是两法的**真实**差异，不是误差：L0 用 Morrish 近似，L1 精确积分。

        本测试把这个差值**钉住并记录**，不让它悄悄漂移。实测约 −1.9%，
        即 Morrish 在该船型上偏高约 2% —— 这是采用 L1 的理由之一。
        """
        diff = 100.0 * (self.l1["kb_m"] - self.l0["kb_m"]) / self.l0["kb_m"]
        self.assertGreater(diff, -4.0)
        self.assertLess(diff, 0.0)          # L1 低于 Morrish
        self.assertAlmostEqual(diff, -1.88, delta=0.5,
                               msg="Morrish 偏差从 −1.88%% 变成 %.2f%%，需复查" % diff)


class TestConvergence(unittest.TestCase):
    """离散精度：站位数与剖面边数增加时，结果必须收敛。"""

    L, B, T, Cb, Cwp = 205.7, 27.1, 8.5, 0.551, 0.80

    def test_section_resolution_converges(self):
        errs = []
        for n_sec in (24, 96, 384):
            hull = G.make_reference_hull(self.L, self.B, self.T, self.Cb, self.Cwp,
                                         n_section=n_sec)
            v = M.hydrostatics_upright(hull, self.T)["volume_m3"]
            errs.append(abs(v - self.Cb * self.L * self.B * self.T))
        for a, b in zip(errs, errs[1:]):
            self.assertLess(b, a, "剖面加密后误差反而变大：%r" % errs)
        self.assertLess(errs[-1] / (self.Cb * self.L * self.B * self.T), 1e-3)

    def test_station_count_converges(self):
        prev = None
        for n in (81, 161):
            hull = G.make_reference_hull(self.L, self.B, self.T, self.Cb, self.Cwp,
                                         n_stations=n, n_section=192)
            v = M.hydrostatics_upright(hull, self.T)["volume_m3"]
            err = abs(v - self.Cb * self.L * self.B * self.T)
            if prev is not None:
                self.assertLessEqual(err, prev + 1e-6)
            prev = err


class TestGZCurveProperties(unittest.TestCase):
    L, B, T, Cb, Cwp = 205.7, 27.1, 8.5, 0.551, 0.80
    KG = 8.6

    @classmethod
    def setUpClass(cls):
        cls.hull = G.make_reference_hull(cls.L, cls.B, cls.T, cls.Cb, cls.Cwp, deck=14.0)
        cls.vol = cls.Cb * cls.L * cls.B * cls.T
        cls.rows = M.gz_curve(cls.hull, cls.KG, cls.vol,
                              [0, 5, 10, 15, 20, 30, 40, 50, 60])

    def test_starts_at_zero(self):
        self.assertAlmostEqual(self.rows[0]["gm_arm_m"], 0.0, places=9)

    def test_initial_slope_matches_upright_gm(self):
        """GZ 曲线在 φ→0 的斜率必须等于 GM —— 这是 L1 内部自洽的关键断言。

        必须在**平衡水线**上取 GM，且角度要足够小：本船 GM≈4.4 m 很刚，
        5° 时二阶项已让 GZ/sinφ 偏离 GM 约 7%，故用 0.01°。
        """
        d0 = self.hull.solve_waterline(0.0, self.vol, tol=1e-13)
        gm = M.hydrostatics_upright(self.hull, d0)["km_m"] - self.KG
        phi = math.radians(0.01)
        d, r = M.solve_equilibrium(self.hull, phi, self.vol, tol=1e-13)
        slope = (r["yb"] * math.cos(phi) + (r["zb"] - self.KG) * math.sin(phi)) / math.sin(phi)
        self.assertAlmostEqual(slope, gm, places=5,
                               msg="0.01° 斜率 %.6f 与 GM %.6f 不符" % (slope, gm))

    def test_positive_through_range(self):
        for r in self.rows:
            self.assertGreaterEqual(r["gm_arm_m"], -1e-9,
                                    "%d° 处复原力臂为负" % r["angle_deg"])

    def test_volume_preserved(self):
        for r in self.rows:
            self.assertAlmostEqual(r["volume_m3"], self.vol, places=0,
                                   msg="%d° 处体积不守恒" % r["angle_deg"])

    def test_curve_is_smooth_and_single_peaked_early(self):
        gz = [r["gm_arm_m"] for r in self.rows]
        diffs = [b - a for a, b in zip(gz, gz[1:])]
        # 前段应单调上升（未到稳性消失角）
        self.assertTrue(all(d > 0 for d in diffs[:4]),
                        "小角度段 GZ 应单调上升，实际 %r" % diffs[:4])


if __name__ == "__main__":
    unittest.main(verbosity=2)
