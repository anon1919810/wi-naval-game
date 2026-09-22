"""Independent analytic anchors for rectangular liquid geometry."""
import copy
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import damage
from tank_geometry import liquid_state, from_legacy_flood_tank


def tank(**changes):
    value = dict(id='box', length_m=10.0, beam_m=4.0, height_m=4.0,
                 x_m=0.0, y_m=0.0, keel_to_bottom_m=0.0,
                 permeability=1.0, free_surface=True)
    value.update(changes)
    return value


class TankGeometryTests(unittest.TestCase):
    def close(self, actual, expected, rel=1e-10, abs_tol=1e-10):
        self.assertTrue(math.isclose(actual, expected, rel_tol=rel, abs_tol=abs_tol),
                        f'{actual!r} != {expected!r}')

    def vector(self, actual, expected):
        for a, b in zip(actual, expected):
            self.close(a, b)

    def test_upright_partial_centroid_and_surface_moments(self):
        result = liquid_state(tank(), 80.0)
        self.vector(result['centroid_m'], [0.0, 0.0, 1.0])
        self.close(result['volume_m3'], 80.0)
        surface = result['free_surface']
        self.close(surface['area_m2'], 40.0)
        self.close(surface['i_u_m4'], 160.0 / 3)
        self.close(surface['i_v_m4'], 1000.0 / 3)
        self.close(surface['i_uv_m4'], 0.0)

    def test_tilted_half_volume_anchor(self):
        result = liquid_state(tank(), 80.0, heel_deg=math.degrees(math.atan(0.5)))
        self.vector(result['centroid_m'], [0.0, 1.0 / 3, 13.0 / 12])
        self.close(result['free_surface']['area_m2'], 40 * math.sqrt(1.25))
        self.close(result['free_surface']['i_u_m4'], 10 * (4 * math.sqrt(1.25))**3 / 12)

    def test_joint_slopes_anchor(self):
        p, q, average_depth = 0.1, 0.5, 2.0
        result = liquid_state(tank(), 80.0, heel_deg=math.degrees(math.atan(q)),
                              trim_deg=math.degrees(math.atan(p)))
        self.vector(result['centroid_m'], [p * 100 / (12 * average_depth),
                                          q * 16 / (12 * average_depth),
                                          average_depth/2 + (p*p*100 + q*q*16)/(24*average_depth)])
        self.close(result['volume_m3'], 80.0)
        self.assertGreater(result['free_surface']['i_u_m4'] * result['free_surface']['i_v_m4'],
                           result['free_surface']['i_uv_m4']**2)

    def test_bottom_cut_triangular_wedge(self):
        # q=1, d=0: water only over y in [0,2], h=y. Triangle area=2;
        # prism volume=20, triangle centroid y=4/3,z=2/3.
        result = liquid_state(tank(), 20.0, heel_deg=45.0)
        self.vector(result['centroid_m'], [0.0, 4.0/3, 2.0/3])
        self.close(result['volume_m3'], 20.0)
        self.close(result['free_surface']['area_m2'], 20 * math.sqrt(2))

    def test_top_cut_is_complement_of_empty_wedge(self):
        result = liquid_state(tank(), 140.0, heel_deg=45.0)
        # Complement empty wedge: V=20, y=-4/3, z=10/3.
        self.vector(result['centroid_m'], [0.0, (20 * 4/3)/140,
                                          (160*2 - 20*10/3)/140])
        self.close(result['volume_m3'], 140.0)

    def test_port_starboard_mirror(self):
        left = liquid_state(tank(y_m=3.0), 47.0, heel_deg=27, trim_deg=-6)
        right = liquid_state(tank(y_m=-3.0), 47.0, heel_deg=-27, trim_deg=-6)
        self.vector(left['centroid_m'], [right['centroid_m'][0],
                                         -right['centroid_m'][1], right['centroid_m'][2]])
        self.close(left['free_surface']['area_m2'], right['free_surface']['area_m2'])

    def test_translation(self):
        origin = liquid_state(tank(), 37, heel_deg=31, trim_deg=7)
        moved = liquid_state(tank(x_m=110, y_m=-13, keel_to_bottom_m=20), 37,
                             heel_deg=31, trim_deg=7)
        self.vector(moved['centroid_m'], [a+b for a, b in zip(origin['centroid_m'], [110,-13,20])])
        for field in ('area_m2','i_u_m4','i_v_m4','i_uv_m4'):
            self.close(origin['free_surface'][field], moved['free_surface'][field])

    def test_uniform_permeability_preserves_height_centroid(self):
        full = liquid_state(tank(), 80, heel_deg=20, trim_deg=3)
        porous = liquid_state(tank(permeability=0.4), 32, heel_deg=20, trim_deg=3)
        self.vector(full['centroid_m'], porous['centroid_m'])
        self.close(porous['free_surface']['available_i_u_m4'],
                   0.4 * full['free_surface']['i_u_m4'])

    def test_empty_full_zero_permeability(self):
        empty = liquid_state(tank(), 0, heel_deg=30, trim_deg=9)
        self.assertIsNone(empty['centroid_m'])
        self.assertFalse(empty['free_surface']['active'])
        full = liquid_state(tank(), 160, heel_deg=30, trim_deg=9)
        self.vector(full['centroid_m'], [0,0,2])
        self.assertFalse(full['free_surface']['active'])
        zero = liquid_state(tank(permeability=0), 0, heel_deg=30)
        self.assertIsNone(zero['centroid_m'])
        with self.assertRaises(ValueError):
            liquid_state(tank(permeability=0), 0.01)

    def test_locked_liquid_proxy_is_explicit(self):
        result = liquid_state(tank(free_surface=False), 80, heel_deg=30, trim_deg=9)
        self.vector(result['centroid_m'], [0,0,1])
        self.assertFalse(result['free_surface']['active'])
        self.assertEqual(result['method'], 'locked_centroid_proxy')
        self.assertTrue(any(d['code']=='liquid.locked_centroid_proxy' for d in result['diagnostics']))

    def test_small_positive_water_has_centroid_and_mass(self):
        result = liquid_state(tank(), 1e-7, heel_deg=30, trim_deg=5)
        self.assertIsNotNone(result['centroid_m'])
        self.assertGreater(result['volume_m3'], 0)
        self.close(result['volume_m3'], 1e-7, rel=1e-5, abs_tol=1e-12)
        self.assertTrue(all(math.isfinite(v) for v in result['centroid_m']))

    def test_high_supported_angle_has_bounded_centroid(self):
        result = liquid_state(tank(), 65.0, heel_deg=80, trim_deg=-10)
        for v, lower, upper in zip(result['centroid_m'], [-5,-2,0], [5,2,4]):
            self.assertGreaterEqual(v, lower)
            self.assertLessEqual(v, upper)
        self.close(result['volume_m3'], 65.0)

    def test_independent_column_quadrature_converges(self):
        result = liquid_state(tank(), 27.3, heel_deg=27.5, trim_deg=10)
        nx, ny, nz = result['plane_normal']
        offset = result['plane_offset_m']
        def quadrature(count):
            dx, dy = 10/count, 4/count
            volume = mx = my = mz = 0.0
            for i in range(count):
                x = -5+(i+0.5)*dx
                for j in range(count):
                    y = -2+(j+0.5)*dy
                    h = min(4, max(0, (offset-nx*x-ny*y)/nz))
                    dv = dx*dy*h
                    volume += dv
                    mx += dv*x
                    my += dv*y
                    mz += dv*h/2
            return [volume, mx/volume, my/volume, mz/volume]
        expected = [27.3, *result['centroid_m']]
        coarse, fine = quadrature(80), quadrature(160)
        coarse_error = max(abs(a-b) for a,b in zip(coarse, expected))
        fine_error = max(abs(a-b) for a,b in zip(fine, expected))
        self.assertLess(fine_error, coarse_error)
        self.assertLess(fine_error, 1e-3)

    def test_surface_points_and_basis_obey_plane(self):
        result = liquid_state(tank(), 61, heel_deg=-34, trim_deg=14)
        surface = result['free_surface']
        u, v, n = surface['basis_u'], surface['basis_v'], surface['normal']
        dot = lambda a,b: sum(x*y for x,y in zip(a,b))
        for vector in (u,v,n):
            self.close(dot(vector,vector), 1)
        for a,b in ((u,v),(u,n),(v,n)):
            self.close(dot(a,b), 0)
        for point in surface['polygon_m']:
            self.close(dot(n,point), result['plane_offset_m'])

    def test_translated_joint_slope_cap_obeys_normal_and_slope_planes(self):
        heel, trim = -34.0, 14.0
        result = liquid_state(
            tank(x_m=110.0, y_m=-13.0, keel_to_bottom_m=20.0),
            61.0, heel_deg=heel, trim_deg=trim)
        normal = result['plane_normal']
        normal_offset = result['plane_offset_m']
        slope_intercept = normal_offset/normal[2]
        p = math.tan(math.radians(trim))
        q = math.tan(math.radians(heel))
        for point in result['free_surface']['polygon_m']:
            self.close(sum(a*b for a, b in zip(normal, point)), normal_offset)
            self.close(point[2], p*point[0] + q*point[1] + slope_intercept)
        self.assertEqual(result['angle_convention'], 'n·r=h with unit n=(-tan(trim_deg),-tan(heel_deg),1)/norm; slope intercept d=h/n_z')

    def test_inputs_are_unchanged(self):
        value = tank()
        before = copy.deepcopy(value)
        liquid_state(value, 20, heel_deg=31)
        self.assertEqual(value, before)

    def test_rejects_bad_geometry_and_water(self):
        for key in ('length_m','beam_m','height_m','x_m','y_m','keel_to_bottom_m','permeability'):
            for bad in (True, float('nan'), float('inf'), '2'):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    liquid_state(tank(**{key:bad}), 0)
        for bad in (True, float('nan'), float('inf'), -0.1, 160.01):
            with self.subTest(volume=bad), self.assertRaises(ValueError):
                liquid_state(tank(), bad)
        for key in ('length_m','beam_m','height_m'):
            with self.assertRaises(ValueError):
                liquid_state(tank(**{key:0}), 0)
        for mu in (-0.1, 1.1):
            with self.assertRaises(ValueError):
                liquid_state(tank(permeability=mu), 0)
        value = tank()
        del value['x_m']
        with self.assertRaises(ValueError):
            liquid_state(value, 20)

    def test_rejects_unsupported_angles_and_surface_flag(self):
        for bad in (89, -90, 180, True, float('nan')):
            with self.assertRaises(ValueError):
                liquid_state(tank(), 20, heel_deg=bad)
        with self.assertRaises(ValueError):
            liquid_state(tank(free_surface='false'), 20)

    def test_adapter_uses_actual_water_and_no_duplicate_fsc(self):
        value = tank(flood_fraction=0.5, fluid_density_t_m3=1.025, permeability=0.4)
        result = from_legacy_flood_tank(value, heel_deg=0)
        self.close(result['added_displacement_t'], 32*1.025)
        self.vector(result['centroid_m'], [0,0,1])
        self.assertEqual(result['fsc_policy'], 'centroid_geometry_no_additional_fsc')
        for key in ('flood_fraction','fluid_density_t_m3'):
            with self.assertRaises(ValueError):
                from_legacy_flood_tank({**value,key:True})

    def test_requested_water_and_adapter_mass_are_exactly_conserved(self):
        requested = 18.8
        value = tank(permeability=0.4, flood_fraction=0.29375,
                     fluid_density_t_m3=1.025)
        state = liquid_state(value, requested, heel_deg=27.0, trim_deg=-6.0)
        self.assertEqual(state['volume_m3'], requested)
        self.assertEqual(state['requested_volume_m3'], requested)
        self.close(state['integrated_volume_m3'] - requested,
                   state['volume_residual_m3'], rel=0.0, abs_tol=1e-15)

        adapted = from_legacy_flood_tank(value, heel_deg=27.0, trim_deg=-6.0)
        self.assertEqual(adapted['volume_m3'], requested)
        self.assertEqual(adapted['added_displacement_t'], 1.025 * requested)

    def test_near_full_surface_matches_complementary_bottom_wedge(self):
        gross = 160.0
        for fraction in (1e-8, 1e-10, 1e-12):
            with self.subTest(fraction=fraction):
                top_volume = gross - gross * fraction
                small_volume = gross - top_volume
                bottom = liquid_state(tank(), small_volume, heel_deg=33.0, trim_deg=17.0)
                top = liquid_state(tank(), top_volume, heel_deg=33.0, trim_deg=17.0)
                self.assertEqual(top['applicability']['status'], 'applicable')
                self.assertTrue(top['free_surface']['active'])
                self.assertTrue(top['free_surface']['converged'])
                for field in ('area_m2', 'i_u_m4', 'i_v_m4', 'i_uv_m4'):
                    self.close(top['free_surface'][field], bottom['free_surface'][field],
                               rel=2e-8, abs_tol=1e-18)

    def test_near_full_reports_phase_accuracy_and_reconstruction_bound(self):
        value = tank(length_m=7.13, beam_m=3.17, height_m=2.73,
                     permeability=0.4)
        capacity = 7.13 * 3.17 * 2.73 * 0.4
        requested = capacity * (1.0 - 1e-10)
        result = liquid_state(value, requested, heel_deg=33.0, trim_deg=17.0)
        small_phase_volume = capacity - requested
        self.assertLessEqual(abs(result['phase_volume_residual_m3']),
                             result['phase_volume_tolerance_m3'])
        self.assertLessEqual(result['phase_volume_tolerance_m3'],
                             small_phase_volume * 2.1e-12)
        self.assertGreater(result['volume_reconstruction_roundoff_m3'], 0.0)
        self.assertLessEqual(abs(result['volume_residual_m3']),
                             result['volume_tolerance_m3'])
        self.assertGreater(result['volume_tolerance_m3'],
                           result['phase_volume_tolerance_m3'])

    def test_capacity_product_is_independent_of_factor_order(self):
        cases = ((1e-200, 1e-200, 1e200, 1e-200),
                 (1e200, 1e200, 1e-200, 1e200))
        for length, beam, height, expected in cases:
            with self.subTest(dimensions=(length, beam, height)):
                value = tank(length_m=length, beam_m=beam, height_m=height,
                             flood_fraction=1.0, fluid_density_t_m3=1.0)
                state = from_legacy_flood_tank(value)
                self.close(state['gross_volume_m3'], expected)
                self.close(state['capacity_m3'], expected)
                self.assertGreater(state['gross_volume_m3'], 0.0)
                self.assertEqual(state['volume_m3'], state['capacity_m3'])

    def test_nonfinite_derived_public_geometry_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'finite'):
            liquid_state(tank(x_m=1.7e308, y_m=1.7e308), 80.0,
                         heel_deg=-45.0, trim_deg=-45.0)
        with self.assertRaisesRegex(ValueError, 'finite'):
            liquid_state(tank(length_m=1e-154, beam_m=1e-154, height_m=1e308,
                              keel_to_bottom_m=1.5e308), 0.9999999999999999)

    def test_unrepresentable_positive_available_moment_is_rejected(self):
        value = tank(length_m=1.0, beam_m=1e-12, height_m=1e-12,
                     permeability=2e-299)
        with self.assertRaisesRegex(
                ValueError, 'available_i_u_m4 is below the positive numerical range'):
            liquid_state(value, 1e-323)

    def test_partial_geometry_has_declared_aspect_ratio_domain(self):
        supported = liquid_state(tank(length_m=1e6, beam_m=1.0, height_m=1.0),
                                 5e5)
        self.vector(supported['centroid_m'], [0.0, 0.0, 0.25])
        self.close(supported['free_surface']['area_m2'], 1e6)
        with self.assertRaisesRegex(ValueError, 'aspect ratio'):
            liquid_state(tank(length_m=1e13, beam_m=1.0, height_m=1.0), 5e12)
        with self.assertRaisesRegex(ValueError, 'phase fraction'):
            liquid_state(tank(), 160.0 * 1e-14, heel_deg=33.0, trim_deg=17.0)

    def test_result_declares_method_applicability_and_moment_convention(self):
        source = {'citation': ['survey', {'page': 7}]}
        estimate = {'kind': ['uniform void distribution']}
        value = tank(source=source, estimate=estimate)
        result = liquid_state(value, 61.0, heel_deg=-34.0, trim_deg=14.0)
        self.assertEqual(result['method_version'], 'rectangular-liquid-geometry-1')
        self.assertEqual(result['angle_convention'], 'n·r=h with unit n=(-tan(trim_deg),-tan(heel_deg),1)/norm; slope intercept d=h/n_z')
        self.assertEqual(result['applicability']['status'], 'applicable')
        self.assertTrue(result['converged'])
        self.assertIn('max_partial_aspect_ratio', result['supported_domain'])
        self.assertIn('rectangular', result['assumptions'])
        self.assertEqual(result['free_surface']['moment_convention']['tensor_off_diagonal'],
                         '-i_uv_m4')
        source['citation'][1]['page'] = 99
        estimate['kind'].append('changed')
        self.assertEqual(result['source'], {'citation': ['survey', {'page': 7}]})
        self.assertEqual(result['estimate'], {'kind': ['uniform void distribution']})

    def test_legacy_adapter_matches_ordinary_upright_damage_geometry(self):
        value = tank(x_m=12.0, y_m=-3.0, keel_to_bottom_m=2.0,
                     permeability=0.4, flood_fraction=0.35,
                     fluid_density_t_m3=1.025)
        legacy = damage.flood_tank_state(value)
        adapted = from_legacy_flood_tank(value)
        self.close(adapted['volume_m3'], legacy['volume_flood_m3'])
        self.close(adapted['added_displacement_t'], legacy['added_displacement_t'])
        self.vector(adapted['centroid_m'],
                    [legacy['x_m'], legacy['y_m'], legacy['kg_flood_m']])
        self.assertEqual(adapted['free_surface']['active'], legacy['free_surface_active'])
        self.assertEqual(adapted['fsc_policy'], 'centroid_geometry_no_additional_fsc')


if __name__ == '__main__':
    unittest.main()
