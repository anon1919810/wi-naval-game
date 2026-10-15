# -*- coding: utf-8 -*-
"""Independent continuous references and declared transformation laws.

This module is the mathematical half of the core-verification round two.  It
answers "what should this number be?" using closed-form integrals or an
independently tightened numerical integration written here, and it never calls
a Plimsoll production kernel.  Nothing in this file reads the repository, the
documentation tree, a personal output path or the network; the standard
library is the only import.

Why the separation matters
--------------------------
A verification case is worthless if its expected value was produced by the
code under test.  Keeping this oracle free of production imports makes that
impossible by construction, and the test module asserts the import closure of
this file.

Evidence kinds are kept apart on purpose.  An answer here is one of

* a *mathematical reference* -- a continuous integral of the declared model;
* a *transformation law* -- how a declared quantity responds to a declared
  change of scale, mirror or datum;
* a *numeric approximation* of either, with its own refinement ladder;
* a *model applicability* statement about the vented single-fluid regime; or
* *pending external experiment*, which no oracle in this file provides.

Nothing here claims a real ship, a statutory stability result or a measured
physical accuracy.  The precision limits below are the accuracy this oracle
must reach for its own arithmetic; they were fixed from design.md section 3
before any production kernel was executed.

Angle convention throughout: the single water plane ``z = p*x + q*y + d`` with
``p = tan(trim)`` and ``q = tan(heel)``; these are slope angles, not successive
Euler rotations.  Coordinates are x forward from midships, y starboard, z
above the declared keel.
"""

from __future__ import annotations

import math
import json


CASE_SCHEMA = "plimsoll-verification-case-1"
REFERENCE_SCHEMA = "plimsoll-verification-reference-1"

# Declared accuracy of these references (design.md section 3).  These budgets
# constrain this module's own arithmetic, not any production answer.
REFERENCE_PRECISION = {
    "volume_abs_m3": 1e-7,
    "geometric_abs_m": 1e-8,
    "scaled_residual_max": 1e-10,
    "event_time_abs_s": 1e-4,
}

GRAVITY_M_S2 = 9.80665
SEA_DENSITY_T_M3 = 1.025

# Independent controls and trajectories are memoised on their immutable
# numeric parameters, so a repeated reference request costs nothing and never
# derives an expected value from a mutable object.
_CONTROL_CACHE = {}
_TRAJECTORY_CACHE = {}

_SHARED_LIMITATIONS = (
    "This is an analytic or independently integrated reference for the "
    "declared idealised model; it is a mathematical reference, not a "
    "measurement.",
    "It is not physical, statutory or historical validation of any real ship "
    "and it carries no external experimental accuracy badge; external "
    "experiment remains pending with no measured input available.",
    "Real ship form, bilge radius, free-surface dynamics, compressed air, "
    "partially wetted openings, waves and structural failure are outside this "
    "model and are not repaired by agreement with these numbers.",
)

_MODEL_APPLICABILITY = {
    "vented_single_fluid": True,
    "static_sea_surface": True,
    "point_orifice_fully_submerged": True,
    "constant_discharge_coefficient": True,
    "rectangular_tanks_only": True,
    "wall_sided_hull_only": True,
    "external_experiment_measured": False,
    "note": "model applicability, numerical convergence and external "
            "validation are separate claims and are reported separately",
}


# ---------------------------------------------------------------------------
# Small numerical helpers (standard library only)
# ---------------------------------------------------------------------------

def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _positive(value, name):
    number = _number(value, name)
    if number <= 0.0:
        raise ValueError(f"{name} must be positive")
    return number


def _gauss_legendre_2(function, low, high):
    """Two-point Gauss-Legendre value; exact for polynomials up to degree 3."""
    half = 0.5 * (high - low)
    mid = 0.5 * (high + low)
    offset = half / math.sqrt(3.0)
    return half * (function(mid - offset) + function(mid + offset))


def _simpson(function, low, high, intervals=64):
    """Composite Simpson value; exact for polynomials up to degree 3."""
    if intervals % 2:
        raise ValueError("Simpson needs an even interval count")
    step = (high - low) / intervals
    terms = [function(low), function(high)]
    terms.extend((4.0 if index % 2 else 2.0) * function(low + index * step)
                 for index in range(1, intervals))
    return math.fsum(terms) * step / 3.0


def _bisect(function, low, high, tolerance=1e-15, iterations=200):
    """Plain bisection root finder; the independent equilibrium solver."""
    low_value, high_value = function(low), function(high)
    if low_value == 0.0:
        return low
    if high_value == 0.0:
        return high
    if (low_value > 0.0) == (high_value > 0.0):
        raise ValueError("independent bisection requires a sign change")
    for _ in range(iterations):
        mid = 0.5 * (low + high)
        if mid in (low, high):
            break
        value = function(mid)
        if abs(value) <= tolerance:
            return mid
        if (value > 0.0) == (low_value > 0.0):
            low, low_value = mid, value
        else:
            high, high_value = mid, value
    return 0.5 * (low + high)


def _secant(function, first, second, tolerance=1e-15, iterations=60):
    """Secant root finder with a bisection fallback, used as the fast path."""
    low, high = sorted((first, second))
    low_value, high_value = function(low), function(high)
    if low_value == 0.0:
        return low
    if high_value == 0.0:
        return high
    if (low_value > 0.0) == (high_value > 0.0):
        return _bisect(function, low, high, tolerance)
    for _ in range(iterations):
        denominator = high_value - low_value
        candidate = (high - high_value * (high - low) / denominator
                     if denominator != 0.0 else 0.5 * (low + high))
        if not low < candidate < high:
            candidate = 0.5 * (low + high)
        value = function(candidate)
        if abs(value) <= tolerance or (high - low) <= tolerance:
            return candidate
        if (value > 0.0) == (low_value > 0.0):
            low, low_value = candidate, value
        else:
            high, high_value = candidate, value
    return 0.5 * (low + high)


def _rk4(rhs, start_state, start_time, stop_time, step):
    """Classical RK4 of an autonomous right-hand side.

    Returns ``(times, values)`` with ``times[0] == start_time`` and
    ``times[-1] == stop_time`` exactly; the final step is shortened so a
    declared sample instant is hit without interpolation error.
    """
    if stop_time <= start_time:
        return [float(start_time)], [float(start_state)]
    span = stop_time - start_time
    count = max(1, int(math.ceil(span / step - 1e-12)))
    actual = span / count
    times = [float(start_time)]
    values = [float(start_state)]
    state = float(start_state)
    time = float(start_time)
    for _ in range(count):
        k1 = rhs(state)
        k2 = rhs(state + 0.5 * actual * k1)
        k3 = rhs(state + 0.5 * actual * k2)
        k4 = rhs(state + actual * k3)
        state += actual * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        time += actual
        times.append(time)
        values.append(state)
    times[-1] = float(stop_time)
    return times, values


def _quantities(pairs):
    """Build the strict-JSON ``{name: {value, unit}}`` table."""
    return {name: {"value": value, "unit": unit}
            for name, (value, unit) in pairs.items()}


def _control(name, measured, unit, budget, description):
    return {
        "name": name,
        "measured_difference": float(measured),
        "unit": unit,
        "budget": float(budget),
        "within_budget": bool(abs(measured) <= budget),
        "description": description,
    }


def _format_time(value):
    value = float(value)
    if value == int(value):
        return f"{int(value)}.0"
    return f"{value:.9f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Reference 1 -- continuous wall-sided box integrals
# ---------------------------------------------------------------------------

def wall_sided_box_column_moments(length_m, beam_m, p, q, draft_m):
    """Analytic submerged volume and buoyancy centre of a sloped-plane box.

    The submerged column height over the plan is ``h = T + p*x + q*y`` and is
    never clipped by the bottom or top plate, so

        V  = L*B*T
        Bx = p*L^2/(12T)
        By = q*B^2/(12T)
        Bz = T/2 + (p^2 L^2 + q^2 B^2)/(24T)
    """
    volume = length_m * beam_m * draft_m
    centre_x = p * length_m ** 2 / (12.0 * draft_m)
    centre_y = q * beam_m ** 2 / (12.0 * draft_m)
    centre_z = 0.5 * draft_m + (p * p * length_m ** 2
                                + q * q * beam_m ** 2) / (24.0 * draft_m)
    return volume, (centre_x, centre_y, centre_z)


def wall_sided_box_quadrature(length_m, beam_m, p, q, draft_m):
    """Independent tensor Gauss-Legendre evaluation of the same integrals.

    This is a different algorithm from the closed-form polynomial moments: it
    evaluates the integrands themselves on a two-point grid in ``x`` and ``y``.
    Because the integrands are at most quadratic in each variable the rule is
    exact in exact arithmetic, so the observed difference is pure roundoff.
    """
    low_x, high_x = -0.5 * length_m, 0.5 * length_m
    low_y, high_y = -0.5 * beam_m, 0.5 * beam_m

    def height(x, y):
        return draft_m + p * x + q * y

    def integrate(weight):
        return _gauss_legendre_2(
            lambda x: _gauss_legendre_2(
                lambda y: weight(x, y, height(x, y)), low_y, high_y),
            low_x, high_x)

    volume = integrate(lambda _x, _y, h: h)
    first_x = integrate(lambda x, _y, h: x * h)
    first_y = integrate(lambda _x, y, h: y * h)
    first_z = integrate(lambda _x, _y, h: 0.5 * h * h)
    return volume, (first_x / volume, first_y / volume, first_z / volume)


def wall_sided_box_free_heel(length_m, beam_m, depth_m, draft_m, p, rho, kg,
                            offset_y_m):
    """Free heel of a box carrying an asymmetric transverse load.

    Unlike :func:`wall_sided_box_column_moments`, which evaluates a declared
    slope, here the heel is *solved* from

        (By - Gy) + q (Bz - Gz) = 0

    with ``Gy`` carrying the declared transverse load offset.  An asymmetric
    load therefore produces a nonzero ``q`` and a nonzero restoring arm at that
    heel, which is exactly what a mirror test needs.  Reflecting the load
    ``y -> -y`` maps ``q -> -q`` and negates ``By``, ``Gy`` and ``GZ`` while
    leaving ``V``, ``M``, ``Bx`` and ``Bz`` identical, so the mirrored case
    follows from the declared sign law rather than from re-running a solver.
    """
    length = _positive(length_m, "length_m")
    beam = _positive(beam_m, "beam_m")
    depth = _positive(depth_m, "depth_m")
    draft = _positive(draft_m, "draft_m")
    p = _number(p, "p")
    rho = _positive(rho, "rho_t_m3")
    kg = _number(kg, "kg_m")
    offset_y = _number(offset_y_m, "cg_offset_y_m")
    if not draft < depth:
        raise ValueError("the sealed prism requires 0 < draft < depth")
    headroom = min(draft, depth - draft)

    def residual(heel_slope):
        centre_y = heel_slope * beam ** 2 / (12.0 * draft)
        centre_z = 0.5 * draft + (p * p * length ** 2
                                  + heel_slope ** 2 * beam ** 2) \
            / (24.0 * draft)
        return centre_y + heel_slope * (centre_z - kg) - offset_y

    slope = _bisect(residual, -0.6, 0.6)
    if abs(slope) * 0.5 * beam >= headroom:
        raise ValueError("the solved heel leaves the sealed prism")

    volume = length * beam * draft
    centre_x = p * length ** 2 / (12.0 * draft)
    centre_y = slope * beam ** 2 / (12.0 * draft)
    centre_z = 0.5 * draft + (p * p * length ** 2
                              + slope * slope * beam ** 2) / (24.0 * draft)
    cg = (centre_x + p * (centre_z - kg), offset_y, kg)
    gz = (centre_y - cg[1] + slope * (centre_z - cg[2])) \
        / math.sqrt(1.0 + slope * slope)
    quad_volume, quad_centre = wall_sided_box_quadrature(
        length, beam, p, slope, draft)

    controls = [_control(
        "volume_vs_gauss_legendre", abs(quad_volume - volume), "m3",
        REFERENCE_PRECISION["volume_abs_m3"],
        "tensor two-point Gauss-Legendre over the plan at the solved heel, "
        "against the closed-form column moments")]
    for index, axis in enumerate("xyz"):
        controls.append(_control(
            f"buoyancy_{axis}_vs_gauss_legendre",
            abs(quad_centre[index] - (centre_x, centre_y, centre_z)[index]),
            "m", REFERENCE_PRECISION["geometric_abs_m"],
            "independent quadrature of the first moment along this axis"))

    return {
        "oracle": "continuous-wall-sided-box-free-heel-1",
        "method": "closed-form box integrals with a solved transverse heel",
        "derivation": [
            "With a prescribed slope the buoyancy centre is "
            "By = q B^2/(12T) and Bz = T/2 + (p^2 L^2 + q^2 B^2)/(24T).",
            "The free equilibrium solves (By - Gy) + q(Bz - Gz) = 0 for q with "
            "Gy carrying the declared transverse load offset.",
            "Reflecting the load y -> -y maps q -> -q and negates By, Gy and GZ "
            "while leaving V, M, Bx and Bz identical.",
        ],
        "quantities": _quantities({
            "volume_m3": (volume, "m3"),
            "mass_t": (rho * volume, "t"),
            "draft_m": (draft, "m"),
            "p": (p, "-"),
            "q": (slope, "-"),
            "heel_deg": (math.degrees(math.atan(slope)), "deg"),
            "trim_deg": (math.degrees(math.atan(p)), "deg"),
            "buoyancy_centre_m": ([centre_x, centre_y, centre_z], "m"),
            "cg_m": ([cg[0], cg[1], cg[2]], "m"),
            "bm_m": (beam ** 2 / (12.0 * draft), "m"),
            "gm_m": (0.5 * draft + beam ** 2 / (12.0 * draft) - kg, "m"),
            "gz_m": (gz, "m"),
            "cg_offset_y_m": (offset_y, "m"),
        }),
        "relations": {
            "model_applicability": dict(_MODEL_APPLICABILITY),
            "ceiling_or_bottom_clipped": False,
            "depth_headroom_m": headroom,
            "wedge_used_m": abs(slope) * 0.5 * beam,
        },
        "evidence": {"controls": controls,
                     "notes": ["no production solver participates"]},
    }


def _box_reference(spec):
    """Full independent reference for one wall-sided box state."""
    length = _positive(spec["length_m"], "length_m")
    beam = _positive(spec["beam_m"], "beam_m")
    depth = _positive(spec["depth_m"], "depth_m")
    draft = _positive(spec["draft_m"], "draft_m")
    p = _number(spec["p"], "p")
    q = _number(spec["q"], "q")
    rho = _positive(spec["rho_t_m3"], "rho_t_m3")
    absolute_cg_z = _number(spec["cg_z_m"], "cg_z_m")
    keel_offset = _number(spec.get("keel_offset_m", 0.0), "keel_offset_m")
    cg_z = absolute_cg_z - keel_offset

    if not draft < depth:
        raise ValueError("the sealed prism requires 0 < draft < depth")
    headroom = min(draft, depth - draft)
    wedge_used = abs(p) * 0.5 * length + abs(q) * 0.5 * beam
    if wedge_used >= headroom:
        raise ValueError("the declared slope leaves the sealed prism")

    volume, centre = wall_sided_box_column_moments(length, beam, p, q, draft)
    quad_volume, quad_centre = wall_sided_box_quadrature(length, beam, p, q, draft)

    mass = rho * volume
    dz = centre[2] - cg_z
    cg = (centre[0] + p * dz, centre[1] + q * dz, cg_z)
    bm = beam ** 2 / (12.0 * draft)
    gm = 0.5 * draft + bm - cg_z
    gz = (centre[1] - cg[1] + q * (centre[2] - cg[2])) / math.sqrt(1.0 + q * q)
    slope_norm = math.sqrt(1.0 + p * p + q * q)
    keel_centre = list(centre)
    absolute_centre = [centre[0], centre[1], centre[2] + keel_offset]

    controls = [_control(
        "volume_vs_gauss_legendre", abs(quad_volume - volume), "m3",
        REFERENCE_PRECISION["volume_abs_m3"],
        "tensor two-point Gauss-Legendre over the plan against the closed-form "
        "column moments")]
    for index, axis in enumerate("xyz"):
        controls.append(_control(
            f"buoyancy_{axis}_vs_gauss_legendre",
            abs(quad_centre[index] - centre[index]), "m",
            REFERENCE_PRECISION["geometric_abs_m"],
            "independent quadrature of the first moment along this axis"))

    return {
        "oracle": "continuous-wall-sided-box-integral-2",
        "method": "closed-form column moments with a two-point Gauss-Legendre control",
        "derivation": [
            "h(x,y) = T + p x + q y is the submerged column height over the "
            "plan and is never clipped by the bottom or top plate.",
            "V = L*B*T, Bx = p L^2/(12T), By = q B^2/(12T) and "
            "Bz = T/2 + (p^2 L^2 + q^2 B^2)/(24T) follow from integrating h, "
            "x h and h^2/2 over the plan; the odd cross terms vanish.",
            "A free equilibrium at a prescribed slope needs "
            "Gx = Bx + p(Bz - Gz) and Gy = By + q(Bz - Gz).",
            "GZ = (By - Gy + q(Bz - Gz))/sqrt(1+q^2), which vanishes at that "
            "constructed equilibrium.",
            "The geometric waterplane is the inclined plane itself and so "
            "carries the factor sqrt(1+p^2+q^2); the projected waterplane "
            "L*B does not. Both are reported because they are different "
            "quantities, not competing answers.",
        ],
        "quantities": _quantities({
            "volume_m3": (volume, "m3"),
            "mass_t": (mass, "t"),
            "draft_m": (draft, "m"),
            "p": (p, "-"),
            "q": (q, "-"),
            "slope_normal_scale": (slope_norm, "-"),
            "heel_deg": (math.degrees(math.atan(q)), "deg"),
            "trim_deg": (math.degrees(math.atan(p)), "deg"),
            "buoyancy_centre_m": (absolute_centre, "m"),
            "buoyancy_centre_keel_m": (keel_centre, "m"),
            "cg_m": ([cg[0], cg[1], cg[2] + keel_offset], "m"),
            "cg_keel_m": ([cg[0], cg[1], cg[2]], "m"),
            "cg_z_m": (cg[2] + keel_offset, "m"),
            "kg_m": (cg[2], "m"),
            "bm_m": (bm, "m"),
            "gm_m": (gm, "m"),
            "gz_m": (gz, "m"),
            "waterplane_projected_area_m2": (length * beam, "m2"),
            "waterplane_geometric_area_m2": (length * beam * slope_norm, "m2"),
            "waterplane_inertia_m4": ([length * beam ** 3 / 12.0,
                                       beam * length ** 3 / 12.0], "m4"),
            "keel_offset_m": (keel_offset, "m"),
            "waterline_d_m": (draft + keel_offset, "m"),
        }),
        "relations": {
            "model_applicability": dict(_MODEL_APPLICABILITY),
            "wedge_condition": "abs(p)*L/2 + abs(q)*B/2 < min(T, depth-T)",
            "wedge_used_m": wedge_used,
            "depth_headroom_m": headroom,
            "within_wedge": True,
            "ceiling_or_bottom_clipped": False,
            "keel_relative_z_m": cg[2],
            "absolute_z_m": cg[2] + keel_offset,
        },
        "evidence": {"controls": controls,
                     "notes": ["no production kernel participates"]},
    }


# ---------------------------------------------------------------------------
# Reference 2 -- continuous sliced ellipsoid
# ---------------------------------------------------------------------------

def _ellipsoid_cap_controls(normal, offset, semi_axes, centre_z):
    """Independent Simpson and Cartesian-polar controls of the cap integrals.

    ``x = aX, y = bY, z = c + cZ`` maps the ellipsoid onto the unit sphere and
    the plane onto ``(-pa, -qb, c) . (X,Y,Z) <= d - c``.  Along the cap axis
    ``s`` the slice area is ``pi*(1 - s^2)``, so integrating that and its
    first moment in ``s`` by Simpson is a second derivation of the volume and
    the axial first moment.  The Cartesian control integrates the first-moment
    *vector* on a polar grid; that is what numerically confirms the centroid
    lies on the cap axis, which a symmetry argument alone would not do.
    """
    key = (round(offset, 15), tuple(round(value, 15) for value in normal),
           tuple(round(value, 15) for value in semi_axes), centre_z)
    cached = _CONTROL_CACHE.get(key)
    if cached is not None:
        return cached
    if not -1.0 < offset < 1.0:
        raise ValueError("the cap axis offset must lie inside the sphere")

    norm = math.sqrt(sum(item * item for item in normal))
    axis = [item / norm for item in normal]
    seed = [0.0, 0.0, 1.0] if abs(axis[2]) < 0.9 else [1.0, 0.0, 0.0]
    raw = [axis[1] * seed[2] - axis[2] * seed[1],
           axis[2] * seed[0] - axis[0] * seed[2],
           axis[0] * seed[1] - axis[1] * seed[0]]
    scale_raw = math.sqrt(sum(item * item for item in raw))
    e1 = [item / scale_raw for item in raw]
    e2 = [axis[1] * e1[2] - axis[2] * e1[1],
          axis[2] * e1[0] - axis[0] * e1[2],
          axis[0] * e1[1] - axis[1] * e1[0]]

    def slice_area(s):
        return math.pi * (1.0 - s * s)

    volume = _simpson(slice_area, -1.0, offset)
    axial_moment = _simpson(lambda s: s * slice_area(s), -1.0, offset)

    # A tensor Gauss rule, unlike midpoint slices, integrates the axial
    # cubic first moment exactly. The azimuth rule cancels transverse first
    # moments and explicitly carries d(theta); no accuracy claim is inferred
    # from a symmetry argument alone.
    angular_steps = 32
    axial_half = (offset + 1.0) / 2.0
    axial_mid = (offset - 1.0) / 2.0
    moment = [0.0, 0.0, 0.0]
    for axial_node in (-1.0 / math.sqrt(3.0), 1.0 / math.sqrt(3.0)):
        s = axial_mid + axial_half * axial_node
        radius = math.sqrt(max(0.0, 1.0 - s * s))
        if radius == 0.0:
            continue
        radial_half = radius / 2.0
        for radial_node in (-1.0 / math.sqrt(3.0), 1.0 / math.sqrt(3.0)):
            rho = radial_half * (1.0 + radial_node)
            weight = rho * radial_half * axial_half * 2.0 * math.pi / angular_steps
            for spoke in range(angular_steps):
                angle = 2.0 * math.pi * spoke / angular_steps
                cos_a, sin_a = math.cos(angle), math.sin(angle)
                for index_axis in range(3):
                    moment[index_axis] += weight * (
                        s * axis[index_axis]
                        + rho * (e1[index_axis] * cos_a + e2[index_axis] * sin_a))
    centroid_unit = [item / volume for item in moment]
    a, b, c = semi_axes
    quad_centre = (a * centroid_unit[0], b * centroid_unit[1],
                   centre_z + c * centroid_unit[2])
    result = (volume, axial_moment / volume, quad_centre)
    _CONTROL_CACHE[key] = result
    return result


def ellipsoid_reference(semi_axes, centre_z, p, q, d, rho, kg, prescribed_gz):
    """Continuous volume and buoyancy centre of the ellipsoid under a plane."""
    a, b, c = (_positive(value, "semi_axis") for value in semi_axes)
    centre_z = _number(centre_z, "centre_z")
    p = _number(p, "p")
    q = _number(q, "q")
    d = _number(d, "d")
    rho = _positive(rho, "rho_t_m3")
    kg = _number(kg, "kg")
    prescribed_gz = _number(prescribed_gz, "prescribed_gz")

    mapped = (-p * a, -q * b, c)
    support = math.sqrt(sum(item * item for item in mapped))
    offset = (d - centre_z) / support
    polynomial = 2.0 + 3.0 * offset - offset ** 3
    centroid_unit = -3.0 * (1.0 - offset * offset) ** 2 / (4.0 * polynomial)
    volume = math.pi * a * b * c * polynomial / 3.0
    centre = (-centroid_unit * p * a * a / support,
              -centroid_unit * q * b * b / support,
              centre_z + centroid_unit * c * c / support)

    quad_volume, quad_centroid_unit, quad_centre = _ellipsoid_cap_controls(
        mapped, offset, (a, b, c), centre_z)

    mass = rho * volume
    dz = centre[2] - kg
    free_cg = (centre[0] + p * dz, centre[1] + q * dz, kg)
    factor = math.sqrt(1.0 + q * q)
    constrained_cg = (centre[0] + p * dz - p * q * prescribed_gz / factor,
                      centre[1] + q * dz - prescribed_gz * factor, kg)

    controls = [
        _control("volume_vs_cap_simpson", abs(quad_volume * a * b * c - volume),
                 "m3", REFERENCE_PRECISION["volume_abs_m3"],
                 "Simpson quadrature of the cap slice area pi*(1-s^2), exact "
                 "for the quadratic integrand, against the closed-form cubic "
                 "volume polynomial"),
        _control("axial_centroid_vs_cap_simpson",
                 abs(quad_centroid_unit - centroid_unit), "-",
                 REFERENCE_PRECISION["geometric_abs_m"] / max(1.0, abs(centroid_unit)),
                 "quadrature of the weighted slice area against the closed-form "
                 "cap centroid"),
    ]
    for index, axis in enumerate("xyz"):
        controls.append(_control(
            f"buoyancy_{axis}_vs_cartesian_polar_quadrature",
            abs(quad_centre[index] - centre[index]), "m",
            REFERENCE_PRECISION["geometric_abs_m"],
            "Cartesian polar quadrature of the first-moment vector, which "
            "confirms numerically that the centroid lies on the cap axis"))

    return {
        "oracle": "continuous-sliced-ellipsoid-3",
        "method": "mapped unit-sphere cap integrals with Simpson and polar controls",
        "derivation": [
            "x = aX, y = bY, z = c + cZ maps the ellipsoid to the unit sphere "
            "and the water plane to (-pa, -qb, c) . (X,Y,Z) <= d - c.",
            "S = |(-pa, -qb, c)| and t = (d-c)/S; the slice area along the cap "
            "axis is pi*(1 - s^2), so the unit-sphere volume is "
            "(pi/3)(2 + 3t - t^3).",
            "The weighted slice integral gives the axial centroid "
            "mu = -3(1-t^2)^2 / (4(2 + 3t - t^3)); rotational symmetry about "
            "the cap axis puts the centroid vector along (-pa, -qb, c)/S.",
            "Rescaling by (a, b, c) gives V = pi a b c (2 + 3t - t^3)/3.",
        ],
        "quantities": _quantities({
            "volume_m3": (volume, "m3"),
            "mass_t": (mass, "t"),
            "buoyancy_centre_m": ([centre[0], centre[1], centre[2]], "m"),
            "free_equilibrium_cg_m": ([free_cg[0], free_cg[1], free_cg[2]], "m"),
            "constrained_heel_cg_m": ([constrained_cg[0], constrained_cg[1],
                                       constrained_cg[2]], "m"),
            "constrained_heel_gz_m": (prescribed_gz, "m"),
            "cap_offset_t": (offset, "-"),
            "heel_deg": (math.degrees(math.atan(q)), "deg"),
            "trim_deg": (math.degrees(math.atan(p)), "deg"),
            "waterline_d_m": (d, "m"),
        }),
        "relations": {
            "model_applicability": dict(_MODEL_APPLICABILITY),
            "continuous_not_discrete": True,
            "discretisation_note": "station and section sampling are separate "
                                   "error sources and must be refined apart; "
                                   "this answer is never fitted to a mesh",
        },
        "evidence": {"controls": controls,
                     "notes": ["no production integrator participates"]},
    }


# ---------------------------------------------------------------------------
# Reference 3 -- single-tank sea-coupled box with buoyancy feedback
# ---------------------------------------------------------------------------

def _single_sea_constants(spec):
    slope = 1.0 / spec["tank_area_m2"] - 1.0 / spec["waterplane_area_m2"]
    flow = (spec["discharge_coefficient"] * spec["orifice_area_m2"]
            * math.sqrt(2.0 * spec["gravity_m_s2"]))
    head = spec["initial_draft_m"] - spec["initial_volume_m3"] / spec["tank_area_m2"]
    plateau = 2.0 * math.sqrt(head) / (slope * flow)
    return slope, flow, head, plateau


def single_sea_coupled_state(spec, time_s):
    """Piecewise reference for one vented sea-coupled tank on a floating box.

    With a symmetric box of waterplane ``Awp``, tank plan area ``S``, dry mass
    ``M_base`` and water volume ``V``:

        d = M_base/(rho*Awp) + V/Awp          (mean immersion)
        H = d - V/S                          (aperture head difference)
        a = 1/S - 1/Awp,  k = Cd*A*sqrt(2g)
        dH/dt = -a k sqrt(H)

    which integrates to ``V - V0 = (H0 - (sqrt(H0) - a k t/2)^2)/a`` until the
    finite hydraulic equilibrium at ``t_eq = 2 sqrt(H0)/(a k)``.  Past that
    instant the flow is exactly zero, so the reference is *piecewise
    constant*; continuing the pre-equilibrium square to a longer duration
    would be a different, and wrong, statement.
    """
    slope, flow, head0, plateau = _single_sea_constants(spec)
    time_s = _number(time_s, "time_s")
    driving = math.sqrt(head0) - slope * flow * time_s / 2.0
    if time_s >= plateau or driving <= 0.0:
        head = 0.0
        influx = head0 / slope
    else:
        head = driving * driving
        influx = (head0 - head) / slope
    volume = spec["initial_volume_m3"] + influx
    level = volume / spec["tank_area_m2"]
    return {
        "time_s": time_s,
        "net_sea_influx_m3": influx,
        "tank_volume_m3": volume,
        "tank_level_m": level,
        "draft_m": spec["initial_draft_m"] + influx / spec["waterplane_area_m2"],
        "head_difference_m": head,
        "aperture_head_sea_m": max(0.0, spec["initial_draft_m"]
                                  + influx / spec["waterplane_area_m2"]
                                  - spec["aperture_z_m"]),
        "aperture_head_tank_m": max(0.0, level - spec["aperture_z_m"]),
        "heel_slope_q": 0.0,
        "heel_deg": 0.0,
        "trim_deg": 0.0,
    }


def single_sea_coupled_reference(spec, sample_times):
    """Reference for the single-tank sea-coupled box, plus its error budget."""
    slope, flow, head0, plateau = _single_sea_constants(spec)
    probes = sorted({0.0, plateau / 4.0, plateau / 2.0, 0.75 * plateau})

    def closed_form_head(probe):
        if probe >= plateau:
            return 0.0
        return (math.sqrt(head0) - slope * flow * probe / 2.0) ** 2

    def integrate_head(probe, step):
        def rhs(head):
            return -slope * flow * math.sqrt(max(0.0, head))

        return _rk4(rhs, head0, 0.0, probe, step)[1][-1]

    ladder = (0.02, 0.01, 0.005)
    differences = [abs(integrate_head(probe, step) - closed_form_head(probe))
                   for step in ladder for probe in probes]
    halving = max(abs(integrate_head(probe, ladder[0])
                      - integrate_head(probe, ladder[-1])) for probe in probes)

    samples = {f"t={_format_time(value)}": single_sea_coupled_state(spec, value)
               for value in sorted(set(sample_times) | {0.0})}
    longest = max(sample_times) if sample_times else plateau
    continued = (head0 - (math.sqrt(head0) - slope * flow * longest / 2.0) ** 2) \
        / slope

    return {
        "oracle": "continuous-coupled-heave-piecewise-equilibrium-3",
        "method": "closed-form hydraulic equilibrium with an RK4 refinement control",
        "derivation": [
            "The box heaves with the added water, so d = M_base/(rho*Awp) + V/Awp.",
            "H = d - V/S, a = 1/S - 1/Awp and k = Cd*A*sqrt(2g) give "
            "dH/dt = -a k sqrt(H).",
            "Integrating gives V - V0 = (H0 - (sqrt(H0) - a k t/2)^2)/a until the "
            "finite hydraulic equilibrium at t_eq = 2 sqrt(H0)/(a k).",
            "Past t_eq the vented flow is exactly zero, so the reference is "
            "piecewise constant; the pre-equilibrium square is never extended "
            "past the equilibrium instant.",
        ],
        "quantities": _quantities({
            "plateau_time_s": (plateau, "s"),
            "plateau_net_influx_m3": (head0 / slope, "m3"),
            "initial_head_m": (head0, "m"),
            "head_differential_rate_per_m2": (slope, "1/m2"),
            "orifice_flow_factor_m5_2_s": (flow, "m^(5/2)/s"),
            "pre_equilibrium_squared_formula_at_longest_sample_m3": (
                continued, "m3"),
            "total_mass_t": (spec["base_mass_t"]
                             + spec["fluid_density_t_m3"]
                             * spec["initial_volume_m3"], "t"),
            "net_transfer_m3": (samples[f"t={_format_time(longest)}"]
                                ["net_sea_influx_m3"], "m3"),
        }),
        "samples": samples,
        "relations": {
            "model_applicability": dict(_MODEL_APPLICABILITY),
            "piecewise_constant_after_equilibrium": True,
            "equilibrium_time_rule": "t >= plateau_time_s uses the constant "
                                     "plateau volume, never the pre-equilibrium "
                                     "square",
            "heave_feedback_included": True,
            "attitude_feedback_required": False,
            "symmetric_fixture_keeps_heel_and_trim_zero": True,
            "tank_height_m": spec["tank_height_m"],
            "tank_level_bounds_m": (0.0, spec["tank_height_m"]),
            "tank_level_used_m": (
                min(item["tank_level_m"] for item in samples.values()),
                max(item["tank_level_m"] for item in samples.values())),
            "ceiling_or_bottom_clipped": False,
        },
        "evidence": {"controls": [
            _control("closed_form_head_vs_rk4", max(differences), "m",
                     REFERENCE_PRECISION["geometric_abs_m"],
                     "RK4 integration of dH/dt = -a k sqrt(H) on a 0.02, 0.01, "
                     "0.005 s ladder compared with the closed-form head"),
            _control("rk4_step_halving_head", halving, "m",
                     REFERENCE_PRECISION["geometric_abs_m"],
                     "observed difference between the coarsest and finest RK4 "
                     "head integration"),
        ], "notes": ["no production stepping participates"]},
    }


# ---------------------------------------------------------------------------
# Reference 4 -- asymmetric connected two-tank free-floating box
# ---------------------------------------------------------------------------

class TwoTankFreeFloatModel:
    """Closed-form rectangular-column model of a free-floating two-tank box.

    The hull is a wall-sided sealed box of ``length x beam x depth`` with keel
    at z = 0, a centred dry mass, and two rectangular tanks placed
    asymmetrically in ``y``.  Every mass and tank centre lies on the centre
    plane, so ``Bx = p L^2/(12T)`` and ``Gx = 0`` are identically satisfied by
    ``p = 0`` and only the heel has to be solved.

    For a tank spanning ``[ya, yb]`` with longitudinal length ``Lt`` and a
    liquid plane ``z = q y + d`` the closed-form column integrals are

        V  = Lt [ q (yb^2-ya^2)/2  +  d (yb-ya) ]
        My = Lt [ q (yb^3-ya^3)/3  +  d (yb^2-ya^2)/2 ]
        Mz = Lt [ q^2 (yb^3-ya^3)/6 + q d (yb^2-ya^2)/2 + d^2 (yb-ya)/2 ]

    Writing ``k = 1/(Lt (yb-ya))`` and ``c = (yb^2-ya^2)/(2 (yb-ya))`` gives
    ``d = k V - c q``, so every tank intercept is affine in its own volume and
    the heel follows from ``(By - Gy) + q (Bz - Gz) = 0``.

    Dividing the mass ledger by the fluid density, the transverse centre is
    ``Gy = (V_a y_a + V_b y_b)/W`` and the vertical centre is
    ``Gz = (M_dry/rho * KG + sum V_i zbar_i)/W`` where ``W = M/rho`` is the
    displaced volume, so ``draft = W/(L B)`` exactly.
    """

    def __init__(self, spec):
        self.spec = dict(spec)
        self.length = _positive(spec["hull_length_m"], "hull_length_m")
        self.beam = _positive(spec["hull_beam_m"], "hull_beam_m")
        self.depth = _positive(spec["hull_depth_m"], "hull_depth_m")
        self.dry_mass = _positive(spec["dry_mass_t"], "dry_mass_t")
        self.dry_kg = _number(spec["dry_kg_m"], "dry_kg_m")
        self.density = _positive(spec["fluid_density_t_m3"], "fluid_density_t_m3")
        self.aperture_y = _number(spec["aperture_y_m"], "aperture_y_m")
        self.aperture_z = _number(spec["aperture_z_m"], "aperture_z_m")
        self.discharge_coefficient = _positive(
            spec["discharge_coefficient"], "discharge_coefficient")
        self.orifice_area = _positive(spec["orifice_area_m2"], "orifice_area_m2")
        self.gravity = _positive(spec["gravity_m_s2"], "gravity_m_s2")

        self.tanks = []
        for tank in spec["tanks"]:
            low = _number(tank["y_low_m"], "y_low_m")
            high = _number(tank["y_high_m"], "y_high_m")
            if not high > low:
                raise ValueError("tank transverse extent must be positive")
            length_t = _positive(tank["length_m"], "tank_length_m")
            height = _positive(tank["height_m"], "tank_height_m")
            self.tanks.append({
                "name": tank["name"],
                "length": length_t,
                "low": low, "high": high,
                "bottom": _number(tank["keel_to_bottom_m"], "keel_to_bottom_m"),
                "height": height,
                "capacity": length_t * (high - low) * height,
                "k": 1.0 / (length_t * (high - low)),
                "c": (high * high - low * low) / (2.0 * (high - low)),
                "m1": (high ** 3 - low ** 3) / 3.0,
                "m2": (high * high - low * low) / 2.0,
                "m3": (high ** 3 - low ** 3) / 6.0,
            })
        if len(self.tanks) != 2:
            raise ValueError("the free-float reference needs exactly two tanks")

        volumes = spec["initial_volumes_m3"]
        if len(volumes) != 2:
            raise ValueError("two initial tank volumes are required")
        self.initial_volumes = tuple(_positive(value, "initial_volume_m3")
                                     for value in volumes)
        self.total_volume = math.fsum(self.initial_volumes)
        self.displaced_volume = self.total_volume + self.dry_mass / self.density
        self.waterplane_area = self.length * self.beam
        self.total_mass = self.dry_mass + self.density * self.total_volume
        # Tank water is added mass, never lost buoyancy, and the hull is a
        # wall-sided prism, so the conserved displacement fixes the draft.
        self.draft = self.displaced_volume / self.waterplane_area
        if not 0.0 < self.draft < self.depth:
            raise ValueError("the free-float fixture must float between plates")
        for tank, volume in zip(self.tanks, self.initial_volumes):
            if volume >= tank["capacity"]:
                raise ValueError("the free-float fixture must start below capacity")
        self.flow_factor = (self.discharge_coefficient * self.orifice_area
                            * math.sqrt(2.0 * self.gravity))
        self.depth_headroom = min(self.draft, self.depth - self.draft)
        self.bm = self.beam ** 2 / (12.0 * self.draft)
        # d(d_a - d_b)/dq at fixed volumes; this is the attitude feedback.
        self.apex_feedback = -(self.tanks[0]["c"] - self.tanks[1]["c"])

    # -- closed-form column integrals --------------------------------------
    def intercept(self, tank, slope, volume):
        """Bottom-relative liquid plane intercept ``d`` of one tank."""
        return tank["k"] * volume - tank["c"] * slope

    def moments(self, tank, slope, volume):
        """(V, My, Mz) of one tank's liquid column."""
        intercept = self.intercept(tank, slope, volume)
        low, high, length = tank["low"], tank["high"], tank["length"]
        return (
            length * (slope * tank["m2"] + intercept * (high - low)),
            length * (slope * tank["m1"] + intercept * tank["m2"]),
            length * (slope * slope * tank["m3"]
                      + slope * intercept * tank["m2"]
                      + intercept * intercept * (high - low) / 2.0),
        )

    def cg_keel(self, volumes, slope):
        """Combined centre of gravity above the keel, in hull coordinates.

        The vertical moment of a tank whose liquid plane is ``q y + d`` above
        the tank bottom is ``bottom * V + integral(h^2/2)``, so the tank bottom
        must be carried explicitly; dropping it would place the liquid at the
        wrong height whenever a tank is lifted above the keel.
        """
        first_y = 0.0
        first_z = 0.0
        for tank, volume in zip(self.tanks, volumes):
            column_volume, moment_y, moment_z = self.moments(tank, slope, volume)
            first_y += moment_y
            first_z += tank["bottom"] * column_volume + moment_z
        return (first_y / self.displaced_volume,
                (self.dry_mass / self.density * self.dry_kg + first_z)
                / self.displaced_volume)

    def buoyancy_keel(self, slope):
        """Buoyancy centre above the keel, in hull coordinates."""
        return (0.0,
                slope * self.beam ** 2 / (12.0 * self.draft),
                0.5 * self.draft
                + slope * slope * self.beam ** 2 / (24.0 * self.draft))

    def transverse_residual(self, volumes, slope):
        cg_y, cg_z = self.cg_keel(volumes, slope)
        _, buoy_y, buoy_z = self.buoyancy_keel(slope)
        return (buoy_y - cg_y) + slope * (buoy_z - cg_z)

    def solve_slope(self, volumes, guess=0.0):
        """Equilibrium heel slope, by secant with automatic bracket expansion."""
        function = lambda value: self.transverse_residual(volumes, value)
        low, high = guess - 1e-3, guess + 1e-3
        low_value, high_value = function(low), function(high)
        for _ in range(60):
            if (low_value > 0.0) != (high_value > 0.0):
                break
            low, low_value = guess - 2.0 * (guess - low), function(guess - 2.0 * (guess - low))
            high, high_value = guess + 2.0 * (high - guess), function(guess + 2.0 * (high - guess))
        else:
            raise ValueError("equilibrium heel root is not bracketed")
        return _secant(function, low, high)

    def volumes_at_transfer(self, transfer):
        """Tank volumes after a nonnegative transfer magnitude.

        ``direction`` is +1 when the flow runs tank A to tank B and -1 when it
        runs the other way, so the donor loses and the receiver gains the same
        volume.  Subtracting from both tanks would destroy the conserved total
        and is exactly the kind of bookkeeping bug this reference must not
        have.
        """
        first, second = self.initial_volumes
        if self.direction > 0.0:
            return (first - transfer, second + transfer)
        return (first + transfer, second - transfer)

    def head_difference(self, volumes, slope):
        scale = math.sqrt(1.0 + slope * slope)
        heads = []
        for tank, volume in zip(self.tanks, volumes):
            intercept = self.intercept(tank, slope, volume) + tank["bottom"]
            heads.append((intercept + slope * self.aperture_y
                          - self.aperture_z) / scale)
        return heads[0] - heads[1], heads[0], heads[1]

    def surface_extremes(self, volumes, slope):
        lowest = math.inf
        highest = -math.inf
        for tank, volume in zip(self.tanks, volumes):
            intercept = self.intercept(tank, slope, volume) + tank["bottom"]
            for edge in (tank["low"], tank["high"]):
                value = slope * edge + intercept
                lowest = min(lowest, value)
                highest = max(highest, value)
        return lowest, highest

    def liquid_centroids(self, volumes, slope):
        result = []
        for tank, volume in zip(self.tanks, volumes):
            _, first_y, first_z = self.moments(tank, slope, volume)
            result.append([0.0, first_y / volume,
                           tank["bottom"] + first_z / volume])
        return result

    def state(self, transfer):
        volumes = self.volumes_at_transfer(transfer)
        slope = self.solve_slope(volumes)
        head, head_a, head_b = self.head_difference(volumes, slope)
        lowest, highest = self.surface_extremes(volumes, slope)
        return {
            "transfer_m3": transfer,
            "volumes_m3": [volumes[0], volumes[1]],
            "heel_slope_q": slope,
            "heel_deg": math.degrees(math.atan(slope)),
            "trim_deg": 0.0,
            "draft_m": self.draft,
            "buoyancy_centre_keel_m": list(self.buoyancy_keel(slope)),
            "effective_cg_keel_m": list(self.cg_keel(volumes, slope)),
            "liquid_centroids_keel_m": self.liquid_centroids(volumes, slope),
            "surface_intercepts_keel_m": [
                self.intercept(self.tanks[0], slope, volumes[0])
                + self.tanks[0]["bottom"],
                self.intercept(self.tanks[1], slope, volumes[1])
                + self.tanks[1]["bottom"]],
            "aperture_pressure_heads_m": [head_a, head_b],
            "head_difference_m": head,
            "liquid_surface_low_m": lowest,
            "liquid_surface_high_m": highest,
            "transverse_residual_m": self.transverse_residual(volumes, slope),
        }

    def _direction_and_endpoint(self):
        slope0 = self.solve_slope(self.initial_volumes)
        head0 = self.head_difference(self.initial_volumes, slope0)[0]
        if head0 == 0.0:
            raise ValueError("the free-float fixture must start with a driving head")
        self.direction = 1.0 if head0 > 0.0 else -1.0
        # With direction +1 the donor is tank 0; with direction -1 it is tank 1.
        # The transfer can never exceed what the donor holds, and it stops at
        # the finite equalisation transfer which is strictly inside that.
        donor, receiver = ((0, 1) if self.direction > 0.0 else (1, 0))
        donor_volume = self.initial_volumes[donor]
        receiver_room = self.tanks[receiver]["capacity"] \
            - self.initial_volumes[receiver]
        self.transfer_limit = max(1e-9, min(0.5 * donor_volume, 0.5 * receiver_room,
                                            self.total_volume))
        self.equalisation_transfer = _bisect(
            lambda value: -self.direction * self.head_difference(
                self.volumes_at_transfer(value),
                self.solve_slope(self.volumes_at_transfer(value)))[0],
            0.0, self.transfer_limit)

    def head_slope_derivative(self, transfer):
        """``d(head)/d(transfer)`` along the equilibrium, by central difference."""
        delta = 1e-6 * self.transfer_limit
        plus = self.state(min(transfer + delta, self.transfer_limit))
        minus = self.state(max(transfer - delta, 0.0))
        return (plus["head_difference_m"] - minus["head_difference_m"]) \
            / (plus["transfer_m3"] - minus["transfer_m3"])

    def regularized_integrand(self, r):
        """dt/(-dr), factoring the two static cubics before subtraction.

        The head vanishes as r**2. Direct subtraction of the two liquid
        intercepts loses relative precision there. This algebraic finite
        difference preserves the endpoint limit without a fitted cutoff.
        """
        endpoint = self.volumes_at_transfer(self.equalisation_transfer)
        qe = self.solve_slope(endpoint)
        delta = self.equalisation_transfer * r * r
        volumes = self.volumes_at_transfer(self.equalisation_transfer - delta)
        q = self.solve_slope(volumes)
        areas = [1.0 / tank["k"] for tank in self.tanks]
        gamma = sum(1.0 / area for area in areas)
        delta_y = self.tanks[1]["c"] - self.tanks[0]["c"]
        moment_area = sum(t["length"] * (t["high"] - t["low"]) ** 3 / 12.0
                          for t in self.tanks)
        beta = self.bm - moment_area / self.displaced_volume
        d0 = self.draft / 2.0 - (self.dry_mass / self.density * self.dry_kg
            + sum(t["bottom"] * v + v * v / (2.0 * area)
                  for t, v, area in zip(self.tanks, volumes, areas))) / self.displaced_volume
        dprime = self.direction * (self.tanks[0]["bottom"] + endpoint[0] / areas[0]
            - self.tanks[1]["bottom"] - endpoint[1] / areas[1]) / self.displaced_volume
        cprime = self.direction * delta_y / self.displaced_volume
        denominator = beta + d0 + beta * (q * q + q * qe + qe * qe) / 2.0
        coefficient = gamma + self.direction * delta_y * (
            -cprime + dprime * qe + gamma * delta * qe / (2.0 * self.displaced_volume)) / denominator
        if denominator <= 0.0 or coefficient <= 0.0:
            raise ValueError("reference static/head branch is outside the bounded model")
        return 2.0 * math.sqrt(self.equalisation_transfer) / (
            self.flow_factor * math.sqrt(coefficient / math.sqrt(1.0 + q * q)))

    def interval_bounds(self):
        """Conservative bounds for the entire continuous transfer interval."""
        ends = [self.initial_volumes, self.volumes_at_transfer(self.equalisation_transfer)]
        areas = [1.0 / t["k"] for t in self.tanks]
        j = sum(t["length"] * (t["high"] - t["low"]) ** 3 / 12.0 for t in self.tanks)
        beta = self.bm - j / self.displaced_volume
        d_values = [self.draft / 2.0 - (self.dry_mass / self.density * self.dry_kg
            + sum(t["bottom"] * v + v * v / (2.0 * a)
                  for t, v, a in zip(self.tanks, vs, areas))) / self.displaced_volume for vs in ends]
        c_values = [sum(t["c"] * v for t, v in zip(self.tanks, vs)) / self.displaced_volume for vs in ends]
        lower = beta + min(d_values)
        if beta <= 0.0 or lower <= 0.0:
            raise ValueError("cannot prove a bounded static branch")
        q_bound = max(abs(c) for c in c_values) / lower
        delta_y = self.tanks[1]["c"] - self.tanks[0]["c"]
        gamma = sum(1.0 / area for area in areas)
        dprime_bound = max(abs((self.tanks[0]["bottom"] + vs[0] / areas[0]
                               - self.tanks[1]["bottom"] - vs[1] / areas[1]) / self.displaced_volume) for vs in ends)
        qprime_bound = (abs(delta_y) / self.displaced_volume + dprime_bound * q_bound) / lower
        numerator_bound = max(abs(self.tanks[0]["bottom"] + vs[0] / areas[0]
                                  - self.tanks[1]["bottom"] - vs[1] / areas[1]) for vs in ends) + abs(delta_y) * q_bound
        slope_bound = -gamma + abs(delta_y) * qprime_bound
        head_derivative_upper = slope_bound / math.sqrt(1.0 + q_bound * q_bound) + numerator_bound * q_bound * qprime_bound
        factor_lower = -slope_bound / math.sqrt(1.0 + q_bound * q_bound)
        if head_derivative_upper >= 0.0 or factor_lower <= 0.0:
            raise ValueError("cannot prove decreasing directed head and positive endpoint factor")
        lows, tops, heads = [], [], []
        for i, t in enumerate(self.tanks):
            heights = [vs[i] / areas[i] for vs in ends]
            wedge = q_bound * (t["high"] - t["low"]) / 2.0
            lows.append(min(heights) - wedge)
            tops.append(t["height"] - max(heights) - wedge)
            heads.append((t["bottom"] + min(heights)
                          - q_bound * abs(self.aperture_y - t["c"])
                          - self.aperture_z) / math.sqrt(1.0 + q_bound * q_bound))
        result = {"method": "concave vertical term endpoint minimum; affine transverse moment endpoint maximum; positive cubic denominator",
                  "abs_q_upper": q_bound, "tank_bottom_clearance_lower_m": lows,
                  "abs_q_derivative_upper_per_m3": qprime_bound,
                  "directed_head_derivative_upper_per_m2": head_derivative_upper,
                  "positive_head_factor_lower_per_m2": factor_lower,
                  "tank_top_clearance_lower_m": tops, "aperture_head_lower_m": heads,
                  "hull_wedge_margin_m": self.depth_headroom - q_bound * self.beam / 2.0}
        if min(lows + tops + heads + [result["hull_wedge_margin_m"]]) <= 0.0:
            raise ValueError("full-interval column/aperture bounds do not hold")
        return result


def two_tank_trajectory(spec, integration_step_s):
    """Integrate the attitude-feedback head ODE for the asymmetric pair.

    The transferred volume ``w`` is the natural state.  ``H(w)`` is monotone
    and reaches zero at the finite equalisation transfer ``w_eq``, so

        dw/dt = k * sqrt(|H|)

    has a square-root endpoint singularity that a naive integrator cannot cross
    accurately.  The substitution ``w = w_eq (1 - r^2)`` removes it exactly:

        -dt/dr = 2 w_eq r / (k * sqrt(|H|))

    and since ``|H| ~ |H'| w_eq r^2`` at the endpoint the ratio tends to the
    finite positive limit ``2 sqrt(w_eq) / (k sqrt(|H'|))``. Here w is
    nonnegative transfer magnitude; direction only selects donor/receiver.
    Integrating ``-dt/dr`` by Simpson from ``r = 0`` to ``r = 1``
    (equalisation) therefore has no event search and no singularity, and the
    time is a regular function of ``r`` everywhere.

    Past ``r = 0`` the vented flow is exactly zero, so the reference is
    piecewise constant and the integration is deliberately *not* continued over
    the remaining requested duration.

    Provenance: this regularisation is the same substitution used by the
    independent review script, reimplemented here from the model algebra with
    no import of that script and no dependency on its output path.
    """
    key = (json.dumps(spec, sort_keys=True), round(integration_step_s, 12))
    cached = _TRAJECTORY_CACHE.get(key)
    if cached is not None:
        return cached

    model = TwoTankFreeFloatModel(spec)
    model._direction_and_endpoint()
    endpoint = model.equalisation_transfer
    direction = model.direction

    def dt_dr(r):
        return model.regularized_integrand(r)

    def elapsed(r, intervals):
        # The positive -dt/dr integrates from the current r back to r=1.
        return _simpson(dt_dr, r, 1.0, intervals)

    step_s = _positive(integration_step_s, "integration_step_s")
    # Intervals scale inversely with the nominal step, so the declared coarse
    # rung really is a coarser quadrature and the refinement control compares
    # two distinct rungs instead of a cached duplicate.
    intervals = max(64, int(round(20.0 / step_s)))
    if intervals % 2:
        intervals += 1
    # An increasing elapsed-time table brackets inversion. Each final local
    # integral still uses Simpson rather than linear interpolation of state.
    rs = [1.0 - index / intervals for index in range(intervals + 1)]
    ts = [0.0]
    for left, right in zip(rs, rs[1:]):
        ts.append(ts[-1] + _simpson(dt_dr, right, left, 2))
    plateau_time = ts[-1]

    def transfer_at_time(time_s):
        if time_s >= plateau_time:
            return endpoint
        if time_s <= 0.0:
            return 0.0
        from bisect import bisect_right
        index = min(len(ts) - 2, bisect_right(ts, time_s) - 1)
        r = _bisect(lambda value: time_s - ts[index]
                    - _simpson(dt_dr, value, rs[index], 4), rs[index + 1], rs[index])
        return endpoint * (1.0 - r * r)

    trace = {
        "model": model,
        "equalisation_transfer": endpoint,
        "plateau_time_s": plateau_time,
        "direction": direction,
        "intervals": intervals,
        "transfer_at_time": transfer_at_time,
        "elapsed": elapsed,
    }
    _TRAJECTORY_CACHE[key] = trace
    return trace


def two_tank_reference(spec):
    """Full reference for the asymmetric connected two-tank free-float."""
    model = TwoTankFreeFloatModel(spec)
    model._direction_and_endpoint()
    step = _positive(spec["integration_step_s"], "integration_step_s")
    finest = two_tank_trajectory(spec, step)
    plateau_time = finest["plateau_time_s"]
    endpoint = finest["equalisation_transfer"]

    # A four-times-coarser quadrature rung, built by the same code path and
    # used only as the measured refinement control.  The reported trajectory is
    # always the fine one.
    coarse = two_tank_trajectory(spec, step * 4.0)

    samples = {}
    for time_s in sorted(set(spec["sample_times_s"]) | {0.0}):
        transfer = finest["transfer_at_time"](time_s)
        row = model.state(transfer)
        row["time_s"] = float(time_s)
        row["net_transfer_m3"] = float(model.direction * transfer)
        row["coarse_net_transfer_m3"] = float(
            model.direction * coarse["transfer_at_time"](time_s))
        row["plateau_constant"] = bool(time_s >= plateau_time)
        samples[f"t={_format_time(time_s)}"] = row

    # Independent control: solve the very same transverse equilibrium with a
    # plain bisection root finder and compare the heel slope with the secant
    # path used everywhere else.
    bisected = _bisect(lambda value: model.transverse_residual(
        model.initial_volumes, value), -0.2, 0.2)
    initial_row = samples[f"t={_format_time(0.0)}"]
    plateau_row = samples[f"t={_format_time(max(spec['sample_times_s']))}"]

    # The grid below is a diagnostic; full interval proof is separate.
    # from no transfer up to the equalisation transfer.  Sampling beyond the
    # equalisation transfer would describe a state the flow never reaches, and
    # a column that has already emptied has no wedge to bound.
    grid = _transfer_grid(finest)
    rows = [model.state(value) for value in grid]
    extremes = [(row["liquid_surface_low_m"], row["liquid_surface_high_m"])
                for row in rows]
    heads = [min(row["aperture_pressure_heads_m"]) for row in rows]
    slopes = [abs(row["heel_slope_q"]) for row in rows]
    wedge_used = max(slopes) * 0.5 * model.beam
    tank_height = min(tank["height"] for tank in model.tanks)

    refinement = max(abs(samples[key]["net_transfer_m3"]
                         - samples[key]["coarse_net_transfer_m3"])
                     for key in samples)
    # Requested 60/300 s samples lie on the plateau. Measure quadrature
    # refinement during transfer as well, including near the finite endpoint.
    control_times = sorted(set((5.0, 10.0, 12.0)) |
                           {plateau_time * fraction for fraction in (.1, .5, .9)} |
                           {finest["elapsed"](r, finest["intervals"]) for r in (1e-4, 1e-6, 1e-8)})
    control_samples = [{"time_s": t, "fine_transfer_m3": finest["transfer_at_time"](t),
                        "coarse_transfer_m3": coarse["transfer_at_time"](t),
                        "before_equalisation": t < plateau_time} for t in control_times]
    refinement = max(refinement, max(abs(row["fine_transfer_m3"] - row["coarse_transfer_m3"])
                                     for row in control_samples))

    def quad_column(tank, slope_at, volume):
        intercept = model.intercept(tank, slope_at, volume)

        def height(y):
            return slope_at * y + intercept

        return (tank["length"] * _gauss_legendre_2(height, tank["low"], tank["high"]),
                tank["length"] * _gauss_legendre_2(lambda y: y * height(y),
                                                   tank["low"], tank["high"]),
                tank["length"] * _gauss_legendre_2(
                    lambda y: 0.5 * height(y) ** 2, tank["low"], tank["high"]))

    worst_volume_control = 0.0
    worst_cg_control = 0.0
    for value in grid:
        volumes = model.volumes_at_transfer(value)
        slope_at = model.solve_slope(volumes)
        closed = [model.moments(tank, slope_at, item)
                  for tank, item in zip(model.tanks, volumes)]
        quad = [quad_column(tank, slope_at, item)
                for tank, item in zip(model.tanks, volumes)]
        for index in (0, 1):
            worst_volume_control = max(worst_volume_control,
                                       abs(closed[index][0] - quad[index][0]))
        closed_cg = model.cg_keel(volumes, slope_at)
        quad_cg = ((quad[0][1] + quad[1][1]) / model.displaced_volume,
                   (model.dry_mass / model.density * model.dry_kg
                    + quad[0][2] + model.tanks[0]["bottom"] * quad[0][0]
                    + quad[1][2] + model.tanks[1]["bottom"] * quad[1][0]) / model.displaced_volume)
        worst_cg_control = max(worst_cg_control,
                               abs(closed_cg[0] - quad_cg[0]),
                               abs(closed_cg[1] - quad_cg[1]))

    residual_gap = abs(bisected - initial_row["heel_slope_q"])
    endpoint_residual = abs(model.state(endpoint)["transverse_residual_m"])

    equal_volumes = model.volumes_at_transfer(endpoint)

    return {
        "oracle": "continuous-two-tank-free-float-attitude-feedback-2",
        "method": "closed-form rectangular columns with a rebalanced heel solve "
                  "and a regularised transfer ODE",
        "derivation": [
            "Both tanks lie on the centre plane and the dry mass is centred, so "
            "Bx = p L^2/(12T) and Gx = 0 are identically satisfied by p = 0.",
            "Each liquid column is z = q y + d, so d = k V - c q with "
            "k = 1/(Lt (yb-ya)) and c = (yb^2-ya^2)/(2 (yb-ya)); the closed-form "
            "volume and first moments then follow from integrating the column.",
            "Buoyancy of the wall-sided box is By = q B^2/(12T) and "
            "Bz = T/2 + q^2 B^2/(24T), with the draft fixed by the conserved "
            "displaced volume because the tank water is added mass, not lost "
            "buoyancy.",
            "The heel solves (By - Gy) + q(Bz - Gz) = 0 at every instant, so "
            "attitude and head difference are solved together: the heel feeds "
            "the head difference and the head difference feeds the heel.",
            "Both aperture heads share the same unit-normal factor, so the head "
            "difference is (d_a - d_b)/sqrt(1+q^2); the q-dependent part of "
            "that apex is exactly the attitude feedback.",
            "For nonnegative transfer magnitude w, u = sqrt(w_eq - w) "
            "satisfies du/dt = -k sqrt(|H(w)|/(w_eq-w))/2; its endpoint "
            "limit is -k sqrt(|H'(w_eq)|)/2. Past equal head "
            "instant the vented flow is exactly zero.",
        ],
        "quantities": _quantities({
            "draft_m": (model.draft, "m"),
            "displaced_volume_m3": (model.displaced_volume, "m3"),
            "dry_mass_equivalent_volume_m3": (model.dry_mass / model.density, "m3"),
            "total_mass_t": (model.total_mass, "t"),
            "total_water_volume_m3": (model.total_volume, "m3"),
            "initial_volume_port_m3": (model.initial_volumes[0], "m3"),
            "initial_volume_starboard_m3": (model.initial_volumes[1], "m3"),
            "initial_heel_slope_q": (initial_row["heel_slope_q"], "-"),
            "initial_heel_deg": (initial_row["heel_deg"], "deg"),
            "initial_head_difference_m": (initial_row["head_difference_m"], "m"),
            "equalisation_transfer_m3": (endpoint, "m3"),
            "equal_head_volume_port_m3": (equal_volumes[0], "m3"),
            "equal_head_volume_starboard_m3": (equal_volumes[1], "m3"),
            "equal_head_heel_slope_q": (
                model.solve_slope(equal_volumes), "-"),
            "final_volume_port_m3": (plateau_row["volumes_m3"][0], "m3"),
            "final_volume_starboard_m3": (plateau_row["volumes_m3"][1], "m3"),
            "net_transfer_m3": (model.direction * endpoint, "m3"),
            "plateau_time_s": (plateau_time, "s"),
            "head_attitude_feedback_coefficient_dh_dq": (model.apex_feedback, "m"),
            "tank_height_m": (tank_height, "m"),
        }),
        "samples": samples,
        "transient_quadrature_controls": control_samples,
        "relations": {
            "model_applicability": dict(_MODEL_APPLICABILITY),
            "full_interval_bounds": model.interval_bounds(),
            "is_fixed_attitude_pair_oracle": False,
            "is_final_equal_volume_answer": False,
            "attitude_feedback_included": True,
            "attitude_feedback_note": "the equilibrium heel is solved at every "
                                      "instant from the closed-form column "
                                      "moments; a frozen-attitude pair solution "
                                      "and a final-equal-volume answer are both "
                                      "explicitly rejected as references",
            "tank_height_m": tank_height,
            "liquid_surface_bounds_m": {
                "minimum_above_tank_bottom_m": min(model.interval_bounds()["tank_bottom_clearance_lower_m"]),
                "maximum_below_tank_top_m": min(model.interval_bounds()["tank_top_clearance_lower_m"]),
                "minimum_aperture_head_m": min(model.interval_bounds()["aperture_head_lower_m"]),
                "hull_wedge_used_m": model.interval_bounds()["abs_q_upper"] * model.beam / 2,
                "hull_wedge_margin_m": model.interval_bounds()["hull_wedge_margin_m"],
            },
            "sampled_absolute_surface_range_m": [min(item[0] for item in extremes), max(item[1] for item in extremes)],
            "hull_wedge_used_m": wedge_used,
            "hull_depth_headroom_m": model.depth_headroom,
            "piecewise_constant_after_equilibrium": True,
            "ceiling_or_bottom_clipped": False,
            "flow_direction": ("port_to_starboard" if model.direction > 0.0
                               else "starboard_to_port"),
            "initial_volumes_m3": [model.initial_volumes[0],
                                   model.initial_volumes[1]],
        },
        "evidence": {"controls": [
            _control("regularised_step_halving_transfer", refinement, "m3",
                     REFERENCE_PRECISION["volume_abs_m3"],
                     "finest and four-times-coarser integration of the "
                     "regularised transfer ODE, compared state by state"),
            _control("column_volume_vs_gauss_legendre", worst_volume_control, "m3",
                     REFERENCE_PRECISION["volume_abs_m3"],
                     "closed-form column volume against two-point "
                     "Gauss-Legendre quadrature of the affine column height"),
            _control("column_cg_vs_gauss_legendre", worst_cg_control, "m",
                     REFERENCE_PRECISION["geometric_abs_m"],
                     "closed-form column first moments against the same "
                     "quadrature, propagated into the centre of gravity"),
            _control("initial_heel_secant_vs_bisection", residual_gap, "-",
                     REFERENCE_PRECISION["scaled_residual_max"],
                     "secant equilibrium solve against an independent bisection "
                     "root finder"),
            _control("endpoint_transverse_residual",
                     endpoint_residual / model.beam, "-",
                     REFERENCE_PRECISION["scaled_residual_max"],
                     "scaled transverse moment residual at the equalisation "
                     "transfer"),
            _control("equalisation_time_vs_coarse_quadrature",
                     abs(plateau_time - coarse["plateau_time_s"]), "s",
                     REFERENCE_PRECISION["event_time_abs_s"],
                     "equalisation instant from the fine and the "
                     "four-times-coarser Simpson rung"),
        ], "notes": ["no production solver participates",
                     "Quadrature refinement is a consistency control; independent derivation/ODE evidence is required for reference accuracy."],
            "endpoint_root_repeat_difference_m3": abs(endpoint - coarse["equalisation_transfer"]),
            "endpoint_root_repeat_meaning": "same algebraic root repeated, not quadrature accuracy evidence"},
    }


def _transfer_grid(trace, count=65):
    """Transfer values spanning the whole interval, used for bound proofs."""
    endpoint = trace["equalisation_transfer"]
    return [endpoint * index / (count - 1.0) for index in range(count)]


# ---------------------------------------------------------------------------
# Reference 5 -- model-boundary and cancellation controls
# ---------------------------------------------------------------------------

def capacity_boundary_reference(spec, sample_times):
    """Reference for the declared receiver-capacity boundary control."""
    slope, flow, head0, _ = _single_sea_constants(spec)
    capacity = _positive(spec["tank_capacity_m3"], "tank_capacity_m3")
    needed = capacity - spec["initial_volume_m3"]
    if needed <= 0.0:
        raise ValueError("the boundary control must start below capacity")
    capacity_time = 2.0 * (math.sqrt(head0)
                           - math.sqrt(max(0.0, head0 - slope * needed))) \
        / (slope * flow)

    samples = {f"t={_format_time(value)}": single_sea_coupled_state(spec, min(value, capacity_time))
               for value in sorted(set(sample_times) | {0.0})}
    return {
        "oracle": "continuous-receiver-capacity-boundary-1",
        "method": "closed-form coupled head with the capacity instant solved "
                  "analytically",
        "derivation": [
            "The same vented head ODE applies until the tank fills, so the "
            "capacity instant follows from V(t) = capacity, i.e. from "
            "sqrt(H0) - a k t/2 = sqrt(H0 - a*(capacity - V0)).",
            "The production model must stop with a receiver_capacity model "
            "limit at or just before that instant and must not invent overflow "
            "or discard water.",
        ],
        "quantities": _quantities({
            "capacity_time_s": (capacity_time, "s"),
            "tank_capacity_m3": (capacity, "m3"),
            "initial_head_m": (head0, "m"),
            "initial_draft_m": (spec["initial_draft_m"], "m"),
            "net_transfer_m3": (samples[f"t={_format_time(max(sample_times))}"]
                                ["net_sea_influx_m3"], "m3"),
        }),
        "samples": samples,
        "relations": {
            "model_applicability": dict(_MODEL_APPLICABILITY),
            "expected_boundary": "receiver_capacity",
            "boundary_is_declared_not_invented": True,
            "overflow_modelled": False,
            "ceiling_or_bottom_clipped": False,
            "heave_feedback_included": True,
        },
        "evidence": {"controls": [_control(
            "capacity_time_volume_residual", abs(single_sea_coupled_state(spec, capacity_time)["tank_volume_m3"] - capacity),
            "m3", REFERENCE_PRECISION["volume_abs_m3"], "closed-form capacity event substituted back into V(t)")],
            "notes": ["Reference ends at capacity; requested later times are bounded diagnostic snapshots, not overflow predictions."]},
    }


def cancellation_reference(spec, cancel_time_s):
    """Reference for the declared cancellation control.

    A cancellation is an operational stop, not a physical event.  The only
    trustworthy content is the last accepted state and the requested instant,
    so the reference states the closed-form state at that instant and
    explicitly declines to predict the solver's bookkeeping.
    """
    cancel_time_s = _positive(cancel_time_s, "cancel_time_s")
    state = single_sea_coupled_state(spec, cancel_time_s)
    return {
        "oracle": "continuous-cancellation-control-1",
        "method": "closed-form state at the declared accepted instant",
        "derivation": [
            "Cancellation is an operational request, so this reference makes no "
            "physical stopping claim of any kind.",
            "It reports the closed-form state at the instant implied by the "
            "declared accepted-step count and time step, and requires the last "
            "accepted timeline to be finite and complete up to that point.",
        ],
        "quantities": _quantities({
            "cancel_time_s": (cancel_time_s, "s"),
            "net_sea_influx_m3": (state["net_sea_influx_m3"], "m3"),
            "tank_volume_m3": (state["tank_volume_m3"], "m3"),
            "draft_m": (state["draft_m"], "m"),
        }),
        "samples": {f"t={_format_time(0.0)}": single_sea_coupled_state(spec, 0.0),
                    f"t={_format_time(cancel_time_s)}": state},
        "relations": {
            "model_applicability": dict(_MODEL_APPLICABILITY),
            "cancellation_is_operational_not_physical": True,
            "no_physical_stop_claimed": True,
            "piecewise_constant_after_equilibrium": True,
        },
        "evidence": single_sea_coupled_reference(spec, [cancel_time_s])["evidence"],
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_BOX_PRECISION = {"integration_step_s": 0.0,
                  "quadrature": "two-point Gauss-Legendre, exact to degree 3"}


def reference_for(case):
    """Return the independent continuous reference declared by ``case``.

    ``case`` is a case dictionary produced by
    ``verification_cases.build_cases``.  The returned mapping is strict
    canonical JSON: no NaN, no infinity, no tuples and no callables.
    """
    kind = case["kind"]
    inputs = case["inputs"]

    if kind == "transform.mirror":
        # A mirror needs a *solved* heel, not a prescribed slope: the point
        # of the case is that an asymmetric load produces a nonzero attitude
        # and that reflecting the load reverses it.
        oracle = _box_reference(inputs["box"])
        oracle["relations"]["mirrored"] = bool(inputs["mirrored"])
        oracle["relations"]["mirror_partner"] = inputs["mirror_partner"]
        return _common(oracle, kind, "wall-sided-box-free-heel-reference-1",
                       dict(_BOX_PRECISION))

    if kind in ("transform.scale_linear", "transform.datum"):
        oracle = _box_reference(inputs["box"])
        if kind == "transform.scale_linear":
            oracle["relations"]["scale_factor"] = inputs["scale_factor"]
            oracle["relations"]["exponents"] = dict(inputs["relation_exponents"])
        else:
            oracle["relations"]["datum_shift_m"] = inputs["keel_offset_m"]
            oracle["relations"]["keel_relative_invariant"] = True
        return _common(oracle, kind, "wall-sided-box-reference-2",
                       dict(_BOX_PRECISION))

    if kind == "mesh.ellipsoid_refinement":
        oracle = ellipsoid_reference(
            inputs["semi_axes_m"], inputs["centre_z_m"], inputs["p"],
            inputs["q"], inputs["waterline_d_m"], inputs["rho_t_m3"],
            inputs["kg_m"], inputs["prescribed_gz_m"])
        return _common(oracle, kind, "sliced-ellipsoid-reference-3",
                       {"integration_step_s": 0.0,
                        "quadrature": "Simpson cap slices plus Cartesian polar"})

    if kind in ("flooding.long_replay", "flooding.control_reversal_guard",
                "flooding.control_head_direction"):
        spec = inputs["reference_spec"]
        if inputs["scenario_name"] == "single_sea_coupled_box":
            oracle = single_sea_coupled_reference(spec, inputs["sample_times_s"])
        else:
            oracle = two_tank_reference(spec)
        if kind == "flooding.control_head_direction":
            oracle["relations"]["opposite_initial_head_control"] = True
        return _common(oracle, kind, "flooding-reference-3",
                       {"integration_step_s": spec.get("integration_step_s", 0.0)})

    if kind == "flooding.control_model_boundary":
        oracle = capacity_boundary_reference(inputs["reference_spec"],
                                             inputs["sample_times_s"])
        return _common(oracle, kind, "flooding-reference-3",
                       {"integration_step_s": 0.0})

    if kind == "flooding.control_cancel":
        oracle = cancellation_reference(inputs["reference_spec"],
                                        inputs["cancel_time_s"])
        return _common(oracle, kind, "flooding-reference-3",
                       {"integration_step_s": 0.0})

    raise KeyError(f"unknown verification case kind: {kind!r}")


def _common(oracle, kind, method_version, precision_extra=None):
    if kind.startswith("transform.") or kind.startswith("mesh."):
        oracle["relations"]["model_applicability"] = {
            "geometry_model": "continuous_ellipsoid" if kind.startswith("mesh.") else "wall_sided_box",
            "single_static_waterplane": True,
            "rectangular_liquid_columns_when_requested": True,
            "external_experiment_measured": False,
        }
    precision = dict(REFERENCE_PRECISION)
    if precision_extra:
        precision.update(precision_extra)
    reference = {
        "schema": REFERENCE_SCHEMA,
        "case_kind": kind,
        "limitations": list(_SHARED_LIMITATIONS),
        "precision": precision,
    }
    reference.update(oracle)
    reference["method_version"] = method_version
    if not reference["evidence"]["controls"]:
        reference["limitations"] = list(reference["limitations"]) + [
            "This control reference reports no numeric accuracy evidence "
            "because its content is a declared boundary or an operational "
            "cancellation, not a computed physical trajectory.",
        ]
    return json.loads(json.dumps(reference, allow_nan=False))
