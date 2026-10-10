# -*- coding: utf-8 -*-
"""Offline numerical convergence study for hull, GZ sampling and flooding time.

The study calls public Plimsoll functions against independent analytic answers
and reports absolute errors, relative errors and observed orders. Every
threshold is declared before the run and is never tuned to a result; a failed,
model-limited or non-finite sample is retained in all three evidence formats
and always fails acceptance.

This measures agreement between the implemented model and continuous
integrals. It does not establish physical accuracy, statutory stability
compliance, historical ship accuracy or any SPS superiority, and it never
touches the network, production state or the frozen release.

Run from any working directory:

    python tools/plimsoll/tools/convergence_study.py --output-dir ABSOLUTE_PATH
"""

from __future__ import annotations

import argparse
import csv
import datetime as _datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import sys


HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = PKG.parent.parent
for _entry in (str(HERE), str(PKG)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import convergence_fixtures as fixtures  # noqa: E402
import flooding  # noqa: E402
import geometry  # noqa: E402
import stability  # noqa: E402


SCHEMA = 'plimsoll-convergence-study-1'
STUDY_ID = 'numerical-convergence-2026-10-10'
JSON_NAME = 'convergence-study.json'
CSV_NAME = 'convergence-study.csv'
MARKDOWN_NAME = 'convergence-study.md'
SUITE_CHOICES = ('all', 'geometry', 'gz', 'flooding')
EXIT_OK = 0
EXIT_ACCEPTANCE_FAILED = 1
EXIT_USAGE = 2

SOURCE_ROLES = (
    ('tools/plimsoll/stability.py', 'runtime_loaded_equilibrium_and_gz_curve'),
    ('tools/plimsoll/geometry.py', 'runtime_polygon_section_hydrostatics'),
    ('tools/plimsoll/flooding.py', 'runtime_flooding_driver'),
    ('tools/plimsoll/_flooding_kernel.py', 'runtime_flooding_flow_kernel'),
    ('tools/plimsoll/loading.py', 'runtime_loading_ledger'),
    ('tools/plimsoll/project_io.py', 'runtime_project_normalisation'),
    ('tools/plimsoll/tank_geometry.py', 'runtime_tank_liquid_geometry'),
    ('tools/plimsoll/offsets.py', 'runtime_offsets_materialisation'),
    ('tools/plimsoll/tools/convergence_fixtures.py', 'study_fixture_builder'),
    ('tools/plimsoll/tools/convergence_study.py', 'study_runner_and_writers'),
    ('docs/plimsoll-1.0/evidence/coupled_ellipsoid_oracles.py',
     'independent_sliced_ellipsoid_oracle'),
    ('docs/plimsoll-1.0/evidence/flooding_oracles.py',
     'independent_coupled_heave_oracle'),
    ('docs/plimsoll-1.0/evidence/wall_sided_box_oracle.py',
     'independent_wall_sided_gz_oracle'),
)

EVIDENCE_DIR = REPO / 'docs/plimsoll-1.0/evidence'

# ---------------------------------------------------------------- thresholds

GEOMETRY_THRESHOLDS = {
    'finest_volume_relative': 1e-3,
    'finest_buoyancy_centre_absolute_m': 0.01,
    'finest_waterline_d_absolute_m': 0.01,
    'finest_trim_slope_absolute': 1e-4,
    'finest_heel_slope_absolute': 1e-4,
    'finest_prescribed_gz_absolute_m': 1e-3,
    'scaled_residual_max': 1e-6,
    'every_declared_state_converged': True,
}
GZ_THRESHOLDS = {
    'fixed_angle_absolute_m': 1e-6,
    'finest_area_relative': 1e-4,
    'area_errors_decrease': True,
    'every_sample_converged': True,
    'every_sample_inside_declared_wedge': True,
}
FLOODING_THRESHOLDS = {
    'influx_relative_error_decreases': True,
    'draft_change_relative_error_decreases': True,
    'finest_influx_relative': 0.01,
    'finest_draft_change_relative': 0.01,
    'volume_conservation_absolute_m3': 1e-9,
    'mass_conservation_absolute_t': 4.1e-8,
    'scaled_residual_max': 1e-6,
    'required_status': 'completed',
    'required_stop_reason': 'scheduled_completion',
    'all_reported_values_finite': True,
}

DEFAULT_GEOMETRY_SEQUENCES = (
    {'name': 'stations',
     'refined_parameter': 'longitudinal_stations',
     'fixed_parameter': {'section_vertices': 128},
     'levels': [{'longitudinal_stations': 41, 'section_vertices': 128},
                {'longitudinal_stations': 81, 'section_vertices': 128},
                {'longitudinal_stations': 161, 'section_vertices': 128}]},
    {'name': 'vertices',
     'refined_parameter': 'section_vertices',
     'fixed_parameter': {'longitudinal_stations': 161},
     'levels': [{'longitudinal_stations': 161, 'section_vertices': 32},
                {'longitudinal_stations': 161, 'section_vertices': 64},
                {'longitudinal_stations': 161, 'section_vertices': 128}]},
)
DEFAULT_GZ_LEVELS = (5.0, 2.5, 1.25, 0.625)
DEFAULT_FLOODING_LEVELS = (0.5, 0.25, 0.125, 0.0625, 0.03125)
GZ_MAX_ANGLE_DEG = 30.0

LIMITATIONS = [
    'Every answer here is an independent analytic integral of an idealised '
    'body, not a measured ship, a model-basin result or a statutory check.',
    'The ellipsoid keeps its section vertex count fixed inside the '
    'longitudinal sequence, so that axis supplies a discretization floor and '
    'the observed longitudinal order is evidence, not a guaranteed pure order.',
    'Fixed-angle lever agreement and curve-area sampling error are different '
    'metrics; a curve can be sampled accurately and integrated inaccurately.',
    'The flooding anchor integrates one chosen constant-Cd orifice law with a '
    'single fluid density and no trapped air, waves, sloshing or structural '
    'failure.',
    'No AVS, downflooding angle or stability-criterion claim is made; the '
    'study reports numeric behaviour of the implemented model only.',
    'External experimental or model-basin validation remains pending and is '
    'not replaced by any result in this report.',
]


# ---------------------------------------------------------------- primitives

def _finite(value):
    """Return a finite float, or None for bool/NaN/inf/None/non-numeric."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _is_non_finite(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and not math.isfinite(value))


def _json_safe(value):
    """Copy external output into the report without ever carrying NaN or inf.

    A non-finite float becomes null in place, so the surrounding structure and
    its status survive while the report stays strict-JSON serialisable.
    """
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return _plain(value)


def _utc_now():
    return _datetime.datetime.now(_datetime.timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%SZ')


def _file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_sha256(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _source_snapshot():
    snapshot = {}
    for relative, role in SOURCE_ROLES:
        path = REPO / relative
        if not path.is_file():
            raise FileNotFoundError(f'study source is missing: {relative}')
        snapshot[relative] = {'role': role, 'sha256': _file_sha256(path),
                              'bytes': path.stat().st_size}
    return snapshot


def _load_oracle(name):
    path = EVIDENCE_DIR / name
    spec = importlib.util.spec_from_file_location(f'oracle_{path.stem}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _error_record(name, computed, reference, *, unit='', limit=None,
                  limit_kind='absolute', comparison='<=', note=None,
                  previous=None, ratio=None):
    """Absolute and relative error for one quantity, never faking a zero error.

    A null or non-finite computed value stays null with an explicit status.
    A zero reference keeps its absolute error but reports the relative error
    as unavailable, and an observed order stays unavailable unless both error
    values are finite, strictly positive and paired with a real refinement.
    """
    computed_value = _finite(computed)
    reference_value = _finite(reference)
    absolute = relative = None
    if computed is None:
        status, relative_status = 'computed_unavailable', 'computed_unavailable'
    elif computed_value is None:
        status, relative_status = 'computed_non_finite', 'computed_non_finite'
    elif reference is None:
        status, relative_status = 'reference_unavailable', 'reference_unavailable'
    elif reference_value is None:
        status, relative_status = 'reference_non_finite', 'reference_non_finite'
    else:
        absolute = abs(computed_value - reference_value)
        status, relative_status = 'ok', 'defined'
        relative = None if reference_value == 0.0 else absolute / abs(reference_value)
        if relative_status == 'defined' and relative is None:
            relative_status = 'zero_reference'
    if status == 'ok' and reference_value == 0.0:
        relative_status = 'zero_reference'

    order, order_status = _observed_order(previous, absolute, ratio)
    if limit is None:
        limit_value, passed = None, None
    else:
        limit_value = absolute if limit_kind == 'absolute' else relative
        passed = bool(status == 'ok' and limit_value is not None
                      and limit_value <= limit)
    return {'name': name, 'unit': unit,
            'reference': reference_value, 'computed': computed_value,
            'absolute_error': absolute, 'relative_error': relative,
            'relative_error_status': relative_status, 'status': status,
            'observed_order': order, 'observed_order_status': order_status,
            'limit': limit, 'limit_kind': limit_kind, 'comparison': comparison,
            'limit_value': limit_value, 'passed': passed, 'note': note}


def _observed_order(previous_absolute, absolute, ratio):
    """Observed order of two strictly positive finite error values.

    Non-finite inputs are rejected explicitly: NaN compares false against
    every ordering test, so relying on that comparison alone would let a
    corrupted pair through whenever the test is written differently.
    """
    if previous_absolute is None or absolute is None:
        return None, 'unavailable_no_previous_level'
    if _finite(previous_absolute) is None or _finite(absolute) is None:
        return None, 'unavailable_non_finite_error_pair'
    if not (previous_absolute > 0.0) or not (absolute > 0.0):
        return None, 'unavailable_zero_or_invalid_error'
    if ratio is None or _finite(ratio) is None or ratio <= 1.0:
        return None, 'unavailable_invalid_refinement_ratio'
    return math.log(previous_absolute / absolute) / math.log(ratio), 'ok'


def _check(suite, name, requirement, value, *, limit=None, comparison='<=',
           passed=None, detail=None):
    """One declared acceptance criterion, recorded whether it passes or not."""
    key = f'{suite}.{name}'
    recorded = value if isinstance(value, bool) else _finite(value)
    if passed is None:
        if isinstance(value, bool):
            passed = bool(value)
        elif recorded is None:
            passed = False
        elif limit is None:
            # An unscored observation still has to be present to count as
            # evidence; it never silently becomes a pass.
            passed = True
        elif comparison == '<':
            passed = recorded < limit
        else:
            passed = recorded <= limit
    return {'suite': suite, 'name': key, 'requirement': requirement,
            'value': recorded, 'limit': limit, 'comparison': comparison,
            'passed': bool(passed), 'detail': detail}


def _strictly_decreasing(values):
    """True when every consecutive pair of finite positive values decreases."""
    if len(values) < 2:
        return False
    for previous, current in zip(values, values[1:]):
        if previous is None or current is None:
            return False
        if not (previous > current > 0.0):
            return False
    return True


def _monotonic_check(suite, name, requirement, values, *, limit=None,
                     limit_name='finest value'):
    """A decreasing-error criterion whose finest value also carries a limit."""
    finite_values = [_finite(value) for value in values]
    decreasing = _strictly_decreasing(finite_values)
    finest = finite_values[-1] if finite_values else None
    within = bool(limit is not None and finest is not None and finest <= limit)
    return [_check(suite, name, requirement, values,
                   passed=decreasing,
                   detail=f'normalized errors {_plain(finite_values)}'),
            _check(suite, f'{name}.{limit_name}', f'{requirement}; {limit_name}',
                   finest, limit=limit, passed=within)]


def _plain(value):
    """JSON-safe rendering: a finite float, a list of them, a string, or None."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        return value
    number = _finite(value)
    if number is not None:
        return number
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return None


# ------------------------------------------------------------------ geometry

def _default_evaluate_plane(hull, p, q, d):
    """Integrate the specified waterplane plane directly, without any solve."""
    prepared = stability.prepare_geometry(hull)
    hull_object = prepared[0]
    return hull_object.integrate(math.atan(q), d, math.atan(p))


def _geometry_reference(oracle):
    p, q, d = (float(oracle['waterplane'][key]) for key in ('p', 'q', 'd_m'))
    return {
        'source': 'docs/plimsoll-1.0/evidence/coupled_ellipsoid_oracles.py',
        'kind': oracle['kind'],
        'semi_axes_m': oracle['geometry_m']['semi_axes'],
        'p': p, 'q': q, 'd_m': d,
        'rho_t_m3': 1.025, 'kg_m': 3.0,
        'volume_m3': float(oracle['volume_m3']),
        'mass_t': float(oracle['mass_t']),
        'buoyancy_centre_m': [float(value)
                              for value in oracle['buoyancy_centre_m']],
        'free_equilibrium_cg_m': [float(value)
                                  for value in oracle['free_equilibrium_cg_m']],
        'constrained_heel_cg_m': [float(value)
                                  for value in oracle['constrained_heel_cg_m']],
        'prescribed_gz_m': float(oracle['constrained_heel_gz_m']),
        'heel_deg': float(oracle['waterplane']['heel_deg']),
        'trim_deg': float(oracle['waterplane']['trim_deg']),
    }


def _geometry_evaluation_metrics(evaluation_name, values, reference, previous,
                                 ratio):
    """Error records for one evaluation of one ellipsoid mesh."""
    limits = GEOMETRY_THRESHOLDS
    if evaluation_name == 'direct_plane':
        computed = {'volume_m3': values['volume_m3'],
                    'buoyancy_centre_x_m': values['buoyancy_centre_x_m'],
                    'buoyancy_centre_y_m': values['buoyancy_centre_y_m'],
                    'buoyancy_centre_z_m': values['buoyancy_centre_z_m']}
        limits_map = {'volume_m3': (1e-3, 'relative')}
        centre_limit = limits['finest_buoyancy_centre_absolute_m']
        for key in ('buoyancy_centre_x_m', 'buoyancy_centre_y_m',
                    'buoyancy_centre_z_m'):
            limits_map[key] = (centre_limit, 'absolute')
    else:
        computed = {'volume_m3': values['volume_m3'],
                    'buoyancy_centre_x_m': values['buoyancy_centre_x_m'],
                    'buoyancy_centre_y_m': values['buoyancy_centre_y_m'],
                    'buoyancy_centre_z_m': values['buoyancy_centre_z_m'],
                    'p': values['p'], 'q': values['q'],
                    'waterline_d_m': values['waterline_d_m'],
                    'gz_m': values['gz_m']}
        limits_map = {'volume_m3': (1e-3, 'relative')}
        for key in ('buoyancy_centre_x_m', 'buoyancy_centre_y_m',
                    'buoyancy_centre_z_m'):
            limits_map[key] = (limits['finest_buoyancy_centre_absolute_m'],
                               'absolute')
        limits_map['waterline_d_m'] = (
            limits['finest_waterline_d_absolute_m'], 'absolute')
        limits_map['p'] = (limits['finest_trim_slope_absolute'], 'absolute')
        limits_map['q'] = (limits['finest_heel_slope_absolute'], 'absolute')
        limits_map['gz_m'] = (
            limits['finest_prescribed_gz_absolute_m']
            if evaluation_name == 'prescribed_heel' else None, 'absolute')
    metrics = {}
    for key, computed_value in computed.items():
        limit, limit_kind = limits_map.get(key, (None, 'absolute'))
        metrics[key] = _error_record(
            key, computed_value, reference[key], unit=_unit_for(key),
            limit=limit, limit_kind=limit_kind,
            previous=(previous or {}).get(key),
            ratio=ratio,
            note=('free equilibrium is constructed for exactly zero lever; '
                  'only the absolute error is defined'
                  if key == 'gz_m' and evaluation_name == 'free_equilibrium'
                  else None))
    return metrics


def _unit_for(key):
    if key.endswith('_m') or key.endswith('_m3') or key == 'gz_m':
        return 'm3' if key.endswith('_m3') else 'm'
    if key in ('p', 'q'):
        return 'waterplane slope (dimensionless)'
    return ''


def run_geometry_suite(sequences=None, hooks=None):
    """Refine longitudinal stations and section vertices separately."""
    hooks = dict(hooks or {})
    sequences = (sequences if sequences is not None
                 else hooks.get('sequences', DEFAULT_GEOMETRY_SEQUENCES))
    evaluate_plane = hooks.get('evaluate_plane', _default_evaluate_plane)
    solve = hooks.get('solve_equilibrium', stability.solve_loaded_equilibrium)
    oracle = _load_oracle('coupled_ellipsoid_oracles.py').oracle()
    reference = _geometry_reference(oracle)
    heel_deg = reference['heel_deg']

    built = []
    for sequence in sequences:
        levels = []
        previous_metrics = {}
        previous_ratio = None
        for index, level in enumerate(sequence['levels']):
            refinement = dict(sequence.get('fixed_parameter') or {})
            refinement.update(level)
            hull = fixtures.ellipsoid_geometry(
                int(refinement['longitudinal_stations']),
                int(refinement['section_vertices']))
            before = _payload_sha256(hull)
            # Refinement is measured in intervals, not nodes: a 41/81/161
            # station mesh has 40/80/160 intervals and therefore exactly halves
            # each step. A section vertex count is a plain node count.
            ratio = None
            if index and previous_ratio is not None:
                current = _refinement_count(refinement,
                                            sequence['refined_parameter'])
                ratio = float(current) / float(previous_ratio)
                if not ratio > 1.0:
                    ratio = None
            sample = {
                'suite': 'geometry',
                'sequence': sequence['name'],
                'refined_parameter': sequence['refined_parameter'],
                'level': index,
                'refinement': {key: int(value)
                               for key, value in sorted(refinement.items())},
                'refinement_ratio_to_previous': ratio,
                'status': 'completed',
                'fixture_sha256_before': before,
                'fixture_sha256_after': before,
                'fixture_unchanged': True,
                'evaluations': {},
                'notes': [],
            }
            evaluations = [
                ('direct_plane',
                 'Integrate the declared waterplane plane z = p*x + q*y + d '
                 'directly on the mesh, without solving an equilibrium.',
                 lambda hull=hull: evaluate_plane(hull, reference['p'],
                                                  reference['q'], reference['d_m']),
                 {'volume_m3': 'volume', 'buoyancy_centre_x_m': 'xlcb',
                  'buoyancy_centre_y_m': 'yb', 'buoyancy_centre_z_m': 'zb'}),
                ('free_equilibrium',
                 'Public solve_loaded_equilibrium with free heel and trim and '
                 'the analytic free-equilibrium CG.',
                 lambda hull=hull: solve(
                     hull, fixtures.ellipsoid_loading(
                         reference['mass_t'], reference['free_equilibrium_cg_m']),
                     {}),
                 {'volume_m3': 'volume_m3', 'buoyancy_centre_x_m':
                  'buoyancy_centre_x_m', 'buoyancy_centre_y_m':
                  'buoyancy_centre_y_m', 'buoyancy_centre_z_m':
                  'buoyancy_centre_z_m', 'p': 'p', 'q': 'q',
                  'waterline_d_m': 'waterline_d_m', 'gz_m': 'gz_m'}),
                ('prescribed_heel',
                 'Public solve_loaded_equilibrium with the analytic heel '
                 'prescribed and longitudinal equilibrium free.',
                 lambda hull=hull: solve(
                     hull, fixtures.ellipsoid_loading(
                         reference['mass_t'], reference['constrained_heel_cg_m']),
                     {'heel_deg': heel_deg}),
                 {'volume_m3': 'volume_m3', 'buoyancy_centre_x_m':
                  'buoyancy_centre_x_m', 'buoyancy_centre_y_m':
                  'buoyancy_centre_y_m', 'buoyancy_centre_z_m':
                  'buoyancy_centre_z_m', 'p': 'p', 'q': 'q',
                  'waterline_d_m': 'waterline_d_m', 'gz_m': 'gz_m'}),
            ]
            for name, description, call, mapping in evaluations:
                record = _run_evaluation(name, description, call, mapping,
                                         reference, previous_metrics.get(name),
                                         ratio, sampled_state=name != 'direct_plane')
                sample['evaluations'][name] = record
                if record['status'] != 'completed':
                    sample['status'] = record['status']
                # Always remember this level's errors so the next level can
                # form an order, including the level right after the coarsest.
                if record['status'] == 'completed':
                    previous_metrics[name] = {
                        key: value['absolute_error']
                        for key, value in record['metrics'].items()
                        if value['status'] == 'ok'}
                else:
                    # An order requires adjacent valid levels, not the last
                    # successful error across a failed refinement step.
                    previous_metrics[name] = {}
            sample['fixture_sha256_after'] = _payload_sha256(hull)
            sample['fixture_unchanged'] = (
                sample['fixture_sha256_after'] == before)
            if not sample['fixture_unchanged']:
                sample['status'] = 'fixture_mutated'
                sample['notes'].append(
                    'the supplied fixture changed during evaluation')
            previous_ratio = _refinement_count(
                refinement, sequence['refined_parameter'])
            levels.append(sample)
        built.append({
            'name': sequence['name'],
            'refined_parameter': sequence['refined_parameter'],
            'refined_measure': ('intervals = stations - 1'
                                if sequence['refined_parameter']
                                == 'longitudinal_stations' else 'nodes'),
            'fixed_parameter': dict(sequence.get('fixed_parameter') or {}),
            'levels': levels,
            'observed_orders': _sequence_orders(levels),
            'order_interpretation': _order_interpretation(levels, reference),
            'finest_mesh_comparison': _finest_mesh_comparison(levels),
        })

    finest = _finest_mesh(built)
    suite = {
        'title': 'Hull discretization: volume, buoyancy centre, p, q, d and GZ',
        'oracle_source': 'docs/plimsoll-1.0/evidence/coupled_ellipsoid_oracles.py',
        'oracle': reference,
        'declared_thresholds': dict(GEOMETRY_THRESHOLDS),
        'declared_before_run': True,
        'sequences': built,
        'shared_finest_mesh': finest['label'],
        'shared_finest': finest['metrics'],
        'fixture_unchanged': all(level['fixture_unchanged']
                                 for sequence in built for level in sequence['levels']),
        'checks': _geometry_checks(built, finest),
        'notes': [
            'The ellipsoid is sampled analytically and each mesh is a closed '
            'polygon hull; the analytic oracle is a continuous integral and is '
            'never fitted to a sampled hull.',
            'The fixed other axis supplies a discretization floor, so the '
            'observed order is evidence about the model, not a guaranteed '
            'pure order.',
        ],
    }
    suite['passed'] = (all(check['passed'] for check in suite['checks'])
                       and suite['fixture_unchanged'])
    return suite


REQUIRED_RESIDUAL_COMPONENTS = ('volume', 'longitudinal', 'transverse')
REQUIRED_PRESCRIBED_RESIDUAL_COMPONENTS = ('volume', 'longitudinal')
GEOMETRY_SOLVER_METRICS = ('volume_m3', 'buoyancy_centre_x_m',
                           'buoyancy_centre_y_m', 'buoyancy_centre_z_m',
                           'p', 'q', 'waterline_d_m', 'gz_m')
DIRECT_PLANE_METRICS = ('volume_m3', 'buoyancy_centre_x_m',
                        'buoyancy_centre_y_m', 'buoyancy_centre_z_m')


def _run_evaluation(name, description, call, mapping, reference, previous,
                    ratio, sampled_state):
    """Run one evaluation, retaining failure instead of dropping the sample."""
    record = {'name': name, 'description': description,
              'status': 'completed', 'metrics': {},
              'max_abs_scaled_residual': None, 'converged': None,
              'required_residual_components': [],
              'missing_residual_components': [],
              'non_finite_residual_components': [],
              'missing_metrics': [], 'notes': [], 'solver': None}
    try:
        raw = call()
    except Exception as error:                      # Retain, never hide.
        record['status'] = 'error'
        record['notes'].append(f'{type(error).__name__}: {error}')
        for key in mapping:
            record['metrics'][key] = _error_record(key, None, reference.get(key))
        record['missing_metrics'] = sorted(mapping)
        return record

    if sampled_state:
        record['converged'] = raw.get('converged')
        # A declared convergence claim must be the boolean true itself. A
        # truthy string or a missing key is not evidence of convergence.
        if record['converged'] is not True:
            record['status'] = 'failed'
            record['notes'].append(
                f'convergence must be boolean true, got '
                f'{record["converged"]!r}')
            record['notes'].append(
                '; '.join(str(item.get('message'))
                           for item in (raw.get('diagnostics') or [])
                           if isinstance(item, dict)))
        required = (REQUIRED_PRESCRIBED_RESIDUAL_COMPONENTS
                    if (raw.get('mode') == 'prescribed_heel'
                        or raw.get('mode') == 'prescribed')
                    else REQUIRED_RESIDUAL_COMPONENTS)
        scaled = ((raw.get('residuals') or {}).get('scaled') or {})
        record['required_residual_components'] = list(required)
        record['missing_residual_components'] = sorted(
            key for key in required if key not in scaled)
        record['non_finite_residual_components'] = sorted(
            key for key in required
            if key in scaled and _finite(scaled[key]) is None)
        finite_required = [_finite(scaled[key]) for key in required
                           if key in scaled]
        # Every required component contributes; a missing or non-finite one
        # makes the maximum unavailable instead of being dropped.
        if (record['missing_residual_components']
                or record['non_finite_residual_components']):
            record['max_abs_scaled_residual'] = None
            record['status'] = 'residual_unavailable'
            record['notes'].append(
                'scaled residual incomplete: missing '
                f'{record["missing_residual_components"]}, non-finite '
                f'{record["non_finite_residual_components"]}')
        elif record['converged'] is not True:
            record['max_abs_scaled_residual'] = max(
                abs(value) for value in finite_required)
        else:
            record['max_abs_scaled_residual'] = max(
                abs(value) for value in finite_required)
            if record['max_abs_scaled_residual'] > \
                    GEOMETRY_THRESHOLDS['scaled_residual_max']:
                record['status'] = 'residual_exceeded'
                record['notes'].append(
                    'scaled equilibrium residual exceeds the declared 1e-6')
        record['solver'] = {
            'method': (raw.get('solver') or {}).get('method'),
            'iterations': (raw.get('solver') or {}).get('iterations'),
            'evaluations': (raw.get('solver') or {}).get('evaluations'),
            'mode': raw.get('mode'),
            'method_version': raw.get('method_version'),
        }

    values = {}
    for key, field in mapping.items():
        if isinstance(raw, dict):
            if key == 'buoyancy_centre_x_m' and field == 'xlcb':
                values[key] = raw.get(field)
            elif field == 'buoyancy_centre_x_m':
                centre = raw.get('buoyancy_centre_m') or []
                values[key] = centre[0] if len(centre) > 0 else None
            elif field == 'buoyancy_centre_y_m':
                centre = raw.get('buoyancy_centre_m') or []
                values[key] = centre[1] if len(centre) > 1 else None
            elif field == 'buoyancy_centre_z_m':
                centre = raw.get('buoyancy_centre_m') or []
                values[key] = centre[2] if len(centre) > 2 else None
            else:
                values[key] = raw.get(field)
        else:
            values[key] = None
    reference_values = {
        'volume_m3': reference['volume_m3'],
        'buoyancy_centre_x_m': reference['buoyancy_centre_m'][0],
        'buoyancy_centre_y_m': reference['buoyancy_centre_m'][1],
        'buoyancy_centre_z_m': reference['buoyancy_centre_m'][2],
        'p': reference['p'], 'q': reference['q'],
        'waterline_d_m': reference['d_m'], 'gz_m': 0.0,
    }
    if name == 'prescribed_heel':
        reference_values['gz_m'] = reference['prescribed_gz_m']
    record['metrics'] = _geometry_evaluation_metrics(
        name, values, reference_values, previous, ratio)
    record['values'] = {key: _finite(value) for key, value in values.items()}
    non_finite = sorted(key for key, value in values.items()
                        if _is_non_finite(value))
    if non_finite:
        record['status'] = 'non_finite'
        record['notes'].append(f'non-finite solver values: {non_finite}')
    # A required value that is absent stays unavailable; it never becomes a
    # silently dropped key that carries a passing limit.
    record['missing_metrics'] = sorted(
        key for key, value in values.items() if value is None)
    unusable = sorted(key for key, metric in record['metrics'].items()
                      if metric['status'] != 'ok')
    if record['missing_metrics'] or unusable:
        record['notes'].append(
            'missing or unusable required metrics: '
            f'{sorted(set(record["missing_metrics"]) | set(unusable))}')
        if record['status'] == 'completed':
            record['status'] = 'metric_unavailable'
    return record


def _sequence_orders(levels):
    """Observed orders per metric, read straight from the retained records."""
    orders = {}
    for level in levels:
        for name, evaluation in level['evaluations'].items():
            for key, metric in evaluation['metrics'].items():
                orders.setdefault(f'{name}.{key}', []).append(
                    metric['observed_order'])
    return orders


def _refinement_count(refinement, parameter):
    """Intervals for a station mesh, nodes for a section vertex count.

    Station refinement converges per interval, so 41/81/161 stations is
    40/80/160 intervals and halves exactly. Section vertices are a direct
    node count, so 32/64/128 vertices doubles exactly.
    """
    value = int(refinement[parameter])
    if parameter == 'longitudinal_stations':
        if value < 2:
            raise ValueError('a station mesh needs at least one interval')
        return value - 1
    if value < 1:
        raise ValueError('section_vertices must be positive')
    return value


def _order_interpretation(levels, reference):
    """Identify equilibrium constraints without inferring an error source."""
    target_volume = reference['mass_t'] / reference['rho_t_m3']
    beam = 2.0 * fixtures.ELLIPSOID['semi_axes_m'][1]
    tolerance = GEOMETRY_THRESHOLDS['scaled_residual_max']
    finest = levels[-1]['evaluations']
    rows = {}
    for name, evaluation in finest.items():
        for key, metric in evaluation['metrics'].items():
            error = metric['absolute_error']
            scale = None
            if error is None:
                classification = 'unavailable'
            elif name == 'direct_plane':
                classification = 'fixed_plane_mesh_comparison'
            elif key == 'volume_m3':
                classification, scale = 'equilibrium_constraint', target_volume
            elif name == 'free_equilibrium' and key == 'gz_m':
                classification, scale = 'equilibrium_constraint', beam
            else:
                classification = 'mixed_error_unclassified'
            rows[f'{name}.{key}'] = {
                'finest_absolute_error': error,
                'characteristic_scale': scale,
                'solver_tolerance_scale': tolerance * scale if scale is not None else None,
                'classification': classification,
            }
    return {
        'definition': 'Solved volume and free-equilibrium GZ satisfy residual '
                      'constraints; small errors in those quantities do not '
                      'isolate mesh accuracy. Other solved-state errors may mix '
                      'discretization and achieved solver residual. A small '
                      'error or raw order alone does not establish round-off '
                      'or a limiting discretization floor.',
        'metrics': rows,
    }


def _finest_mesh_comparison(levels):
    """Error relative to the finite finest mesh error of the same sequence.

    This is a comparison between measured meshes, not a decomposition of the
    discretization error. The subtracted value is the finite finest mesh's own
    error, which still contains the effect of the axis held fixed; it is not a
    measured or analytic floor for that axis, so no claim is made about which
    axis "sets" the order. Reported as evidence only and never used to score
    acceptance.
    """
    if len(levels) < 2:
        return {'available': False, 'reason': 'sequence too short',
                'used_for_acceptance': False, 'observed_orders': {}}
    finest = levels[-1]['evaluations']
    comparison = {}
    orders = {}
    for name, evaluation in finest.items():
        if evaluation['status'] != 'completed':
            continue
        for key, metric in evaluation['metrics'].items():
            if metric['status'] != 'ok':
                continue
            reference = metric['absolute_error']
            row = {'finest_mesh_absolute_error': reference}
            series, ratios = [], []
            for level in levels[:-1]:
                previous_evaluation = level['evaluations'][name]
                previous = previous_evaluation['metrics'][key]
                error = (previous['absolute_error']
                         if previous_evaluation['status'] == 'completed'
                         and previous['status'] == 'ok' else None)
                difference = error - reference if error is not None else None
                row[f'level_{level["level"]}_absolute_error'] = error
                row[f'level_{level["level"]}_minus_finest_mesh'] = difference
                # Keep gaps so the diagnostic cannot compress a failed
                # level out of an adjacent refinement ratio either.
                series.append(difference)
                ratios.append(level.get('refinement_ratio_to_previous'))
            comparison[f'{name}.{key}'] = row
            values = []
            for index in range(1, len(series)):
                order, _status = _observed_order(series[index - 1], series[index],
                                                 ratios[index])
                values.append(order)
            if any(value is not None for value in values):
                orders[f'{name}.{key}'] = values
    return {
        'available': True,
        'used_for_acceptance': False,
        'definition': 'absolute error minus the finite finest mesh error of the '
                      'same sequence; the subtracted value is itself a measured '
                      'mesh error that still contains the fixed-axis effect, so '
                      'this is a comparison, not a limiting floor or a claim '
                      'about a pure order',
        'metrics': comparison,
        'observed_orders': orders,
        'observed_order_definition':
            'observed order of the finite-finest-mesh-subtracted series using '
            'the declared refinement ratio',
    }


def _finest_mesh(built):
    """Merge the finest level of every sequence into one shared comparison."""
    finest = None
    for sequence in built:
        level = sequence['levels'][-1]
        key = tuple(sorted(level['refinement'].items()))
        if finest is None:
            finest = {'label': ' x '.join(
                f'{name}={value}' for name, value in key),
                'refinement': dict(key), 'metrics': {}}
        elif tuple(sorted(finest['refinement'].items())) != key:
            finest['note'] = (
                'sequences do not share a finest mesh; acceptance is evaluated '
                'on the coarsest common refinement')
    if finest is None:
        return {'label': 'none', 'refinement': {}, 'metrics': {}, 'sources': []}
    sources = []
    for sequence in built:
        level = sequence['levels'][-1]
        if tuple(sorted(level['refinement'].items())) != tuple(
                sorted(finest['refinement'].items())):
            continue
        sources.append({'sequence': sequence['name'], 'level': level['level']})
        for name, evaluation in level['evaluations'].items():
            bucket = finest['metrics'].setdefault(name, {})
            for key, metric in evaluation['metrics'].items():
                current = bucket.get(key)
                if current is None or (
                        metric['absolute_error'] is not None
                        and (current['absolute_error'] is None
                             or metric['absolute_error']
                             > current['absolute_error'])):
                    bucket[key] = dict(metric)
    finest['sources'] = sources
    return finest


def _geometry_checks(built, finest):
    """Integrity of every declared evaluation, then accuracy at the finest mesh.

    Integrity is checked per evaluation so that a single failed coarse level
    fails the suite even when the finest mesh would have passed; the accuracy
    limits are then applied to the shared finest mesh.
    """
    limits = GEOMETRY_THRESHOLDS
    checks = []
    incomplete, unconverged = [], []
    unavailable_residual, missing_metrics = [], []
    residuals = []
    for sequence in built:
        for level in sequence['levels']:
            for name, evaluation in level['evaluations'].items():
                label = f"{sequence['name']}/{level['level']}/{name}"
                if evaluation['status'] != 'completed':
                    incomplete.append(f'{label}: {evaluation["status"]}')
                if name == 'direct_plane':
                    continue
                if evaluation['converged'] is not True:
                    unconverged.append(f'{label}: {evaluation["converged"]!r}')
                if evaluation['max_abs_scaled_residual'] is None:
                    unavailable_residual.append(
                        f'{label}: missing {evaluation["missing_residual_components"]},'
                        f' non-finite {evaluation["non_finite_residual_components"]}')
                else:
                    residuals.append(evaluation['max_abs_scaled_residual'])
                if evaluation['missing_metrics']:
                    missing_metrics.append(
                        f'{label}: {evaluation["missing_metrics"]}')
    checks.append(_check(
        'geometry', 'every_declared_evaluation_completed',
        'every declared evaluation, including the direct plane integration, '
        'completed', not incomplete,
        limit=limits['every_declared_state_converged'],
        detail=f'{len(incomplete)} incomplete: {incomplete}' if incomplete
               else f'{len(built)} sequences completed'))
    checks.append(_check(
        'geometry', 'every_declared_state_converged',
        'every declared solved state reports convergence as boolean true',
        not unconverged, limit=limits['every_declared_state_converged'],
        detail=f'{len(unconverged)} not converged: {unconverged}'
               if unconverged else 'all declared solved states converged'))
    checks.append(_check(
        'geometry', 'residuals_fully_available',
        'every required scaled residual component is present and finite',
        not unavailable_residual,
        detail=f'{len(unavailable_residual)} unavailable: '
               f'{unavailable_residual}' if unavailable_residual
               else f'{len(residuals)} declared solved states complete'))
    checks.append(_check(
        'geometry', 'every_required_metric_present',
        'every declared metric of every evaluation is present and finite',
        not missing_metrics,
        detail=f'{len(missing_metrics)} missing: {missing_metrics}'
               if missing_metrics else 'no required metric missing'))
    checks.append(_check(
        'geometry', 'scaled_residual_max',
        'every declared solved state has scaled residual <= 1e-6',
        max(residuals, default=None), limit=limits['scaled_residual_max'],
        detail=f'{len(residuals)} declared solved states with complete residuals'))

    bucket = finest['metrics']
    for name, evaluation in bucket.items():
        for key, metric in sorted(evaluation.items()):
            if key == 'gz_m' and name != 'prescribed_heel':
                continue
            if key == 'gz_m':
                limit = limits['finest_prescribed_gz_absolute_m']
                kind = 'absolute'
                requirement = ('prescribed GZ error <= 0.001 m at the shared '
                               'finest mesh')
            elif key == 'volume_m3':
                limit, kind = limits['finest_volume_relative'], 'relative'
                requirement = ('volume relative error <= 1e-3 at the shared '
                               'finest mesh')
            elif key.startswith('buoyancy_centre'):
                limit, kind = limits['finest_buoyancy_centre_absolute_m'], 'absolute'
                requirement = (f'{key} error <= 0.01 m at the shared finest mesh')
            elif key == 'waterline_d_m':
                limit, kind = limits['finest_waterline_d_absolute_m'], 'absolute'
                requirement = 'd error <= 0.01 m at the shared finest mesh'
            elif key == 'p':
                limit, kind = limits['finest_trim_slope_absolute'], 'absolute'
                requirement = 'p error <= 1e-4 at the shared finest mesh'
            else:
                limit, kind = limits['finest_heel_slope_absolute'], 'absolute'
                requirement = 'q error <= 1e-4 at the shared finest mesh'
            checks.append(_check(
                'geometry', f'shared_finest.{name}.{key}', requirement,
                metric['absolute_error'] if kind == 'absolute'
                else metric['relative_error'],
                limit=limit,
                detail=f"{finest['label']} via "
                       f"{', '.join(source['sequence'] for source in finest['sources'])}"
                       + (f"; {metric['status']}" if metric['status'] != 'ok'
                          else '')))
    return checks


# ----------------------------------------------------------------------- gz

def _trapezoid_area(angles_rad, values):
    """Composite trapezoid over the sampled lever; units are m*rad."""
    terms = []
    for index in range(len(values) - 1):
        terms.append(0.5 * (values[index] + values[index + 1])
                     * (angles_rad[index + 1] - angles_rad[index]))
    return math.fsum(terms)


def run_gz_suite(levels=None, hooks=None):
    """Refine the sampled righting-lever curve over 0..30 degrees."""
    hooks = dict(hooks or {})
    levels = list(levels if levels is not None
                  else hooks.get('levels', DEFAULT_GZ_LEVELS))
    curve_solver = hooks.get('stability_curve', stability.stability_curve)
    box_oracle = _load_oracle('wall_sided_box_oracle.py')
    declared = box_oracle.oracle()
    limit_deg = float(declared['valid_range']['limit_deg'])
    exact_area = box_oracle.exact_area_m_rad(GZ_MAX_ANGLE_DEG)

    hull = fixtures.box_geometry()
    state = fixtures.box_loading()
    before = _payload_sha256((hull, state))

    built = []
    for index, step in enumerate(levels):
        count = int(round(GZ_MAX_ANGLE_DEG / float(step))) + 1
        angles = [index_step * float(step) for index_step in range(count)]
        built.append(_gz_level(index, float(step), angles, hull, state,
                               curve_solver, box_oracle, limit_deg,
                               exact_area,
                               previous=built[-1] if built else None))

    common = _common_angles(built)
    samples = []
    for level in built:
        for sample in level['fixed_angle']['samples']:
            sample['is_common_angle'] = sample['angle_deg'] in common
        level['common_angles_deg'] = sorted(common)
        level['fixed_angle']['max_abs_error_common_angles_m'] = _max_error(
            [sample for sample in level['fixed_angle']['samples']
             if sample['is_common_angle']])
        samples.append(level)

    area_errors = [level['curve_area']['relative_area_error']
                   for level in samples]
    fixed_errors = [level['fixed_angle']['max_abs_error_m']
                    for level in samples]
    checks = []
    for index, level in enumerate(samples):
        checks.append(_check(
            'gz', f'every_sample_converged.level_{index}',
            'every sampled angle produced a converged equilibrium',
            level['status'] == 'completed',
            limit=GZ_THRESHOLDS['every_sample_converged'],
            detail=f"endpoint {level['endpoint']}"))
        checks.append(_check(
            'gz', f'model_applicable.level_{index}',
            'every sampled angle reported model_applicable true and the curve '
            'endpoint is a resolved sample, not a model limit',
            level.get('not_applicable_samples', 0) == 0
            and level['endpoint'].get('kind') not in ('model_limit',
                                                      'failed_sample'),
            limit=True,
            detail=f"endpoint kind {level['endpoint'].get('kind')}, "
                   f"{level.get('not_applicable_samples', 0)} samples "
                   'did not report model_applicable boolean true'))
        checks.append(_check(
            'gz', f'fixed_angle_agreement.level_{index}',
            'every valid GZ sample matches the analytic lever within 1e-6 m',
            level['fixed_angle']['max_abs_error_m'],
            limit=GZ_THRESHOLDS['fixed_angle_absolute_m'],
            detail=f"{level['sample_count']} samples, "
                   f"{level['fixed_angle']['converged_samples']} converged, "
                   f"step {level['step_deg']} deg"))
        checks.append(_check(
            'gz', f'fixed_angle_agreement_common.level_{index}',
            'common-angle agreement within 1e-6 m on the angles shared by '
            'every level', level['fixed_angle']['max_abs_error_common_angles_m'],
            limit=GZ_THRESHOLDS['fixed_angle_absolute_m'],
            detail=f'{len(level["common_angles_deg"])} common angles'))
        checks.append(_check(
            'gz', f'samples_inside_declared_wedge.level_{index}',
            'every sampled angle satisfies abs(tan(phi))*B/2 < min(T, depth-T)',
            level['out_of_bounds_samples'] == 0,
            limit=GZ_THRESHOLDS['every_sample_inside_declared_wedge'],
            detail=f'declared wedge +/-{limit_deg:.6f} deg'))
    checks.extend(_monotonic_check(
        'gz', 'curve_area_relative_error',
        'trapezoidal area error decreases across the four sampling levels',
        area_errors, limit=GZ_THRESHOLDS['finest_area_relative'],
        limit_name='finest_area_relative'))
    checks.append(_check(
        'gz', 'observed_area_order_available',
        'the finest level reports a finite observed area order',
        samples[-1]['curve_area']['observed_order'] if samples else None,
        passed=bool(samples
                    and samples[-1]['curve_area']['observed_order'] is not None),
        detail='an unavailable order is reported, never replaced by a claim'))

    after = _payload_sha256((hull, state))
    suite = {
        'title': 'GZ sampling: fixed-angle solver accuracy and curve-area quadrature',
        'oracle_source': 'docs/plimsoll-1.0/evidence/wall_sided_box_oracle.py',
        'oracle': {
            'kind': declared['kind'],
            'geometry_m': declared['geometry_m'],
            'loading': declared['loading'],
            'derived': declared['derived'],
            'valid_range': declared['valid_range'],
            'exact_area_m_rad_at_30_deg': exact_area,
            'gz_formula': '(GM + BM*tan(phi)^2/2)*sin(phi)',
            'area_formula': 'GM*(1-cos P) + BM/2*(1/cos P + cos P - 2)',
            'independent_simpson_area_m_rad': declared['exact_area_m_rad'][
                'independent_simpson_at_30_deg'],
        },
        'declared_thresholds': dict(GZ_THRESHOLDS),
        'declared_before_run': True,
        'angle_range_deg': [0.0, GZ_MAX_ANGLE_DEG],
        'levels': samples,
        'metric_definitions': {
            'fixed_angle': 'per sampled waterplane slope angle, the absolute '
                           'difference between the public solver lever and the '
                           'analytic lever',
            'curve_area': 'the composite trapezoid of the solver lever over '
                          'the sampled angles compared with the exact integral',
            'relationship': 'fixed-angle accuracy is independent of the sample '
                            'count; curve-area error contains the sampling '
                            'quadrature error as well',
        },
        'fixture_sha256_before': before,
        'fixture_sha256_after': after,
        'fixture_unchanged': (before == after
                              and all(level['fixture_unchanged'] for level in samples)),
        'no_claim': [
            'No AVS or unrestricted-angle validation is made in this range; a '
            'smaller step does not improve solver accuracy at a fixed angle.',
        ],
        'checks': checks,
    }
    suite['passed'] = (all(check['passed'] for check in checks)
                       and suite['fixture_unchanged'])
    return suite


def _max_error(samples):
    errors = [sample['absolute_error_m'] for sample in samples
              if sample['absolute_error_m'] is not None]
    return max(errors) if errors else None


def _common_angles(levels):
    shared = None
    for level in levels:
        values = {sample['angle_deg'] for sample in level['fixed_angle']['samples']}
        shared = values if shared is None else (shared & values)
    return sorted(shared or set())


def _gz_level(index, step, angles, hull, state, curve_solver, box_oracle,
              limit_deg, exact_area, previous=None):
    """One sampling level: fixed-angle agreement and curve-area error apart."""
    ratio = None
    if previous is not None:
        ratio = float(previous['step_deg']) / float(step)
    record = {
        'suite': 'gz',
        'level': index,
        'step_deg': step,
        'angles_deg': list(angles),
        'sample_count': len(angles),
        'status': 'completed',
        'fixture_sha256_before': _payload_sha256((hull, state, list(angles))),
        'fixture_sha256_after': '',
        'fixture_unchanged': False,
        'notes': [],
    }
    try:
        curve = curve_solver(hull, state, list(angles), [])
    except Exception as error:                       # Retain, never hide.
        record['status'] = 'error'
        record['notes'].append(f'{type(error).__name__}: {error}')
        record['fixed_angle'] = {
            'samples': [dict(angle_deg=angle, status='not_run',
                             computed_gz_m=None, analytic_gz_m=None,
                             absolute_error_m=None, is_common_angle=False)
                        for angle in angles],
            'max_abs_error_m': None, 'converged_samples': 0,
            'max_abs_error_common_angles_m': None,
        }
        record['curve_area'] = {
            'quadrature': 'composite_trapezoid_on_solver_samples',
            'trapezoid_area_m_rad': None, 'exact_area_m_rad': exact_area,
            'absolute_area_error': None, 'relative_area_error': None,
            'observed_order': None,
            'observed_order_status': 'unavailable_no_previous_level',
            'refinement_ratio_to_previous': ratio,
        }
        record['sampled_maximum'] = None
        record['endpoint'] = {'kind': 'not_run', 'angle_deg': None, 'gz_m': None}
        record['not_applicable_samples'] = 0
        record['out_of_bounds_samples'] = 0
        record['avs_deg'] = None
        record['zero_crossing_count'] = 0
        record['solver_method_version'] = None
        record['fixed_angle'] = {
            'definition': 'absolute agreement between the public solver lever '
                          'and the analytic lever at each sampled angle',
            'unit': 'm',
            'samples': [dict(angle_deg=angle, status='failed_sample',
                             analytic_gz_m=_finite(box_oracle.gz_m(angle)),
                             computed_gz_m=None, absolute_error_m=None,
                             is_common_angle=False, converged=None,
                             model_applicable=None, inside_declared_wedge=True,
                             diagnostics=[], failure_reason='not_run')
                        for angle in angles],
            'max_abs_error_m': None,
            'mean_abs_error_m': None,
            'converged_samples': 0,
            'available_samples': 0,
        }
        record['curve_area'] = {
            'definition': 'composite trapezoid of the solver lever over the '
                          'sampled angles compared with the exact analytic '
                          'integral',
            'quadrature': 'composite_trapezoid_on_solver_samples',
            'unit': 'm*rad',
            'trapezoid_area_m_rad': None, 'exact_area_m_rad': exact_area,
            'absolute_area_error': None, 'relative_area_error': None,
            'observed_order': None,
            'observed_order_status': 'unavailable_no_previous_level',
            'refinement_ratio_to_previous': ratio,
            'sample_count': len(angles),
        }
        _seal_gz_hashes(record, hull, state, list(angles))
        return record

    rows = {float(row['angle_deg']): row for row in curve.get('rows', [])}
    samples = []
    converged = 0
    non_finite = 0
    unusable = 0
    not_applicable = 0
    out_of_bounds = 0
    for angle in angles:
        row = rows.get(float(angle))
        computed = row.get('gz_m') if isinstance(row, dict) else None
        analytic = box_oracle.gz_m(angle)
        equilibrium = (row.get('equilibrium') or {}) if isinstance(row, dict) else {}
        validity = (row.get('validity') or {}) if isinstance(row, dict) else {}
        # Convergence and model applicability are separate claims; a sample
        # that solved a state outside the model still cannot be evidence.
        solved = equilibrium.get('converged')
        applicable = validity.get('model_applicable')
        if applicable is not True:
            not_applicable += 1
        inside = box_oracle.bounds_ok(angle)
        if not inside:
            out_of_bounds += 1
        base = {
            'angle_deg': angle, 'analytic_gz_m': _finite(analytic),
            'is_common_angle': False, 'converged': solved,
            'model_applicable': applicable,
            'inside_declared_wedge': inside,
            'diagnostics': _json_safe(equilibrium.get('diagnostics')),
        }
        # A lever must be a real finite number. Missing, None, bool, string,
        # NaN and inf are rejected before any quadrature is attempted.
        lever = _finite(computed)
        if isinstance(computed, bool) or not isinstance(computed, (int, float)):
            reason = 'non_numeric_lever' if computed is not None else 'missing_lever'
        elif _is_non_finite(computed):
            reason = 'non_finite_lever'
        elif applicable is False:
            reason = 'model_not_applicable'
        elif applicable is None:
            reason = 'missing_model_applicability'
        elif applicable is not True:
            reason = 'invalid_model_applicability'
        elif solved is not True:
            reason = 'not_converged'
        else:
            reason = None
        if reason is not None:
            if reason == 'non_finite_lever':
                non_finite += 1
            else:
                unusable += 1
            samples.append(dict(base, status='failed_sample',
                                computed_gz_m=None, absolute_error_m=None,
                                failure_reason=reason))
        else:
            converged += 1
            samples.append(dict(
                base, status='completed', computed_gz_m=lever,
                absolute_error_m=abs(lever - _finite(analytic)),
                failure_reason=None))
    if non_finite:
        record['status'] = 'non_finite'
    elif unusable or converged != len(angles):
        record['status'] = 'failed'
    record['not_applicable_samples'] = not_applicable

    angles_rad = [math.radians(angle) for angle in angles]
    levers = [entry['computed_gz_m'] for entry in samples]
    area = None
    relative = None
    absolute_area = None
    if record['status'] == 'completed':
        area = _trapezoid_area(angles_rad, levers)
        absolute_area = abs(area - exact_area)
        relative = absolute_area / abs(exact_area)
    previous_relative = (previous or {}).get('curve_area', {}).get(
        'relative_area_error')
    order, order_status = _observed_order(previous_relative, relative, ratio)
    record['fixed_angle'] = {
        'definition': 'absolute agreement between the public solver lever and '
                      'the analytic lever at each sampled angle',
        'unit': 'm',
        'samples': samples,
        'max_abs_error_m': _max_error(samples),
        'mean_abs_error_m': _mean_error(samples),
        'converged_samples': converged,
        'available_samples': len(samples),
    }
    record['curve_area'] = {
        'definition': 'composite trapezoid of the solver lever over the sampled '
                      'angles compared with the exact analytic integral',
        'quadrature': 'composite_trapezoid_on_solver_samples',
        'unit': 'm*rad',
        'trapezoid_area_m_rad': _finite(area),
        'exact_area_m_rad': exact_area,
        'absolute_area_error': _finite(absolute_area),
        'relative_area_error': _finite(relative),
        'observed_order': order,
        'observed_order_status': (order_status if previous is not None
                                  else 'unavailable_no_previous_level'),
        'refinement_ratio_to_previous': ratio,
        'sample_count': len(angles),
    }
    record['sampled_maximum'] = _json_safe(curve.get('maximum'))
    record['endpoint'] = _json_safe(curve.get('endpoint'))
    record['avs_deg'] = _json_safe(curve.get('avs_deg'))
    record['zero_crossing_count'] = len(curve.get('zero_crossings') or [])
    record['out_of_bounds_samples'] = out_of_bounds
    record['solver_method_version'] = curve.get('method_version')
    _seal_gz_hashes(record, hull, state, list(angles))
    return record


def _seal_gz_hashes(record, hull, state, angles):
    """Re-hash the supplied fixtures after the level ran, for real evidence."""
    record['fixture_sha256_after'] = _payload_sha256((hull, state, angles))
    record['fixture_unchanged'] = (
        record['fixture_sha256_after'] == record['fixture_sha256_before'])
    if not record['fixture_unchanged']:
        record['status'] = 'fixture_mutated'
        record['notes'].append('the supplied fixture changed during the level')


def _mean_error(samples):
    errors = [sample['absolute_error_m'] for sample in samples
              if sample['absolute_error_m'] is not None]
    return math.fsum(errors) / len(errors) if errors else None


# ------------------------------------------------------------------ flooding

def _flooding_reference(oracle):
    coupled = oracle['coupled_heave']
    return {
        'source': 'docs/plimsoll-1.0/evidence/flooding_oracles.py',
        'kind': coupled['kind'],
        'ship_dimensions_m': coupled['ship_dimensions_m'],
        'base_mass_t': float(coupled['base_mass_t']),
        'base_kg_m': float(coupled['base_cg_keel_m'][2]),
        'tank_dimensions_m': coupled['tank_dimensions_m'],
        'initial_volume_m3': float(coupled['initial_water_volume_m3']),
        'initial_draft_m': float(coupled['initial_draft_m']),
        'aperture_xyz_m': coupled['aperture_xyz_m'],
        'orifice_area_m2': float(coupled['orifice_area_m2']),
        'discharge_coefficient': float(coupled['discharge_coefficient']),
        'duration_s': float(coupled['time_s']),
        'net_sea_inflow_m3': float(coupled['net_sea_inflow_m3']),
        'final_draft_m': float(coupled['final_draft_m']),
        'draft_change_m': (float(coupled['final_draft_m'])
                           - float(coupled['initial_draft_m'])),
    }


def run_flooding_suite(levels=None, hooks=None):
    """Refine the flooding time step against the coupled-heave ODE oracle."""
    hooks = dict(hooks or {})
    levels = list(levels if levels is not None
                 else hooks.get('levels', DEFAULT_FLOODING_LEVELS))
    simulate = hooks.get('simulate_flooding', flooding.simulate_flooding)
    oracle = _load_oracle('flooding_oracles.py').oracle()
    reference = _flooding_reference(oracle)
    tank_id = fixtures.FLOODING['tank_id']
    condition = fixtures.FLOODING['condition_id']

    built = []
    for index, step in enumerate(levels):
        built.append(_flooding_level(index, float(step), simulate, reference,
                                     tank_id, condition,
                                     previous=built[-1] if built else None))
    influx_errors = [level['metrics']['net_sea_inflow_m3']['relative_error']
                     for level in built]
    draft_errors = [level['metrics']['draft_change_relative_error']
                    for level in built]
    limits = FLOODING_THRESHOLDS
    checks = []
    for index, level in enumerate(built):
        finite = all(level['finite_values'])
        checks.append(_check(
            'flooding', f'all_values_finite.level_{index}',
            'every reported flooding value is finite', finite,
            limit=limits['all_reported_values_finite'],
            detail=f"status {level['status']}/{level['stop_reason']}"))
        checks.append(_check(
            'flooding', f'scheduled_completion.level_{index}',
            'the run completed with the scheduled duration elapsed',
            level['status'] == limits['required_status']
            and level['stop_reason'] == limits['required_stop_reason'],
            detail=f"status {level['status']}, stop reason {level['stop_reason']}, "
                   f"{level['accepted_timeline_steps']} accepted steps"))
        checks.append(_check(
            'flooding', f'timeline_complete.level_{index}',
            'every accepted state converged and carried the required finite '
            'residual, attitude, volume and time values',
            not level['broken_states'] and not level['not_converged_states'],
            detail=(f"{level['broken_states']} "
                    f"{level['not_converged_states']}").strip()
                   or f"{level['complete_accepted_states']} complete states"))
        final_report = level['final_state_report']
        checks.append(_check(
            'flooding', f'final_state_complete.level_{index}',
            'the final state converged and carried the required finite '
            'residual, attitude and tank volume values',
            final_report['present'] and not final_report['problems']
            and final_report['converged'] is True,
            detail=f"present={final_report['present']}, "
                   f"converged={final_report['converged']!r}, "
                   f"problems={final_report['problems']}"))
        consistency = level['time_consistency']
        checks.append(_check(
            'flooding', f'time_consistency.level_{index}',
            'accepted times start at zero, never decrease, and both the last '
            'timeline time and the final state time equal the declared '
            'duration and each other',
            not consistency['problems'],
            detail='; '.join(consistency['problems']) or
                   f"last timeline {level['last_timeline_time_s']}, "
                   f"final {level['final_time_s']}, "
                   f"duration {level['scheduled_duration_s']}"))
        checks.append(_check(
            'flooding', f'timeline_final_time.level_{index}',
            'the last accepted time equals the scheduled duration',
            level['final_time_s'] is not None
            and abs(level['final_time_s'] - level['scheduled_duration_s']) <= 1e-9,
            detail=f"final time {level['final_time_s']} of scheduled "
                   f"{level['scheduled_duration_s']}"))
        # The declared limits bound the magnitude of the conservation error;
        # the signed value stays in the report as the observation.
        checks.append(_check(
            'flooding', f'volume_conservation.level_{index}',
            'absolute volume conservation error <= 1e-9 m3',
            abs(level['volume_conservation_error_m3'])
            if level['volume_conservation_error_m3'] is not None else None,
            limit=limits['volume_conservation_absolute_m3'],
            detail=f"signed error {level['volume_conservation_error_m3']} m3"))
        checks.append(_check(
            'flooding', f'mass_conservation.level_{index}',
            'absolute mass conservation error <= 4.1e-8 t',
            abs(level['mass_conservation_error_t'])
            if level['mass_conservation_error_t'] is not None else None,
            limit=limits['mass_conservation_absolute_t'],
            detail=f"signed error {level['mass_conservation_error_t']} t"))
        checks.append(_check(
            'flooding', f'scaled_residual.level_{index}',
            'every accepted state has a scaled equilibrium residual <= 1e-6',
            level['max_abs_scaled_residual'],
            limit=limits['scaled_residual_max'],
            detail=f"{level['complete_accepted_states']} complete accepted states"))
    checks.extend(_monotonic_check(
        'flooding', 'influx_relative_error',
        'normalized net-inflow error decreases under time-step refinement',
        influx_errors, limit=limits['finest_influx_relative'],
        limit_name='finest_influx_relative'))
    checks.extend(_monotonic_check(
        'flooding', 'draft_change_relative_error',
        'normalized draft-change error decreases under time-step refinement',
        draft_errors, limit=limits['finest_draft_change_relative'],
        limit_name='finest_draft_change_relative'))

    suite = {
        'title': 'Flooding time integration against the coupled-heave ODE oracle',
        'oracle_source': 'docs/plimsoll-1.0/evidence/flooding_oracles.py',
        'oracle': reference,
        'declared_thresholds': dict(limits),
        'declared_before_run': True,
        'levels': built,
        'fixture_unchanged': all(level['fixture_unchanged'] for level in built),
        'notes': [
            'The observed time order is evidence about the implemented '
            'integration, not an automatic claim of a higher-order scheme.',
            'A finite, completed, scheduled-completion state with the declared '
            'conservation and residual limits can pass on its own.',
        ],
        'checks': checks,
    }
    suite['passed'] = (all(check['passed'] for check in suite['checks'])
                       and suite['fixture_unchanged'])
    return suite


def _flooding_level(index, step, simulate, reference, tank_id, condition,
                    previous=None):
    """One time-step level.

    The record starts complete, with every field the checks and the writers
    read already present, so an exception part way through leaves a usable
    failure record instead of a half-built one.
    """
    ratio = float(previous['time_step_s']) / step if previous else None
    project = fixtures.flooding_project()
    scenario = fixtures.flooding_scenario(step)
    before = _payload_sha256((project, scenario))
    initial_volume = float(fixtures.FLOODING['initial_volume_m3'])
    duration = float(scenario['duration_s'])
    record = {
        'suite': 'flooding', 'level': index, 'time_step_s': step,
        'refinement_ratio_to_previous': ratio,
        'status': 'not_run', 'stop_reason': None,
        'accepted_timeline_steps': None,
        'influx_m3': None, 'final_draft_m': None,
        'final_tank_volume_m3': None,
        'final_time_s': None,
        'last_timeline_time_s': None,
        'scheduled_duration_s': duration,
        'volume_conservation_error_m3': None,
        'mass_conservation_error_t': None,
        'max_abs_scaled_residual': None,
        'max_abs_heel_deg': None, 'max_abs_trim_deg': None,
        'complete_accepted_states': 0,
        'broken_states': [], 'not_converged_states': [],
        'final_state_report': _empty_final_state_report(tank_id),
        'time_consistency': {'initial_time_is_zero': False,
                             'times_nondecreasing': False,
                             'last_timeline_matches_duration': False,
                             'final_state_matches_duration': False,
                             'final_state_matches_timeline': False,
                             'problems': ['not_run']},
        'finite_values': [], 'fixture_sha256_before': before,
        'fixture_sha256_after': before, 'fixture_unchanged': True,
        'metrics': {}, 'notes': [],
        'diagnostics': [], 'failed_attempt': None,
        'solver_method_version': None, 'kernel_method_version': None,
        'validity': None,
    }
    try:
        result = simulate(project, condition, scenario, options={})
    except Exception as error:                       # Retain, never hide.
        record['status'] = 'error'
        record['notes'].append(f'{type(error).__name__}: {error}')
        record['finite_values'] = [False]
        record['metrics'] = _flooding_metrics(record, reference, initial_volume,
                                              None)
        _seal_flooding_hashes(record, project, scenario, before)
        return record

    final_state = result.get('final_state') or {}
    equilibrium = final_state.get('equilibrium') or {}
    timeline = result.get('timeline') or []
    volumes = final_state.get('volumes_m3') or {}
    influx = ((volumes.get(tank_id) - initial_volume)
              if isinstance(volumes.get(tank_id), (int, float))
              and not isinstance(volumes.get(tank_id), bool) else None)
    extremes = _timeline_extremes(timeline, tank_id)
    duration = record['scheduled_duration_s']
    final_report = _inspect_state(final_state, tank_id, 'final_state')
    # A separate final_state is part of the all-state residual/attitude
    # extrema even when it does not alias the last accepted timeline row.
    if (not final_report['present'] or final_report['problems']
            or final_report['converged'] is not True):
        for key in ('max_abs_scaled_residual', 'max_abs_heel_deg',
                    'max_abs_trim_deg'):
            extremes[key] = None
    else:
        final_extrema = {
            'max_abs_scaled_residual': final_report['max_abs_scaled_residual'],
            'max_abs_heel_deg': abs(_finite(equilibrium['heel_deg'])),
            'max_abs_trim_deg': abs(_finite(equilibrium['trim_deg'])),
        }
        for key, final_value in final_extrema.items():
            if extremes[key] is not None:
                extremes[key] = max(extremes[key], final_value)
    consistency = _time_consistency(timeline, final_report['time_s'], duration)
    record.update({
        'status': result.get('status'),
        'stop_reason': result.get('stop_reason'),
        'accepted_timeline_steps': max(0, len(timeline) - 1),
        'influx_m3': _finite(influx),
        'final_draft_m': _finite(equilibrium.get('waterline_above_keel_m')),
        'final_tank_volume_m3': _finite(volumes.get(tank_id)),
        'final_time_s': final_report['time_s'],
        'last_timeline_time_s': (consistency['accepted_times'][-1]
                                 if consistency['accepted_times'] else None),
        'volume_conservation_error_m3':
            _finite(result.get('volume_conservation_error_m3')),
        'mass_conservation_error_t':
            _finite(result.get('mass_conservation_error_t')),
        'max_abs_scaled_residual': extremes['max_abs_scaled_residual'],
        'max_abs_heel_deg': extremes['max_abs_heel_deg'],
        'max_abs_trim_deg': extremes['max_abs_trim_deg'],
        'broken_states': extremes['broken_states'],
        'not_converged_states': extremes['not_converged_states'],
        'complete_accepted_states': extremes['complete_state_count'],
        'final_state_report': final_report,
        'time_consistency': consistency,
        'solver_method_version': result.get('method_version'),
        'kernel_method_version': result.get('kernel_method_version'),
        'validity': _json_safe(result.get('validity')),
        'failed_attempt': _json_safe(result.get('failed_attempt')),
        'diagnostics': _json_safe(result.get('diagnostics')),
    })
    record['finite_values'] = [
        _finite(value) is not None for value in (
            record['influx_m3'], record['final_draft_m'],
            record['volume_conservation_error_m3'],
            record['mass_conservation_error_t'],
            record['max_abs_scaled_residual'],
            record['max_abs_heel_deg'], record['max_abs_trim_deg'],
            record['final_time_s'])]
    for note in extremes['broken_states']:
        record['notes'].append(f'incomplete accepted state {note}')
    for note in extremes['not_converged_states']:
        record['notes'].append(f'accepted state not converged {note}')
    for problem in final_report['problems']:
        record['notes'].append(f'final state invalid: {problem}')
    if final_report['converged'] is not True and final_report['present']:
        record['notes'].append(
            f'final state not converged: {final_report["converged"]!r}')
    for problem in consistency['problems']:
        record['notes'].append(f'time consistency: {problem}')
    previous_metrics = (previous or {}).get('metrics', {})
    record['metrics'] = _flooding_metrics(record, reference, initial_volume,
                                          previous_metrics)
    _seal_flooding_hashes(record, project, scenario, before)
    return record


REQUIRED_STATE_RESIDUAL_COMPONENTS = ('volume', 'longitudinal', 'transverse')


def _empty_final_state_report(tank_id):
    """A complete, empty final-state record for a level that never produced one."""
    return {
        'present': False, 'converged': None, 'missing': ['final_state'],
        'non_finite': [], 'missing_residual_components': [],
        'non_finite_residual_components': [], 'tank_id': tank_id,
        'missing_tanks': [tank_id], 'non_finite_tanks': [],
        'max_abs_scaled_residual': None, 'time_s': None,
        'problems': ['final_state missing'],
    }


def _inspect_state(state, tank_id, label):
    """Validate one accepted state: convergence, residuals, tanks and values."""
    problems = []
    equilibrium = (state or {}).get('equilibrium') or {}
    scaled = ((equilibrium.get('residuals') or {}).get('scaled') or {})
    missing_residual = [key for key in REQUIRED_STATE_RESIDUAL_COMPONENTS
                        if key not in scaled]
    non_finite_residual = [key for key in REQUIRED_STATE_RESIDUAL_COMPONENTS
                           if key in scaled and _finite(scaled[key]) is None]
    missing, non_finite = [], []
    for key in ('heel_deg', 'trim_deg', 'waterline_above_keel_m'):
        if _finite(equilibrium.get(key)) is None:
            missing.append(key)
    volumes = state.get('volumes_m3') if isinstance(state, dict) else None
    missing_tanks, non_finite_tanks = [], []
    if not isinstance(volumes, dict) or not volumes:
        missing_tanks.append(tank_id)
    else:
        if tank_id not in volumes:
            missing_tanks.append(tank_id)
        for name, value in volumes.items():
            if _finite(value) is None:
                non_finite_tanks.append(name)
    if missing_residual:
        problems.append(f'missing residual components {missing_residual}')
    if non_finite_residual:
        problems.append(f'non-finite residual components {non_finite_residual}')
    if missing:
        problems.append(f'missing values {sorted(missing)}')
    if missing_tanks:
        problems.append(f'missing tank volume {sorted(set(missing_tanks))}')
    if non_finite_tanks:
        problems.append(f'non-finite tank volumes {sorted(set(non_finite_tanks))}')
    residual = None
    if not missing_residual and not non_finite_residual:
        residual = max(abs(_finite(scaled[key]))
                       for key in REQUIRED_STATE_RESIDUAL_COMPONENTS)
    return {
        'label': label,
        'present': isinstance(state, dict) and bool(state),
        'converged': equilibrium.get('converged'),
        'missing': sorted(missing),
        'non_finite': sorted(non_finite),
        'missing_residual_components': missing_residual,
        'non_finite_residual_components': non_finite_residual,
        'tank_id': tank_id,
        'missing_tanks': sorted(set(missing_tanks)),
        'non_finite_tanks': sorted(set(non_finite_tanks)),
        'max_abs_scaled_residual': residual,
        'time_s': _finite((state or {}).get('time_s')),
        'problems': problems,
    }


def _time_consistency(timeline, final_time, duration):
    """Every time relationship the public result object does not guarantee.

    A result can alias `final_state` into the last timeline row, so agreement
    between the two is assumed nowhere: each is read and compared separately
    against the declared duration and against each other.
    """
    problems = []
    times = []
    for index, state in enumerate(timeline):
        value = _finite((state or {}).get('time_s'))
        times.append(value)
        if value is None:
            problems.append(f'timeline[{index}] has no finite time_s')
    initial_zero = bool(times) and times[0] == 0.0
    if not initial_zero:
        problems.append(
            f'initial accepted time is {times[0] if times else None}, expected 0')
    nondecreasing = all(times[index] is not None
                        and times[index - 1] is not None
                        and times[index] >= times[index - 1]
                        for index in range(1, len(times)))
    if not nondecreasing:
        problems.append('accepted times are not nondecreasing')
    last = times[-1] if times else None
    last_matches = bool(last is not None and abs(last - duration) <= 1e-9)
    if not last_matches:
        problems.append(f'last timeline time {last} does not equal the declared '
                        f'duration {duration}')
    final_ok = bool(final_time is not None
                    and abs(final_time - duration) <= 1e-9)
    if not final_ok:
        problems.append(f'final_state time {final_time} does not equal the '
                        f'declared duration {duration}')
    agree = bool(final_time is not None and last is not None
                 and abs(final_time - last) <= 1e-9)
    if not agree:
        problems.append(f'final_state time {final_time} does not match the last '
                        f'timeline time {last}')
    return {'initial_time_is_zero': initial_zero,
            'times_nondecreasing': nondecreasing,
            'last_timeline_matches_duration': last_matches,
            'final_state_matches_duration': final_ok,
            'final_state_matches_timeline': agree,
            'accepted_times': times,
            'problems': problems}


def _seal_flooding_hashes(record, project, scenario, before):
    record['fixture_sha256_after'] = _payload_sha256((project, scenario))
    record['fixture_unchanged'] = record['fixture_sha256_after'] == before
    if not record['fixture_unchanged']:
        record['notes'].append('the supplied fixture changed during the level')
        record['status'] = 'fixture_mutated'


def _timeline_extremes(timeline, tank_id):
    """Worst-case values across every accepted state, with nothing dropped.

    A state missing a required value, not converged, or carrying a non-finite
    residual makes the whole maximum unavailable; dropping that state would
    hide a broken state behind its healthy neighbours.
    """
    residuals, heels, trims = [], [], []
    broken, not_converged = [], []
    for index, state in enumerate(timeline):
        label = f'timeline[{index}]'
        report = _inspect_state(state, tank_id, label)
        if report['converged'] is not True:
            not_converged.append(f'{label}: {report["converged"]!r}')
        if report['problems']:
            broken.append(f'{label}: {"; ".join(report["problems"])}')
            continue
        equilibrium = state['equilibrium']
        residuals.append(report['max_abs_scaled_residual'])
        heels.append(abs(_finite(equilibrium['heel_deg'])))
        trims.append(abs(_finite(equilibrium['trim_deg'])))
    complete = bool(timeline) and not broken and not not_converged
    return {'max_abs_scaled_residual': max(residuals) if complete else None,
            'max_abs_heel_deg': max(heels) if complete else None,
            'max_abs_trim_deg': max(trims) if complete else None,
            'broken_states': broken, 'not_converged_states': not_converged,
            'complete_state_count': len(residuals)}


def _flooding_metrics(record, reference, initial_volume, previous):
    influx = _error_record('net_sea_inflow_m3', record.get('influx_m3'),
                           reference['net_sea_inflow_m3'], unit='m3',
                           previous=(previous or {}).get(
                               'net_sea_inflow_m3', {}).get('absolute_error'),
                           ratio=record.get('refinement_ratio_to_previous'))
    draft = _error_record('final_draft_m', record.get('final_draft_m'),
                          reference['final_draft_m'], unit='m',
                          previous=(previous or {}).get(
                              'final_draft_m', {}).get('absolute_error'),
                          ratio=record.get('refinement_ratio_to_previous'))
    change_reference = reference['draft_change_m']
    computed_draft = _finite(record.get('final_draft_m'))
    if computed_draft is None or _finite(change_reference) in (None, 0.0):
        draft_change_relative, draft_change_status = None, 'unavailable'
    else:
        draft_change_relative = abs(
            (computed_draft - reference['initial_draft_m']) - change_reference) \
            / abs(change_reference)
        draft_change_status = 'ok'
    previous_change = (previous or {}).get('draft_change_relative_error')
    order, order_status = _observed_order(
        previous_change, draft_change_relative,
        record.get('refinement_ratio_to_previous'))
    return {
        'net_sea_inflow_m3': influx,
        'final_draft_m': draft,
        'draft_change_relative_error': draft_change_relative,
        'draft_change_relative_error_status': draft_change_status,
        'draft_change_observed_order': order,
        'draft_change_observed_order_status': order_status,
        'volume_conservation_error_m3': _error_record(
            'volume_conservation_error_m3',
            record.get('volume_conservation_error_m3'), 0.0, unit='m3',
            limit=FLOODING_THRESHOLDS['volume_conservation_absolute_m3'],
            note='declared absolute conservation limit'),
        'mass_conservation_error_t': _error_record(
            'mass_conservation_error_t',
            record.get('mass_conservation_error_t'), 0.0, unit='t',
            limit=FLOODING_THRESHOLDS['mass_conservation_absolute_t'],
            note='declared absolute conservation limit'),
        'initial_tank_volume_m3': _finite(initial_volume),
    }


# --------------------------------------------------------------------- study

def _suite_name(suite):
    if suite not in SUITE_CHOICES:
        raise ValueError(f'unknown suite {suite!r}; choose from '
                         f'{", ".join(SUITE_CHOICES)}')
    return suite


def run_study(suite='all', hooks=None):
    """Run one or all bounded suites and return the complete evidence report."""
    name = _suite_name(suite)
    hooks = dict(hooks or {})
    before = _source_snapshot()
    started = _utc_now()
    suites, oracle_answers = {}, {}
    if name in ('all', 'geometry'):
        suites['geometry'] = run_geometry_suite(hooks=hooks)
        oracle_answers['geometry'] = suites['geometry']['oracle']
    if name in ('all', 'gz'):
        suites['gz'] = run_gz_suite(hooks=hooks)
        oracle_answers['gz'] = suites['gz']['oracle']
    if name in ('all', 'flooding'):
        suites['flooding'] = run_flooding_suite(hooks=hooks)
        oracle_answers['flooding'] = suites['flooding']['oracle']

    checks = []
    for key in sorted(suites):
        checks.extend(suites[key]['checks'])
    checks.append(_check(
        'study', 'fixtures_not_mutated',
        'every supplied fixture is byte-identical after the run',
        all(suites[key].get('fixture_unchanged', True)
            for key in suites)))
    after = _source_snapshot()
    changed = sorted(path for path in before
                     if before[path]['sha256'] != after[path]['sha256'])
    checks.append(_check(
        'study', 'sources_not_mutated',
        'every hashed kernel, fixture builder, oracle and study source is '
        'byte-identical after the run', not changed,
        detail=f'changed: {changed}' if changed else 'no source changed'))
    acceptance = {
        'passed': all(check['passed'] for check in checks),
        'checks': checks,
        'failed': sorted(check['name'] for check in checks
                         if not check['passed']),
        'counts': {'total': len(checks),
                   'passed': sum(1 for check in checks if check['passed']),
                   'failed': sum(1 for check in checks if not check['passed'])},
        'thresholds_are_declared_before_the_run': True,
        'thresholds_are_not_tuned_to_results': True,
    }
    # Validate raw claims before replacing non-finite metadata with null.
    # Failure statuses and reasons remain available in a strict JSON report.
    return _json_safe({
        'schema': SCHEMA,
        'study': {
            'id': STUDY_ID,
            'suite': name,
            'suites_run': sorted(suites),
            'description': 'Offline numerical convergence of hull '
                           'discretization, GZ sampling and flooding time '
                           'integration against independent analytic answers.',
            'generated_utc': started,
            'completed_utc': _utc_now(),
            'runtime': {
                'implementation': platform.python_implementation(),
                'version': platform.python_version(),
                'api_version': sys.api_version,
                'platform': sys.platform,
            },
            'working_directory': str(Path.cwd()),
            'working_directory_affects_results': False,
            'repository_root': str(REPO),
            'network_access': 'none',
            'writes_production_state': False,
            'dependencies_added': [],
        },
        'units': fixtures.fixture_provenance()['units'],
        'meanings': fixtures.fixture_provenance()['meanings'],
        'fixtures': fixtures.fixture_provenance(),
        'method_versions': _method_versions(),
        'oracle_answers': oracle_answers,
        'sources': before,
        'source_integrity': {'checked_utc': _utc_now(), 'unchanged': not changed,
                             'changed': changed},
        'suites': suites,
        'acceptance': acceptance,
        'status': 'pass' if acceptance['passed'] else 'fail',
        'limitations': list(LIMITATIONS),
    })


def _method_versions():
    return {
        'stability.METHOD_VERSION': stability.METHOD_VERSION,
        'stability.RESIDUAL_TOLERANCE': stability.RESIDUAL_TOLERANCE,
        'flooding.METHOD_VERSION': flooding.METHOD_VERSION,
        'flooding.kernel.METHOD_VERSION':
            getattr(flooding.kernel, 'METHOD_VERSION', None),
        'flooding.HYDRAULIC_HEAD_TOLERANCE_M':
            flooding.HYDRAULIC_HEAD_TOLERANCE_M,
        'fixture_version': fixtures.FIXTURE_VERSION,
        'study_schema': SCHEMA,
    }


# ------------------------------------------------------------------- writers

CSV_COLUMNS = ('suite', 'sequence', 'level', 'refinement', 'evaluation',
               'metric', 'unit', 'reference', 'computed', 'absolute_error',
               'relative_error', 'relative_error_status', 'observed_order',
               'observed_order_status', 'status', 'failure_reason', 'limit',
               'comparison', 'limit_value', 'passed', 'note')


def _csv_rows(report):
    """Flatten every retained sample; failures are rows like any other."""
    rows = []
    for relative, entry in sorted(report['sources'].items()):
        rows.append({'suite': 'provenance', 'sequence': 'source',
                     'level': '', 'refinement': '', 'evaluation': 'source_sha256',
                     'metric': relative, 'unit': 'sha256',
                     'reference': '', 'computed': entry['sha256'],
                     'note': entry['role']})
    for suite_name, suite in sorted(report['suites'].items()):
        sequences = suite.get('sequences')
        if sequences is not None:
            groups = [(sequence['name'], level)
                      for sequence in sequences for level in sequence['levels']]
        else:
            groups = [('levels', level) for level in suite.get('levels', [])]
        for sequence_name, level in groups:
            refinement = {key: value for key, value in level.items()
                          if key in ('step_deg', 'time_step_s')}
            base = {
                'suite': suite_name, 'sequence': sequence_name,
                'level': level['level'],
                'refinement': json.dumps(
                    level.get('refinement') or refinement, sort_keys=True),
            }
            evaluations = level.get('evaluations')
            if evaluations is not None:
                for name, evaluation in sorted(evaluations.items()):
                    for key, metric in sorted(evaluation['metrics'].items()):
                        rows.append(dict(base, evaluation=name,
                                         **_metric_row(metric)))
                    rows.append(dict(
                        base, evaluation=name, metric='evaluation_status',
                        unit='', computed=evaluation.get('status'),
                        status=evaluation.get('status'),
                        failure_reason='; '.join(
                            evaluation.get('missing_residual_components', [])
                            + evaluation.get('non_finite_residual_components', [])
                            + evaluation.get('missing_metrics', [])) or None,
                        note='; '.join(evaluation.get('notes', []))))
                rows.append(dict(
                    base, evaluation='*',
                    metric='sample_status', unit='',
                    status=level['status'],
                    note=json.dumps(level.get('notes', []), ensure_ascii=False)))
            else:
                rows.extend(_level_rows(base, level))
    for check in report['acceptance']['checks']:
        rows.append({'suite': check['suite'], 'sequence': 'acceptance',
                     'level': '', 'refinement': '', 'evaluation': 'acceptance_check',
                     'metric': check['name'], 'unit': '', 'reference': '',
                     'computed': _plain(check['value']), 'absolute_error': '',
                     'relative_error': '', 'relative_error_status': '',
                     'observed_order': '', 'observed_order_status': '',
                     'status': 'passed' if check['passed'] else 'failed',
                     'limit': check['limit'], 'comparison': check['comparison'],
                     'limit_value': '', 'passed': check['passed'],
                     'note': check.get('detail') or check['requirement']})
    return rows


def _sample_diagnostics(sample):
    """Flatten a failed sample's diagnostics into one readable CSV cell."""
    items = sample.get('diagnostics')
    if not isinstance(items, list) or not items:
        return ''
    parts = []
    for item in items:
        if isinstance(item, dict):
            parts.append(str(item.get('code') or item.get('message') or item))
        else:
            parts.append(str(item))
    return 'diagnostics: ' + '; '.join(parts)


def _level_rows(base, level):
    """CSV rows for one GZ or flooding level, keyed on what the level holds."""
    rows = []
    if 'fixed_angle' in level:
        for sample in level['fixed_angle']['samples']:
            rows.append(dict(
                base, evaluation='fixed_angle',
                metric=f"gz_m_at_{sample['angle_deg']}deg", unit='m',
                reference=sample.get('analytic_gz_m'),
                computed=sample.get('computed_gz_m'),
                absolute_error=sample.get('absolute_error_m'),
                status=sample.get('status'),
                failure_reason=sample.get('failure_reason'),
                note='; '.join(filter(None, [
                    'common angle' if sample.get('is_common_angle') else '',
                    f"converged={sample.get('converged')!r}",
                    f"model_applicable={sample.get('model_applicable')!r}",
                    _sample_diagnostics(sample)]))))
        area = level['curve_area']
        rows.append(dict(
            base, evaluation='curve_area', metric='relative_area_error',
            unit='', reference=1.0,
            computed=area['relative_area_error'],
            absolute_error=area['absolute_area_error'],
            relative_error=area['relative_area_error'],
            observed_order=area['observed_order'],
            observed_order_status=area['observed_order_status'],
            status=level['status'], note=area.get('quadrature', '')))
        rows.append(dict(
            base, evaluation='*', metric='sample_status', unit='',
            status=level['status'],
            note=json.dumps(level.get('notes', []), ensure_ascii=False)))
        return rows
    for key in ('status', 'stop_reason', 'accepted_timeline_steps',
                'max_abs_scaled_residual', 'volume_conservation_error_m3',
                'mass_conservation_error_t', 'max_abs_heel_deg',
                'max_abs_trim_deg', 'influx_m3', 'final_draft_m',
                'final_time_s', 'last_timeline_time_s',
                'scheduled_duration_s', 'final_tank_volume_m3',
                'complete_accepted_states'):
        if key in level:
            rows.append(dict(base, evaluation='run', metric=key,
                             computed=_plain(level[key]), status=level['status']))
    for problem in level.get('broken_states', []):
        rows.append(dict(base, evaluation='broken_state', metric='problem',
                         computed=problem, status=level['status']))
    for problem in level.get('not_converged_states', []):
        rows.append(dict(base, evaluation='not_converged_state',
                         metric='problem', computed=problem,
                         status=level['status']))
    consistency = level.get('time_consistency') or {}
    for key, value in sorted(consistency.items()):
        if key == 'problems':
            for problem in value or []:
                rows.append(dict(base, evaluation='time_consistency',
                                 metric='problem', computed=problem,
                                 status=level['status']))
        else:
            rows.append(dict(base, evaluation='time_consistency', metric=key,
                             computed=_plain(value), status=level['status']))
    final_report = level.get('final_state_report') or {}
    for problem in final_report.get('problems', []):
        rows.append(dict(base, evaluation='final_state', metric='problem',
                         computed=problem, status=level['status']))
    for note in level.get('notes', []):
        rows.append(dict(base, evaluation='*', metric='note', computed=note,
                         status=level['status']))
    for key, metric in sorted(level.get('metrics', {}).items()):
        if isinstance(metric, dict):
            rows.append(dict(base, evaluation='metrics',
                             **_metric_row(metric)))
        else:
            rows.append(dict(base, evaluation='metrics', metric=key,
                             computed=_plain(metric), status=level['status']))
    rows.append(dict(base, evaluation='*', metric='sample_status', unit='',
                     status=level['status'],
                     note=json.dumps(level.get('notes', []), ensure_ascii=False)))
    return rows


def _metric_row(metric):
    return {        'metric': metric['name'], 'unit': metric['unit'],
        'reference': metric['reference'], 'computed': metric['computed'],
        'absolute_error': metric['absolute_error'],
        'relative_error': metric['relative_error'],
        'relative_error_status': metric['relative_error_status'],
        'observed_order': metric['observed_order'],
        'observed_order_status': metric['observed_order_status'],
        'status': metric['status'], 'limit': metric['limit'],
        'comparison': metric['comparison'],
        'limit_value': metric['limit_value'], 'passed': metric['passed'],
        'note': metric['note'] or '',
    }


def _cell(value):
    if value is None:
        return 'unavailable'
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, float):
        return f'{value:.6e}'
    return str(value)


def _table(headers, rows):
    lines = ['| ' + ' | '.join(headers) + ' |',
             '| ' + ' | '.join('---' for _ in headers) + ' |']
    for row in rows:
        lines.append('| ' + ' | '.join(_cell(value) for value in row) + ' |')
    return '\n'.join(lines)


def render_markdown(report):
    """Render the whole report, including every failed sample."""
    study = report['study']
    parts = [
        '# Numerical convergence study',
        '',
        f"- study id: `{study['id']}`",
        f"- suite: `{study['suite']}`",
        f"- generated (UTC): {study['generated_utc']}",
        f"- runtime: {study['runtime']['implementation']} "
        f"{study['runtime']['version']} on {study['runtime']['platform']}",
        f"- overall status: **{report['status']}**",
        f"- acceptance: {report['acceptance']['counts']['passed']} of "
        f"{report['acceptance']['counts']['total']} declared checks passed",
        '',
        'This is an offline numerical convergence study of the implemented '
        'model against independent analytic answers. It does not establish '
        'physical accuracy, statutory stability compliance, historical ship '
        'accuracy or SPS superiority.',
        '',
        '## Source identity',
        '',
        _table(['source', 'role', 'sha256'],
               [[name, entry['role'], entry['sha256'][:16]]
                for name, entry in sorted(report['sources'].items())]),
        '',
        f"Sources unchanged after the run: "
        f"**{report['source_integrity']['unchanged']}**.",
        '',
        '## Declared method versions',
        '',
        _table(['item', 'version'],
               sorted(report['method_versions'].items())),
    ]
    for name in sorted(report['suites']):
        suite = report['suites'][name]
        parts.extend(['', f'## Suite: {name}', '',
                      suite['title'], '',
                      f"- passed: **{suite['passed']}**",
                      f"- oracle: `{suite['oracle_source']}`", '',
                      '### Declared thresholds (fixed before this run)', '',
                      _table(['criterion', 'declared value'],
                             sorted(suite['declared_thresholds'].items()))])
        if suite.get('sequences') is not None:
            for sequence in suite['sequences']:
                parts.extend(['', f"### Sequence: {sequence['name']}",
                              '',
                              f"refined: `{sequence['refined_parameter']}`; "
                              f"fixed: `{json.dumps(sequence['fixed_parameter'], sort_keys=True)}`",
                              '', '#### Retained samples', ''])
                rows = []
                for level in sequence['levels']:
                    for evaluation_name, evaluation in level['evaluations'].items():
                        for metric_name, metric in evaluation['metrics'].items():
                            rows.append([
                                level['refinement'], evaluation_name,
                                metric_name, metric['reference'],
                                metric['computed'], metric['absolute_error'],
                                metric['relative_error'],
                                metric['observed_order'], metric['status'],
                                'yes' if metric['passed'] else
                                ('no' if metric['passed'] is False else 'n/a')])
                parts.append(_table(
                    ['refinement', 'evaluation', 'metric', 'reference',
                     'computed', 'abs err', 'rel err', 'order', 'status',
                     'within limit'], rows))
        else:
            parts.extend(['', '### Retained samples', ''])
            if name == 'gz':
                rows = [[level['step_deg'], level['sample_count'],
                         level['fixed_angle']['max_abs_error_m'],
                         level['fixed_angle']['max_abs_error_common_angles_m'],
                         level['curve_area']['relative_area_error'],
                         level['curve_area']['observed_order'],
                         level['sampled_maximum'],
                         level['endpoint']['kind'], level['status']]
                        for level in suite['levels']]
                parts.append(_table(
                    ['step deg', 'samples', 'max fixed-angle err m',
                     'common-angle err m', 'area rel err', 'area order',
                     'sampled max', 'endpoint', 'status'], rows))
                parts.extend(['', '#### Metric definitions', ''])
                parts.extend(f"- **{key}**: {value}"
                             for key, value in
                             sorted(suite['metric_definitions'].items()))
                parts.extend(['', '#### Sampled maximum and endpoint', '',
                              _table(['step deg', 'sampled maximum', 'endpoint',
                                      'AVS deg'],
                                     [[level['step_deg'],
                                       level['sampled_maximum'],
                                       level['endpoint'],
                                       level['avs_deg']]
                                      for level in suite['levels']]),
                              '', '#### Every sampled angle', ''])
                parts.append(_table(
                    ['step deg', 'angle deg', 'solver GZ m', 'analytic GZ m',
                     'abs err m', 'converged', 'model_applicable', 'status',
                     'failure reason', 'diagnostics'],
                    [[level['step_deg'], sample['angle_deg'],
                      sample.get('computed_gz_m'),
                      sample.get('analytic_gz_m'),
                      sample.get('absolute_error_m'),
                      sample.get('converged'), sample.get('model_applicable'),
                      sample.get('status'), sample.get('failure_reason'),
                      _sample_diagnostics(sample)]
                     for level in suite['levels']
                     for sample in level['fixed_angle']['samples']]))
            else:
                rows = [[level['time_step_s'], level['status'],
                         level['stop_reason'], level['accepted_timeline_steps'],
                         level['final_time_s'],
                         level['metrics']['net_sea_inflow_m3']['absolute_error'],
                         level['metrics']['net_sea_inflow_m3']['relative_error'],
                         level['metrics']['net_sea_inflow_m3']['observed_order'],
                         level['metrics']['draft_change_relative_error'],
                         level['max_abs_scaled_residual'],
                         level['volume_conservation_error_m3'],
                         level['mass_conservation_error_t'],
                         '; '.join(level.get('broken_states', []))
                         or '; '.join(level.get('not_converged_states', []))]
                        for level in suite['levels']]
                parts.append(_table(
                    ['dt s', 'status', 'stop reason', 'steps', 'final time s',
                     'influx abs err', 'influx rel err', 'influx order',
                     'draft-change rel err', 'max scaled residual',
                     'volume cons m3 (signed)', 'mass cons t (signed)',
                     'broken states'], rows))
        parts.extend(['', '### Acceptance checks for this suite', ''])
        parts.append(_table(['criterion', 'requirement', 'value', 'limit',
                             'comparison', 'passed', 'detail'],
                            [[check['name'].split('.', 1)[-1],
                              check['requirement'], _plain(check['value']),
                              check['limit'], check['comparison'],
                              check['passed'], check['detail'] or '']
                             for check in suite['checks']]))
        notes = list(suite.get('notes', [])) + list(suite.get('no_claim', []))
        # An exception detail belongs in the report, not only in the log.
        notes.extend(f'{name} level {level.get("level")}: {note}'
                     for level in suite.get('levels', []) or []
                     for note in level.get('notes', []))
        for sequence in suite.get('sequences', []) or []:
            for level in sequence['levels']:
                notes.extend(f"{sequence['name']} level {level['level']}: {note}"
                             for note in level.get('notes', []))
                for name, evaluation in level['evaluations'].items():
                    notes.extend(f"{sequence['name']} level {level['level']} "
                                 f'{name}: {note}'
                                 for note in evaluation.get('notes', []))
        if notes:
            parts.extend(['', '### Suite notes and failure detail', ''])
            parts.extend(f'- {note}' for note in notes)
    parts.extend(['', '## Acceptance summary', '',
                  _table(['criterion', 'passed', 'detail'],
                         [[check['name'], check['passed'],
                           check['detail'] or check['requirement']]
                          for check in report['acceptance']['checks']]),
                  '', '## Limitations', ''])
    parts.extend(f'- {item}' for item in report['limitations'])
    parts.append('')
    return '\n'.join(parts)


def write_json(report, path):
    path = Path(path)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                               allow_nan=False), encoding='utf-8')
    return path


def write_csv(report, path):
    path = Path(path)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS),
                                extrasaction='ignore')
        writer.writeheader()
        for row in _csv_rows(report):
            writer.writerow({key: ('' if row.get(key) is None
                                   else _csv_value(row.get(key)))
                             for key in CSV_COLUMNS})
    return path


def _csv_value(value):
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return value


def write_markdown(report, path):
    path = Path(path)
    path.write_text(render_markdown(report), encoding='utf-8')
    return path


def write_evidence(report, output_dir):
    """Write JSON, CSV and Markdown; a failing study still writes everything."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return {
        'json': write_json(report, directory / JSON_NAME),
        'csv': write_csv(report, directory / CSV_NAME),
        'markdown': write_markdown(report, directory / MARKDOWN_NAME),
    }


def exit_code_for(report):
    """0 when every declared check passed, 1 otherwise; never a partial pass."""
    return EXIT_OK if report['acceptance']['passed'] else EXIT_ACCEPTANCE_FAILED


def build_parser():
    parser = argparse.ArgumentParser(
        prog='convergence_study.py',
        description='Offline numerical convergence study against independent '
                    'analytic answers. Writes JSON, CSV and Markdown evidence '
                    'and exits 1 when any declared check fails.',
        epilog='The study never touches the network or production state, and '
               'its result does not depend on the current working directory.')
    parser.add_argument('--suite', choices=SUITE_CHOICES, default='all',
                        help='which bounded suite to run (default: all)')
    parser.add_argument('--output-dir', required=True, metavar='PATH',
                        help='absolute or relative directory that receives the '
                             'three evidence files')
    return parser


def main(argv=None):
    """Run the study and write evidence; 0 pass, 1 acceptance failed, 2 error."""
    arguments = build_parser().parse_args(argv)
    try:
        report = run_study(suite=arguments.suite)
        written = write_evidence(report, arguments.output_dir)
    except OSError as error:
        sys.stderr.write(f'convergence-study: cannot write evidence: {error}\n')
        return EXIT_USAGE
    except ValueError as error:
        sys.stderr.write(f'convergence-study: {error}\n')
        return EXIT_USAGE
    counts = report['acceptance']['counts']
    sys.stdout.write(
        f"convergence-study: suite={report['study']['suite']} "
        f"status={report['status']} checks={counts['passed']}/{counts['total']} "
        f"failed={','.join(report['acceptance']['failed']) or 'none'}\n")
    for name in ('json', 'csv', 'markdown'):
        sys.stdout.write(f'convergence-study: wrote {written[name]}\n')
    if not report['acceptance']['passed']:
        sys.stderr.write('convergence-study: at least one declared check '
                         'failed; retained evidence is complete\n')
    return exit_code_for(report)


if __name__ == '__main__':
    raise SystemExit(main())
