"""Connected flooding anchors, coupled feedback, events, and public contracts."""
from __future__ import annotations

import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG))

import project_io

try:
    import flooding
except ModuleNotFoundError:
    flooding = None
try:
    import _flooding_kernel as kernel
except ModuleNotFoundError:
    kernel = None


DT_SEQUENCE = (0.5, 0.25, 0.125)


def oracle() -> dict:
    path = HERE.parents[2] / 'docs/plimsoll-1.0/evidence/flooding_oracles.py'
    spec = importlib.util.spec_from_file_location('independent_flooding_oracle', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.oracle()


def box_project(*, base_y_m: float = 0.0) -> dict:
    project = project_io.new_project('Coupled flooding box', 'coupled-flooding-box')
    project['hull'] = {'lwl_m': 20.0, 'beam_m': 10.0, 'depth_m': 6.0}
    section = [[-5.0, 0.0], [5.0, 0.0], [5.0, 6.0], [-5.0, 6.0]]
    project['geometry'] = {
        'kind': 'offsets',
        'keel_offset_m': 0.0,
        'source': {'kind': 'analytic_rectangular_prism'},
        'estimate': False,
        'offsets': {
            'schema': 'plimsoll-section-polygons-1',
            'stations': [
                [-10.0 + i, copy.deepcopy(section)] for i in range(21)
            ],
        },
    }
    project['weight_groups'] = [{
        'id': 'lightship',
        'label': 'Base mass',
        'required': True,
        'items': [{
            'id': 'base-mass',
            'mass_t': 401.8,
            'x_m': 0.0,
            'y_m': base_y_m,
            'kg_m': 1.0,
            'source': {'kind': 'analytic_fixture'},
            'estimate': False,
        }],
    }]
    project['loading_conditions'] = [{
        'id': 'normal',
        'label': 'Normal',
        'reference_displacement_t': 401.8,
        'overrides': {},
    }]
    project['openings'] = []
    return project


def tank(tank_id: str = 'centre', *, y_m: float = 0.0,
         initial_volume_m3: float = 8.0, permeability: float = 1.0) -> dict:
    return {
        'id': tank_id,
        'length_m': 4.0,
        'beam_m': 2.0,
        'height_m': 4.0,
        'x_m': 0.0,
        'y_m': y_m,
        'keel_to_bottom_m': 0.0,
        'permeability': permeability,
        'free_surface': True,
        'fluid_density_t_m3': 1.025,
        'initial_volume_m3': initial_volume_m3,
        'source': {'kind': 'analytic_fixture'},
        'estimate': False,
    }


def scenario(*, dt: float = 0.25, duration: float = 5.0,
             y_m: float = 0.0, open_edge: bool = True) -> dict:
    return {
        'schema': 'plimsoll-flooding-scenario-1',
        'id': 'coupled-heave',
        'duration_s': duration,
        'time_step_s': dt,
        'source': {'kind': 'independent_analytic_fixture'},
        'estimate': False,
        'sea': {
            'id': 'sea',
            'fluid_density_t_m3': 1.025,
            'source': {'kind': 'analytic_fixture'},
            'estimate': False,
        },
        'tanks': [tank(y_m=y_m)],
        'connections': [{
            'id': 'sea-hole',
            'from': 'sea',
            'to': 'centre',
            'x_m': 0.0,
            'y_m': y_m,
            'z_m': 0.1,
            'area_m2': 0.1,
            'discharge_coefficient': 0.6,
            'fluid_density_t_m3': 1.025,
            'open': open_edge,
            'source': {'kind': 'analytic_fixture'},
            'estimate': False,
        }],
    }


def kernel_tank(tank_id: str, *, y_m: float = 0.0,
                permeability: float = 1.0) -> dict:
    value = tank(tank_id, y_m=y_m, initial_volume_m3=0.0,
                 permeability=permeability)
    value.update(length_m=10.0, beam_m=1.0, height_m=5.0)
    return value


def kernel_edge(edge_id: str, source: str, target: str, **changes) -> dict:
    value = {
        'id': edge_id,
        'from_node_id': source,
        'to_node_id': target,
        'centre_m': [0.0, 0.0, 0.0],
        'area_m2': 0.1,
        'discharge_coefficient': 0.6,
        'fluid_density_t_m3': 1.025,
        'open': True,
        'source': {'kind': 'analytic_fixture'},
        'estimate': False,
    }
    value.update(changes)
    return value


class FixedAttitudeKernelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(kernel, 'private flooding kernel is not implemented')

    def close(self, actual: float, expected: float) -> None:
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10),
                        f'{actual!r} != {expected!r}')

    def test_inclined_pressure_head_anchor_mirror_and_datum(self):
        answer = oracle()['inclined_instantaneous']
        p, q = 0.1, 0.2
        tanks = [kernel_tank('port', y_m=-0.5), kernel_tank('starboard', y_m=0.5)]
        result = kernel.evaluate_flows(
            tanks, {'port': 15.0, 'starboard': 15.0},
            [kernel_edge('cross', 'port', 'starboard', centre_m=[0.0, 0.0, 0.25])],
            attitude={'heel_deg': math.degrees(math.atan(q)),
                      'trim_deg': math.degrees(math.atan(p)),
                      'geometry_keel_offset_m': 0.0})
        edge = result['edges'][0]
        self.close(edge['from_head_m'], answer['port_head_m'])
        self.close(edge['to_head_m'], answer['starboard_head_m'])
        self.close(edge['flow_m3_s'], answer['flow_port_to_starboard_m3_s'])

        moved = kernel.evaluate_flows(
            [kernel_tank('a')], {'a': 10.0},
            [kernel_edge('fill', 'sea', 'a')],
            attitude={'heel_deg': 0.0, 'trim_deg': 0.0,
                      'geometry_keel_offset_m': 17.0},
            sea={'id': 'sea', 'surface_offset_m': 20.0,
                 'fluid_density_t_m3': 1.025,
                 'source': {'kind': 'fixture'}, 'estimate': False})
        base = kernel.evaluate_flows(
            [kernel_tank('a')], {'a': 10.0},
            [kernel_edge('fill', 'sea', 'a')],
            attitude={'heel_deg': 0.0, 'trim_deg': 0.0,
                      'geometry_keel_offset_m': 0.0},
            sea={'id': 'sea', 'surface_offset_m': 3.0,
                 'fluid_density_t_m3': 1.025,
                 'source': {'kind': 'fixture'}, 'estimate': False})
        self.close(moved['edges'][0]['flow_m3_s'], base['edges'][0]['flow_m3_s'])

    def test_closed_equal_reverse_zero_and_partial_aperture_statuses(self):
        tanks = [kernel_tank('a'), kernel_tank('b')]
        cases = [
            (kernel_edge('closed', 'a', 'b', open=False), {'a': 20.0, 'b': 10.0}, 'closed', 0),
            (kernel_edge('zero', 'a', 'b', area_m2=0.0), {'a': 20.0, 'b': 10.0}, 'zero_area', 0),
            (kernel_edge('equal', 'a', 'b'), {'a': 10.0, 'b': 10.0}, 'equal_heads', 0),
            (kernel_edge('reverse', 'a', 'b'), {'a': 10.0, 'b': 20.0}, 'flowing', -1),
        ]
        attitude = {'heel_deg': 0.0, 'trim_deg': 0.0, 'geometry_keel_offset_m': 0.0}
        for edge, volumes, status, sign in cases:
            with self.subTest(edge=edge['id']):
                row = kernel.evaluate_flows(tanks, volumes, [edge], attitude=attitude)['edges'][0]
                self.assertEqual(row['status'], status)
                self.assertEqual(math.copysign(1, row['flow_m3_s']) if row['flow_m3_s'] else 0, sign)

        limited = kernel.evaluate_flows(
            tanks, {'a': 10.0, 'b': 5.0},
            [kernel_edge('partial', 'a', 'b', centre_m=[0, 0, 0.9], aperture_height_m=0.5)],
            attitude=attitude)
        self.assertEqual(limited['status'], 'model_limit')
        self.assertIsNone(limited['edges'][0]['flow_m3_s'])

        equal_partial = kernel.evaluate_flows(
            tanks, {'a': 10.0, 'b': 10.0},
            [kernel_edge('equal-partial', 'a', 'b', centre_m=[0, 0, 1],
                         aperture_height_m=0.5)], attitude=attitude)
        self.assertEqual(equal_partial['status'], 'applicable')
        self.assertEqual(equal_partial['edges'][0]['status'], 'equal_heads')
        self.assertEqual(equal_partial['edges'][0]['flow_m3_s'], 0.0)

    def test_fixed_ode_refinement_and_conservation(self):
        answer = oracle()
        pair_errors = []
        sea_errors = []
        attitude = {'heel_deg': 0.0, 'trim_deg': 0.0, 'geometry_keel_offset_m': 0.0}
        sea_node = {'id': 'sea', 'surface_offset_m': 3.0,
                    'fluid_density_t_m3': 1.025,
                    'source': {'kind': 'fixture'}, 'estimate': False}
        for dt in DT_SEQUENCE:
            pair = kernel.simulate_fixed_attitude(
                [kernel_tank('a'), kernel_tank('b')], {'a': 20.0, 'b': 10.0},
                [kernel_edge('cross', 'a', 'b')], attitude=attitude,
                duration_s=5.0, requested_dt_s=dt)
            pair_transfer = pair['final_volumes_m3']['b'] - 10.0
            pair_errors.append(abs(pair_transfer-answer['pair']['transferred_m3']))
            self.assertLessEqual(abs(pair['volume_conservation_error_m3']), 3e-9)
            self.assertLessEqual(abs(pair['mass_conservation_error_t']), 3e-9)

            wet = kernel.simulate_fixed_attitude(
                [kernel_tank('a')], {'a': 10.0},
                [kernel_edge('fill', 'sea', 'a')], attitude=attitude,
                sea=sea_node, duration_s=5.0, requested_dt_s=dt)
            sea_transfer = wet['final_volumes_m3']['a'] - 10.0
            sea_errors.append(abs(sea_transfer-answer['sea']['net_sea_inflow_m3']))
            self.close(sea_transfer, wet['cumulative_sea_exchange_m3'])

            drain = kernel.simulate_fixed_attitude(
                [kernel_tank('a')], {'a': 40.0},
                [kernel_edge('drain', 'sea', 'a')], attitude=attitude,
                sea=sea_node, duration_s=1.0, requested_dt_s=dt)
            sea_loss = 40.0-drain['final_volumes_m3']['a']
            self.close(sea_loss, -drain['cumulative_sea_exchange_m3'])

            stagnant = kernel.simulate_fixed_attitude(
                [kernel_tank('a')], {'a': 10.0}, [], attitude=attitude,
                sea=sea_node, duration_s=1.0, requested_dt_s=dt)
            self.close(stagnant['final_volumes_m3']['a'], 10.0)
            self.close(stagnant['cumulative_sea_exchange_m3'], 0.0)
        self.assertGreater(pair_errors[0], pair_errors[1])
        self.assertGreater(pair_errors[1], pair_errors[2])
        self.assertLess(pair_errors[2]/answer['pair']['transferred_m3'], 0.01)
        self.assertGreater(sea_errors[0], sea_errors[1])
        self.assertGreater(sea_errors[1], sea_errors[2])
        self.assertLess(sea_errors[2]/answer['sea']['net_sea_inflow_m3'], 0.01)

    def test_aggregate_budget_capacity_and_zero_permeability(self):
        attitude = {'heel_deg': 0.0, 'trim_deg': 0.0, 'geometry_keel_offset_m': 0.0}
        sea_node = {'id': 'sea', 'surface_offset_m': -1.0,
                    'fluid_density_t_m3': 1.025,
                    'source': {'kind': 'fixture'}, 'estimate': False}
        step = kernel.step_fixed_attitude(
            [kernel_tank('source')], {'source': 0.1},
            [kernel_edge('one', 'source', 'sea'), kernel_edge('two', 'source', 'sea')],
            attitude=attitude, sea=sea_node, requested_dt_s=10.0)
        self.assertAlmostEqual(step['volumes_m3']['source'], 0.0, places=12)
        self.assertAlmostEqual(sum(abs(e['transfer_m3']) for e in step['edge_transfers']),
                               0.1, places=12)

        blocked = kernel.step_fixed_attitude(
            [kernel_tank('blocked', permeability=0.0)], {'blocked': 0.0},
            [kernel_edge('fill', 'sea', 'blocked')], attitude=attitude,
            sea={**sea_node, 'surface_offset_m': 3.0}, requested_dt_s=1.0)
        self.assertEqual(blocked['status'], 'model_limit')
        self.assertEqual(blocked['stop_reason'], 'receiver_capacity')

        full = kernel.step_fixed_attitude(
            [kernel_tank('full')], {'full': 50.0},
            [kernel_edge('fill', 'sea', 'full')], attitude=attitude,
            sea={**sea_node, 'surface_offset_m': 6.0}, requested_dt_s=1.0)
        self.assertEqual(full['status'], 'model_limit')
        self.assertEqual(full['stop_reason'], 'receiver_capacity')
        self.assertAlmostEqual(full['volumes_m3']['full'], 50.0, places=12)

    def test_private_kernel_rejects_empty_source_metadata(self):
        attitude = {'heel_deg': 0.0, 'trim_deg': 0.0,
                    'geometry_keel_offset_m': 0.0}
        bad_tank = kernel_tank('a')
        bad_tank['source'] = None
        with self.assertRaisesRegex(ValueError, 'source'):
            kernel.evaluate_flows(
                [bad_tank, kernel_tank('b')], {'a': 10.0, 'b': 5.0},
                [kernel_edge('cross', 'a', 'b')], attitude=attitude)

        bad_edge = kernel_edge('cross', 'a', 'b')
        bad_edge['source'] = {}
        with self.assertRaisesRegex(ValueError, 'source'):
            kernel.evaluate_flows(
                [kernel_tank('a'), kernel_tank('b')], {'a': 10.0, 'b': 5.0},
                [bad_edge], attitude=attitude)


class CoupledFloodingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(flooding, 'public flooding API is not implemented')

    def test_coupled_heave_refines_to_independent_feedback_oracle(self):
        answer = oracle()['coupled_heave']
        influx_errors = []
        draft_errors = []
        for dt in DT_SEQUENCE:
            result = flooding.simulate_flooding(
                box_project(), 'normal', scenario(dt=dt), options={})
            self.assertEqual(result['status'], 'completed', result)
            self.assertEqual(result['stop_reason'], 'scheduled_completion')
            self.assertIs(result['validity']['numerical_convergence'], True)
            influx = result['final_state']['volumes_m3']['centre'] - 8.0
            draft = result['final_state']['equilibrium']['waterline_above_keel_m']
            influx_errors.append(abs(influx-answer['net_sea_inflow_m3']))
            draft_errors.append(abs(draft-answer['final_draft_m']))
            self.assertLessEqual(abs(result['volume_conservation_error_m3']), 1e-10*10)
            self.assertLessEqual(abs(result['mass_conservation_error_t']), 1e-10*410)
            self.assertEqual(result['timeline'][0]['flows'][0]['from'], 'sea')
            self.assertEqual(result['timeline'][0]['flows'][0]['to'], 'centre')
            self.assertNotIn('from_node_id', result['timeline'][0]['flows'][0])
            for state in result['timeline']:
                eq = state['equilibrium']
                self.assertTrue(eq['converged'])
                self.assertLessEqual(abs(eq['heel_deg']), 1e-6)
                self.assertLessEqual(abs(eq['trim_deg']), 1e-6)
                self.assertLessEqual(max(abs(v) for v in eq['residuals']['scaled'].values()), 1e-6)
        self.assertGreater(influx_errors[0], influx_errors[1])
        self.assertGreater(influx_errors[1], influx_errors[2])
        self.assertLess(influx_errors[2]/answer['net_sea_inflow_m3'], 0.01)
        draft_change = answer['final_draft_m'] - answer['initial_draft_m']
        self.assertLess(draft_errors[2]/draft_change, 0.01)

    def test_mirror_replay_and_input_immutability(self):
        project = box_project()
        port = scenario(dt=0.25, duration=0.5, y_m=-2.0)
        starboard = scenario(dt=0.25, duration=0.5, y_m=2.0)
        before = copy.deepcopy((project, port, starboard))
        left = flooding.simulate_flooding(project, 'normal', port)
        right = flooding.simulate_flooding(project, 'normal', starboard)
        self.assertEqual((project, port, starboard), before)
        self.assertAlmostEqual(left['final_state']['volumes_m3']['centre'],
                               right['final_state']['volumes_m3']['centre'], places=9)
        self.assertAlmostEqual(left['final_state']['equilibrium']['heel_deg'],
                               -right['final_state']['equilibrium']['heel_deg'], places=7)
        replay = flooding.simulate_flooding(project, 'normal', port)
        self.assertEqual(left['input_fingerprint'], replay['input_fingerprint'])
        self.assertEqual(left['timeline'], replay['timeline'])

    def test_cancel_failure_downflooding_and_invalid_input_are_distinct(self):
        calls = {'count': 0}
        def cancel(_state):
            calls['count'] += 1
            return calls['count'] > 1

        canceled = flooding.simulate_flooding(
            box_project(), 'normal', scenario(duration=2.0),
            options={'cancel_check': cancel})
        self.assertEqual(canceled['status'], 'canceled')
        self.assertEqual(canceled['stop_reason'], 'canceled')
        self.assertIs(canceled['validity']['numerical_convergence'], True)
        self.assertGreater(canceled['final_state']['time_s'], 0.0)

        failed = flooding.simulate_flooding(
            box_project(base_y_m=1.0), 'normal', scenario(duration=0.0),
            options={'equilibrium': {'max_iterations': 1}})
        self.assertEqual(failed['status'], 'equilibrium_failure')
        self.assertEqual(failed['timeline'], [])
        self.assertIs(failed['validity']['numerical_convergence'], False)
        self.assertFalse(failed['failed_attempt']['equilibrium']['converged'])

        flooding_event = scenario(duration=2.0)
        flooding_event['openings'] = [{
            'id': 'low-opening', 'x_m': 0.0, 'y_m': 0.0, 'z_m': 2.001,
            'open': True, 'source': {'kind': 'fixture'}, 'estimate': False,
        }]
        event = flooding.simulate_flooding(box_project(), 'normal', flooding_event)
        self.assertEqual(event['status'], 'downflooding_event')
        self.assertEqual(event['stop_reason'], 'downflooding_event')
        self.assertIs(event['validity']['numerical_convergence'], True)
        self.assertGreater(event['final_state']['time_s'], 0.0)
        self.assertLessEqual(event['final_state']['time_s'], 2.0)
        self.assertEqual(event['downflooding']['opening_id'], 'low-opening')

        invalid_scenario = scenario()
        del invalid_scenario['connections'][0]['discharge_coefficient']
        invalid = flooding.simulate_flooding(box_project(), 'normal', invalid_scenario)
        self.assertEqual(invalid['status'], 'invalid_input')
        self.assertEqual(invalid['timeline'], [])
        self.assertIsNone(invalid['validity']['numerical_convergence'])
        self.assertTrue(any(d['blocking'] for d in invalid['diagnostics']))

        over_capacity = scenario()
        over_capacity['tanks'][0]['initial_volume_m3'] = 33.0
        invalid_volume = flooding.simulate_flooding(
            box_project(), 'normal', over_capacity)
        self.assertEqual(invalid_volume['status'], 'invalid_input')
        self.assertEqual(invalid_volume['timeline'], [])

        unknown_option = flooding.simulate_flooding(
            box_project(), 'normal', scenario(duration=0.0),
            options={'unrecognized': True})
        self.assertEqual(unknown_option['status'], 'invalid_input')

        unordered_gz = flooding.simulate_flooding(
            box_project(), 'normal', scenario(duration=0.0),
            options={'remaining_gz_angles_deg': [0.0, -5.0]})
        self.assertEqual(unordered_gz['status'], 'invalid_input')
        self.assertEqual(unordered_gz['timeline'], [])

        for field, value in (('area_m2', math.nan), ('open', 1)):
            with self.subTest(invalid_connection_field=field):
                bad = scenario(duration=0.0)
                bad['connections'][0][field] = value
                rejected = flooding.simulate_flooding(box_project(), 'normal', bad)
                self.assertEqual(rejected['status'], 'invalid_input')
                self.assertEqual(rejected['timeline'], [])

    def test_absent_openings_remain_unknown(self):
        project = box_project()
        del project['openings']
        result = flooding.simulate_flooding(
            project, 'normal', scenario(duration=0.0))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['openings_origin'], 'unknown')
        self.assertEqual(result['final_state']['downflooding']['status'], 'unknown')
        self.assertTrue(any(d['code'] == 'flooding.openings_unknown'
                            for d in result['diagnostics']))

        explicit_unknown = scenario(duration=0.0)
        explicit_unknown['openings'] = None
        bridged = flooding.simulate_flooding(
            box_project(), 'normal', explicit_unknown)
        self.assertEqual(bridged['openings_origin'], 'scenario')
        self.assertIsNone(bridged['scenario']['openings'])
        self.assertEqual(bridged['final_state']['downflooding']['status'], 'unknown')

        supplied_empty = scenario(duration=0.0)
        supplied_empty['openings'] = []
        known_none = flooding.simulate_flooding(
            box_project(), 'normal', supplied_empty)
        self.assertEqual(known_none['final_state']['downflooding']['status'],
                         'no_open_points')
        self.assertNotEqual(bridged['input_fingerprint'],
                            known_none['input_fingerprint'])

    def test_public_scenario_rejects_empty_source_metadata(self):
        cases = []
        bad = scenario(duration=0.0)
        bad['source'] = None
        cases.append(('scenario', bad, '$.scenario.source'))
        bad = scenario(duration=0.0)
        bad['sea']['source'] = {}
        cases.append(('sea', bad, '$.scenario.sea.source'))
        bad = scenario(duration=0.0)
        bad['tanks'][0]['source'] = ''
        cases.append(('tank', bad, '$.scenario.tanks[0].source'))
        bad = scenario(duration=0.0)
        bad['connections'][0]['source'] = None
        cases.append(('connection', bad, '$.scenario.connections[0].source'))
        bad = scenario(duration=0.0)
        bad['openings'] = [{
            'id': 'opening', 'x_m': 0.0, 'y_m': 0.0, 'z_m': 5.0,
            'open': True, 'source': {}, 'estimate': False,
        }]
        cases.append(('opening', bad, '$.scenario.openings[0].source'))

        for label, bad_scenario, expected_path in cases:
            with self.subTest(location=label):
                result = flooding.simulate_flooding(
                    box_project(), 'normal', bad_scenario)
                self.assertEqual(result['status'], 'invalid_input')
                self.assertEqual(result['timeline'], [])
                self.assertTrue(any(
                    item['code'] == 'flooding.source_invalid'
                    and item['path'] == expected_path
                    and item['blocking']
                    for item in result['diagnostics']), result['diagnostics'])

    def test_model_limit_keeps_convergence_separate_from_completion(self):
        partial = scenario(duration=1.0)
        partial['connections'][0]['z_m'] = 0.9
        partial['connections'][0]['aperture_height_m'] = 0.5
        result = flooding.simulate_flooding(box_project(), 'normal', partial)
        self.assertEqual(result['status'], 'model_limit')
        self.assertFalse(result['validity']['complete'])
        self.assertFalse(result['validity']['model_applicable'])
        self.assertIs(result['validity']['numerical_convergence'], True)

    def test_late_kernel_validation_retains_resolved_identity_and_context(self):
        project = box_project()
        declared = scenario(duration=0.0)
        with mock.patch.object(
                flooding.kernel, 'evaluate_flows',
                side_effect=ValueError('injected kernel invariant')):
            result = flooding.simulate_flooding(project, 'normal', declared)
        self.assertEqual(result['status'], 'invalid_input')
        self.assertIsNotNone(result['input_fingerprint'])
        self.assertEqual(result['project_fingerprint'],
                         project_io.input_fingerprint(project))
        self.assertEqual(result['loading']['condition_id'], 'normal')
        self.assertEqual(result['scenario']['id'], 'coupled-heave')
        self.assertEqual(result['openings_origin'], 'project')
        self.assertIs(result['validity']['numerical_convergence'], True)
        self.assertTrue(any(
            item['code'] == 'flooding.invalid_input'
            and 'kernel invariant' in item['message']
            for item in result['diagnostics']))

    def test_closed_valve_keeps_free_surface_and_optional_gz_uses_current_liquid(self):
        closed = flooding.simulate_flooding(
            box_project(), 'normal', scenario(open_edge=False))
        self.assertEqual(closed['status'], 'completed')
        self.assertEqual(closed['stop_reason'], 'equal_heads_or_no_open_flow')
        self.assertEqual(len(closed['timeline']), 1)
        tank_state = closed['timeline'][0]['tanks'][0]
        self.assertTrue(tank_state['free_surface']['active'])

        gz = flooding.simulate_flooding(
            box_project(), 'normal', scenario(duration=0.0),
            options={'remaining_gz_angles_deg': [-5.0, 0.0, 5.0]})
        self.assertEqual(gz['status'], 'completed')
        self.assertTrue(gz['remaining_gz']['converged'])
        self.assertEqual([row['angle_deg'] for row in gz['remaining_gz']['rows']],
                         [-5.0, 0.0, 5.0])
        self.assertEqual(
            gz['remaining_gz']['rows'][1]['equilibrium']['effective_loading']['added_mass_t'],
            8.0*1.025)

    def test_presets_cover_required_generic_and_queen_mary_proxy_cases(self):
        path = PKG / 'cases/projects/damage-presets.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        projects = {}
        for project_path in path.parent.glob('*.project.json'):
            project = json.loads(project_path.read_text(encoding='utf-8'))
            projects[project['id']] = project
        self.assertEqual(data['schema'], 'plimsoll-flooding-presets-1')
        kinds = {preset['category'] for preset in data['presets']}
        self.assertTrue({'single', 'two_connected', 'asymmetric', 'closed_valve'} <= kinds)
        self.assertTrue(any(preset['project_id'] == 'hms-queen-mary-1913' for preset in data['presets']))
        for preset in data['presets']:
            self.assertEqual(preset['scenario']['schema'], 'plimsoll-flooding-scenario-1')
            self.assertIn('source', preset['scenario'])
            self.assertIn('estimate', preset['scenario'])
            with self.subTest(public_replay=preset['id']):
                project = projects.get(preset['project_id'])
                self.assertIsNotNone(
                    project, f"unresolved preset project_id {preset['project_id']!r}")
                self.assertIn(
                    preset['condition_id'],
                    {condition['id'] for condition in project['loading_conditions']})
                initial_only = copy.deepcopy(preset['scenario'])
                initial_only['duration_s'] = 0.0
                replay = flooding.simulate_flooding(
                    project, preset['condition_id'], initial_only)
                self.assertEqual(replay['status'], 'completed', replay)
                self.assertEqual(replay['stop_reason'], 'scheduled_completion')
                self.assertIs(replay['validity']['numerical_convergence'], True)
                if preset['project_id'] == 'generic-box-fixture':
                    self.assertEqual(project['opening_definition'], 'supplied')
                    self.assertEqual(project['openings'], [])
            if preset['project_id'] == 'hms-queen-mary-1913':
                self.assertTrue(preset['scenario']['estimate'])
                self.assertIn('proxy', json.dumps(preset['scenario']['source']).lower())


if __name__ == '__main__':
    unittest.main()
