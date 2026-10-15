"""Independent analytic and boundary anchors for inclined-equilibrium roll stiffness.

Every expected number below is derived from the continuous formulas pinned by
``docs/plimsoll-1.0/inclined-small-angle-stability-design.md``. Nothing is
manufactured from the kernel's own output, and no loading quantity is taken
from a production equilibrium solver: the analytic hull, mass and CG come from
closed-form integration of the same continuous body.

Derivations (geometry datum, keel at z = 0, rho = 1.025 t/m3)
----------------------------------------------------------
1. Continuous rectangular barge, length L, beam B, mean draught d, deck and
   keel clear of every station, waterline ``z = d + p*x`` with p = tan(trim)::

       per-station immersed area    A(x) = B*(d + p*x)          (heel independent)
       displacement                V    = B*d*L
       centre of buoyancy          xB   = p*L**2/(12*d)
                                   zB   = d/2 + p**2*L**2/(24*d)
       transverse shift at heel q  dyB  = q*B**2/(12*d)
       vertical shift              dzB  = q**2*B**2/(24*d)
       GZ(q) with trim held        = q*(B**2/(12*d) + zB - zG) + O(q**3)

   so the fixed-trim waterplane-slope stiffness is ``B**2/(12*d) + zB - zG``.
   The physical roll angle is *not* the slope angle: a probe normal
   ``n = (-p,-q,1)/sqrt(1+p**2+q**2)`` measured against the baseline normal
   gives ``tan(phi) = q/sqrt(1+p**2)``. The free equilibrium stiffness in the
   physical angle is therefore

       GM = sqrt(1 + p**2) * (B**2/(12*d) + zB - zG)

   which is the pinned continuous formula. Keeping the slope-angle convention
   returns the inner factor instead (0.8324859 m at 15 deg against
   0.8618535 m), a 3.5 % error this file asserts against.

2. Free-trim counterexample. Shift every station's transverse centre to
   ``y = k*x``. A shifted section is no longer heel independent::

       A(x) = B*(d + x*(p + q*k))      ->  xB = (p + q*k)*L**2/(12*d)
       dyB = k*xB + q*B**2/(12*d)

   Writing ``A0 = L**2/(12*d)``, ``J = B**2/(12*d)`` and ``D = d/2 - zG`` and
   evaluating at the upright free equilibrium (p = q = 0 for a CG at the
   origin), the first-order trim equation is

       (A0 + D)*p + k*A0*q = 0        ->  dp/dq = -k*A0/(A0 + D)

   and the transverse stiffness is ``J + k**2*A0 + D`` with trim locked, or

       GM = J + k**2*A0 + D - (k*A0)**2/(A0 + D) = 0.4979351 m

   with trim free (k = 0.2). The locked-trim value 0.8666667 m is a 74 % error
   and identifies an implementation that never frees trim.

3. Moving liquid. For a rectangular tank of length l and beam b with a free
   surface the transverse free-surface correction is exactly

       dGM = -rho_liquid * l*b**3/12 / m_total

   applied once, because the liquid centroid is recomputed at every attitude
   and no additional FSC may be added. The frozen-solid reference is the same
   hull at the same total mass with the liquid CG frozen at its upright
   position, so the measured difference between the two analyses must equal
   that correction.
"""

import copy
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve()
PACKAGE_DIR = HERE.parents[1]
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

import geometry_analysis  # noqa: E402
import stability  # noqa: E402

METHOD_VERSION = "free_trim_equilibrium_roll_stiffness_v1"
FSC_POLICY = "centroid_geometry_no_additional_fsc"
OLD_ROLL_METHOD = "selected_loading_small_angle_roll_v1"
LENGTH, BEAM, MEAN_DRAFT, DECK, RHO, KG = 20.0, 8.0, 4.0, 12.0, 1.025, 2.8
DISPLACEMENT_T = LENGTH * BEAM * MEAN_DRAFT * RHO          # 656 t
FINE_MESH, COARSE_MESH, REFINE_MESH = 129, 33, 257
# Pinned acceptance: relative 2e-4 and absolute 2e-5 m against the continuous
# analytic value, the absolute term scaled by the geometry scale factor.
RELATIVE_TOLERANCE, ABSOLUTE_TOLERANCE = 2e-4, 2e-5
NEUTRAL_KG = MEAN_DRAFT / 2 + BEAM ** 2 / (12 * MEAN_DRAFT)


def kernel():
    """Return the small-angle kernel, imported late so collection never fails."""
    try:
        import small_angle_stability as module
        return module
    except ModuleNotFoundError:
        pass
    from plimsoll import small_angle_stability as module
    return module


def assert_finite_payload(test, payload, path="$"):
    if payload is None or isinstance(payload, (bool, str, int)):
        return
    if isinstance(payload, float):
        test.assertTrue(math.isfinite(payload), f"{path} must be finite, got {payload!r}")
    elif isinstance(payload, dict):
        for key, value in payload.items():
            test.assertIsInstance(key, str, f"{path} keys must be strings")
            assert_finite_payload(test, value, f"{path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            assert_finite_payload(test, value, f"{path}[{index}]")
    else:
        test.fail(f"{path} has an unsupported type {type(payload).__name__}")


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def rectangular_poly(beam=BEAM, bottom=0.0, height=DECK, shear=0.0, x=0.0, scale=1.0, datum=0.0):
    return [[(shear * x + y) * scale, datum + (bottom + z) * scale]
            for y, z in ((-beam / 2, 0.0), (beam / 2, 0.0), (beam / 2, height), (-beam / 2, height))]


def hull_record(stations, keel_offset=0.0):
    return dict(kind="offsets", keel_offset_m=keel_offset,
                source="independent analytic section polygons", estimate=False,
                offsets=dict(schema="plimsoll-section-polygons-1", stations=stations))


def barge_hull(stations=FINE_MESH, *, shear=0.0, scale=1.0, datum=0.0, mirror_y=False, mirror_x=False):
    # A uniform scale multiplies every coordinate by ``scale``; the section shear
    # is applied to the unscaled station coordinate before that scaling.
    rows = []
    for index in range(stations):
        x = -LENGTH / 2 + LENGTH * index / (stations - 1)
        rows.append([x * scale, rectangular_poly(shear=shear, x=x, scale=scale, datum=datum)])
    if mirror_y:
        rows = [[x, [[-y, z] for y, z in poly]] for x, poly in rows]
    if mirror_x:
        rows = [[-x, poly] for x, poly in reversed(rows)]
    return hull_record(rows, keel_offset=datum)


def notch_hull(stations=FINE_MESH):
    """Outer slab z in [2,12] with a central tunnel whose floor sits at z = 4.

    At the 2 m mean draught equilibrium the tunnel floor edge is locally
    coincident with the waterplane while the hull as a whole is partially
    immersed, which the design requires the kernel to reject.
    """
    poly = [[-4.0, 0.0], [4.0, 0.0], [4.0, DECK], [1.0, DECK],
            [1.0, 2.0], [-1.0, 2.0], [-1.0, DECK], [-4.0, DECK]]
    rows = [[-LENGTH / 2 + LENGTH * index / (stations - 1), copy.deepcopy(poly)]
            for index in range(stations)]
    return hull_record(rows)


def trim_slope(trim_deg):
    return math.tan(math.radians(trim_deg))


def buoyancy_centre_xz(trim_deg):
    """Continuous centre of buoyancy at a fixed trim slope (unscaled body)."""
    slope = trim_slope(trim_deg)
    return (slope * LENGTH ** 2 / (12 * MEAN_DRAFT),
            MEAN_DRAFT / 2 + slope * slope * LENGTH ** 2 / (24 * MEAN_DRAFT))


def trim_cg_x(trim_deg, kg=KG, scale=1.0):
    """LCG that makes the continuous body float at ``trim_deg`` (derivation 1)."""
    xb, zb = buoyancy_centre_xz(trim_deg)
    return (xb + trim_slope(trim_deg) * (zb - kg)) * scale


def analytic_box_gm(trim_deg, kg=KG, scale=1.0):
    """Continuous free-trim roll stiffness of the barge (derivation 1).

    Lengths inside the bracket are unscaled body dimensions; a uniform scale
    multiplies the finished stiffness, because every term in it is a length.
    """
    slope = trim_slope(trim_deg)
    _, zb = buoyancy_centre_xz(trim_deg)
    return math.sqrt(1 + slope * slope) * (BEAM ** 2 / (12 * MEAN_DRAFT) + zb - kg) * scale


def analytic_slope_convention_gm(trim_deg, kg=KG):
    """The pinned *wrong* answer: dGZ/d(heel slope) at the same equilibrium."""
    return BEAM ** 2 / (12 * MEAN_DRAFT) + buoyancy_centre_xz(trim_deg)[1] - kg


def analytic_locked_trim_gm(shear, kg=KG):
    """Transverse stiffness of the sheared barge with trim locked (wrong)."""
    return (BEAM ** 2 / (12 * MEAN_DRAFT) + shear ** 2 * LENGTH ** 2 / (12 * MEAN_DRAFT)
            + MEAN_DRAFT / 2 - kg)


def analytic_free_trim_gm(shear, kg=KG):
    """Continuous free-trim roll stiffness of the sheared barge (derivation 2)."""
    a0 = LENGTH ** 2 / (12 * MEAN_DRAFT)
    d = MEAN_DRAFT / 2 - kg
    return BEAM ** 2 / (12 * MEAN_DRAFT) + shear ** 2 * a0 + d - (shear * a0) ** 2 / (a0 + d)


def analytic_shear_dp_dq(shear):
    a0 = LENGTH ** 2 / (12 * MEAN_DRAFT)
    return -shear * a0 / (a0 + MEAN_DRAFT / 2 - KG)


def analytic_slab_gm(draught, kg=KG):
    """Slab hull (depth DECK) without the tunnel: GM = B**2/(12*d) + d/2 - zG."""
    return BEAM ** 2 / (12 * draught) + draught / 2 - kg


def loading_state(mass=DISPLACEMENT_T, *, lcg=0.0, kg=KG, tcg=0.0, complete_mass=True,
                  complete_cg=True, diagnostics=None):
    return dict(complete_mass=complete_mass, complete_cg=complete_cg,
                diagnostics=[] if diagnostics is None else diagnostics,
                values=dict(total_mass_t=mass, lcg_m=lcg, tcg_m=tcg, kg_m=kg),
                effective_items=[dict(id="analytic-solid", mass_t=mass, x_m=lcg, y_m=tcg,
                                      kg_m=kg, source="independent analytic loading",
                                      estimate=False)],
                provenance=dict(estimate=False), uncertainty=dict(status="unknown"),
                condition_id="analytic", project_id="analytic-barge",
                coverage=dict(reference_displacement_t=mass), input_fingerprint="analytic-fixture")


def trimmed_barge(trim_deg=0.0, stations=FINE_MESH, *, scale=1.0, datum=0.0, kg=KG, mass=None,
                  **kwargs):
    """Hull, state and solver seed for the barge floating at ``trim_deg``."""
    hull = barge_hull(stations, scale=scale, datum=datum, **kwargs)
    state = loading_state(DISPLACEMENT_T * scale ** 3 if mass is None else mass,
                          lcg=trim_cg_x(trim_deg, kg, scale), kg=kg * scale)
    return hull, state, dict(initial=dict(trim_deg=trim_deg, heel_deg=0.0))


def tank_dict(identifier="analytic-tank"):
    return dict(id=identifier, length_m=4.0, beam_m=2.0, height_m=2.0, x_m=0.0, y_m=0.0,
                keel_to_bottom_m=0.5, permeability=1.0)


def liquid_case(volume_m3, *, density_t_m3=1.0, kg=KG):
    """Split the analytic 656 t into a solid part and one moving rectangular tank.

    The tank's upright centroid is computed here (fill height = volume/(l*b)),
    so the combined loading reproduces exactly the frozen-solid reference
    state. Returns (hull, state, options, expected_gm, expected_correction).
    """
    tank = tank_dict()
    capacity = tank["length_m"] * tank["beam_m"] * tank["height_m"] * tank["permeability"]
    if not 0.0 <= volume_m3 <= capacity:
        raise ValueError("fixture volume must lie inside the tank capacity")
    mass = DISPLACEMENT_T - volume_m3 * density_t_m3
    liquid_kg = tank["keel_to_bottom_m"] + volume_m3 / (tank["length_m"] * tank["beam_m"]) / 2
    solid_kg = (DISPLACEMENT_T * kg - volume_m3 * density_t_m3 * liquid_kg) / mass
    options = dict(liquid_loads=[dict(tank=tank, volume_m3=volume_m3,
                                      fluid_density_t_m3=density_t_m3)])
    correction = 0.0
    if 0.0 < volume_m3 < capacity:
        correction = (density_t_m3 * tank["length_m"] * tank["beam_m"] ** 3 / 12) / DISPLACEMENT_T
    return barge_hull(), loading_state(mass, kg=solid_kg), options, analytic_box_gm(0.0) - correction, correction


class KernelResultContract:
    """Shared result assertions: a completed number or an explained refusal."""

    def analyze(self, *args, **kwargs):
        return kernel().analyze(*args, **kwargs)

    def assertCompleted(self, result, note=""):
        self.assertEqual(result["method_version"], METHOD_VERSION)
        self.assertEqual(result["status"], "completed", note or result.get("reason"))
        self.assertIsNone(result["reason"], note)
        self.assertTrue(result["definition"], "the restoring definition must be stated")
        self.assertIsInstance(result["base_equilibrium"], dict)
        self.assertTrue(result["validity"]["model_applicable"])
        self.assertIsNone(result["validity"]["historical_validated"])
        self.assertIsNone(result["validity"]["safe"])
        self.assertEqual(result["fsc_policy"], FSC_POLICY)
        self.assertTrue(is_number(result["equilibrium_gm_m"]))
        self.assertTrue(math.isfinite(result["equilibrium_gm_m"]))
        self.assertIsNotNone(result["restoring_sign"])
        json.dumps(result, allow_nan=False)
        assert_finite_payload(self, result)
        return result["equilibrium_gm_m"]

    def assertNoStiffness(self, result, note=""):
        self.assertEqual(result["method_version"], METHOD_VERSION)
        self.assertNotEqual(result["status"], "completed", note)
        self.assertIsNone(result["equilibrium_gm_m"], note)
        self.assertTrue(result["reason"], "an unavailable result must carry a reason")
        self.assertIsNone(result["validity"]["safe"])
        json.dumps(result, allow_nan=False)
        assert_finite_payload(self, result)

    def assertNothingFabricated(self, call, note=""):
        """A rejected request may raise or report unavailable, but never a number."""
        try:
            result = call()
        except (ValueError, TypeError) as error:
            self.assertTrue(str(error), note)
            return
        self.assertNoStiffness(result, note)


class KernelContractTests(KernelResultContract, unittest.TestCase):
    """Identity, controlled-failure and immutability contracts of the kernel."""

    def test_method_identity_and_controlled_result_payload(self):
        hull, state, options = trimmed_barge(0.0)
        result = self.analyze(hull, state, options)
        gm = self.assertCompleted(result)
        self.assertAlmostEqual(gm, analytic_box_gm(0.0), delta=ABSOLUTE_TOLERANCE)
        self.assertEqual(result["input_fingerprint"], state["input_fingerprint"])

    def test_refinement_and_sign_resolution_follow_the_pinned_rule(self):
        hull, state, options = trimmed_barge(15.0)
        result = self.analyze(hull, state, options)
        stiffness = self.assertCompleted(result)
        beam = BEAM
        limit = max(1e-5 * beam, 0.002 * abs(stiffness))
        self.assertGreaterEqual(result["refinement_delta_m"], 0.0)
        self.assertLessEqual(result["refinement_delta_m"], limit)
        self.assertGreaterEqual(result["sign_resolution_m"], result["refinement_delta_m"])
        self.assertGreaterEqual(result["sign_resolution_m"], 1e-6 * beam)

    def test_step_is_keyword_only_finite_and_bounded(self):
        hull, state, options = trimmed_barge(0.0)
        upright = analytic_box_gm(0.0)
        for step in (0.02, 0.2, 0.5):
            measured = self.assertCompleted(self.analyze(hull, state, options, step_deg=step))
            self.assertTrue(math.isclose(measured, upright, rel_tol=RELATIVE_TOLERANCE,
                                         abs_tol=ABSOLUTE_TOLERANCE),
                            f"step_deg={step}: measured {measured!r} against {upright!r}")
        with self.assertRaises(TypeError):
            kernel().analyze(hull, state, options, 0.2)
        for step in (0.0, 0.019, 0.51, 1.0, -0.2, True, False, float("nan"), float("inf"), None, "0.2"):
            self.assertNothingFabricated(
                lambda step=step: self.analyze(hull, state, options, step_deg=step),
                f"step_deg={step!r} must not yield a stiffness")

    def test_options_must_be_an_object_and_prescribed_heel_is_rejected(self):
        hull, state, options = trimmed_barge(0.0)
        for bad in ([], "options", 1, True):
            self.assertNothingFabricated(lambda bad=bad: self.analyze(hull, state, bad),
                                         f"options={bad!r} must not yield a stiffness")
        # A null heel keeps the free transverse equilibrium; any non-null value,
        # including an explicit zero, forces the attitude and proves nothing.
        self.assertCompleted(self.analyze(hull, state, dict(options, heel_deg=None)))
        for prescribed in (0.0, 0, 1.0):
            self.assertNoStiffness(
                self.analyze(hull, state, dict(options, heel_deg=prescribed)),
                f"heel_deg={prescribed!r} is prescribed, not a free equilibrium")

    def test_unknown_mass_cg_and_blocking_diagnostics_never_stiffen(self):
        hull, _, options = trimmed_barge(0.0)
        cases = [loading_state(complete_mass=False), loading_state(complete_cg=False),
                 loading_state(diagnostics=[dict(code="loading.blocking", message="unknown",
                                                 severity="error", path="$", blocking=True)]),
                 loading_state(mass=0.0), loading_state(mass=-1.0), loading_state(tcg=1e9),
                 None, [], dict(loading_state(), values=None), dict(loading_state(), diagnostics=None)]
        for state in cases:
            self.assertNoStiffness(self.analyze(hull, state, options),
                                    f"loading state {state!r} must not yield a stiffness")

    def test_saturated_and_out_of_domain_liquid_never_stiffen(self):
        hull, _, options = trimmed_barge(0.0)
        for mass in (LENGTH * BEAM * DECK * RHO, LENGTH * BEAM * DECK * RHO * 1.1):
            self.assertNoStiffness(self.analyze(hull, loading_state(mass), options),
                                    f"saturation at {mass} t must not yield a stiffness")
        liquid = dict(tank=tank_dict(), volume_m3=4.0, fluid_density_t_m3=1.0)
        for liquids in ([dict(liquid, volume_m3=500.0)],
                        [liquid, dict(liquid, tank=tank_dict("analytic-tank"))],
                        [dict(liquid, fluid_density_t_m3=0.0)],
                        [dict(liquid, tank=dict(tank_dict(), permeability=0.0))],
                        [None]):
            self.assertNoStiffness(self.analyze(hull, loading_state(DISPLACEMENT_T - 4.0),
                                                dict(options, liquid_loads=liquids)),
                                    f"liquid loads {liquids!r} must not yield a stiffness")

    def test_failed_baseline_or_a_single_probe_yields_no_stiffness(self):
        hull, state, options = trimmed_barge(0.0)
        # An iteration budget too small for the trimmed baseline to converge.
        trimmed_hull, trimmed_state, trimmed_options = trimmed_barge(15.0)
        starved = dict(trimmed_options, max_iterations=1)
        self.assertFalse(stability.solve_loaded_equilibrium(
            trimmed_hull, trimmed_state, starved)["converged"])
        self.assertNoStiffness(self.analyze(trimmed_hull, trimmed_state, starved))
        # Heel bounds that contain the free baseline (0 deg) but exclude the
        # negative probe group: only some prescribed attitudes are solvable.
        narrow = dict(options, heel_bounds_deg=[-0.05, 85.0])
        baseline = stability.solve_loaded_equilibrium(hull, state, narrow)
        self.assertTrue(baseline["converged"], baseline.get("diagnostics"))
        rejected = stability.solve_loaded_equilibrium(hull, state, dict(narrow, heel_deg=-0.2))
        self.assertFalse(rejected["converged"])
        self.assertNoStiffness(self.analyze(hull, state, narrow))
        # Neutral baseline: the transverse Jacobian is singular, so no free
        # equilibrium exists to differentiate.
        neutral = loading_state(kg=NEUTRAL_KG)
        self.assertFalse(stability.solve_loaded_equilibrium(hull, neutral)["converged"])
        self.assertNoStiffness(self.analyze(hull, neutral, options))

    def test_geometry_is_prepared_once_and_not_per_perturbation_state(self):
        hull, state, options = trimmed_barge(15.0)
        with patch.object(stability, "_prepare", wraps=stability._prepare) as prepared:
            result = self.analyze(hull, state, options)
        self.assertCompleted(result)
        # One free baseline and six prescribed-heel probes share a single
        # prepared geometry; re-validating per state is the defect guarded here.
        self.assertLessEqual(prepared.call_count, 2,
                             f"geometry was prepared {prepared.call_count} times for 7 states")

    def test_inputs_and_request_are_never_mutated(self):
        hull, state, options = trimmed_barge(15.0)
        before = copy.deepcopy((hull, state, options))
        result = self.assertCompleted(self.analyze(hull, state, options))
        self.assertEqual((hull, state, options), before)
        self.assertEqual(hull, barge_hull(FINE_MESH, datum=0.0))
        self.assertTrue(math.isclose(result, analytic_box_gm(15.0), rel_tol=RELATIVE_TOLERANCE,
                                     abs_tol=ABSOLUTE_TOLERANCE))

    def test_target_trim_study_option_never_moves_the_free_equilibrium(self):
        hull, state, options = trimmed_barge(15.0)
        expected = analytic_box_gm(15.0)
        reference = self.assertCompleted(self.analyze(hull, state, options))
        result = self.assertCompleted(self.analyze(hull, state, dict(options, target_trim_deg=-12.0)))
        self.assertAlmostEqual(result, reference, delta=1e-9)
        self.assertTrue(math.isclose(result, expected, rel_tol=RELATIVE_TOLERANCE,
                                     abs_tol=ABSOLUTE_TOLERANCE))


class ContinuousBoxAnalyticTests(KernelResultContract, unittest.TestCase):
    """Analytic free-trim roll stiffness of the continuous rectangular barge."""

    def stiffness(self, trim_deg=0.0, stations=FINE_MESH, options=None, **kwargs):
        hull, state, seed = trimmed_barge(trim_deg, stations, **kwargs)
        result = kernel().analyze(hull, state, seed if options is None else options)
        self.assertEqual(result["method_version"], METHOD_VERSION, result.get("reason"))
        self.assertEqual(result["status"], "completed", result.get("reason"))
        json.dumps(result, allow_nan=False)
        assert_finite_payload(self, result)
        return result["equilibrium_gm_m"]

    def close(self, measured, expected, scale=1.0, note=""):
        self.assertTrue(math.isclose(measured, expected, rel_tol=RELATIVE_TOLERANCE,
                                     abs_tol=ABSOLUTE_TOLERANCE * scale),
                        f"{note}measured {measured!r} against analytic {expected!r}")

    def test_upright_and_trimmed_boxes_match_the_continuous_formula(self):
        for trim_deg in (0.0, 5.0, -5.0, 15.0, -15.0):
            self.close(self.stiffness(trim_deg), analytic_box_gm(trim_deg),
                       note=f"trim_deg={trim_deg}: ")

    def test_trimmed_box_must_not_return_the_slope_angle_convention(self):
        # At 15 deg the pinned slope-angle answer is 3.4 % low, a gap no
        # tolerance can hide. A kernel that differentiates GZ against the
        # waterplane slope angle, or that renames the upright curve stiffness,
        # cannot pass both assertions.
        measured = self.stiffness(15.0)
        expected = analytic_box_gm(15.0)
        self.close(measured, expected)
        self.assertGreater(abs(measured - analytic_slope_convention_gm(15.0)), 1e-2)

    def test_station_refinement_shrinks_the_quadrature_error(self):
        coarse = self.stiffness(15.0, FINE_MESH)
        fine = self.stiffness(15.0, REFINE_MESH)
        expected = analytic_box_gm(15.0)
        coarse_error, fine_error = abs(coarse - expected), abs(fine - expected)
        self.close(coarse, expected)
        self.close(fine, expected)
        self.assertLess(fine_error, coarse_error)
        self.assertGreater(coarse_error, 4 * fine_error)

    def test_vertical_datum_translation_preserves_the_stiffness(self):
        expected = analytic_box_gm(15.0)
        base = self.stiffness(15.0, datum=0.0)
        shifted = self.stiffness(15.0, datum=137.0)
        self.assertAlmostEqual(base, shifted, delta=1e-9)
        self.close(shifted, expected)

    def test_uniform_scale_scales_the_stiffness_by_length(self):
        scale = 3.0
        measured = self.stiffness(15.0, scale=scale)
        expected = analytic_box_gm(15.0, scale=scale)
        # The scaled hull keeps the same station count over a longer body, so the
        # quadrature error scales with it; only the ratio is required exactly.
        self.assertAlmostEqual(measured / analytic_box_gm(15.0), scale,
                               delta=RELATIVE_TOLERANCE * scale)
        self.close(measured, expected, scale=scale, note="scaled case: ")

    def test_mirrored_hulls_reproduce_the_same_stiffness(self):
        expected = analytic_box_gm(15.0)
        reference = self.stiffness(15.0)
        for mirror_y, mirror_x in ((True, False), (False, True)):
            hull, state, options = trimmed_barge(15.0, mirror_y=mirror_y, mirror_x=mirror_x)
            if mirror_x:
                state["values"]["lcg_m"] *= -1
                state["effective_items"][0]["x_m"] *= -1
            result = kernel().analyze(hull, state, options)
            self.assertEqual(result["status"], "completed", result.get("reason"))
            self.assertAlmostEqual(result["equilibrium_gm_m"], reference, delta=1e-9,
                                   msg=f"mirror_y={mirror_y}, mirror_x={mirror_x}")
            self.close(result["equilibrium_gm_m"], expected,
                       note=f"mirror_y={mirror_y}, mirror_x={mirror_x}: ")

    def test_negative_stiffness_is_preserved_as_an_observed_direction(self):
        measured = self.stiffness(0.0, kg=4.0)
        self.assertLess(measured, 0.0, "a raised centre of gravity stays unstable")
        self.close(measured, analytic_box_gm(0.0, kg=4.0))

    def test_near_neutral_stiffness_is_never_reported_as_a_resolved_positive(self):
        # 20 mm above neutral is still inside the resolved regime, so the sign
        # and the magnitude of a marginally unstable body must survive.
        measured = self.stiffness(0.0, kg=NEUTRAL_KG + 0.02)
        self.close(measured, analytic_box_gm(0.0, kg=NEUTRAL_KG + 0.02))
        self.assertLess(measured, 0.0)
        # Exactly neutral: the free baseline is singular, so nothing may be
        # returned rather than a fabricated positive stiffness.
        neutral = loading_state(kg=NEUTRAL_KG)
        self.assertFalse(stability.solve_loaded_equilibrium(
            barge_hull(), neutral)["converged"])
        self.assertNoStiffness(kernel().analyze(barge_hull(), neutral))


class FreeTrimCounterexampleTests(unittest.TestCase):
    """A sheared hull that can only be right if trim is genuinely free."""

    SHEAR = 0.2

    def stiffness(self, shear, stations=FINE_MESH):
        hull, state, _ = trimmed_barge(0.0, stations, shear=shear)
        result = kernel().analyze(hull, state)
        self.assertEqual(result["method_version"], METHOD_VERSION, result.get("reason"))
        self.assertEqual(result["status"], "completed", result.get("reason"))
        json.dumps(result, allow_nan=False)
        assert_finite_payload(self, result)
        return result["equilibrium_gm_m"]

    def close(self, measured, expected):
        self.assertTrue(math.isclose(measured, expected, rel_tol=RELATIVE_TOLERANCE,
                                     abs_tol=ABSOLUTE_TOLERANCE),
                        f"measured {measured!r} against analytic {expected!r}")

    def test_sheared_box_matches_the_free_trim_formula_not_the_locked_one(self):
        expected = analytic_free_trim_gm(self.SHEAR)
        self.assertAlmostEqual(expected, 0.49793510324483814, places=12)
        for stations in (FINE_MESH, REFINE_MESH):
            measured = self.stiffness(self.SHEAR, stations)
            self.close(measured, expected)
            locked = analytic_locked_trim_gm(self.SHEAR)
            self.assertAlmostEqual(locked, 0.8666666666666671, places=12)
            self.assertGreater(abs(measured - locked), 0.1,
                               f"stations={stations}: locking trim would return 0.8666667 m")

    def test_sheared_box_quadrature_error_shrinks_with_the_mesh(self):
        coarse = self.stiffness(self.SHEAR, COARSE_MESH)
        fine = self.stiffness(self.SHEAR, FINE_MESH)
        expected = analytic_free_trim_gm(self.SHEAR)
        self.close(coarse, expected)
        self.close(fine, expected)
        self.assertLess(abs(fine - coarse), abs(coarse - expected))

    def test_pinned_first_order_trim_response_of_the_sheared_hull(self):
        # Independent restatement of the pinned dp/dq for the same fixture, kept
        # as a documented constant so a change in the analytic case is deliberate.
        self.assertAlmostEqual(analytic_shear_dp_dq(self.SHEAR), -0.22123893805309736, places=12)


class MovingLiquidAnalyticTests(unittest.TestCase):
    """One free-surface correction, from an independently computed tank state."""

    def stiffness(self, *args, **kwargs):
        hull, state, options, _, _ = liquid_case(*args, **kwargs)
        result = kernel().analyze(hull, state, options)
        self.assertEqual(result["method_version"], METHOD_VERSION, result.get("reason"))
        self.assertEqual(result["status"], "completed", result.get("reason"))
        self.assertEqual(result["fsc_policy"], FSC_POLICY)
        json.dumps(result, allow_nan=False)
        assert_finite_payload(self, result)
        return result["equilibrium_gm_m"]

    def test_frozen_solid_reference_is_the_analytic_upright_stiffness(self):
        # An empty tank leaves the analytic 656 t upright state untouched.
        measured = self.stiffness(0.0)
        self.assertTrue(math.isclose(measured, analytic_box_gm(0.0), rel_tol=RELATIVE_TOLERANCE,
                                     abs_tol=ABSOLUTE_TOLERANCE),
                        f"measured {measured!r} against analytic {analytic_box_gm(0.0)!r}")

    def test_moving_liquid_applies_the_free_surface_correction_exactly_once(self):
        reference = self.stiffness(0.0)
        for volume in (4.0, 8.0):
            measured = self.stiffness(volume)
            _, _, _, expected, correction = liquid_case(volume)
            self.assertGreater(correction, 0.0)
            self.assertTrue(math.isclose(measured, expected, rel_tol=RELATIVE_TOLERANCE,
                                         abs_tol=ABSOLUTE_TOLERANCE),
                            f"volume={volume}: measured {measured!r} against analytic {expected!r}")
            difference = measured - reference
            self.assertLess(abs(difference + correction), 2e-6,
                            f"volume={volume}: expected one correction of {-correction!r} m, "
                            f"measured {difference!r}")
            self.assertGreater(abs(difference), 0.9 * correction)
            self.assertLess(abs(difference), 1.1 * correction)

    def test_full_and_empty_tanks_match_the_frozen_reference(self):
        reference = self.stiffness(0.0)
        for volume in (0.0, 16.0):
            self.assertAlmostEqual(self.stiffness(volume), reference, delta=1e-6,
                                   msg=f"volume_m3={volume} must match the frozen reference")


class FailedRefinementTests(KernelResultContract, unittest.TestCase):
    """A refinement that does not converge must refuse, not raise or invent."""

    def test_failed_refinement_through_public_analyze_is_a_controlled_result(self):
        module = kernel()
        hull, state, options = trimmed_barge(0.0)
        # The probe states stay physical; only the measured derivative is made
        # inconsistent, which is exactly the failed-refinement control branch.
        with patch.object(module, "_three_point_derivative", side_effect=[1.0, 2.0, 3.0]):
            result = module.analyze(hull, state, options)
        self.assertNoStiffness(result)
        self.assertFalse(result["refinement_passed"])
        self.assertEqual(result["restoring_sign"], "unresolved")
        self.assertEqual(result["input_fingerprint"], state["input_fingerprint"])
        self.assertTrue(result["geometry"])
        self.assertEqual(len(result["samples"]["groups"]), 3)
        self.assertTrue(result["refinement_delta_m"] > result["refinement_tolerance_m"])
        self.assertTrue(is_number(result["samples"]["baseline"]["restoring_arm_m"]))
        for group in result["samples"]["groups"]:
            self.assertEqual(len(group["restoring_arm_m"]), 2)
            self.assertEqual(len(group["phi_rad"]), 2)


def custom_hull(polygon, stations=3, length=LENGTH):
    rows = [[-length / 2 + length * index / (stations - 1), copy.deepcopy(polygon)]
            for index in range(stations)]
    return hull_record(rows)


SYMMETRIC_SECTION = [[-4.0, 0.0], [4.0, 0.0], [4.0, DECK], [-4.0, DECK]]
# Simple and concave: every vertex has a mirrored partner, but the boundary runs
# in a different order, so the immersed area is not symmetric.
SET_SYMMETRIC_SECTION = [[-2.0, 0.0], [2.0, 0.0], [1.0, 1.0], [-1.0, 1.0],
                         [2.0, 2.0], [-2.0, 2.0]]


class ScalarRollSymmetryTests(unittest.TestCase):
    """Boundary symmetry and rigid-mass accounting behind the roll gate."""

    def eligibility(self, polygon, state=None, options=None):
        return kernel().scalar_roll_eligibility(custom_hull(polygon),
                                                loading_state() if state is None else state,
                                                options)

    def test_concave_section_that_only_mirrors_as_a_vertex_set_is_rejected(self):
        result = self.eligibility(SET_SYMMETRIC_SECTION)
        self.assertFalse(result["symmetry_proved"])
        self.assertEqual(result["status"], "unavailable")
        self.assertTrue(result["reasons"])
        self.assertTrue(any("not symmetric" in reason for reason in result["reasons"]))
        json.dumps(result, allow_nan=False)

    def test_rotated_start_and_reversed_winding_still_prove_symmetry(self):
        rotated = [[4.0, 0.0], [4.0, DECK], [-4.0, DECK], [-4.0, 0.0]]
        reversed_winding = [[-4.0, 0.0], [-4.0, DECK], [4.0, DECK], [4.0, 0.0]]
        for label, polygon in (("as built", SYMMETRIC_SECTION), ("rotated start", rotated),
                               ("reversed winding", reversed_winding)):
            with self.subTest(section=label):
                result = self.eligibility(polygon)
                self.assertTrue(result["symmetry_proved"], result["reasons"])
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["checked"]["items"], 1)
                json.dumps(result, allow_nan=False)

    def test_unknown_or_empty_rigid_ledger_cannot_prove_symmetry(self):
        absent = loading_state(mass=80.0, kg=0.5)
        absent.pop("effective_items")
        empty = dict(loading_state(mass=80.0, kg=0.5), effective_items=[])
        unknown = dict(loading_state(mass=80.0, kg=0.5),
                       effective_items=[dict(id="bad", mass_t=None, y_m=4.0)])
        off_axis = dict(loading_state(mass=80.0, kg=0.5),
                        effective_items=[dict(id="off", mass_t=80.0, y_m=4.0, kg_m=0.5)])
        short_ledger = dict(loading_state(mass=80.0, kg=0.5),
                            effective_items=[dict(id="part", mass_t=60.0, y_m=0.0, kg_m=0.5)])
        incomplete = dict(loading_state(mass=80.0, kg=0.5), complete_mass=False)
        for label, state in (("absent", absent), ("empty", empty), ("unknown mass", unknown),
                             ("off-axis item", off_axis), ("short ledger", short_ledger),
                             ("incomplete flags", incomplete)):
            with self.subTest(ledger=label):
                result = self.eligibility(SYMMETRIC_SECTION, state)
                self.assertFalse(result["symmetry_proved"], label)
                self.assertEqual(result["status"], "unavailable")
                self.assertTrue(result["reasons"])

    def test_known_centered_ledger_proves_symmetry_without_inventing_inertia(self):
        state = loading_state(mass=80.0, kg=0.5)
        state["values"]["tcg_m"] = 0.0
        result = self.eligibility(SYMMETRIC_SECTION, state)
        self.assertTrue(result["symmetry_proved"], result["reasons"])
        self.assertEqual(result["checked"]["items"], 1)
        self.assertEqual(result["checked"]["sections"], 3)
        # The proof is a symmetry statement only: it supplies no inertia.
        self.assertIsNone(result["validity"]["safe"])
        self.assertIsNone(result["validity"]["historical_validated"])

    def test_mass_accounting_is_independent_of_geometry_length_units(self):
        for mass in (1e-9, 80.0):
            for ratio in (0.0, 0.5):
                with self.subTest(mass=mass, accounted_ratio=ratio):
                    state = loading_state(mass=mass, kg=0.5)
                    state['effective_items'] = ([] if ratio == 0 else [
                        dict(id='partial', mass_t=mass * ratio, y_m=0.0, kg_m=0.5)])
                    self.assertFalse(self.eligibility(SYMMETRIC_SECTION, state)['symmetry_proved'])
            self.assertTrue(self.eligibility(SYMMETRIC_SECTION,
                                            loading_state(mass=mass, kg=0.5))['symmetry_proved'])

    def test_off_axis_or_mirrored_tanks_block_the_proof(self):
        tank = dict(tank_dict(), y_m=1.5)
        options = dict(liquid_loads=[dict(tank=tank, volume_m3=4.0, fluid_density_t_m3=1.0)])
        self.assertFalse(self.eligibility(SYMMETRIC_SECTION, options=options)["symmetry_proved"])
        centred = dict(liquid_loads=[dict(tank=tank_dict(), volume_m3=4.0,
                                          fluid_density_t_m3=1.0)])
        self.assertTrue(self.eligibility(SYMMETRIC_SECTION, options=centred)["symmetry_proved"])


class LocalContactTests(KernelResultContract, unittest.TestCase):
    """Local section contact must be rejected even while globally partial."""

    def test_tunnel_floor_on_the_waterplane_is_rejected_while_partial(self):
        hull = notch_hull()
        mass = LENGTH * BEAM * 2.0 * RHO
        state = loading_state(mass, kg=2.8)
        # Independent evidence that the fixture is what it claims: the hull is
        # partially immersed at 2 m and one local edge lies on that plane.
        solved = stability.solve_loaded_equilibrium(hull, state)
        self.assertTrue(solved["converged"], solved.get("diagnostics"))
        self.assertAlmostEqual(solved["waterline_d_m"], 2.0, places=9)
        measures = geometry_analysis.measures_at_plane(hull, {"p": 0.0, "q": 0.0, "waterline_d_m": 2.0})
        self.assertEqual(measures["envelope_state"], "partial")
        self.assertFalse(measures["upright_empirical_eligible"])
        self.assertIn("geometry.waterplane_contact", [d["code"] for d in measures["diagnostics"]])

        self.assertNoStiffness(kernel().analyze(hull, state))

        # Control: the same hull without the tunnel is a supported case, so the
        # rejection above is the contact and not the loading.
        plain = kernel().analyze(barge_hull(), loading_state(mass, kg=2.8))
        self.assertEqual(plain["status"], "completed", plain.get("reason"))
        self.assertTrue(math.isclose(plain["equilibrium_gm_m"], analytic_slab_gm(2.0),
                                     rel_tol=RELATIVE_TOLERANCE, abs_tol=ABSOLUTE_TOLERANCE),
                        f"measured {plain['equilibrium_gm_m']!r} against "
                        f"analytic {analytic_slab_gm(2.0)!r}")


if __name__ == "__main__":
    unittest.main()
