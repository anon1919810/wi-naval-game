"""Plimsoll · 阶段 4.1 进水组合模型测试"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import damage as D  # noqa: E402


class TestFloodTankState(unittest.TestCase):

    def test_analytical_weight_and_kg(self):
        tank = {
            "id": "A",
            "length_m": 10.0, "beam_m": 8.0, "height_m": 4.0,
            "keel_to_bottom_m": 2.0,
            "permeability": 0.8,
            "flood_fraction": 0.5,
            "fluid_density_t_m3": 1.0,
            "x_m": 5.0, "y_m": 0.0,
        }
        row = D.flood_tank_state(tank)
        v_tank = 10 * 8 * 4
        v_flood = 0.8 * 0.5 * v_tank
        self.assertAlmostEqual(row["volume_tank_m3"], v_tank, places=9)
        self.assertAlmostEqual(row["volume_flood_m3"], v_flood, places=9)
        self.assertAlmostEqual(row["added_displacement_t"], 1.0 * v_flood, places=9)
        self.assertAlmostEqual(row["kg_flood_m"], 2.0 + 0.5 * 4.0, places=9)
        self.assertTrue(row["free_surface_active"])
        self.assertAlmostEqual(row["i_effective_m4"], 10.0 * 8.0 ** 3 / 12.0, places=9)

    def test_zero_flood_no_weight_no_fs(self):
        row = D.flood_tank_state({
            "length_m": 10, "beam_m": 8, "height_m": 4,
            "flood_fraction": 0.0,
        })
        self.assertEqual(row["added_displacement_t"], 0.0)
        self.assertFalse(row["free_surface_active"])

    def test_full_flood_weight_but_no_fs(self):
        row = D.flood_tank_state({
            "length_m": 10, "beam_m": 8, "height_m": 4,
            "permeability": 1.0, "flood_fraction": 1.0,
            "fluid_density_t_m3": 1.025,
        })
        self.assertAlmostEqual(row["added_displacement_t"],
                               1.025 * 10 * 8 * 4, places=9)
        self.assertFalse(row["free_surface_active"])

    def test_permeability_zero_no_water(self):
        row = D.flood_tank_state({
            "length_m": 10, "beam_m": 8, "height_m": 4,
            "permeability": 0.0, "flood_fraction": 0.7,
        })
        self.assertEqual(row["added_displacement_t"], 0.0)

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            D.flood_tank_state({"length_m": 0, "beam_m": 1, "height_m": 1})
        with self.assertRaises(ValueError):
            D.flood_tank_state({"length_m": 1, "beam_m": 1, "height_m": 1,
                                "permeability": 1.5})
        with self.assertRaises(ValueError):
            D.flood_tank_state({"length_m": 1, "beam_m": 1, "height_m": 1,
                                "flood_fraction": 2.0})


class TestFloodCombination(unittest.TestCase):

    def test_two_tanks_hand_calc(self):
        ship = {"displacement_t": 1000.0, "kg_m": 5.0, "km_m": 8.0}
        t1 = {
            "id": "a", "length_m": 10.0, "beam_m": 4.0, "height_m": 5.0,
            "keel_to_bottom_m": 1.0,
            "permeability": 1.0, "flood_fraction": 0.4,
            "fluid_density_t_m3": 1.0, "x_m": 20.0,
        }
        t2 = {
            "id": "b", "length_m": 8.0, "beam_m": 6.0, "height_m": 5.0,
            "keel_to_bottom_m": 1.0,
            "permeability": 0.5, "flood_fraction": 0.5,
            "fluid_density_t_m3": 1.025, "x_m": -10.0,
            "free_surface": False,
        }
        # hand calc
        d1 = 1.0 * 1.0 * 0.4 * 10 * 4 * 5  # 80
        kg1 = 1.0 + 0.4 * 5  # 3.0
        d2 = 1.025 * 0.5 * 0.5 * 8 * 6 * 5  # 61.5
        kg2 = 1.0 + 0.5 * 5  # 3.5
        d_sum = d1 + d2
        d_tot = 1000.0 + d_sum
        kg_s = (1000.0 * 5.0 + d1 * kg1 + d2 * kg2) / d_tot
        i1 = 10.0 * 4.0 ** 3 / 12.0
        fsc = (1.0 * i1) / d_tot  # t2 FS off
        kg_e = kg_s + fsc
        gm = 8.0 - kg_e

        out = D.flood_combination(ship, [t1, t2])
        self.assertAlmostEqual(out["added_displacement_t"], d_sum, places=9)
        self.assertAlmostEqual(out["displacement_after_t"], d_tot, places=9)
        self.assertAlmostEqual(out["kg_solid_m"], kg_s, places=9)
        self.assertAlmostEqual(out["fsc_m"], fsc, places=9)
        self.assertAlmostEqual(out["kg_effective_m"], kg_e, places=9)
        self.assertAlmostEqual(out["gm_m"], gm, places=9)
        self.assertEqual(out["n_tanks"], 2)

    def test_empty_tanks_identity(self):
        out = D.flood_combination({"displacement_t": 26780.0, "kg_m": 8.6,
                                   "km_m": 13.41}, [])
        self.assertEqual(out["added_displacement_t"], 0.0)
        self.assertAlmostEqual(out["kg_effective_m"], 8.6, places=12)
        self.assertEqual(out["fsc_m"], 0.0)
        self.assertAlmostEqual(out["gm_m"], 13.41 - 8.6, places=12)

    def test_fsc_uses_displacement_after(self):
        """FSC 分母必须是 Δ'，若误用 Δ 则数值不同 → 本测试钉死。"""
        ship = {"displacement_t": 1000.0, "kg_m": 4.0}
        tank = {
            "length_m": 20.0, "beam_m": 10.0, "height_m": 6.0,
            "permeability": 1.0, "flood_fraction": 0.5,
            "fluid_density_t_m3": 1.025,
        }
        out = D.flood_combination(ship, [tank])
        d_flood = 1.025 * 0.5 * 20 * 10 * 6
        d_tot = 1000.0 + d_flood
        i = 20.0 * 1000.0 / 12.0
        expect = (1.025 * i) / d_tot
        wrong = (1.025 * i) / 1000.0
        self.assertAlmostEqual(out["fsc_m"], expect, places=9)
        self.assertNotAlmostEqual(out["fsc_m"], wrong, places=6)

    def test_kg_rises_with_flood_weight_high(self):
        ship = {"displacement_t": 1000.0, "kg_m": 4.0}
        high = {
            "length_m": 5, "beam_m": 5, "height_m": 2,
            "keel_to_bottom_m": 12.0,
            "permeability": 1.0, "flood_fraction": 0.6,
            "fluid_density_t_m3": 1.0, "free_surface": False,
        }
        out = D.flood_combination(ship, [high])
        self.assertGreater(out["kg_solid_m"], 4.0)

    def test_invalid_ship_raises(self):
        with self.assertRaises(ValueError):
            D.flood_combination({"displacement_t": 0, "kg_m": 5}, [])
        with self.assertRaises(ValueError):
            D.flood_combination({"kg_m": 5}, [])


if __name__ == "__main__":
    unittest.main()
