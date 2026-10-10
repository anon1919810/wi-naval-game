"""Convergence-study oracle, fixture and runner contracts.

The study itself lives in tools/plimsoll/tools/convergence_study.py and its
independent oracles in docs/plimsoll-1.0/evidence. Nothing here imports a
repository test module to build a fixture.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import unittest.mock


HERE = Path(__file__).resolve().parent
PKG = HERE.parent
TOOLS = PKG / 'tools'
REPO = PKG.parent.parent
for _entry in (str(PKG), str(TOOLS)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE_PATH = REPO / 'docs/plimsoll-1.0/evidence/wall_sided_box_oracle.py'
FIXTURE_PATH = TOOLS / 'convergence_fixtures.py'
STUDY_PATH = TOOLS / 'convergence_study.py'

wall_sided = _load_module('wall_sided_box_oracle', ORACLE_PATH)

try:
    import convergence_fixtures
except ImportError:  # Reported by the fixture tests, not by this import guard.
    convergence_fixtures = None

try:
    import convergence_study
except ImportError:  # Reported by the runner tests, not by this import guard.
    convergence_study = None


def _run_python(script):
    completed = subprocess.run(
        [sys.executable, '-c', script], capture_output=True)
    return (completed.returncode,
            completed.stdout.decode('utf-8', 'replace'),
            completed.stderr.decode('utf-8', 'replace'))


class WallSidedBoxOracleTests(unittest.TestCase):
    """The new GZ oracle must be analytic, bounded and independently checked."""

    def setUp(self):
        self.oracle = wall_sided.oracle()

    def test_declared_parameters_and_valid_range(self):
        answer = self.oracle
        self.assertEqual(answer['geometry_m']['length_m'], 40.0)
        self.assertEqual(answer['geometry_m']['beam_m'], 10.0)
        self.assertEqual(answer['geometry_m']['depth_m'], 10.0)
        self.assertEqual(answer['loading']['draft_m'], 4.0)
        self.assertEqual(answer['loading']['kg_m'], 3.0)
        self.assertEqual(answer['loading']['rho_t_m3'], 1.025)
        self.assertAlmostEqual(answer['loading']['mass_t'], 1640.0, places=12)
        self.assertAlmostEqual(answer['derived']['bm_m'], 100.0 / 48.0, places=15)
        self.assertAlmostEqual(
            answer['derived']['gm_m'], 4.0 / 2.0 + 100.0 / 48.0 - 3.0, places=15)
        # abs(tan(phi))*B/2 < min(T, depth-T) limits the wedge to tan(phi) < 0.8
        self.assertAlmostEqual(answer['valid_range']['limit_deg'],
                               math.degrees(math.atan(0.8)), places=12)
        self.assertAlmostEqual(answer['valid_range']['min_deg'],
                               -math.degrees(math.atan(0.8)), places=12)

    def test_analytic_lever_at_zero_and_thirty_degrees(self):
        gm, bm = 13.0 / 12.0, 25.0 / 12.0
        self.assertEqual(wall_sided.gz_m(0.0), 0.0)
        expected = (gm + bm * math.tan(math.radians(30.0)) ** 2 / 2.0) * math.sin(
            math.radians(30.0))
        self.assertAlmostEqual(wall_sided.gz_m(30.0), expected, places=15)
        self.assertAlmostEqual(wall_sided.gz_m(30.0), 0.7152777777777778, places=12)
        self.assertAlmostEqual(
            wall_sided.gz_m(-30.0), -wall_sided.gz_m(30.0), places=15)
        self.assertEqual(self.oracle['derived']['gm_m'], wall_sided.gm_m())
        self.assertEqual(self.oracle['derived']['bm_m'], wall_sided.bm_m())

    def test_bounds_rejection_is_explicit(self):
        self.assertTrue(wall_sided.bounds_ok(30.0))
        self.assertFalse(wall_sided.bounds_ok(45.0))
        self.assertFalse(wall_sided.bounds_ok(-45.0))
        self.assertFalse(wall_sided.bounds_ok(float('nan')))
        self.assertAlmostEqual(
            wall_sided.maximum_angle_deg(), math.degrees(math.atan(0.8)), places=12)
        self.assertEqual(wall_sided.require_valid_angle_deg(30.0), 30.0)
        for bad in (45.0, -45.0, 90.0, float('nan'), float('inf'), None, '30'):
            with self.subTest(angle=bad), self.assertRaises(ValueError):
                wall_sided.require_valid_angle_deg(bad)
        for bad in (float('nan'), float('inf'), None, '30'):
            with self.subTest(angle=bad), self.assertRaises(ValueError):
                wall_sided.gz_m(bad)

    def test_exact_area_matches_independent_simpson_integration(self):
        exact = wall_sided.exact_area_m_rad(30.0)
        self.assertEqual(wall_sided.exact_area_m_rad(0.0), 0.0)
        numeric = wall_sided.simpson_area_m_rad(30.0, intervals=2000)
        self.assertAlmostEqual(exact, numeric, places=12)
        self.assertAlmostEqual(exact, 0.16672866898736885, places=12)
        gm, bm = 13.0 / 12.0, 25.0 / 12.0
        angle = math.radians(30.0)
        self.assertAlmostEqual(
            exact, gm * (1.0 - math.cos(angle))
            + bm / 2.0 * (1.0 / math.cos(angle) + math.cos(angle) - 2.0),
            places=15)

    def test_closed_form_area_has_the_declared_derivative(self):
        # d(area)/d(angle in degrees) is the lever per degree, that is
        # gz_m(angle)*pi/180. Differencing the closed form therefore recovers
        # the analytic lever and would expose a wrong primitive.
        step = 1e-6
        for angle in (5.0, 20.0, 30.0):
            with self.subTest(angle=angle):
                derivative = (wall_sided.exact_area_m_rad(angle + step)
                              - wall_sided.exact_area_m_rad(angle - step)) / (2.0 * step)
                self.assertAlmostEqual(derivative,
                                       wall_sided.gz_m(angle) * math.pi / 180.0,
                                       places=8)

    def test_oracle_reports_its_provenance_and_limits(self):
        self.assertIn('not_solver_result', self.oracle['kind'])
        json.dumps(self.oracle, allow_nan=False)
        self.assertTrue(self.oracle['derivation'])
        self.assertTrue(self.oracle['limitations'])
        self.assertEqual(self.oracle['imports_plimsoll_code'], False)

    def test_oracle_module_imports_no_plimsoll_code(self):
        script = (
            'import importlib.util, json, sys\n'
            f'spec = importlib.util.spec_from_file_location("wall_sided_box_oracle", r"{ORACLE_PATH}")\n'
            'module = importlib.util.module_from_spec(spec)\n'
            'spec.loader.exec_module(module)\n'
            'module.oracle()\n'
            'module.gz_m(30.0)\n'
            'module.simpson_area_m_rad(30.0, 64)\n'
            f'root = r"{PKG}"\n'
            'loaded = sorted(name for name, value in sys.modules.items()\n'
            '                if getattr(value, "__file__", None)\n'
            '                and str(root) in str(value.__file__))\n'
            'print(json.dumps(loaded))\n'
        )
        code, out, err = _run_python(script)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out.strip().splitlines()[-1]), [])


class FixtureTests(unittest.TestCase):
    """Fixtures are deterministic, fresh and never shared between callers."""

    def setUp(self):
        self.assertIsNotNone(convergence_fixtures,
                             'convergence fixtures are not implemented')

    def test_ellipsoid_geometry_is_fresh_deterministic_and_immutable(self):
        first = convergence_fixtures.ellipsoid_geometry(41, 32)
        second = convergence_fixtures.ellipsoid_geometry(41, 32)
        self.assertIsNot(first, second)
        original = json.dumps(second, sort_keys=True)
        self.assertEqual(json.dumps(first, sort_keys=True), original)
        first['offsets']['stations'][3][1][2][0] = 123.0
        self.assertNotEqual(json.dumps(first, sort_keys=True), original)
        self.assertEqual(json.dumps(second, sort_keys=True), original)
        self.assertEqual(json.dumps(convergence_fixtures.ellipsoid_geometry(41, 32),
                                    sort_keys=True), original)

    def test_ellipsoid_mesh_follows_the_declared_analytic_ellipse(self):
        stations, vertices = 41, 32
        record = convergence_fixtures.ellipsoid_geometry(stations, vertices)
        table = record['offsets']['stations']
        self.assertEqual(len(table), stations)
        self.assertEqual(table[0][0], -20.0)
        self.assertEqual(table[-1][0], 20.0)
        self.assertEqual(table[0][1], [[0.0, 5.0]] * vertices)
        middle = table[(stations - 1) // 2]
        self.assertAlmostEqual(middle[0], 0.0, places=12)
        self.assertEqual(middle[1][0], [5.0, 5.0])
        self.assertAlmostEqual(middle[1][vertices // 4][0], 0.0, places=12)
        self.assertEqual(middle[1][vertices // 4][1], 10.0)
        for j, (y, z) in enumerate(middle[1]):
            angle = 2.0 * math.pi * j / vertices
            self.assertAlmostEqual(y, 5.0 * math.cos(angle), places=12)
            self.assertAlmostEqual(z, 5.0 + 5.0 * math.sin(angle), places=12)
        # cosine longitudinal clustering: the refined mesh reaches further
        # before its first interior station, so its end spacing is finer
        coarse = convergence_fixtures.ellipsoid_geometry(stations, vertices)
        dense = convergence_fixtures.ellipsoid_geometry(161, vertices)
        coarse_end = coarse['offsets']['stations'][1][0] - coarse['offsets']['stations'][0][0]
        dense_end = dense['offsets']['stations'][1][0] - dense['offsets']['stations'][0][0]
        self.assertLess(dense_end, coarse_end)
        self.assertEqual(record['offsets']['schema'], 'plimsoll-section-polygons-1')
        self.assertEqual(record['kind'], 'offsets')
        self.assertEqual(record['keel_offset_m'], 0.0)

    def test_box_and_loading_fixtures_are_sealed_empty_and_fresh(self):
        hull = convergence_fixtures.box_geometry()
        again = convergence_fixtures.box_geometry()
        self.assertIsNot(hull, again)
        self.assertEqual(hull, again)
        original = json.dumps(again, sort_keys=True)
        hull['offsets']['stations'][5][1][0][1] = 99.0
        self.assertEqual(json.dumps(convergence_fixtures.box_geometry(),
                                    sort_keys=True), original)
        table = hull['offsets']['stations']
        self.assertEqual(len(table), 21)
        self.assertEqual(table[0][0], -20.0)
        self.assertEqual(table[-1][0], 20.0)
        self.assertEqual(table[10][1], [[-5.0, 0.0], [5.0, 0.0],
                                        [5.0, 10.0], [-5.0, 10.0]])
        loading = convergence_fixtures.box_loading()
        self.assertIs(loading['complete_mass'], True)
        self.assertIs(loading['complete_cg'], True)
        self.assertEqual(loading['values']['total_mass_t'], 1640.0)
        self.assertEqual(loading['values']['kg_m'], 3.0)
        self.assertEqual(convergence_fixtures.box_loading(), loading)

    def test_flooding_fixtures_are_fresh_and_serialisable(self):
        project = convergence_fixtures.flooding_project()
        again = convergence_fixtures.flooding_project()
        self.assertIsNot(project, again)
        self.assertEqual(project, again)
        original = json.dumps(again, sort_keys=True, allow_nan=False)
        project['weight_groups'][0]['items'][0]['mass_t'] = 1.0
        self.assertEqual(
            json.dumps(convergence_fixtures.flooding_project(),
                       sort_keys=True, allow_nan=False), original)
        self.assertEqual(project['geometry']['offsets']['stations'][0][0], -10.0)
        self.assertEqual(len(project['geometry']['offsets']['stations']), 21)
        scenario = convergence_fixtures.flooding_scenario(0.25)
        self.assertEqual(scenario['schema'], 'plimsoll-flooding-scenario-1')
        self.assertEqual(scenario['duration_s'], 5.0)
        self.assertEqual(scenario['time_step_s'], 0.25)
        self.assertEqual(scenario['tanks'][0]['initial_volume_m3'], 8.0)
        self.assertEqual(scenario['connections'][0]['area_m2'], 0.1)
        self.assertEqual(scenario['connections'][0]['discharge_coefficient'], 0.6)
        self.assertEqual(scenario['connections'][0]['z_m'], 0.1)
        json.dumps(scenario, allow_nan=False)
        self.assertEqual(convergence_fixtures.flooding_scenario(0.25), scenario)
        self.assertNotEqual(convergence_fixtures.flooding_scenario(0.125),
                            scenario)

    def test_fixture_provenance_declares_units_and_sources(self):
        provenance = convergence_fixtures.fixture_provenance()
        json.dumps(provenance, allow_nan=False)
        self.assertEqual(provenance['study_id'], 'numerical-convergence-2026-10-10')
        self.assertEqual(provenance['ellipsoid']['semi_axes_m'], [20.0, 5.0, 5.0])
        self.assertEqual(provenance['ellipsoid']['kg_m'], 3.0)
        self.assertEqual(provenance['box']['mass_t'], 1640.0)
        self.assertEqual(provenance['flooding']['duration_s'], 5.0)
        self.assertIn('coupled_ellipsoid_oracles.py', provenance['oracle_sources'])
        self.assertIn('flooding_oracles.py', provenance['oracle_sources'])
        self.assertIn('wall_sided_box_oracle.py', provenance['oracle_sources'])
        self.assertTrue(provenance['imports_test_modules'] is False)

    def test_fixtures_build_in_a_clean_interpreter_without_test_modules(self):
        script = (
            'import json, sys\n'
            f'sys.path.insert(0, r"{TOOLS}")\n'
            'import convergence_fixtures\n'
            'convergence_fixtures.ellipsoid_geometry(5, 8)\n'
            'convergence_fixtures.box_geometry()\n'
            'convergence_fixtures.box_loading()\n'
            'convergence_fixtures.flooding_project()\n'
            'convergence_fixtures.flooding_scenario(0.5)\n'
            'convergence_fixtures.fixture_provenance()\n'
            f'root = r"{PKG}"\n'
            'loaded = sorted(name for name, value in sys.modules.items()\n'
            '                if getattr(value, "__file__", None)\n'
            '                and str(root) in str(value.__file__))\n'
            'print(json.dumps(loaded))\n'
        )
        code, out, err = _run_python(script)
        self.assertEqual(code, 0, err)
        loaded = json.loads(out.strip().splitlines()[-1])
        self.assertEqual([name for name in loaded if name.startswith('test')], [])


TINY_GEOMETRY_SEQUENCE = [{
    'name': 'probe',
    'refined_parameter': 'longitudinal_stations',
    'fixed_parameter': {'section_vertices': 16},
    'levels': [{'longitudinal_stations': 17, 'section_vertices': 16}],
}]


def _failed_curve(hull, state, angles_deg, openings=None, options=None):
    """A curve whose every sample is an explicit solver failure."""
    return {
        'method_version': 'injected_failure', 'converged': False,
        'rows': [dict(angle_deg=angle, gz_m=None,
                      equilibrium={'converged': False, 'diagnostics': []},
                      validity={'model_applicable': False})
                 for angle in angles_deg],
        'zero_crossings': [], 'avs_deg': None, 'maximum': None,
        'initial_stiffness_m': None, 'diagnostics': [], 'downflooding': None,
        'input_fingerprint': None,
        'endpoint': {'kind': 'failed_sample', 'angle_deg': angles_deg[-1],
                     'gz_m': None},
    }


def _non_finite_curve(hull, state, angles_deg, openings=None, options=None):
    """A curve that claims convergence while reporting NaN levers."""
    nan = float('nan')
    return {
        'method_version': 'injected_non_finite', 'converged': True,
        'rows': [dict(angle_deg=angle, gz_m=nan,
                      equilibrium={'converged': True, 'diagnostics': []},
                      validity={'model_applicable': True})
                 for angle in angles_deg],
        'zero_crossings': [], 'avs_deg': None,
        'maximum': {'kind': 'sampled_maximum', 'angle_deg': angles_deg[-1],
                    'gz_m': nan},
        'initial_stiffness_m': None, 'diagnostics': [], 'downflooding': None,
        'input_fingerprint': None,
        'endpoint': {'kind': 'positive_sample', 'angle_deg': angles_deg[-1],
                     'gz_m': nan},
    }


class _StudyTestCase(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(convergence_study,
                             'convergence study runner is not implemented')


class StudyReportContractTests(_StudyTestCase):
    """Required metadata, error metrics, orders and declared thresholds."""

    @classmethod
    def setUpClass(cls):
        if convergence_study is None:  # pragma: no cover - import guard
            raise unittest.SkipTest('convergence_study is not implemented')
        cls.report = convergence_study.run_study(suite='gz')

    def test_required_metadata_is_present_and_json_safe(self):
        report = self.report
        self.assertEqual(report['schema'], 'plimsoll-convergence-study-1')
        self.assertEqual(report['study']['id'], 'numerical-convergence-2026-10-10')
        self.assertEqual(report['study']['suite'], 'gz')
        self.assertIn('generated_utc', report['study'])
        self.assertTrue(report['study']['runtime']['version'])
        self.assertEqual(report['study']['network_access'], 'none')
        self.assertIs(report['study']['writes_production_state'], False)
        self.assertTrue(report['units'])
        self.assertTrue(report['fixtures']['oracle_sources'])
        self.assertTrue(report['method_versions'])
        self.assertTrue(report['limitations'])
        self.assertIn('oracle_answers', report)
        # A conforming report must never carry NaN or Infinity.
        json.dumps(report, allow_nan=False)

    def test_source_identity_covers_kernels_fixtures_oracles_and_study(self):
        sources = self.report['sources']
        required = [
            'tools/plimsoll/stability.py', 'tools/plimsoll/geometry.py',
            'tools/plimsoll/flooding.py', 'tools/plimsoll/_flooding_kernel.py',
            'tools/plimsoll/loading.py', 'tools/plimsoll/project_io.py',
            'tools/plimsoll/tank_geometry.py', 'tools/plimsoll/offsets.py',
            'tools/plimsoll/tools/convergence_fixtures.py',
            'tools/plimsoll/tools/convergence_study.py',
            'docs/plimsoll-1.0/evidence/coupled_ellipsoid_oracles.py',
            'docs/plimsoll-1.0/evidence/flooding_oracles.py',
            'docs/plimsoll-1.0/evidence/wall_sided_box_oracle.py',
        ]
        for path in required:
            self.assertIn(path, sources, path)
            self.assertEqual(len(sources[path]['sha256']), 64, path)
            self.assertTrue(sources[path]['role'])
        # The generated evidence must never hash itself or the written report.
        for path in sources:
            self.assertNotIn('numerical-convergence-study.', path)
            self.assertNotIn('convergence-study.json', path)
        self.assertIs(self.report['source_integrity']['unchanged'], True)
        self.assertEqual(self.report['source_integrity']['changed'], [])

    def test_declared_thresholds_are_published_before_the_run(self):
        gz = self.report['suites']['gz']
        self.assertEqual(gz['declared_thresholds']['fixed_angle_absolute_m'], 1e-6)
        self.assertEqual(gz['declared_thresholds']['finest_area_relative'], 1e-4)
        self.assertIs(gz['declared_thresholds']['area_errors_decrease'], True)
        for name, value in gz['declared_thresholds'].items():
            self.assertIsInstance(value, (int, float, bool), name)

    def test_every_sample_reports_absolute_relative_error_and_order(self):
        levels = self.report['suites']['gz']['levels']
        self.assertGreaterEqual(len(levels), 2)
        first, second = levels[0], levels[1]
        area_first = first['curve_area']['relative_area_error']
        area_second = second['curve_area']['relative_area_error']
        self.assertIsInstance(area_first, float)
        self.assertIsInstance(area_second, float)
        self.assertLess(area_second, area_first)
        self.assertAlmostEqual(second['curve_area']['observed_order'], 2.0,
                               delta=0.35)
        self.assertEqual(first['curve_area']['observed_order'], None)
        self.assertEqual(first['curve_area']['observed_order_status'],
                         'unavailable_no_previous_level')
        for level in levels:
            sample = level['fixed_angle']
            self.assertEqual(len(sample['samples']), level['sample_count'])
            self.assertIsNotNone(sample['max_abs_error_m'])
            self.assertLessEqual(sample['max_abs_error_m'], 1e-6)

    def test_fixed_angle_accuracy_and_curve_area_are_distinct_metrics(self):
        level = self.report['suites']['gz']['levels'][-1]
        self.assertIn('max_abs_error_m', level['fixed_angle'])
        self.assertIn('max_abs_error_common_angles_m', level['fixed_angle'])
        self.assertIn('relative_area_error', level['curve_area'])
        self.assertIn('observed_order', level['curve_area'])
        self.assertNotIn('relative_area_error', level['fixed_angle'])
        self.assertNotIn('max_abs_error_m', level['curve_area'])
        # The two metrics are numerically different quantities, not copies.
        self.assertGreater(level['curve_area']['relative_area_error'], 0.0)
        self.assertLess(level['fixed_angle']['max_abs_error_m'],
                        level['curve_area']['relative_area_error'])
        self.assertIn('sampled_maximum', level)
        self.assertIn('endpoint', level)
        self.assertEqual(level['endpoint']['kind'], 'positive_sample')
        self.assertEqual(level['sample_count'],
                         len(level['fixed_angle']['samples']))

    def test_fixtures_and_sources_are_proven_unmutated(self):
        for level in self.report['suites']['gz']['levels']:
            self.assertEqual(level['fixture_sha256_before'],
                             level['fixture_sha256_after'])
            self.assertIs(level['fixture_unchanged'], True)

    def test_acceptance_reports_every_declared_check(self):
        acceptance = self.report['acceptance']
        self.assertIn('passed', acceptance)
        self.assertIsInstance(acceptance['checks'], list)
        self.assertTrue(acceptance['checks'])
        for check in acceptance['checks']:
            for key in ('suite', 'name', 'requirement', 'passed'):
                self.assertIn(key, check)
        self.assertEqual(acceptance['passed'],
                         all(check['passed'] for check in acceptance['checks']))
        self.assertEqual(self.report['status'],
                         'pass' if acceptance['passed'] else 'fail')


class GeometryErrorMetricTests(_StudyTestCase):
    """Zero references and non-finite values must never become a zero error."""

    def test_zero_reference_keeps_absolute_error_only(self):
        suite = convergence_study.run_geometry_suite(
            sequences=TINY_GEOMETRY_SEQUENCE)
        level = suite['sequences'][0]['levels'][0]
        lever = level['evaluations']['free_equilibrium']['metrics']['gz_m']
        self.assertEqual(lever['reference'], 0.0)
        self.assertIsNotNone(lever['absolute_error'])
        self.assertIsNone(lever['relative_error'])
        self.assertEqual(lever['relative_error_status'], 'zero_reference')
        self.assertEqual(lever['status'], 'ok')

    def test_declared_geometry_thresholds_and_observed_orders(self):
        suite = convergence_study.run_geometry_suite()
        declared = suite['declared_thresholds']
        self.assertEqual(declared['finest_volume_relative'], 1e-3)
        self.assertEqual(declared['finest_buoyancy_centre_absolute_m'], 0.01)
        self.assertEqual(declared['finest_waterline_d_absolute_m'], 0.01)
        self.assertEqual(declared['finest_trim_slope_absolute'], 1e-4)
        self.assertEqual(declared['finest_prescribed_gz_absolute_m'], 1e-3)
        self.assertEqual(declared['scaled_residual_max'], 1e-6)
        names = {sequence['refined_parameter'] for sequence in suite['sequences']}
        self.assertEqual(names,
                         {'longitudinal_stations', 'section_vertices'})
        for sequence in suite['sequences']:
            self.assertEqual(len(sequence['levels']), 3)
            for level in sequence['levels']:
                self.assertEqual(level['status'], 'completed')
                for name in ('direct_plane', 'free_equilibrium',
                             'prescribed_heel'):
                    evaluation = level['evaluations'][name]
                    if name == 'direct_plane':
                        # A direct plane integration has no equilibrium solve,
                        # so there is no scaled solver residual to report.
                        self.assertIsNone(evaluation['max_abs_scaled_residual'])
                        continue
                    self.assertIsNotNone(evaluation['max_abs_scaled_residual'])
                    self.assertLessEqual(
                        evaluation['max_abs_scaled_residual'], 1e-6)


class FailedSampleRetentionTests(_StudyTestCase):
    """Failed and non-finite samples survive in the report and fail acceptance."""

    def test_failed_samples_are_retained_and_never_scored_as_zero(self):
        report = convergence_study.run_study(
            suite='gz', hooks={'stability_curve': _failed_curve,
                               'levels': [5.0, 2.5]})
        levels = report['suites']['gz']['levels']
        self.assertEqual(len(levels), 2)
        self.assertEqual([level['sample_count'] for level in levels], [7, 13])
        for level in levels:
            self.assertEqual(level['status'], 'failed')
            self.assertEqual(level['fixed_angle']['converged_samples'], 0)
            for sample in level['fixed_angle']['samples']:
                self.assertEqual(sample['status'], 'failed_sample')
                self.assertIsNone(sample['computed_gz_m'])
                self.assertIsNone(sample['absolute_error_m'])
            self.assertIsNone(level['fixed_angle']['max_abs_error_m'])
            self.assertIsNone(level['curve_area']['relative_area_error'])
            self.assertIsNone(level['curve_area']['observed_order'])
        self.assertIs(report['acceptance']['passed'], False)
        self.assertEqual(report['status'], 'fail')
        self.assertTrue(report['acceptance']['failed'])
        json.dumps(report, allow_nan=False)

    def test_non_finite_samples_are_flagged_and_fail_acceptance(self):
        report = convergence_study.run_study(
            suite='gz', hooks={'stability_curve': _non_finite_curve,
                               'levels': [5.0]})
        level = report['suites']['gz']['levels'][0]
        self.assertEqual(level['status'], 'non_finite')
        for sample in level['fixed_angle']['samples']:
            self.assertEqual(sample['status'], 'failed_sample')
            self.assertEqual(sample['failure_reason'], 'non_finite_lever')
            self.assertIsNone(sample['computed_gz_m'])
            self.assertIsNone(sample['absolute_error_m'])
        self.assertIsNone(level['fixed_angle']['max_abs_error_m'])
        self.assertIs(report['acceptance']['passed'], False)
        self.assertEqual(report['status'], 'fail')
        json.dumps(report, allow_nan=False)

    def test_acceptance_never_partially_passes(self):
        report = convergence_study.run_study(
            suite='gz', hooks={'stability_curve': _failed_curve,
                               'levels': [5.0, 2.5]})
        failed = [check['name'] for check in report['acceptance']['checks']
                  if not check['passed']]
        self.assertTrue(failed)
        self.assertFalse(report['acceptance']['passed'])
        self.assertEqual(sorted(report['acceptance']['failed']),
                         sorted(failed))


class GeometryRefinementTests(_StudyTestCase):
    """Refinement ratios must coarsen, and orders must not vanish silently."""

    @classmethod
    def setUpClass(cls):
        if convergence_study is None:  # pragma: no cover - import guard
            raise unittest.SkipTest('convergence_study is not implemented')
        cls.suite = convergence_study.run_geometry_suite()

    def test_refinement_ratio_is_fine_over_coarse_and_never_inverted(self):
        for sequence in self.suite['sequences']:
            levels = sequence['levels']
            self.assertIsNone(levels[0]['refinement_ratio_to_previous'])
            for previous, current in zip(levels, levels[1:]):
                ratio = current['refinement_ratio_to_previous']
                self.assertIsNotNone(ratio)
                self.assertGreater(ratio, 1.0, sequence['name'])
                # Station meshes refine per interval (n-1), vertex meshes per node.
                count = (lambda n: n - 1 if sequence['refined_parameter']
                         == 'longitudinal_stations' else n)
                expected = (count(current['refinement'][sequence['refined_parameter']])
                            / count(previous['refinement'][sequence['refined_parameter']]))
                self.assertAlmostEqual(ratio, expected, places=12)

    def test_order_availability_matches_the_recorded_error_pairs(self):
        # An order needs this level's error and the previous level's error to
        # both be positive and finite. Anything else must report unavailable
        # with its own reason rather than a dropped or invented number.
        for sequence in self.suite['sequences']:
            for evaluation in ('direct_plane', 'free_equilibrium',
                               'prescribed_heel'):
                orders = sequence['observed_orders'][f'{evaluation}.volume_m3']
                levels = sequence['levels']
                self.assertEqual(len(orders), len(levels))
                for index, (level, order) in enumerate(zip(levels, orders)):
                    metric = level['evaluations'][evaluation]['metrics'][
                        'volume_m3']
                    error = metric['absolute_error']
                    usable = error is not None and error > 0.0
                    if not usable:
                        self.assertIsNone(order, index)
                        self.assertIsNone(metric['observed_order'])
                        self.assertTrue(metric['observed_order_status'])
                        continue
                    previous = (levels[index - 1]['evaluations'][evaluation]
                                ['metrics']['volume_m3']
                                if index else None)
                    previous_usable = bool(
                        previous and previous['absolute_error']
                        and previous['absolute_error'] > 0.0)
                    if index and previous_usable:
                        self.assertIsInstance(order, float)
                    else:
                        self.assertIsNone(order, index)

    def test_equilibrium_constraints_do_not_classify_unconstrained_errors(self):
        # Volume and free-GZ satisfy equilibrium constraints. Prescribed GZ
        # does not: a small error cannot identify its source as round-off.
        for sequence in self.suite['sequences']:
            interpretation = sequence['order_interpretation']['metrics']
            direct = [order for order in
                      sequence['observed_orders']['direct_plane.volume_m3'][1:]
                      if order is not None]
            self.assertTrue(direct)
            for order in direct:
                self.assertGreater(order, 0.0)
            self.assertEqual(
                interpretation['direct_plane.volume_m3']['classification'],
                'fixed_plane_mesh_comparison')
            solved = interpretation['free_equilibrium.volume_m3']
            self.assertEqual(solved['classification'], 'equilibrium_constraint')
            self.assertIsNotNone(solved['solver_tolerance_scale'])
            self.assertGreater(solved['characteristic_scale'], 0.0)
            prescribed = interpretation['prescribed_heel.gz_m']
            self.assertEqual(prescribed['classification'], 'mixed_error_unclassified')
            self.assertIsNone(prescribed['solver_tolerance_scale'])

    def test_floor_relative_orders_expose_the_refined_axis(self):
        for sequence in self.suite['sequences']:
            diagnostic = sequence['finest_mesh_comparison']
            self.assertIs(diagnostic['available'], True)
            orders = diagnostic['observed_orders']
            self.assertIn('direct_plane.volume_m3', orders)
            for value in orders['direct_plane.volume_m3']:
                self.assertIsNotNone(value)
                self.assertGreater(value, 1.5)

    def test_non_finite_error_pairs_never_produce_an_observed_order(self):
        # NaN is never a usable error, whichever comparison a future edit uses.
        for previous, current in ((float('nan'), 1.0), (1.0, float('nan')),
                                  (float('inf'), 1.0), (1.0, float('inf')),
                                  (float('-inf'), 1.0)):
            with self.subTest(previous=previous, current=current):
                order, status = convergence_study._observed_order(
                    previous, current, 2.0)
                self.assertIsNone(order)
                self.assertEqual(status, 'unavailable_non_finite_error_pair')

    def test_geometry_sequence_order_matches_the_gz_and_flooding_convention(self):
        # Cross-suite: the same helper must coarsen everywhere.
        gz = convergence_study.run_gz_suite(levels=[5.0, 2.5, 1.25])
        ratios = [level['curve_area']['refinement_ratio_to_previous']
                  for level in gz['levels']]
        self.assertEqual(ratios, [None, 2.0, 2.0])
        flooding = convergence_study.run_flooding_suite(levels=[0.5, 0.25])
        self.assertEqual(
            [level['refinement_ratio_to_previous']
             for level in flooding['levels']], [None, 2.0])


class GeometryIntegrityTests(_StudyTestCase):
    """A failed or non-finite geometry sample must never pass acceptance."""

    @staticmethod
    def _perfect_plane(reference):
        def plane(_hull, _p, _q, _d):
            return dict(volume=reference['volume_m3'],
                        xlcb=reference['buoyancy_centre_m'][0],
                        yb=reference['buoyancy_centre_m'][1],
                        zb=reference['buoyancy_centre_m'][2])
        return plane

    @staticmethod
    def _perfect_solver(reference):
        def solve(_hull, _state, options):
            prescribed = options.get('heel_deg') is not None
            # Component names must match the public solver's scaled residual.
            scaled = {'volume': 0.0, 'longitudinal': 0.0}
            if not prescribed:
                scaled['transverse'] = 0.0
            return dict(
                converged=True, volume_m3=reference['volume_m3'],
                buoyancy_centre_m=reference['buoyancy_centre_m'],
                p=reference['p'], q=reference['q'], waterline_d_m=reference['d_m'],
                gz_m=reference['prescribed_gz_m'] if prescribed else 0.0,
                residuals={'scaled': scaled},
                solver={}, diagnostics=[], mode='prescribed' if prescribed else 'free')
        return solve

    def test_perfect_synthetic_answers_pass(self):
        # The controls above must genuinely pass, otherwise the negative
        # probes below would prove nothing.
        reference = convergence_study._geometry_reference(
            convergence_study._load_oracle(
                'coupled_ellipsoid_oracles.py').oracle())
        suite = convergence_study.run_geometry_suite(
            hooks={'evaluate_plane': self._perfect_plane(reference),
                   'solve_equilibrium': self._perfect_solver(reference)})
        self.assertIs(suite['passed'], True, suite['checks'])

    def test_changed_input_hashes_fail_each_suite_and_the_study(self):
        reference = convergence_study._geometry_reference(
            convergence_study._load_oracle('coupled_ellipsoid_oracles.py').oracle())

        def mutate_plane(hull, *args):
            hull['source']['changed_during_calculation'] = True
            return self._perfect_plane(reference)(hull, *args)

        geometry_report = convergence_study.run_study('geometry', hooks={
            'sequences': TINY_GEOMETRY_SEQUENCE, 'evaluate_plane': mutate_plane,
            'solve_equilibrium': self._perfect_solver(reference)})
        self.assertIs(geometry_report['acceptance']['passed'], False)
        self.assertIs(geometry_report['suites']['geometry']['passed'], False)
        self.assertIs(geometry_report['suites']['geometry']['fixture_unchanged'], False)

        real_curve = convergence_study.stability.stability_curve

        def toggle_curve(hull, *args):
            answer = real_curve(hull, *args)
            if hull['source'].pop('changed_during_calculation', None) is None:
                hull['source']['changed_during_calculation'] = True
            return answer

        gz_report = convergence_study.run_study('gz', hooks={'stability_curve': toggle_curve})
        self.assertIs(gz_report['acceptance']['passed'], False)
        self.assertIs(gz_report['suites']['gz']['passed'], False)
        # Four changes restore the global payload, but each call still mutated it.
        self.assertEqual(gz_report['suites']['gz']['fixture_sha256_before'],
                         gz_report['suites']['gz']['fixture_sha256_after'])

        flood_reference = FloodingIntegrityTests()._reference()
        valid_flood = FloodingIntegrityTests._good_run(flood_reference)

        def mutate_flood(project, *args, **kwargs):
            project['changed_during_calculation'] = True
            return valid_flood(project, *args, **kwargs)

        flood_report = convergence_study.run_study('flooding', hooks={'simulate_flooding': mutate_flood})
        self.assertIs(flood_report['acceptance']['passed'], False)
        self.assertIs(flood_report['suites']['flooding']['passed'], False)

    def test_nan_direct_buoyancy_centre_keeps_its_failure_reason(self):
        reference = convergence_study._geometry_reference(
            convergence_study._load_oracle('coupled_ellipsoid_oracles.py').oracle())

        def non_finite_plane(*args):
            raw = self._perfect_plane(reference)(*args)
            raw['xlcb'] = float('nan')
            return raw

        suite = convergence_study.run_geometry_suite(
            sequences=TINY_GEOMETRY_SEQUENCE,
            hooks={'evaluate_plane': non_finite_plane,
                   'solve_equilibrium': self._perfect_solver(reference)})
        self.assertIs(suite['passed'], False)
        evaluation = suite['sequences'][0]['levels'][0]['evaluations']['direct_plane']
        self.assertEqual(evaluation['status'], 'non_finite')
        metric = evaluation['metrics']['buoyancy_centre_x_m']
        self.assertEqual(metric['status'], 'computed_non_finite')
        self.assertIsNone(metric['computed'])
        self.assertIsNone(metric['absolute_error'])

    def test_a_failed_coarse_level_fails_acceptance_despite_a_fine_pass(self):
        reference = convergence_study._geometry_reference(
            convergence_study._load_oracle(
                'coupled_ellipsoid_oracles.py').oracle())
        plane = self._perfect_plane(reference)
        state = {'calls': 0}

        def failing_plane(*args):
            state['calls'] += 1
            if state['calls'] == 1:
                raise ValueError('injected coarse failure')
            return plane(*args)

        suite = convergence_study.run_geometry_suite(
            hooks={'evaluate_plane': failing_plane,
                   'solve_equilibrium': self._perfect_solver(reference)})
        self.assertIs(suite['passed'], False)
        first = suite['sequences'][0]['levels'][0]
        self.assertEqual(first['evaluations']['direct_plane']['status'], 'error')
        self.assertEqual(first['status'], 'error')
        # Every later level must still be retained, not silently skipped.
        self.assertEqual(len(suite['sequences'][0]['levels']), 3)
        for name, metric in first['evaluations']['direct_plane']['metrics'].items():
            self.assertIsNone(metric['computed'], name)
            self.assertIsNone(metric['absolute_error'], name)
            self.assertIsNone(metric['relative_error'], name)
        # An order may not be formed across the broken level.
        orders = suite['sequences'][0]['observed_orders'][
            'direct_plane.volume_m3']
        self.assertIsNone(orders[1],
                          'order reused an earlier error across a failure')

    def test_a_non_finite_residual_component_fails_the_suite(self):
        reference = convergence_study._geometry_reference(
            convergence_study._load_oracle(
                'coupled_ellipsoid_oracles.py').oracle())

        def nan_residual(*args):
            raw = self._perfect_solver(reference)(*args)
            raw['residuals']['scaled']['transverse'] = float('nan')
            return raw

        suite = convergence_study.run_geometry_suite(
            hooks={'evaluate_plane': self._perfect_plane(reference),
                   'solve_equilibrium': nan_residual})
        self.assertIs(suite['passed'], False)
        first = suite['sequences'][0]['levels'][0]
        evaluation = first['evaluations']['free_equilibrium']
        self.assertEqual(evaluation['status'], 'residual_unavailable')
        self.assertIn('transverse',
                      evaluation['non_finite_residual_components'])
        self.assertIsNone(evaluation['max_abs_scaled_residual'],
                          'a NaN component was filtered out instead of failing')
        self.assertTrue(any('residual' in note for note in evaluation['notes']))

    def test_recovered_geometry_level_cannot_bridge_a_failed_middle_level(self):
        reference = convergence_study._geometry_reference(
            convergence_study._load_oracle('coupled_ellipsoid_oracles.py').oracle())
        errors = iter((1.0, None, 0.25, 0.125))

        def interrupted_plane(*args):
            error = next(errors)
            if error is None:
                raise ValueError('injected middle-level failure')
            raw = self._perfect_plane(reference)(*args)
            raw['volume'] += error
            return raw

        sequence = {'name': 'interrupted',
                    'refined_parameter': 'longitudinal_stations',
                    'fixed_parameter': {'section_vertices': 8},
                    'levels': [{'longitudinal_stations': n}
                               for n in (5, 9, 17, 33)]}
        suite = convergence_study.run_geometry_suite(
            sequences=[sequence], hooks={
                'evaluate_plane': interrupted_plane,
                'solve_equilibrium': self._perfect_solver(reference)})
        self.assertIs(suite['passed'], False)
        retained = suite['sequences'][0]
        with self.subTest(series='raw'):
            orders = retained['observed_orders']['direct_plane.volume_m3']
            self.assertIsNone(orders[2])
            self.assertAlmostEqual(orders[3], 1.0)
        with self.subTest(series='finest_mesh_comparison'):
            orders = retained['finest_mesh_comparison']['observed_orders'].get(
                'direct_plane.volume_m3', [])
            self.assertFalse(any(order is not None for order in orders))

    def test_a_missing_required_metric_is_unavailable_and_fails(self):
        reference = convergence_study._geometry_reference(
            convergence_study._load_oracle(
                'coupled_ellipsoid_oracles.py').oracle())

        def missing_metric(*args):
            raw = self._perfect_solver(reference)(*args)
            raw['residuals'] = {'scaled': {'volume': 0.0}}
            return raw

        suite = convergence_study.run_geometry_suite(
            hooks={'evaluate_plane': self._perfect_plane(reference),
                   'solve_equilibrium': missing_metric})
        self.assertIs(suite['passed'], False)

    def test_declared_truthful_boolean_not_truthy_value(self):
        # A non-boolean convergence claim must not count as converged.
        reference = convergence_study._geometry_reference(
            convergence_study._load_oracle(
                'coupled_ellipsoid_oracles.py').oracle())

        def string_converged(*args):
            raw = self._perfect_solver(reference)(*args)
            raw['converged'] = 'yes'
            return raw

        suite = convergence_study.run_geometry_suite(
            hooks={'evaluate_plane': self._perfect_plane(reference),
                   'solve_equilibrium': string_converged})
        self.assertIs(suite['passed'], False)

    def test_non_finite_convergence_claim_keeps_serializable_failure_evidence(self):
        reference = convergence_study._geometry_reference(
            convergence_study._load_oracle('coupled_ellipsoid_oracles.py').oracle())
        for value in (float('nan'), float('inf')):
            with self.subTest(value=value):
                def invalid_claim(*args, value=value):
                    raw = self._perfect_solver(reference)(*args)
                    raw['converged'] = value
                    return raw
                report = convergence_study.run_study('geometry', hooks={
                    'sequences': TINY_GEOMETRY_SEQUENCE,
                    'evaluate_plane': self._perfect_plane(reference),
                    'solve_equilibrium': invalid_claim})
                self.assertIs(report['acceptance']['passed'], False)
                json.dumps(report, allow_nan=False)
                self.assertEqual(convergence_study.exit_code_for(report), 1)
                with tempfile.TemporaryDirectory() as folder:
                    files = convergence_study.write_evidence(report, folder)
                    retained = json.loads(files['json'].read_text(encoding='utf-8'))
                    self.assertEqual(retained['status'], 'fail')
                    self.assertIn('geometry.every_declared_state_converged',
                                  retained['acceptance']['failed'])
                    for name in ('csv', 'markdown'):
                        self.assertIn(str(value), files[name].read_text(
                            encoding='utf-8'))


class GzIntegrityTests(_StudyTestCase):
    """GZ applicability, convergence and quadrature must stay distinguishable."""

    @staticmethod
    def _curve(kind='normal', mutate=None, drop_angle=None):
        def curve(_hull, _state, angles, _openings=None, options=None):
            rows = []
            for angle in angles:
                if drop_angle is not None and angle == drop_angle:
                    rows.append({'angle_deg': angle, 'gz_m': None,
                                 'equilibrium': {'converged': True},
                                 'validity': {'model_applicable': True}})
                    continue
                applicable = kind != 'not_applicable'
                rows.append({
                    'angle_deg': angle,
                    'gz_m': wall_sided.gz_m(angle),
                    'equilibrium': {'converged': kind != 'not_converged',
                                    'diagnostics': []},
                    'validity': {'model_applicable': applicable}})
            payload = {
                'rows': rows, 'maximum': None, 'avs_deg': None,
                'zero_crossings': [],
                'endpoint': {'kind': 'positive_sample',
                             'angle_deg': angles[-1],
                             'gz_m': wall_sided.gz_m(angles[-1])}}
            if kind == 'model_limit':
                payload['endpoint'] = {'kind': 'model_limit',
                                       'angle_deg': angles[-1],
                                       'gz_m': None}
            elif kind == 'not_applicable':
                payload['endpoint'] = {'kind': 'model_limit',
                                       'angle_deg': angles[-1],
                                       'gz_m': None}
            if mutate is not None:
                mutate(payload)
            return payload
        return curve

    def test_healthy_synthetic_curve_passes(self):
        report = convergence_study.run_study(
            suite='gz', hooks={'stability_curve': self._curve()})
        self.assertIs(report['acceptance']['passed'], True, report['acceptance'])

    def test_missing_or_non_boolean_model_applicability_fails(self):
        # Only the explicit boolean True can support a valid sampled lever.
        cases = (('missing', {}),
                 ('null', {'model_applicable': None}),
                 ('string', {'model_applicable': 'yes'}),
                 ('one', {'model_applicable': 1}),
                 ('zero', {'model_applicable': 0}),
                 ('list', {'model_applicable': [True]}),
                 ('nan', {'model_applicable': float('nan')}),
                 ('infinity', {'model_applicable': float('inf')}))
        for name, validity in cases:
            with self.subTest(case=name):
                def mutate(payload, value=validity):
                    payload['rows'][1]['validity'] = value
                report = convergence_study.run_study(
                    suite='gz', hooks={'stability_curve': self._curve(
                        mutate=mutate)})
                self.assertIs(report['acceptance']['passed'], False)
                self.assertIn('gz.model_applicable.level_0',
                              report['acceptance']['failed'])
                level = report['suites']['gz']['levels'][0]
                sample = level['fixed_angle']['samples'][1]
                self.assertEqual(sample['status'], 'failed_sample')
                self.assertTrue(sample['failure_reason'])
                self.assertIsNone(sample['computed_gz_m'])
                self.assertIsNone(level['curve_area']['trapezoid_area_m_rad'])
                self.assertEqual(convergence_study.exit_code_for(report), 1)
                json.dumps(report, allow_nan=False)

    def test_model_limited_or_inapplicable_curve_fails_acceptance(self):
        for kind in ('not_applicable', 'model_limit'):
            with self.subTest(kind=kind):
                report = convergence_study.run_study(
                    suite='gz', hooks={'stability_curve': self._curve(kind)})
                self.assertIs(report['acceptance']['passed'], False)
                self.assertEqual(report['status'], 'fail')

    def test_a_missing_lever_is_retained_rather_than_crashing(self):
        report = convergence_study.run_study(
            suite='gz', hooks={'stability_curve': self._curve(
                drop_angle=0.0), 'levels': [5.0]})
        level = report['suites']['gz']['levels'][0]
        failed = [sample for sample in level['fixed_angle']['samples']
                  if sample['angle_deg'] == 0.0]
        self.assertEqual(failed[0]['status'], 'failed_sample')
        self.assertIsNone(failed[0]['computed_gz_m'])
        self.assertEqual(level['status'], 'failed')
        self.assertIs(report['acceptance']['passed'], False)
        json.dumps(report, allow_nan=False)

    def test_non_numeric_and_boolean_levers_are_rejected_as_failed(self):
        for bad in (True, '0.5', float('nan'), float('inf')):
            with self.subTest(value=bad):
                def mutate(payload, value=bad):
                    payload['rows'][1]['gz_m'] = value
                report = convergence_study.run_study(
                    suite='gz', hooks={'stability_curve': self._curve(
                        mutate=mutate), 'levels': [5.0]})
                sample = report['suites']['gz']['levels'][0][
                    'fixed_angle']['samples'][1]
                self.assertEqual(sample['status'], 'failed_sample')
                self.assertIsNone(sample['computed_gz_m'])
                self.assertIsNone(sample['absolute_error_m'])
                self.assertIs(report['acceptance']['passed'], False)

    def test_every_failure_probe_writes_all_three_formats_and_exits_one(self):
        # Each probe must produce a report, write all three formats and exit 1
        # instead of aborting. The marker differs because the defect differs.
        probes = {
            'missing_gz': (self._curve(drop_angle=0.0), 'failed_sample'),
            'not_applicable': (self._curve('not_applicable'), 'failed_sample'),
            'model_limit': (self._curve('model_limit'), 'model_limit'),
        }
        for name, (curve, marker) in probes.items():
            with self.subTest(probe=name), tempfile.TemporaryDirectory() as folder:
                real_run = convergence_study.run_study

                def failing(suite='all', **_kwargs):
                    return real_run(suite='gz',
                                    hooks={'stability_curve': curve,
                                           'levels': [5.0]})
                with unittest.mock.patch.object(convergence_study, 'run_study',
                                               failing):
                    code = convergence_study.main(
                        ['--suite', 'gz', '--output-dir', folder])
                self.assertEqual(code, 1, name)
                for filename in ('convergence-study.json',
                                 'convergence-study.csv',
                                 'convergence-study.md'):
                    self.assertTrue((Path(folder) / filename).is_file(),
                                    f'{name}: {filename}')
                report = json.loads(
                    (Path(folder) / 'convergence-study.json').read_text(
                        encoding='utf-8'))
                self.assertEqual(report['status'], 'fail', name)
                self.assertTrue(report['acceptance']['failed'], name)
                markdown = (Path(folder) / 'convergence-study.md').read_text(
                    encoding='utf-8')
                csv_text = (Path(folder) / 'convergence-study.csv').read_text(
                    encoding='utf-8')
                # The defect survives to disk in both readable formats.
                self.assertIn(marker, markdown, name)
                self.assertIn(marker, csv_text, name)
                self.assertIn('failure reason', markdown, name)

    def test_per_level_gz_fixture_hashes_are_real_before_and_after(self):
        report = convergence_study.run_study(suite='gz')
        for level in report['suites']['gz']['levels']:
            self.assertEqual(len(level['fixture_sha256_before']), 64)
            self.assertEqual(len(level['fixture_sha256_after']), 64)
            self.assertEqual(level['fixture_sha256_before'],
                             level['fixture_sha256_after'])
            self.assertIs(level['fixture_unchanged'], True)


class FloodingIntegrityTests(_StudyTestCase):
    """A broken accepted state must fail the suite, not be averaged away."""

    def _reference(self):
        return convergence_study._flooding_reference(
            convergence_study._load_oracle('flooding_oracles.py').oracle())

    def test_a_broken_state_cannot_leave_an_all_state_maximum(self):
        valid = self._good_run(self._reference())

        def broken(*args, **kwargs):
            result = valid(*args, **kwargs)
            result['timeline'][1]['equilibrium']['residuals']['scaled']['transverse'] = float('nan')
            return result

        suite = convergence_study.run_flooding_suite(
            levels=[0.5, 0.25], hooks={'simulate_flooding': broken})
        self.assertIs(suite['passed'], False)
        for level in suite['levels']:
            self.assertTrue(level['broken_states'])
            self.assertIsNone(level['max_abs_scaled_residual'])

    @staticmethod
    def _good_run(reference, *, residual=0.0, drop_residual=False):
        """A synthetic run whose error shrinks with the time step.

        The study requires the normalized error to decrease under refinement,
        so a control that returned the exact answer at every step would fail
        it. This stub carries a small first-order term that scales with dt.
        """
        def simulate(_project, _condition, scenario, options=None):
            dt = scenario['time_step_s']
            duration = scenario['duration_s']
            count = max(1, int(round(duration / dt)))
            exact_influx = reference['net_sea_inflow_m3']
            influx = exact_influx * (1.0 + 0.002 * dt)
            draft = reference['initial_draft_m'] + (
                reference['draft_change_m'] * (1.0 + 0.002 * dt))
            states = []
            for index in range(count + 1):
                share = index / count
                scaled = {'volume': 0.0, 'longitudinal': 0.0,
                          'transverse': residual}
                if drop_residual:
                    scaled = {'volume': 0.0}
                states.append({
                    'time_s': duration * share,
                    'volumes_m3': {
                        convergence_study.fixtures.FLOODING['tank_id']:
                            8.0 + influx * share},
                    'equilibrium': {
                        'waterline_above_keel_m': 2.0 + (draft - 2.0) * share,
                        'heel_deg': 0.0, 'trim_deg': 0.0, 'converged': True,
                        'residuals': {'scaled': scaled}},
                    'volume_conservation_error_m3': 0.0,
                    'mass_conservation_error_t': 0.0})
            return {
                'status': 'completed', 'stop_reason': 'scheduled_completion',
                'method_version': 'synthetic',
                'volume_conservation_error_m3': 0.0,
                'mass_conservation_error_t': 0.0,
                'timeline': states,
                'final_state': states[-1],
                'validity': {'complete': True}}
        return simulate

    @staticmethod
    def _adversarial_control(reference, mutate=None):
        """A flooding stub with an independently derived analytic answer.

        The d(V)/dt integration is recomputed here from the orifice law rather
        than copied from the oracle module, so a passing control is evidence
        that the study accepts correct input.
        """
        discharge = 0.6 * 0.1 * math.sqrt(2.0 * 9.80665)
        alpha = 1.0 / 8.0 - 1.0 / 200.0
        exact_influx = (1.0 - (1.0 - alpha * discharge * 5.0 / 2.0) ** 2) / alpha
        tank_id = convergence_study.fixtures.FLOODING['tank_id']

        def simulate(_project, _condition, scenario, options=None):
            dt = scenario['time_step_s']
            count = round(5.0 / dt)
            influx = exact_influx * (1.0 + 0.01 * dt)
            rows = []
            for index in range(count + 1):
                delta = influx * index / count
                rows.append({
                    'time_s': index * dt,
                    'actual_dt_s': dt if index else 0.0,
                    'volumes_m3': {tank_id: 8.0 + delta},
                    'equilibrium': {
                        'converged': True, 'heel_deg': 0.0, 'trim_deg': 0.0,
                        'waterline_above_keel_m': 2.0 + delta / 200.0,
                        'residuals': {'scaled': {'volume': 0.0,
                                                 'longitudinal': 0.0,
                                                 'transverse': 0.0}}},
                    'volume_conservation_error_m3': 0.0,
                    'mass_conservation_error_t': 0.0})
            payload = {
                'status': 'completed', 'stop_reason': 'scheduled_completion',
                'method_version': 'control',
                'kernel_method_version': 'control',
                'validity': {'complete': True, 'model_applicable': True,
                             'numerical_convergence': True},
                'final_state': copy.deepcopy(rows[-1]),
                'timeline': rows, 'diagnostics': [],
                'volume_conservation_error_m3': 0.0,
                'mass_conservation_error_t': 0.0}
            if mutate is not None:
                mutate(payload)
            return payload
        return simulate

    def test_complete_synthetic_run_passes(self):
        reference = self._reference()
        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': self._good_run(reference)})
        self.assertIs(suite['passed'], True, suite['checks'])

    def test_a_separate_final_state_is_included_in_residual_limit(self):
        # The final object need not alias the last timeline row.
        for residual in (1.0, -1.0):
            with self.subTest(residual=residual):
                def mutate(payload, value=residual):
                    payload['final_state']['equilibrium']['residuals'][
                        'scaled']['volume'] = value
                report = convergence_study.run_study(
                    suite='flooding', hooks={'simulate_flooding':
                        self._adversarial_control(self._reference(), mutate)})
                self.assertIs(report['acceptance']['passed'], False)
                self.assertIn('flooding.scaled_residual.level_0',
                              report['acceptance']['failed'])
                level = report['suites']['flooding']['levels'][0]
                self.assertEqual(level['max_abs_scaled_residual'], 1.0)
                self.assertEqual(level['final_state_report'][
                    'max_abs_scaled_residual'], 1.0)
                self.assertEqual(convergence_study.exit_code_for(report), 1)
                json.dumps(report, allow_nan=False)

    def test_incomplete_final_state_cannot_leave_all_state_extrema(self):
        mutations = {
            'not_converged': lambda state: state['equilibrium'].update(
                converged=False),
            'missing_residual': lambda state: state['equilibrium'][
                'residuals']['scaled'].pop('volume'),
            'nan_residual': lambda state: state['equilibrium'][
                'residuals']['scaled'].update(volume=float('nan')),
        }
        for name, change in mutations.items():
            with self.subTest(case=name):
                def mutate(payload, change=change):
                    change(payload['final_state'])
                report = convergence_study.run_study(
                    suite='flooding', hooks={'simulate_flooding':
                        self._adversarial_control(self._reference(), mutate)})
                self.assertIs(report['acceptance']['passed'], False)
                level = report['suites']['flooding']['levels'][0]
                for key in ('max_abs_scaled_residual', 'max_abs_heel_deg',
                            'max_abs_trim_deg'):
                    self.assertIsNone(level[key], key)
                json.dumps(report, allow_nan=False)

    def test_a_non_finite_accepted_state_residual_fails(self):
        reference = self._reference()
        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': self._good_run(reference,
                                                       residual=float('nan'))})
        self.assertIs(suite['passed'], False)
        level = suite['levels'][0]
        self.assertIsNone(level['max_abs_scaled_residual'])
        self.assertTrue(any('residual' in note for note in level['notes']))

    def test_an_accepted_state_without_required_values_fails(self):
        reference = self._reference()
        run = self._good_run(reference)

        def dropping(*args, **kwargs):
            payload = run(*args, **kwargs)
            payload['timeline'][1]['equilibrium'].pop('heel_deg')
            return payload

        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': dropping})
        self.assertIs(suite['passed'], False)

    def test_empty_or_inconsistent_timeline_fails(self):
        reference = self._reference()
        run = self._good_run(reference)

        def empty(*args, **kwargs):
            payload = run(*args, **kwargs)
            payload['timeline'] = []
            payload['final_state'] = None
            return payload

        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': empty})
        self.assertIs(suite['passed'], False)

    def test_final_time_must_match_the_scheduled_duration(self):
        reference = self._reference()
        run = self._good_run(reference)

        def short(*args, **kwargs):
            payload = run(*args, **kwargs)
            payload['timeline'][-1]['time_s'] = 4.0
            payload['final_state'] = payload['timeline'][-1]
            return payload

        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': short})
        self.assertIs(suite['passed'], False)

    def test_an_unconverged_accepted_state_fails(self):
        reference = self._reference()
        run = self._good_run(reference)

        def unconverged(*args, **kwargs):
            payload = run(*args, **kwargs)
            payload['timeline'][1]['equilibrium']['converged'] = False
            return payload

        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': unconverged})
        self.assertIs(suite['passed'], False)

    def test_a_signed_negative_conservation_error_cannot_pass(self):
        # A limit on |error|: a large negative volume or mass conservation
        # error is as fatal as a large positive one.
        reference = self._reference()
        run = self._good_run(reference)

        def negative(*args, **kwargs):
            payload = run(*args, **kwargs)
            payload['volume_conservation_error_m3'] = -1.0
            payload['mass_conservation_error_t'] = -1.0
            return payload

        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': negative})
        self.assertIs(suite['passed'], False)
        failed = [check['name'] for check in suite['checks']
                  if not check['passed']]
        self.assertTrue(any('volume_conservation' in name for name in failed))
        self.assertTrue(any('mass_conservation' in name for name in failed))
        # The signed observation itself is preserved unchanged.
        self.assertEqual(suite['levels'][0]['volume_conservation_error_m3'], -1.0)
        self.assertEqual(suite['levels'][0]['mass_conservation_error_t'], -1.0)

    def test_a_small_negative_conservation_error_still_passes(self):
        reference = self._reference()
        run = self._good_run(reference)

        def small_negative(*args, **kwargs):
            payload = run(*args, **kwargs)
            payload['volume_conservation_error_m3'] = -1e-12
            payload['mass_conservation_error_t'] = -1e-13
            return payload

        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': small_negative})
        self.assertIs(suite['passed'], True, suite['checks'])

    def test_stop_reason_survives_into_the_csv(self):
        reference = self._reference()
        with tempfile.TemporaryDirectory() as folder:
            real_run = convergence_study.run_study

            def flooding_only(suite='all', **_kwargs):
                return real_run(
                    suite='flooding',
                    hooks={'simulate_flooding': self._good_run(reference)})
            with unittest.mock.patch.object(convergence_study, 'run_study',
                                           flooding_only):
                self.assertEqual(
                    convergence_study.main(
                        ['--suite', 'flooding', '--output-dir', folder]), 0)
            csv_text = (Path(folder) / 'convergence-study.csv').read_text(
                encoding='utf-8')
            self.assertIn('scheduled_completion', csv_text)
            self.assertIn('completed', csv_text)


class LongitudinalIntervalRatioTests(_StudyTestCase):
    """Interval counts, not node counts, define the refinement ratio."""

    def test_station_ratios_are_exactly_two(self):
        suite = convergence_study.run_geometry_suite(
            sequences=[{'name': 'probe',
                        'refined_parameter': 'longitudinal_stations',
                        'fixed_parameter': {'section_vertices': 128},
                        'levels': [{'longitudinal_stations': 41,
                                    'section_vertices': 128},
                                   {'longitudinal_stations': 81,
                                    'section_vertices': 128},
                                   {'longitudinal_stations': 161,
                                    'section_vertices': 128}]}])
        ratios = [level['refinement_ratio_to_previous']
                  for level in suite['sequences'][0]['levels']]
        self.assertEqual(ratios, [None, 2.0, 2.0])

    def test_section_vertex_ratio_uses_the_vertex_count(self):
        suite = convergence_study.run_geometry_suite(
            sequences=[{'name': 'probe',
                        'refined_parameter': 'section_vertices',
                        'fixed_parameter': {'longitudinal_stations': 161},
                        'levels': [{'longitudinal_stations': 161,
                                    'section_vertices': 32},
                                   {'longitudinal_stations': 161,
                                    'section_vertices': 128}]}])
        ratios = [level['refinement_ratio_to_previous']
                  for level in suite['sequences'][0]['levels']]
        self.assertEqual(ratios, [None, 4.0])

    def test_finest_mesh_diagnostic_is_not_presented_as_a_causal_floor(self):
        suite = convergence_study.run_geometry_suite()
        for sequence in suite['sequences']:
            diagnostic = sequence['finest_mesh_comparison']
            self.assertNotIn('floor_diagnostic', sequence)
            self.assertEqual(diagnostic['used_for_acceptance'], False)
            self.assertIn('finite finest mesh', diagnostic['definition'])
            self.assertNotIn('fixed axis sets', diagnostic['definition'])
            for orders in diagnostic['observed_orders'].values():
                for order in orders:
                    if order is not None:
                        self.assertIsInstance(order, float)
            self.assertIn('observed_orders', sequence)

    def test_finest_mesh_subtracted_orders_are_numeric_where_reported(self):
        suite = convergence_study.run_geometry_suite()
        for sequence in suite['sequences']:
            diagnostic = sequence['finest_mesh_comparison']
            self.assertTrue(diagnostic['available'])
            orders = diagnostic['observed_orders']
            self.assertIn('direct_plane.volume_m3', orders)
            for value in orders['direct_plane.volume_m3']:
                self.assertIsNotNone(value)
                self.assertIsInstance(value, float)


class SuiteExceptionTests(_StudyTestCase):
    """A raising hook must still produce a fail report and complete evidence."""

    @staticmethod
    def _boom(*args, **kwargs):
        raise ValueError('injected solver exception')

    def _run_and_write(self, suite, hooks, folder):
        report = convergence_study.run_study(suite=suite, hooks=hooks)
        files = convergence_study.write_evidence(report, folder)
        return report, files

    def test_gz_exception_returns_a_fail_report_and_writes_everything(self):
        with tempfile.TemporaryDirectory() as folder:
            report, files = self._run_and_write(
                'gz', {'stability_curve': self._boom}, folder)
            self.assertIs(report['acceptance']['passed'], False)
            self.assertEqual(report['status'], 'fail')
            self.assertTrue(report['acceptance']['failed'])
            self.assertEqual(convergence_study.exit_code_for(report), 1)
            for path in files.values():
                self.assertTrue(Path(path).is_file())
            for name in ('convergence-study.json', 'convergence-study.csv',
                         'convergence-study.md'):
                self.assertTrue((Path(folder) / name).is_file(), name)
            json.dumps(report, allow_nan=False)
            markdown = (Path(folder) / 'convergence-study.md').read_text(
                encoding='utf-8')
            self.assertIn('injected solver exception', markdown)

    def test_flooding_exception_returns_a_fail_report_and_writes_everything(self):
        with tempfile.TemporaryDirectory() as folder:
            report, files = self._run_and_write(
                'flooding', {'simulate_flooding': self._boom}, folder)
            self.assertIs(report['acceptance']['passed'], False)
            self.assertEqual(convergence_study.exit_code_for(report), 1)
            for name in ('convergence-study.json', 'convergence-study.csv',
                         'convergence-study.md'):
                self.assertTrue((Path(folder) / name).is_file(), name)
            json.dumps(report, allow_nan=False)
            markdown = (Path(folder) / 'convergence-study.md').read_text(
                encoding='utf-8')
            self.assertIn('injected solver exception', markdown)

    def test_geometry_exception_returns_a_fail_report_and_writes_everything(self):
        reference = convergence_study._geometry_reference(
            convergence_study._load_oracle(
                'coupled_ellipsoid_oracles.py').oracle())
        with tempfile.TemporaryDirectory() as folder:
            report, files = self._run_and_write(
                'geometry', {'evaluate_plane': self._boom,
                             'solve_equilibrium': self._boom}, folder)
            self.assertIs(report['acceptance']['passed'], False)
            self.assertEqual(convergence_study.exit_code_for(report), 1)
            for name in ('convergence-study.json', 'convergence-study.csv',
                         'convergence-study.md'):
                self.assertTrue((Path(folder) / name).is_file(), name)
            json.dumps(report, allow_nan=False)

    def test_an_exception_level_carries_the_complete_default_record(self):
        # Every level record must expose the keys the writers and checks read,
        # whatever path produced it.
        report = convergence_study.run_study(
            suite='flooding', hooks={'simulate_flooding': self._boom})
        level = report['suites']['flooding']['levels'][0]
        for key in ('broken_states', 'not_converged_states', 'final_time_s',
                    'last_timeline_time_s', 'scheduled_duration_s',
                    'max_abs_scaled_residual',
                    'volume_conservation_error_m3', 'mass_conservation_error_t',
                    'complete_accepted_states', 'final_state_report',
                    'time_consistency', 'metrics', 'notes'):
            self.assertIn(key, level, key)
        gz = convergence_study.run_study(
            suite='gz', hooks={'stability_curve': self._boom})
        for level in gz['suites']['gz']['levels']:
            self.assertIn('out_of_bounds_samples', level)
            self.assertIn('not_applicable_samples', level)
            self.assertIn('sampled_maximum', level)
            self.assertIn('endpoint', level)


class AcceptedStateIntegrityTests(_StudyTestCase):
    """Required values on every accepted state and on final_state."""

    def setUp(self):
        super().setUp()
        self.reference = convergence_study._flooding_reference(
            convergence_study._load_oracle('flooding_oracles.py').oracle())

    def _control(self, mutate=None):
        return FloodingIntegrityTests._adversarial_control(
            self.reference, mutate)

    def test_the_control_run_passes(self):
        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': self._control()})
        self.assertIs(suite['passed'], True, suite['checks'])

    def test_a_missing_required_residual_component_fails(self):
        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': self._control(
                lambda r: r['timeline'][1]['equilibrium']['residuals'][
                    'scaled'].pop('longitudinal'))})
        self.assertIs(suite['passed'], False)
        self.assertTrue(any('longitudinal' in detail
                            for check in suite['checks']
                            for detail in [check['detail'] or '']
                            if 'missing' in detail))

    def test_a_non_finite_tank_volume_fails(self):
        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': self._control(
                lambda r: r['timeline'][1]['volumes_m3'].update(
                    centre=float('nan')))})
        self.assertIs(suite['passed'], False)

    def test_a_missing_tank_id_fails(self):
        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': self._control(
                lambda r: r['timeline'][1]['volumes_m3'].pop('centre'))})
        self.assertIs(suite['passed'], False)

    def test_an_unconverged_final_state_fails(self):
        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': self._control(
                lambda r: r['final_state']['equilibrium'].update(
                    converged=False))})
        self.assertIs(suite['passed'], False)

    def test_a_timeline_and_final_time_mismatch_fails(self):
        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': self._control(
                lambda r: r['timeline'][-1].update(time_s=3.0))})
        self.assertIs(suite['passed'], False)

    def test_non_monotonic_accepted_times_fail(self):
        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': self._control(
                lambda r: r['timeline'][2].update(time_s=0.0))})
        self.assertIs(suite['passed'], False)

    def test_a_non_finite_final_state_value_fails(self):
        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': self._control(
                lambda r: r['final_state']['equilibrium'].update(
                    waterline_above_keel_m=float('inf')))})
        self.assertIs(suite['passed'], False)

    def test_an_empty_timeline_fails(self):
        suite = convergence_study.run_flooding_suite(
            hooks={'simulate_flooding': self._control(
                lambda r: (r.update(timeline=[], final_state=None)))})
        self.assertIs(suite['passed'], False)


class CommandLineTests(_StudyTestCase):
    """Exit codes, absolute paths, bounded suites and unwritable destinations."""

    def test_help_runs_no_study_and_writes_nothing(self):
        before = sorted(os.listdir(os.getcwd()))
        with self.assertRaises(SystemExit) as raised:
            convergence_study.main(['--help'])
        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(sorted(os.listdir(os.getcwd())), before)

    def test_invalid_suite_is_bounded_by_the_parser(self):
        for suite in ('nope', 'GEOMETRY', '', 'geometry,gz'):
            with self.subTest(suite=suite), self.assertRaises(SystemExit) as raised:
                convergence_study.main(['--suite', suite, '--output-dir', os.getcwd()])
            self.assertEqual(raised.exception.code, 2)

    def test_missing_output_dir_is_rejected(self):
        with self.assertRaises(SystemExit) as raised:
            convergence_study.main(['--suite', 'gz'])
        self.assertEqual(raised.exception.code, 2)

    def test_unwritable_output_directory_reports_a_clear_error(self):
        with tempfile.TemporaryDirectory() as folder:
            blocker = Path(folder) / 'not-a-directory'
            blocker.write_text('occupied', encoding='utf-8')
            code = convergence_study.main(
                ['--suite', 'gz', '--output-dir', str(blocker / 'nested')])
        self.assertEqual(code, 2)

    def test_successful_run_writes_all_three_formats_and_returns_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'nested' / 'evidence'
            code = convergence_study.main(
                ['--suite', 'gz', '--output-dir', str(target)])
            self.assertEqual(code, 0)
            for name in ('convergence-study.json', 'convergence-study.csv',
                         'convergence-study.md'):
                self.assertTrue((target / name).is_file(), name)
            report = json.loads(
                (target / 'convergence-study.json').read_text(encoding='utf-8'))
            self.assertIs(report['acceptance']['passed'], True)
            csv_text = (target / 'convergence-study.csv').read_text(encoding='utf-8')
            self.assertIn('suite,sequence,level', csv_text)
            self.assertIn('relative_area_error', csv_text)
            markdown = (target / 'convergence-study.md').read_text(encoding='utf-8')
            self.assertIn('# Numerical convergence study', markdown)
            self.assertIn('Acceptance', markdown)

    def test_failing_acceptance_still_writes_evidence_and_exits_one(self):
        real_run = convergence_study.run_study

        def failing(suite='all', **kwargs):
            return real_run(
                suite='gz', hooks={'stability_curve': _failed_curve,
                                   'levels': [5.0]})
        with tempfile.TemporaryDirectory() as folder:
            with unittest.mock.patch.object(convergence_study, 'run_study', failing):
                code = convergence_study.main(
                    ['--suite', 'gz', '--output-dir', folder])
            self.assertEqual(code, 1)
            for name in ('convergence-study.json', 'convergence-study.csv',
                         'convergence-study.md'):
                self.assertTrue((Path(folder) / name).is_file(), name)
            report = json.loads(
                (Path(folder) / 'convergence-study.json').read_text(encoding='utf-8'))
            self.assertEqual(report['status'], 'fail')
            csv_text = (Path(folder) / 'convergence-study.csv').read_text(encoding='utf-8')
            self.assertIn('failed', csv_text)

    def test_absolute_output_path_is_independent_of_the_working_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            here = Path(folder) / 'here'
            there = Path(folder) / 'there'
            here.mkdir()
            there.mkdir()
            original = os.getcwd()
            os.chdir(here)
            try:
                self.assertEqual(
                    convergence_study.main(
                        ['--suite', 'gz', '--output-dir', str(there)]), 0)
            finally:
                os.chdir(original)
            moved = json.loads(
                (there / 'convergence-study.json').read_text(encoding='utf-8'))
            reference = convergence_study.run_study(suite='gz')
            self.assertEqual(json.dumps(moved['suites'], sort_keys=True),
                             json.dumps(reference['suites'], sort_keys=True))
            self.assertEqual(moved['sources'], reference['sources'])
            self.assertFalse(list(here.iterdir()))


if __name__ == '__main__':
    unittest.main()
