"""Private conservative pressure-head network used by connected flooding."""
from __future__ import annotations

import copy
import math

try:
    from .tank_geometry import liquid_state
except ImportError:  # Preserve direct-module imports used by repository tests.
    from tank_geometry import liquid_state


METHOD_VERSION = 'vented-orifice-network-2'
DEFAULT_GRAVITY_M_S2 = 9.80665
ANGLE_LIMIT_DEG = 89.0
RATE_TOLERANCE_M3_S = 1e-12
MAX_STEP_HALVINGS = 60
UNSUPPORTED_PRESSURE_FIELDS = ('pressure_pa', 'from_pressure_pa',
                              'to_pressure_pa', 'air_pressure_pa')
# A gross-flow budget bounds one explicit step; a physical full/dry event needs
# the accepted net volume to reach capacity or zero within numerical round-off.
MODEL_LIMIT_REASONS = {
    'flooding.partial_aperture_unsupported': 'partial_aperture',
    'flooding.liquid_plane_unsupported': 'liquid_plane_unsupported',
    'flooding.derived_flow_out_of_range': 'derived_flow_out_of_range',
}


def _number(value, name, *, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite real number')
    result = float(value)
    if minimum is not None and result < minimum:
        raise ValueError(f'{name} must be at least {minimum}')
    if maximum is not None and result > maximum:
        raise ValueError(f'{name} must be at most {maximum}')
    return result


def _reject_pressure_state(node, path):
    """Refuse recognized pressure state: this network is vented only."""
    for unsupported in UNSUPPORTED_PRESSURE_FIELDS:
        if unsupported in node:
            raise ValueError(f'{path}.{unsupported} is outside the vented-liquid model')


def _model_limit_reason(evaluation):
    """Return the visible stop reason carried by a blocking kernel diagnostic."""
    for item in evaluation.get('diagnostics', []):
        if item.get('blocking'):
            return MODEL_LIMIT_REASONS.get(item.get('code'), 'model_limit')
    return 'model_limit'


def _metadata(value, name, path):
    if name not in value:
        raise ValueError(f'{path}.{name} metadata must be explicit')
    return copy.deepcopy(value[name])


def _source(value, path):
    source = _metadata(value, 'source', path)
    if not ((isinstance(source, str) and source.strip())
            or (isinstance(source, dict) and source)):
        raise ValueError(f'{path}.source must be a non-empty string or object')
    return source


def _dot(a, b):
    return math.fsum(x*y for x, y in zip(a, b))


def _normal(attitude):
    if not isinstance(attitude, dict):
        raise ValueError('attitude must be an object')
    heel = _number(attitude.get('heel_deg'), 'attitude.heel_deg')
    trim = _number(attitude.get('trim_deg'), 'attitude.trim_deg')
    keel_offset = _number(
        attitude.get('geometry_keel_offset_m'), 'attitude.geometry_keel_offset_m')
    if abs(heel) >= ANGLE_LIMIT_DEG or abs(trim) >= ANGLE_LIMIT_DEG:
        raise ValueError('fixed-attitude slopes require absolute angles below 89 degrees')
    p = math.tan(math.radians(trim))
    q = math.tan(math.radians(heel))
    scale = math.sqrt(1.0 + p*p + q*q)
    return (-p/scale, -q/scale, 1.0/scale), heel, trim, keel_offset


def _prepare_tanks(tanks, volumes_m3, heel, trim):
    if not isinstance(tanks, list):
        raise ValueError('tanks must be a list')
    if not isinstance(volumes_m3, dict):
        raise ValueError('volumes_m3 must be an object keyed by tank id')
    prepared = {}
    for index, tank in enumerate(tanks):
        path = f'tanks[{index}]'
        if not isinstance(tank, dict):
            raise ValueError(f'{path} must be an object')
        _reject_pressure_state(tank, path)
        tank_id = tank.get('id')
        if not isinstance(tank_id, str) or not tank_id:
            raise ValueError(f'{path}.id must be a non-empty string')
        if tank_id in prepared:
            raise ValueError(f'duplicate tank id {tank_id!r}')
        density = _number(
            tank.get('fluid_density_t_m3'), f'{path}.fluid_density_t_m3',
            minimum=math.nextafter(0.0, math.inf))
        source = _source(tank, path)
        estimate = _metadata(tank, 'estimate', path)
        if tank_id not in volumes_m3:
            raise ValueError(f'missing volume for tank {tank_id!r}')
        volume = _number(volumes_m3[tank_id], f'volumes_m3.{tank_id}', minimum=0.0)
        state = liquid_state(tank, volume, heel_deg=heel, trim_deg=trim)
        prepared[tank_id] = {
            'geometry': copy.deepcopy(tank),
            'volume_m3': volume,
            'capacity_m3': state['capacity_m3'],
            'fluid_density_t_m3': density,
            'source': source,
            'estimate': estimate,
            'liquid_state': state,
        }
    extras = set(volumes_m3) - set(prepared)
    if extras:
        raise ValueError(f'volumes supplied for unknown tanks: {sorted(extras)!r}')
    return prepared


def _prepare_sea(sea, normal, tank_ids):
    if sea is None:
        return None
    if not isinstance(sea, dict):
        raise ValueError('sea must be an object')
    sea_id = sea.get('id')
    if not isinstance(sea_id, str) or not sea_id:
        raise ValueError('sea.id must be a non-empty string')
    if sea_id in tank_ids:
        raise ValueError('sea node id must be distinct from every tank id')
    _reject_pressure_state(sea, 'sea')
    return {
        'id': sea_id,
        'surface_offset_m': _number(sea.get('surface_offset_m'), 'sea.surface_offset_m'),
        'fluid_density_t_m3': _number(
            sea.get('fluid_density_t_m3'), 'sea.fluid_density_t_m3',
            minimum=math.nextafter(0.0, math.inf)),
        'source': _source(sea, 'sea'),
        'estimate': _metadata(sea, 'estimate', 'sea'),
        'normal': list(normal),
    }


def _full_surface_offset(tank, normal, keel_offset):
    centre = (
        tank['x_m'], tank['y_m'],
        tank['keel_to_bottom_m'] + keel_offset + tank['height_m']/2.0,
    )
    return (_dot(normal, centre)
            + abs(normal[0])*tank['length_m']/2.0
            + abs(normal[1])*tank['beam_m']/2.0
            + abs(normal[2])*tank['height_m']/2.0)


def _node(node_id, tanks, sea_node):
    """Return the node kind and its explicit fluid density, without any head."""
    if sea_node is not None and node_id == sea_node['id']:
        return 'sea', sea_node['fluid_density_t_m3']
    if node_id not in tanks:
        raise ValueError(f'connection references unknown node {node_id!r}')
    return 'tank', tanks[node_id]['fluid_density_t_m3']


def _surface(node_id, tanks, sea_node, normal, keel_offset, point):
    """Return {'surface_offset_m', 'head_m'}, or None when no plane is resolved.

    An empty tank and an explicit locked-centroid proxy both lack a liquid plane.
    The empty tank has a defined zero head; the locked proxy has none at all, so
    the caller must not invent one.
    """
    if sea_node is not None and node_id == sea_node['id']:
        offset = sea_node['surface_offset_m']
    else:
        prepared = tanks[node_id]
        state = prepared['liquid_state']
        if state['volume_m3'] == 0.0:
            return {'surface_offset_m': None, 'head_m': 0.0}
        if state['volume_m3'] == state['capacity_m3']:
            offset = _full_surface_offset(prepared['geometry'], normal, keel_offset)
        elif state['plane_offset_m'] is None:
            return None
        else:
            offset = state['plane_offset_m']+normal[2]*keel_offset
    projection = _dot(normal, point)
    if not math.isfinite(offset) or not math.isfinite(projection):
        raise ValueError(f'node {node_id!r} derived liquid head is outside the numeric range')
    head = 0.0 if offset <= projection else offset-projection
    if not math.isfinite(head):
        raise ValueError(f'node {node_id!r} derived liquid head is outside the numeric range')
    return {'surface_offset_m': offset, 'head_m': head}


def _orifice_flow(coefficient, area, gravity, head_difference_m):
    """Evaluate Cd A sqrt(2 g |dh|), scaling every factor when necessary.

    The velocity alone may overflow even when a small aperture makes the final
    discharge representable. Binary exponents avoid that intermediate limit.
    """
    product = 2.0*gravity*abs(head_difference_m)
    if 0 < product < math.inf:
        ordinary = coefficient*area*math.sqrt(product)
        if 0 < ordinary < math.inf:
            return ordinary
    mantissa, exponent = 1.0, 0
    for factor in (coefficient, area, math.sqrt(2.0), math.sqrt(gravity),
                   math.sqrt(abs(head_difference_m))):
        fraction, power = math.frexp(factor)
        mantissa *= fraction
        exponent += power
    try:
        return math.ldexp(mantissa, exponent)
    except OverflowError:
        return math.inf


def _prepare_connection(edge, index, node_ids, sea_node):
    path = f'connections[{index}]'
    if not isinstance(edge, dict):
        raise ValueError(f'{path} must be an object')
    _reject_pressure_state(edge, path)
    edge_id = edge.get('id')
    if not isinstance(edge_id, str) or not edge_id:
        raise ValueError(f'{path}.id must be a non-empty string')
    source, target = edge.get('from_node_id'), edge.get('to_node_id')
    if source not in node_ids or target not in node_ids:
        raise ValueError(f'connection {edge_id!r} has a dangling node reference')
    if source == target:
        raise ValueError(f'connection {edge_id!r} must join distinct nodes')
    if sea_node is not None and source == sea_node['id'] and target == sea_node['id']:
        raise ValueError(f'connection {edge_id!r} cannot join sea to itself')
    centre = edge.get('centre_m')
    if not isinstance(centre, (list, tuple)) or len(centre) != 3:
        raise ValueError(f'connection {edge_id!r}.centre_m must have three coordinates')
    centre = tuple(_number(value, f'{path}.centre_m[{axis}]')
                   for axis, value in enumerate(centre))
    is_open = edge.get('open')
    if not isinstance(is_open, bool):
        raise ValueError(f'connection {edge_id!r}.open must be a boolean')
    aperture_height = None
    if 'aperture_height_m' in edge:
        aperture_height = _number(
            edge['aperture_height_m'], f'{path}.aperture_height_m',
            minimum=math.nextafter(0.0, math.inf))
    return {
        'id': edge_id, 'from_node_id': source, 'to_node_id': target,
        'centre_m': centre,
        'area_m2': _number(edge.get('area_m2'), f'{path}.area_m2', minimum=0.0),
        'discharge_coefficient': _number(
            edge.get('discharge_coefficient'), f'{path}.discharge_coefficient',
            minimum=0.0, maximum=1.0),
        'fluid_density_t_m3': _number(
            edge.get('fluid_density_t_m3'), f'{path}.fluid_density_t_m3',
            minimum=math.nextafter(0.0, math.inf)),
        'open': is_open, 'aperture_height_m': aperture_height,
        'source': _source(edge, path),
        'estimate': _metadata(edge, 'estimate', path),
    }


def evaluate_flows(tanks, volumes_m3, connections, *, attitude, sea=None,
                   gravity_m_s2=DEFAULT_GRAVITY_M_S2):
    """Evaluate signed point-orifice flows for one frozen attitude."""
    gravity = _number(gravity_m_s2, 'gravity_m_s2',
                      minimum=math.nextafter(0.0, math.inf))
    normal, heel, trim, keel_offset = _normal(attitude)
    prepared_tanks = _prepare_tanks(tanks, volumes_m3, heel, trim)
    sea_node = _prepare_sea(sea, normal, set(prepared_tanks))
    node_ids = set(prepared_tanks)
    if sea_node is not None:
        node_ids.add(sea_node['id'])
    if not isinstance(connections, list):
        raise ValueError('connections must be a list')

    rows, seen_ids, diagnostics = [], set(), []
    result_status = 'applicable'
    for index, raw_edge in enumerate(connections):
        edge = _prepare_connection(raw_edge, index, node_ids, sea_node)
        if edge['id'] in seen_ids:
            raise ValueError(f'duplicate connection id {edge["id"]!r}')
        seen_ids.add(edge['id'])
        point = (edge['centre_m'][0], edge['centre_m'][1],
                 edge['centre_m'][2]+keel_offset)
        left_density = _node(edge['from_node_id'], prepared_tanks, sea_node)[1]
        right_density = _node(edge['to_node_id'], prepared_tanks, sea_node)[1]
        densities = (left_density, right_density, edge['fluid_density_t_m3'])
        if not (densities[0] == densities[1] == densities[2]):
            raise ValueError(
                f'connection {edge["id"]!r} must use one identical explicit fluid density')

        edge_status, flow = 'flowing', None
        left = right = None
        if not edge['open']:
            # A closed valve transfers nothing and needs no hydrostatic head.
            edge_status, flow = 'closed', 0.0
        else:
            left = _surface(edge['from_node_id'], prepared_tanks, sea_node,
                            normal, keel_offset, point)
            right = _surface(edge['to_node_id'], prepared_tanks, sea_node,
                             normal, keel_offset, point)
            if left is None or right is None:
                edge_status = 'unsupported_liquid_plane'
                result_status = 'model_limit'
                diagnostics.append({
                    'code': 'flooding.liquid_plane_unsupported',
                    'severity': 'error', 'path': f'$.connections.{edge["id"]}',
                    'message': 'A connected node has no resolved liquid plane; a locked liquid-centroid proxy has no free surface for this vented head model.',
                    'blocking': True,
                })
            elif edge['area_m2'] == 0.0 or edge['discharge_coefficient'] == 0.0:
                edge_status, flow = 'zero_area', 0.0
            elif left['head_m'] == right['head_m']:
                edge_status, flow = 'equal_heads', 0.0
        if (edge_status == 'flowing' and flow is None
                and edge['aperture_height_m'] is not None):
            half_normal_height = abs(normal[2])*edge['aperture_height_m']/2.0
            for endpoint in (left, right):
                offset = endpoint['surface_offset_m']
                if offset is not None and abs(offset-_dot(normal, point)) < half_normal_height:
                    edge_status = 'partial_aperture_unsupported'
                    result_status = 'model_limit'
                    diagnostics.append({
                        'code': 'flooding.partial_aperture_unsupported',
                        'severity': 'error', 'path': f'$.connections.{edge["id"]}',
                        'message': 'A liquid surface intersects the finite aperture height; the point-orifice law is not applicable.',
                        'blocking': True,
                    })
                    break
        if edge_status == 'flowing' and flow is None:
            difference = left['head_m']-right['head_m']
            flow = math.copysign(
                _orifice_flow(edge['discharge_coefficient'], edge['area_m2'],
                              gravity, difference), difference)
            if not math.isfinite(flow) or not math.isfinite(flow*edge['fluid_density_t_m3']):
                # The declared inputs are finite but their discharge is not
                # representable; report the range instead of a non-finite value.
                flow = None
                edge_status = 'out_of_range'
                result_status = 'model_limit'
                diagnostics.append({
                    'code': 'flooding.derived_flow_out_of_range',
                    'severity': 'error', 'path': f'$.connections.{edge["id"]}',
                    'message': 'The declared volume or mass discharge is outside the representable numeric range of this model.',
                    'blocking': True,
                })
        rows.append({
            **edge, 'centre_m': list(edge['centre_m']),
            'from_head_m': left['head_m'] if left else None,
            'to_head_m': right['head_m'] if right else None,
            'flow_m3_s': flow, 'status': edge_status,
            'model': 'fully_submerged_point_orifice',
        })
    return {
        'method_version': METHOD_VERSION, 'mode': 'fixed_attitude_validation',
        'status': result_status, 'normal': list(normal),
        'heel_deg': heel, 'trim_deg': trim,
        'geometry_keel_offset_m': keel_offset, 'gravity_m_s2': gravity,
        'tank_states': prepared_tanks, 'sea': copy.deepcopy(sea_node),
        'edges': rows, 'diagnostics': diagnostics,
    }


def _refused(reason, volumes_m3, boundary_reason=None):
    """Return a visible model limit that leaves every accepted volume untouched."""
    return {'status': 'model_limit', 'stop_reason': reason, 'actual_dt_s': 0.0,
            'volumes_m3': copy.deepcopy(volumes_m3), 'edge_transfers': [],
            'sea_exchange_m3': 0.0, 'sea_exchange_t': 0.0,
            'boundary_reason': boundary_reason}


def _accepted_boundary_reason(evaluation, incoming, outgoing, duration):
    """Return the genuine full/dry event implied by the accepted net state.

    A tank is on a physical boundary only when its net exchange actually reaches
    capacity (filling) or zero (draining). Simultaneous inflow and outflow that
    merely exhausts a gross-flow budget is not such an event.
    """
    events = []
    for tank_id, prepared in evaluation['tank_states'].items():
        net = math.fsum((incoming[tank_id], -outgoing[tank_id]))
        if net == 0.0:
            continue
        capacity = prepared['capacity_m3']
        volume = prepared['volume_m3']
        event_time = (capacity-volume)/net if net > 0.0 else volume/-net
        # Compare the event time to the accepted step, rather than treating a
        # positive remaining volume as full/dry using a hull-scale tolerance.
        if event_time <= duration or math.isclose(event_time, duration, rel_tol=8e-15):
            events.append((event_time, 'receiver_capacity' if net > 0 else 'source_dry'))
    if not events:
        return None
    return min(events, key=lambda event: event[0])[1]


def propose_transfers(evaluation, volumes_m3, requested_dt_s):
    """Return one aggregate-budgeted conservative candidate without solving attitude."""
    try:
        return _propose_transfers(evaluation, volumes_m3, requested_dt_s)
    except OverflowError:
        return _refused('numeric_out_of_range', volumes_m3)


def _propose_transfers(evaluation, volumes_m3, requested_dt_s):
    requested_dt = _number(
        requested_dt_s, 'requested_dt_s', minimum=math.nextafter(0.0, math.inf))
    if evaluation['status'] == 'model_limit':
        return _refused(_model_limit_reason(evaluation), volumes_m3)
    active = [edge for edge in evaluation['edges'] if edge['flow_m3_s'] != 0.0]
    if not active:
        return {'status': 'equilibrium', 'stop_reason': 'equal_heads_or_no_open_flow',
                'actual_dt_s': 0.0, 'volumes_m3': copy.deepcopy(volumes_m3),
                'edge_transfers': [], 'sea_exchange_m3': 0.0,
                'sea_exchange_t': 0.0, 'boundary_reason': None}
    sea_id = evaluation['sea']['id'] if evaluation['sea'] is not None else None
    outgoing = {tank_id: 0.0 for tank_id in volumes_m3}
    incoming = {tank_id: 0.0 for tank_id in volumes_m3}
    for edge in active:
        rate = edge['flow_m3_s']
        source = edge['from_node_id'] if rate > 0.0 else edge['to_node_id']
        target = edge['to_node_id'] if rate > 0.0 else edge['from_node_id']
        if source != sea_id:
            outgoing[source] = math.fsum((outgoing[source], abs(rate)))
        if target != sea_id:
            incoming[target] = math.fsum((incoming[target], abs(rate)))
    # The gross budgets keep every single edge transfer possible inside one
    # explicit step. They limit the step; they do not declare a physical event.
    duration = requested_dt
    for tank_id, prepared in evaluation['tank_states'].items():
        volume = prepared['volume_m3']
        capacity = prepared['capacity_m3']
        for gross, available, reason in (
                (outgoing[tank_id], volume, 'source_dry'),
                (incoming[tank_id], capacity-volume, 'receiver_capacity')):
            if gross <= 0.0:
                continue
            if available <= 0.0:
                # No conservative step is possible and the node already sits on
                # that boundary, so the model reports it instead of stalling.
                return _refused(reason, volumes_m3, boundary_reason=reason)
            duration = min(duration, available/gross)
    if duration <= 0.0:
        return _refused('numeric_out_of_range', volumes_m3)

    result = dict(volumes_m3)
    transfers, sea_exchange, sea_mass = [], 0.0, 0.0
    for edge in active:
        transfer = edge['flow_m3_s']*duration
        source, target = edge['from_node_id'], edge['to_node_id']
        if source != sea_id:
            result[source] = math.fsum((result[source], -transfer))
        else:
            sea_exchange = math.fsum((sea_exchange, transfer))
            sea_mass = math.fsum((sea_mass, transfer*edge['fluid_density_t_m3']))
        if target != sea_id:
            result[target] = math.fsum((result[target], transfer))
        else:
            sea_exchange = math.fsum((sea_exchange, -transfer))
            sea_mass = math.fsum((sea_mass, -transfer*edge['fluid_density_t_m3']))
        transfers.append({
            'connection_id': edge['id'], 'from_node_id': source,
            'to_node_id': target, 'flow_m3_s': edge['flow_m3_s'],
            'transfer_m3': transfer,
            'transfer_t': transfer*edge['fluid_density_t_m3'],
        })
    derived = [row[field] for row in transfers
               for field in ('flow_m3_s', 'transfer_m3', 'transfer_t')]
    if (not all(math.isfinite(value) for value in derived)
            or not all(math.isfinite(value) for value in result.values())
            or not math.isfinite(sea_exchange) or not math.isfinite(sea_mass)):
        # Finite declared inputs whose transfers are not representable are
        # refused as a range limit; no volume or ledger value is fabricated.
        return _refused('numeric_out_of_range', volumes_m3)
    boundary_reason = _accepted_boundary_reason(
        evaluation, incoming, outgoing, duration)
    return {'status': 'candidate', 'stop_reason': boundary_reason,
            'actual_dt_s': duration, 'volumes_m3': result,
            'edge_transfers': transfers, 'sea_exchange_m3': sea_exchange,
            'sea_exchange_t': sea_mass, 'boundary_reason': boundary_reason}


def has_flow_reversal(before, after):
    """Return true when an active edge changes sign beyond the zero-rate tolerance."""
    after_by_id = {edge['id']: edge for edge in after['edges']}
    for edge in before['edges']:
        rate = edge['flow_m3_s']
        if rate in (None, 0.0):
            continue
        next_rate = after_by_id[edge['id']]['flow_m3_s']
        if (next_rate is not None and abs(rate) > RATE_TOLERANCE_M3_S
                and abs(next_rate) > RATE_TOLERANCE_M3_S and rate*next_rate < 0.0):
            return True
    return False


def _model_limit(volumes, reason, evaluation, requested_dt):
    return {
        'method_version': METHOD_VERSION, 'mode': 'fixed_attitude_validation',
        'status': 'model_limit', 'stop_reason': reason,
        'requested_dt_s': requested_dt, 'actual_dt_s': 0.0,
        'volumes_m3': copy.deepcopy(volumes), 'edge_transfers': [],
        'sea_exchange_m3': 0.0, 'sea_exchange_t': 0.0,
        'volume_conservation_error_m3': 0.0, 'mass_conservation_error_t': 0.0,
        'evaluation': evaluation, 'diagnostics': copy.deepcopy(evaluation['diagnostics']),
    }


def step_fixed_attitude(tanks, volumes_m3, connections, *, attitude,
                        requested_dt_s, sea=None,
                        gravity_m_s2=DEFAULT_GRAVITY_M_S2):
    """Advance one conservative fixed-attitude step with reversal protection."""
    requested_dt = _number(
        requested_dt_s, 'requested_dt_s', minimum=math.nextafter(0.0, math.inf))
    before = evaluate_flows(tanks, volumes_m3, connections, attitude=attitude,
                            sea=sea, gravity_m_s2=gravity_m_s2)
    duration = requested_dt
    for _ in range(MAX_STEP_HALVINGS+1):
        candidate = propose_transfers(before, volumes_m3, duration)
        if candidate['status'] != 'candidate':
            result = _model_limit(volumes_m3, candidate['stop_reason'], before, requested_dt)
            result['status'] = candidate['status']
            return result
        try:
            after = evaluate_flows(
                tanks, candidate['volumes_m3'], connections, attitude=attitude,
                sea=sea, gravity_m_s2=gravity_m_s2)
        except ValueError:
            duration /= 2.0
            continue
        if after['status'] == 'model_limit' or has_flow_reversal(before, after):
            duration /= 2.0
            continue
        initial_total = math.fsum(volumes_m3.values())
        final_total = math.fsum(candidate['volumes_m3'].values())
        initial_mass = math.fsum(
            volumes_m3[tank_id]*state['fluid_density_t_m3']
            for tank_id, state in before['tank_states'].items())
        final_mass = math.fsum(
            candidate['volumes_m3'][tank_id]*state['fluid_density_t_m3']
            for tank_id, state in before['tank_states'].items())
        return {
            'method_version': METHOD_VERSION, 'mode': 'fixed_attitude_validation',
            'status': 'advanced', 'stop_reason': candidate['boundary_reason'],
            'requested_dt_s': requested_dt, 'actual_dt_s': candidate['actual_dt_s'],
            'volumes_m3': candidate['volumes_m3'],
            'edge_transfers': candidate['edge_transfers'],
            'sea_exchange_m3': candidate['sea_exchange_m3'],
            'sea_exchange_t': candidate['sea_exchange_t'],
            'volume_conservation_error_m3': (
                final_total-initial_total-candidate['sea_exchange_m3']),
            'mass_conservation_error_t': (
                final_mass-initial_mass-candidate['sea_exchange_t']),
            'evaluation': after, 'diagnostics': [],
        }
    return _model_limit(volumes_m3, 'minimum_timestep', before, requested_dt)


def simulate_fixed_attitude(tanks, initial_volumes_m3, connections, *, attitude,
                            duration_s, requested_dt_s, sea=None,
                            gravity_m_s2=DEFAULT_GRAVITY_M_S2,
                            max_steps=100000):
    """Integrate the fixed-attitude validation mode with auditable ledgers."""
    duration = _number(duration_s, 'duration_s', minimum=0.0)
    requested_dt = _number(requested_dt_s, 'requested_dt_s',
                           minimum=math.nextafter(0.0, math.inf))
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps <= 0:
        raise ValueError('max_steps must be a positive integer')
    volumes = copy.deepcopy(initial_volumes_m3)
    initial = evaluate_flows(tanks, volumes, connections, attitude=attitude,
                             sea=sea, gravity_m_s2=gravity_m_s2)
    densities = {tank_id: state['fluid_density_t_m3']
                 for tank_id, state in initial['tank_states'].items()}
    initial_total = math.fsum(volumes.values())
    initial_mass = math.fsum(volumes[k]*density for k, density in densities.items())
    time_s = cumulative_sea = cumulative_sea_mass = 0.0
    timeline = [{'time_s': 0.0, 'actual_dt_s': 0.0,
                 'volumes_m3': copy.deepcopy(volumes),
                 'edge_flows': copy.deepcopy(initial['edges']),
                 'edge_transfers': [], 'sea_exchange_m3': 0.0,
                 'sea_exchange_t': 0.0, 'cumulative_sea_exchange_m3': 0.0,
                 'cumulative_sea_exchange_t': 0.0,
                 'volume_conservation_error_m3': 0.0,
                 'mass_conservation_error_t': 0.0}]
    status = 'completed' if duration == 0 else 'running'
    stop_reason = 'scheduled_completion' if duration == 0 else None
    diagnostics = copy.deepcopy(initial['diagnostics'])
    if initial['status'] == 'model_limit':
        status, stop_reason = 'model_limit', _model_limit_reason(initial)
    steps = 0
    while status == 'running' and time_s < duration:
        if steps >= max_steps:
            status, stop_reason = 'model_limit', 'step_limit'
            break
        step = step_fixed_attitude(
            tanks, volumes, connections, attitude=attitude,
            requested_dt_s=min(requested_dt, duration-time_s), sea=sea,
            gravity_m_s2=gravity_m_s2)
        if step['status'] != 'advanced':
            status = 'completed' if step['status'] == 'equilibrium' else step['status']
            stop_reason = step['stop_reason']
            diagnostics.extend(step['diagnostics'])
            break
        volumes = step['volumes_m3']
        time_s = math.fsum((time_s, step['actual_dt_s']))
        cumulative_sea = math.fsum((cumulative_sea, step['sea_exchange_m3']))
        cumulative_sea_mass = math.fsum((cumulative_sea_mass, step['sea_exchange_t']))
        total = math.fsum(volumes.values())
        mass = math.fsum(volumes[k]*density for k, density in densities.items())
        timeline.append({
            'time_s': time_s, 'actual_dt_s': step['actual_dt_s'],
            'volumes_m3': copy.deepcopy(volumes),
            'edge_flows': copy.deepcopy(step['evaluation']['edges']),
            'edge_transfers': copy.deepcopy(step['edge_transfers']),
            'sea_exchange_m3': step['sea_exchange_m3'],
            'sea_exchange_t': step['sea_exchange_t'],
            'cumulative_sea_exchange_m3': cumulative_sea,
            'cumulative_sea_exchange_t': cumulative_sea_mass,
            'volume_conservation_error_m3': total-initial_total-cumulative_sea,
            'mass_conservation_error_t': mass-initial_mass-cumulative_sea_mass,
        })
        steps += 1
        if time_s >= duration or math.isclose(time_s, duration, rel_tol=0.0, abs_tol=1e-14):
            timeline[-1]['time_s'] = duration
            time_s = duration
            status, stop_reason = 'completed', 'scheduled_completion'
        elif step['stop_reason'] is not None:
            status, stop_reason = 'model_limit', step['stop_reason']
    final_total = math.fsum(volumes.values())
    final_mass = math.fsum(volumes[k]*density for k, density in densities.items())
    return {
        'method_version': METHOD_VERSION, 'mode': 'fixed_attitude_validation',
        'status': status, 'stop_reason': stop_reason,
        'requested_duration_s': duration, 'elapsed_time_s': time_s,
        'requested_dt_s': requested_dt,
        'initial_total_volume_m3': initial_total,
        'final_total_volume_m3': final_total,
        'initial_total_mass_t': initial_mass, 'final_total_mass_t': final_mass,
        'final_volumes_m3': copy.deepcopy(volumes),
        'cumulative_sea_exchange_m3': cumulative_sea,
        'cumulative_sea_exchange_t': cumulative_sea_mass,
        'volume_conservation_error_m3': final_total-initial_total-cumulative_sea,
        'mass_conservation_error_t': final_mass-initial_mass-cumulative_sea_mass,
        'timeline': timeline, 'diagnostics': diagnostics,
        'limitations': {
            'attitude': 'fixed; no floating-body equilibrium is solved',
            'fluid': 'single incompressible fluid with identical explicit density',
            'opening': 'vented fully submerged point-orifice approximation',
        },
    }
