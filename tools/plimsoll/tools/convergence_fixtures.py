# -*- coding: utf-8 -*-
"""Deterministic fixtures for the offline numerical convergence study.

Every builder returns a freshly constructed dictionary that the caller owns:
mutating one result can never change a later call, and no builder reuses a
shared module-level object. Values are declared in
docs/superpowers/plans/2026-10-10-numerical-convergence-study.md and follow
docs/plimsoll-1.0/equilibrium-validation-design.md,
docs/plimsoll-1.0/flooding-validation-design.md and the independent oracles in
docs/plimsoll-1.0/evidence.

This module deliberately imports no repository test module: the study
reproduces its own inputs instead of borrowing another test's fixtures. The
imports below are production Plimsoll entry points used to build canonical
project payloads, not test helpers.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PKG = HERE.parent
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

import project_io  # noqa: E402  (canonical project construction only)


STUDY_ID = 'numerical-convergence-2026-10-10'
FIXTURE_VERSION = 'convergence-fixtures-1'

ELLIPSOID = {
    'semi_axes_m': (20.0, 5.0, 5.0),
    'centre_z_m': 5.0,
    'p': 0.01,
    'q': 0.1,
    'd_m': 4.0,
    'rho_t_m3': 1.025,
    'kg_m': 3.0,
    'prescribed_gz_m': 0.15,
    'prescribed_heel_deg': None,   # filled in by ellipsoid_prescribed_heel_deg
}

BOX = {
    'length_m': 40.0,
    'beam_m': 10.0,
    'depth_m': 10.0,
    'draft_m': 4.0,
    'kg_m': 3.0,
    'rho_t_m3': 1.025,
    'mass_t': 1640.0,
    'stations': 21,
}

FLOODING = {
    'ship_dimensions_m': (20.0, 10.0, 6.0),
    'base_mass_t': 401.8,
    'base_kg_m': 1.0,
    'tank_dimensions_m': (4.0, 2.0, 4.0),
    'initial_volume_m3': 8.0,
    'rho_t_m3': 1.025,
    'discharge_coefficient': 0.6,
    'orifice_area_m2': 0.1,
    'aperture_xyz_m': (0.0, 0.0, 0.1),
    'duration_s': 5.0,
    'initial_draft_m': 2.0,
    'condition_id': 'normal',
    'tank_id': 'centre',
    'sea_id': 'sea',
    'connection_id': 'sea-hole',
}

ORACLE_SOURCES = (
    'coupled_ellipsoid_oracles.py',
    'flooding_oracles.py',
    'wall_sided_box_oracle.py',
)


def ellipsoid_prescribed_heel_deg():
    """Waterplane slope heel angle of the ellipsoid fixture, in degrees."""
    return math.degrees(math.atan(ELLIPSOID['q']))


def _offsets_record(stations, keel_offset_m=0.0):
    """Wrap station polygons in the canonical materialized-geometry record."""
    return {
        'kind': 'offsets',
        'keel_offset_m': float(keel_offset_m),
        'source': {'kind': 'analytic_fixture', 'study_id': STUDY_ID},
        'estimate': False,
        'offsets': {
            'schema': 'plimsoll-section-polygons-1',
            'stations': copy.deepcopy(stations),
        },
    }


def ellipsoid_stations(stations, section_vertices):
    """Analytic ellipse sampling at cosine-spaced longitudinal stations.

    x = -a*cos(pi*i/(n-1)) clusters stations at both ends; each section is a
    closed polygon of `section_vertices` points on the ellipse of half-width
    b*sqrt(1-(x/a)^2) centred at z = c. The analytic ellipsoid is not a
    polyline, so a fixed vertex count is a discretization floor that no
    longitudinal refinement removes.
    """
    count = int(stations)
    vertices = int(section_vertices)
    if count < 3:
        raise ValueError('at least three stations are required')
    if vertices < 3:
        raise ValueError('at least three section vertices are required')
    a, b, c = (float(value) for value in ELLIPSOID['semi_axes_m'])
    centre_z = float(ELLIPSOID['centre_z_m'])
    table = []
    for index in range(count):
        x = -a * math.cos(math.pi * index / (count - 1.0))
        radius = math.sqrt(max(0.0, 1.0 - (x / a) ** 2))
        section = [[b * radius * math.cos(2.0 * math.pi * j / vertices),
                    centre_z + c * radius * math.sin(2.0 * math.pi * j / vertices)]
                   for j in range(vertices)]
        table.append([x, section])
    return table


def ellipsoid_geometry(stations, section_vertices):
    """Fresh ellipsoid hull record at the requested refinement."""
    return _offsets_record(
        ellipsoid_stations(stations, section_vertices), keel_offset_m=0.0)


def _loading_state(mass_t, cg_m, *, project_id, condition_id='selected'):
    """Fresh resolved base loading state accepted by the public solver."""
    if not isinstance(cg_m, (list, tuple)) or len(cg_m) != 3:
        raise ValueError('cg_m must be three coordinates')
    cg = [_number(value, 'cg_m') for value in cg_m]
    mass = _number(mass_t, 'mass_t')
    if mass <= 0.0:
        raise ValueError('mass_t must be positive')
    return {
        'complete_mass': True,
        'complete_cg': True,
        'input_fingerprint': f'{FIXTURE_VERSION}:{project_id}',
        'project_id': project_id,
        'condition_id': condition_id,
        'diagnostics': [],
        'provenance': {'estimate': True, 'study_id': STUDY_ID},
        'uncertainty': {'status': 'unknown'},
        'values': {
            'total_mass_t': mass,
            'lcg_m': cg[0], 'tcg_m': cg[1], 'kg_m': cg[2],
        },
        'coverage': {'reference_displacement_t': mass * 9.0},
    }


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite real number')
    return float(value)


def ellipsoid_loading(mass_t, cg_m):
    """Fresh ellipsoid loading state for the free or prescribed heel solve."""
    return _loading_state(mass_t, cg_m, project_id='convergence-ellipsoid')


def box_stations(stations=None, length_m=None, beam_m=None, depth_m=None):
    """Uniformly spaced rectangular sections of the sealed empty prism."""
    count = int(BOX['stations'] if stations is None else stations)
    if count < 3:
        raise ValueError('at least three stations are required')
    length = _number(BOX['length_m'] if length_m is None else length_m, 'length_m')
    beam = _number(BOX['beam_m'] if beam_m is None else beam_m, 'beam_m')
    depth = _number(BOX['depth_m'] if depth_m is None else depth_m, 'depth_m')
    if min(length, beam, depth) <= 0.0:
        raise ValueError('box dimensions must be positive')
    section = [[-beam / 2.0, 0.0], [beam / 2.0, 0.0],
               [beam / 2.0, depth], [-beam / 2.0, depth]]
    return [[-length / 2.0 + length * index / (count - 1.0),
             copy.deepcopy(section)] for index in range(count)]


def box_geometry(stations=None, length_m=None, beam_m=None, depth_m=None,
                 keel_offset_m=0.0):
    """Fresh sealed empty prism record at the requested refinement."""
    return _offsets_record(
        box_stations(stations, length_m, beam_m, depth_m), keel_offset_m)


def box_loading(mass_t=None, cg_m=None):
    """Fresh box loading state; the declared default is 1640 t at KG 3 m."""
    mass = BOX['mass_t'] if mass_t is None else mass_t
    cg = (0.0, 0.0, BOX['kg_m']) if cg_m is None else cg_m
    return _loading_state(mass, cg, project_id='convergence-box')


def flooding_project():
    """Fresh canonical project for the coupled-heave flooding fixture."""
    length, beam, depth = (float(value)
                            for value in FLOODING['ship_dimensions_m'])
    project = project_io.new_project('Convergence flooding box',
                                     'convergence-flooding-box')
    project['hull'] = {'lwl_m': length, 'beam_m': beam, 'depth_m': depth}
    section = [[-beam / 2.0, 0.0], [beam / 2.0, 0.0],
               [beam / 2.0, depth], [-beam / 2.0, depth]]
    project['geometry'] = {
        'kind': 'offsets',
        'keel_offset_m': 0.0,
        'source': {'kind': 'analytic_rectangular_prism', 'study_id': STUDY_ID},
        'estimate': False,
        'offsets': {
            'schema': 'plimsoll-section-polygons-1',
            'stations': [[-length / 2.0 + index * 1.0,
                          copy.deepcopy(section)] for index in range(21)],
        },
    }
    project['weight_groups'] = [{
        'id': 'lightship',
        'label': 'Base mass',
        'required': True,
        'items': [{
            'id': 'base-mass',
            'mass_t': float(FLOODING['base_mass_t']),
            'x_m': 0.0, 'y_m': 0.0,
            'kg_m': float(FLOODING['base_kg_m']),
            'source': {'kind': 'analytic_fixture', 'study_id': STUDY_ID},
            'estimate': False,
        }],
    }]
    project['loading_conditions'] = [{
        'id': FLOODING['condition_id'],
        'label': 'Normal',
        'reference_displacement_t': float(FLOODING['base_mass_t']),
        'overrides': {},
    }]
    project['openings'] = []
    return project


def flooding_scenario(time_step_s):
    """Fresh vented sea-orifice scenario at the requested time step."""
    step = _number(time_step_s, 'time_step_s')
    if step <= 0.0:
        raise ValueError('time_step_s must be positive')
    tank_length, tank_beam, tank_height = (
        float(value) for value in FLOODING['tank_dimensions_m'])
    density = float(FLOODING['rho_t_m3'])
    provenance = {'kind': 'analytic_fixture', 'study_id': STUDY_ID}
    return {
        'schema': 'plimsoll-flooding-scenario-1',
        'id': 'coupled-heave-convergence',
        'duration_s': float(FLOODING['duration_s']),
        'time_step_s': step,
        'source': {'kind': 'independent_analytic_fixture', 'study_id': STUDY_ID},
        'estimate': False,
        'sea': {
            'id': FLOODING['sea_id'],
            'fluid_density_t_m3': density,
            'source': dict(provenance),
            'estimate': False,
        },
        'tanks': [{
            'id': FLOODING['tank_id'],
            'length_m': tank_length, 'beam_m': tank_beam,
            'height_m': tank_height,
            'x_m': 0.0, 'y_m': 0.0, 'keel_to_bottom_m': 0.0,
            'permeability': 1.0, 'free_surface': True,
            'fluid_density_t_m3': density,
            'initial_volume_m3': float(FLOODING['initial_volume_m3']),
            'source': dict(provenance),
            'estimate': False,
        }],
        'connections': [{
            'id': FLOODING['connection_id'],
            'from': FLOODING['sea_id'],
            'to': FLOODING['tank_id'],
            'x_m': float(FLOODING['aperture_xyz_m'][0]),
            'y_m': float(FLOODING['aperture_xyz_m'][1]),
            'z_m': float(FLOODING['aperture_xyz_m'][2]),
            'area_m2': float(FLOODING['orifice_area_m2']),
            'discharge_coefficient': float(FLOODING['discharge_coefficient']),
            'fluid_density_t_m3': density,
            'open': True,
            'source': dict(provenance),
            'estimate': False,
        }],
    }


def fixture_provenance():
    """Declared parameters, units and oracle provenance for the study header."""
    return {
        'fixture_version': FIXTURE_VERSION,
        'study_id': STUDY_ID,
        'imports_test_modules': False,
        'coordinate_convention': 'x forward from midships, y starboard, z from keel',
        'angle_convention': 'waterplane slope angles, not Euler rotations',
        'ellipsoid': {
            'semi_axes_m': [float(value) for value in ELLIPSOID['semi_axes_m']],
            'centre_m': [0.0, 0.0, float(ELLIPSOID['centre_z_m'])],
            'p': float(ELLIPSOID['p']), 'q': float(ELLIPSOID['q']),
            'd_m': float(ELLIPSOID['d_m']),
            'rho_t_m3': float(ELLIPSOID['rho_t_m3']),
            'kg_m': float(ELLIPSOID['kg_m']),
            'prescribed_gz_m': float(ELLIPSOID['prescribed_gz_m']),
            'prescribed_heel_deg': ellipsoid_prescribed_heel_deg(),
            'section_sampling': 'analytic ellipse, closed polygon, cosine stations',
        },
        'box': {
            'length_m': float(BOX['length_m']), 'beam_m': float(BOX['beam_m']),
            'depth_m': float(BOX['depth_m']), 'draft_m': float(BOX['draft_m']),
            'kg_m': float(BOX['kg_m']), 'rho_t_m3': float(BOX['rho_t_m3']),
            'mass_t': float(BOX['mass_t']), 'stations': int(BOX['stations']),
            'openings': [], 'liquid_loads': [],
            'section_sampling': 'exact rectangle, uniform stations',
        },
        'flooding': {
            'ship_dimensions_m': [float(v) for v in FLOODING['ship_dimensions_m']],
            'base_mass_t': float(FLOODING['base_mass_t']),
            'base_kg_m': float(FLOODING['base_kg_m']),
            'tank_dimensions_m': [float(v) for v in FLOODING['tank_dimensions_m']],
            'initial_volume_m3': float(FLOODING['initial_volume_m3']),
            'rho_t_m3': float(FLOODING['rho_t_m3']),
            'discharge_coefficient': float(FLOODING['discharge_coefficient']),
            'orifice_area_m2': float(FLOODING['orifice_area_m2']),
            'aperture_xyz_m': [float(v) for v in FLOODING['aperture_xyz_m']],
            'duration_s': float(FLOODING['duration_s']),
            'initial_draft_m': float(FLOODING['initial_draft_m']),
            'hull_stations': 21,
        },
        'oracle_sources': list(ORACLE_SOURCES),
        'units': {
            'length': 'm', 'volume': 'm3', 'mass': 't', 'angle': 'deg',
            'time': 's', 'lever': 'm', 'area': 'm*rad', 'density': 't/m3',
        },
        'meanings': [
            'A convergence study measures agreement between the implemented '
            'model and independent analytic answers.',
            'It does not establish physical accuracy, statutory stability '
            'compliance, historical ship accuracy or any SPS superiority.',
        ],
    }
