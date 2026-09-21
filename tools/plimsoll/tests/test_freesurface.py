"""Plimsoll · 阶段 3 自由液面修正测试

验收锚：
  1. 矩形舱 i = L·b³/12 与 FSC = Σ(ρi·i)/Δ 闭式解
  2. 空/满舱不计自由液面
  3. GZ 接入后 GM/GZ 按 FSC 下降，且等于用 KG+FSC 算出的对照
"""

import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import freesurface as FS     # noqa: E402
import geometric as M         # noqa: E402
import geometry as G          # noqa: E402

RHO = 1.025


def make_box(L, B, T, depth, n=81, bottom_z=0.0):
    st = []
    for i in range(n):
        x = -0.5 * L * math.cos(math.pi * i / (n - 1))
        st.append((x, [(B / 2, bottom_z), (B / 2, bottom_z + depth),
                       (-B / 2, bottom_z + depth), (-B / 2, bottom_z)]))
    return G.StationedHull(st, name="box")


class TestTankInertia(unittest.TestCase):

    def test_rectangular_closed_form(self):
        row = FS.tank_free_surface_inertia({
            "id": "A", "length_m": 20.0, "beam_m": 10.0,
            "fluid_density_t_m3": 1.0, "fill_fraction": 0.5,
        })
        expect = 20.0 * (10.0 ** 3) / 12.0
        self.assertAlmostEqual(row["i_m4"], expect, places=9)
        self.assertAlmostEqual(row["i_effective_m4"], expect, places=9)
        self.assertTrue(row["active"])

    def test_empty_and_full_inactive(self):
        for fill in (0.0, 1.0, -0.2, 1.5):
            row = FS.tank_free_surface_inertia({
                "length_m": 20.0, "beam_m": 10.0, "fill_fraction": fill,
            })
            self.assertFalse(row["active"], "fill=%r 不应计自由液面" % fill)
            self.assertEqual(row["i_effective_m4"], 0.0)

    def test_zero_beam_inactive_zero_i(self):
        row = FS.tank_free_surface_inertia({
            "length_m": 20.0, "beam_m": 0.0, "fill_fraction": 0.4,
        })
        self.assertFalse(row["active"])
        self.assertEqual(row["i_effective_m4"], 0.0)

    def test_invalid_inputs_raise(self):
        with self.assertRaises(ValueError):
            FS.tank_free_surface_inertia({"length_m": 0.0, "beam_m": 5.0})
        with self.assertRaises(ValueError):
            FS.tank_free_surface_inertia({"length_m": 5.0, "beam_m": -1.0})
        with self.assertRaises(ValueError):
            FS.tank_free_surface_inertia({"length_m": 5.0, "beam_m": 2.0,
                                          "fluid_density_t_m3": -1.0})


class TestFSCSum(unittest.TestCase):

    def test_single_tank_matches_formula(self):
        tank = {"length_m": 20.0, "beam_m": 10.0,
                "fluid_density_t_m3": 1.025, "fill_fraction": 0.6}
        i = 20.0 * 1000.0 / 12.0
        delta = 25000.0
        expect = 1.025 * i / delta
        out = FS.free_surface_correction([tank], delta)
        self.assertAlmostEqual(out["fsc_m"], expect, places=9)
        self.assertEqual(out["n_active"], 1)

    def test_two_tanks_sum_linearly(self):
        t1 = {"id": "a", "length_m": 20.0, "beam_m": 10.0,
              "fluid_density_t_m3": 1.0, "fill_fraction": 0.5}
        t2 = {"id": "b", "length_m": 10.0, "beam_m": 8.0,
              "fluid_density_t_m3": 1.025, "fill_fraction": 0.3}
        delta = 20000.0
        i1 = 20.0 * 10 ** 3 / 12.0
        i2 = 10.0 * 8 ** 3 / 12.0
        expect = (1.0 * i1 + 1.025 * i2) / delta
        out = FS.free_surface_correction([t1, t2], delta)
        self.assertAlmostEqual(out["fsc_m"], expect, places=9)
        self.assertEqual(out["n_active"], 2)
        self.assertAlmostEqual(out["sum_rho_i"], 1.0 * i1 + 1.025 * i2, places=9)

    def test_full_tank_contributes_zero(self):
        t_full = {"length_m": 20.0, "beam_m": 10.0, "fill_fraction": 1.0}
        t_part = {"length_m": 20.0, "beam_m": 10.0,
                  "fluid_density_t_m3": 1.0, "fill_fraction": 0.5}
        delta = 10000.0
        expect = (20.0 * 1000.0 / 12.0) / delta  # only partial, rho=1
        out = FS.free_surface_correction([t_full, t_part], delta)
        self.assertAlmostEqual(out["fsc_m"], expect, places=9)
        self.assertEqual(out["n_active"], 1)

    def test_zero_displacement_raises(self):
        tank = {"length_m": 20.0, "beam_m": 10.0, "fill_fraction": 0.5}
        with self.assertRaises(ValueError):
            FS.free_surface_correction([tank], 0.0)
        with self.assertRaises(ValueError):
            FS.free_surface_correction([tank], -1.0)

    def test_fsc_nonnegative(self):
        tank = {"length_m": 15.0, "beam_m": 6.0,
                "fluid_density_t_m3": 1.025, "fill_fraction": 0.4}
        out = FS.free_surface_correction([tank], 30000.0)
        self.assertGreaterEqual(out["fsc_m"], 0.0)


class TestApplyFSC(unittest.TestCase):

    def test_kg_eff_and_gm_delta(self):
        out = FS.apply_fsc(8.6, 0.25)
        self.assertAlmostEqual(out["kg_effective_m"], 8.85, places=12)
        self.assertAlmostEqual(out["gm_delta_m"], -0.25, places=12)

    def test_negative_fsc_raises(self):
        with self.assertRaises(ValueError):
            FS.apply_fsc(8.0, -0.1)


class TestGZWithFSC(unittest.TestCase):
    """3.2：GZ 用 KG+FSC；应与手工改 kg 的未接入路径一致。"""

    L, B, T, DEPTH = 100.0, 20.0, 5.0, 30.0
    KG = 4.0

    @classmethod
    def setUpClass(cls):
        cls.hull = make_box(cls.L, cls.B, cls.T, cls.DEPTH)
        cls.vol = cls.L * cls.B * cls.T
        cls.tank = {
            "id": "flood", "length_m": 30.0, "beam_m": 12.0,
            "fluid_density_t_m3": RHO, "fill_fraction": 0.55,
        }
        cls.fsc = FS.free_surface_correction(
            [cls.tank], cls.vol * RHO)["fsc_m"]

    def test_fsc_positive_for_partial_tank(self):
        self.assertGreater(self.fsc, 0.0)

    def test_gz_matches_manual_kg_plus_fsc(self):
        rows_fsc = M.gz_curve(self.hull, self.KG, self.vol,
                              [10.0, 20.0, 30.0],
                              free_surface_tanks=[self.tank])
        rows_ref = M.gz_curve(self.hull, self.KG + self.fsc, self.vol,
                              [10.0, 20.0, 30.0])
        for a, b in zip(rows_fsc, rows_ref):
            self.assertAlmostEqual(a["gm_arm_m"], b["gm_arm_m"], places=9)
            self.assertAlmostEqual(a["fsc_m"], self.fsc, places=12)
            self.assertAlmostEqual(a["kg_effective_m"], self.KG + self.fsc,
                                   places=12)

    def test_gz_reduced_vs_no_fsc(self):
        rows0 = M.gz_curve(self.hull, self.KG, self.vol, [10.0, 20.0, 30.0])
        rows1 = M.gz_curve(self.hull, self.KG, self.vol, [10.0, 20.0, 30.0],
                           free_surface_tanks=[self.tank])
        for a, b in zip(rows0, rows1):
            self.assertLess(b["gm_arm_m"], a["gm_arm_m"] + 1e-12)
            # 小角度差约 FSC·sinφ
            phi = math.radians(a["angle_deg"])
            drop = a["gm_arm_m"] - b["gm_arm_m"]
            self.assertLess(abs(drop - self.fsc * math.sin(phi)), 1e-9)

    def test_default_behavior_unchanged_without_tanks(self):
        rows = M.gz_curve(self.hull, self.KG, self.vol, [5.0])
        self.assertNotIn("fsc_m", rows[0])
        self.assertNotIn("kg_effective_m", rows[0])


class TestL0GMDelta(unittest.TestCase):
    """对照：GM_eff = GM − FSC（不改 L0 核心，只验公式一致性）。"""

    def test_gm_delta_equals_fsc(self):
        tank = {"length_m": 25.0, "beam_m": 9.0,
                "fluid_density_t_m3": 1.025, "fill_fraction": 0.5}
        fsc = FS.free_surface_correction([tank], 26780.0)["fsc_m"]
        gm0, kg, km = 4.81, 8.6, 13.41
        gm1 = km - (kg + fsc)
        self.assertAlmostEqual(gm0 - gm1, fsc, places=12)
        self.assertAlmostEqual(FS.apply_fsc(kg, fsc)["gm_delta_m"], -fsc,
                               places=12)


if __name__ == "__main__":
    unittest.main()
