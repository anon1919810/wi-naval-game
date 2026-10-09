"""Finite arithmetic and empirical applicability must be separate from completeness."""
import math
import unittest

from plimsoll import analysis, engines, geometry_analysis, guns, loading, project_io, resistance, units
from test_analysis_resistance import selected_project


class RangePolicyAuditTests(unittest.TestCase):
    def test_identity_units_and_nonrepresentable_conversion(self):
        self.assertEqual(units.convert(1e307, 'rad', 'rad'), 1e307)
        with self.assertRaises(ValueError):
            units.convert(1e308, 'rad', 'deg')
        with self.assertRaises(ValueError):
            units.convert(10**1000, 'rad', 'rad')

    def test_optional_engine_numbers_validate_even_without_derivation(self):
        for field in ('displacement_normal_t', 'lwl_m'):
            for value in (True, '10', 0, -1, math.nan, math.inf):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    engines.compute(dict(schema='plimsoll-engines-1', shafts=2, **{field: value}))

    def test_charge_validates_even_without_magazine(self):
        battery = dict(id='gun', column='main', guns=1, gun_weight_t=1,
                       shell_lb=10, broadside_guns=1)
        for value in (-20, True, '1', math.nan, math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                guns.compute(dict(schema='plimsoll-guns-1', batteries=[dict(battery, charge_lb=value)]))
        r = guns.compute(dict(schema='plimsoll-guns-1',
            batteries=[dict(battery, charge_lb=0, rounds_per_gun=1)]))
        self.assertAlmostEqual(r['batteries']['main']['magazine_t'], .0045359237)

    def test_loading_rejects_nominal_and_interval_range_overflow(self):
        for masses, x, interval in (([1e308], 10, False), ([1e308, 1e308], 0, False), ([1], 10, True)):
            p = project_io.new_project('Range', 'range')
            items = [dict(id=str(i), mass_t=m, x_m=x, y_m=0, kg_m=0, source='analytic', estimate=False)
                     for i, m in enumerate(masses)]
            if interval:
                items[0]['uncertainty'] = {'mass_t': [1, 1e308]}
            p['weight_groups'] = [dict(id='outfit', items=items)]
            p['loading_conditions'] = [dict(id='normal', overrides={})]
            with self.subTest(masses=masses, interval=interval), self.assertRaises(ValueError):
                loading.resolve_loading(p, 'normal')
            with self.assertRaises(analysis.AnalysisInputError):
                analysis.compute_project(p, 'normal', dict(stages=['loading']))

    def test_complete_taylor_table_does_not_certify_low_re_friction(self):
        table = dict(axes=dict(cp=[.5, .6], bt=[2, 3], volumetric=[.001, .008], fn=[.2, .3]),
            cr=[[[[.01, .01] for _ in range(2)] for _ in range(2)] for _ in range(2)],
            interpolation_coordinate='l_over_volume_cuberoot',
            source_axes={'l_over_volume_cuberoot': [10, 5]}, source='synthetic complete table')
        speed = .2*math.sqrt(9.81*.2)/(1852/3600)
        curve = resistance.speed_power_curve(dict(lwl_m=.2, s_m2=.02, cp=.5, bt=2,
            volumetric=1/7.5**3), [speed], table, interpolation_method='taylor_gertler_source_axis_strict',
            friction_method='schoenherr_implicit_ittc_0.242', speed_conversion_method='international_knot_exact')
        row = curve['rows'][0]
        self.assertTrue(row['complete'])
        self.assertFalse(row.get('model_applicable', True))
        self.assertTrue(any('reynolds' in d['code'] for d in row['diagnostics']))

    def test_canonical_taylor_retains_the_low_re_diagnostic(self):
        p = selected_project()
        p['geometry'] = geometry_analysis.materialize_reference_hull(
            dict(lwl_m=.2, beam_m=.03, draught_m=.01, block_coeff=.6,
                 waterplane_coeff=.8, depth_m=.018),
            keel_offset_m=.004, source='scaled numerical model', estimate=True,
            n_stations=17, n_section=12)
        p['weight_groups'][0]['items'][0].update(mass_t=3.2e-5, x_m=0, kg_m=.006)
        scenario = p['resistance_scenarios'][0]
        scenario['attitude_policy'] = 'strict_upright'
        options = dict(stages=['resistance'], resistance=dict(scenario_id='trial',
                       speeds_kn=[12*math.sqrt(.002)]))
        result = analysis.compute_project(p, 'normal', options)
        data = result['stages']['resistance']['data']
        self.assertTrue(data['rows'][0]['complete'])
        self.assertFalse(data['primary_result'])
        self.assertTrue(all(not row['primary_result'] for row in data['power_rows']))
        policy = [d for d in data['diagnostics'] if d['code'] == 'resistance.reynolds_policy']
        self.assertEqual(len(policy), 1)
        self.assertEqual(policy[0]['path'], '$.options.resistance.speeds_kn[0]')
        request = options['resistance']
        request.update(speeds_kn=[speed*math.sqrt(.002) for speed in (12, 13)],
                       qpc_override=dict(value=.5, source='declared QPC', estimate=True))
        prediction = analysis.compute_project(p, 'normal', options)['stages']['resistance']['data']
        self.assertTrue(all(row['complete'] for row in prediction['rows']))
        request.update(mode='fixed_power', fixed_shaft_power_kw=sum(
            row['shaft_power_kw'] for row in prediction['power_rows'])/2)
        inverse = analysis.compute_project(p, 'normal', options)['stages']['resistance']['data']
        self.assertEqual(inverse['fixed_power_study']['status'], 'estimated_nonprimary')
        self.assertFalse(inverse['fixed_power_study']['model_applicable'])
        request['mode'] = 'predict_power'
        request.pop('fixed_shaft_power_kw')
        scenario['inputs']['kinematic_viscosity_m2_s'] = (
            sum(request['speeds_kn'])/2*1852/3600*data['effective_inputs']['lwl_m']/1e5)
        mixed = analysis.compute_project(p, 'normal', options)['stages']['resistance']['data']
        self.assertEqual([row['primary_result'] for row in mixed['rows']], [False, True])
        self.assertEqual([row['primary_result'] for row in mixed['power_rows']], [False, True])
        self.assertFalse(mixed['validity']['model_applicable'])
        scenario['inputs']['kinematic_viscosity_m2_s'] = 1.19e-8
        control = analysis.compute_project(p, 'normal', options)['stages']['resistance']['data']
        self.assertTrue(control['primary_result'])
        self.assertFalse(any(d['code'] == 'resistance.reynolds_policy' for d in control['diagnostics']))

    def test_coverage_percentage_cannot_overflow_a_certified_loading(self):
        p = project_io.new_project('Coverage range', 'coverage-range')
        p['weight_groups'] = [dict(id='mass', items=[dict(id='m', mass_t=1e306,
            x_m=0, y_m=0, kg_m=0, source='analytic', estimate=False)])]
        p['loading_conditions'] = [dict(id='normal', reference_displacement_t=.1)]
        with self.assertRaises(loading.LoadingRangeError):
            loading.resolve_loading(p, 'normal')
        with self.assertRaises(analysis.AnalysisInputError):
            analysis.compute_project(p, 'normal', dict(stages=['loading']))

    def test_engine_fraction_and_admiralty_avoid_intermediate_overflow(self):
        base = dict(schema='plimsoll-engines-1', shafts=2, power_design_shp=1000,
                    max_speed_kn=10, coal_t=0, oil_t=0)
        result = engines.compute(dict(base, coal_t=1e307, oil_t=1e307))
        self.assertEqual(result['values']['pct_coal'], 50)
        result = engines.compute(dict(base, displacement_normal_t=1e150,
            max_speed_kn=1e75, power_design_shp=1e200))
        self.assertTrue(math.isclose(result['values']['admiralty_coeff'], 1e125, rel_tol=1e-12))

    def test_engine_unrepresentable_inventory_and_endurance_are_rejected(self):
        base = dict(schema='plimsoll-engines-1', shafts=2, coal_t=1e308, oil_t=0)
        with self.assertRaises(ValueError):
            engines.compute(dict(base, oil_t=1e308))
        for rate, speed in ((1e-308, 10), (100, 100)):
            scenario = dict(method='steady_simultaneous_fuel_consumption', source='analytic',
                estimate=False, speed_kn=speed, power_kw=100,
                fuels=dict(coal=dict(required=True, burn_t_per_day=rate, reserve_t=0),
                           oil=dict(required=False, burn_t_per_day=0, reserve_t=0)))
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                engines.compute(dict(base, endurance_scenario=scenario))


if __name__ == '__main__':
    unittest.main()
