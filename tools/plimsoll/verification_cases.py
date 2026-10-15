# -*- coding: utf-8 -*-
"""Deterministic verification cases with predeclared expectations.

``build_cases(suite)`` is the frozen half of core-verification round two.  It
returns strict canonical JSON dictionaries: every number is a finite,
non-boolean literal, every identifier is stable, and every expected status,
reason, check and tolerance is written here *before* any production kernel is
executed.  Nothing in this module reads the repository, the documentation tree
or the network, and it imports no test module.

The companion module ``verification_oracles`` supplies the continuous answers.
The separation is deliberate: an expected value must never be produced by the
code under test.

Suite layout (design.md section 4)
----------------------------------
``quick``     deterministic scale/mirror/datum checks plus three joint meshes.
``extended``  the complete nine-mesh matrix, the twelve long replays and the
              boundary, cancellation, head-direction and reversal controls.
``all``       the deduplicated union of the two.

Evidence types are declared per case in ``expected.evidence_kind`` and are
never interchangeable: a mathematical reference, a transformation law, a
numeric approximation, a model-applicability statement and pending external
experiment are five different claims.
"""

from __future__ import annotations

import copy
import math


CASE_SCHEMA = "plimsoll-verification-case-1"
SUITES = ("quick", "extended", "all")
CASE_KINDS = (
    "transform.scale_linear",
    "transform.mirror",
    "transform.datum",
    "mesh.ellipsoid_refinement",
    "flooding.long_replay",
    "flooding.control_head_direction",
    "flooding.control_model_boundary",
    "flooding.control_cancel",
    "flooding.control_reversal_guard",
)

STOP_CLASSES = (
    "scheduled_completion",
    "hydraulic_equilibrium_tolerance",
    "equal_heads_or_no_open_flow",
    "model_limit",
    "canceled",
    "downflooding_event",
    "equilibrium_failure",
    "invalid_input",
)
STOP_REASONS = {
    "scheduled_completion": "scheduled_completion",
    "hydraulic_equilibrium_tolerance": "hydraulic_equilibrium_tolerance",
    "model_limit": "receiver_capacity",
    "canceled": "canceled",
}

# Declared tolerance budgets, fixed from design.md sections 2 and 3 before any
# kernel run.  These are authoritative and are never relaxed to make a case
# pass.
GEOMETRY_TRANSFORM_RELATIVE = 1e-8
GEOMETRY_TRANSFORM_CENTROID_ABS_M = 1e-7
SOLVED_TRANSFORM_VOLUME_RELATIVE = 1e-6
SOLVED_TRANSFORM_POSITION_ABS_M = 1e-5
SOLVED_TRANSFORM_ANGLE_ABS_DEG = 1e-5
SOLVED_TRANSFORM_RESIDUAL_MAX = 1e-6
SCALED_RESIDUAL_MAX = 1e-6

FINEST_VOLUME_RELATIVE = 1e-3
FINEST_BUOYANCY_AXIS_ABS_M = 0.01
FINEST_DRAFT_ABS_M = 0.01
FINEST_SLOPE_ABS = 1e-4

ORACLE_VOLUME_ABS_M3 = 1e-7
ORACLE_GEOMETRIC_ABS_M = 1e-8
ORACLE_SCALED_RESIDUAL_MAX = 1e-10
ORACLE_EVENT_TIME_ABS_S = 1e-4

TRAJECTORY_VOLUME_ABS_M3 = 1e-4
TRAJECTORY_VOLUME_RELATIVE = 0.01
TRAJECTORY_DRAFT_ABS_M = 1e-3
VOLUME_CONSERVATION_ABS_M3 = 1e-9
VOLUME_CONSERVATION_RELATIVE = 1e-10
MASS_CONSERVATION_ABS_T = 1e-9
MASS_CONSERVATION_RELATIVE = 1e-10

# Declared geometric fixture constants.  These are literal inputs, not results.
BOX_LENGTH_M = 40.0
BOX_BEAM_M = 10.0
BOX_DEPTH_M = 10.0
BOX_DRAFT_M = 4.0
BOX_KG_M = 1.5
BOX_P = 0.01
BOX_Q = 0.1
RHO_T_M3 = 1.025

# The supported asymmetric free-float pair: 20x10x6 box, displaced 400 m3,
# draft exactly 2 m, dry 398.725 t at KG 1 m, two 4 m long tanks of beam 1 and
# 2 centred at y = -0.5 and +1.0, bottom z = 0, height 4 m.
PAIR_HULL = (20.0, 10.0, 6.0)
PAIR_DRY_MASS_T = 398.725
PAIR_DRY_KG_M = 1.0
PAIR_DENSITY = 1.025
PAIR_TANKS = (
    {"name": "port", "length_m": 4.0, "beam_m": 1.0, "height_m": 4.0,
     "centre_y_m": -0.5, "y_low_m": -1.0, "y_high_m": 0.0,
     "keel_to_bottom_m": 0.0},
    {"name": "starboard", "length_m": 4.0, "beam_m": 2.0, "height_m": 4.0,
     "centre_y_m": 1.0, "y_low_m": 0.0, "y_high_m": 2.0,
     "keel_to_bottom_m": 0.0},
)
PAIR_APERTURE = (0.0, 0.0, 0.1)
PAIR_ORIFICE_AREA_M2 = 0.1
PAIR_DISCHARGE_COEFFICIENT = 0.6
PAIR_INTEGRATION_STEP_S = 0.02

SINGLE_HULL = (20.0, 10.0, 6.0)
SINGLE_TANK = {"length_m": 4.0, "beam_m": 2.0, "height_m": 4.0, "x_m": 0.0,
               "y_m": 0.0, "keel_to_bottom_m": 0.0}
SINGLE_DRY_MASS_T = 392.0 * RHO_T_M3
SINGLE_DRY_KG_M = 1.0
SINGLE_INITIAL_VOLUME_M3 = 8.0
SINGLE_DRAFT_M = 2.0

LONG_DURATIONS_S = (60.0, 300.0)
LONG_TIME_STEPS_S = (0.5, 0.25, 0.125)
SCALE_FACTORS = (0.5, 1.0, 2.0)
MESH_STATION_COUNTS = (41, 81, 161)
MESH_VERTEX_COUNTS = (32, 64, 128)
DIAGONAL_MESHES = ((41, 32), (81, 64), (161, 128))

GRAVITY_M_S2 = 9.80665
SCENARIO_SCHEMA = "plimsoll-flooding-scenario-1"
PROJECT_SCHEMA = "plimsoll-project-1"

_PROVENANCE = {"kind": "declared_verification_fixture",
               "suite": "core-verification-round-two"}
_NO_ESTIMATE = {"kind": "declared_verification_fixture", "estimate": False}


def _check(name, kind, required, description, *, path=None, tolerance=None,
           scale=None, unit="-"):
    entry = {
        "name": name,
        "kind": kind,
        "required": bool(required),
        "description": description,
        "path": path,
        "tolerance": tolerance,
        "scale": scale,
        "unit": unit,
    }
    return entry


def _flooding_checks(volume_tolerance_m3, transfer_scale, include_refinement):
    checks = [
        _check("status_flag_matches", "status", True,
               "the returned status must equal the declared stop class"),
        _check("stop_reason_matches", "reason", True,
               "the returned stop reason must equal the declared reason"),
        _check("numerical_convergence_is_true", "flag", True,
               "every accepted equilibrium must have converged"),
        _check("all_states_finite", "finite", True,
               "every reported scalar must be finite"),
        _check("time_monotone", "monotone", True,
               "accepted times must be strictly increasing after t=0"),
        _check("last_accepted_state_present", "presence", True,
               "the run must expose a last accepted state matching the actual "
               "accepted time, never the requested duration"),
        _check("tank_volume_within_capacity", "range", True,
               "every tank volume must stay within zero and capacity"),
        _check("final_volume_vs_reference", "absolute", True,
               "the final transferred volume must match the independent "
               "reference within the declared budget",
               path="final_volume", tolerance=volume_tolerance_m3, unit="m3"),
        _check("final_draft_vs_reference", "absolute", True,
               "the final draft must match the independent reference",
               path="final_draft", tolerance=TRAJECTORY_DRAFT_ABS_M, unit="m"),
        _check("final_angle_vs_reference", "diagnostic", False,
               "report heel and trim differences; no time-stepping angular "
               "accuracy threshold has been justified",
               path="final_angle", unit="deg"),
        _check("scaled_residual_within_limit", "residual_max", True,
               "the scaled equilibrium residual at every accepted state must "
               "stay within the declared solver limit",
               path="max_scaled_residual",
               tolerance=SCALED_RESIDUAL_MAX, unit="-"),
        _check("volume_conservation", "conservation", True,
               "abs(volume_error) <= max(1e-9 m3, 1e-10 * declared transfer "
               "scale)", path="volume_conservation_error_m3",
               tolerance=max(VOLUME_CONSERVATION_ABS_M3,
                             VOLUME_CONSERVATION_RELATIVE * transfer_scale),
               unit="m3"),
        _check("mass_conservation", "conservation", True,
               "abs(mass_error) <= max(1e-9 t, 1e-10 * declared mass scale)",
               path="mass_conservation_error_t",
               tolerance=MASS_CONSERVATION_ABS_T,
               unit="t"),
    ]
    if include_refinement:
        checks.append(_check("transfer_never_reverses_direction", "monotone",
                             True,
                             "no accepted step may reverse the initial flow "
                             "direction; reversal must be prevented by step "
                             "halving, not accepted"))
    return checks


def _reference_spec_single():
    return {
        "waterplane_area_m2": SINGLE_HULL[0] * SINGLE_HULL[1],
        "tank_area_m2": SINGLE_TANK["length_m"] * SINGLE_TANK["beam_m"],
        "tank_height_m": SINGLE_TANK["height_m"],
        "initial_volume_m3": SINGLE_INITIAL_VOLUME_M3,
        "initial_draft_m": SINGLE_DRAFT_M,
        "base_mass_t": SINGLE_DRY_MASS_T,
        "fluid_density_t_m3": RHO_T_M3,
        "aperture_z_m": PAIR_APERTURE[2],
        "discharge_coefficient": PAIR_DISCHARGE_COEFFICIENT,
        "orifice_area_m2": PAIR_ORIFICE_AREA_M2,
        "gravity_m_s2": GRAVITY_M_S2,
    }


def _reference_spec_pair(volumes, sample_times):
    return {
        "hull_length_m": PAIR_HULL[0],
        "hull_beam_m": PAIR_HULL[1],
        "hull_depth_m": PAIR_HULL[2],
        "dry_mass_t": PAIR_DRY_MASS_T,
        "dry_kg_m": PAIR_DRY_KG_M,
        "fluid_density_t_m3": PAIR_DENSITY,
        "tanks": copy.deepcopy(list(PAIR_TANKS)),
        "aperture_y_m": PAIR_APERTURE[1],
        "aperture_z_m": PAIR_APERTURE[2],
        "orifice_area_m2": PAIR_ORIFICE_AREA_M2,
        "discharge_coefficient": PAIR_DISCHARGE_COEFFICIENT,
        "gravity_m_s2": GRAVITY_M_S2,
        "initial_volumes_m3": [float(value) for value in volumes],
        "integration_step_s": PAIR_INTEGRATION_STEP_S,
        "sample_times_s": [float(value) for value in sample_times],
    }


def _box_spec(scale, keel_offset, cg_offset_y, kg=None):
    """Literal box state at a linear scale, with nonzero slopes."""
    length = BOX_LENGTH_M * scale
    beam = BOX_BEAM_M * scale
    depth = BOX_DEPTH_M * scale
    draft = BOX_DRAFT_M * scale
    return {
        "length_m": float(length),
        "beam_m": float(beam),
        "depth_m": float(depth),
        "draft_m": float(draft),
        "p": BOX_P,
        "q": BOX_Q,
        "rho_t_m3": RHO_T_M3,
        "cg_z_m": float((BOX_KG_M if kg is None else kg) * scale),
        "keel_offset_m": float(keel_offset),
        "cg_offset_y_m": float(cg_offset_y),
        "scale": float(scale),
    }


def _transform_tolerances():
    return {
        "geometry_transform": {
            "relative": GEOMETRY_TRANSFORM_RELATIVE,
            "centroid_abs_m": GEOMETRY_TRANSFORM_CENTROID_ABS_M,
            "applies_to": "volume, area, waterplane inertia under the declared "
                          "linear scale law and centroid shifts under mirror "
                          "and datum transforms",
        },
        "solved_transform": {
            "volume_relative": SOLVED_TRANSFORM_VOLUME_RELATIVE,
            "position_abs_m": SOLVED_TRANSFORM_POSITION_ABS_M,
            "angle_abs_deg": SOLVED_TRANSFORM_ANGLE_ABS_DEG,
            "scaled_residual_max": SOLVED_TRANSFORM_RESIDUAL_MAX,
        },
        "reference": {
            "volume_abs_m3": ORACLE_VOLUME_ABS_M3,
            "geometric_abs_m": ORACLE_GEOMETRIC_ABS_M,
            "scaled_residual_max": ORACLE_SCALED_RESIDUAL_MAX,
            "event_time_abs_s": ORACLE_EVENT_TIME_ABS_S,
        },
        "production": {"scaled_residual_max": SCALED_RESIDUAL_MAX},
    }


def _build_scale_cases():
    cases = []
    exponents = {"length_m": 1, "area_m2": 2, "volume_m3": 3, "mass_t": 3,
                 "waterplane_inertia_m4": 4, "dimensionless": 0, "angle_deg": 0}
    for load_state in ("dry", "liquid_loaded"):
        for scale in SCALE_FACTORS:
            tag = f"l{str(scale).replace('.', 'p')}"
            case_id = f"transform-scale-{load_state.replace('_', '-')}-{tag}"
            spec = _box_spec(scale, 0.0, 0.0)
            inputs = {
                "box": spec,
                "scale_factor": float(scale),
                "reference_scale_factor": 1.0,
                "load_state": load_state,
                "relation_exponents": dict(exponents),
                "target": "StationedHull.integrate",
                "liquid_volume_fraction": 0.5 if load_state == "liquid_loaded"
                                          else 0.0,
            }
            if load_state == "liquid_loaded":
                inputs["liquid_tank"] = {
                    "id": f"scale-tank-{tag}",
                    "length_m": 8.0 * scale, "beam_m": 4.0 * scale,
                    "height_m": 4.0 * scale, "x_m": 2.0 * scale,
                    "y_m": 1.0 * scale, "keel_to_bottom_m": 0.0,
                    "permeability": 1.0,
                }
            checks = [
                _check("status_flag_matches", "status", True,
                       "the solved status must equal the declared stop class"),
                _check("scaled_residual_within_limit", "residual_max", True,
                       "the scaled residual must stay within the solver limit",
                       path="max_scaled_residual",
                       tolerance=SOLVED_TRANSFORM_RESIDUAL_MAX, unit="-"),
                _check("volume_relative_vs_reference", "relative", True,
                       "the produced volume must match the analytic value at "
                       "this scale within the relative budget",
                       path="volume_m3",
                       tolerance=GEOMETRY_TRANSFORM_RELATIVE, unit="-"),
                _check("buoyancy_axis_vs_reference", "absolute", True,
                       "each buoyancy axis must match the analytic value at "
                       "this scale",
                       path="buoyancy_centre_m",
                       tolerance=GEOMETRY_TRANSFORM_CENTROID_ABS_M, unit="m"),
                _check("scale_exponent_law", "relation", True,
                       "the produced value must follow the declared power of "
                       "the scale factor relative to lambda=1"),
                _check("angles_invariant", "relation", True,
                       "heel and trim must be unchanged by the linear scale"),
            ]
            cases.append({
                "schema": CASE_SCHEMA,
                "id": case_id,
                "kind": "transform.scale_linear",
                "family": "transform_scale",
                "group": f"scale-{load_state}",
                "suite": "quick",
                "in_suites": {"quick": True, "extended": False, "all": True},
                "title": f"linear scale x{scale} ({load_state}) with nonzero p/q",
                "inputs": inputs,
                "expected": {
                    "status": "accepted",
                    "reason": None,
                    "stop_class": "completed",
                    "crosses_hydraulic_equilibrium": False,
                    "requires_reversal": False,
                    "checks": checks,
                },
                "tolerances": _transform_tolerances(),
                "tolerance_profile": "transform-geometry-relative-v1",
                "method": {"method_version": "loaded-projected-equilibrium-2",
                           "target": "stability.solve_loaded_equilibrium"},
                "source": dict(_PROVENANCE),
                "estimate": False,
                "reference": {"oracle": "wall-sided-box-reference-2",
                              "precision": "declared-before-run"},
                "relation": {
                    "scale_factor": float(scale),
                    "load_state": load_state,
                    "exponents": dict(exponents),
                    "p": BOX_P, "q": BOX_Q,
                    "identical": ["heel_deg", "trim_deg", "gm_over_scale"],
                },
            })
    return cases


def _build_mirror_cases():
    cases = []
    for load_state in ("dry", "liquid_loaded"):
        base = f"transform-mirror-{load_state.replace('_', '-')}"
        identical = ["displacement_t", "trim_deg", "volume_m3", "buoyancy_x_m",
                     "buoyancy_z_m"]
        reversed_law = ["buoyancy_y_m", "cg_y_m", "gz_m", "heel_deg"]
        for mirrored in (False, True):
            case_id = base + ("-reflected" if mirrored else "")
            # The transverse offset is the asymmetric load being reflected:
            # a positive CG offset produces positive heel and must produce
            # negative heel after mirroring, so both the load and the tank
            # that carries the liquid are negated together.
            signed_q = -BOX_Q if mirrored else BOX_Q
            bz = BOX_DRAFT_M / 2.0 + (BOX_P ** 2 * BOX_LENGTH_M ** 2
                                     + signed_q ** 2 * BOX_BEAM_M ** 2) / (24.0 * BOX_DRAFT_M)
            offset_y = signed_q * (BOX_BEAM_M ** 2 / (12.0 * BOX_DRAFT_M)
                                   + bz - BOX_KG_M)
            spec = _box_spec(1.0, 0.0, offset_y)
            spec["q"] = signed_q
            inputs = {
                "box": spec,
                "mirrored": bool(mirrored),
                "mirror_partner": base + ("-reflected" if not mirrored else ""),
                "load_state": load_state,
                "target": "solve_loaded_equilibrium with mirrored transverse "
                          "loading",
                "cg_offset_y_m": float(offset_y),
                "liquid_tank": {
                    "id": f"mirror-tank-{'stbd' if not mirrored else 'port'}",
                    "length_m": 8.0, "beam_m": 4.0, "height_m": 4.0,
                    "x_m": 0.0, "y_m": 1.0 if not mirrored else -1.0,
                    "keel_to_bottom_m": 0.0, "permeability": 1.0,
                },
                "liquid_volume_fraction": 0.5 if load_state == "liquid_loaded"
                                          else 0.0,
            }
            checks = [
                _check("status_flag_matches", "status", True,
                       "the solved status must equal the declared stop class"),
                _check("scaled_residual_within_limit", "residual_max", True,
                       "the scaled residual must stay within the solver limit",
                       path="max_scaled_residual",
                       tolerance=SOLVED_TRANSFORM_RESIDUAL_MAX, unit="-"),
                _check("mirror_invariant_volume", "relation", True,
                       "volume and mass must be identical under the mirror"),
                _check("mirror_invariant_longitudinal", "relation", True,
                       "Bx and trim must be identical under the mirror"),
                _check("mirror_reverses_transverse", "relation", True,
                       "By, Gy, GZ and heel must reverse sign under the mirror"),
                _check("volume_relative_vs_reference", "relative", True,
                       "volume must match the analytic reference",
                       path="volume_m3",
                       tolerance=GEOMETRY_TRANSFORM_RELATIVE, unit="-"),
            ]
            cases.append({
                "schema": CASE_SCHEMA,
                "id": case_id,
                "kind": "transform.mirror",
                "family": "transform_mirror",
                "group": f"mirror-{load_state}",
                "suite": "quick",
                "in_suites": {"quick": True, "extended": False, "all": True},
                "title": f"{'reflected' if mirrored else 'straight'} "
                         f"{load_state} mirror with nonzero p/q",
                "inputs": inputs,
                "expected": {
                    "status": "accepted", "reason": None,
                    "stop_class": "completed",
                    "crosses_hydraulic_equilibrium": False,
                    "requires_reversal": False, "checks": checks,
                },
                "tolerances": _transform_tolerances(),
                "tolerance_profile": "transform-solved-sign-v1",
                "method": {"method_version": "loaded-projected-equilibrium-2",
                           "target": "stability.solve_loaded_equilibrium"},
                "source": dict(_PROVENANCE),
                "estimate": False,
                "reference": {"oracle": "wall-sided-box-reference-2",
                              "precision": "declared-before-run"},
                "relation": {
                    "load_state": load_state,
                    "p": BOX_P, "q": BOX_Q,
                    "identical": sorted(identical),
                    "sign_reversed": sorted(reversed_law),
                    "partner": base + ("-reflected" if not mirrored else ""),
                },
            })
    return cases


def _build_datum_cases():
    cases = []
    for shift in (0.0, 13.25):
        case_id = "transform-datum-shift-0" if shift == 0.0 \
            else "transform-datum-shift-13p25"
        # The hull, its declared keel and the waterline all shift together, so
        # the *absolute* CG moves with the datum while the keel-relative KG
        # stays put.  Declaring kg independently of the shift is what makes the
        # keel-relative/absolute distinction observable rather than assumed.
        spec = _box_spec(1.0, shift, 1.25 * BOX_BEAM_M)
        spec["cg_z_m"] = float(BOX_KG_M + shift)
        inputs = {
            "box": spec,
            "keel_offset_m": float(shift),
            "waterline_d_m": float(BOX_DRAFT_M + shift),
            "cg_keel_m": float(BOX_KG_M),
            "tank_keel_to_bottom_m": 0.0,
            "aperture_z_keel_m": PAIR_APERTURE[2],
            "partner": ("transform-datum-shift-13p25" if shift == 0.0
                        else "transform-datum-shift-0"),
            "target": "hull z, keel_offset_m and waterline d shift together",
        }
        checks = [
            _check("status_flag_matches", "status", True,
                   "the solved status must equal the declared stop class"),
            _check("scaled_residual_within_limit", "residual_max", True,
                   "the scaled residual must stay within the solver limit",
                   path="max_scaled_residual",
                   tolerance=SOLVED_TRANSFORM_RESIDUAL_MAX, unit="-"),
            _check("keel_relative_invariants", "relation", True,
                   "KG, tank bottom, aperture height, draft, heel and trim "
                   "must be unchanged by the datum shift"),
            _check("absolute_shift_applied", "relation", True,
                   "cg_z, buoyancy_centre_z and waterline_d must move by "
                   "exactly the declared shift"),
        ]
        cases.append({
            "schema": CASE_SCHEMA,
            "id": case_id,
            "kind": "transform.datum",
            "family": "transform_datum",
            "group": "datum",
            "suite": "quick",
            "in_suites": {"quick": True, "extended": False, "all": True},
            "title": f"z-datum shift by {shift} m with absolute and "
                         "keel-relative fields distinct",
            "inputs": inputs,
            "expected": {
                "status": "accepted", "reason": None,
                "stop_class": "completed",
                "crosses_hydraulic_equilibrium": False,
                "requires_reversal": False, "checks": checks,
            },
            "tolerances": _transform_tolerances(),
            "tolerance_profile": "transform-datum-relative-v1",
            "method": {"method_version": "loaded-projected-equilibrium-2",
                       "target": "stability.solve_loaded_equilibrium"},
            "source": dict(_PROVENANCE),
            "estimate": False,
            "reference": {"oracle": "wall-sided-box-reference-2",
                          "precision": "declared-before-run"},
            "relation": {
                "datum_shift_m": float(shift),
                "keel_relative_invariant": sorted([
                    "aperture_height_m", "cg_keel_m", "draft_m", "heel_deg",
                    "kg_m", "tank_bottom_keel_m", "trim_deg"]),
                "absolute_shift": sorted([
                    "buoyancy_centre_z_m", "cg_z_m", "waterline_d_m"]),
                "partner": ("transform-datum-shift-13p25" if shift == 0.0
                            else "transform-datum-shift-0"),
            },
        })
    return cases


def _build_mesh_cases():
    cases = []
    for stations in MESH_STATION_COUNTS:
        for vertices in MESH_VERTEX_COUNTS:
            diagonal = (stations, vertices) in DIAGONAL_MESHES
            finest = (stations, vertices) == DIAGONAL_MESHES[-1]
            case_id = f"mesh-sta{stations}-vert{vertices}"
            production = {"scaled_residual_max": SCALED_RESIDUAL_MAX}
            if finest:
                production["final_analytic_accuracy"] = {
                    "volume_relative": FINEST_VOLUME_RELATIVE,
                    "buoyancy_axis_abs_m": FINEST_BUOYANCY_AXIS_ABS_M,
                    "draft_abs_m": FINEST_DRAFT_ABS_M,
                    "slope_abs": FINEST_SLOPE_ABS,
                }
            inputs = {
                "semi_axes_m": [20.0, 5.0, 5.0],
                "centre_z_m": 5.0,
                "p": 0.01, "q": 0.1, "waterline_d_m": 4.0,
                "rho_t_m3": RHO_T_M3, "kg_m": 3.0,
                "prescribed_gz_m": 0.15,
                "stations": stations, "section_vertices": vertices,
                "solve_equilibrium": bool(diagonal),
                "refinement_stage": "diagonal" if diagonal else "single_axis",
                "target": "StationedHull.integrate"
                          + (" and solve_loaded_equilibrium"
                             if diagonal else ""),
            }
            checks = [
                _check("status_flag_matches", "status", True,
                       "the integrated status must equal the declared class"),
                _check("all_states_finite", "finite", True,
                       "every integrated quantity must be finite"),
                _check("analytic_volume_relative_error", "relative", True,
                       "the reported discretisation volume error against the "
                       "continuous analytic value must be reported",
                       path="volume_relative_error", unit="-"),
            ]
            if diagonal:
                # Only the three diagonal meshes run the loaded-equilibrium
                # solver, so solver-only guards belong only to them.
                checks.append(_check(
                    "equilibrium_converged_flag", "flag", True,
                    "the loaded equilibrium must report convergence",
                    path="converged"))
                checks.append(_check(
                    "scaled_residual_within_limit", "residual_max", True,
                    "the scaled residual must stay within the declared solver "
                    "limit at this level", path="max_scaled_residual",
                    tolerance=SCALED_RESIDUAL_MAX, unit="-"))
                checks.append(_check(
                    "analytic_volume_within_finest_limit", "relative", finest,
                    "only the finest mesh carries the final analytic accuracy "
                    "limit; coarser levels report their real error without "
                    "being held to it", path="volume_relative_error",
                    tolerance=FINEST_VOLUME_RELATIVE, unit="-"))
                checks.append(_check(
                    "analytic_buoyancy_axis_within_finest_limit", "absolute",
                    finest, "only the finest mesh carries the final buoyancy "
                    "axis accuracy limit", path="buoyancy_axis_error",
                    tolerance=FINEST_BUOYANCY_AXIS_ABS_M, unit="m"))
                checks.append(_check(
                    "analytic_draft_within_finest_limit", "absolute", finest,
                    "only the finest mesh carries the final draft accuracy "
                    "limit", path="draft_error",
                    tolerance=FINEST_DRAFT_ABS_M, unit="m"))
                checks.append(_check(
                    "analytic_slope_within_finest_limit", "absolute", finest,
                    "only the finest mesh carries the final slope accuracy "
                    "limit", path="slope_error",
                    tolerance=FINEST_SLOPE_ABS, unit="-"))
            cases.append({
                "schema": CASE_SCHEMA,
                "id": case_id,
                "kind": "mesh.ellipsoid_refinement",
                "family": "mesh",
                "group": "ellipsoid-joint-mesh",
                "suite": "extended",
                "in_suites": {
                    "quick": diagonal, "extended": True, "all": True},
                "title": f"ellipsoid {stations} stations x {vertices} vertices"
                         + (" with equilibrium" if diagonal else ""),
                "inputs": inputs,
                "expected": {
                    "status": "accepted", "reason": None,
                    "stop_class": "completed",
                    "crosses_hydraulic_equilibrium": False,
                    "requires_reversal": False, "checks": checks,
                },
                "tolerances": {
                    "geometry_transform": {
                        "relative": GEOMETRY_TRANSFORM_RELATIVE,
                        "centroid_abs_m": GEOMETRY_TRANSFORM_CENTROID_ABS_M,
                    },
                    "solved_transform": {
                        "volume_relative": SOLVED_TRANSFORM_VOLUME_RELATIVE,
                        "position_abs_m": SOLVED_TRANSFORM_POSITION_ABS_M,
                        "angle_abs_deg": SOLVED_TRANSFORM_ANGLE_ABS_DEG,
                        "scaled_residual_max": SOLVED_TRANSFORM_RESIDUAL_MAX,
                    },
                    "reference": {
                        "volume_abs_m3": ORACLE_VOLUME_ABS_M3,
                        "geometric_abs_m": ORACLE_GEOMETRIC_ABS_M,
                        "scaled_residual_max": ORACLE_SCALED_RESIDUAL_MAX,
                        "event_time_abs_s": ORACLE_EVENT_TIME_ABS_S,
                    },
                    "production": production,
                },
                "tolerance_profile": (
                    "analytic-geometry-fine-v1" if finest
                    else "analytic-geometry-coarse-v1"),
                "method": {"method_version": "loaded-projected-equilibrium-2",
                           "target": "geometry.StationedHull.integrate"},
                "source": dict(_PROVENANCE),
                "estimate": False,
                "reference": {"oracle": "sliced-ellipsoid-reference-3",
                              "precision": "declared-before-run"},
                "relation": {
                    "station_count": stations,
                    "section_vertex_count": vertices,
                    "on_diagonal": bool(diagonal),
                    "final_accuracy_limits_apply": bool(finest),
                    "refinement_ladder": [list(item) for item in DIAGONAL_MESHES],
                },
            })
    return cases


def _tank_payload(tank_id, length, beam, height, x, y, bottom, density,
                  initial_volume):
    return {
        "id": tank_id, "length_m": length, "beam_m": beam, "height_m": height,
        "x_m": x, "y_m": y, "keel_to_bottom_m": bottom, "permeability": 1.0,
        "free_surface": True, "fluid_density_t_m3": density,
        "initial_volume_m3": initial_volume, "source": dict(_NO_ESTIMATE),
        "estimate": False,
    }


def _connection_payload(conn_id, from_id, to_id, xyz, area, density, cd,
                        open_flag=True):
    return {
        "id": conn_id, "from": from_id, "to": to_id,
        "x_m": xyz[0], "y_m": xyz[1], "z_m": xyz[2], "area_m2": area,
        "discharge_coefficient": cd, "fluid_density_t_m3": density,
        "open": open_flag, "source": dict(_NO_ESTIMATE), "estimate": False,
    }


def _project_payload(length, beam, depth, dry_mass, dry_kg):
    section = [[-beam / 2.0, 0.0], [beam / 2.0, 0.0],
               [beam / 2.0, depth], [-beam / 2.0, depth]]
    stations = [[-length / 2.0 + length * index / 20.0,
                 [[point[0], point[1]] for point in section]]
                for index in range(21)]
    return {
        "schema": PROJECT_SCHEMA,
        "id": "core-verification-box",
        "name": "Core verification wall-sided box",
        "revision": 0,
        "units": {"length": "m", "mass": "t", "speed": "kn", "power": "kW",
                  "angle": "deg"},
        "coordinates": {"x_positive": "forward", "x_origin": "midships",
                        "y_positive": "starboard", "z_origin": "keel"},
        "hull": {"lwl_m": length, "beam_m": beam, "depth_m": depth},
        "geometry": {
            "kind": "offsets", "keel_offset_m": 0.0,
            "source": {"kind": "analytic_rectangular_prism"},
            "estimate": False,
            "offsets": {"schema": "plimsoll-section-polygons-1",
                        "stations": stations},
        },
        "weight_groups": [{
            "id": "dry", "label": "Dry mass", "required": True,
            "items": [{"id": "dry-mass", "mass_t": dry_mass, "x_m": 0.0,
                       "y_m": 0.0, "kg_m": dry_kg,
                       "source": {"kind": "declared_verification_fixture"},
                       "estimate": False}],
        }],
        "loading_conditions": [{"id": "normal", "label": "Normal",
                                "reference_displacement_t": dry_mass,
                                "overrides": {}}],
        "systems": {}, "compartments": [], "openings": [],
        "opening_definition": "supplied", "sources": {},
    }


def _single_scenario(duration, step):
    return {
        "schema": SCENARIO_SCHEMA,
        "id": "single-sea-coupled-box",
        "duration_s": float(duration),
        "time_step_s": float(step),
        "source": {"kind": "declared_verification_fixture"},
        "estimate": False,
        "sea": {"id": "sea", "fluid_density_t_m3": RHO_T_M3,
                "source": dict(_NO_ESTIMATE), "estimate": False},
        "tanks": [_tank_payload("centre", SINGLE_TANK["length_m"],
                                SINGLE_TANK["beam_m"], SINGLE_TANK["height_m"],
                                SINGLE_TANK["x_m"], SINGLE_TANK["y_m"],
                                SINGLE_TANK["keel_to_bottom_m"], RHO_T_M3,
                                SINGLE_INITIAL_VOLUME_M3)],
        "connections": [_connection_payload(
            "sea-hole", "sea", "centre", PAIR_APERTURE,
            PAIR_ORIFICE_AREA_M2, RHO_T_M3, PAIR_DISCHARGE_COEFFICIENT)],
        "openings": [],
    }


def _pair_scenario(duration, step, volumes):
    return {
        "schema": SCENARIO_SCHEMA,
        "id": "asymmetric-two-tank-free-float",
        "duration_s": float(duration),
        "time_step_s": float(step),
        "source": {"kind": "declared_verification_fixture"},
        "estimate": False,
        "sea": {"id": "sea", "fluid_density_t_m3": PAIR_DENSITY,
                "source": dict(_NO_ESTIMATE), "estimate": False},
        "tanks": [
            _tank_payload("port", PAIR_TANKS[0]["length_m"],
                          PAIR_TANKS[0]["beam_m"], PAIR_TANKS[0]["height_m"],
                          0.0, PAIR_TANKS[0]["centre_y_m"],
                          PAIR_TANKS[0]["keel_to_bottom_m"], PAIR_DENSITY,
                          volumes[0]),
            _tank_payload("starboard", PAIR_TANKS[1]["length_m"],
                          PAIR_TANKS[1]["beam_m"], PAIR_TANKS[1]["height_m"],
                          0.0, PAIR_TANKS[1]["centre_y_m"],
                          PAIR_TANKS[1]["keel_to_bottom_m"], PAIR_DENSITY,
                          volumes[1]),
        ],
        "connections": [_connection_payload(
            "internal-hole", "port", "starboard", PAIR_APERTURE,
            PAIR_ORIFICE_AREA_M2, PAIR_DENSITY, PAIR_DISCHARGE_COEFFICIENT)],
        "openings": [],
    }


def _flooding_tolerances(volume_tolerance):
    return {
        "geometry_transform": {
            "relative": GEOMETRY_TRANSFORM_RELATIVE,
            "centroid_abs_m": GEOMETRY_TRANSFORM_CENTROID_ABS_M,
        },
        "solved_transform": {
            "volume_relative": SOLVED_TRANSFORM_VOLUME_RELATIVE,
            "position_abs_m": SOLVED_TRANSFORM_POSITION_ABS_M,
            "angle_abs_deg": SOLVED_TRANSFORM_ANGLE_ABS_DEG,
            "scaled_residual_max": SOLVED_TRANSFORM_RESIDUAL_MAX,
        },
        "reference": {
            "volume_abs_m3": ORACLE_VOLUME_ABS_M3,
            "geometric_abs_m": ORACLE_GEOMETRIC_ABS_M,
            "scaled_residual_max": ORACLE_SCALED_RESIDUAL_MAX,
            "event_time_abs_s": ORACLE_EVENT_TIME_ABS_S,
        },
        "production": {
            "trajectory_volume_abs_m3": TRAJECTORY_VOLUME_ABS_M3,
            "trajectory_volume_relative": TRAJECTORY_VOLUME_RELATIVE,
            "draft_abs_m": TRAJECTORY_DRAFT_ABS_M,
            "scaled_residual_max": SCALED_RESIDUAL_MAX,
            "volume_conservation_abs_m3": VOLUME_CONSERVATION_ABS_M3,
            "volume_conservation_relative": VOLUME_CONSERVATION_RELATIVE,
            "mass_conservation_abs_t": MASS_CONSERVATION_ABS_T,
            "mass_conservation_relative": MASS_CONSERVATION_RELATIVE,
            "transfer_volume_tolerance_m3": volume_tolerance,
        },
    }


def _long_case(scenario_name, duration, step):
    duration_tag = "60s" if duration == 60.0 else "300s"
    step_tag = str(step).replace(".", "p")
    case_id = f"flooding-{scenario_name.replace('_', '-')}-{duration_tag}-dt{step_tag}"
    if scenario_name == "single_sea_coupled_box":
        scenario = _single_scenario(duration, step)
        reference_spec = _reference_spec_single()
        # 5 s is the published analytic anchor for this fixture and the
        # requested duration is the replay endpoint; both are declared sample
        # instants so the reference is evaluated exactly, never interpolated.
        sample_times = [5.0, float(duration)]
        declared_transfer = 25.0 / 3.0
        stop_class = ("scheduled_completion" if duration < 62.72232718774828
                      else "hydraulic_equilibrium_tolerance")
        project = _project_payload(SINGLE_HULL[0], SINGLE_HULL[1],
                                   SINGLE_HULL[2], SINGLE_DRY_MASS_T,
                                   SINGLE_DRY_KG_M)
    else:
        scenario = _pair_scenario(duration, step, (5.0, 6.0))
        reference_spec = _reference_spec_pair((5.0, 6.0), [float(duration)])
        sample_times = [float(duration)]
        declared_transfer = 5.0 / 3.0
        stop_class = "hydraulic_equilibrium_tolerance"
        project = _project_payload(PAIR_HULL[0], PAIR_HULL[1], PAIR_HULL[2],
                                   PAIR_DRY_MASS_T, PAIR_DRY_KG_M)
    volume_tolerance = max(TRAJECTORY_VOLUME_ABS_M3,
                           TRAJECTORY_VOLUME_RELATIVE * declared_transfer)
    inputs = {
        "scenario_name": scenario_name,
        "scenario_schema": SCENARIO_SCHEMA,
        "duration_s": float(duration),
        "time_step_s": float(step),
        "project": project,
        "scenario": scenario,
        "condition_id": "normal",
        "reference_spec": reference_spec,
        "sample_times_s": sample_times,
        "declared_transferred_volume_scale_m3": float(declared_transfer),
        "declared_mass_scale_t": float(PAIR_DRY_MASS_T
                                       if scenario_name != "single_sea_coupled_box"
                                       else SINGLE_DRY_MASS_T),
        "target": "flooding.simulate_flooding",
        "max_steps": 100000,
        "max_step_halvings": 40,
        "gravity_m_s2": GRAVITY_M_S2,
    }
    return {
        "schema": CASE_SCHEMA,
        "id": case_id,
        "kind": "flooding.long_replay",
        "family": "flooding",
        "group": f"long-{scenario_name}",
        "suite": "extended",
        "in_suites": {"quick": False, "extended": True, "all": True},
        "title": f"{scenario_name} {duration:g} s at dt={step:g} s",
        "inputs": inputs,
        "expected": {
            "status": "completed" if stop_class in (
                "scheduled_completion", "hydraulic_equilibrium_tolerance")
                else stop_class,
            "reason": STOP_REASONS.get(stop_class),
            "stop_class": stop_class,
            "crosses_hydraulic_equilibrium": False,
            "requires_reversal": False,
            "checks": _flooding_checks(volume_tolerance, declared_transfer,
                                       include_refinement=False),
        },
        "tolerances": _flooding_tolerances(volume_tolerance),
        "tolerance_profile": "flooding-trajectory-v1",
        "method": {"method_version": "connected-quasi-static-flooding-3",
                   "kernel_method_version": "vented-orifice-network-2",
                   "target": "flooding.simulate_flooding"},
        "source": dict(_PROVENANCE),
        "estimate": False,
        "reference": {"oracle": "flooding-reference-3",
                      "precision": "declared-before-run"},
        "relation": {
            "scenario_name": scenario_name,
            "duration_s": float(duration),
            "time_step_s": float(step),
            "declared_transfer_scale_m3": float(declared_transfer),
            "piecewise_constant_after_equilibrium": True,
            "attitude_feedback_required": scenario_name != "single_sea_coupled_box",
        },
    }


def _build_flooding_cases():
    cases = []
    for scenario_name in ("single_sea_coupled_box",
                          "two_tank_asymmetric_free_float"):
        for duration in LONG_DURATIONS_S:
            for step in LONG_TIME_STEPS_S:
                cases.append(_long_case(scenario_name, duration, step))

    # Opposite-initial-head controls: both flow directions on the same pair.
    for direction, volumes in (("port_to_starboard", (5.0, 6.0)),
                               ("starboard_to_port", (3.0, 8.0))):
        tag = direction.replace("_", "-")
        case_id = f"flooding-control-head-{tag}"
        scenario = _pair_scenario(300.0, 0.25, volumes)
        reference_spec = _reference_spec_pair(volumes, [300.0])
        declared_transfer = abs(5.0 - volumes[0] - 1.0 / 3.0)
        volume_tolerance = max(TRAJECTORY_VOLUME_ABS_M3,
                               TRAJECTORY_VOLUME_RELATIVE * declared_transfer)
        inputs = {
            "scenario_name": "two_tank_asymmetric_free_float",
            "scenario_schema": SCENARIO_SCHEMA,
            "duration_s": 300.0,
            "time_step_s": 0.25,
            "project": _project_payload(PAIR_HULL[0], PAIR_HULL[1],
                                        PAIR_HULL[2], PAIR_DRY_MASS_T,
                                        PAIR_DRY_KG_M),
            "scenario": scenario,
            "condition_id": "normal",
            "reference_spec": reference_spec,
            "sample_times_s": [300.0],
            "declared_transferred_volume_scale_m3": float(declared_transfer),
            "declared_mass_scale_t": float(PAIR_DRY_MASS_T),
            "initial_volume_port_m3": float(volumes[0]),
            "initial_volume_starboard_m3": float(volumes[1]),
            "initial_flow_direction": direction,
            "target": "flooding.simulate_flooding",
            "max_steps": 100000,
            "max_step_halvings": 40,
            "gravity_m_s2": GRAVITY_M_S2,
        }
        cases.append({
            "schema": CASE_SCHEMA,
            "id": case_id,
            "kind": "flooding.control_head_direction",
            "family": "flooding",
            "group": "control-head-direction",
            "suite": "extended",
            "in_suites": {"quick": False, "extended": True, "all": True},
            "title": f"opposite initial head, {direction.replace('_', ' ')}",
            "inputs": inputs,
            "expected": {
                "status": "completed",
                "reason": STOP_REASONS["hydraulic_equilibrium_tolerance"],
                "stop_class": "hydraulic_equilibrium_tolerance",
                "crosses_hydraulic_equilibrium": False,
                "requires_reversal": False,
                "checks": _flooding_checks(volume_tolerance, declared_transfer,
                                           include_refinement=True),
            },
            "tolerances": _flooding_tolerances(volume_tolerance),
            "tolerance_profile": "flooding-control-v1",
            "method": {"method_version": "connected-quasi-static-flooding-3",
                       "kernel_method_version": "vented-orifice-network-2",
                       "target": "flooding.simulate_flooding"},
            "source": dict(_PROVENANCE),
            "estimate": False,
            "reference": {"oracle": "flooding-reference-3",
                          "precision": "declared-before-run"},
            "relation": {
                "opposite_head_control": True,
                "flow_direction": direction,
                "initial_volumes_m3": [float(volumes[0]), float(volumes[1])],
                "declared_transfer_scale_m3": float(declared_transfer),
            },
        })

    # Known model boundary: the tank provably reaches capacity.
    boundary_spec = dict(_reference_spec_single())
    boundary_spec["tank_height_m"] = 1.0
    boundary_spec["initial_volume_m3"] = 4.0
    boundary_spec["base_mass_t"] = 405.9
    boundary_spec["tank_capacity_m3"] = 8.0
    boundary_scenario = _single_scenario(60.0, 0.25)
    boundary_scenario["tanks"][0]["height_m"] = 1.0
    boundary_scenario["tanks"][0]["initial_volume_m3"] = 4.0
    boundary_project = _project_payload(
        SINGLE_HULL[0], SINGLE_HULL[1], SINGLE_HULL[2], 405.9, SINGLE_DRY_KG_M)
    cases.append({
        "schema": CASE_SCHEMA,
        "id": "flooding-control-boundary-receiver-capacity",
        "kind": "flooding.control_model_boundary",
        "family": "flooding",
        "group": "control-model-boundary",
        "suite": "extended",
        "in_suites": {"quick": False, "extended": True, "all": True},
        "title": "known model boundary: receiver reaches tank capacity",
        "inputs": {
            "scenario_name": "single_sea_coupled_box",
            "scenario_schema": SCENARIO_SCHEMA,
            "duration_s": 60.0, "time_step_s": 0.25,
            "project": boundary_project, "scenario": boundary_scenario,
            "condition_id": "normal",
            "reference_spec": boundary_spec,
            "sample_times_s": [60.0],
            "declared_transferred_volume_scale_m3": 12.5,
            "declared_mass_scale_t": 405.9,
            "target": "flooding.simulate_flooding",
            "max_steps": 100000, "max_step_halvings": 40,
            "gravity_m_s2": GRAVITY_M_S2,
        },
        "expected": {
            "status": "model_limit",
            "reason": STOP_REASONS["model_limit"],
            "stop_class": "model_limit",
            "crosses_hydraulic_equilibrium": False,
            "requires_reversal": False,
            "checks": _flooding_checks(TRAJECTORY_VOLUME_ABS_M3, 12.5,
                                       include_refinement=False),
        },
        "tolerances": _flooding_tolerances(TRAJECTORY_VOLUME_ABS_M3),
        "tolerance_profile": "flooding-model-boundary-v1",
        "method": {"method_version": "connected-quasi-static-flooding-3",
                   "kernel_method_version": "vented-orifice-network-2",
                   "target": "flooding.simulate_flooding"},
        "source": dict(_PROVENANCE),
        "estimate": False,
        "reference": {"oracle": "receiver-capacity-boundary-1",
                      "precision": "declared-before-run"},
        "relation": {"declared_boundary": "receiver_capacity",
                     "overflow_modelled": False,
                     "early_stop_expected": True},
    })

    # Cancellation control: operational stop after a declared accepted count.
    cancel_after = 6
    cancel_step = 0.5
    cancel_time = cancel_after * cancel_step
    cancel_spec = _reference_spec_single()
    cases.append({
        "schema": CASE_SCHEMA,
        "id": "flooding-control-cancel",
        "kind": "flooding.control_cancel",
        "family": "flooding",
        "group": "control-cancel",
        "suite": "extended",
        "in_suites": {"quick": False, "extended": True, "all": True},
        "title": "cancellation after six accepted steps retains the timeline",
        "inputs": {
            "scenario_name": "single_sea_coupled_box",
            "scenario_schema": SCENARIO_SCHEMA,
            "duration_s": 60.0, "time_step_s": cancel_step,
            "project": _project_payload(SINGLE_HULL[0], SINGLE_HULL[1],
                                        SINGLE_HULL[2], SINGLE_DRY_MASS_T,
                                        SINGLE_DRY_KG_M),
            "scenario": _single_scenario(60.0, cancel_step),
            "condition_id": "normal",
            "reference_spec": cancel_spec,
            "sample_times_s": [cancel_time],
            "cancel_after_accepted_steps": cancel_after,
            "cancel_time_s": cancel_time,
            "declared_transferred_volume_scale_m3": 25.0 / 3.0,
            "declared_mass_scale_t": SINGLE_DRY_MASS_T,
            "target": "flooding.simulate_flooding",
            "max_steps": 100000, "max_step_halvings": 40,
            "gravity_m_s2": GRAVITY_M_S2,
        },
        "expected": {
            "status": "canceled",
            "reason": STOP_REASONS["canceled"],
            "stop_class": "canceled",
            "crosses_hydraulic_equilibrium": False,
            "requires_reversal": False,
            "checks": _flooding_checks(TRAJECTORY_VOLUME_ABS_M3, 25.0 / 3.0,
                                       include_refinement=False),
        },
        "tolerances": _flooding_tolerances(TRAJECTORY_VOLUME_ABS_M3),
        "tolerance_profile": "flooding-cancel-v1",
        "method": {"method_version": "connected-quasi-static-flooding-3",
                   "kernel_method_version": "vented-orifice-network-2",
                   "target": "flooding.simulate_flooding"},
        "source": dict(_PROVENANCE),
        "estimate": False,
        "reference": {"oracle": "cancellation-control-1",
                      "precision": "declared-before-run"},
        "relation": {"cancellation_is_operational": True,
                     "cancel_after_accepted_steps": cancel_after,
                     "last_accepted_time_s": cancel_time},
    })

    # Reversal guard: a coarse step that would overshoot equalisation.
    guard_spec = _reference_spec_pair((5.0, 6.0), [300.0])
    guard_scenario = _pair_scenario(300.0, 1.0, (5.0, 6.0))
    guard_transfer = 5.0 / 3.0
    guard_tolerance = max(TRAJECTORY_VOLUME_ABS_M3,
                          TRAJECTORY_VOLUME_RELATIVE * guard_transfer)
    cases.append({
        "schema": CASE_SCHEMA,
        "id": "flooding-control-reversal-guard",
        "kind": "flooding.control_reversal_guard",
        "family": "flooding",
        "group": "control-reversal-guard",
        "suite": "extended",
        "in_suites": {"quick": False, "extended": True, "all": True},
        "title": "coarse step must not accept a reversed transfer",
        "inputs": {
            "scenario_name": "two_tank_asymmetric_free_float",
            "scenario_schema": SCENARIO_SCHEMA,
            "duration_s": 300.0, "time_step_s": 1.0,
            "project": _project_payload(PAIR_HULL[0], PAIR_HULL[1],
                                        PAIR_HULL[2], PAIR_DRY_MASS_T,
                                        PAIR_DRY_KG_M),
            "scenario": guard_scenario,
            "condition_id": "normal",
            "reference_spec": guard_spec,
            "sample_times_s": [300.0],
            "declared_transferred_volume_scale_m3": float(guard_transfer),
            "declared_mass_scale_t": float(PAIR_DRY_MASS_T),
            "target": "flooding.simulate_flooding",
            "max_steps": 100000, "max_step_halvings": 40,
            "gravity_m_s2": GRAVITY_M_S2,
        },
        "expected": {
            "status": "completed",
            "reason": STOP_REASONS["hydraulic_equilibrium_tolerance"],
            "stop_class": "hydraulic_equilibrium_tolerance",
            "crosses_hydraulic_equilibrium": False,
            "requires_reversal": False,
            "checks": _flooding_checks(guard_tolerance, guard_transfer,
                                       include_refinement=True),
        },
        "tolerances": _flooding_tolerances(guard_tolerance),
        "tolerance_profile": "flooding-reversal-guard-v1",
        "method": {"method_version": "connected-quasi-static-flooding-3",
                   "kernel_method_version": "vented-orifice-network-2",
                   "target": "flooding.simulate_flooding"},
        "source": dict(_PROVENANCE),
        "estimate": False,
        "reference": {"oracle": "flooding-reference-3",
                      "precision": "declared-before-run"},
        "relation": {"reversal_guard": True,
                     "declared_transfer_scale_m3": float(guard_transfer)},
    })
    return cases


_ALL_CASES = None


def _all_cases():
    global _ALL_CASES
    if _ALL_CASES is None:
        cases = []
        cases.extend(_build_scale_cases())
        cases.extend(_build_mirror_cases())
        cases.extend(_build_datum_cases())
        cases.extend(_build_mesh_cases())
        cases.extend(_build_flooding_cases())
        for case in cases:
            if case["family"] == "flooding":
                inputs = case["inputs"]
                # Independent cubic roots, not measured kernel output. Freeze
                # the physical transfer scale consistently across time steps.
                if inputs["scenario_name"] == "two_tank_asymmetric_free_float":
                    initial = inputs["reference_spec"]["initial_volumes_m3"][0]
                    scale = abs(initial - 3.653442604630976)
                    inputs["declared_transferred_volume_scale_m3"] = scale
                    case["relation"]["declared_transfer_scale_m3"] = scale
                    case["tolerances"]["production"]["transfer_volume_tolerance_m3"] = max(1e-4, .01 * scale)
                else:
                    scale = inputs["declared_transferred_volume_scale_m3"]
                for check in case["expected"]["checks"]:
                    if check["name"] == "mass_conservation":
                        check["tolerance"] = max(1e-9, 1e-10 * inputs["declared_mass_scale_t"])
                    elif check["name"] == "volume_conservation":
                        check["tolerance"] = max(1e-9, 1e-10 * scale)
                    elif check["name"] == "final_volume_vs_reference":
                        check["tolerance"] = case["tolerances"]["production"]["transfer_volume_tolerance_m3"]
                    if check["name"] in ("final_volume_vs_reference", "final_draft_vs_reference"):
                        check["required"] = case["kind"] == "flooding.long_replay" and inputs["time_step_s"] == .125
            elif case["kind"] == "transform.scale_linear":
                for check in case["expected"]["checks"]:
                    if check["name"] == "buoyancy_axis_vs_reference":
                        check["description"] = "same finite station mesh centroid obeys declared scale law; continuous centroid mismatch is diagnostic"
                        check["kind"] = "relation"
        _ALL_CASES = cases
    return [copy.deepcopy(case) for case in _ALL_CASES]


def build_cases(suite):
    """Return the frozen case list for ``suite``.

    ``quick`` is the bounded deterministic subset, ``extended`` carries the
    complete matrix, and ``all`` is the deduplicated union.  Every returned
    dictionary is a fresh deep copy, so a caller may mutate it freely.
    """
    if suite not in SUITES:
        raise ValueError(f"unknown verification suite: {suite!r}; "
                         f"expected one of {SUITES}")
    cases = _all_cases()
    if suite == "all":
        selected = cases
    else:
        selected = [case for case in cases if case["in_suites"][suite]]
    # ``all`` deduplicates by id; overlapping quick/extended cases are the same
    # frozen object, so the union is stable and order-independent.
    seen = set()
    unique = []
    for case in selected:
        if case["id"] in seen:
            continue
        seen.add(case["id"])
        unique.append(case)
    return unique


def _self_check():
    """Validate the frozen manifest without executing any kernel."""
    problems = []
    cases = _all_cases()
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        problems.append("duplicate case id")
    for case in cases:
        try:
            import json

            json.dumps(case, sort_keys=True, allow_nan=False)
        except Exception as error:  # pragma: no cover - manifest guard
            problems.append(f"{case['id']}: not strict JSON ({error})")
        if case["expected"]["stop_class"] not in STOP_CLASSES:
            problems.append(f"{case['id']}: unknown stop class")
    return problems


if __name__ == "__main__":  # pragma: no cover - manual inspection
    import json

    print(json.dumps({"problems": _self_check(),
                      "counts": {suite: len(build_cases(suite))
                                 for suite in SUITES}}, indent=2))
