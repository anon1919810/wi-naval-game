"""Liquid in an explicit rectangular compartment under a planar free surface.

Angles describe body-coordinate waterplane slopes, not sequential Euler angles.
Uniform permeability scales available volume and area; it does not reduce depth.
Centroid movement is resolved geometrically: do not add FSC for the same liquid.
"""
from __future__ import annotations

import copy
import math


METHOD_VERSION = 'rectangular-liquid-geometry-1'
MAX_PARTIAL_ASPECT_RATIO = 1e12
MIN_ACTIVE_PHASE_FRACTION = 1e-13
ANGLE_LIMIT_DEG = 89.0


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite real number')
    return float(value)


def _checked_positive_product(values, name):
    """Multiply non-negative factors without order-dependent overflow/underflow."""
    mantissa, exponent = 1.0, 0
    for value in values:
        if value == 0.0:
            return 0.0
        factor_mantissa, factor_exponent = math.frexp(value)
        mantissa *= factor_mantissa
        exponent += factor_exponent
        mantissa, adjustment = math.frexp(mantissa)
        exponent += adjustment
    try:
        product = math.ldexp(mantissa, exponent)
    except OverflowError as exc:
        raise ValueError(f'{name} exceeds numerical range') from exc
    if not math.isfinite(product):
        raise ValueError(f'{name} exceeds numerical range')
    if product == 0.0:
        raise ValueError(f'{name} is below the positive numerical range')
    return product


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _unique(points, tolerance):
    result = []
    for point in points:
        if not any(_dot(_sub(point, old), _sub(point, old)) <= tolerance*tolerance for old in result):
            result.append(point)
    return result


def _basis(normal):
    # Projection of body +x onto the free surface, then v chosen so u×v=n.
    raw = (1-normal[0]*normal[0], -normal[0]*normal[1], -normal[0]*normal[2])
    magnitude = math.sqrt(_dot(raw, raw))
    u = tuple(value/magnitude for value in raw)
    return u, _cross(normal, u)


def _cube_faces(length, beam, height):
    a, b, c = length/2, beam/2, height/2
    vertices = [(-a,-b,-c), (a,-b,-c), (a,b,-c), (-a,b,-c),
                (-a,-b,c), (a,-b,c), (a,b,c), (-a,b,c)]
    indexes = [(3,2,1,0), (4,5,6,7), (0,1,5,4),
               (1,2,6,5), (2,3,7,6), (3,0,4,7)]
    return vertices, [[vertices[i] for i in face] for face in indexes]


def _clip_faces(faces, normal, offset, tolerance):
    clipped, boundary = [], []
    for face in faces:
        polygon = []
        for index, current in enumerate(face):
            previous = face[index-1]
            a, b = _dot(normal, previous)-offset, _dot(normal, current)-offset
            if (a <= 0) != (b <= 0):
                fraction = a/(a-b)
                crossing = tuple(x+fraction*(y-x) for x, y in zip(previous, current))
                polygon.append(crossing)
                boundary.append(crossing)
            if b <= 0:
                polygon.append(current)
                if abs(b) <= tolerance:
                    boundary.append(current)
        polygon = _unique(polygon, tolerance)
        if len(polygon) >= 3:
            clipped.append(polygon)
    cap = _unique(boundary, tolerance)
    if len(cap) >= 3:
        centre = tuple(sum(p[i] for p in cap)/len(cap) for i in range(3))
        u, v = _basis(normal)
        cap.sort(key=lambda p: math.atan2(_dot(_sub(p, centre), v), _dot(_sub(p, centre), u)))
        clipped.append(cap)
    else:
        cap = []
    return clipped, cap


def _volume_centroid(faces):
    points = [point for face in faces for point in face]
    if not points:
        return 0.0, None
    # A convex combination is inside the clipped body. Using it as a tetrahedron
    # origin avoids subtraction of large signed volumes for very shallow liquid.
    origin = tuple(math.fsum(p[i] for p in points)/len(points) for i in range(3))
    volumes, moments = [], [[], [], []]
    for face in faces:
        for j in range(1, len(face)-1):
            a, b, c = face[0], face[j], face[j+1]
            volume = _dot(_sub(a, origin), _cross(_sub(b, origin), _sub(c, origin)))/6
            volumes.append(volume)
            for axis in range(3):
                moments[axis].append(volume*(origin[axis]+a[axis]+b[axis]+c[axis])/4)
    volume = math.fsum(volumes)
    if volume <= 0:
        return 0.0, None
    return volume, tuple(math.fsum(m)/volume for m in moments)


def _empty_surface(normal):
    u, v = _basis(normal)
    return dict(active=False, polygon_m=[], centroid_m=None, area_m2=0.0,
                i_u_m4=0.0, i_v_m4=0.0, i_uv_m4=0.0,
                available_area_m2=0.0, available_i_u_m4=0.0,
                available_i_v_m4=0.0, available_i_uv_m4=0.0,
                basis_u=list(u), basis_v=list(v), normal=list(normal),
                converged=None,
                applicability=dict(status='inactive', reason='empty_or_full_or_locked'),
                moment_convention=dict(
                    basis_handedness='basis_u cross basis_v = normal',
                    i_u_m4='integral(v^2 dA) about the surface centroid',
                    i_v_m4='integral(u^2 dA) about the surface centroid',
                    i_uv_m4='signed integral(u*v dA) about the surface centroid',
                    tensor_off_diagonal='-i_uv_m4'))


def _surface(cap, normal, centre, permeability):
    result = _empty_surface(normal)
    if len(cap) < 3:
        return result
    origin = tuple(math.fsum(p[i] for p in cap)/len(cap) for i in range(3))
    u, v = result['basis_u'], result['basis_v']
    xy = [(_dot(_sub(p, origin), u), _dot(_sub(p, origin), v)) for p in cap]
    crosses, mx, my, ixx, iyy, ixy = [], [], [], [], [], []
    for i, (x0, y0) in enumerate(xy):
        x1, y1 = xy[(i+1) % len(xy)]
        cross = x0*y1-x1*y0
        crosses.append(cross)
        mx.append((x0+x1)*cross)
        my.append((y0+y1)*cross)
        ixx.append((y0*y0+y0*y1+y1*y1)*cross)
        iyy.append((x0*x0+x0*x1+x1*x1)*cross)
        ixy.append((2*x0*y0+x0*y1+x1*y0+2*x1*y1)*cross)
    area = math.fsum(crosses)/2
    if area <= 0:
        raise ValueError('free surface polygon has invalid orientation or zero area')
    cx, cy = math.fsum(mx)/(6*area), math.fsum(my)/(6*area)
    iu = math.fsum(ixx)/12-area*cy*cy
    iv = math.fsum(iyy)/12-area*cx*cx
    iuv = math.fsum(ixy)/24-area*cx*cy
    result.update(active=True, area_m2=area, i_u_m4=iu, i_v_m4=iv, i_uv_m4=iuv,
                  available_area_m2=permeability*area,
                  available_i_u_m4=permeability*iu, available_i_v_m4=permeability*iv,
                  available_i_uv_m4=permeability*iuv,
                  centroid_m=[centre[i]+origin[i]+cx*u[i]+cy*v[i] for i in range(3)],
                  polygon_m=[[centre[i]+p[i] for i in range(3)] for p in cap],
                  converged=True,
                  applicability=dict(status='applicable', reason='resolved_active_section'))
    return result


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _ensure_public_geometry_is_finite(result):
    scalar_fields = ('volume_m3', 'requested_volume_m3', 'integrated_volume_m3',
                     'capacity_m3', 'gross_volume_m3', 'geometric_volume_m3',
                     'fill_fraction', 'permeability', 'heel_deg', 'trim_deg',
                     'volume_residual_m3', 'volume_tolerance_m3')
    for field in scalar_fields:
        if not _finite(result[field]):
            raise ValueError(f'derived public field {field} must be finite')
    if result['plane_offset_m'] is not None and not _finite(result['plane_offset_m']):
        raise ValueError('derived public field plane_offset_m must be finite')
    if result['plane_offset_local_m'] is not None and not _finite(result['plane_offset_local_m']):
        raise ValueError('derived public field plane_offset_local_m must be finite')
    for field in ('plane_normal', 'centroid_m'):
        values = result[field]
        if values is not None and not all(_finite(value) for value in values):
            raise ValueError(f'derived public field {field} must be finite')
    surface = result['free_surface']
    for field in ('area_m2', 'i_u_m4', 'i_v_m4', 'i_uv_m4',
                  'available_area_m2', 'available_i_u_m4',
                  'available_i_v_m4', 'available_i_uv_m4'):
        if not _finite(surface[field]):
            raise ValueError(f'derived public field free_surface.{field} must be finite')
    for field in ('basis_u', 'basis_v', 'normal'):
        if not all(_finite(value) for value in surface[field]):
            raise ValueError(f'derived public field free_surface.{field} must be finite')
    if surface['centroid_m'] is not None and not all(_finite(value) for value in surface['centroid_m']):
        raise ValueError('derived public field free_surface.centroid_m must be finite')
    if not all(all(_finite(value) for value in point) for point in surface['polygon_m']):
        raise ValueError('derived public field free_surface.polygon_m must be finite')
    return result


def _tank_parameters(tank):
    if not isinstance(tank, dict):
        raise ValueError('tank must be an object')
    keys = ('length_m','beam_m','height_m','x_m','y_m','keel_to_bottom_m','permeability')
    values = {key: _number(tank.get(key), key) for key in keys}
    if any(values[key] <= 0 for key in keys[:3]):
        raise ValueError('tank dimensions must be positive')
    if not 0 <= values['permeability'] <= 1:
        raise ValueError('permeability must be within [0,1]')
    if not isinstance(tank.get('free_surface', True), bool):
        raise ValueError('free_surface must be a boolean')
    return values


def _tank_capacity(values):
    dimensions = (values['length_m'], values['beam_m'], values['height_m'])
    gross = _checked_positive_product(dimensions, 'tank gross volume')
    permeability = values['permeability']
    capacity = 0.0 if permeability == 0.0 else _checked_positive_product(
        (gross, permeability), 'tank available capacity')
    return gross, capacity


def _solve_small_phase(faces, vertices, normal, target, point_tolerance):
    projections = [_dot(normal, point) for point in vertices]
    lo, hi = min(projections), max(projections)
    tolerance = max(target * 2e-12, math.ulp(target) * 8)
    for iteration in range(1, 101):
        offset = (lo + hi) / 2
        clipped, cap = _clip_faces(faces, normal, offset, point_tolerance)
        volume, centroid = _volume_centroid(clipped)
        error = volume - target
        if abs(error) <= tolerance and centroid is not None and len(cap) >= 3:
            return offset, volume, centroid, cap, error, tolerance, iteration
        if offset == lo or offset == hi:
            raise ValueError('liquid small phase cannot be resolved at floating-point precision')
        if error < 0:
            lo = offset
        else:
            hi = offset
    raise ValueError('liquid volume root did not converge')


def liquid_state(tank, volume_m3, heel_deg=0, trim_deg=0):
    """Return water volume, centroid and surface in body coordinates (metres).

    ``volume_m3`` denotes real water volume, not gross compartment volume.
    ``free_surface=False`` explicitly requests a locked-centroid solid-load proxy.
    Finite slope coordinates are supported for |heel|, |trim| < 89 degrees.
    """
    values = _tank_parameters(tank)
    requested = _number(volume_m3, 'volume_m3')
    heel = _number(heel_deg, 'heel_deg')
    trim = _number(trim_deg, 'trim_deg')
    if abs(heel) >= ANGLE_LIMIT_DEG or abs(trim) >= ANGLE_LIMIT_DEG:
        raise ValueError('liquid plane supports absolute heel and trim below 89 degrees')
    length, beam, height = (values[k] for k in ('length_m', 'beam_m', 'height_m'))
    gross, capacity = _tank_capacity(values)
    mu = values['permeability']
    if not 0 <= requested <= capacity:
        raise ValueError('volume_m3 is outside the available compartment capacity')
    p, q = math.tan(math.radians(trim)), math.tan(math.radians(heel))
    norm = math.sqrt(1 + p*p + q*q)
    normal = (-p/norm, -q/norm, 1/norm)
    centre = (values['x_m'], values['y_m'], values['keel_to_bottom_m'] + height/2)
    fraction = requested/capacity if capacity else 0.0
    if requested not in (0.0, capacity) and not 0.0 < fraction < 1.0:
        raise ValueError('partial fill fraction is outside the supported numerical domain')
    geometric_requested = requested/mu if mu else 0.0
    result = dict(
        tank_id=tank.get('id', ''), requested_volume_m3=requested,
        volume_m3=requested, integrated_volume_m3=requested,
        capacity_m3=capacity, gross_volume_m3=gross,
        geometric_volume_m3=geometric_requested,
        fill_fraction=fraction, permeability=mu, centroid_m=None,
        heel_deg=heel, trim_deg=trim, plane_normal=list(normal),
        plane_offset_m=None, plane_offset_local_m=None,
        free_surface=_empty_surface(normal),
        method='convex_polyhedron_clipping', method_version=METHOD_VERSION,
        angle_convention='n·r=h with unit n=(-tan(trim_deg),-tan(heel_deg),1)/norm; slope intercept d=h/n_z',
        assumptions={
            'rectangular': 'axis-aligned rectangular compartment',
            'permeability': 'uniform available-volume and free-surface-area factor',
            'free_surface': 'horizontal in the world frame',
        },
        supported_domain={
            'absolute_slope_angle_deg_exclusive': ANGLE_LIMIT_DEG,
            'max_partial_aspect_ratio': MAX_PARTIAL_ASPECT_RATIO,
            'min_active_phase_fraction_inclusive': MIN_ACTIVE_PHASE_FRACTION,
            'positive_phase_requirement': 'smaller phase must be representable and resolvable',
            'full_empty_product_domain': 'positive gross volume and capacity must be representable',
        },
        applicability={'status': 'applicable', 'reason': 'validated_input_in_method_domain'},
        converged=True, volume_residual_m3=0.0, volume_tolerance_m3=0.0,
        iterations=0, fsc_policy='centroid_geometry_no_additional_fsc',
        source=copy.deepcopy(tank.get('source')),
        estimate=copy.deepcopy(tank.get('estimate')), diagnostics=[])
    if requested == 0.0:
        return _ensure_public_geometry_is_finite(result)
    if requested == capacity:
        result['centroid_m'] = list(centre)
        result['geometric_volume_m3'] = gross
        result['integrated_volume_m3'] = capacity
        return _ensure_public_geometry_is_finite(result)
    if not tank.get('free_surface', True):
        result['centroid_m'] = [
            centre[0], centre[1], values['keel_to_bottom_m'] + fraction*height/2]
        result['method'] = 'locked_centroid_proxy'
        result['diagnostics'].append(dict(
            code='liquid.locked_centroid_proxy', severity='warning',
            path='$.free_surface', blocking=False,
            message='Liquid CG is locked to an upright solid-load proxy; closing a valve alone does not remove a free surface.'))
        return _ensure_public_geometry_is_finite(result)

    aspect_ratio = max(length, beam, height)/min(length, beam, height)
    if not math.isfinite(aspect_ratio) or aspect_ratio > MAX_PARTIAL_ASPECT_RATIO:
        raise ValueError(
            f'partial tank aspect ratio exceeds supported limit {MAX_PARTIAL_ASPECT_RATIO:g}')
    vertices, faces = _cube_faces(length, beam, height)
    point_tolerance = min(length, beam, height) * 1e-13
    complement = capacity - requested
    solve_complement = complement < requested
    phase_water = complement if solve_complement else requested
    if phase_water <= 0.0:
        raise ValueError('smaller liquid phase is below the positive numerical range')
    if phase_water/capacity < MIN_ACTIVE_PHASE_FRACTION:
        raise ValueError(
            f'smaller liquid phase fraction is below supported limit '
            f'{MIN_ACTIVE_PHASE_FRACTION:g}')
    phase_target = phase_water/mu
    offset, phase_volume, phase_centroid, phase_cap, _phase_error, tolerance, iteration = (
        _solve_small_phase(faces, vertices, normal, phase_target, point_tolerance))

    if solve_complement:
        geometric_volume = gross - phase_volume
        local_centroid = tuple(
            phase_volume*phase_centroid[i]/geometric_volume for i in range(3))
        offset = -offset
        cap = [tuple(-coordinate for coordinate in point) for point in phase_cap]
    else:
        geometric_volume = phase_volume
        local_centroid = phase_centroid
        cap = phase_cap
    integrated = geometric_volume*mu
    residual = integrated - requested
    result.update(
        integrated_volume_m3=integrated,
        geometric_volume_m3=geometric_volume,
        centroid_m=[centre[i] + local_centroid[i] for i in range(3)],
        plane_offset_local_m=offset,
        plane_offset_m=offset + _dot(normal, centre),
        free_surface=_surface(cap, normal, centre, mu),
        volume_residual_m3=residual,
        volume_tolerance_m3=tolerance*mu,
        iterations=iteration)
    return _ensure_public_geometry_is_finite(result)


def from_legacy_flood_tank(tank, heel_deg=0, trim_deg=0):
    """Explicit adapter from the old flood-fraction dictionary, without extra FSC."""
    values = _tank_parameters(tank)
    fraction = _number(tank.get('flood_fraction'), 'flood_fraction')
    density = _number(tank.get('fluid_density_t_m3'), 'fluid_density_t_m3')
    if not 0 <= fraction <= 1 or density <= 0:
        raise ValueError('flood_fraction must be [0,1] and fluid density positive')
    _, capacity = _tank_capacity(values)
    if fraction == 0.0 or capacity == 0.0:
        volume = 0.0
    elif fraction == 1.0:
        volume = capacity
    else:
        volume = _checked_positive_product(
            (fraction, capacity), 'legacy requested liquid volume')
    result = liquid_state(tank, volume, heel_deg, trim_deg)
    result['fluid_density_t_m3'] = density
    result['added_displacement_t'] = _checked_positive_product(
        (density, result['requested_volume_m3']), 'added displacement') if volume else 0.0
    return result
