"""Audit regressions for flooding boundaries, stability zeros and numeric range.

These tests carry the independent counter-examples of the 2026-10-09 core audit:
conservative gross-flow budgets must not masquerade as physical full/dry events
(F01), a sampled zero must not delete an observed AVS (F02), a closed valve must
not need a locked-centroid liquid plane (F10), unsupported node pressure state
must be rejected instead of silently ignored (F11), and derived flows must stay
finite for representable inputs (F20).

Fixture provenance: the flooding scenarios are the audit's own runnable
counter-examples, rebuilt here from `cases/projects/generic_flooding_box` plus
the audit's explicit tank volumes and orifice areas so that the suite stays
self-contained inside the repository.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import sys
import unittest


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
try:
    import stability
except ModuleNotFoundError:
    stability = None


GRAVITY_M_S2 = 9.80665
DENSITY_T_M3 = 1.025
DISCHARGE_COEFFICIENT = 0.6
ATTITUDE = {'heel_deg': 0.0, 'trim_deg': 0.0, 'geometry_keel_offset_m': 0.0}


class BudgetRangeReviewTests(unittest.TestCase):
    def test_unrepresentable_pressure_head_is_rejected_before_publication(self):
        sea = {**sea_node(), 'surface_offset_m': 1.7e308}
        connection = edge('range', 'sea', 't', centre_z_m=-1.7e308)
        with self.assertRaises(ValueError):
            kernel.evaluate_flows([kernel_tank('t', length_m=1, beam_m=1, height_m=10)], {'t': 1}, [connection],
                                  attitude=ATTITUDE, sea=sea, gravity_m_s2=1)
        sea['surface_offset_m'] = -1.7e308
        connection['centre_m'][2] = 1.7e308
        result = kernel.evaluate_flows([kernel_tank('t', length_m=1, beam_m=1, height_m=10)],
            {'t': 1}, [connection], attitude=ATTITUDE, sea=sea, gravity_m_s2=1)
        self.assertEqual(result['edges'][0]['from_head_m'], 0)
        self.assertEqual(result['edges'][0]['flow_m3_s'], 0)
        json.dumps(result, allow_nan=False)

    def test_mass_discharge_range_limit_is_visible_even_at_zero_duration(self):
        scenario = single_tank_scenario(volume_m3=8, duration_s=0)
        scenario['sea']['fluid_density_t_m3'] = 1e154
        scenario['tanks'][0]['fluid_density_t_m3'] = 1e154
        scenario['connections'][0].update(fluid_density_t_m3=1e154, area_m2=100)
        result = flooding.simulate_flooding(box_project(), 'normal', scenario,
                                           options={'gravity_m_s2': 1e308})
        self.assertEqual(result['status'], 'model_limit')
        self.assertIsNone(result['final_state']['flows'][0]['mass_flow_t_s'])
        json.dumps(result, allow_nan=False)

    def test_positive_remaining_volume_is_not_a_physical_boundary(self):
        for volume, source, target in ((10-5e-9, 'sea', 't'), (5e-9, 't', 'sea')):
            with self.subTest(volume=volume):
                evaluation = {'status': 'applicable', 'sea': {'id': 'sea'},
                    'tank_states': {'t': {'volume_m3': volume, 'capacity_m3': 10}},
                    'edges': [{'id': 'e', 'from_node_id': source,
                               'to_node_id': target, 'flow_m3_s': 1e-9,
                               'fluid_density_t_m3': 1.025}]}
                result = kernel.propose_transfers(evaluation, {'t': volume}, 1)
                self.assertEqual(result['status'], 'candidate')
                self.assertEqual(result['actual_dt_s'], 1)
                self.assertIsNone(result['boundary_reason'])

    def test_final_discharge_remains_representable_with_tiny_aperture(self):
        raw = kernel_tank('t', length_m=1, beam_m=1, height_m=10)
        valve = edge('e', 'sea', 't', area_m2=1e-308, centre_z_m=0)
        result = kernel.evaluate_flows([raw], {'t': 1}, [valve], attitude=ATTITUDE,
            sea={'id': 'sea', 'surface_offset_m': 1.7e308,
                 'fluid_density_t_m3': 1.025, 'source': 'analytic', 'estimate': False},
            gravity_m_s2=1.7e308)
        self.assertEqual(result['status'], 'applicable')
        self.assertAlmostEqual(result['edges'][0]['flow_m3_s'], .6*1.7*math.sqrt(2))


def box_project() -> dict:
    """The shipped analytic box used by the audit flooding counter-examples."""
    path = PKG / 'cases' / 'projects' / 'generic_flooding_box.project.json'
    return json.loads(path.read_text(encoding='utf-8'))


def tank(tank_id: str, *, length_m: float, beam_m: float, height_m: float,
         volume_m3: float, free_surface: bool = True,
         permeability: float = 1.0) -> dict:
    return {
        'id': tank_id, 'length_m': length_m, 'beam_m': beam_m,
        'height_m': height_m, 'x_m': 0.0, 'y_m': 0.0, 'keel_to_bottom_m': 0.0,
        'permeability': permeability, 'free_surface': free_surface,
        'fluid_density_t_m3': DENSITY_T_M3,
        'initial_volume_m3': volume_m3,
        'source': {'kind': 'independent_audit_fixture'}, 'estimate': False,
    }


def kernel_tank(tank_id: str, *, length_m: float, beam_m: float, height_m: float,
                free_surface: bool = True, permeability: float = 1.0) -> dict:
    row = tank(tank_id, length_m=length_m, beam_m=beam_m, height_m=height_m,
               volume_m3=0.0, free_surface=free_surface,
               permeability=permeability)
    row.pop('initial_volume_m3')
    return row


def edge(edge_id: str, source: str, target: str, *, area_m2: float = 0.1,
         centre_z_m: float = 0.1, open_edge: bool = True) -> dict:
    return {
        'id': edge_id, 'from_node_id': source, 'to_node_id': target,
        'centre_m': [0.0, 0.0, centre_z_m], 'area_m2': area_m2,
        'discharge_coefficient': DISCHARGE_COEFFICIENT,
        'fluid_density_t_m3': DENSITY_T_M3, 'open': open_edge,
        'source': {'kind': 'independent_audit_fixture'}, 'estimate': False,
    }


def connection(edge_id: str, source: str, target: str, **changes) -> dict:
    row = edge(edge_id, source, target)
    row.pop('from_node_id')
    row.pop('to_node_id')
    row['from'] = source
    row['to'] = target
    row['x_m'], row['y_m'], row['z_m'] = row.pop('centre_m')
    row.update(changes)
    return row


def sea_node(surface_offset_m: float = 3.0) -> dict:
    return {'id': 'sea', 'surface_offset_m': surface_offset_m,
            'fluid_density_t_m3': DENSITY_T_M3,
            'source': {'kind': 'independent_audit_fixture'}, 'estimate': False}


def orifice_area_m2(flow_m3_s: float, head_difference_m: float) -> float:
    """Area that produces `flow_m3_s` at `head_difference_m` for the fixture Cd."""
    return flow_m3_s/(DISCHARGE_COEFFICIENT
                      * math.sqrt(2*GRAVITY_M_S2*head_difference_m))


def scenario(*, tanks: list, connections: list, duration_s: float,
             time_step_s: float) -> dict:
    return {
        'schema': 'plimsoll-flooding-scenario-1', 'id': 'audit',
        'duration_s': duration_s, 'time_step_s': time_step_s,
        'source': {'kind': 'independent_audit_fixture'}, 'estimate': False,
        'sea': {'id': 'sea', 'fluid_density_t_m3': DENSITY_T_M3,
                'source': {'kind': 'independent_audit_fixture'}, 'estimate': False},
        'tanks': tanks, 'connections': connections,
    }


def chain_fixture(middle_volume_m3: float, low_volume_m3: float,
                  middle_inflow_m3_s: float,
                  middle_outflow_m3_s: float) -> dict:
    """Audit F01 chain: high 10x1x20 (150 m3) -> middle 1x1x10 -> low 10x1x10.

    Both orifices sit at z=0.1 m, so each orifice head difference is the plain
    difference of the two liquid surface offsets (15, middle, low/10 metres).
    """
    tanks = [
        tank('high', length_m=10.0, beam_m=1.0, height_m=20.0, volume_m3=150.0),
        tank('middle', length_m=1.0, beam_m=1.0, height_m=10.0,
             volume_m3=middle_volume_m3),
        tank('low', length_m=10.0, beam_m=1.0, height_m=10.0,
             volume_m3=low_volume_m3),
    ]
    high_depth, low_depth = 150.0/10.0, low_volume_m3/10.0
    area_in = orifice_area_m2(middle_inflow_m3_s, high_depth-middle_volume_m3)
    area_out = orifice_area_m2(middle_outflow_m3_s, middle_volume_m3-low_depth)
    connections = [
        edge('in', 'high', 'middle', area_m2=area_in),
        edge('out', 'middle', 'low', area_m2=area_out),
    ]
    return {'tanks': tanks, 'connections': connections,
            'volumes': {'high': 150.0, 'middle': middle_volume_m3,
                        'low': low_volume_m3},
            'rates': {'in': middle_inflow_m3_s, 'out': middle_outflow_m3_s},
            'areas_m2': {'in': area_in, 'out': area_out},
            'plan_area_m2': {'high': 10.0, 'middle': 1.0, 'low': 10.0},
            'capacity': {'high': 200.0, 'middle': 10.0, 'low': 100.0}}


def single_tank_scenario(*, volume_m3: float, area_m2: float = 0.1,
                         open_edge: bool = True, free_surface: bool = True,
                         height_m: float = 4.0,
                         duration_s: float = 0.5,
                         time_step_s: float = 0.25) -> dict:
    return scenario(
        tanks=[tank('a', length_m=4.0, beam_m=2.0, height_m=height_m,
                    volume_m3=volume_m3, free_surface=free_surface)],
        connections=[connection('sea-hole', 'sea', 'a', area_m2=area_m2,
                                open=open_edge)],
        duration_s=duration_s, time_step_s=time_step_s)


def box_hull(length_m=20.0, beam_m=10.0, depth_m=4.0) -> dict:
    section = [[-beam_m/2, 0.0], [beam_m/2, 0.0],
               [beam_m/2, depth_m], [-beam_m/2, depth_m]]
    return {'kind': 'offsets', 'keel_offset_m': 0.0,
            'source': {'kind': 'independent_audit_fixture'}, 'estimate': False,
            'offsets': {'schema': 'plimsoll-section-polygons-1',
                        'stations': [[x, copy.deepcopy(section)]
                                     for x in (-length_m/2, 0.0, length_m/2)]}}


def box_loading(mass_t: float, kg_m: float) -> dict:
    return {'complete_mass': True, 'complete_cg': True,
            'input_fingerprint': 'independent-audit-fixture',
            'condition_id': 'selected', 'project_id': 'box', 'diagnostics': [],
            'provenance': {'estimate': False}, 'uncertainty': {'status': 'unknown'},
            'values': {'total_mass_t': mass_t, 'lcg_m': 0.0, 'tcg_m': 0.0,
                       'kg_m': kg_m},
            'coverage': {'reference_displacement_t': mass_t*9}}


def blocking(result, code, path=None):
    return [item for item in result['diagnostics']
            if item['code'] == code and item['blocking']
            and (path is None or item['path'] == path)]


class GrossBudgetBoundaryTests(unittest.TestCase):
    """F01: conservative gross budgets are step limits, not physical events."""

    def setUp(self) -> None:
        self.assertIsNotNone(kernel, 'private flooding kernel is not implemented')
        self.assertIsNotNone(flooding, 'public flooding API is not implemented')

    def euler_oracle(self, fixture, duration_s=6.0):
        """Independent explicit-Euler oracle for the F01 chain.

        Orifice rates are frozen inside one accepted step and recomputed from the
        moved liquid surfaces for the next one. Steps are bounded by the same
        conservative per-tank budgets (room/inflow, volume/outflow), so the oracle
        never assumes the initial rates persist over the whole duration.
        """
        areas, plan, capacity = (fixture['areas_m2'], fixture['plan_area_m2'],
                                 fixture['capacity'])
        state, elapsed, times = dict(fixture['volumes']), 0.0, [0.0]

        def discharge(area_m2, head_m):
            return (DISCHARGE_COEFFICIENT*area_m2
                    * math.sqrt(2*GRAVITY_M_S2*head_m))

        while elapsed < duration_s-1e-12:
            depth = {k: state[k]/plan[k] for k in state}
            inflow = discharge(areas['in'], depth['high']-depth['middle'])
            outflow = discharge(areas['out'], depth['middle']-depth['low'])
            step = min(duration_s-elapsed,
                       (capacity['middle']-state['middle'])/inflow,
                       state['middle']/outflow)
            state = {'high': state['high']-inflow*step,
                     'middle': state['middle']+(inflow-outflow)*step,
                     'low': state['low']+outflow*step}
            elapsed += step
            times.append(elapsed)
        return state, times

    def assert_volumes(self, actual, expected):
        for tank_id, value in expected.items():
            self.assertAlmostEqual(actual[tank_id], value, places=6,
                                   msg=f'tank {tank_id!r}')

    def assert_timeline(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        self.assertEqual(actual[0], 0.0)
        self.assertAlmostEqual(actual[-1], expected[-1], places=9)
        for got, want in zip(actual[1:-1], expected[1:-1]):
            self.assertAlmostEqual(got, want, places=6)

    def test_proposal_keeps_the_step_limit_but_reports_no_boundary(self):
        for name, middle, low, rate_in, rate_out in (
                ('false_receiver_capacity', 9.0, 10.0, 0.2, 0.1),
                ('false_source_dry', 1.0, 1.0, 0.1, 0.2)):
            with self.subTest(case=name):
                fixture = chain_fixture(middle, low, rate_in, rate_out)
                evaluation = kernel.evaluate_flows(
                    fixture['tanks'], fixture['volumes'], fixture['connections'],
                    attitude=ATTITUDE)
                self.assertAlmostEqual(evaluation['edges'][0]['flow_m3_s'],
                                       rate_in, places=12)
                self.assertAlmostEqual(evaluation['edges'][1]['flow_m3_s'],
                                       rate_out, places=12)
                proposal = kernel.propose_transfers(
                    evaluation, fixture['volumes'], 6.0)
                # The gross budget still bounds one explicit step at 1/rate, but
                # the accepted net state is neither empty nor at capacity.
                self.assertEqual(proposal['status'], 'candidate')
                self.assertAlmostEqual(proposal['actual_dt_s'],
                                       min(6.0, 1.0/max(rate_in, rate_out)),
                                       places=9)
                self.assertIsNone(proposal['boundary_reason'])
                self.assertIsNone(proposal['stop_reason'])
                middle_after = fixture['volumes']['middle']+(
                    rate_in-rate_out)*proposal['actual_dt_s']
                self.assertTrue(0.0 < middle_after < fixture['capacity']['middle'])

                step = kernel.step_fixed_attitude(
                    fixture['tanks'], fixture['volumes'], fixture['connections'],
                    attitude=ATTITUDE, requested_dt_s=6.0)
                self.assertEqual(step['status'], 'advanced')
                self.assertIsNone(step['stop_reason'])
                self.assertAlmostEqual(step['actual_dt_s'], 5.0, places=9)
                self.assertLessEqual(abs(step['volume_conservation_error_m3']), 1e-12)
                self.assertLessEqual(abs(step['mass_conservation_error_t']), 1e-12)

    def test_fixed_attitude_runs_past_the_gross_budget_to_the_duration(self):
        for name, middle, low, rate_in, rate_out in (
                ('false_receiver_capacity', 9.0, 10.0, 0.2, 0.1),
                ('false_source_dry', 1.0, 1.0, 0.1, 0.2)):
            with self.subTest(case=name):
                fixture = chain_fixture(middle, low, rate_in, rate_out)
                expected, times = self.euler_oracle(fixture)
                run = kernel.simulate_fixed_attitude(
                    fixture['tanks'], fixture['volumes'], fixture['connections'],
                    attitude=ATTITUDE, duration_s=6.0, requested_dt_s=6.0)
                self.assertEqual(run['status'], 'completed', run['stop_reason'])
                self.assertEqual(run['stop_reason'], 'scheduled_completion')
                self.assertAlmostEqual(run['elapsed_time_s'], 6.0, places=9)
                self.assert_timeline([row['time_s'] for row in run['timeline']],
                                     times)
                self.assert_volumes(run['final_volumes_m3'], expected)
                self.assertLessEqual(abs(run['volume_conservation_error_m3']), 1e-12)
                self.assertLessEqual(abs(run['mass_conservation_error_t']), 1e-12)

    def test_coupled_chain_completes_the_requested_six_seconds(self):
        for name, middle, low, rate_in, rate_out in (
                ('false_receiver_capacity', 9.0, 10.0, 0.2, 0.1),
                ('false_source_dry', 1.0, 1.0, 0.1, 0.2)):
            with self.subTest(case=name):
                fixture = chain_fixture(middle, low, rate_in, rate_out)
                expected, times = self.euler_oracle(fixture)
                public = scenario(
                    tanks=fixture['tanks'],
                    connections=[connection(row['id'], row['from_node_id'],
                                        row['to_node_id'],
                                        area_m2=row['area_m2'],
                                        z_m=row['centre_m'][2])
                                 for row in fixture['connections']],
                    duration_s=6.0, time_step_s=6.0)
                result = flooding.simulate_flooding(
                    box_project(), 'normal', public)
                self.assertEqual(result['status'], 'completed', result['stop_reason'])
                self.assertEqual(result['stop_reason'], 'scheduled_completion')
                self.assertIs(result['validity']['complete'], True)
                self.assert_timeline([row['time_s'] for row in result['timeline']],
                                     times)
                self.assert_volumes(result['final_state']['volumes_m3'],
                                    expected)
                self.assertLessEqual(abs(result['volume_conservation_error_m3']), 1e-9)
                self.assertLessEqual(abs(result['mass_conservation_error_t']), 1e-9)
                accepted_middle = result['final_state']['volumes_m3']['middle']
                self.assertTrue(0.0 < accepted_middle < fixture['capacity']['middle'])

    def test_genuine_capacity_and_dry_out_events_are_preserved(self):
        # Sea above a tank that is exactly full: net inflow, no accepted room.
        sea = {'id': 'sea', 'surface_offset_m': 6.0,
               'fluid_density_t_m3': DENSITY_T_M3,
               'source': {'kind': 'fixture'}, 'estimate': False}
        full = kernel_tank('full', length_m=10.0, beam_m=1.0, height_m=5.0)
        blocked = kernel.step_fixed_attitude(
            [full], {'full': 50.0}, [edge('fill', 'sea', 'full', centre_z_m=0.0)],
            attitude=ATTITUDE, sea=sea, requested_dt_s=1.0)
        self.assertEqual(blocked['status'], 'model_limit')
        self.assertEqual(blocked['stop_reason'], 'receiver_capacity')
        self.assertAlmostEqual(blocked['volumes_m3']['full'], 50.0, places=12)

        # A partially full receiver reaches capacity exactly at the accepted
        # state of the conservative step: that is a real boundary event.
        almost = kernel.step_fixed_attitude(
            [full], {'full': 49.0}, [edge('fill', 'sea', 'full', centre_z_m=0.0)],
            attitude=ATTITUDE, sea=sea, requested_dt_s=10.0)
        self.assertEqual(almost['status'], 'advanced')
        self.assertEqual(almost['stop_reason'], 'receiver_capacity')
        self.assertAlmostEqual(almost['volumes_m3']['full'], 50.0, places=9)
        self.assertLessEqual(abs(almost['volume_conservation_error_m3']), 1e-12)
        follow_up = kernel.step_fixed_attitude(
            [full], {'full': 50.0}, [edge('fill', 'sea', 'full', centre_z_m=0.0)],
            attitude=ATTITUDE, sea=sea, requested_dt_s=10.0)
        self.assertEqual(follow_up['status'], 'model_limit')
        self.assertEqual(follow_up['stop_reason'], 'receiver_capacity')

        # Draining a tank to empty is still a genuine source_dry event: the accepted
        # net drain ends on the boundary rather than only on a gross budget.
        below = {**sea, 'surface_offset_m': -1.0}
        drain_edges = [edge('drain', 'full', 'sea', centre_z_m=0.0)]
        drain_evaluation = kernel.evaluate_flows(
            [full], {'full': 1.0}, drain_edges, attitude=ATTITUDE, sea=below)
        drained = kernel.propose_transfers(drain_evaluation, {'full': 1.0}, 100.0)
        self.assertEqual(drained['status'], 'candidate')
        self.assertEqual(drained['boundary_reason'], 'source_dry')
        self.assertLessEqual(drained['volumes_m3']['full'], 1e-9)
        self.assertLessEqual(abs(drained['sea_exchange_m3']+1.0), 1e-9)
        self.assertEqual([row['transfer_m3'] for row in drained['edge_transfers']],
                         [1.0-(drained['volumes_m3']['full'])])
        emptied = kernel.step_fixed_attitude(
            [full], {'full': 0.0}, [edge('drain', 'full', 'sea', centre_z_m=0.0)],
            attitude=ATTITUDE, sea=below, requested_dt_s=10.0)
        self.assertAlmostEqual(emptied['volumes_m3']['full'], 0.0, places=12)

        # Public sea-fed flooding still terminates at a real capacity limit.
        # The 4x2x1 m tank holds 8 m3 (1 m level) while the outside waterline
        # stays near 2 m, so the sea head can reach the tank ceiling; the last
        # accepted step is the conservative budget that lands on capacity.
        public = flooding.simulate_flooding(
            box_project(), 'normal',
            single_tank_scenario(volume_m3=7.0, area_m2=0.1, height_m=1.0,
                                 duration_s=5.0, time_step_s=0.25))
        self.assertEqual(public['status'], 'model_limit', public['stop_reason'])
        self.assertEqual(public['stop_reason'], 'receiver_capacity')
        self.assertGreater(public['final_state']['time_s'], 0.0)
        self.assertAlmostEqual(public['final_state']['volumes_m3']['a'], 8.0,
                               places=9)
        self.assertLessEqual(abs(public['volume_conservation_error_m3']), 1e-9)


class SampledZeroStabilityTests(unittest.TestCase):
    """F02: sampled near-zero rows keep the observed positive-to-negative AVS."""

    KG_M = 3.2637555892261814

    def setUp(self) -> None:
        self.assertIsNotNone(stability, 'loaded stability API is not implemented')

    def curve(self, angles, *, openings=(), mass_t=410.0, kg_m=None):
        return stability.stability_curve(
            box_hull(), box_loading(mass_t, self.KG_M if kg_m is None else kg_m),
            list(angles), openings=list(openings))

    def test_sampled_zero_grid_and_neighbour_grid_agree_on_sixty_degrees(self):
        sampled = self.curve([0, 30, 60, 70, 80])
        self.assertTrue(sampled['converged'])
        self.assertEqual([row['angle_deg'] for row in sampled['rows']],
                         [0.0, 30.0, 60.0, 70.0, 80.0])
        self.assertTrue(all(row['equilibrium']['converged'] for row in sampled['rows']))
        near_zero = sampled['rows'][2]['gz_m']
        self.assertLess(abs(near_zero), 1e-8)
        self.assertGreater(sampled['rows'][1]['gz_m'], 1e-8)
        self.assertLess(sampled['rows'][3]['gz_m'], -1e-8)
        self.assertIsNotNone(sampled['avs_deg'], 'observed AVS was lost')
        self.assertAlmostEqual(sampled['avs_deg'], 60.0, places=9)
        self.assertEqual(len(sampled['zero_crossings']), 1)
        root = sampled['zero_crossings'][0]
        self.assertEqual(root['direction'], 'positive_to_negative')
        self.assertIs(root['intact_valid'], True)
        # The root is bracketed by the resolved neighbours that span the run.
        self.assertLessEqual(root['bracket_deg'][0], 30.0)
        self.assertGreaterEqual(root['bracket_deg'][1], 70.0)

        control = self.curve([0, 30, 59, 61, 70, 80])
        self.assertAlmostEqual(control['avs_deg'], 60.0, places=9)
        self.assertEqual([row['angle_deg'] for row in control['rows'][:-1]],
                         [0.0, 30.0, 59.0, 61.0, 70.0])

    def test_multiple_sampled_near_zero_rows_still_resolve_one_root(self):
        # |dGZ/dangle| is about 4.2e-2 m/deg here, so samples within 2e-7 deg of
        # the 60 deg root are inside the 1e-8 m near-zero band.
        angles = [0, 30, 60-1e-7, 60, 60+1e-7, 70, 80]
        result = self.curve(angles)
        self.assertTrue(result['converged'])
        self.assertTrue(all(abs(row['gz_m']) < 1e-8
                            for row in result['rows'][2:5]))
        self.assertEqual(len(result['zero_crossings']), 1)
        self.assertAlmostEqual(result['zero_crossings'][0]['angle_deg'], 60.0,
                               places=7)
        self.assertIsNotNone(result['avs_deg'], 'observed AVS was lost')
        self.assertAlmostEqual(result['avs_deg'], 60.0, places=7)

    def test_unstable_upright_curve_keeps_no_crossing_or_avs(self):
        # Sealed 20x10x4 box at half displacement with KG=6.0 m: the sampled
        # upright stiffness is negative, GZ(0)=0 exactly and every other sample
        # is negative, so the startup zero run carries no crossing at all.
        result = self.curve([0, 2, 5, 10, 20, 30, 40], kg_m=6.0)
        self.assertTrue(result['converged'])
        self.assertLess(result['initial_stiffness_m'], 0.0)
        self.assertEqual(result['rows'][0]['gz_m'], 0.0)
        self.assertTrue(all(row['gz_m'] < -1e-8 for row in result['rows'][1:]))
        self.assertEqual(result['zero_crossings'], [])
        self.assertIsNone(result['avs_deg'])
        self.assertEqual(result['endpoint']['kind'], 'nonpositive_sample')

    def test_bracket_across_a_near_zero_run_respects_downflooding(self):
        # The resolved positive sample is at 5 degrees, a run of near-zero samples
        # brackets 60 degrees, and the deck-edge opening immerses at about 21.8
        # degrees, so the resolved root is real but not intact.
        openings = [{'id': 'edge', 'open': True, 'x_m': 0.0, 'y_m': 5.0,
                     'z_m': 4.0}]
        angles = [0, 5, 60-1e-7, 60, 60+1e-7, 61, 80]
        result = self.curve(angles, openings=openings)
        self.assertIsNotNone(result['downflooding'])
        self.assertAlmostEqual(result['downflooding']['angle_deg'],
                               math.degrees(math.atan(0.4)), places=6)
        self.assertEqual(len(result['zero_crossings']), 1)
        root = result['zero_crossings'][0]
        self.assertEqual(root['direction'], 'positive_to_negative')
        self.assertEqual(root['bracket_deg'], [5.0, 61.0])
        self.assertIs(root['intact_valid'], False)
        self.assertIsNone(result['avs_deg'])

    def test_failed_samples_break_the_run_without_fabricating_a_root(self):
        result = self.curve([0, 30, 60, 86, 88, 90])
        self.assertFalse(result['converged'])
        self.assertEqual(result['zero_crossings'], [])
        self.assertIsNone(result['avs_deg'])
        self.assertEqual(result['endpoint']['kind'], 'model_limit')
        self.assertFalse(result['rows'][-1]['validity']['model_applicable'])

    def test_root_after_downflooding_stays_intact_invalid(self):
        openings = [{'id': 'edge', 'open': True, 'x_m': 0.0, 'y_m': 5.0,
                     'z_m': 2.5}]
        result = self.curve([0, 30, 60, 70, 80], openings=openings)
        self.assertIsNotNone(result['downflooding'])
        self.assertAlmostEqual(result['downflooding']['angle_deg'],
                               math.degrees(math.atan(0.1)), places=6)
        self.assertEqual(len(result['zero_crossings']), 1)
        self.assertIs(result['zero_crossings'][0]['intact_valid'], False)
        self.assertIsNone(result['avs_deg'])


class LockedCentroidTests(unittest.TestCase):
    """F10: closed valves never need a liquid plane that does not exist."""

    def setUp(self) -> None:
        self.assertIsNotNone(kernel, 'private flooding kernel is not implemented')
        self.assertIsNotNone(flooding, 'public flooding API is not implemented')

    def locked_tank(self, volume_m3=8.0):
        return kernel_tank('a', length_m=4.0, beam_m=2.0, height_m=4.0,
                           free_surface=False)

    def test_closed_edge_keeps_state_without_evaluating_a_liquid_plane(self):
        tanks = [self.locked_tank()]
        connections = [edge('sea-hole', 'sea', 'a', open_edge=False)]
        evaluation = kernel.evaluate_flows(
            tanks, {'a': 8.0}, connections, attitude=ATTITUDE, sea=sea_node())
        self.assertEqual(evaluation['status'], 'applicable')
        row = evaluation['edges'][0]
        self.assertEqual(row['status'], 'closed')
        self.assertEqual(row['flow_m3_s'], 0.0)
        self.assertIsNone(row['from_head_m'])
        self.assertIsNone(row['to_head_m'])
        self.assertEqual(evaluation['diagnostics'], [])

        # The closed edge still validates the tank state and geometry.
        with self.assertRaisesRegex(ValueError, 'capacity'):
            kernel.evaluate_flows(
                tanks, {'a': 40.0}, connections, attitude=ATTITUDE,
                sea=sea_node())
        broken = [{**tanks[0], 'height_m': 0.0}]
        with self.assertRaises((ValueError, TypeError, KeyError)):
            kernel.evaluate_flows(
                broken, {'a': 8.0}, connections, attitude=ATTITUDE,
                sea=sea_node())

    def test_closed_locked_scenario_settles_with_the_proxy_warning(self):
        result = flooding.simulate_flooding(
            box_project(), 'normal',
            single_tank_scenario(volume_m3=8.0, open_edge=False,
                                 free_surface=False))
        self.assertEqual(result['status'], 'completed', result['diagnostics'])
        self.assertEqual(result['stop_reason'], 'equal_heads_or_no_open_flow')
        self.assertIs(result['validity']['complete'], True)
        self.assertIs(result['validity']['model_applicable'], True)
        self.assertEqual(len(result['timeline']), 1)
        self.assertEqual(result['final_state']['volumes_m3'], {'a': 8.0})
        self.assertEqual(result['final_state']['time_s'], 0.0)
        flow = result['final_state']['flows'][0]
        self.assertEqual(flow['flow_m3_s'], 0.0)
        self.assertIsNone(flow['from_head_m'])
        liquid = result['final_state']['tanks'][0]
        self.assertEqual(liquid['method'], 'locked_centroid_proxy')
        self.assertTrue(any(item['code'] == 'liquid.locked_centroid_proxy'
                            for item in liquid['diagnostics']))
        json.dumps(result, allow_nan=False)

    def test_open_edge_on_a_locked_proxy_is_an_explicit_model_limit(self):
        result = flooding.simulate_flooding(
            box_project(), 'normal',
            single_tank_scenario(volume_m3=8.0, free_surface=False))
        self.assertEqual(result['status'], 'invalid_input')
        self.assertIs(result['validity']['model_applicable'], False)
        self.assertEqual(result['timeline'], [])
        diagnostics = blocking(
            result, 'flooding.locked_centroid_open_connection',
            '$.scenario.connections[0]')
        self.assertEqual(len(diagnostics), 1, result['diagnostics'])
        self.assertIn('free_surface', diagnostics[0]['message'])
        self.assertFalse([item for item in result['diagnostics']
                          if 'TypeError' in item['message']
                          or 'operand type' in item['message']])

        evaluation = kernel.evaluate_flows(
            [self.locked_tank()], {'a': 8.0},
            [edge('sea-hole', 'sea', 'a')], attitude=ATTITUDE,
            sea={'id': 'sea', 'surface_offset_m': 3.0,
                 'fluid_density_t_m3': DENSITY_T_M3,
                 'source': {'kind': 'fixture'}, 'estimate': False})
        self.assertEqual(evaluation['status'], 'model_limit')
        self.assertIsNone(evaluation['edges'][0]['flow_m3_s'])
        self.assertEqual([item['code'] for item in evaluation['diagnostics']],
                         ['flooding.liquid_plane_unsupported'])
        self.assertTrue(evaluation['diagnostics'][0]['blocking'])


class UnsupportedPressureTests(unittest.TestCase):
    """F11: recognized pressure state is rejected on every scenario node."""

    PRESSURE_KEYS = ('pressure_pa', 'from_pressure_pa', 'to_pressure_pa',
                     'air_pressure_pa')

    def setUp(self) -> None:
        self.assertIsNotNone(kernel, 'private flooding kernel is not implemented')
        self.assertIsNotNone(flooding, 'public flooding API is not implemented')

    def test_public_scenario_rejects_pressure_on_sea_tank_and_connection(self):
        containers = (
            ('sea', lambda fixture, key: fixture['sea'].__setitem__(key, 200000.0),
             '$.scenario.sea.{}'),
            ('tank', lambda fixture, key: fixture['tanks'][0].__setitem__(key, 200000.0),
             '$.scenario.tanks[0].{}'),
            ('connection',
             lambda fixture, key: fixture['connections'][0].__setitem__(key, 200000.0),
             '$.scenario.connections[0].{}'),
        )
        for container, mutate, template in containers:
            for key in self.PRESSURE_KEYS:
                with self.subTest(container=container, field=key):
                    fixture = single_tank_scenario(volume_m3=8.0, duration_s=0.0)
                    mutate(fixture, key)
                    result = flooding.simulate_flooding(
                        box_project(), 'normal', fixture)
                    self.assertEqual(result['status'], 'invalid_input')
                    self.assertIs(result['validity']['complete'], False)
                    self.assertIs(result['validity']['model_applicable'], False)
                    self.assertEqual(result['timeline'], [])
                    diagnostics = blocking(result, 'flooding.pressure_unsupported',
                                           template.format(key))
                    self.assertEqual(len(diagnostics), 1, result['diagnostics'])

    def test_kernel_entry_points_reject_pressure_state(self):
        sea = {'id': 'sea', 'surface_offset_m': 3.0,
               'fluid_density_t_m3': DENSITY_T_M3,
               'source': {'kind': 'fixture'}, 'estimate': False}
        for key in self.PRESSURE_KEYS:
            with self.subTest(field=key, node='tank'):
                tanks = [kernel_tank('a', length_m=10.0, beam_m=1.0, height_m=5.0)]
                tanks[0][key] = 200000.0
                with self.assertRaisesRegex(ValueError, key):
                    kernel.evaluate_flows(
                        tanks, {'a': 10.0},
                        [edge('sea-hole', 'sea', 'a', centre_z_m=0.0)],
                        attitude=ATTITUDE, sea=sea)
            with self.subTest(field=key, node='sea'):
                pressured = {**sea, key: 200000.0}
                with self.assertRaisesRegex(ValueError, key):
                    kernel.evaluate_flows(
                        [kernel_tank('a', length_m=10.0, beam_m=1.0, height_m=5.0)],
                        {'a': 10.0},
                        [edge('sea-hole', 'sea', 'a', centre_z_m=0.0)],
                        attitude=ATTITUDE, sea=pressured)
            with self.subTest(field=key, node='connection'):
                connections = [edge('sea-hole', 'sea', 'a', centre_z_m=0.0)]
                connections[0][key] = 200000.0
                with self.assertRaisesRegex(ValueError, key):
                    kernel.evaluate_flows(
                        [kernel_tank('a', length_m=10.0, beam_m=1.0, height_m=5.0)],
                        {'a': 10.0}, connections, attitude=ATTITUDE, sea=sea)

    def test_supported_metadata_is_still_accepted(self):
        fixture = single_tank_scenario(volume_m3=8.0, duration_s=0.0)
        fixture['tanks'][0]['note'] = 'inert audit metadata'
        fixture['sea']['comment'] = 'inert audit metadata'
        result = flooding.simulate_flooding(box_project(), 'normal', fixture)
        self.assertEqual(result['status'], 'completed', result['diagnostics'])
        self.assertIs(result['validity']['model_applicable'], True)


class DerivedFlowRangeTests(unittest.TestCase):
    """F20: finite inputs keep representable flows and bound the rest."""

    def setUp(self) -> None:
        self.assertIsNotNone(kernel, 'private flooding kernel is not implemented')
        self.assertIsNotNone(flooding, 'public flooding API is not implemented')

    def extreme_case(self, *, area_m2, gravity_m_s2):
        # Sea surface 3 m above a 10x1x5 m tank holding 10 m3 (1 m deep), so the
        # orifice head difference is exactly 2 m.
        sea = {'id': 'sea', 'surface_offset_m': 3.0,
               'fluid_density_t_m3': DENSITY_T_M3,
               'source': {'kind': 'fixture'}, 'estimate': False}
        tanks = [kernel_tank('a', length_m=10.0, beam_m=1.0, height_m=5.0)]
        connections = [edge('sea-hole', 'sea', 'a', area_m2=area_m2,
                            centre_z_m=0.0)]
        return kernel.evaluate_flows(tanks, {'a': 10.0}, connections,
                                     attitude=ATTITUDE, sea=sea,
                                     gravity_m_s2=gravity_m_s2)

    def test_ordinary_gravity_keeps_the_exact_orifice_formula(self):
        ordinary = self.extreme_case(area_m2=0.1, gravity_m_s2=GRAVITY_M_S2)
        row = ordinary['edges'][0]
        difference = row['from_head_m']-row['to_head_m']
        self.assertEqual(row['flow_m3_s'],
                         DISCHARGE_COEFFICIENT*0.1
                         * math.sqrt(2*GRAVITY_M_S2*difference))
        self.assertAlmostEqual(difference, 2.0, places=9)

    def test_representable_extreme_gravity_flow_is_finite(self):
        evaluation = self.extreme_case(area_m2=0.1, gravity_m_s2=1e308)
        expected = DISCHARGE_COEFFICIENT*0.1*math.sqrt(1e308)*math.sqrt(2*2.0)
        self.assertEqual(evaluation['status'], 'applicable')
        self.assertTrue(math.isfinite(expected))
        flow = evaluation['edges'][0]['flow_m3_s']
        self.assertTrue(math.isfinite(flow), repr(flow))
        self.assertTrue(math.isclose(flow, expected, rel_tol=1e-12),
                        f'{flow!r} != {expected!r}')
        self.assertEqual(evaluation['diagnostics'], [])

    def test_unrepresentable_derived_flow_is_a_structured_model_limit(self):
        evaluation = self.extreme_case(area_m2=1e300, gravity_m_s2=1e308)
        self.assertEqual(evaluation['status'], 'model_limit')
        self.assertIsNone(evaluation['edges'][0]['flow_m3_s'])
        self.assertEqual([item['code'] for item in evaluation['diagnostics']],
                         ['flooding.derived_flow_out_of_range'])
        self.assertTrue(evaluation['diagnostics'][0]['blocking'])

    def test_public_zero_duration_extreme_gravity_is_finite_and_serializable(self):
        result = flooding.simulate_flooding(
            box_project(), 'normal',
            single_tank_scenario(volume_m3=8.0, duration_s=0.0),
            options={'gravity_m_s2': 1e308})
        flow = result['final_state']['flows'][0]
        difference = flow['from_head_m']-flow['to_head_m']
        self.assertGreater(difference, 0.0)
        expected = (DISCHARGE_COEFFICIENT*0.1*math.sqrt(1e308)
                    * math.sqrt(2*difference))
        self.assertTrue(math.isclose(flow['flow_m3_s'], expected, rel_tol=1e-12),
                        f"{flow['flow_m3_s']!r} != {expected!r}")
        self.assertTrue(math.isfinite(flow['mass_flow_t_s']))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['stop_reason'], 'scheduled_completion')
        json.dumps(result, allow_nan=False)

    def test_public_unrepresentable_gravity_is_not_reported_complete(self):
        result = flooding.simulate_flooding(
            box_project(), 'normal',
            single_tank_scenario(volume_m3=8.0, area_m2=1e300, duration_s=0.0),
            options={'gravity_m_s2': 1e308})
        self.assertEqual(result['status'], 'model_limit')
        self.assertIs(result['validity']['complete'], False)
        self.assertIs(result['validity']['model_applicable'], False)
        self.assertEqual(result['stop_reason'], 'derived_flow_out_of_range')
        self.assertEqual(
            [item['code'] for item in result['diagnostics']],
            ['flooding.derived_flow_out_of_range'])
        json.dumps(result, allow_nan=False)

    def test_extreme_gravity_keeps_every_accepted_transfer_bounded(self):
        # The conservative budget limits one step at 2 m3 of head, so even an
        # extreme declared gravity cannot produce an unrepresentable transfer.
        evaluation = self.extreme_case(area_m2=0.1, gravity_m_s2=1e308)
        proposal = kernel.propose_transfers(evaluation, {'a': 10.0}, 1e156)
        self.assertEqual(proposal['status'], 'candidate')
        self.assertTrue(math.isfinite(proposal['actual_dt_s']))
        self.assertLess(proposal['actual_dt_s'], 1e-150)
        for row in proposal['edge_transfers']:
            self.assertTrue(math.isfinite(row['transfer_m3']), repr(row))
            self.assertLessEqual(row['transfer_m3'], 40.0)
        self.assertLessEqual(proposal['volumes_m3']['a'], 50.0)
        self.assertTrue(math.isfinite(proposal['sea_exchange_t']))

    def test_unrepresentable_mass_ledger_is_a_structured_range_limit(self):
        # Finite but extreme explicit density makes the declared mass ledger
        # unrepresentable; no volume or mass figure may be published.
        density = 1e308
        tanks = [{**kernel_tank('a', length_m=10.0, beam_m=1.0, height_m=5.0),
                  'fluid_density_t_m3': density}]
        connections = [{**edge('sea-hole', 'sea', 'a', centre_z_m=0.0),
                        'fluid_density_t_m3': density}]
        sea = {**sea_node(), 'fluid_density_t_m3': density}
        proposal = kernel.propose_transfers(
            kernel.evaluate_flows(tanks, {'a': 10.0}, connections,
                                  attitude=ATTITUDE, sea=sea),
            {'a': 10.0}, 100.0)
        self.assertEqual(proposal['status'], 'model_limit')
        self.assertEqual(proposal['stop_reason'], 'numeric_out_of_range')
        self.assertEqual(proposal['volumes_m3'], {'a': 10.0})
        self.assertEqual(proposal['edge_transfers'], [])
        step = kernel.step_fixed_attitude(
            tanks, {'a': 10.0}, connections, attitude=ATTITUDE, sea=sea,
            requested_dt_s=100.0)
        self.assertEqual(step['status'], 'model_limit')
        self.assertEqual(step['stop_reason'], 'numeric_out_of_range')
        self.assertEqual(step['volumes_m3'], {'a': 10.0})


if __name__ == '__main__':
    unittest.main()
