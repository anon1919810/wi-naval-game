"""Connected quasi-static flooding with repeated three-axis equilibrium."""
from __future__ import annotations

import copy
import hashlib
import json
import math

try:
    from . import _flooding_kernel as kernel
    from . import loading, project_io, stability, tank_geometry
except ImportError:  # Preserve direct-module imports used by repository tests.
    import _flooding_kernel as kernel
    import loading
    import project_io
    import stability
    import tank_geometry


SCHEMA = 'plimsoll-flooding-result-1'
SCENARIO_SCHEMA = 'plimsoll-flooding-scenario-1'
METHOD_VERSION = 'connected-quasi-static-flooding-1'
DEFAULT_MAX_STEPS = 100000
DEFAULT_MAX_STEP_HALVINGS = 40


class FloodingInputError(ValueError):
    """Carry a structured blocking diagnostic for invalid scenario input."""

    def __init__(self, code, path, message):
        self.diagnostic = _diagnostic(code, 'error', path, message, True)
        super().__init__(message)


def _diagnostic(code, severity, path, message, blocking=False):
    return {'code': code, 'severity': severity, 'path': path,
            'message': message, 'blocking': blocking}


def _number(value, path, *, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise FloodingInputError('flooding.number_invalid', path,
                                 'value must be a finite real number')
    result = float(value)
    if minimum is not None and result < minimum:
        raise FloodingInputError('flooding.number_below_minimum', path,
                                 f'value must be at least {minimum}')
    if maximum is not None and result > maximum:
        raise FloodingInputError('flooding.number_above_maximum', path,
                                 f'value must be at most {maximum}')
    return result


def _positive(value, path):
    return _number(value, path, minimum=math.nextafter(0.0, math.inf))


def _string(value, path):
    if not isinstance(value, str) or not value.strip():
        raise FloodingInputError('flooding.string_invalid', path,
                                 'value must be a non-empty string')
    return value


def _metadata(value, field, path):
    if field not in value:
        raise FloodingInputError('flooding.metadata_missing', f'{path}.{field}',
                                 f'{field} metadata must be explicit')
    return copy.deepcopy(value[field])


def _source(value, path):
    source = _metadata(value, 'source', path)
    if not ((isinstance(source, str) and source.strip())
            or (isinstance(source, dict) and source)):
        raise FloodingInputError(
            'flooding.source_invalid', f'{path}.source',
            'source must be a non-empty string or object')
    return source


def _estimate(value, path):
    estimate = _metadata(value, 'estimate', path)
    if not isinstance(estimate, bool):
        raise FloodingInputError('flooding.estimate_invalid', f'{path}.estimate',
                                 'estimate metadata must be boolean')
    return estimate


def _validate_options(options):
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise FloodingInputError('flooding.options_invalid', '$.options',
                                 'options must be an object')
    allowed = {
        'equilibrium', 'gravity_m_s2', 'max_steps', 'max_step_halvings',
        'cancel_check', 'remaining_gz_angles_deg', 'remaining_gz_snapshot',
    }
    unknown = sorted(set(options)-allowed)
    if unknown:
        raise FloodingInputError('flooding.option_unknown', '$.options',
                                 f'unsupported option fields: {unknown!r}')
    result = copy.deepcopy(options)
    equilibrium = result.get('equilibrium', {})
    if not isinstance(equilibrium, dict):
        raise FloodingInputError('flooding.equilibrium_options_invalid',
                                 '$.options.equilibrium',
                                 'equilibrium options must be an object')
    if 'liquid_loads' in equilibrium:
        raise FloodingInputError('flooding.liquid_loads_owned',
                                 '$.options.equilibrium.liquid_loads',
                                 'flooding owns equilibrium liquid_loads')
    result['equilibrium'] = copy.deepcopy(equilibrium)
    result['gravity_m_s2'] = _positive(
        result.get('gravity_m_s2', kernel.DEFAULT_GRAVITY_M_S2),
        '$.options.gravity_m_s2')
    max_steps = result.get('max_steps', DEFAULT_MAX_STEPS)
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps <= 0:
        raise FloodingInputError('flooding.max_steps_invalid', '$.options.max_steps',
                                 'max_steps must be a positive integer')
    result['max_steps'] = max_steps
    halvings = result.get('max_step_halvings', DEFAULT_MAX_STEP_HALVINGS)
    if isinstance(halvings, bool) or not isinstance(halvings, int) or not 0 <= halvings <= 60:
        raise FloodingInputError(
            'flooding.max_step_halvings_invalid', '$.options.max_step_halvings',
            'max_step_halvings must be an integer in [0,60]')
    result['max_step_halvings'] = halvings
    cancel = result.get('cancel_check')
    if cancel is not None and not callable(cancel):
        raise FloodingInputError('flooding.cancel_check_invalid',
                                 '$.options.cancel_check',
                                 'cancel_check must be callable')
    if 'remaining_gz_angles_deg' in result:
        angles = result['remaining_gz_angles_deg']
        if not isinstance(angles, (list, tuple)):
            raise FloodingInputError('flooding.gz_angles_invalid',
                                     '$.options.remaining_gz_angles_deg',
                                     'remaining GZ angles must be an array')
        prepared_angles = [
            _number(value, f'$.options.remaining_gz_angles_deg[{index}]')
            for index, value in enumerate(angles)
        ]
        if any(right <= left
               for left, right in zip(prepared_angles, prepared_angles[1:])):
            raise FloodingInputError(
                'flooding.gz_angles_unordered',
                '$.options.remaining_gz_angles_deg',
                'remaining GZ angles must be strictly increasing')
        result['remaining_gz_angles_deg'] = prepared_angles
    snapshot = result.get('remaining_gz_snapshot', 'final')
    if snapshot not in ('final', 'each_state'):
        raise FloodingInputError('flooding.gz_snapshot_invalid',
                                 '$.options.remaining_gz_snapshot',
                                 'remaining_gz_snapshot must be final or each_state')
    result['remaining_gz_snapshot'] = snapshot
    return result


def _validate_openings(value, path):
    if value is None:
        return None
    if not isinstance(value, list):
        raise FloodingInputError('flooding.openings_invalid', path,
                                 'openings must be an array or null')
    result, identities = [], set()
    for index, opening in enumerate(value):
        item_path = f'{path}[{index}]'
        if not isinstance(opening, dict):
            raise FloodingInputError('flooding.opening_invalid', item_path,
                                     'opening must be an object')
        identity = _string(opening.get('id'), f'{item_path}.id')
        if identity in identities:
            raise FloodingInputError('flooding.opening_duplicate', f'{item_path}.id',
                                     f'duplicate opening id {identity!r}')
        identities.add(identity)
        is_open = opening.get('open')
        if not isinstance(is_open, bool):
            raise FloodingInputError('flooding.opening_state_invalid',
                                     f'{item_path}.open',
                                     'opening open state must be boolean')
        row = {
            'id': identity, 'open': is_open,
            'x_m': _number(opening.get('x_m'), f'{item_path}.x_m'),
            'y_m': _number(opening.get('y_m'), f'{item_path}.y_m'),
            'z_m': _number(opening.get('z_m'), f'{item_path}.z_m'),
            'source': _source(opening, item_path),
            'estimate': _estimate(opening, item_path),
        }
        if 'kind' in opening:
            row['kind'] = copy.deepcopy(opening['kind'])
        result.append(row)
    return result


def _validate_scenario(raw_scenario, raw_project):
    if not isinstance(raw_scenario, dict):
        raise FloodingInputError('flooding.scenario_invalid', '$.scenario',
                                 'scenario must be an object')
    scenario = copy.deepcopy(raw_scenario)
    if scenario.get('schema') != SCENARIO_SCHEMA:
        raise FloodingInputError('flooding.scenario_schema', '$.scenario.schema',
                                 f'scenario schema must be {SCENARIO_SCHEMA!r}')
    scenario['id'] = _string(scenario.get('id'), '$.scenario.id')
    scenario['duration_s'] = _number(scenario.get('duration_s'),
                                     '$.scenario.duration_s', minimum=0.0)
    scenario['time_step_s'] = _positive(scenario.get('time_step_s'),
                                        '$.scenario.time_step_s')
    scenario['source'] = _source(scenario, '$.scenario')
    scenario['estimate'] = _estimate(scenario, '$.scenario')

    sea = scenario.get('sea')
    if not isinstance(sea, dict):
        raise FloodingInputError('flooding.sea_invalid', '$.scenario.sea',
                                 'sea must be an object')
    sea_id = _string(sea.get('id'), '$.scenario.sea.id')
    sea_density = _positive(sea.get('fluid_density_t_m3'),
                            '$.scenario.sea.fluid_density_t_m3')
    normalized_sea = {
        'id': sea_id, 'fluid_density_t_m3': sea_density,
        'source': _source(sea, '$.scenario.sea'),
        'estimate': _estimate(sea, '$.scenario.sea'),
    }

    tanks = scenario.get('tanks')
    if not isinstance(tanks, list):
        raise FloodingInputError('flooding.tanks_invalid', '$.scenario.tanks',
                                 'tanks must be an array')
    normalized_tanks, volumes, tank_ids = [], {}, set()
    for index, tank in enumerate(tanks):
        path = f'$.scenario.tanks[{index}]'
        if not isinstance(tank, dict):
            raise FloodingInputError('flooding.tank_invalid', path,
                                     'tank must be an object')
        identity = _string(tank.get('id'), f'{path}.id')
        if identity == sea_id or identity in tank_ids:
            raise FloodingInputError('flooding.node_duplicate', f'{path}.id',
                                     'tank IDs must be unique and distinct from sea')
        tank_ids.add(identity)
        density = _positive(tank.get('fluid_density_t_m3'),
                            f'{path}.fluid_density_t_m3')
        if density != sea_density:
            raise FloodingInputError('flooding.fluid_density_mismatch',
                                     f'{path}.fluid_density_t_m3',
                                     'all water nodes must use the same explicit density')
        initial = _number(tank.get('initial_volume_m3'),
                          f'{path}.initial_volume_m3', minimum=0.0)
        _source(tank, path)
        _estimate(tank, path)
        try:
            tank_geometry.liquid_state(tank, initial)
        except (ValueError, TypeError, KeyError) as error:
            raise FloodingInputError('flooding.tank_state_invalid', path, str(error)) from error
        normalized_tanks.append(copy.deepcopy(tank))
        volumes[identity] = initial

    connections = scenario.get('connections')
    if not isinstance(connections, list):
        raise FloodingInputError('flooding.connections_invalid',
                                 '$.scenario.connections',
                                 'connections must be an array')
    normalized_connections, edge_ids = [], set()
    node_ids = tank_ids | {sea_id}
    for index, edge in enumerate(connections):
        path = f'$.scenario.connections[{index}]'
        if not isinstance(edge, dict):
            raise FloodingInputError('flooding.connection_invalid', path,
                                     'connection must be an object')
        identity = _string(edge.get('id'), f'{path}.id')
        if identity in edge_ids:
            raise FloodingInputError('flooding.connection_duplicate', f'{path}.id',
                                     f'duplicate connection id {identity!r}')
        edge_ids.add(identity)
        source, target = edge.get('from'), edge.get('to')
        if source not in node_ids or target not in node_ids:
            raise FloodingInputError('flooding.connection_dangling', path,
                                     'connection has a dangling node reference')
        if source == target:
            raise FloodingInputError('flooding.connection_self', path,
                                     'connection must join distinct nodes')
        density = _positive(edge.get('fluid_density_t_m3'),
                            f'{path}.fluid_density_t_m3')
        if density != sea_density:
            raise FloodingInputError('flooding.fluid_density_mismatch',
                                     f'{path}.fluid_density_t_m3',
                                     'connection density must match both water nodes')
        is_open = edge.get('open')
        if not isinstance(is_open, bool):
            raise FloodingInputError('flooding.connection_state_invalid',
                                     f'{path}.open', 'open must be boolean')
        row = {
            'id': identity, 'from_node_id': source, 'to_node_id': target,
            'centre_m': [_number(edge.get(field), f'{path}.{field}')
                         for field in ('x_m', 'y_m', 'z_m')],
            'area_m2': _number(edge.get('area_m2'), f'{path}.area_m2', minimum=0.0),
            'discharge_coefficient': _number(
                edge.get('discharge_coefficient'),
                f'{path}.discharge_coefficient', minimum=0.0, maximum=1.0),
            'fluid_density_t_m3': density, 'open': is_open,
            'source': _source(edge, path),
            'estimate': _estimate(edge, path),
        }
        if 'aperture_height_m' in edge:
            row['aperture_height_m'] = _positive(
                edge['aperture_height_m'], f'{path}.aperture_height_m')
        for unsupported in ('pressure_pa', 'from_pressure_pa', 'to_pressure_pa',
                            'air_pressure_pa'):
            if unsupported in edge:
                raise FloodingInputError('flooding.pressure_unsupported',
                                         f'{path}.{unsupported}',
                                         'pressure networks are outside this model')
        normalized_connections.append(row)

    if 'openings' in scenario:
        openings = _validate_openings(scenario['openings'], '$.scenario.openings')
        openings_origin = 'scenario'
    elif isinstance(raw_project, dict) and 'openings' in raw_project:
        openings = _validate_openings(raw_project['openings'], '$.project.openings')
        openings_origin = 'project'
    else:
        openings, openings_origin = None, 'unknown'
    return scenario, normalized_sea, normalized_tanks, normalized_connections, volumes, openings, openings_origin


def _input_fingerprint(project, condition_id, scenario, options):
    physical_options = {
        key: copy.deepcopy(value) for key, value in options.items()
        if key != 'cancel_check'
    }
    encoded = json.dumps({
        'project_fingerprint': project_io.input_fingerprint(project),
        'condition_id': condition_id,
        'scenario': scenario,
        'options': physical_options,
    }, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _liquid_loads(tanks, volumes):
    return [{
        'tank': copy.deepcopy(tank),
        'volume_m3': volumes[tank['id']],
        'fluid_density_t_m3': tank['fluid_density_t_m3'],
    } for tank in tanks]


def _solve_equilibrium(geometry, loading_state, tanks, volumes, sea_density,
                       equilibrium_options, previous=None):
    options = copy.deepcopy(equilibrium_options)
    if 'rho_t_m3' in options and options['rho_t_m3'] != sea_density:
        return {
            'converged': False,
            'validity': {'complete': False, 'model_applicable': False,
                         'numerical_convergence': False,
                         'historical_validated': None, 'safe': None},
            'diagnostics': [_diagnostic(
                'flooding.ambient_density_mismatch', 'error',
                '$.options.equilibrium.rho_t_m3',
                'equilibrium ambient density must match scenario sea density', True)],
        }
    options['rho_t_m3'] = sea_density
    options['liquid_loads'] = _liquid_loads(tanks, volumes)
    if previous is not None and previous.get('converged'):
        options['initial'] = {
            'heel_deg': previous['heel_deg'], 'trim_deg': previous['trim_deg']}
    return stability.solve_loaded_equilibrium(geometry, loading_state, options)


def _attitude_and_sea(equilibrium, geometry, sea):
    scale = math.sqrt(1.0+equilibrium['p']**2+equilibrium['q']**2)
    return ({
        'heel_deg': equilibrium['heel_deg'],
        'trim_deg': equilibrium['trim_deg'],
        'geometry_keel_offset_m': geometry['keel_offset_m'],
    }, {
        **copy.deepcopy(sea),
        'surface_offset_m': equilibrium['waterline_d_m']/scale,
    })


def _compact_equilibrium(equilibrium):
    omitted = {'loading', 'liquids'}
    return {key: copy.deepcopy(value) for key, value in equilibrium.items()
            if key not in omitted}


def _public_flow(edge):
    row = copy.deepcopy(edge)
    row['from'] = row.pop('from_node_id')
    row['to'] = row.pop('to_node_id')
    row['mass_flow_t_s'] = (
        None if row['flow_m3_s'] is None
        else row['flow_m3_s']*row['fluid_density_t_m3'])
    return row


def _public_transfer(transfer):
    row = copy.deepcopy(transfer)
    row['from'] = row.pop('from_node_id')
    row['to'] = row.pop('to_node_id')
    return row


def _opening_assessment(openings, equilibrium, keel_offset):
    if openings is None:
        return {'status': 'unknown', 'event': None,
                'minimum_normal_clearance_m': None}
    active = [opening for opening in openings if opening['open']]
    if not active:
        return {'status': 'no_open_points', 'event': None,
                'minimum_normal_clearance_m': None}
    scale = math.sqrt(1+equilibrium['p']**2+equilibrium['q']**2)
    clearances = [
        ((opening['z_m']+keel_offset-equilibrium['p']*opening['x_m']
          -equilibrium['q']*opening['y_m']-equilibrium['waterline_d_m'])/scale,
         opening)
        for opening in active
    ]
    clearance, opening = min(clearances, key=lambda value: value[0])
    event = None
    status = 'clear'
    if clearance <= 0.0:
        status = 'immersed'
        event = {
            'kind': 'immersed_at_accepted_state',
            'opening_id': opening['id'],
            'normal_clearance_m': clearance,
            'source': copy.deepcopy(opening['source']),
            'estimate': copy.deepcopy(opening['estimate']),
        }
    return {'status': status, 'event': event,
            'minimum_normal_clearance_m': clearance}


def _state_row(time_s, actual_dt_s, volumes, equilibrium, evaluation, transfers,
               sea_exchange_m3, sea_exchange_t, cumulative_sea_m3,
               cumulative_sea_t, initial_volume, initial_mass, openings,
               keel_offset):
    total_volume = math.fsum(volumes.values())
    total_mass = math.fsum(
        volumes[tank_id]*state['fluid_density_t_m3']
        for tank_id, state in evaluation['tank_states'].items())
    assessment = _opening_assessment(openings, equilibrium, keel_offset)
    tanks = []
    for liquid in equilibrium['liquids']:
        row = copy.deepcopy(liquid)
        row['fluid_density_t_m3'] = next(
            state['fluid_density_t_m3']
            for tank_id, state in evaluation['tank_states'].items()
            if tank_id == liquid['tank_id'])
        tanks.append(row)
    return {
        'time_s': time_s, 'actual_dt_s': actual_dt_s,
        'volumes_m3': copy.deepcopy(volumes), 'tanks': tanks,
        'equilibrium': _compact_equilibrium(equilibrium),
        'flows': [_public_flow(edge) for edge in evaluation['edges']],
        'edge_transfers': [_public_transfer(transfer) for transfer in transfers],
        'sea_exchange_m3': sea_exchange_m3,
        'sea_exchange_t': sea_exchange_t,
        'cumulative_sea_exchange_m3': cumulative_sea_m3,
        'cumulative_sea_exchange_t': cumulative_sea_t,
        'total_onboard_water_volume_m3': total_volume,
        'total_onboard_water_mass_t': total_mass,
        'volume_conservation_error_m3': total_volume-initial_volume-cumulative_sea_m3,
        'mass_conservation_error_t': total_mass-initial_mass-cumulative_sea_t,
        'downflooding': assessment,
    }


def _invalid_result(diagnostics, *, input_fingerprint=None,
                    project_fingerprint=None, loading_state=None,
                    scenario=None, openings_origin=None,
                    numerical_convergence=None):
    return {
        'schema': SCHEMA, 'method_version': METHOD_VERSION,
        'status': 'invalid_input', 'stop_reason': 'invalid_input',
        'validity': {'complete': False, 'model_applicable': False,
                     'numerical_convergence': numerical_convergence,
                     'historical_validated': None, 'safe': None},
        'input_fingerprint': input_fingerprint,
        'project_fingerprint': project_fingerprint,
        'loading': copy.deepcopy(loading_state),
        'scenario': copy.deepcopy(scenario),
        'openings_origin': openings_origin,
        'timeline': [], 'final_state': None,
        'failed_attempt': None, 'downflooding': None,
        'remaining_gz': None, 'gz_snapshots': [],
        'volume_conservation_error_m3': None,
        'mass_conservation_error_t': None,
        'diagnostics': diagnostics,
    }


def _failure_diagnostics(error):
    if isinstance(error, FloodingInputError):
        return [copy.deepcopy(error.diagnostic)]
    if isinstance(error, project_io.ProjectValidationError):
        return copy.deepcopy(error.diagnostics)
    diagnostics = getattr(error, 'diagnostics', None)
    if isinstance(diagnostics, list):
        return copy.deepcopy(diagnostics)
    return [_diagnostic('flooding.invalid_input', 'error', '$', str(error), True)]


def _remaining_gz(geometry, loading_state, tanks, volumes, sea_density,
                  equilibrium_options, openings, angles):
    options = copy.deepcopy(equilibrium_options)
    options['rho_t_m3'] = sea_density
    options['liquid_loads'] = _liquid_loads(tanks, volumes)
    return stability.stability_curve(
        geometry, loading_state, angles, openings=openings, options=options)


def simulate_flooding(project, condition_id, scenario, options=None):
    """Simulate a connected vented flooding scenario with repeated equilibrium.

    Scenario water is additional mass. The base loading must therefore exclude
    the same physical liquid, and tank IDs must be absent from its item ledger.
    """
    raw_project = copy.deepcopy(project)
    try:
        prepared_options = _validate_options(options)
        normalized_project = project_io.normalize_project(project)
        loading_state = loading.resolve_loading(normalized_project, condition_id)
        (normalized_scenario, sea, tanks, connections, volumes, openings,
         openings_origin) = _validate_scenario(scenario, raw_project)
        base_ids = {item.get('id') for item in loading_state.get('effective_items', [])}
        overlap = sorted(base_ids & {tank['id'] for tank in tanks})
        if overlap:
            raise FloodingInputError('flooding.base_liquid_overlap', '$.scenario.tanks',
                                     f'tank IDs overlap base weight items: {overlap!r}')
        equilibrium_density = prepared_options['equilibrium'].get('rho_t_m3')
        if equilibrium_density is not None and equilibrium_density != sea['fluid_density_t_m3']:
            raise FloodingInputError(
                'flooding.ambient_density_mismatch',
                '$.options.equilibrium.rho_t_m3',
                'equilibrium ambient density must match scenario sea density')
        fingerprint = _input_fingerprint(
            normalized_project, condition_id, normalized_scenario, prepared_options)
    except (FloodingInputError, project_io.ProjectValidationError,
            loading.LoadingConditionError, ValueError, TypeError, KeyError) as error:
        return _invalid_result(_failure_diagnostics(error))

    geometry = normalized_project['geometry']
    duration = normalized_scenario['duration_s']
    requested_dt = normalized_scenario['time_step_s']
    gravity = prepared_options['gravity_m_s2']
    equilibrium_options = prepared_options['equilibrium']
    max_steps = prepared_options['max_steps']
    max_halvings = prepared_options['max_step_halvings']
    cancel_check = prepared_options.get('cancel_check')
    initial_volume = math.fsum(volumes.values())
    initial_mass = math.fsum(
        volumes[tank['id']]*tank['fluid_density_t_m3'] for tank in tanks)
    diagnostics = []
    if openings is None:
        diagnostics.append(_diagnostic(
            'flooding.openings_unknown', 'warning', '$.openings',
            'Downflooding is unknown because no opening definitions were supplied.'))

    equilibrium = _solve_equilibrium(
        geometry, loading_state, tanks, volumes, sea['fluid_density_t_m3'],
        equilibrium_options)
    if not equilibrium.get('converged'):
        diagnostics.extend(copy.deepcopy(equilibrium.get('diagnostics', [])))
        return {
            'schema': SCHEMA, 'method_version': METHOD_VERSION,
            'status': 'equilibrium_failure', 'stop_reason': 'equilibrium_failure',
            'validity': {'complete': False, 'model_applicable': False,
                         'numerical_convergence': False,
                         'historical_validated': None, 'safe': None},
            'input_fingerprint': fingerprint,
            'project_fingerprint': loading_state.get('project_fingerprint'),
            'loading': loading_state, 'scenario': normalized_scenario,
            'openings_origin': openings_origin,
            'timeline': [], 'final_state': None,
            'failed_attempt': {'time_s': 0.0, 'volumes_m3': copy.deepcopy(volumes),
                               'equilibrium': copy.deepcopy(equilibrium)},
            'downflooding': None, 'remaining_gz': None, 'gz_snapshots': [],
            'volume_conservation_error_m3': 0.0,
            'mass_conservation_error_t': 0.0,
            'diagnostics': diagnostics,
        }

    attitude, sea_state = _attitude_and_sea(equilibrium, geometry, sea)
    try:
        evaluation = kernel.evaluate_flows(
            tanks, volumes, connections, attitude=attitude, sea=sea_state,
            gravity_m_s2=gravity)
    except (ValueError, TypeError, KeyError) as error:
        return _invalid_result(
            _failure_diagnostics(error),
            input_fingerprint=fingerprint,
            project_fingerprint=loading_state.get('project_fingerprint'),
            loading_state=loading_state,
            scenario=normalized_scenario,
            openings_origin=openings_origin,
            numerical_convergence=True)
    timeline = [_state_row(
        0.0, 0.0, volumes, equilibrium, evaluation, [], 0.0, 0.0, 0.0, 0.0,
        initial_volume, initial_mass, openings, geometry['keel_offset_m'])]
    status, stop_reason = 'running', None
    failed_attempt = None
    downflooding = timeline[0]['downflooding']['event']
    if downflooding is not None:
        downflooding['time_s'] = 0.0
        status, stop_reason = 'downflooding_event', 'downflooding_event'
    elif evaluation['status'] == 'model_limit':
        status, stop_reason = 'model_limit', 'partial_aperture'
        diagnostics.extend(copy.deepcopy(evaluation['diagnostics']))
    elif duration == 0.0:
        status, stop_reason = 'completed', 'scheduled_completion'

    time_s = cumulative_sea = cumulative_sea_mass = 0.0
    steps = 0
    while status == 'running':
        if cancel_check is not None:
            try:
                canceled = cancel_check(copy.deepcopy(timeline[-1]))
            except Exception as error:  # User callback is an external boundary.
                diagnostics.append(_diagnostic(
                    'flooding.cancel_check_failed', 'error', '$.options.cancel_check',
                    str(error), True))
                status, stop_reason = 'invalid_input', 'cancel_check_failed'
                break
            if canceled:
                status, stop_reason = 'canceled', 'canceled'
                break
        if steps >= max_steps:
            diagnostics.append(_diagnostic(
                'flooding.step_limit', 'error', '$.options.max_steps',
                'The integration exhausted its explicit accepted-step limit.', True))
            status, stop_reason = 'model_limit', 'step_limit'
            break
        proposal = kernel.propose_transfers(
            evaluation, volumes, min(requested_dt, duration-time_s))
        if proposal['status'] != 'candidate':
            status = 'completed' if proposal['status'] == 'equilibrium' else 'model_limit'
            stop_reason = proposal['stop_reason']
            break

        requested_attempt = min(requested_dt, duration-time_s)
        accepted = None
        last_failure = None
        for halving in range(max_halvings+1):
            attempt_dt = requested_attempt/(2**halving)
            proposal = kernel.propose_transfers(evaluation, volumes, attempt_dt)
            if proposal['status'] != 'candidate':
                last_failure = {'kind': proposal['stop_reason']}
                break
            candidate_volumes = proposal['volumes_m3']
            candidate_equilibrium = _solve_equilibrium(
                geometry, loading_state, tanks, candidate_volumes,
                sea['fluid_density_t_m3'], equilibrium_options, equilibrium)
            if not candidate_equilibrium.get('converged'):
                last_failure = {'kind': 'equilibrium_failure',
                                'equilibrium': candidate_equilibrium,
                                'volumes_m3': copy.deepcopy(candidate_volumes),
                                'requested_dt_s': attempt_dt}
                continue
            candidate_attitude, candidate_sea = _attitude_and_sea(
                candidate_equilibrium, geometry, sea)
            try:
                candidate_evaluation = kernel.evaluate_flows(
                    tanks, candidate_volumes, connections,
                    attitude=candidate_attitude, sea=candidate_sea,
                    gravity_m_s2=gravity)
            except (ValueError, TypeError, KeyError) as error:
                last_failure = {'kind': 'model_limit', 'error': str(error),
                                'volumes_m3': copy.deepcopy(candidate_volumes),
                                'requested_dt_s': attempt_dt}
                continue
            if candidate_evaluation['status'] == 'model_limit':
                last_failure = {'kind': 'partial_aperture',
                                'volumes_m3': copy.deepcopy(candidate_volumes),
                                'requested_dt_s': attempt_dt,
                                'diagnostics': candidate_evaluation['diagnostics']}
                continue
            if kernel.has_flow_reversal(evaluation, candidate_evaluation):
                last_failure = {'kind': 'head_reversal',
                                'volumes_m3': copy.deepcopy(candidate_volumes),
                                'requested_dt_s': attempt_dt}
                continue
            accepted = (proposal, candidate_equilibrium, candidate_evaluation)
            break
        if accepted is None:
            failed_attempt = {'time_s': time_s, **(last_failure or {'kind': 'minimum_timestep'})}
            if last_failure and last_failure.get('kind') == 'equilibrium_failure':
                status, stop_reason = 'equilibrium_failure', 'equilibrium_failure'
                diagnostics.extend(copy.deepcopy(
                    last_failure['equilibrium'].get('diagnostics', [])))
            else:
                status, stop_reason = 'model_limit', (
                    last_failure.get('kind') if last_failure else 'minimum_timestep')
                if last_failure and isinstance(last_failure.get('diagnostics'), list):
                    diagnostics.extend(copy.deepcopy(last_failure['diagnostics']))
            break

        proposal, equilibrium, evaluation = accepted
        volumes = proposal['volumes_m3']
        time_s = math.fsum((time_s, proposal['actual_dt_s']))
        cumulative_sea = math.fsum((cumulative_sea, proposal['sea_exchange_m3']))
        cumulative_sea_mass = math.fsum(
            (cumulative_sea_mass, proposal['sea_exchange_t']))
        row = _state_row(
            time_s, proposal['actual_dt_s'], volumes, equilibrium, evaluation,
            proposal['edge_transfers'], proposal['sea_exchange_m3'],
            proposal['sea_exchange_t'], cumulative_sea, cumulative_sea_mass,
            initial_volume, initial_mass, openings, geometry['keel_offset_m'])
        timeline.append(row)
        steps += 1
        if row['downflooding']['event'] is not None:
            downflooding = copy.deepcopy(row['downflooding']['event'])
            downflooding['time_s'] = time_s
            status, stop_reason = 'downflooding_event', 'downflooding_event'
        elif proposal['boundary_reason'] is not None:
            status, stop_reason = 'model_limit', proposal['boundary_reason']
        elif time_s >= duration or math.isclose(time_s, duration, rel_tol=0.0, abs_tol=1e-14):
            time_s = duration
            timeline[-1]['time_s'] = duration
            status, stop_reason = 'completed', 'scheduled_completion'

    final_state = timeline[-1] if timeline else None
    gz_snapshots = []
    remaining_gz = None
    angles = prepared_options.get('remaining_gz_angles_deg')
    if angles is not None and final_state is not None:
        selected = timeline if prepared_options['remaining_gz_snapshot'] == 'each_state' else [final_state]
        for state in selected:
            curve = _remaining_gz(
                geometry, loading_state, tanks, state['volumes_m3'],
                sea['fluid_density_t_m3'], equilibrium_options, openings, angles)
            gz_snapshots.append({'time_s': state['time_s'], 'curve': curve})
        remaining_gz = gz_snapshots[-1]['curve']

    complete = status == 'completed'
    model_applicable = status not in ('invalid_input', 'model_limit', 'equilibrium_failure')
    numerical_convergence = status != 'equilibrium_failure'
    return {
        'schema': SCHEMA, 'method_version': METHOD_VERSION,
        'kernel_method_version': kernel.METHOD_VERSION,
        'status': status, 'stop_reason': stop_reason,
        'validity': {'complete': complete, 'model_applicable': model_applicable,
                     'numerical_convergence': numerical_convergence,
                     'historical_validated': None, 'safe': None},
        'input_fingerprint': fingerprint,
        'project_fingerprint': loading_state.get('project_fingerprint'),
        'loading': loading_state,
        'scenario': copy.deepcopy(normalized_scenario),
        'openings_origin': openings_origin,
        'timeline': timeline, 'final_state': final_state,
        'failed_attempt': failed_attempt,
        'downflooding': downflooding,
        'remaining_gz': remaining_gz, 'gz_snapshots': gz_snapshots,
        'initial_total_water_volume_m3': initial_volume,
        'initial_total_water_mass_t': initial_mass,
        'cumulative_sea_exchange_m3': cumulative_sea,
        'cumulative_sea_exchange_t': cumulative_sea_mass,
        'volume_conservation_error_m3': (
            final_state['volume_conservation_error_m3'] if final_state else 0.0),
        'mass_conservation_error_t': (
            final_state['mass_conservation_error_t'] if final_state else 0.0),
        'diagnostics': diagnostics,
        'assumptions': {
            'mass_convention': 'scenario water is additional mass; no lost-buoyancy subtraction',
            'fsc_policy': 'centroid_geometry_no_additional_fsc',
            'fluid': 'single incompressible same-density vented liquid network',
            'opening': 'fully submerged point-orifice flow; finite partial aperture is unsupported',
            'equilibrium': 'full force and projected-moment equilibrium at every accepted state',
        },
    }
