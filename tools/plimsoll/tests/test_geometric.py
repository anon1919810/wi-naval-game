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


def make_box(L, B, T, depth, n=81, bottom_z=0.0):
    """方箱：每站剖面都是 z∈[bottom_z, bottom_z+depth]、y∈[−B/2,B/2] 的矩形。

    `bottom_z` 用来把解析件整体下移 —— 这样龙骨不再位于 z=0，
    "$z_B - \\text{keel}$" 才不是恒等变换，基准错误才有可能被测出来。
    """
    st = []
    for i in range(n):
        x = -0.5 * L * math.cos(math.pi * i / (n - 1))
        st.append((x, [(B / 2, bottom_z), (B / 2, bottom_z + depth),
                       (-B / 2, bottom_z + depth), (-B / 2, bottom_z)]))
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


class TestDatumShift(unittest.TestCase):
    """基准校验：把解析件**整体下移**，验证 KB / 吃水 / GZ 仍然自龙骨量。

    为什么必须单独测这个：`TestBoxAnalytic` 的方箱龙骨恰在 z=0，
    于是 "$z_B - \\text{keel}$" 是恒等变换 —— **基准错误在它上面天然不可见**。
    这是复核查出的盲区。这里把方箱下移到 z ∈ [−5, 0]、水线仍在 z=0，
    就逼出了真实基准。

    同时覆盖一个退化情形：水面正好切在剖面顶边（`_waterline_halfbeam`
    必须靠"顶点在水线上"兜住，严格穿越判据会把边全跳过）。

    箱子高度取 20 m（远高于水线）：**必须留出水线以上的舷侧**，否则倾斜后
    没有舱容可补偿，等体积倾斜无解。箱顶恰好压在水线上是常见的建模错误。
    """

    L, B, T, SHIFT, DEPTH = 100.0, 10.0, 5.0, -5.0, 20.0

    @classmethod
    def setUpClass(cls):
        cls.hull = make_box(cls.L, cls.B, cls.T, cls.DEPTH, n=81, bottom_z=cls.SHIFT)

    def test_volume_and_awp(self):
        gh = M.hydrostatics_upright(self.hull, 0.0)
        self.assertAlmostEqual(gh["volume_m3"], self.L * self.B * self.T, places=6)
        self.assertAlmostEqual(gh["awp_m2"], self.L * self.B, places=6)

    def test_datum_is_exposed_correctly(self):
        gh = M.hydrostatics_upright(self.hull, 0.0)
        self.assertAlmostEqual(gh["keel_z_m"], self.SHIFT, places=9)
        self.assertAlmostEqual(gh["draught_m"], self.T, places=9)

    def test_kb_is_measured_from_keel(self):
        gh = M.hydrostatics_upright(self.hull, 0.0)
        # 自龙骨量仍是 T/2 = 2.5；若漏掉换算会得到 z_B = −2.5（负数）
        self.assertAlmostEqual(gh["kb_m"], self.T / 2, places=9)

    def test_bm_and_km(self):
        gh = M.hydrostatics_upright(self.hull, 0.0)
        self.assertAlmostEqual(gh["bm_t_m"], self.B ** 2 / (12 * self.T), places=9)
        self.assertAlmostEqual(gh["km_m"], self.T / 2 + self.B ** 2 / (12 * self.T), places=9)

    def test_gz_matches_closed_form_after_shift(self):
        """GZ 只依赖 KG 与浮心，与坐标平移无关 —— 下移后闭式解必须仍成立。"""
        KG = 3.0
        vol = self.L * self.B * self.T
        bm = self.B ** 2 / (12 * self.T)
        gm = bm + self.T / 2 - KG
        for deg in (0, 5.0, 10.0, 20.0):
            phi = math.radians(deg)
            d, r = M.solve_equilibrium(self.hull, phi, vol)
            gz = r["yb"] * math.cos(phi) + (r["zb"] - self.SHIFT - KG) * math.sin(phi)
            exact = (gm * math.sin(phi)
                     + (self.B ** 2 / (24 * self.T)) * math.sin(phi) ** 3 / math.cos(phi) ** 2)
            self.assertAlmostEqual(gz, exact, places=5, msg="%d° 平移后闭式解不符" % deg)

    def test_waterline_outside_hull_raises(self):
        with self.assertRaises(ValueError):
            M.hydrostatics_upright(self.hull, self.SHIFT + self.DEPTH + 1.0)   # 高于箱顶
        with self.assertRaises(ValueError):
            M.hydrostatics_upright(self.hull, self.SHIFT - 1.0)                # 低于龙骨


class TestTrim(unittest.TestCase):
    """纵倾（阶段 2.1）：水线在 x–z 平面倾斜后，必须与解析解一致。

    取**直壁方箱**（沿 x 也是矩形），此时浸没剖面面积沿 x **线性**变化，
    所有量都有闭式解。设船长 L、船宽 B、龙骨 z=k、x=0 处水线高 d，
    吃水 T = d − k，纵倾角 θ（**θ > 0 = 艏倾**）：

        体积      ∇  = B·L·T                       （tanθ 项在对称区间上积掉）
        浮心纵向  x_B = tanθ · L² / (12·T)          （艏倾 → 浮心向艏）
        浮心垂向  KB = T/2 + tan²θ · L² / (24·T)    （纵倾对 KB 是二阶小量）
        水线面    Awp = L·B·√(1 + tan²θ)            （斜平面面积要乘这个因子）
    """

    L, B, T = 100.0, 10.0, 5.0
    KEEL, BOX_H = -5.0, 30.0          # 箱高 30 m：两端都不出水、不露底
    THETA_DEG = 2.0

    @classmethod
    def setUpClass(cls):
        cls.hull = make_box(cls.L, cls.B, cls.T, cls.BOX_H, n=241, bottom_z=cls.KEEL)
        cls.d0 = cls.KEEL + cls.T     # x=0 处水线高 → 吃水恰为 T
        cls.theta = math.radians(cls.THETA_DEG)
        cls.t = math.tan(cls.theta)
        cls.vol = cls.L * cls.B * cls.T

    def _untrimmed(self):
        return self.hull.integrate(0.0, self.d0, 0.0)

    def test_trim_zero_matches_untrimmed(self):
        """θ=0 必须**逐位**退化为原来的无纵倾结果 —— 新参数不能改变旧行为。"""
        a = self.hull.integrate(0.0, self.d0, 0.0)
        b = self.hull.integrate(0.0, self.d0)
        for k in ("volume", "yb", "zb", "xlcb", "awp"):
            self.assertAlmostEqual(a[k], b[k], places=12, msg="键 %s 不一致" % k)

    def test_volume_matches_closed_form(self):
        """体积必须等于 L·B·T。

        ⚠️ **但体积测不出纵倾有没有实现** —— 实测：把纵倾去掉，体积仍是 5000.0000。
        原因是 tanθ 项在对称区间 [−L/2, L/2] 上积掉了，体积对纵倾**一阶不敏感**。
        真正守住纵倾的是下面三条（LCB / KB / Awp），它们的差异分别是
        5.82 / 0.10 / 0.61 —— 一去掉纵倾立刻见红。
        这是"最直觉的断言往往抓不住 bug"的又一例，故在此写明。
        """
        got = self.hull.integrate(0.0, self.d0, self.theta)["volume"]
        self.assertAlmostEqual(got, self.vol, places=4)

    def test_lcb_shifts_toward_bow(self):
        r = self.hull.integrate(0.0, self.d0, self.theta)
        self.assertGreater(r["xlcb"], 0.0, "艏倾时浮心应向舰艏移动")
        expect = self.t * self.L ** 2 / (12.0 * self.T)
        # ∫x·A dx 的被积函数是**二次**的（A 沿 x 线性 ×x），梯形积分对二次不精确，
        # 故残留约 1e-4 相对量级的离散误差（体积与 KB 则是精确的）。
        # 这里断言相对误差，比写死小数位数更能说明"差在哪、为什么可以接受"。
        self.assertLess(abs(r["xlcb"] - expect) / expect, 1e-3,
                        "LCB 相对误差 %.2e 超出梯形积分的离散量级" % (abs(r["xlcb"] - expect) / expect))

    def test_kb_second_order_in_trim(self):
        kb = self.hull.integrate(0.0, self.d0, self.theta)["zb"] - self.KEEL
        expect = self.T / 2 + self.t ** 2 * self.L ** 2 / (24.0 * self.T)
        self.assertAlmostEqual(kb, expect, places=4)
        # 一阶项为零：KB 对纵倾是二阶敏感，这是纵倾不显著改变 KB 的定量依据
        self.assertLess(abs(kb - self.T / 2), 0.2)

    def test_awp_includes_slope_factor(self):
        awp = self.hull.integrate(0.0, self.d0, self.theta)["awp"]
        self.assertAlmostEqual(awp, self.L * self.B * math.sqrt(1 + self.t ** 2), places=3)
        # 必须比未纵倾时大（斜平面）
        self.assertGreater(awp, self._untrimmed()["awp"])
        self.assertAlmostEqual(self._untrimmed()["awp"], self.L * self.B, places=4)

    def test_lcb_sign_reverses_with_trim_sign(self):
        a = self.hull.integrate(0.0, self.d0, self.theta)["xlcb"]
        b = self.hull.integrate(0.0, self.d0, -self.theta)["xlcb"]
        self.assertAlmostEqual(a, -b, places=6)

    def test_solve_waterline_respects_trim(self):
        """等体积倾斜下给定纵倾求水线：体积必须回到目标值。"""
        d = self.hull.solve_waterline(0.0, self.vol, tol=1e-12, trim_rad=self.theta)
        v = self.hull.integrate(0.0, d, self.theta)["volume"]
        self.assertAlmostEqual(v, self.vol, places=6)
        # 纵倾对称：艏倾时 x=0 处水线应仍在同一高度
        self.assertAlmostEqual(d, self.d0, places=6)


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
