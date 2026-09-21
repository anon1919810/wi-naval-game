"""Plimsoll 阶段 4.2–4.4 + 5.1 测试"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import damage as D          # noqa: E402
import geometry as G         # noqa: E402
import geometric as M        # noqa: E402
import run_damage_scenarios as RDS  # noqa: E402

RHO = 1.025


def make_box(L=100.0, B=20.0, T=5.0, depth=30.0, n=81, bottom_z=-5.0):
    st = []
    for i in range(n):
        x = -0.5 * L + L * i / (n - 1)
        st.append((x, [(B / 2, bottom_z), (B / 2, bottom_z + depth),
                       (-B / 2, bottom_z + depth), (-B / 2, bottom_z)]))
    return G.StationedHull(st, name="box")


class TestIntegrateTrace(unittest.TestCase):

    def test_trace_keys_present(self):
        hull = make_box()
        r = hull.integrate(0.0, 0.0, 0.0)
        self.assertIn("trace", r)
        for k in ("volume", "yb", "zb", "xlcb", "awp"):
            self.assertIn(k, r["trace"])
            self.assertIn("formula", r["trace"][k])
            self.assertIn("source", r["trace"][k])


class TestFloodedEquilibrium(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.hull = make_box()
        cls.vol0 = 100.0 * 20.0 * 5.0
        cls.ship = {
            "displacement_t": cls.vol0 * RHO,
            "kg_m": 4.0,
            "lcg_m": 0.0,
            "lcb_m": 0.0,
        }
        cls.tank = {
            "id": "mid",
            "length_m": 10.0, "beam_m": 8.0, "height_m": 4.0,
            "keel_to_bottom_m": 1.0,
            "x_m": 0.0, "y_m": 0.0,
            "permeability": 1.0,
            "flood_fraction": 0.5,
            "fluid_density_t_m3": RHO,
            "free_surface": True,
        }

    def test_volume_and_trim_self_consistent(self):
        eq = D.solve_flooded_equilibrium(self.hull, self.ship, [self.tank],
                                         rho=RHO, lcb_tol=1e-6)
        self.assertGreater(eq["combination"]["displacement_after_t"],
                           self.ship["displacement_t"])
        self.assertLess(abs(eq["volume_residual_m3"] or 0.0), 1e-3)
        self.assertLess(abs(eq["lcb_residual_m"] or 0.0), 1e-5)
        self.assertLess(abs(eq["trim_rad"]), 1e-3)
        self.assertIsNotNone(eq["km_m"])
        self.assertIsNotNone(eq["gm_m"])

    def test_asymmetric_flood_induces_trim_sign(self):
        tank = dict(self.tank, id="bow", x_m=20.0)
        eq = D.solve_flooded_equilibrium(self.hull, self.ship, [tank],
                                         rho=RHO, lcb_tol=1e-6)
        # 艏部增重 → LCG>0 → 艏倾 θ>0
        self.assertGreater(eq["trim_rad"], 0.0)
        self.assertGreater(eq["target_lcg_m"], 0.0)

    def test_remaining_gz_fields(self):
        eq = D.solve_flooded_equilibrium(self.hull, self.ship, [self.tank],
                                         rho=RHO, lcb_tol=1e-6)
        gz = D.remaining_gz_curve(self.hull, eq["kg_effective_m"],
                                  eq["target_volume_m3"])
        self.assertGreater(gz["max_gz_m"], 0.0)
        self.assertGreater(gz["range_deg"], 0.0)
        self.assertTrue(gz["rows"])
        self.assertIn("estimate", gz)

    def test_gz_reduced_when_flood_raises_kg(self):
        eq = D.solve_flooded_equilibrium(self.hull, self.ship, [self.tank],
                                         rho=RHO, lcb_tol=1e-6)
        gz_flood = D.remaining_gz_curve(self.hull, eq["kg_effective_m"],
                                        eq["target_volume_m3"])
        gz_ref = D.remaining_gz_curve(self.hull, 4.0, eq["target_volume_m3"])
        self.assertLess(gz_flood["max_gz_m"], gz_ref["max_gz_m"] + 1e-9)


class TestScenarios(unittest.TestCase):

    def test_three_scenarios_reproducible(self):
        path = os.path.join(os.path.dirname(HERE),
                            "cases", "damage_scenarios.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        hull = RDS.load_hull(data["hull"])
        ship = data["ship_baseline"]
        outs = []
        for sc in data["scenarios"]:
            a = D.run_damage_scenario(hull, {"id": sc["id"], "ship": ship,
                                             "tanks": sc["tanks"]})
            b = D.run_damage_scenario(hull, {"id": sc["id"], "ship": ship,
                                             "tanks": sc["tanks"]})
            self.assertEqual(a["equilibrium"]["trim_rad"],
                             b["equilibrium"]["trim_rad"])
            self.assertEqual(a["remaining_gz"]["max_gz_m"],
                             b["remaining_gz"]["max_gz_m"])
            self.assertIn("stable", a)
            outs.append(a)
        self.assertEqual(len(outs), 3)
        self.assertEqual([o["id"] for o in outs],
                         ["single_boiler", "double_boiler", "engine_room"])

    def test_engine_room_heel_sign(self):
        path = os.path.join(os.path.dirname(HERE),
                            "cases", "damage_scenarios.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        hull = RDS.load_hull(data["hull"])
        sc = next(s for s in data["scenarios"] if s["id"] == "engine_room")
        eq = D.solve_flooded_equilibrium(hull, data["ship_baseline"], sc["tanks"])
        self.assertGreater(eq["tcg_flood_m"], 0.0)
        if eq["heel_deg"] is not None:
            self.assertGreater(eq["heel_deg"], 0.0)


class TestPackageImport(unittest.TestCase):

    def test_import_plimsoll_callables(self):
        tools_dir = os.path.dirname(HERE)
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        import plimsoll
        self.assertTrue(hasattr(plimsoll, "damage"))
        self.assertTrue(hasattr(plimsoll.damage, "solve_flooded_equilibrium"))
        self.assertTrue(hasattr(plimsoll.damage, "flood_combination"))
        self.assertTrue(hasattr(plimsoll, "geometry"))
        self.assertTrue(hasattr(plimsoll.geometry, "StationedHull"))
        # 真正可调用，而不只是模块名存在
        hull = make_box()
        out = plimsoll.damage.flood_combination(
            {"displacement_t": 1000.0, "kg_m": 5.0}, [])
        self.assertAlmostEqual(out["kg_effective_m"], 5.0, places=12)


class TestFSCOnce(unittest.TestCase):

    def test_double_count_raises(self):
        hull = make_box()
        kg_solid = 4.0
        vol = 100.0 * 20.0 * 5.0
        tank = {"id": "t", "length_m": 10.0, "beam_m": 8.0, "height_m": 4.0,
                "permeability": 1.0, "flood_fraction": 0.5,
                "fluid_density_t_m3": RHO}
        with self.assertRaises(ValueError):
            D.remaining_gz_curve(hull, kg_solid + 0.1, vol,
                                 free_surface_tanks=[tank],
                                 fsc_already_in_kg=True)

    def test_scenario_gz_has_no_implicit_fs_tanks(self):
        path = os.path.join(os.path.dirname(HERE),
                            "cases", "damage_scenarios.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        hull = RDS.load_hull(data["hull"])
        sc = data["scenarios"][0]
        out = D.run_damage_scenario(hull, {
            "id": sc["id"], "ship": data["ship_baseline"], "tanks": sc["tanks"],
        })
        self.assertTrue(out["remaining_gz"]["fsc_already_in_kg"])
        # kg_eff 含 FSC；GZ 层不得再叠 tanks（rows 里 fsc_m 若存在应为 0/缺省）
        for row in out["remaining_gz"]["rows"]:
            if "fsc_m" in row:
                self.assertEqual(row["fsc_m"], 0.0)

    def test_mapped_tanks_with_solid_kg(self):
        """显式路径：实心 KG + 映射后的 tanks → GZ 层 FS 生效。"""
        hull = make_box()
        vol = 100.0 * 20.0 * 5.0
        tanks = [{"id": "t", "length_m": 20.0, "beam_m": 10.0,
                  "height_m": 4.0, "flood_fraction": 0.5,
                  "fluid_density_t_m3": 1.0}]
        fs_tanks = D.flood_tanks_to_fs_tanks(tanks)
        self.assertEqual(fs_tanks[0]["fill_fraction"], 0.5)
        gz_solid = D.remaining_gz_curve(hull, 4.0, vol)
        gz_fs = D.remaining_gz_curve(hull, 4.0, vol,
                                     free_surface_tanks=fs_tanks,
                                     fsc_already_in_kg=False)
        self.assertLess(gz_fs["max_gz_m"], gz_solid["max_gz_m"])


if __name__ == "__main__":
    unittest.main()
