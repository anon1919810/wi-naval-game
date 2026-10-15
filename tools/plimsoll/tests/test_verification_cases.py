# -*- coding: utf-8 -*-
"""Deterministic verification cases and independent references (Task 1).

These tests constrain two things only:

* ``verification_cases.build_cases`` returns frozen, strict canonical JSON
  case dictionaries with literal, predeclared expectations; and
* ``verification_oracles.reference_for`` answers them from continuous math.

Nothing here imports a repository test module to build an expectation and
nothing here lets a production kernel produce an expected value.  Every
expected number that appears as a literal in this file was derived by hand
from the closed-form integrals recorded in the design documents, or is an
independently published anchor (see the comments above each literal).

Imports follow the existing package convention: ``tools/plimsoll`` is put on
``sys.path`` and the two modules are imported directly.
"""

from __future__ import annotations

import ast
import copy
import json
import math
from pathlib import Path
import sys
import unittest


PKG = Path(__file__).resolve().parents[1]
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

import verification_cases  # noqa: E402
import verification_oracles  # noqa: E402


SUITES = ("quick", "extended", "all")

# Literal matrix sizes.  These are design-fixed counts, not whatever the
# current builders happen to produce.
QUICK_CASE_COUNT = 15      # 6 scale + 4 mirror + 2 datum + 3 diagonal meshes
EXTENDED_CASE_COUNT = 26   # 9 meshes + 12 long replays + 5 controls
ALL_CASE_COUNT = 38        # union: 12 transform + 9 mesh + 17 flooding

MESH_STATION_COUNTS = (41, 81, 161)
MESH_VERTEX_COUNTS = (32, 64, 128)
DIAGONAL_MESHES = ((41, 32), (81, 64), (161, 128))

LONG_DURATIONS_S = (60.0, 300.0)
LONG_TIME_STEPS_S = (0.5, 0.25, 0.125)

# Declared tolerance budgets from design.md section 2 and section 3.  Written
# down here independently of any case builder.
DESIGN_GEOMETRY_TRANSFORM_RELATIVE = 1e-8
DESIGN_GEOMETRY_TRANSFORM_CENTROID_ABS_M = 1e-7
DESIGN_SOLVED_TRANSFORM_VOLUME_RELATIVE = 1e-6
DESIGN_SOLVED_TRANSFORM_POSITION_ABS_M = 1e-5
DESIGN_SOLVED_TRANSFORM_ANGLE_ABS_DEG = 1e-5
DESIGN_SCALED_RESIDUAL_MAX = 1e-6

DESIGN_FINEST_VOLUME_RELATIVE = 1e-3
DESIGN_FINEST_BUOYANCY_AXIS_ABS_M = 0.01
DESIGN_FINEST_DRAFT_ABS_M = 0.01
DESIGN_FINEST_SLOPE_ABS = 1e-4

DESIGN_ORACLE_VOLUME_ABS_M3 = 1e-7
DESIGN_ORACLE_GEOMETRIC_ABS_M = 1e-8
DESIGN_ORACLE_SCALED_RESIDUAL_MAX = 1e-10
DESIGN_ORACLE_EVENT_TIME_ABS_S = 1e-4

DESIGN_TRAJECTORY_VOLUME_ABS_M3 = 1e-4
DESIGN_TRAJECTORY_VOLUME_RELATIVE = 0.01
DESIGN_TRAJECTORY_DRAFT_ABS_M = 1e-3

DESIGN_VOLUME_CONSERVATION_ABS_M3 = 1e-9
DESIGN_VOLUME_CONSERVATION_RELATIVE = 1e-10
DESIGN_MASS_CONSERVATION_ABS_T = 1e-9
DESIGN_MASS_CONSERVATION_RELATIVE = 1e-10


# ---------------------------------------------------------------------------
# Independent hand derivations used as controls inside this test module.
# Nothing below calls verification_oracles.
# ---------------------------------------------------------------------------

def gauss_legendre_2(f, low, high):
    """Two-point Gauss-Legendre value of f on [low, high] (exact to deg 3)."""
    half = 0.5 * (high - low)
    mid = 0.5 * (high + low)
    return half * (f(mid - half / math.sqrt(3.0)) + f(mid + half / math.sqrt(3.0)))


def independent_column_moments(plane_slope, mean_depth, low, high):
    """Column volume/first moments of a wall-sided wedge, by quadrature.

    ``plane_slope`` is q for a box of beam ``high-low`` whose liquid surface is
    ``z = plane_slope*y + mean_depth``.  Nothing is clipped, so the column
    height is the affine function itself.  This is a different algorithm from
    the closed-form polynomial moments the oracle publishes.
    """
    def height(y):
        return plane_slope * y + mean_depth

    volume = gauss_legendre_2(height, low, high)
    first_y = gauss_legendre_2(lambda y: y * height(y), low, high)
    first_z = gauss_legendre_2(lambda y: 0.5 * height(y) ** 2, low, high)
    return volume, first_y, first_z


def independent_sphere_cap_coefficients(t):
    """Unit-sphere cap volume and axial first moment.

    The slice area along the cap axis is ``pi*(1 - s^2)``, so integrating it
    from -1 to t gives ``(pi/3)(2 + 3t - t^3)`` and integrating it weighted by
    s gives ``pi(t^2/2 - t^4/4 - 1/4)``.  Both are exact antiderivatives,
    derived here without reference to the oracle module.  The volume already
    carries its own pi and its 1/3 factor, so callers scale it by the semi-axis
    product directly.
    """
    volume = math.pi * (t - t ** 3 / 3.0 + 2.0 / 3.0)
    moment = math.pi * (t * t / 2.0 - t ** 4 / 4.0 - 0.25)
    return volume, moment


def independent_mirror_reference(base_inputs):
    """Mirror y -> -y of a transform reference built by hand."""
    mirrored = copy.deepcopy(base_inputs)
    mirrored["q"] = -mirrored["q"]
    return mirrored


def _bisect(function, low, high, tolerance=1e-15, iterations=200):
    """Plain bisection root finder used as an independent equilibrium solver."""
    low_value = function(low)
    high_value = function(high)
    if low_value == 0.0:
        return low
    if high_value == 0.0:
        return high
    if (low_value > 0.0) == (high_value > 0.0):
        raise AssertionError("independent bisection needs a sign change")
    for _ in range(iterations):
        mid = 0.5 * (low + high)
        value = function(mid)
        if abs(value) <= tolerance:
            return mid
        if (value > 0.0) == (low_value > 0.0):
            low, low_value = mid, value
        else:
            high, high_value = mid, value
    return 0.5 * (low + high)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def walk_numbers(value, path=""):
    """Yield ``(path, number)`` for every numeric leaf in a JSON-safe tree."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk_numbers(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_numbers(item, f"{path}[{index}]")
    elif isinstance(value, bool):
        yield path, value
    elif isinstance(value, (int, float)):
        yield path, value


class VerificationCaseModuleTest(unittest.TestCase):
    """Suite selection, identity, strict JSON and clone independence."""

    def test_build_cases_exposes_exactly_the_three_declared_suites(self):
        for suite in SUITES:
            cases = verification_cases.build_cases(suite)
            self.assertIsInstance(cases, list, suite)
            self.assertTrue(cases, suite)
            for case in cases:
                self.assertIn(case["suite"], ("quick", "extended"), case["id"])
                self.assertTrue(case["in_suites"][suite], case["id"])

    def test_build_cases_rejects_an_unknown_suite(self):
        for bad in ("", "QUICK", "everything", "all ", None, 7):
            with self.assertRaises(ValueError):
                verification_cases.build_cases(bad)

    def test_ids_are_unique_inside_every_suite(self):
        for suite in SUITES:
            ids = [case["id"] for case in verification_cases.build_cases(suite)]
            self.assertEqual(len(ids), len(set(ids)), suite)

    def test_literal_matrix_counts(self):
        self.assertEqual(len(verification_cases.build_cases("quick")),
                         QUICK_CASE_COUNT)
        self.assertEqual(len(verification_cases.build_cases("extended")),
                         EXTENDED_CASE_COUNT)
        self.assertEqual(len(verification_cases.build_cases("all")),
                         ALL_CASE_COUNT)

    def test_all_is_the_deduplicated_union_of_quick_and_extended(self):
        quick = {case["id"]: case for case in verification_cases.build_cases("quick")}
        extended = {case["id"]: case
                    for case in verification_cases.build_cases("extended")}
        merged = verification_cases.build_cases("all")
        merged_ids = [case["id"] for case in merged]
        self.assertEqual(sorted(merged_ids), sorted(set(quick) | set(extended)))
        self.assertEqual(len(merged_ids), len(set(merged_ids)))
        # Overlapping ids must be byte-identical between suites.
        for shared in set(quick) & set(extended):
            self.assertEqual(
                json.dumps(quick[shared], sort_keys=True),
                json.dumps(extended[shared], sort_keys=True), shared)

    def test_every_case_is_strict_canonical_json(self):
        for suite in SUITES:
            for case in verification_cases.build_cases(suite):
                text = json.dumps(case, sort_keys=True, allow_nan=False,
                                  ensure_ascii=True, separators=(",", ":"))
                self.assertIsInstance(text, str)
                self.assertEqual(json.loads(text), case, case["id"])

    def test_case_numbers_are_finite(self):
        # Canonical JSON legitimately carries booleans as state and metadata
        # (``mirrored``, ``open``, ``solve_equilibrium``, ``estimate``), so the
        # scan checks that every *numeric* leaf is a finite real.  Booleans are
        # excluded from the arithmetic scan but are still required to survive
        # the JSON round trip unchanged.
        for suite in SUITES:
            for case in verification_cases.build_cases(suite):
                for section in ("inputs", "expected", "tolerances"):
                    for path, value in walk_numbers(case[section]):
                        if isinstance(value, bool):
                            continue
                        self.assertTrue(math.isfinite(value),
                                        f"{case['id']} {section}{path} is not "
                                        "a finite number")

    def test_declared_boolean_flags_are_real_booleans(self):
        wanted = {"mirrored", "open", "solve_equilibrium", "estimate",
                  "free_surface", "crosses_hydraulic_equilibrium",
                  "requires_reversal", "plateau_constant"}
        seen = set()
        for case in verification_cases.build_cases("all"):
            for path, value in walk_numbers(case["inputs"]):
                if path.rsplit(".", 1)[-1] in wanted:
                    self.assertIsInstance(value, bool, f"{case['id']}{path}")
                    seen.add(path.rsplit(".", 1)[-1])
            for path, value in walk_numbers(case["expected"]):
                if path.rsplit(".", 1)[-1] in wanted:
                    self.assertIsInstance(value, bool,
                                          f"{case['id']} expected{path}")
                    seen.add(path.rsplit(".", 1)[-1])
            self.assertIsInstance(case["estimate"], bool, case["id"])
        self.assertTrue({"mirrored", "open", "solve_equilibrium", "estimate",
                         "free_surface", "crosses_hydraulic_equilibrium",
                         "requires_reversal"} <= seen)

    def test_case_trees_carry_no_tuples_sets_or_bytes(self):
        def scan(value, case_id, path):
            if isinstance(value, tuple) or isinstance(value, set) \
                    or isinstance(value, bytes):
                self.fail(f"{case_id}{path} is {type(value).__name__}")
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertIsInstance(key, str, f"{case_id}{path}")
                    scan(item, case_id, f"{path}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    scan(item, case_id, f"{path}[{index}]")

        for suite in SUITES:
            for case in verification_cases.build_cases(suite):
                scan(case, case["id"], "")

    def test_build_cases_returns_independent_clones(self):
        first = verification_cases.build_cases("all")
        for case in first:
            case["inputs"]["__probe__"] = 1
            case["expected"]["checks"].clear()
            case["id"] = case["id"] + "-mutated"
        second = verification_cases.build_cases("all")
        self.assertEqual(len(second), ALL_CASE_COUNT)
        for case in second:
            self.assertNotIn("__probe__", case["inputs"])
            self.assertTrue(case["expected"]["checks"])
            self.assertFalse(case["id"].endswith("-mutated"))
        # The first result really was mutated, proving the probe is meaningful.
        self.assertIn("__probe__", first[0]["inputs"])

    def test_case_records_carry_the_required_context(self):
        required = ("schema", "id", "kind", "family", "group", "suite",
                    "in_suites", "title", "inputs", "expected",
                    "tolerances", "tolerance_profile", "method", "source",
                    "estimate", "reference", "relation")
        for suite in SUITES:
            for case in verification_cases.build_cases(suite):
                for key in required:
                    self.assertIn(key, case, f"{case['id']} missing {key}")
                self.assertEqual(case["schema"], "plimsoll-verification-case-1")
                self.assertIsInstance(case["estimate"], bool)
                self.assertTrue(case["source"])
                self.assertIn("method_version", case["method"])
                self.assertIn("oracle", case["reference"])
                self.assertIn("precision", case["reference"])
                self.assertIn("status", case["expected"])
                self.assertIn("reason", case["expected"])
                self.assertIn("stop_class", case["expected"])
                self.assertTrue(case["expected"]["checks"])
                self.assertIn("production", case["tolerances"])
                self.assertIn("reference", case["tolerances"])


class TransformCaseDeclarationTest(unittest.TestCase):
    """Scale, mirror and z-datum expectations are predeclared laws."""

    def setUp(self):
        self.cases = {case["id"]: case
                      for case in verification_cases.build_cases("all")}

    def _family(self, family):
        return sorted((case for case in self.cases.values()
                       if case["family"] == family),
                      key=lambda case: case["id"])

    def test_scale_family_has_three_lambdas_for_dry_and_loaded_states(self):
        scale = self._family("transform_scale")
        self.assertEqual(len(scale), 6)
        lambdas = {case["relation"]["scale_factor"] for case in scale}
        self.assertEqual(sorted(lambdas), [0.5, 1.0, 2.0])
        states = {case["relation"]["load_state"] for case in scale}
        self.assertEqual(sorted(states), ["dry", "liquid_loaded"])
        for case in scale:
            self.assertTrue(case["relation"]["p"] != 0.0, case["id"])
            self.assertTrue(case["relation"]["q"] != 0.0, case["id"])

    def test_scale_exponents_are_the_declared_physics(self):
        for case in self._family("transform_scale"):
            exponents = case["relation"]["exponents"]
            self.assertEqual(exponents["length_m"], 1, case["id"])
            self.assertEqual(exponents["area_m2"], 2, case["id"])
            self.assertEqual(exponents["volume_m3"], 3, case["id"])
            self.assertEqual(exponents["mass_t"], 3, case["id"])
            self.assertEqual(exponents["waterplane_inertia_m4"], 4, case["id"])
            self.assertEqual(exponents["dimensionless"], 0, case["id"])
            self.assertEqual(exponents["angle_deg"], 0, case["id"])

    def test_scale_reference_reproduces_hand_derived_box_integrals(self):
        # Hand derivation for lambda = 1, L=40, B=10, T=4, p=0.01, q=0.1,
        # KG=1.5, keel at z=0 and a waterplane that never reaches a plate:
        #   V  = L*B*T                      = 1600
        #   Bx = p*L^2/(12T)                = 16/48      = 1/3
        #   By = q*B^2/(12T)                = 10/48      = 5/24
        #   Bz = T/2 + (p^2 L^2 + q^2 B^2)/(24T)
        #      = 2 + (0.16 + 1)/96          = 2 + 29/2400
        #   dz = Bz - KG                    = 1229/2400
        #   Gx = Bx + p*dz                  = 81229/240000
        #   Gy = By + q*dz                  = 6229/24000
        # The decimals below are the literal expansions of those fractions.
        case = self.cases["transform-scale-dry-l1p0"]
        reference = verification_oracles.reference_for(case)
        qty = reference["quantities"]
        self.assertAlmostEqual(qty["volume_m3"]["value"], 1600.0, delta=1e-9)
        # 1600 * 1.025 is 1639.9999999999998 in binary floating point; the
        # literal 1640 t is the declared mass, and the reference reproduces it
        # to roundoff rather than exactly.
        self.assertAlmostEqual(qty["mass_t"]["value"], 1640.0, delta=1e-9)
        self.assertAlmostEqual(qty["buoyancy_centre_m"]["value"][0],
                               0.3333333333333333, delta=1e-15)
        self.assertAlmostEqual(qty["buoyancy_centre_m"]["value"][1],
                               0.2083333333333333, delta=1e-15)
        self.assertAlmostEqual(qty["buoyancy_centre_m"]["value"][2],
                               2.0120833333333334, delta=1e-15)
        self.assertAlmostEqual(qty["cg_m"]["value"][0],
                               0.3384541666666666, delta=1e-15)
        self.assertAlmostEqual(qty["cg_m"]["value"][1],
                               0.2595416666666666, delta=1e-15)
        self.assertAlmostEqual(qty["cg_m"]["value"][2], 1.5, delta=0.0)

    def test_scale_reference_scales_exactly_with_the_declared_exponents(self):
        base = verification_oracles.reference_for(
            self.cases["transform-scale-dry-l1p0"])["quantities"]
        # name -> declared power of the linear scale factor.
        expectations = {
            "volume_m3": 3, "mass_t": 3, "draft_m": 1, "kg_m": 1,
            "buoyancy_centre_m": 1, "cg_m": 1,
            "waterplane_inertia_m4": 4, "waterplane_geometric_area_m2": 2,
            "waterplane_projected_area_m2": 2,
        }
        for suffix, factor in (("l0p5", 0.5), ("l2p0", 2.0)):
            scaled = verification_oracles.reference_for(
                self.cases[f"transform-scale-dry-{suffix}"])["quantities"]
            for name, power in expectations.items():
                want = base[name]["value"]
                if isinstance(want, list):
                    # Component-wise scaling of a position triple.
                    targets = [value * factor ** power for value in want]
                else:
                    targets = want * factor ** power
                got = scaled[name]["value"]
                if isinstance(targets, list):
                    for index, target in enumerate(targets):
                        self.assertAlmostEqual(
                            got[index], target, places=11,
                            msg=f"{name}[{index}] at {suffix}")
                else:
                    self.assertAlmostEqual(
                        got, targets, places=11, msg=f"{name} at {suffix}")
            # Dimensionless and angular quantities must not move at all.
            self.assertAlmostEqual(scaled["heel_deg"]["value"],
                                   base["heel_deg"]["value"], delta=1e-12)
            self.assertAlmostEqual(scaled["trim_deg"]["value"],
                                   base["trim_deg"]["value"], delta=1e-12)
            self.assertAlmostEqual(scaled["gm_m"]["value"],
                                   base["gm_m"]["value"] * factor, delta=1e-12)

    def test_mirror_family_declares_invariants_and_sign_reversals(self):
        mirror = self._family("transform_mirror")
        self.assertEqual(len(mirror), 4)
        for case in mirror:
            law = case["relation"]
            self.assertEqual(
                sorted(law["identical"]),
                sorted(["displacement_t", "trim_deg", "volume_m3",
                        "buoyancy_x_m", "buoyancy_z_m"]), case["id"])
            self.assertEqual(
                sorted(law["sign_reversed"]),
                sorted(["buoyancy_y_m", "cg_y_m", "gz_m", "heel_deg"]), case["id"])
            self.assertTrue(law["p"] != 0.0, case["id"])
            self.assertTrue(law["q"] != 0.0, case["id"])

    def test_mirror_reference_pairs_are_exact_transverse_negations(self):
        straight = verification_oracles.reference_for(
            self.cases["transform-mirror-dry"])
        reflected = verification_oracles.reference_for(
            self.cases["transform-mirror-dry-reflected"])
        self.assertEqual(
            straight["quantities"]["volume_m3"]["value"],
            reflected["quantities"]["volume_m3"]["value"])
        self.assertEqual(
            straight["quantities"]["mass_t"]["value"],
            reflected["quantities"]["mass_t"]["value"])
        self.assertEqual(
            straight["quantities"]["buoyancy_centre_m"]["value"][0],
            reflected["quantities"]["buoyancy_centre_m"]["value"][0])
        self.assertAlmostEqual(
            straight["quantities"]["buoyancy_centre_m"]["value"][1],
            -reflected["quantities"]["buoyancy_centre_m"]["value"][1],
            delta=1e-15)
        self.assertEqual(
            straight["quantities"]["buoyancy_centre_m"]["value"][2],
            reflected["quantities"]["buoyancy_centre_m"]["value"][2])
        self.assertAlmostEqual(
            straight["quantities"]["heel_deg"]["value"],
            -reflected["quantities"]["heel_deg"]["value"], delta=1e-12)
        self.assertAlmostEqual(
            straight["quantities"]["gz_m"]["value"],
            -reflected["quantities"]["gz_m"]["value"], delta=1e-12)
        self.assertEqual(straight["quantities"]["trim_deg"]["value"],
                         reflected["quantities"]["trim_deg"]["value"])

    def test_datum_family_declares_keel_relative_invariants(self):
        datum = self._family("transform_datum")
        self.assertEqual(len(datum), 2)
        shifts = sorted(case["relation"]["datum_shift_m"] for case in datum)
        self.assertEqual(shifts, [0.0, 13.25])
        for case in datum:
            law = case["relation"]
            self.assertEqual(sorted(law["keel_relative_invariant"]),
                             ["aperture_height_m", "cg_keel_m", "draft_m",
                              "heel_deg", "kg_m", "tank_bottom_keel_m",
                              "trim_deg"], case["id"])
            self.assertEqual(sorted(law["absolute_shift"]),
                             ["buoyancy_centre_z_m", "cg_z_m",
                              "waterline_d_m"], case["id"])
            self.assertEqual(case["inputs"]["keel_offset_m"],
                             case["relation"]["datum_shift_m"], case["id"])

    def test_datum_reference_moves_only_absolute_coordinates(self):
        base = verification_oracles.reference_for(
            self.cases["transform-datum-shift-0"])
        shifted = verification_oracles.reference_for(
            self.cases["transform-datum-shift-13p25"])
        offset = 13.25
        self.assertAlmostEqual(
            shifted["quantities"]["cg_z_m"]["value"]
            - base["quantities"]["cg_z_m"]["value"], offset, delta=1e-12)
        self.assertAlmostEqual(
            shifted["quantities"]["buoyancy_centre_keel_m"]["value"][2]
            - base["quantities"]["buoyancy_centre_keel_m"]["value"][2],
            0.0, delta=1e-12)
        self.assertAlmostEqual(
            shifted["quantities"]["draft_m"]["value"]
            - base["quantities"]["draft_m"]["value"], 0.0, delta=1e-12)
        self.assertAlmostEqual(
            shifted["quantities"]["heel_deg"]["value"]
            - base["quantities"]["heel_deg"]["value"], 0.0, delta=1e-12)
        for axis in range(3):
            self.assertAlmostEqual(
                shifted["quantities"]["cg_keel_m"]["value"][axis]
                - base["quantities"]["cg_keel_m"]["value"][axis], 0.0,
                delta=1e-12)
            self.assertAlmostEqual(
                shifted["quantities"]["cg_m"]["value"][axis]
                - base["quantities"]["cg_m"]["value"][axis],
                offset if axis == 2 else 0.0, delta=1e-12)
        self.assertAlmostEqual(
            shifted["quantities"]["waterline_d_m"]["value"]
            - base["quantities"]["waterline_d_m"]["value"], offset, delta=1e-12)


class MeshCaseDeclarationTest(unittest.TestCase):
    """Nine joint refinement meshes and their guarded acceptance."""

    def setUp(self):
        self.cases = {case["id"]: case
                      for case in verification_cases.build_cases("all")
                      if case["family"] == "mesh"}

    def test_mesh_family_is_nine_cases_on_the_declared_grid(self):
        self.assertEqual(len(self.cases), 9)
        seen = {(case["inputs"]["stations"], case["inputs"]["section_vertices"])
                for case in self.cases.values()}
        self.assertEqual(seen,
                         {(s, v) for s in MESH_STATION_COUNTS
                          for v in MESH_VERTEX_COUNTS})

    def test_exactly_three_diagonal_meshes_request_equilibrium(self):
        solving = [tuple(item) for item in sorted(
            (case["inputs"]["stations"], case["inputs"]["section_vertices"])
            for case in self.cases.values()
            if case["inputs"]["solve_equilibrium"])]
        self.assertEqual(solving, [tuple(item) for item in DIAGONAL_MESHES])

    def test_only_the_finest_mesh_carries_final_accuracy_limits(self):
        for case in self.cases.values():
            finest = (case["inputs"]["stations"] == 161
                      and case["inputs"]["section_vertices"] == 128)
            profile = case["tolerance_profile"]
            if finest:
                self.assertEqual(profile, "analytic-geometry-fine-v1", case["id"])
            else:
                self.assertEqual(profile, "analytic-geometry-coarse-v1",
                                 case["id"])
            accuracy = case["tolerances"]["production"].get(
                "final_analytic_accuracy")
            if finest:
                self.assertEqual(accuracy, {
                    "volume_relative": DESIGN_FINEST_VOLUME_RELATIVE,
                    "buoyancy_axis_abs_m": DESIGN_FINEST_BUOYANCY_AXIS_ABS_M,
                    "draft_abs_m": DESIGN_FINEST_DRAFT_ABS_M,
                    "slope_abs": DESIGN_FINEST_SLOPE_ABS,
                }, case["id"])
            else:
                self.assertIsNone(accuracy, case["id"])

    def test_status_and_finite_guards_apply_at_every_mesh_level(self):
        # Direct geometry integration happens on all nine meshes, so the
        # status and finiteness guards must be required everywhere.
        for case in self.cases.values():
            names = {check["name"]: check for check in case["expected"]["checks"]}
            for required in ("status_flag_matches", "all_states_finite"):
                self.assertIn(required, names, case["id"])
                self.assertTrue(names[required]["required"], case["id"])

    def test_solver_residual_guards_apply_only_where_equilibrium_runs(self):
        # Only the three diagonal meshes call the loaded-equilibrium solver,
        # so only they may demand solver convergence and a scaled residual.
        for case in self.cases.values():
            names = {check["name"]: check for check in case["expected"]["checks"]}
            solves = case["inputs"]["solve_equilibrium"]
            if not solves:
                self.assertNotIn("scaled_residual_within_limit", names,
                                 case["id"])
                self.assertNotIn("equilibrium_converged_flag", names, case["id"])
                self.assertEqual(case["method"]["target"],
                                 "geometry.StationedHull.integrate", case["id"])
                continue
            for required in ("scaled_residual_within_limit",
                             "equilibrium_converged_flag"):
                self.assertIn(required, names, case["id"])
                check = names[required]
                self.assertTrue(check["required"], case["id"])
                if check["kind"] == "residual_max":
                    self.assertEqual(check["tolerance"],
                                     DESIGN_SCALED_RESIDUAL_MAX, case["id"])

    def test_coarse_meshes_still_report_observed_analytic_error(self):
        for case in self.cases.values():
            names = {check["name"] for check in case["expected"]["checks"]}
            self.assertIn("analytic_volume_relative_error", names, case["id"])


class OracleEllipsoidTest(unittest.TestCase):
    """The continuous ellipsoid reference against published independent values."""

    SEMI_AXES = (20.0, 5.0, 5.0)
    CENTRE_Z = 5.0
    P = 0.01
    Q = 0.1
    D = 4.0

    def test_oracle_matches_the_independently_published_ellipsoid_values(self):
        # Published independent values for semi-axes (20,5,5), centre z=5,
        # plane z = 0.01 x + 0.1 y + 4:
        #   V  = 738.9616567702824 m^3
        #   B  = (0.38992486365407397, 0.24370303978379626, 2.5629696021620374) m
        case = next(c for c in verification_cases.build_cases("all")
                    if c["family"] == "mesh")
        reference = verification_oracles.reference_for(case)
        self.assertAlmostEqual(reference["quantities"]["volume_m3"]["value"],
                               738.9616567702824, delta=1e-9)
        for axis, expected in zip(
                reference["quantities"]["buoyancy_centre_m"]["value"],
                (0.38992486365407397, 0.24370303978379626,
                 2.5629696021620374)):
            self.assertAlmostEqual(axis, expected, delta=1e-12)

    def test_oracle_volume_matches_an_independent_quadrature_of_the_cap(self):
        # x = aX, y = bY, z = c + cZ maps the ellipsoid onto the unit sphere and
        # the plane onto (-p a, -q b, c) . (X,Y,Z) <= d - c, i.e. a cap whose
        # signed normalised offset is t = (d-c)/S.  Integrating the slice area
        # pi*(1-s^2) along the cap axis is a separate derivation of the same
        # number.
        a, b, c = self.SEMI_AXES
        support = math.sqrt((self.P * a) ** 2 + (self.Q * b) ** 2 + c * c)
        offset = (self.D - c) / support
        unit_volume, unit_moment = independent_sphere_cap_coefficients(offset)
        # unit_volume already carries pi and its 1/3 factor, so the semi-axis
        # product is the only remaining scale.
        expected_volume = a * b * c * unit_volume
        centroid_unit = unit_moment / unit_volume
        case = next(c for c in verification_cases.build_cases("all")
                    if c["family"] == "mesh")
        reference = verification_oracles.reference_for(case)
        self.assertAlmostEqual(reference["quantities"]["volume_m3"]["value"],
                               expected_volume, delta=1e-9)
        centre = reference["quantities"]["buoyancy_centre_m"]["value"]
        self.assertAlmostEqual(
            centre[0], -centroid_unit * self.P * a * a / support, delta=1e-12)
        self.assertAlmostEqual(
            centre[1], -centroid_unit * self.Q * b * b / support, delta=1e-12)
        self.assertAlmostEqual(
            centre[2],
            c + centroid_unit * c * c / support, delta=1e-12)


class OracleReferencePrecisionTest(unittest.TestCase):
    """Declared budgets and measured, not asserted, reference accuracy."""

    def setUp(self):
        self.cases = verification_cases.build_cases("all")

    def test_every_case_declares_the_design_reference_budgets(self):
        for case in self.cases:
            budgets = case["tolerances"]["reference"]
            self.assertEqual(budgets["volume_abs_m3"],
                             DESIGN_ORACLE_VOLUME_ABS_M3, case["id"])
            self.assertEqual(budgets["geometric_abs_m"],
                             DESIGN_ORACLE_GEOMETRIC_ABS_M, case["id"])
            self.assertEqual(budgets["scaled_residual_max"],
                             DESIGN_ORACLE_SCALED_RESIDUAL_MAX, case["id"])
            self.assertEqual(budgets["event_time_abs_s"],
                             DESIGN_ORACLE_EVENT_TIME_ABS_S, case["id"])

    def test_every_reference_reports_measured_control_evidence(self):
        for case in self.cases:
            reference = verification_oracles.reference_for(case)
            controls = reference["evidence"]["controls"]
            self.assertTrue(controls, case["id"])
            for control in controls:
                for key in ("name", "measured_difference", "unit", "budget",
                            "within_budget"):
                    self.assertIn(key, control, f"{case['id']} {control}")
                self.assertIsInstance(control["measured_difference"], float,
                                      case["id"])
                self.assertIsInstance(control["within_budget"], bool, case["id"])
                self.assertTrue(control["within_budget"],
                                f"{case['id']} control {control['name']} "
                                f"exceeded its budget")

    def test_transform_cases_declare_the_design_transform_budgets(self):
        for case in self.cases:
            if not case["family"].startswith("transform"):
                continue
            geometry = case["tolerances"]["geometry_transform"]
            self.assertEqual(geometry["relative"],
                             DESIGN_GEOMETRY_TRANSFORM_RELATIVE, case["id"])
            self.assertEqual(geometry["centroid_abs_m"],
                             DESIGN_GEOMETRY_TRANSFORM_CENTROID_ABS_M,
                             case["id"])
            solved = case["tolerances"]["solved_transform"]
            self.assertEqual(solved["volume_relative"],
                             DESIGN_SOLVED_TRANSFORM_VOLUME_RELATIVE, case["id"])
            self.assertEqual(solved["position_abs_m"],
                             DESIGN_SOLVED_TRANSFORM_POSITION_ABS_M, case["id"])
            self.assertEqual(solved["angle_abs_deg"],
                             DESIGN_SOLVED_TRANSFORM_ANGLE_ABS_DEG, case["id"])
            self.assertEqual(solved["scaled_residual_max"],
                             DESIGN_SCALED_RESIDUAL_MAX, case["id"])

    def test_flooding_cases_declare_the_design_trajectory_budgets(self):
        for case in self.cases:
            if case["family"] != "flooding":
                continue
            production = case["tolerances"]["production"]
            self.assertEqual(production["trajectory_volume_abs_m3"],
                             DESIGN_TRAJECTORY_VOLUME_ABS_M3, case["id"])
            self.assertEqual(production["trajectory_volume_relative"],
                             DESIGN_TRAJECTORY_VOLUME_RELATIVE, case["id"])
            self.assertEqual(production["draft_abs_m"],
                             DESIGN_TRAJECTORY_DRAFT_ABS_M, case["id"])
            self.assertEqual(production["scaled_residual_max"],
                             DESIGN_SCALED_RESIDUAL_MAX, case["id"])
            self.assertEqual(production["volume_conservation_abs_m3"],
                             DESIGN_VOLUME_CONSERVATION_ABS_M3, case["id"])
            self.assertEqual(production["volume_conservation_relative"],
                             DESIGN_VOLUME_CONSERVATION_RELATIVE, case["id"])
            self.assertEqual(production["mass_conservation_abs_t"],
                             DESIGN_MASS_CONSERVATION_ABS_T, case["id"])
            self.assertEqual(production["mass_conservation_relative"],
                             DESIGN_MASS_CONSERVATION_RELATIVE, case["id"])
            self.assertIn("declared_transferred_volume_scale_m3",
                          case["inputs"])
            self.assertIn("declared_mass_scale_t", case["inputs"])
            self.assertTrue(
                case["inputs"]["declared_transferred_volume_scale_m3"] > 0.0,
                case["id"])
            self.assertTrue(case["inputs"]["declared_mass_scale_t"] > 0.0,
                            case["id"])


class FloodingCaseDeclarationTest(unittest.TestCase):
    """The literal twelve long requests plus the declared controls."""

    def setUp(self):
        self.flooding = [case for case
                         in verification_cases.build_cases("all")
                         if case["family"] == "flooding"]
        self.long_cases = [case for case in self.flooding
                           if case["kind"] == "flooding.long_replay"]

    def test_twelve_long_requests_cover_two_scenarios_and_the_full_ladder(self):
        self.assertEqual(len(self.long_cases), 12)
        seen = {(case["inputs"]["scenario_name"],
                 case["inputs"]["duration_s"],
                 case["inputs"]["time_step_s"])
                for case in self.long_cases}
        expected = {(scenario, duration, step)
                    for scenario in ("single_sea_coupled_box",
                                     "two_tank_asymmetric_free_float")
                    for duration in LONG_DURATIONS_S
                    for step in LONG_TIME_STEPS_S}
        self.assertEqual(seen, expected)

    def test_expected_stop_class_is_declared_before_any_run(self):
        # Independently derived plateau instants: the single sea coupled box
        # equilibrates at 62.72232718774828 s, so a 60 s request completes on
        # schedule while a 300 s request must stop at hydraulic equilibrium.
        # The asymmetric pair equilibrates at 14.288 s, well inside both
        # requests, so neither may claim scheduled completion.
        for case in self.long_cases:
            single = case["inputs"]["scenario_name"] == "single_sea_coupled_box"
            duration = case["inputs"]["duration_s"]
            expected = ("scheduled_completion"
                        if single and duration < 62.72232718774828
                        else "hydraulic_equilibrium_tolerance")
            self.assertEqual(case["expected"]["stop_class"], expected, case["id"])
            self.assertEqual(case["expected"]["reason"],
                             "scheduled_completion"
                             if expected == "scheduled_completion"
                             else "hydraulic_equilibrium_tolerance", case["id"])

    def test_stop_class_follows_the_reference_equilibrium_instant(self):
        # A scheduled completion is only credible when the requested duration
        # is still strictly before the finite hydraulic equilibrium; an
        # equilibrium stop requires the request to reach or pass it.
        for case in self.long_cases:
            reference = verification_oracles.reference_for(case)
            plateau = reference["quantities"]["plateau_time_s"]["value"]
            duration = case["inputs"]["duration_s"]
            self.assertGreater(plateau, 0.0, case["id"])
            if case["expected"]["stop_class"] == "scheduled_completion":
                self.assertLess(duration, plateau, case["id"])
            else:
                self.assertGreater(duration, plateau, case["id"])

    def test_pair_replays_cannot_claim_scheduled_completion(self):
        for case in self.long_cases:
            if case["inputs"]["scenario_name"] != "two_tank_asymmetric_free_float":
                continue
            reference = verification_oracles.reference_for(case)
            plateau = reference["quantities"]["plateau_time_s"]["value"]
            self.assertLess(plateau, 60.0, case["id"])
            self.assertEqual(case["expected"]["stop_class"],
                             "hydraulic_equilibrium_tolerance", case["id"])

    def test_no_case_requires_crossing_equilibrium_and_reversing(self):
        for case in self.flooding:
            self.assertIs(case["expected"]["crosses_hydraulic_equilibrium"],
                          False, case["id"])
            self.assertIs(case["expected"]["requires_reversal"], False, case["id"])

    def test_opposite_initial_head_controls_cover_both_flow_directions(self):
        controls = [case for case in self.flooding
                    if case["kind"] == "flooding.control_head_direction"]
        self.assertEqual(len(controls), 2)
        directions = {case["inputs"]["initial_flow_direction"] for case in controls}
        self.assertEqual(directions, {"port_to_starboard", "starboard_to_port"})
        # The signed expected transfer must disagree between the two controls.
        signed = {case["inputs"]["initial_flow_direction"]:
                  math.copysign(1.0,
                                verification_oracles.reference_for(
                                    case)["quantities"]
                                ["net_transfer_m3"]["value"])
                  for case in controls}
        self.assertEqual(len(set(signed.values())), 2)

    def test_head_direction_control_reference_matches_the_published_cubic(self):
        # Independent published anchor for the supported non-symmetric pair
        # control: 20x10 box, draft 2 m, base KG 1 m, rho 1.025 t/m^3,
        # dry mass 398.725 t, two 4 m long tanks of beam 1 and 2 centred at
        # y = -0.5 and +1.0, bottom z = 0, height 4 m, initial 5 m^3 and 6 m^3.
        # The transverse equilibrium reduces to 19964 q^3 + 40063 q - 84 = 0.
        control = next(case for case in self.flooding
                       if case["kind"] == "flooding.control_head_direction"
                       and case["inputs"]["initial_flow_direction"]
                       == "port_to_starboard")
        self.assertEqual(control["inputs"]["initial_volume_port_m3"], 5.0)
        self.assertEqual(control["inputs"]["initial_volume_starboard_m3"], 6.0)
        reference = verification_oracles.reference_for(control)
        heel_slope = reference["quantities"]["initial_heel_slope_q"]["value"]
        residual = 19964.0 * heel_slope ** 3 + 40063.0 * heel_slope - 84.0
        self.assertLess(abs(residual), 1e-9, heel_slope)

    def test_boundary_and_cancel_controls_declare_their_expected_behaviour(self):
        boundary = [case for case in self.flooding
                    if case["kind"] == "flooding.control_model_boundary"]
        cancel = [case for case in self.flooding
                  if case["kind"] == "flooding.control_cancel"]
        self.assertEqual(len(boundary), 1)
        self.assertEqual(len(cancel), 1)
        self.assertEqual(boundary[0]["expected"]["stop_class"], "model_limit")
        self.assertEqual(boundary[0]["expected"]["reason"],
                         "receiver_capacity")
        self.assertEqual(cancel[0]["expected"]["stop_class"], "canceled")
        self.assertEqual(cancel[0]["expected"]["reason"], "canceled")
        # The cancel request must be JSON data, never a callable.
        self.assertEqual(cancel[0]["inputs"]["cancel_after_accepted_steps"], 6)
        json.dumps(cancel[0], allow_nan=False)

    def test_reversal_guard_control_uses_a_coarse_step_that_could_overshoot(self):
        guard = [case for case in self.flooding
                 if case["kind"] == "flooding.control_reversal_guard"]
        self.assertEqual(len(guard), 1)
        self.assertGreater(guard[0]["inputs"]["time_step_s"], 0.125)
        names = {check["name"] for check in guard[0]["expected"]["checks"]}
        self.assertIn("transfer_never_reverses_direction", names)

    def test_flooding_inputs_are_self_contained_canonical_payloads(self):
        for case in self.flooding:
            inputs = case["inputs"]
            self.assertEqual(inputs["scenario_schema"],
                             "plimsoll-flooding-scenario-1", case["id"])
            scenario = inputs["scenario"]
            self.assertEqual(scenario["schema"], "plimsoll-flooding-scenario-1")
            self.assertEqual(scenario["duration_s"], inputs["duration_s"])
            self.assertEqual(scenario["time_step_s"], inputs["time_step_s"])
            self.assertEqual(inputs["project"]["schema"], "plimsoll-project-1")
            self.assertTrue(scenario["tanks"], case["id"])
            self.assertTrue(scenario["connections"], case["id"])
            sea_ids = {tank["id"] for tank in scenario["tanks"]}
            for connection in scenario["connections"]:
                self.assertNotEqual(connection["from"], connection["to"])
                self.assertTrue(
                    connection["from"] == scenario["sea"]["id"]
                    or connection["to"] in sea_ids
                    or connection["from"] in sea_ids, case["id"])
            json.dumps(inputs, allow_nan=False, sort_keys=True)


class OracleFloodingReferenceTest(unittest.TestCase):
    """The flooding references: piecewise equilibrium and attitude feedback."""

    def setUp(self):
        self.flooding = [case for case
                         in verification_cases.build_cases("all")
                         if case["family"] == "flooding"]

    def _single_sea(self, duration, step):
        return next(case for case in self.flooding
                    if case["kind"] == "flooding.long_replay"
                    and case["inputs"]["scenario_name"]
                    == "single_sea_coupled_box"
                    and case["inputs"]["duration_s"] == duration
                    and case["inputs"]["time_step_s"] == step)

    def test_single_sea_reference_reproduces_the_published_five_second_anchor(self):
        # Published independent anchor for the supported single sea coupled
        # box: 20x10x6 hull, Awp 200 m^2, 4x2x4 tank (S = 8 m^2), rho 1.025,
        # base 401.8 t at KG 1 m, tank 8 m^3, aperture (0,0,0.1), A 0.1 m^2,
        # Cd 0.6, g 9.80665.  Net sea inflow at 5 s is 1.2756512554179793 m^3.
        reference = verification_oracles.reference_for(
            self._single_sea(60.0, 0.25))
        five_second = reference["samples"]["t=5.0"]["net_sea_influx_m3"]
        self.assertAlmostEqual(five_second, 1.2756512554179793, delta=1e-12)
        self.assertAlmostEqual(five_second,
                               reference["samples"]["t=5.0"]["net_sea_influx_m3"],
                               delta=0.0)

    def test_single_sea_reference_declares_the_finite_equalization_instant(self):
        reference = verification_oracles.reference_for(
            self._single_sea(300.0, 0.125))
        plateau = reference["quantities"]["plateau_time_s"]["value"]
        # Published independent instant at which the finite hydraulic
        # equilibrium of this fixture is reached.
        self.assertAlmostEqual(plateau, 62.72232718774828, delta=1e-9)
        influx = reference["quantities"]["plateau_net_influx_m3"]["value"]
        self.assertAlmostEqual(influx, 25.0 / 3.0, delta=1e-12)

    def test_single_sea_reference_is_constant_after_equalization(self):
        reference = verification_oracles.reference_for(
            self._single_sea(300.0, 0.125))
        after = reference["samples"]["t=300.0"]["net_sea_influx_m3"]
        self.assertAlmostEqual(after, 25.0 / 3.0, delta=1e-12)
        # The pre-equilibrium squared formula continued to 300 s would give a
        # different (and wrong) answer; the reference must not do that.
        continued = reference["quantities"][
            "pre_equilibrium_squared_formula_at_longest_sample_m3"]["value"]
        self.assertGreater(abs(continued - 25.0 / 3.0), 1.0)
        self.assertAlmostEqual(after, reference["quantities"][
            "plateau_net_influx_m3"]["value"], delta=1e-12)

    def test_single_sea_reference_volume_matches_the_published_60s_value(self):
        reference = verification_oracles.reference_for(
            self._single_sea(60.0, 0.25))
        at_60 = reference["samples"]["t=60.0"]["net_sea_influx_m3"]
        # Independent hand derivation: with a = 1/S - 1/Awp = 0.12 per m^2,
        # H0 = 1 m and K = Cd*A*sqrt(2g), V(t) - V0 = (H0 - (sqrt(H0) - aKt/2)^2)/a.
        a = 1.0 / 8.0 - 1.0 / 200.0
        flow = 0.6 * 0.1 * math.sqrt(2.0 * 9.80665)
        expected = (1.0 - (1.0 - a * flow * 60.0 / 2.0) ** 2) / a
        self.assertAlmostEqual(a, 0.12, delta=1e-15)
        self.assertAlmostEqual(at_60, expected, delta=1e-12)

    def _two_tank(self, duration, step):
        return next(case for case in self.flooding
                    if case["kind"] == "flooding.long_replay"
                    and case["inputs"]["scenario_name"]
                    == "two_tank_asymmetric_free_float"
                    and case["inputs"]["duration_s"] == duration
                    and case["inputs"]["time_step_s"] == step)

    def test_two_tank_reference_initial_state_is_hand_derivable(self):
        case = self._two_tank(60.0, 0.25)
        reference = verification_oracles.reference_for(case)
        quantities = reference["quantities"]
        # Independent hand derivation of the mass ledger: the dry mass is
        # 389 * 1.025 = 398.725 t and the two tanks hold 5 + 6 = 11 m3, so the
        # displaced volume is 389 + 11 = 400 m3 and the 20 x 10 box floats at
        # draft = 400 / 200 = 2 m exactly.
        self.assertAlmostEqual(quantities["dry_mass_equivalent_volume_m3"]["value"],
                               389.0, delta=1e-12)
        self.assertAlmostEqual(quantities["displaced_volume_m3"]["value"], 400.0,
                               delta=1e-12)
        self.assertAlmostEqual(quantities["draft_m"]["value"], 2.0, delta=1e-12)
        self.assertAlmostEqual(quantities["total_water_volume_m3"]["value"], 11.0,
                               delta=1e-12)
        # At zero heel the two mean depths are 5/4 and 6/8 and the column
        # intercepts are d_a = h_a + q/2 and d_b = h_b - q, so the head
        # difference at q=0 is 5/4 - 6/8 = 0.5 m at the shared aperture.
        self.assertAlmostEqual(quantities["initial_head_difference_m"]["value"],
                               (0.5 + 1.5 * quantities["initial_heel_slope_q"]["value"])
                               / math.sqrt(1.0 + quantities["initial_heel_slope_q"]["value"] ** 2),
                               delta=1e-12)

    def test_two_tank_reference_matches_an_independent_quadrature_solve(self):
        case = self._two_tank(60.0, 0.25)
        reference = verification_oracles.reference_for(case)
        slope = reference["quantities"]["initial_heel_slope_q"]["value"]
        self.assertNotEqual(slope, 0.0)
        # Independent reconstruction of the tank-A column.  The tank spans
        # y in [-1, 0] with 4 m length, so k = 1/4 and c = -1/2, giving
        # d_a = V_a/4 + q/2 for a 5 m3 hold.
        port_volume, _, _ = independent_column_moments(
            slope, 5.0 / 4.0 + 0.5 * slope, -1.0, 0.0)
        self.assertAlmostEqual(port_volume * 4.0, 5.0, delta=1e-12)
        # Tank B spans y in [0, 2] with 4 m length: k = 1/8, c = 1, so
        # d_b = V_b/8 - q for a 6 m3 hold.
        star_volume, _, _ = independent_column_moments(
            slope, 6.0 / 8.0 - slope, 0.0, 2.0)
        self.assertAlmostEqual(star_volume * 4.0, 6.0, delta=1e-12)
        # Independent transverse equilibrium residual, by plain bisection.
        # Dividing the mass ledger by rho, the displaced volume is 400 m3 and
        # the dry mass contributes 389 * 1 m at KG 1 m.
        def residual(heel_slope):
            d_a = 5.0 / 4.0 + 0.5 * heel_slope
            d_b = 6.0 / 8.0 - heel_slope
            _, fy_a, fz_a = independent_column_moments(heel_slope, d_a, -1.0, 0.0)
            _, fy_b, fz_b = independent_column_moments(heel_slope, d_b, 0.0, 2.0)
            cg_y = 4.0 * (fy_a + fy_b) / 400.0
            cg_z = (389.0 + 4.0 * (fz_a + fz_b)) / 400.0
            buoy_y = heel_slope * 100.0 / 24.0
            buoy_z = 1.0 + heel_slope ** 2 * 100.0 / 48.0
            return (buoy_y - cg_y) + heel_slope * (buoy_z - cg_z)

        solved = _bisect(residual, -0.05, 0.05)
        self.assertAlmostEqual(slope, solved, delta=1e-11)
        self.assertLess(abs(residual(slope)), 1e-12)

    def test_two_tank_reference_reproduces_the_declared_positive_cubic(self):
        # Independently derived cubic for the initial equilibrium of this
        # fixture: substituting the published column integrals into
        # (By - Gy) + q(Bz - Gz) = 0 and clearing the positive denominators
        # gives 19964 q^3 + 40063 q - 84 = 0.
        case = self._two_tank(60.0, 0.25)
        reference = verification_oracles.reference_for(case)
        slope = reference["quantities"]["initial_heel_slope_q"]["value"]
        residual = 19964.0 * slope ** 3 + 40063.0 * slope - 84.0
        self.assertLess(abs(residual), 1e-9, slope)

    def test_two_tank_reference_includes_attitude_feedback(self):
        case = self._two_tank(300.0, 0.125)
        reference = verification_oracles.reference_for(case)
        initial = reference["samples"]["t=0.0"]
        plateau = reference["samples"]["t=300.0"]
        # Independent hand derivation of the feedback term.  With p = 0 the
        # liquid planes are z = q y + d_i, the unit-normal offsets are
        # c_i = d_i / sqrt(1+q^2), and both planes share one aperture, so
        # H = (d_a - d_b)/sqrt(1+q^2) with
        #   d_a - d_b = V_a/4 - V_b/8 + 3q/2.
        # The "3q/2" term is the attitude feedback a frozen-attitude oracle
        # cannot produce.
        slope = initial["heel_slope_q"]
        volumes = case["inputs"]["reference_spec"]["initial_volumes_m3"]
        fixed_attitude_head = volumes[0] / 4.0 - volumes[1] / 8.0
        feedback_head = (fixed_attitude_head + 1.5 * slope) \
            / math.sqrt(1.0 + slope * slope)
        self.assertAlmostEqual(initial["head_difference_m"], feedback_head,
                               delta=1e-12)
        self.assertNotAlmostEqual(initial["head_difference_m"],
                                  fixed_attitude_head, places=6)
        self.assertAlmostEqual(reference["quantities"][
            "head_attitude_feedback_coefficient_dh_dq"]["value"], 1.5,
            delta=1e-12)
        # The equilibrium heel itself moves as water is transferred.
        self.assertNotAlmostEqual(initial["heel_slope_q"],
                                  plateau["heel_slope_q"], places=6)
        self.assertLess(abs(plateau["head_difference_m"]),
                        abs(initial["head_difference_m"]))
        # Equality is a terminal event; the analytic flow does not cross it.
        self.assertLess(abs(plateau["head_difference_m"]), 1e-10)

    def test_two_tank_reference_is_not_the_fixed_attitude_pair_oracle(self):
        case = self._two_tank(300.0, 0.125)
        reference = verification_oracles.reference_for(case)
        # The old frozen-attitude pair solution transfers S*(H0-Ht)/2 with the
        # symmetric surface area; the reference must differ from that.
        self.assertFalse(reference["relations"]["is_fixed_attitude_pair_oracle"])
        self.assertFalse(reference["relations"]["is_final_equal_volume_answer"])
        final_port = reference["quantities"]["final_volume_port_m3"]["value"]
        self.assertNotAlmostEqual(final_port, 16.0, places=3)
        self.assertGreater(abs(final_port - 16.0), 2.0)

    def test_two_tank_reference_liquid_surfaces_never_clip(self):
        for case in [self._two_tank(60.0, 0.25), self._two_tank(300.0, 0.125)]:
            reference = verification_oracles.reference_for(case)
            bounds = reference["relations"]["liquid_surface_bounds_m"]
            self.assertGreater(bounds["minimum_above_tank_bottom_m"], 0.0,
                               case["id"])
            self.assertLess(bounds["maximum_below_tank_top_m"],
                            reference["relations"]["tank_height_m"], case["id"])
            self.assertGreater(bounds["minimum_aperture_head_m"], 0.0, case["id"])
            self.assertGreater(
                bounds["hull_wedge_margin_m"],
                reference["relations"]["hull_wedge_used_m"], case["id"])

    def test_two_tank_reference_hull_never_breaches_its_plates(self):
        case = self._two_tank(300.0, 0.125)
        reference = verification_oracles.reference_for(case)
        self.assertGreater(reference["relations"]["hull_wedge_used_m"], 0.0)
        self.assertLess(reference["relations"]["hull_wedge_used_m"],
                        reference["relations"]["hull_depth_headroom_m"])


class ReferenceModulePurityTest(unittest.TestCase):
    """The oracle is math only; the case builder borrows no test or doc file."""

    def _imported_names(self, module_name):
        path = PKG / f"{module_name}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ""
                names.add(prefix)
                names.update(f"{prefix}.{alias.name}" for alias in node.names)
        return names, path

    def test_oracle_imports_only_the_standard_library(self):
        names, path = self._imported_names("verification_oracles")
        self.assertTrue(names, path)
        for name in names:
            root = name.split(".")[0]
            self.assertNotIn(root, ("plimsoll", "project_io", "stability",
                                    "flooding", "tank_geometry", "geometry",
                                    "hydrostatics", "geometric", "loading",
                                    "damage", "freesurface", "hull", "engines"),
                             f"{path.name} imports {name}")
            self.assertNotIn("tests", name, path.name)
        roots = {name.split(".")[0] for name in names}
        self.assertEqual(roots, {"__future__", "math", "json", "bisect"},
                         f"{path.name} imports {sorted(roots)}")

    def test_case_builder_imports_no_test_module_and_no_docs(self):
        names, path = self._imported_names("verification_cases")
        for name in names:
            self.assertNotIn("test", name.split(".")[0], path.name)
            self.assertNotIn("convergence", name.split(".")[0], path.name)
        roots = {name.split(".")[0] for name in names}
        self.assertEqual(roots, {"__future__", "copy", "json", "math"},
                         f"{path.name} imports {sorted(roots)}")

    def test_reference_for_rejects_an_unknown_case_kind(self):
        with self.assertRaises(KeyError):
            verification_oracles.reference_for({"kind": "not-a-real-kind",
                                                "inputs": {}})
        with self.assertRaises(KeyError):
            verification_oracles.reference_for({"kind": "transform.scale_linear"})

    def test_every_reference_is_strict_json_safe(self):
        for case in verification_cases.build_cases("all"):
            reference = verification_oracles.reference_for(case)
            text = json.dumps(reference, sort_keys=True, allow_nan=False,
                              ensure_ascii=True)
            self.assertEqual(json.loads(text), reference, case["id"])
            for path_name, number in walk_numbers(reference):
                self.assertTrue(math.isfinite(number),
                                f"{case['id']} reference{path_name}")


class ReferenceMeaningTest(unittest.TestCase):
    """Analytic agreement is never presented as physical accuracy."""

    def test_references_separate_the_five_evidence_kinds(self):
        for case in verification_cases.build_cases("all"):
            reference = verification_oracles.reference_for(case)
            meanings = reference["limitations"]
            joined = " ".join(meanings).lower()
            self.assertIn("analytic", joined, case["id"])
            self.assertIn("not", joined, case["id"])
            self.assertIn("experimental", joined, case["id"])
            self.assertNotIn("validated against sea trials", joined, case["id"])

    def test_flooding_references_report_model_applicability_separately(self):
        flooding = [case for case in verification_cases.build_cases("all")
                    if case["family"] == "flooding"]
        self.assertTrue(flooding)
        for case in flooding:
            reference = verification_oracles.reference_for(case)
            applicability = reference["relations"]["model_applicability"]
            self.assertTrue(applicability["vented_single_fluid"])
            self.assertTrue(applicability["static_sea_surface"])
            self.assertTrue(applicability["point_orifice_fully_submerged"])
            self.assertFalse(applicability["external_experiment_measured"])

    def test_mesh_applicability_names_its_actual_geometry(self):
        case = next(case for case in verification_cases.build_cases("quick") if case["family"] == "mesh")
        applicability = verification_oracles.reference_for(case)["relations"]["model_applicability"]
        self.assertEqual(applicability["geometry_model"], "continuous_ellipsoid")
        self.assertNotIn("wall_sided_hull_only", applicability)

    def test_pair_control_includes_transfer_before_plateau_and_signed_samples(self):
        for identity in ("flooding-control-head-port-to-starboard", "flooding-control-head-starboard-to-port"):
            case = next(case for case in verification_cases.build_cases("all") if case["id"] == identity)
            reference = verification_oracles.reference_for(case)
            self.assertTrue(any(row["before_equalisation"] for row in reference["transient_quadrature_controls"]))
            bounds = reference["relations"]["full_interval_bounds"]
            self.assertLess(bounds["directed_head_derivative_upper_per_m2"], 0.)
            self.assertGreater(bounds["positive_head_factor_lower_per_m2"], 0.)
            final = reference["quantities"]["net_transfer_m3"]["value"]
            sample = max(reference["samples"].values(), key=lambda row: row["time_s"])["net_transfer_m3"]
            self.assertAlmostEqual(sample, final)
            names = {item["name"] for item in reference["evidence"]["controls"]}
            self.assertNotIn("equalisation_volume_vs_coarse_quadrature", names)

    def test_mirror_absolute_datum_is_applied_once(self):
        case = copy.deepcopy(next(case for case in verification_cases.build_cases("quick") if case["id"] == "transform-mirror-dry"))
        base = verification_oracles.reference_for(case)
        case["inputs"]["box"]["keel_offset_m"] += 13.25
        case["inputs"]["box"]["cg_z_m"] += 13.25
        shifted = verification_oracles.reference_for(case)
        for key in ("buoyancy_centre_m", "cg_m"):
            self.assertAlmostEqual(shifted["quantities"][key]["value"][2] - base["quantities"][key]["value"][2], 13.25)


if __name__ == "__main__":  # pragma: no cover - manual entry point
    unittest.main()
