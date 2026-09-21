"""Plimsoll · 阶段 2.2 纵倾平衡求解测试

验收锚：
  1. 直壁方箱闭式解（整段浸没）—— d*、θ、LCB 必须同时成立
  2. 方程必须**同时**满足体积与 LCB（只满足体积是假绿）
  3. 参照船体：由已知 θ 生成观测再反解，必须往返还原
  4. 不可达目标必须抛错，不返回伪解
"""

import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import geometry as G          # noqa: E402
import geometric as M         # noqa: E402


def make_box(L, B, T, depth, n=81, bottom_z=0.0):
    st = []
    for i in range(n):
        x = -0.5 * L * math.cos(math.pi * i / (n - 1))
        st.append((x, [(B / 2, bottom_z), (B / 2, bottom_z + depth),
                       (-B / 2, bottom_z + depth), (-B / 2, bottom_z)]))
    return G.StationedHull(st, name="box")


def make_asymmetric_box(L, B_aft, B_fore, depth, n=81, bottom_z=0.0):
    """艉半宽 B_aft、艏半宽 B_fore 的直壁折线箱。

    对称船体上 ∫x·B(x)dx=0，等体积下 d*(+θ)=d*(−θ)，**测不出内层丢掉 θ**。
    不对称时 d* = (V* − tanθ·∫xB dx)/∫B dx，必须随 θ 变化。
    """
    st = []
    for i in range(n):
        t = i / (n - 1.0)
        x = -0.5 * L + t * L
        if x <= 0.0:
            half = 0.5 * B_aft
        else:
            half = 0.5 * B_fore
        if -L * 0.05 < x < L * 0.05:
            u = (x + L * 0.05) / (L * 0.1)
            half = 0.5 * ((1 - u) * B_aft + u * B_fore)
        st.append((x, [(half, bottom_z), (half, bottom_z + depth),
                       (-half, bottom_z + depth), (-half, bottom_z)]))
    return G.StationedHull(st, name="asym-box")


class TestTrimEquilibriumBox(unittest.TestCase):
    """方箱：整段浸没时闭式解 d*=keel+T，tanθ=12·T·LCB/L²。"""

    L, B, T = 100.0, 20.0, 5.0
    KEEL, BOX_H = -5.0, 30.0

    @classmethod
    def setUpClass(cls):
        cls.hull = make_box(cls.L, cls.B, cls.T, cls.BOX_H, n=241, bottom_z=cls.KEEL)
        cls.vol = cls.L * cls.B * cls.T
        cls.d_star = cls.KEEL + cls.T

    def test_zero_lcb_is_upright(self):
        """LCG 在船中 → θ=0，水线在 keel+T。体积与 LCB 同时达标。"""
        out = self.hull.solve_trim_equilibrium(self.vol, 0.0, lcb_tol=1e-8)
        self.assertAlmostEqual(out["volume_m3"], self.vol, places=6)
        self.assertAlmostEqual(out["xlcb_m"], 0.0, places=8)
        self.assertAlmostEqual(out["trim_rad"], 0.0, places=8)
        self.assertAlmostEqual(out["d_m"], self.d_star, places=6)

    def _closed_form(self, lcb):
        tan_theta = 12.0 * self.T * lcb / (self.L ** 2)
        return math.atan(tan_theta)

    def test_positive_lcb_matches_closed_form(self):
        """艏向载荷：θ 与 LCB 同号，d 仍为 keel+T（整段浸没）。

        θ 对闭式解用**相对误差**：数值 LCB 的被积函数含 x·A(x)，
        梯形积分对二次不精确（TestTrim 已钉在 ~1e-3 量级），
        故反解出的 θ 与解析 θ 会有同量级相对差 —— 这不是求根失败。
        真正必须钉死的是：体积达标、**数值 xlcb 逼近目标**、θ 与 LCB 同号。
        """
        lcb = 2.0
        theta_expect = self._closed_form(lcb)
        out = self.hull.solve_trim_equilibrium(self.vol, lcb, lcb_tol=1e-7)
        self.assertGreater(out["trim_rad"], 0.0, "正 LCB → 艏倾")
        self.assertAlmostEqual(out["volume_m3"], self.vol, places=6)
        self.assertAlmostEqual(out["xlcb_m"], lcb, places=6)
        rel = abs(out["trim_rad"] - theta_expect) / abs(theta_expect)
        self.assertLess(rel, 1e-3, "θ 相对误差 %.2e 超出离散量级" % rel)
        self.assertAlmostEqual(out["d_m"], self.d_star, places=5)

    def test_negative_lcb_matches_closed_form(self):
        """艉向载荷：θ 为负（艉倾），符号约定必须一致。"""
        lcb = -1.5
        theta_expect = self._closed_form(lcb)
        out = self.hull.solve_trim_equilibrium(self.vol, lcb, lcb_tol=1e-7)
        self.assertLess(out["trim_rad"], 0.0, "负 LCB → 艉倾")
        self.assertAlmostEqual(out["volume_m3"], self.vol, places=6)
        self.assertAlmostEqual(out["xlcb_m"], lcb, places=6)
        rel = abs(out["trim_rad"] - theta_expect) / abs(theta_expect)
        self.assertLess(rel, 1e-3, "θ 相对误差 %.2e 超出离散量级" % rel)
        self.assertAlmostEqual(out["d_m"], self.d_star, places=5)

    def test_volume_and_lcb_both_required(self):
        """假绿哨兵：解必须同时满足体积与 LCB，且残差字段可核。

        若实现只解体积、θ 恒 0，则 LCB 残差不会是 0。
        """
        lcb = 2.0
        out = self.hull.solve_trim_equilibrium(self.vol, lcb, lcb_tol=1e-7)
        self.assertLess(abs(out["volume_residual_m3"]), 1e-6)
        self.assertLess(abs(out["lcb_residual_m"]), 1e-7)
        # 反证：固定 θ=0 只解体积时，LCB 必为 0，对不上目标
        d0 = self.hull.solve_waterline(0.0, self.vol, trim_rad=0.0)
        r0 = self.hull.integrate(0.0, d0, 0.0)
        self.assertLess(abs(r0["xlcb"]), 1e-9)
        self.assertGreater(abs(r0["xlcb"] - lcb), 0.5,
                           "θ=0 时 LCB 与目标差很大 → 只满足体积的假解过不了")

    def test_wrapper_returns_same_trim(self):
        out_hull = self.hull.solve_trim_equilibrium(self.vol, 2.0, lcb_tol=1e-7)
        out_wrap = M.solve_trim_equilibrium(self.hull, self.vol, 2.0, lcb_tol=1e-7)
        self.assertAlmostEqual(out_hull["trim_rad"], out_wrap["trim_rad"], places=12)
        self.assertAlmostEqual(out_hull["d_m"], out_wrap["d_m"], places=12)
        self.assertIn("hydrostatics", out_wrap)
        self.assertEqual(out_wrap["target_lcb_m"], 2.0)

    def test_tighter_tol_reduces_residual(self):
        loose = self.hull.solve_trim_equilibrium(self.vol, 2.0, lcb_tol=1e-4)
        tight = self.hull.solve_trim_equilibrium(self.vol, 2.0, lcb_tol=1e-9)
        self.assertLessEqual(abs(tight["lcb_residual_m"]), abs(loose["lcb_residual_m"]) + 1e-15)
        self.assertLessEqual(abs(tight["lcb_residual_m"]), 1e-9)

    def test_unreachable_lcb_raises(self):
        """超出物理可达范围的 LCB 必须报错，不能静默返回伪解。"""
        absurd = self.L * 50.0
        with self.assertRaises(ValueError):
            self.hull.solve_trim_equilibrium(self.vol, absurd)

    def test_nonpositive_volume_raises(self):
        with self.assertRaises(ValueError):
            self.hull.solve_trim_equilibrium(0.0, 0.0)
        with self.assertRaises(ValueError):
            self.hull.solve_trim_equilibrium(-1.0, 0.0)

    def test_overcapacity_volume_raises(self):
        """目标排水量超过船体可浸没体积 → 必须抛错（体积门闩）。

        方箱最大浸没体积 = L·B·BOX_H（整箱，龙骨到箱顶）。
        """
        v_max = self.L * self.B * self.BOX_H
        v_over = v_max * 1.2
        with self.assertRaises(ValueError) as ctx:
            self.hull.solve_trim_equilibrium(v_over, 0.0)
        msg = str(ctx.exception)
        self.assertTrue("体积" in msg or "可浸没" in msg, msg)

    def test_success_requires_volume_and_lcb_gates(self):
        """成功返回时体积与 LCB 残差都必须在容差内（双门闩）。"""
        out = self.hull.solve_trim_equilibrium(self.vol, 2.0, lcb_tol=1e-7)
        self.assertLessEqual(abs(out["volume_residual_m3"]), out["volume_eq_tol_m3"])
        self.assertLessEqual(abs(out["lcb_residual_m"]), 1e-7)
        self.assertIn("volume_eq_tol_m3", out)


class TestTrimEquilibriumRoundTrip(unittest.TestCase):
    """参照船体往返：先由已知 θ 观测 xlcb，再反解必须还原 θ。"""

    @classmethod
    def setUpClass(cls):
        cls.hull = G.make_reference_hull(L=200.0, B=30.0, T=9.0,
                                         Cb=0.53, Cwp=0.80,
                                         depth=9.0 * 1.6, n_stations=81)
        # 设计水线：参照船体龙骨在 z=0、满载吃水 T 时水线在 z=T
        cls.vol = None
        r0 = cls.hull.integrate(0.0, 9.0, 0.0)
        cls.vol = r0["volume"]
        cls.lcb0 = r0["xlcb"]

    def test_round_trip_known_trim(self):
        theta_true = math.radians(1.2)
        r = self.hull.integrate(0.0, 9.0, theta_true)
        # 参照船体壁面侧、体积对纵倾一阶不敏感；用同一目标体积反解
        out = self.hull.solve_trim_equilibrium(
            self.vol, r["xlcb"], lcb_tol=1e-6, max_outer=60)
        self.assertAlmostEqual(out["volume_m3"], self.vol, places=4)
        self.assertAlmostEqual(out["xlcb_m"], r["xlcb"], places=5)
        # 反解 θ 应还原（离散积分下给合理容差）
        self.assertLess(abs(out["trim_rad"] - theta_true), 5e-4,
                        "往返 θ 误差 %.3e rad" % abs(out["trim_rad"] - theta_true))

    def test_zero_offset_trim_is_small(self):
        """以未纵倾 LCB 为目标 → θ 应接近 0。"""
        out = self.hull.solve_trim_equilibrium(self.vol, self.lcb0, lcb_tol=1e-6)
        self.assertLess(abs(out["trim_rad"]), 1e-3)
        self.assertAlmostEqual(out["xlcb_m"], self.lcb0, places=5)

    def test_d_changes_with_trim_on_asymmetric_hull(self):
        """内层若忽略 θ，不对称船体上的 d 会不对 —— 变异哨兵。

        对称船体 d*(±θ) 相同，测不出内层丢掉纵倾；艉宽 30 / 艏宽 12 时
        d* = (V* − tanθ·∫xB dx)/∫B dx，必须随 θ 变化。
        """
        hull = make_asymmetric_box(100.0, 30.0, 12.0, 30.0, n=121, bottom_z=-5.0)
        # 设计状态：中线吃水 6 m 的等效体积（按 x=0 处宽 21 m 估算目标）
        vol = hull.integrate(0.0, 1.0, 0.0)["volume"]  # waterline z=1 → draught 6
        theta_a = math.radians(-2.0)
        theta_b = math.radians(2.0)
        d_a = hull.solve_waterline(0.0, vol, trim_rad=theta_a)
        d_b = hull.solve_waterline(0.0, vol, trim_rad=theta_b)
        self.assertGreater(abs(d_a - d_b), 1e-4,
                           "不对称船体上 ±θ 的平衡 d 应不同（实测 Δd=%.3e）"
                           % abs(d_a - d_b))
        lcb_b = hull.integrate(0.0, d_b, theta_b)["xlcb"]
        out = hull.solve_trim_equilibrium(vol, lcb_b, lcb_tol=1e-6)
        self.assertLess(abs(out["d_m"] - d_b), 1e-3)
        self.assertLess(abs(out["volume_residual_m3"]), out["volume_eq_tol_m3"])


if __name__ == "__main__":
    unittest.main()
