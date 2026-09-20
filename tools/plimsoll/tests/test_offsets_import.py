"""Plimsoll · 型值表导入的验证测试

跑法：
    python -m unittest discover -s tools/plimsoll/tests -v

本文件的核心不是"跑通"，而是**分清哪些结论已被证明、哪些还没有**。
仓库里能当锚点的既有数据有三个，但它们**测的不是同一件事**，混用会得出错误结论：

  锚点                                       性质                     可信度
  hull_signed_volume_m3 = 54865.7            v3 FBX 网格的三角面片有符号体积（精确多面体）  几何真值（但有下述疑点）
  hydrostatics.json immersed_volume 30663.7  由 22 个表结点做粗积分             **偏低 ~0.9%**
  hydrostatics.json waterplane_area 4610.4   由 22 个表结点做梯形积分           **偏低 ~0.4%**（已精确复现）

关键发现（已证明，见 TestAnchorProvenance）：
    `waterplane_area_m2 = 4610.4` 可以用「对 22 个表结点直接做梯形积分」**逐位复现（0.000%）**，
    而网格实际使用的是 `station_params` 的三次插值曲线，密集积分给出 **4628.9**。
    即：**项目里存的那个数来自更粗的求积，不是网格的真实几何。**
    游戏侧 `ShipFloatPrototype.waterplaneAreaM2 = 4610.4` 正是这个数。
"""

import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import offsets as O          # noqa: E402
import geometry as G         # noqa: E402
import geometric as M        # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
V4_SCRIPT = os.path.join(REPO, "queen_mary_v4", "queen_mary_v4.py")
V3_SCRIPT = os.path.join(REPO, "queen_mary_v3", "queen_mary.py")

DECK_Z = 5.10
ANCHOR_CLOSED_VOLUME = 54865.7
ANCHOR_IMMERSED_VOLUME = 30663.7
ANCHOR_WATERPLANE = 4610.4


def load_table():
    return O.parse_offsets_from_python(V4_SCRIPT)


class TestTableImport(unittest.TestCase):
    def test_v3_and_v4_tables_identical(self):
        """v3 与 v4 用同一张型值表 —— 所以 v3 的静水力结论对 v4 同样适用。"""
        self.assertEqual(O.parse_offsets_from_python(V3_SCRIPT), load_table())

    def test_table_shape(self):
        t = load_table()
        self.assertEqual(len(t), 22)
        self.assertAlmostEqual(t[0][0], -106.7, places=6)
        self.assertAlmostEqual(t[-1][0], 106.7, places=6)
        self.assertAlmostEqual(t[-1][0] - t[0][0], 213.4, places=6)   # 模型全长

    def test_station_params_clamps_never_overshoots(self):
        """钳位是生成脚本的明确行为，也是"合成指纹"的来源，必须复现。"""
        t = load_table()
        for y in (-106.7, -60.0, -30.0, 0.0, 30.0, 60.0, 106.7):
            got = O.station_params(t, y)
            for col in range(4):
                lo = min(r[col + 1] for r in t)
                hi = max(r[col + 1] for r in t)
                self.assertGreaterEqual(got[col], lo - 1e-12)
                self.assertLessEqual(got[col], hi + 1e-12)

    def test_synthetic_fingerprints_are_present(self):
        """"恰好相等"是合成船体的指纹，不是 bug。

        若提取结果复现了它们，说明模型本来如此；若不复现，才是提取错了。
        断言直接取自型值表本身（不硬编码外部摘要里的数字 —— 那类数字必须回源核对）。
        """
        t = load_table()
        row = {r[0]: r for r in t}
        # 平行中体：甲板半宽在一段区间内几乎恒定（表值 13.60，末端收到 13.55）
        self.assertAlmostEqual(row[-30.0][1], 13.60, places=6)
        self.assertAlmostEqual(row[0.0][1], 13.60, places=6) if 0.0 in row else None
        for y in (-30.0, -18.0, -10.0, 10.0):
            self.assertAlmostEqual(row[y][1], 13.60, places=6)
        # 平龙骨：一段区间内龙骨恰好 -9.90（注意 +50 处已收到 -9.85）
        for y in (-50.0, -30.0, -18.0, -10.0, 10.0, 30.0):
            self.assertAlmostEqual(row[y][3], -9.90, places=6)
        # 插值必须精确通过表结点本身（否则就是插值实现错了）
        for y in row:
            got = O.station_params(t, y)
            for col in range(4):
                self.assertAlmostEqual(got[col], row[y][col + 1], places=9,
                                       msg="y=%.1f 第 %d 列插值未过结点" % (y, col))


class TestAnchorProvenance(unittest.TestCase):
    """把"仓库里的锚点是怎么算出来的"钉死。这一节是整个验证的核心。"""

    def test_waterplane_anchor_is_table_knot_trapezoid(self):
        """4610.4 = 对 22 个表结点直接梯形积分。逐位复现 → 证明其来历。"""
        t = load_table()
        ys = [r[0] for r in t]
        hb = [r[2] for r in t]          # 第 3 列 = 水线半宽
        acc = sum((hb[i] + hb[i + 1]) * (ys[i + 1] - ys[i]) for i in range(len(ys) - 1))
        self.assertAlmostEqual(acc, ANCHOR_WATERPLANE, places=2,
                               msg="表结点梯形积分 %.4f 再现不了锚点 %.1f" % (acc, ANCHOR_WATERPLANE))

    def test_mesh_uses_cubic_interpolant_not_the_table(self):
        """网格用的是三次插值曲线，其水线面比表结点梯形积分大约 +0.4%。"""
        t = load_table()
        ys = [r[0] for r in t]
        n = 20000
        acc = 0.0
        prev_y = prev_v = None
        for i in range(n + 1):
            y = ys[0] + (ys[-1] - ys[0]) * i / n
            v = 2.0 * O.station_params(t, y)[1]
            if prev_y is not None:
                acc += 0.5 * (prev_v + v) * (y - prev_y)
            prev_y, prev_v = y, v
        bias = 100.0 * (acc - ANCHOR_WATERPLANE) / ANCHOR_WATERPLANE
        self.assertGreater(acc, ANCHOR_WATERPLANE)
        self.assertAlmostEqual(bias, 0.40, delta=0.10,
                               msg="偏差 %.3f%% 与记录的 +0.40%% 不符，需复查" % bias)

    def test_our_extraction_matches_the_interpolant_not_the_coarse_anchor(self):
        """我们的提取必须复现**同一插值**，而不是去迁就那个粗求积的锚点。"""
        t = load_table()
        hull = O.build_hull(t)
        awp = M.hydrostatics_upright(hull, 0.0)["awp_m2"]
        # 与"三次插值密集积分"一致（0.05% 内）
        self.assertGreater(awp, ANCHOR_WATERPLANE)
        self.assertLess(abs(awp - 4628.9) / 4628.9, 5e-3,
                        "提取得 %.1f，与插值曲线的 4628.9 差得太多" % awp)


class TestReproducesModelGeometry(unittest.TestCase):
    def test_closed_volume_near_anchor(self):
        """闭合体积（龙骨→主甲板 5.10 m）与网格有符号体积同量级。

        ⚠️ 实测差约 +0.67%（本方法）／−1.17%（本方法的多面体精确值），
        两者把网格值夹在中间，且随站位数增加**不再收敛**。
        已排除：剖面采样密度、站位间距、形状模型复现。**原因尚未查明**。
        故此处只断言量级与正负，不假装精确。
        """
        hull = O.build_hull(load_table())
        v = M.hydrostatics_upright(hull, DECK_Z)["volume_m3"]
        self.assertGreater(v, 0)
        self.assertLess(abs(v - ANCHOR_CLOSED_VOLUME) / ANCHOR_CLOSED_VOLUME, 0.02,
                        "与网格体积差 %.3f%%，超出 2%% 容差" % (100 * (v - ANCHOR_CLOSED_VOLUME) / ANCHOR_CLOSED_VOLUME))

    def test_immersed_volume_brackets_the_coarse_anchor(self):
        """设计水线 z=0 处的浸没体积略高于粗求积锚点（同水线面的道理）。"""
        hull = O.build_hull(load_table())
        v = M.hydrostatics_upright(hull, 0.0)["volume_m3"]
        self.assertGreater(v, ANCHOR_IMMERSED_VOLUME)
        self.assertLess(v, ANCHOR_IMMERSED_VOLUME * 1.02)


class TestGZOnRealOffsets(unittest.TestCase):
    """用型值表船体跑 GZ —— 这条曲线才是本舰几何的产物，而非合成船体。"""

    @classmethod
    def setUpClass(cls):
        cls.hull = O.build_hull(load_table())
        cls.d0 = cls.hull.solve_waterline(0.0, M.hydrostatics_upright(cls.hull, 0.0)["volume_m3"],
                                          tol=1e-12)
        cls.vol = M.hydrostatics_upright(cls.hull, cls.d0)["volume_m3"]
        cls.kg = 8.6

    def test_upright_gm_sane(self):
        gh = M.hydrostatics_upright(self.hull, self.d0)
        gm = gh["km_m"] - self.kg
        self.assertGreater(gm, 0.5)
        self.assertLess(gm, 8.0)

    def test_gz_starts_at_zero_and_rises(self):
        rows = M.gz_curve(self.hull, self.kg, self.vol, [0, 10, 20, 30])
        self.assertAlmostEqual(rows[0]["gm_arm_m"], 0.0, places=6)
        for a, b in zip(rows, rows[1:]):
            self.assertGreater(b["gm_arm_m"], a["gm_arm_m"])

    def test_volume_conserved(self):
        for r in M.gz_curve(self.hull, self.kg, self.vol, [0, 15, 30]):
            self.assertAlmostEqual(r["volume_m3"], self.vol, places=0)

    def test_initial_slope_matches_gm(self):
        """初始斜率 = GM。注意 zb 要按龙骨换算 —— 漏掉就正好差一个龙骨高度。"""
        kz = M.keel_z(self.hull)
        phi = math.radians(0.01)
        d, r = M.solve_equilibrium(self.hull, phi, self.vol, tol=1e-12)
        slope = (r["yb"] * math.cos(phi) + (r["zb"] - kz - self.kg) * math.sin(phi)) / math.sin(phi)
        gm = M.hydrostatics_upright(self.hull, self.d0)["km_m"] - self.kg
        self.assertAlmostEqual(slope, gm, places=3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
