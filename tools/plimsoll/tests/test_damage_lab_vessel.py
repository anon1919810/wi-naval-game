"""The visual demo must be a declared vessel and run on its own actual offsets."""
import copy
import json
from pathlib import Path
import unittest

from tools.plimsoll.damage_lab import normalize_request, run_experiment

CASES = Path(__file__).resolve().parents[1] / "cases/damage_lab"


def section_at(stations, x):
    for (xa, a), (xb, b) in zip(stations, stations[1:]):
        if xa - 1e-9 <= x <= xb + 1e-9:
            fraction = (x - xa) / (xb - xa)
            return [[u + (v-u)*fraction for u, v in zip(pa, pb)] for pa, pb in zip(a, b)]
    raise AssertionError(f"Room end {x} is outside the hull")


def inside_convex(polygon, y, z):
    cross = [(b[0]-a[0])*(z-a[1]) - (b[1]-a[1])*(y-a[0])
             for a, b in zip(polygon, polygon[1:] + polygon[:1])]
    return min(cross) >= -1e-8 or max(cross) <= 1e-8


class DamageLabVesselTests(unittest.TestCase):
    def setUp(self):
        for filename in ("synthetic-vessel.project.json", "synthetic-vessel.experiment.json"):
            self.assertTrue((CASES / filename).is_file(), f"New canonical vessel fixture missing: {filename}")
        self.project = json.loads((CASES / "synthetic-vessel.project.json").read_text(encoding="utf-8"))
        self.experiment = json.loads((CASES / "synthetic-vessel.experiment.json").read_text(encoding="utf-8"))

    def test_vessel_has_declared_bow_stern_bilge_deck_and_keel(self):
        hull, geometry = self.project["hull"], self.project["geometry"]
        self.assertEqual([hull[k] for k in ("lwl_m", "beam_m", "depth_m")], [36, 8, 5.5])
        self.assertTrue(geometry["estimate"])
        self.assertIn("synthetic", str(geometry["source"]).lower())
        stations = geometry["offsets"]["stations"]
        self.assertGreaterEqual(len(stations), 21)
        self.assertEqual(stations[-1][0] - stations[0][0], 36)
        mid = min(stations, key=lambda station: abs(station[0]))[1]
        width = lambda points: max(p[0] for p in points) - min(p[0] for p in points)
        self.assertAlmostEqual(width(mid), 8)
        self.assertLess(width(stations[-1][1]), .1)
        self.assertLess(width(stations[0][1]), width(mid)*.7)
        self.assertGreater(min(p[1] for p in stations[0][1]), min(p[1] for p in mid))
        self.assertGreater(min(p[1] for p in stations[-1][1]), min(p[1] for p in mid))
        self.assertGreater(len({p[1] for p in mid}), 4)
        self.assertEqual(max(p[1] for p in mid), 5.5)
        self.assertEqual(min(p[1] for p in mid), 0)
        for _, points in stations:
            self.assertEqual(len(points), len(mid))
            self.assertEqual(len({tuple(p) for p in points}), len(points))
            area = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(points, points[1:] + points[:1]))/2
            self.assertGreater(area, 0)

    def test_rectangular_rooms_fit_the_canonical_vessel_profiles(self):
        stations = self.project["geometry"]["offsets"]["stations"]
        for room in self.project["compartments"]:
            start, end = [room["x_m"] + sign*room["length_m"]/2 for sign in (-1, 1)]
            sample_x = [start, end] + [x for x, _ in stations if start <= x <= end]
            for x in sample_x:
                profile = section_at(stations, x)
                for y in (room["y_m"]-room["beam_m"]/2, room["y_m"]+room["beam_m"]/2):
                    for z in (room["keel_to_bottom_m"], room["keel_to_bottom_m"]+room["height_m"]):
                        self.assertTrue(inside_convex(profile, y, z), (room["id"], x, y, z))
        # Real request admission also checks the equipment and crew station bounds.
        normalize_request(self.project, "normal", self.experiment)

    def test_vessel_dry_equilibrium_uses_the_declared_hull_without_invented_damage(self):
        experiment = copy.deepcopy(self.experiment)
        experiment.update(duration_s=0, breaches=[])
        experiment["impact"]["severity"] = 0
        result = run_experiment(self.project, "normal", experiment)
        self.assertEqual(result["status"], "completed")
        ship = result["final_state"]["ship"]
        self.assertEqual(ship["total_onboard_water_mass_t"], 0)
        self.assertGreater(ship["equilibrium"]["waterline_d_m"], 1)
        self.assertLess(ship["equilibrium"]["waterline_d_m"], 4)
        self.assertLess(abs(ship["equilibrium"]["heel_deg"]), .001)
        for module in result["final_state"]["modules"]:
            self.assertEqual(module["effective_availability"], 1)

    def test_vessel_flooding_retains_offsets_native_states_and_conserved_crew(self):
        before = copy.deepcopy((self.project, self.experiment))
        result = run_experiment(self.project, "normal", self.experiment)
        self.assertEqual(result["status"], "completed", result.get("diagnostics"))
        self.assertEqual(result["final_state"]["time_s"], 12)
        self.assertEqual(result["input_snapshot"]["geometry"], self.project["geometry"])
        self.assertEqual((self.project, self.experiment), before)
        native = result["core_analysis"]["stages"]["flooding"]["data"]
        ship = result["final_state"]["ship"]
        self.assertEqual(ship["equilibrium"], native["final_state"]["equilibrium"])
        self.assertEqual(ship["total_onboard_water_mass_t"], native["final_state"]["total_onboard_water_mass_t"])
        self.assertGreater(ship["total_onboard_water_mass_t"], 0)
        self.assertLess(abs(ship["mass_conservation_error_t"]), 1e-8)
        counts = {group["id"]: group["personnel"] for group in self.experiment["crew_groups"]}
        for group in result["final_state"]["crew_groups"]:
            self.assertEqual(sum(group[key] for key in ("available", "incapacitated", "dead", "evacuated")), counts[group["id"]])


if __name__ == "__main__":
    unittest.main()
