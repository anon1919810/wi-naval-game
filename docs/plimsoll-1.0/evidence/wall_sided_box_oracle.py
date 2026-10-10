"""Independent wall-sided prism GZ integrals; this imports no Plimsoll code.

Model: a closed rectangular prism L x B x depth with keel z=0, empty and
upright, waterplane slope angle phi (q = tan(phi)) and no longitudinal trim.
The transverse section is a rectangle, so at abscissa y the submerged column
has height

    h(y) = T + y*tan(phi)

and, because the prism is prismatic and the waterplane carries no trim, every
station integrates the same section. Integrating over y in [-B/2, B/2]:

    V    = L*integral(h dy)          = L*B*T
    B_y  = L*integral(y*h dy)/V     = B^2/(12T)*tan(phi)      = BM*tan(phi)
    B_z  = L*integral(h^2/2 dy)/V    = T/2 + B^2/(24T)*tan^2(phi)
                                             = T/2 + BM*tan^2(phi)/2

The public solver measures GZ as the transverse buoyancy arm of the projected
equilibrium, (B_y + q*(B_z - G_z))/sqrt(1+q^2) with G_z = KG, hence

    GZ(phi) = (GM + BM*tan(phi)^2/2)*sin(phi),   GM = T/2 + BM - KG.

That derivation only holds while the waterplane stays between the bottom and
the top plate, so it is a statement about the sealed box and not an
extrapolation. `bounds_ok` and `require_valid_angle_deg` gate every lever and
every area on

    abs(tan(phi))*B/2 < min(T, depth-T),

and `gz_m` applies the same gate: a value outside the wedge is not a lever of
this model, and returning a smooth extrapolation there would invent an answer
the derivation never made. The boundary is a wedge limit, not a zero of the
righting lever and not an AVS.

The closed-form area under the lever in radians is

    integral_0^P GZ dphi = GM*(1 - cos P) + BM/2*(1/cos P + cos P - 2),

using integral(sin^3/cos^2) dphi = 1/cos + cos. The 1/cos P term diverges as
P approaches 90 degrees, so the closed form is only valid inside the wedge
bound above; `simpson_area_m_rad` integrates the same analytic lever purely
numerically as an independent cross-check.

These answers test the chosen box model against continuous integrals. They say
nothing about a real ship's form, coefficients of vanishing stability or any
statutory requirement.
"""
import json
import math


LENGTH_M = 40.0
BEAM_M = 10.0
DEPTH_M = 10.0
DRAFT_M = 4.0
KG_M = 3.0
RHO_T_M3 = 1.025
MASS_T = 1640.0
STATION_COUNT = 21


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite real number')
    return float(value)


def _positive(value, name):
    number = _number(value, name)
    if number <= 0.0:
        raise ValueError(f'{name} must be positive')
    return number


def bm_m(beam_m=BEAM_M, draft_m=DRAFT_M):
    """Transverse metacentric radius BM = B^2/(12T) of the wall-sided prism."""
    return _positive(beam_m, 'beam_m') ** 2 / (12.0 * _positive(draft_m, 'draft_m'))


def gm_m(beam_m=BEAM_M, draft_m=DRAFT_M, kg_m=KG_M):
    """Upright metacentric height GM = T/2 + BM - KG above the keel datum."""
    return 0.5 * _positive(draft_m, 'draft_m') \
        + bm_m(beam_m, draft_m) - _number(kg_m, 'kg_m')


def depth_headroom_m(draft_m=DRAFT_M, depth_m=DEPTH_M):
    """min(T, depth-T): the smaller vertical margin to bottom or top plate."""
    draft = _positive(draft_m, 'draft_m')
    depth = _positive(depth_m, 'depth_m')
    if not draft < depth:
        raise ValueError('the wedge requires 0 < draft < depth')
    return min(draft, depth - draft)


def _wedge_limit_deg(beam_m, draft_m, depth_m):
    """Exclusive wedge limit from tan(phi)*B/2 = min(T, depth-T)."""
    beam = _positive(beam_m, 'beam_m')
    limit = 2.0 * depth_headroom_m(draft_m, depth_m) / beam
    if limit <= 0.0:
        raise ValueError('the wedge requires a positive depth headroom')
    return math.degrees(math.atan(limit))


def bounds_ok(angle_deg, beam_m=BEAM_M, draft_m=DRAFT_M, depth_m=DEPTH_M):
    """True while abs(tan(phi))*B/2 < min(T, depth-T) keeps both corners inside.

    A non-finite or non-numeric angle is never inside the wedge, and an angle
    at or beyond 90 degrees has no finite wedge limit to compare against.
    """
    try:
        angle = _number(angle_deg, 'angle_deg')
        limit = _wedge_limit_deg(beam_m, draft_m, depth_m)
    except ValueError:
        return False
    if abs(angle) >= 90.0 or abs(angle) >= limit:
        return False
    rise = abs(math.tan(math.radians(angle))) * 0.5 * _positive(beam_m, 'beam_m')
    return rise < depth_headroom_m(draft_m, depth_m)


def maximum_angle_deg(beam_m=BEAM_M, draft_m=DRAFT_M, depth_m=DEPTH_M):
    """Exclusive wedge limit in degrees. This is a model bound, not a zero."""
    return _wedge_limit_deg(beam_m, draft_m, depth_m)


def require_valid_angle_deg(angle_deg, beam_m=BEAM_M, draft_m=DRAFT_M,
                            depth_m=DEPTH_M):
    """Return the angle in degrees, or raise ValueError outside the wedge."""
    angle = _number(angle_deg, 'angle_deg')
    if abs(angle) >= 90.0:
        raise ValueError(
            f'heel {angle} deg has no wall-sided lever; the model needs '
            f'|angle| below 90 deg')
    if not bounds_ok(angle, beam_m, draft_m, depth_m):
        raise ValueError(
            f'heel {angle} deg leaves the sealed prism: abs(tan(phi))*B/2 must '
            f'stay below min(T, depth-T) = '
            f'{depth_headroom_m(draft_m, depth_m)} m')
    return angle


def gz_m(angle_deg, beam_m=BEAM_M, draft_m=DRAFT_M, depth_m=DEPTH_M, kg_m=KG_M):
    """Analytic righting lever GZ = (GM + BM*tan(phi)^2/2)*sin(phi) in metres.

    The derivation applies only inside the declared wedge, so this function
    gates on it and raises rather than extrapolating a number the model never
    defined. Use `bounds_ok` for a non-raising validity query.
    """
    angle = math.radians(require_valid_angle_deg(angle_deg, beam_m, draft_m, depth_m))
    slope = math.tan(angle)
    return (gm_m(beam_m, draft_m, kg_m)
            + 0.5 * bm_m(beam_m, draft_m) * slope * slope) * math.sin(angle)


def exact_area_m_rad(angle_deg, beam_m=BEAM_M, draft_m=DRAFT_M, depth_m=DEPTH_M,
                     kg_m=KG_M):
    """Closed-form integral of `gz_m` from upright to `angle_deg`, in m*rad."""
    angle = math.radians(
        require_valid_angle_deg(angle_deg, beam_m, draft_m, depth_m))
    cos_angle = math.cos(angle)
    return gm_m(beam_m, draft_m, kg_m) * (1.0 - cos_angle) \
        + 0.5 * bm_m(beam_m, draft_m) * (1.0 / cos_angle + cos_angle - 2.0)


def simpson_area_m_rad(angle_deg, intervals=2000, beam_m=BEAM_M, draft_m=DRAFT_M,
                       depth_m=DEPTH_M, kg_m=KG_M):
    """Composite Simpson quadrature of the same lever; an independent check."""
    limit = require_valid_angle_deg(angle_deg, beam_m, draft_m, depth_m)
    if isinstance(intervals, bool) or not isinstance(intervals, int):
        raise ValueError('intervals must be an integer, not a float or bool')
    if intervals <= 0:
        raise ValueError('intervals must be positive')
    if intervals % 2:
        raise ValueError('Simpson needs an even interval count')
    step = math.radians(limit) / intervals
    total = gz_m(0.0, beam_m, draft_m, depth_m, kg_m) \
        + gz_m(limit, beam_m, draft_m, depth_m, kg_m)
    for index in range(1, intervals):
        total += (4.0 if index % 2 else 2.0) * \
            gz_m(math.degrees(index * step), beam_m, draft_m, depth_m, kg_m)
    return total * step / 3.0


def oracle():
    """Return the parameters, valid wedge, analytic lever and exact area."""
    lever = [{'angle_deg': angle,
              'gz_m': gz_m(angle),
              'exact_area_m_rad': exact_area_m_rad(angle)}
             for angle in (0.0, 5.0, 15.0, 30.0)]
    limit = maximum_angle_deg()
    return {
        'kind': 'continuous_analytic_wall_sided_prism_oracle_not_solver_result',
        'geometry_m': {
            'shape': 'closed rectangular prism, wall sided, flat bottom, '
                     'flat top, no bilge radius, no openings',
            'length_m': LENGTH_M, 'beam_m': BEAM_M, 'depth_m': DEPTH_M,
            'keel_z_m': 0.0, 'station_count': STATION_COUNT,
            'sections_are_rectangles': True,
        },
        'loading': {
            'draft_m': DRAFT_M, 'kg_m': KG_M, 'rho_t_m3': RHO_T_M3,
            'mass_t': MASS_T, 'cg_m': [0.0, 0.0, KG_M],
            'liquid_loads': [], 'openings': [], 'free_surface_correction': 'none',
            'displacement_t': MASS_T,
        },
        'derived': {
            'displaced_volume_m3': MASS_T / RHO_T_M3,
            'bm_m': bm_m(), 'gm_m': gm_m(),
            'initial_metacentric_height_m': gm_m(),
            'lever_at_declared_angles': lever,
            'first_zero_gz_deg': None,
            'first_zero_gz_deg_status': 'not_computed_within_this_model',
            'first_zero_gz_deg_reason':
                'the wedge boundary is a geometry limit, not a zero of the '
                'righting lever; this oracle makes no AVS or vanishing '
                'stability claim and reports no zero angle',
        },
        'valid_range': {
            'condition': 'abs(tan(phi))*B/2 < min(T, depth-T)',
            'depth_headroom_m': depth_headroom_m(),
            'limit_deg': limit, 'min_deg': -limit, 'max_deg': limit,
            'limit_meaning': 'exclusive model wedge boundary; it is neither a '
                             'zero of GZ nor an angle of vanishing stability',
            'closed_form_area_diverges_at_deg': 90.0,
        },
        'exact_area_m_rad': {
            'at_0_deg': exact_area_m_rad(0.0),
            'at_30_deg': exact_area_m_rad(30.0),
            'independent_simpson_at_30_deg': simpson_area_m_rad(30.0, 2000),
            'definition': 'integral of GZ(phi) dphi in radians, upright to the angle',
        },
        'derivation': [
            'h(y) = T + y*tan(phi) gives the submerged column height in the section.',
            'V = L*integral(h dy) = L*B*T and B_y = BM*tan(phi), '
            'B_z = T/2 + BM*tan(phi)^2/2 from the first and second column moments.',
            'GZ = (B_y + tan(phi)*(B_z - KG))/sqrt(1+tan(phi)^2) '
            '= (GM + BM*tan(phi)^2/2)*sin(phi).',
            'int GZ dphi = GM*(1-cos P) + BM/2*(1/cos P + cos P - 2) '
            'because int sin^3/cos^2 dphi = 1/cos + cos.',
        ],
        'limitations': [
            'A rectangular wall-sided prism has no bilge radius, no flare and no '
            'superstructure; real ship sections differ from this idealisation.',
            'Exact only while the waterplane stays between bottom and top plate, '
            'which is the declared wedge; gz_m raises outside it.',
            'Fixed-angle lever agreement measures solver accuracy at one attitude; '
            'the area error of a sampled curve additionally contains the sampling '
            'quadrature error and is reported as a separate metric.',
            'No AVS, downflooding or flooding claim is made in this angle range.',
            'Numerical agreement with this analytic anchor is not physical, '
            'historical or statutory validation of any ship.',
        ],
        'imports_plimsoll_code': False,
    }


if __name__ == '__main__':
    print(json.dumps(oracle(), ensure_ascii=False, indent=2, allow_nan=False))
