"""Zero-heel free-trim roll stiffness of a loaded finite polygon envelope.

The kernel reconstructs its own free equilibrium from the raw geometry, the
selected loading and the shared solver options, then differentiates the
physical restoring lever with respect to the physical roll angle while heave and
trim re-equilibrate at every probe.

Package-internal coupling (deliberate, documented, not a public interface):
geometry is prepared once through ``stability.prepare_geometry`` and every
state, free baseline and prescribed-heel probe included, is solved by the
private ``stability._solve`` engine. No second section-clipping or free-liquid
integrator exists here, and no "prepared object" argument is accepted publicly.
The waterplane-slope convention of ``stability.stability_curve`` is a different
quantity: its derivative is taken against the waterplane slope angle, not
against the physical roll angle, so it is never relabelled as this stiffness.

Small-angle roll period remains a separate claim: this module reports a static
derivative and the symmetry proof that a first-order decoupled response would
need, never a natural period of the coupled system.
"""

from __future__ import annotations

import copy
import json
import math

try:
    from . import stability
except ImportError:  # pragma: no cover - flat module layout
    import stability

METHOD_VERSION = 'free_trim_equilibrium_roll_stiffness_v1'
SYMMETRY_METHOD_VERSION = METHOD_VERSION + ':reflection-symmetry-v1'
FSC_POLICY = 'centroid_geometry_no_additional_fsc'
DEFINITION = ('dR/dphi at the zero-heel free equilibrium with heave and trim free, '
              'R = dot(cross(B - G, n), u0) in metres and phi the physical roll '
              'angle in radians; not the waterplane-slope derivative and not a '
              'dynamic validation')
ANGLE_CONVENTION = 'physical_roll_angle_from_waterplane_normal_against_fixed_baseline_axes'
STEP_BOUNDS_DEG = (0.02, 0.5)
PERTURBATION_GROUPS = (1.0, 0.5, 0.25)
BASELINE_HEEL_TOLERANCE_DEG = 1e-7
REFINEMENT_BEAM_FLOOR = 1e-5
REFINEMENT_RELATIVE = 2e-3
SIGN_RESOLUTION_BEAM_FLOOR = 1e-6
# A scale-aware coordinate tolerance: the equilibrium draft is found by floating
# point bisection, so a mathematically coincident boundary edge misses an exact
# equality test by a few ulps. The tolerance stays far below any physical
# clearance and never relaxes the solver residuals themselves.
CONTACT_RELATIVE_TOLERANCE = 1e-9
MINIMUM_COORDINATE_TOLERANCE = 1e-12


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite real number')
    return float(value)


def _finite(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _diagnostic(code, message, blocking=False):
    return dict(code=code, message=message, path='$.small_angle_stability',
                severity='error' if blocking else 'warning', blocking=blocking)


def _dot(a, b):
    return math.fsum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _validity(status):
    complete = status == 'completed'
    return dict(complete=complete, model_applicable=complete, numerical_convergence=complete,
                historical_validated=None, safe=None)


def _result(status, reason, **fields):
    result = dict(status=status, reason=reason, method_version=METHOD_VERSION,
                  definition=DEFINITION, equilibrium_gm_m=None, restoring_sign='unavailable',
                  refinement_delta_m=None, refinement_passed=False, sign_resolution_m=None,
                  step_deg=fields.pop('step_deg', None), validity=_validity(status),
                  diagnostics=fields.pop('diagnostics', []) or [], fsc_policy=FSC_POLICY,
                  input_fingerprint=fields.pop('input_fingerprint', None),
                  angle_convention=ANGLE_CONVENTION,
                  units=dict(length='m', angle='rad', mass='t', density='t/m3'),
                  assumptions=['static derivative with heave and trim re-equilibrated at '
                               'each probe', 'moving-liquid centroids recomputed per attitude; '
                               'no additional free-surface correction is applied',
                               'no added inertia, damping or coupled dynamics; perturbation '
                               'refinement is not geometric convergence evidence'])
    result.update(fields)
    json.dumps(result, allow_nan=False)
    return result


def _unavailable(reason, *, state=None, step_deg=None, diagnostics=None, prepared=None,
                 input_fingerprint=None, geometry=None, **fields):
    supplied = []
    if isinstance(state, dict) and isinstance(state.get('diagnostics'), list):
        supplied = [copy.deepcopy(d) for d in state['diagnostics']
                    if isinstance(d, dict) and d.get('blocking')]
    fingerprint = input_fingerprint
    if fingerprint is None and isinstance(state, dict):
        fingerprint = state.get('input_fingerprint')
    if geometry is None and prepared is not None:
        geometry = prepared[3]
    return _result('unavailable', reason, step_deg=step_deg, input_fingerprint=fingerprint,
                   geometry=copy.deepcopy(geometry) if geometry is not None else None,
                   diagnostics=supplied + list(diagnostics or []) + [_diagnostic(
                       'stability.small_angle_unavailable', reason, True)],
                   **fields)


def _base_equilibrium(solved):
    """Controlled subset of one solved state: attitude, residuals and axes."""
    return dict(mode=solved['mode'], converged=True, trim_deg=solved['trim_deg'],
                heel_deg=solved['heel_deg'], p=solved['p'], q=solved['q'],
                waterline_d_m=solved['waterline_d_m'],
                waterline_above_keel_m=solved['waterline_above_keel_m'],
                volume_m3=solved['volume_m3'], target_volume_m3=solved['target_volume_m3'],
                waterplane_area_m2=solved['waterplane_area_m2'],
                buoyancy_centre_m=list(solved['buoyancy_centre_m']),
                buoyancy_centre_keel_m=list(solved['buoyancy_centre_keel_m']),
                effective_cg_m=list(solved['effective_loading']['cg_m']),
                effective_mass_t=solved['effective_loading']['total_mass_t'],
                residuals=dict(scaled=dict(solved['residuals']['scaled']),
                               raw=dict(solved['residuals']['raw']),
                               tolerance=solved['residuals']['tolerance']),
                axes={k: list(v) for k, v in solved['axes'].items()},
                liquids=[dict(tank_id=item.get('tank_id'), volume_m3=item.get('volume_m3'),
                              centroid_m=item.get('centroid_m'),
                              fsc_policy=item.get('fsc_policy'))
                         for item in solved.get('liquids', [])],
                solver=dict(method=solved['solver']['method'],
                            iterations=solved['solver']['iterations'],
                            evaluations=solved['solver']['evaluations']))


def _coordinate_tolerance(scales):
    return max(CONTACT_RELATIVE_TOLERANCE * max(scales), MINIMUM_COORDINATE_TOLERANCE)


def _plane_state(prepared, solved, tolerance):
    """Classify one solved plane against the prepared envelope.

    Returns (partial_immersion, local_boundary_contact, margin_m). Global partial
    immersion alone is not enough: a section edge lying on its own waterplane
    makes the geometric intersection a one-sided limit, not a derivative.
    """
    hull, vertices, _, _ = prepared
    p, q, d = solved['p'], solved['q'], solved['waterline_d_m']
    supports = [z - p * x - q * y for x, y, z in vertices]
    low, high = min(supports), max(supports)
    partial = low < d < high
    contact = False
    for x, poly in hull.stations:
        intercept = d + p * x
        for (y0, z0), (y1, z1) in zip(poly, poly[1:] + poly[:1]):
            if (y0, z0) == (y1, z1):
                continue
            if (abs(z0 - q * y0 - intercept) <= tolerance
                    and abs(z1 - q * y1 - intercept) <= tolerance):
                contact = True
                break
        if contact:
            break
    return partial, contact, min(d - low, high - d)


def _three_point_derivative(left_span, right_span, arm_left, arm_zero, arm_right):
    """Central three-point derivative at phi = 0 on a nonuniform grid."""
    span = left_span + right_span
    return (arm_zero * (right_span - left_span) / (left_span * right_span)
            - arm_left * right_span / (left_span * span)
            + arm_right * left_span / (right_span * span))


def analyze(hull, loading_state, options=None, *, step_deg=0.2):
    """Free-trim equilibrium roll stiffness near zero heel.

    Args:
        hull: Materialized canonical geometry or a legacy stationed hull.
        loading_state: Complete resolved base mass/CG, before additional liquids.
        options: Density, angle bounds, iteration limit, initial attitude and
            liquid loads of the shared equilibrium solver. A non-null
            ``heel_deg`` is rejected: a prescribed attitude does not prove a
            free transverse equilibrium. ``target_trim_deg`` is a separate study
            option and never applies an external trim moment here.
        step_deg: Finite nonboolean probe step in degrees, 0.02 to 0.5; it
            controls the three symmetric probe groups step, step/2 and step/4.

    Returns:
        (dict): Controlled result with ``status``, ``reason``, the measured
            ``equilibrium_gm_m`` or null plus diagnostics, never a fabricated
            default and never a historical or safety claim.
    """
    if options is not None and not isinstance(options, dict):
        raise ValueError('options must be an object')
    step = _number(step_deg, 'step_deg')
    if not STEP_BOUNDS_DEG[0] <= step <= STEP_BOUNDS_DEG[1]:
        raise ValueError(f'step_deg must lie within {STEP_BOUNDS_DEG} degrees')
    resolved = copy.deepcopy(options) if options is not None else {}
    if resolved.get('heel_deg') is not None:
        return _unavailable('options.heel_deg prescribes the attitude; a prescribed heel is '
                            'not a free transverse equilibrium', state=loading_state, step_deg=step)
    state = loading_state if isinstance(loading_state, dict) else None
    fingerprint = state.get('input_fingerprint') if state is not None else None
    try:
        prepared = stability.prepare_geometry(hull, resolved)
    except (ValueError, TypeError, KeyError, OverflowError, ZeroDivisionError) as error:
        return _unavailable(f'geometry is unusable: {error}', state=loading_state, step_deg=step)
    scales = prepared[2]
    tolerance = _coordinate_tolerance(scales)
    base_beam = scales[1]

    def solve(options_for_state):
        # The private shared engine is reused on one prepared geometry; no second
        # integrator is created here.
        return stability._solve(prepared, loading_state, options_for_state)

    try:
        baseline = solve(resolved)
    except (ValueError, TypeError, KeyError, OverflowError, ZeroDivisionError) as error:
        return _unavailable(f'free baseline equilibrium failed: {error}', state=loading_state,
                            step_deg=step, prepared=prepared)
    if not baseline.get('converged'):
        reason = 'free baseline equilibrium did not converge'
        return _unavailable(reason, state=loading_state, step_deg=step, prepared=prepared,
                            diagnostics=[_diagnostic('stability.small_angle_baseline_failed', reason,
                                                    True)])
    if baseline.get('mode') != 'free':
        return _unavailable('free baseline equilibrium must be solved with a free heel',
                            state=loading_state, step_deg=step, prepared=prepared)
    residuals = baseline.get('residuals', {}).get('scaled', {})
    tolerance_limit = baseline.get('residuals', {}).get('tolerance', stability.RESIDUAL_TOLERANCE)
    if len(residuals) != 3 or any(not _finite(v) or abs(v) > tolerance_limit
                                  for v in residuals.values()):
        return _unavailable('free baseline equilibrium did not satisfy all three residuals',
                            state=loading_state, step_deg=step, prepared=prepared)
    if abs(baseline['heel_deg']) > BASELINE_HEEL_TOLERANCE_DEG:
        return _unavailable('free baseline carries a nonzero equilibrium heel',
                            state=loading_state, step_deg=step, prepared=prepared)

    partial, contact, margin = _plane_state(prepared, baseline, tolerance)
    if not partial:
        return _unavailable('free baseline plane is not partially immersed inside the sealed '
                            'envelope', state=loading_state, step_deg=step, prepared=prepared)
    if contact:
        return _unavailable('a local section boundary edge coincides with the baseline waterplane; '
                            'the geometric intersection is not a one-sided derivative',
                            state=loading_state, step_deg=step, prepared=prepared)

    axes = baseline['axes']
    u0, v0, n0 = tuple(axes['u']), tuple(axes['v']), tuple(axes['n'])

    def lever(solved):
        normal = tuple(solved['axes']['n'])
        delta = [b - g for b, g in zip(solved['buoyancy_centre_m'],
                                       solved['effective_loading']['cg_m'])]
        phi = math.atan2(-_dot(normal, v0), _dot(normal, n0))
        return phi, _dot(_cross(delta, normal), u0)

    phi0, arm0 = lever(baseline)
    if abs(phi0) > 1e-12:
        return _unavailable('baseline restoring lever is not evaluated at phi = 0',
                            state=loading_state, step_deg=step, prepared=prepared)

    groups = []
    for factor in PERTURBATION_GROUPS:
        probe_step = step * factor
        arms = {}
        for sign in (-1, 1):
            probe_options = dict(resolved, heel_deg=sign * probe_step,
                                 initial=dict(trim_deg=baseline['trim_deg'], heel_deg=0.0))
            try:
                probe = solve(probe_options)
            except (ValueError, TypeError, KeyError, OverflowError,
                    ZeroDivisionError) as error:
                return _unavailable(f'heel probe at {sign * probe_step} deg failed: {error}',
                                    state=loading_state, step_deg=step, prepared=prepared)
            if not probe.get('converged') or probe.get('mode') != 'prescribed_heel':
                return _unavailable(f'heel probe at {sign * probe_step} deg did not converge',
                                    state=loading_state, step_deg=step, prepared=prepared)
            probe_partial, probe_contact, probe_margin = _plane_state(prepared, probe, tolerance)
            if not probe_partial:
                return _unavailable(f'heel probe at {sign * probe_step} deg leaves the partially '
                                    'immersed envelope', state=loading_state, step_deg=step,
                                    prepared=prepared)
            if probe_contact:
                return _unavailable(f'a local section boundary edge coincides with the waterplane '
                                    f'at the {sign * probe_step} deg probe',
                                    state=loading_state, step_deg=step, prepared=prepared)
            phi, arm = lever(probe)
            arms[sign] = (phi, arm, probe)
        groups.append(dict(factor=factor, step_deg=probe_step,
                           phi_rad=[arms[-1][0], arms[1][0]],
                           restoring_arm_m=[arms[-1][1], arms[1][1]],
                           trim_deg=[arms[-1][2]['trim_deg'], arms[1][2]['trim_deg']],
                           probe_trim_residuals=[arms[-1][2]['residuals']['scaled']['longitudinal'],
                                                 arms[1][2]['residuals']['scaled']['longitudinal']],
                           probe_heel_residuals=[arms[-1][2]['residuals']['scaled']['volume'],
                                                 arms[1][2]['residuals']['scaled']['volume']],
                           envelope_margin_m=[_plane_state(prepared, arms[-1][2], tolerance)[2],
                                              _plane_state(prepared, arms[1][2], tolerance)[2]]))

    for group in groups:
        group['derivative_m'] = _three_point_derivative(
            -group['phi_rad'][0], group['phi_rad'][1], group['restoring_arm_m'][0], arm0,
            group['restoring_arm_m'][1])
    finest, medium, coarsest = groups[-1], groups[-2], groups[0]
    refinement_delta = abs(finest['derivative_m'] - medium['derivative_m'])
    coarsest['difference_to_next_finer_m'] = abs(coarsest['derivative_m'] - medium['derivative_m'])
    medium['difference_to_next_finer_m'] = refinement_delta
    finest['difference_to_next_finer_m'] = None
    stiffness = finest['derivative_m']
    refinement_limit = max(REFINEMENT_BEAM_FLOOR * base_beam,
                           REFINEMENT_RELATIVE * max(abs(finest['derivative_m']),
                                                     abs(medium['derivative_m'])))
    refinement_passed = refinement_delta <= refinement_limit
    sign_resolution = max(refinement_delta, SIGN_RESOLUTION_BEAM_FLOOR * base_beam)
    samples = dict(baseline=dict(phi_rad=0.0, restoring_arm_m=arm0, trim_deg=baseline['trim_deg'],
                                 volume_m3=baseline['volume_m3'],
                                 residuals_scaled=dict(baseline['residuals']['scaled']),
                                 envelope_margin_m=margin,
                                 liquids=[dict(tank_id=item.get('tank_id'),
                                               volume_m3=item.get('volume_m3'),
                                               centroid_m=item.get('centroid_m'),
                                               fsc_policy=item.get('fsc_policy'))
                                          for item in baseline.get('liquids', [])]),
                    groups=groups)
    common = dict(step_deg=step, input_fingerprint=fingerprint, geometry=copy.deepcopy(prepared[3]),
                  base_equilibrium=_base_equilibrium(baseline), samples=samples,
                  axes={k: list(v) for k, v in axes.items()},
                  refinement_delta_m=refinement_delta, refinement_tolerance_m=refinement_limit,
                  refinement_passed=refinement_passed, sign_resolution_m=sign_resolution,
                  base_beam_m=base_beam, contact_tolerance_m=tolerance)
    if not refinement_passed:
        # Report the refusal with the measured samples instead of a fabricated
        # number; the shared fields are forwarded without duplicating identity.
        fields = {key: value for key, value in common.items()
                  if key not in ('step_deg', 'input_fingerprint', 'geometry')}
        return _unavailable('perturbation refinement did not meet the pinned tolerance between '
                            'the two finest probe groups', state=loading_state, step_deg=step,
                            prepared=prepared, restoring_sign='unresolved', **fields)
    resolved_sign = 'positive' if stiffness > sign_resolution else (
        'negative' if stiffness < -sign_resolution else 'unresolved')
    return _result('completed', None, equilibrium_gm_m=stiffness, restoring_sign=resolved_sign,
                   **common)


def _near(a, b, tolerance):
    return abs(a[0] - b[0]) <= tolerance and abs(a[1] - b[1]) <= tolerance


def _reflects_onto_itself(poly, tolerance):
    """True when the reflected boundary is the same polygon, start and winding aside.

    A vertex multiset is not enough: a simple concave section can contain the
    mirror of every vertex while its boundary runs in a different order, which
    makes the immersed area and its centroid asymmetric. Only an invariance of
    the cyclic edge sequence proves the section is mirror symmetric.
    """
    count = len(poly)
    if count < 3:
        return False
    mirrored = [(-y, z) for y, z in poly]
    for direction in (1, -1):
        for start in range(count):
            if not _near(poly[start], mirrored[0], tolerance):
                continue
            index = start
            for target in mirrored:
                if not _near(poly[index % count], target, tolerance):
                    break
                index += direction
            else:
                return True
    return False


def scalar_roll_eligibility(hull, loading_state, options=None, *, equilibrium=None):
    """Prove the reflection symmetry a small-angle roll estimate needs.

    A first-order heave and trim response to a small roll angle is an even
    function of that angle only when the modelled body maps onto itself under
    y -> -y. A zero total TCG is not such a proof, and mirrored off-axis weight
    pairs or mirrored tank pairs are deliberately not supported here: this
    bounded iteration only admits items and tanks that lie on the centre plane.
    The rigid side of the proof is also a completeness claim: every positive
    rigid mass must be a known centred item, and those items must account for
    the selected base mass, so an absent, empty or partly unknown ledger stays
    unproved instead of counting as zero.

    Returns:
        (dict): ``status``, ``symmetry_proved`` and the explicit reasons, with
            the checked items and tolerances, so the caller can report the
            missing basis instead of silently reusing an inertia coefficient.
            When the coordinator supplies its selected equilibrium, baseline
            waterplane applicability is classified separately from symmetry.
    """
    reasons = []
    checked = dict(sections=0, items=0, tanks=0)
    if options is not None and not isinstance(options, dict):
        return dict(method_version=SYMMETRY_METHOD_VERSION, status='unavailable',
                    symmetry_proved=False, reasons=['options must be an object'], checked=checked)
    resolved = copy.deepcopy(options) if options is not None else {}
    state = loading_state if isinstance(loading_state, dict) else {}
    try:
        prepared = stability.prepare_geometry(hull, resolved)
    except (ValueError, TypeError, KeyError, OverflowError, ZeroDivisionError) as error:
        return dict(method_version=SYMMETRY_METHOD_VERSION, status='unavailable',
                    symmetry_proved=False, reasons=[f'geometry is unusable: {error}'],
                    checked=checked)
    tolerance = _coordinate_tolerance(prepared[2])
    baseline = dict(partial=None, contact=None,
                    reason='a converged selected equilibrium is required')
    baseline_applicable = None
    if isinstance(equilibrium, dict) and equilibrium.get('converged') is True:
        try:
            partial, contact, margin = _plane_state(prepared, equilibrium, tolerance)
            baseline = dict(partial=partial, contact=contact, envelope_margin_m=margin,
                            reason=('local waterplane contact prevents a scalar roll period'
                                    if contact else 'selected plane is not partially immersed'
                                    if not partial else None))
            baseline_applicable = partial and not contact
        except (ValueError, TypeError, KeyError, OverflowError, ZeroDivisionError) as error:
            baseline['reason'] = f'selected equilibrium plane is unusable: {error}'
    hull_object = prepared[0]
    for x, poly in hull_object.stations:
        checked['sections'] += 1
        if not _reflects_onto_itself(poly, tolerance):
            reasons.append(f'section at x = {x} m is not symmetric under y -> -y')
            break
    if state.get('complete_mass') is not True:
        reasons.append('the selected loading does not assert complete rigid mass')
    if state.get('complete_cg') is not True:
        reasons.append('the selected loading does not assert a complete three-axis CG')
    values = state.get('values')
    base_mass = values.get('total_mass_t') if isinstance(values, dict) else None
    if not _finite(base_mass) or base_mass <= 0:
        reasons.append('the selected rigid base mass is unknown')
        base_mass = None
    items = state.get('effective_items')
    if not isinstance(items, list):
        reasons.append('loading effective_items are unknown')
        items = []
    known_mass = 0.0
    for item in items:
        if not isinstance(item, dict):
            reasons.append('loading effective_items contain a malformed entry')
            continue
        mass = item.get('mass_t')
        if not _finite(mass):
            reasons.append(f"rigid item {item.get('id')!r} has an unknown mass; it cannot be "
                           'skipped as zero')
            continue
        if mass < 0:
            reasons.append(f"rigid item {item.get('id')!r} has a negative mass")
            continue
        if mass == 0:
            continue
        known_mass += mass
        checked['items'] += 1
        offset = item.get('y_m')
        if not _finite(offset):
            reasons.append(f"positive mass item {item.get('id')!r} has an unknown transverse "
                           'position')
        elif abs(offset) > tolerance:
            reasons.append(f"positive mass item {item.get('id')!r} sits off the centre plane "
                           f'at y = {offset} m')
    if base_mass is not None and (checked['items'] == 0
                                  or not math.isclose(known_mass, base_mass, rel_tol=1e-6,
                                                      abs_tol=0.0)):
        reasons.append(f'known positive rigid items account for {known_mass} t of the selected '
                       f'{base_mass} t base mass')
    liquids = resolved.get('liquid_loads', [])
    if not isinstance(liquids, list):
        reasons.append('liquid loads are unknown')
        liquids = []
    for liquid in liquids:
        if not isinstance(liquid, dict) or not isinstance(liquid.get('tank'), dict):
            reasons.append('a liquid tank definition is malformed')
            continue
        volume = liquid.get('volume_m3')
        density = liquid.get('fluid_density_t_m3')
        if not _finite(volume) or not _finite(density) or volume <= 0 or density <= 0:
            continue
        checked['tanks'] += 1
        offset = liquid['tank'].get('y_m')
        if not _finite(offset):
            reasons.append(f"moving tank {liquid['tank'].get('id')!r} has an unknown transverse "
                           'centre')
        elif abs(offset) > tolerance:
            reasons.append(f"moving tank {liquid['tank'].get('id')!r} sits off the centre plane "
                           f'at y = {offset} m')
    return dict(method_version=SYMMETRY_METHOD_VERSION,
                status='completed' if not reasons else 'unavailable',
                symmetry_proved=not reasons, reasons=reasons, checked=checked,
                baseline_applicable=baseline_applicable, baseline_plane=baseline,
                tolerance_m=tolerance,
                definition='every hull section reflects onto itself under y -> -y and every '
                           'positive rigid item and nonzero moving tank lies on the centre plane',
                validity=dict(complete=not reasons, model_applicable=not reasons,
                              historical_validated=None, safe=None))
