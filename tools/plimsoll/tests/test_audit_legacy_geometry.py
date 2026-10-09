"""Independent analytic regressions from the 2026-10-09 core audit."""
import math
import unittest

import damage
import freeboard
import geometric
import geometry
import hull
import hydrostatics


class LegacyGeometryAuditTests(unittest.TestCase):
    def test_steep_heel_preserves_displacement(self):
        poly = [(-5, 0), (5, 0), (5, 4), (-5, 4)]
        box = geometry.StationedHull([(-10, poly), (0, poly), (10, poly)])
        d = box.solve_waterline(math.radians(80), 80)
        self.assertAlmostEqual(d, -20.68512727847, places=7)
        self.assertAlmostEqual(box.integrate(math.radians(80), d)['volume'], 80, places=6)
        with self.assertRaises(ValueError):
            box.solve_waterline(0, 801)
        with self.assertRaises(ValueError):
            box.solve_waterline(math.radians(80), 80, lo=-4, hi=8)

    def test_concave_waterplane_integrates_occupied_strips(self):
        poly = [(-3, 0), (3, 0), (3, 5), (2.5, 5), (2.5, 1),
                (-2.5, 1), (-2.5, 5), (-3, 5)]
        box = geometry.StationedHull([(-10, poly), (0, poly), (10, poly)])
        r = geometric.hydrostatics_upright(box, 3)
        self.assertAlmostEqual(r['volume_m3'], 160)
        self.assertAlmostEqual(r['it_m4'], 151.6666666667)
        self.assertAlmostEqual(r['km_m'], 1.8229166667)

    def test_known_lcg_does_not_require_lcb(self):
        r = damage.flood_combination({'displacement_t': 1000, 'kg_m': 1, 'lcg_m': 2},
            [{'id': 'tank', 'length_m': 10, 'beam_m': 4, 'height_m': 2,
              'flood_fraction': 1, 'fluid_density_t_m3': 1.025, 'x_m': 4}])
        self.assertAlmostEqual(r['lcg_solid_m'], 2328/1082)
        self.assertIsNone(r['lcb_m'])

    def test_entrance_fraction_locates_and_differentiates_its_crossing(self):
        stations = []
        for x in range(-50, 51):
            b = 10*(1-(x/50)**2)
            stations.append((x, [(-b, -1), (b, -1), (b, 1), (-b, 1)]))
        box = geometry.StationedHull(stations)
        for f in (.2, .8):
            r = hull.half_angle_of_entrance(box, at_frac=f)['values']
            expected_x = 50*math.sqrt(1-f)
            self.assertAlmostEqual(r['x_at_m'], expected_x, delta=.01)
            self.assertAlmostEqual(r['iE_deg'], math.degrees(math.atan(.008*expected_x)), delta=.005)
        for f in (True, '0.2', 0, 1, math.nan):
            with self.subTest(f=f), self.assertRaises(ValueError):
                hull.half_angle_of_entrance(box, at_frac=f)

    def test_mct_uses_signed_longitudinal_gm_when_kg_known(self):
        for kg in (1, 8, 9):
            r = hydrostatics.compute({'lwl_m': 10, 'beam_m': 10, 'draught_m': 1,
                    'block_coeff': 1, 'waterplane_coeff': 1, 'kg_m': kg})
            self.assertAlmostEqual(r['values']['mct1cm_t_m_per_cm'],
                                   102.5*(.5+100/12-kg)/1000)

    def test_entrance_does_not_borrow_an_afterbody_crossing(self):
        profile = [(-50, .5), (-25, 5), (0, 1), (25, 10), (50, 5)]
        box = geometry.StationedHull([(x, [(-b, -1), (b, -1), (b, 1), (-b, 1)])
                                     for x, b in profile])
        self.assertIsNone(hull.half_angle_of_entrance(box, at_frac=.2)['values']['iE_deg'])

    def test_deck_contact_uses_lowest_endpoint_not_segment_average(self):
        r = freeboard.compute({'schema': 'plimsoll-freeboard-1', 'lwl_m': 100,
            'beam_m': 10, 'segments': [{'id': 'deck', 'length_pct_lwl': 100,
                'fb_fore_m': 0, 'fb_aft_m': 4, 'source': 'analytic'}]})
        self.assertEqual(r['values']['average_freeboard_m'], 2)
        self.assertEqual(r['values']['min_freeboard_m'], 0)
        self.assertEqual(r['values']['deck_immersion_min_deg'], 0)
        self.assertEqual(r['segments'][0]['deck_immersion_deg'], 0)


if __name__ == '__main__':
    unittest.main()
