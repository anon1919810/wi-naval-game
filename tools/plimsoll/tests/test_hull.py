# -*- coding: utf-8 -*-
"""Hull 页三项补齐（湿面积 / 长宽比 / 自然航速）：解析对照 + 几何法交叉验证。"""
import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import hull as H    # noqa: E402
import geometry as GE  # noqa: E402
import hydrostatics as HS  # noqa: E402

# ---- 解析方箱：常剖面矩形，型宽 10、型深 7、吃水 5、长 100
B, T, L, DECK = 10.0, 5.0, 100.0, 2.0


def box_hull(nx=3):
    """常剖面方箱船体：剖面 (-B/2, -T) → (B/2, -T) → (B/2, DECK) → (-B/2, DECK)。"""
    poly = [(-B / 2, -T), (B / 2, -T), (B / 2, DECK), (-B / 2, DECK)]
    xs = [L * i / (nx - 1) for i in range(nx)]
    return [(x, list(poly)) for x in xs]


def steamer_hull():
    p = os.path.join(PKG, "cases", "generic_test_steamer_1910.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)["hull"]


class TestFormRatios(unittest.TestCase):
    def test_length_beam_exact(self):
        r = H.form_ratios(steamer_hull())
        self.assertAlmostEqual(r["values"]["length_beam"], 90.0 / 13.0, places=9)

    def test_missing_field_raises(self):
        with self.assertRaises(ValueError):
            H.form_ratios({"beam_m": 13.0, "draught_normal_m": 5.5, "block_coeff": 0.7})


class TestWettedSurface(unittest.TestCase):
    def test_girth_exact_on_box(self):
        """方箱常剖面：每站湿周长 = B + 2T = 20 m（水线闭合边必须扣除），
        沿船长积分 = 20 × 100 = 2000 m²。"""
        h = GE.StationedHull(box_hull(), name="box")
        r = H.wetted_surface_from_hull(h)
        self.assertAlmostEqual(r["values"]["wetted_surface_m2"], 2000.0, places=6)

    def test_waterline_edge_is_excluded(self):
        """若把水线上的闭合边算进去会得到 3000（多出 10×100）—— 专门守住这个坑。"""
        h = GE.StationedHull(box_hull(), name="box")
        r = H.wetted_surface_from_hull(h)
        self.assertNotAlmostEqual(r["values"]["wetted_surface_m2"], 3000.0, places=1)

    def test_refinement_is_stable(self):
        """加密站位不改变结果（常剖面下梯形积分本就精确）。"""
        a = H.wetted_surface_from_hull(GE.StationedHull(box_hull(3)))["values"]["wetted_surface_m2"]
        b = H.wetted_surface_from_hull(GE.StationedHull(box_hull(21)))["values"]["wetted_surface_m2"]
        self.assertAlmostEqual(a, b, places=6)

    def test_parametric_analytic(self):
        """Mumford：S = L·(1.7·T + Cb·B)。方箱 Cb=1 → 100×(8.5+10) = 1850。"""
        r = H.wetted_surface_parametric({"lwl_m": L, "beam_m": B,
                                         "draught_normal_m": T, "block_coeff": 1.0})
        self.assertAlmostEqual(r["values"]["wetted_surface_m2"], 1850.0, places=9)

    def test_parametric_near_geometric_for_steamer(self):
        """同一艘船两个口径应在 ±25% 内 —— 经验式 vs 几何积分的粗校。"""
        hull = steamer_hull()
        pm = H.wetted_surface_parametric(hull)["values"]["wetted_surface_m2"]
        # 用 steamer 的 Cb/B/T 造一个等效的常剖面船体作几何法对照
        poly = [(-hull["beam_m"] / 2, -hull["draught_normal_m"]),
                (hull["beam_m"] / 2, -hull["draught_normal_m"]),
                (hull["beam_m"] / 2, 2.0), (-hull["beam_m"] / 2, 2.0)]
        xs = [0.0, hull["lwl_m"] / 2, hull["lwl_m"]]
        gg = H.wetted_surface_from_hull(GE.StationedHull([(x, list(poly)) for x in xs]))
        gm = gg["values"]["wetted_surface_m2"]
        self.assertTrue(abs(pm - gm) / gm < 0.25,
                        "经验式 %.0f 与几何 %.0f 相差 %.0f%%" % (pm, gm, 100 * (pm - gm) / gm))


class TestNaturalSpeed(unittest.TestCase):
    def test_froude_hull_speed_exact(self):
        """V = √(gL/2π) / 0.514444；L=90 m → 23.03 kn 量级（手算锚）。"""
        r = H.natural_speed(steamer_hull())
        expect = (H.math.sqrt(H.G * 90.0 / (2.0 * H.math.pi))) / H.KNOT_MPS
        self.assertAlmostEqual(r["values"]["hull_speed_kn"], expect, places=9)

    def test_sps_natural_speed_exact(self):
        """V = 1.09·√Lwl(ft)；L=90 m = 295.2756 ft → 18.73 kn 量级。"""
        r = H.natural_speed(steamer_hull())
        expect = 1.09 * H.math.sqrt(90.0 * H.FT_PER_M)
        self.assertAlmostEqual(r["values"]["natural_speed_kn"], expect, places=9)

    def test_sps_constant_flagged_estimate(self):
        """SPS 的 1.09 无公开出处 → 该值必须标 estimate 并带警告。"""
        r = H.natural_speed(steamer_hull())
        t = next(t for t in r["trace"] if t["key"] == "natural_speed_kn")
        self.assertTrue(t["estimate"])
        self.assertTrue(any("无公开文献出处" in w for w in r["warnings"]))

    def test_froude_below_typical_threshold(self):
        """SPS 口径对应的 Fn 应在 0.3 附近（兴波门槛区），不是荒谬值。"""
        r = H.natural_speed(steamer_hull())
        self.assertTrue(0.25 < r["values"]["froude_at_natural"] < 0.40,
                        "Fn=%.3f 不合理" % r["values"]["froude_at_natural"])

    def test_trace_discipline(self):
        for fn in (H.form_ratios, H.natural_speed, H.wetted_surface_parametric):
            for t in fn(steamer_hull())["trace"]:
                self.assertIn("formula", t)
                self.assertIn("source", t)
                self.assertIn("estimate", t)


def wedge_hull(n=21):
    """楔形：半宽自艉 0 线性增到艏 B/2。
    解析：∇ = B·T·L/2 = 2500，Am = 50，Cb = Cp = 0.5，Cm = 1.0，LCB = 66.67，
          半进流角 = atan((B/2)/L) = atan(0.05) = 2.862°。"""
    st = []
    for i in range(n):
        x = L * i / (n - 1)
        hb = (B / 2.0) * (x / L)
        st.append((x, [(-hb, -T), (hb, -T), (hb, DECK), (-hb, DECK)]))
    return GE.StationedHull(st, name="wedge")


def queen_mary_hull():
    import offsets as OF
    tbl, _src, dz = OF.load_offsets_payload(
        os.path.join(PKG, "cases", "queen_mary_1913_offsets.json"))
    return OF.build_hull(tbl, deck_z=dz)


class TestFormCoefficients(unittest.TestCase):
    """船型系数 Cb/Cp/Cm —— 7.3 阻力模型的地基，全部解析锚定。"""

    def test_wedge_matches_analysis(self):
        r = H.form_coefficients(wedge_hull())
        v = r["values"]
        self.assertAlmostEqual(v["volume_m3"], 2500.0, places=6)
        self.assertAlmostEqual(v["midship_area_m2"], 50.0, places=6)
        self.assertAlmostEqual(v["cb"], 0.5, places=6)
        self.assertAlmostEqual(v["cp"], 0.5, places=6)
        self.assertAlmostEqual(v["cm"], 1.0, places=6)
        self.assertAlmostEqual(v["lcb_x_m"], 200.0 / 3.0, delta=0.2)

    def test_box_is_unity(self):
        r = H.form_coefficients(GE.StationedHull(box_hull(), name="box"))
        v = r["values"]
        self.assertAlmostEqual(v["cb"], 1.0, places=9)
        self.assertAlmostEqual(v["cp"], 1.0, places=9)
        self.assertAlmostEqual(v["cm"], 1.0, places=9)
        self.assertAlmostEqual(v["volume_m3"], 5000.0, places=9)
        self.assertAlmostEqual(v["lcb_x_m"], 50.0, places=9)

    def test_cb_equals_cp_times_cm(self):
        """Cb = Cp·Cm 是恒等式：两个形状都该成立（守系数定义不写错）。"""
        for h in (wedge_hull(), GE.StationedHull(box_hull(), name="box")):
            v = H.form_coefficients(h)["values"]
            self.assertAlmostEqual(v["cb"], v["cp"] * v["cm"], places=9)

    def test_empty_waterline_raises(self):
        h = GE.StationedHull(box_hull(), name="box")
        with self.assertRaises(ValueError):
            H.form_coefficients(h, z=50.0)

    def test_queen_mary_anchored(self):
        """∇ = 30943.9 m³（案例记录的模型体积），Cb ≈ 0.5465。"""
        v = H.form_coefficients(queen_mary_hull())["values"]
        self.assertAlmostEqual(v["volume_m3"], 30943.9, delta=1.0)
        self.assertAlmostEqual(v["cb"], 0.5465, delta=0.005)
        self.assertAlmostEqual(v["cb"], v["cp"] * v["cm"], places=9)

    def test_queen_mary_cm_is_low_and_documented(self):
        """⚠️ 模型型线 Cm≈0.71，明显低于战舰常见 0.9+ —— 这是『形状分布未验证』的量化证据。
        型线若被修正，本测试会提醒重新记录（锚值会说话）。"""
        v = H.form_coefficients(queen_mary_hull())["values"]
        self.assertTrue(0.6 < v["cm"] < 0.8,
                        "Cm=%.3f 已不在记录区间：型线是否改过？请复查并重记。" % v["cm"])

    def test_trace_discipline(self):
        for t in H.form_coefficients(wedge_hull())["trace"]:
            self.assertIn("formula", t)
            self.assertIn("source", t)
            self.assertIn("estimate", t)


class TestHalfAngleOfEntrance(unittest.TestCase):
    def forward_wedge(self):
        # x is forward: the original volume fixture narrows toward its stern.
        return GE.StationedHull([(L-x, poly) for x, poly in wedge_hull().stations])

    def test_wedge_exact(self):
        """线性水线：iE = atan(0.05) = 2.862°（与 at_frac 无关，因为斜率恒定）。"""
        r = H.half_angle_of_entrance(self.forward_wedge())
        self.assertAlmostEqual(r["values"]["iE_deg"],
                               math.degrees(math.atan(0.05)), places=6)

    def test_blunt_cut_off_bow_gives_none(self):
        """方箱艏端未收拢 → 取不到角度就返回 None，**不编造**（这是本函数最重要的行为）。"""
        r = H.half_angle_of_entrance(GE.StationedHull(box_hull(), name="box"))
        self.assertIsNone(r["values"]["iE_deg"])
        self.assertTrue(any("不编造" in w for w in r["warnings"]))

    def test_convention_is_declared(self):
        """口径不唯一必须写进警告 —— 跨来源比较前先对齐。"""
        r = H.half_angle_of_entrance(self.forward_wedge())
        self.assertTrue(any("口径" in w for w in r["warnings"]))

    def test_queen_mary_in_plausible_band(self):
        """QM 型线 iE ≈ 27°，落在细瘦船常见区间。"""
        r = H.half_angle_of_entrance(queen_mary_hull())
        self.assertTrue(10.0 < r["values"]["iE_deg"] < 40.0,
                        "iE=%.2f 不合理" % r["values"]["iE_deg"])


class TestWaterlineLength(unittest.TestCase):
    def test_box_exact(self):
        """常剖面方箱：水线长 = 全长 100 m。"""
        h = GE.StationedHull(box_hull(), name="box")
        self.assertAlmostEqual(H.waterline_length(h)["values"]["lwl_at_z_m"], 100.0, places=6)

    def test_tapered_ends_interpolated(self):
        """端部收拢：只在 x=50 有半宽，两端线性插到零 → 25 → 100，长 75。
        （不插值会退化成取整站位置 50，专门守这个坑）"""
        end = [(0.0, -T), (0.0, DECK), (0.0, -1.0)]
        st = [(0.0, list(end)), (25.0, list(end)),
              (50.0, [(-B / 2, -T), (B / 2, -T), (B / 2, DECK), (-B / 2, DECK)]),
              (100.0, list(end))]
        h = GE.StationedHull(st, name="tapered")
        self.assertAlmostEqual(H.waterline_length(h)["values"]["lwl_at_z_m"], 75.0, places=6)

    def test_no_intersection_gives_zero_and_warns(self):
        h = GE.StationedHull(box_hull(), name="box")
        r = H.waterline_length(h, z=50.0)
        self.assertEqual(r["values"]["lwl_at_z_m"], 0.0)
        self.assertTrue(any("无交点" in w for w in r["warnings"]))

    def test_queen_mary_deep_draught_lwl(self):
        """QM 型线 z=0（满载吃水 9.9）→ 213.4 m，比案例『正常吃水』Lwl 212.8 略长（方向自洽）。"""
        import offsets as OF
        tbl, _src, dz = OF.load_offsets_payload(
            os.path.join(PKG, "cases", "queen_mary_1913_offsets.json"))
        hh = OF.build_hull(tbl, deck_z=dz)
        r = H.waterline_length(hh)
        self.assertAlmostEqual(r["values"]["lwl_at_z_m"], 213.4, delta=0.5)
        self.assertTrue(any("口径" in w for w in r["warnings"]))
        self.assertGreater(r["values"]["lwl_at_z_m"], 212.8)

    def test_trace_discipline(self):
        h = GE.StationedHull(box_hull(), name="box")
        for t in H.waterline_length(h)["trace"]:
            self.assertIn("formula", t)
            self.assertIn("source", t)
            self.assertIn("estimate", t)


class TestQueenMarySanity(unittest.TestCase):
    """QM 只是其中一艘船；这里两法交叉校验（经验式 vs 逐站积分）。"""

    @classmethod
    def setUpClass(cls):
        p = os.path.join(PKG, "cases", "queen_mary_1913.json")
        with open(p, encoding="utf-8") as f:
            cls.hull = json.load(f)["hull"]

    def test_length_beam_band(self):
        self.assertAlmostEqual(H.form_ratios(self.hull)["values"]["length_beam"],
                               212.8 / 27.1, places=9)

    def test_two_wetted_surface_methods_agree(self):
        """Mumford 6148.7 vs 逐站积分 6407.9：差 4.2%，应在 10% 内。"""
        pm = H.wetted_surface_parametric(self.hull)["values"]["wetted_surface_m2"]
        import offsets as OF
        tbl, _src, dz = OF.load_offsets_payload(
            os.path.join(PKG, "cases", "queen_mary_1913_offsets.json"))
        hh = OF.build_hull(tbl, deck_z=dz)
        gm = H.wetted_surface_from_hull(hh)["values"]["wetted_surface_m2"]
        self.assertTrue(abs(pm - gm) / gm < 0.10,
                        "两法相差 %.1f%%（经验式 %.0f / 积分 %.0f）" % (100 * (pm - gm) / gm, pm, gm))

    def test_natural_speed_below_froude(self):
        """SPS 口径自然航速必须低于 Froude 兴波速度（否则口径自相矛盾）。"""
        r = H.natural_speed(self.hull)
        self.assertLess(r["values"]["natural_speed_kn"], r["values"]["hull_speed_kn"])


class TestSpsView(unittest.TestCase):
    def test_missing_items_are_none(self):
        v = H.sps_view(length_beam=6.9)
        self.assertIsNone(v["wetted_surface_m2"])
        self.assertIsNone(v["natural_speed_kn"])
        self.assertAlmostEqual(v["length_beam"], 6.9, places=9)


if __name__ == "__main__":
    unittest.main()
