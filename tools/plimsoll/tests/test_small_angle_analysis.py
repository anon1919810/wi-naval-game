"""Coordinator integration for the F06 inclined-equilibrium stability kernel.

The coordinator must expose the new kernel as a nested result without
disturbing the existing upright hydrostatic facts, must carry the kernel
method version in both stage metadata and request identity, and must keep the
scalar roll period honest.

Analytic anchors (the same continuous barge as
``test_small_angle_stability.py``, keel datum, rho = 1.025 t/m3)
---------------------------------------------------------------
``V = L*B*d``, ``xB = p*L**2/(12*d)``, ``zB = d/2 + p**2*L**2/(24*d)`` and, with
``xG = xB + p*(zB - zG)`` so that the body floats at the requested trim:

* upright: the legacy definition ``gm_t_m = KM - KG`` with
  ``KM = d/2 + B**2/(12*d)`` stays available and equals 0.5333333 m;
* trimmed: that legacy definition is unavailable by definition, while the new
  physical-angle stiffness is ``sqrt(1+p**2)*(B**2/(12*d) + zB - zG)`` =
  0.8618535 m at 15 deg;
* a free-surface tank reduces the stiffness by exactly
  ``rho_liquid*l*b**3/12/m_total`` = 0.00406504 m, applied once;
* a sheared (asymmetric) hull keeps a valid static stiffness while the roll
  period stays unavailable, because ``TCG = 0`` is not a symmetry proof.
"""

import copy
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve()
TOOLS_DIR = HERE.parents[2]
PACKAGE_DIR = HERE.parents[1]
for candidate in (str(TOOLS_DIR), str(PACKAGE_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from plimsoll import analysis, loading  # noqa: E402
from plimsoll import _analysis_request as request_api  # noqa: E402

KERNEL_METHOD = "free_trim_equilibrium_roll_stiffness_v1"
NEW_ROLL_METHOD = "selected_loading_equilibrium_roll_v2"
OLD_ROLL_METHOD = "selected_loading_small_angle_roll_v1"
LENGTH, BEAM, MEAN_DRAFT, DECK, RHO, KG = 20.0, 8.0, 4.0, 12.0, 1.025, 2.8
DISPLACEMENT_T = LENGTH * BEAM * MEAN_DRAFT * RHO          # 656 t
STATIONS, RELATIVE_TOLERANCE, ABSOLUTE_TOLERANCE = 129, 2e-4, 2e-5
GYRATION, GYRATION_SOURCE = 0.38, "declared study coefficient"
SHEAR = 0.2


def trim_slope(trim_deg):
    return math.tan(math.radians(trim_deg))


def buoyancy_centre_xz(trim_deg):
    slope = trim_slope(trim_deg)
    return (slope * LENGTH ** 2 / (12 * MEAN_DRAFT),
            MEAN_DRAFT / 2 + slope * slope * LENGTH ** 2 / (24 * MEAN_DRAFT))


def trimmed_lcg(trim_deg, kg=KG):
    """LCG that makes the continuous body float at ``trim_deg``."""
    xb, zb = buoyancy_centre_xz(trim_deg)
    return xb + trim_slope(trim_deg) * (zb - kg)


def analytic_upright_gm(kg=KG):
    """Legacy upright ``KM - KG`` and the coincident physical-angle stiffness."""
    return BEAM ** 2 / (12 * MEAN_DRAFT) + MEAN_DRAFT / 2 - kg


def analytic_trimmed_gm(trim_deg, kg=KG):
    _, zb = buoyancy_centre_xz(trim_deg)
    return math.sqrt(1 + trim_slope(trim_deg) ** 2) * (BEAM ** 2 / (12 * MEAN_DRAFT) + zb - kg)


def analytic_sheared_gm(shear=SHEAR, kg=KG):
    a0 = LENGTH ** 2 / (12 * MEAN_DRAFT)
    return (BEAM ** 2 / (12 * MEAN_DRAFT) + shear ** 2 * a0 + MEAN_DRAFT / 2 - kg
            - (shear * a0) ** 2 / (a0 + MEAN_DRAFT / 2 - kg))


def tank_dict(identifier="f06-tank"):
    return dict(id=identifier, length_m=4.0, beam_m=2.0, height_m=2.0, x_m=0.0, y_m=0.0,
                keel_to_bottom_m=0.5, permeability=1.0)


def tank_fill(volume_m3, density_t_m3=1.0):
    """Solid/moving split whose combined upright CG is exactly ``KG``."""
    mass = DISPLACEMENT_T - volume_m3 * density_t_m3
    liquid_kg = tank_dict()["keel_to_bottom_m"] + volume_m3 / (4.0 * 2.0) / 2
    return mass, (DISPLACEMENT_T * KG - volume_m3 * density_t_m3 * liquid_kg) / mass


def barge_project(*, trim_deg=0.0, shear=0.0, stations=STATIONS, mass=DISPLACEMENT_T,
                  kg=KG, lcg=None, roll_source=GYRATION_SOURCE):
    rows = []
    for index in range(stations):
        x = -LENGTH / 2 + LENGTH * index / (stations - 1)
        rows.append([x, [[shear * x + y, z] for y, z in
                         ((-BEAM / 2, 0.0), (BEAM / 2, 0.0), (BEAM / 2, DECK), (-BEAM / 2, DECK))]])
    return dict(
        schema="plimsoll-project-1", id="f06-analytic-barge", name="F06 analytic barge",
        geometry=dict(kind="offsets", keel_offset_m=0.0, source="independent analytic barge",
                      estimate=False,
                      offsets=dict(schema="plimsoll-section-polygons-1", stations=rows)),
        hull=dict(lwl_m=LENGTH, beam_m=BEAM, draught_normal_m=MEAN_DRAFT, block_coeff=1.0,
                  waterplane_coeff=1.0, roll_gyration_coeff=GYRATION,
                  sources=dict(roll_gyration_coeff=roll_source)),
        weight_groups=[dict(id="solid", items=[dict(
            id="analytic-load", mass_t=mass, x_m=trimmed_lcg(trim_deg, kg) if lcg is None else lcg,
            y_m=0.0, kg_m=kg, source="independent analytic loading", estimate=False)])],
        loading_conditions=[dict(id="loaded")], opening_definition="supplied", openings=[])


def compute(project, options=None, condition_id="loaded"):
    return analysis.compute_project(project, condition_id,
                                    options if options is not None else {"stages": ["hydrostatics"]})


class SmallAngleResultExposureTests(unittest.TestCase):
    """The nested kernel result and the legacy upright facts stay distinct."""

    def hydrostatics(self, project, options=None):
        result = compute(project, options)
        self.assertEqual(result["stages"]["hydrostatics"]["status"], "completed", result["status"])
        return result, result["stages"]["hydrostatics"]["data"]

    def test_upright_case_reports_both_definitions_and_the_same_number(self):
        result, data = self.hydrostatics(barge_project())
        nested = data["small_angle_stability"]
        self.assertEqual(nested["method_version"], KERNEL_METHOD)
        self.assertEqual(nested["status"], "completed", nested.get("reason"))
        self.assertTrue(nested["definition"])
        self.assertTrue(data["gm_definition"])
        # Legacy upright definition: KM - KG on the selected upright plane.
        self.assertTrue(math.isclose(data["values"]["gm_t_m"], analytic_upright_gm(),
                                     rel_tol=1e-9, abs_tol=1e-9),
                        f"legacy gm_t_m {data['values']['gm_t_m']!r} against "
                        f"{analytic_upright_gm()!r}")
        # New definition: its own key, carrying the kernel number verbatim.
        self.assertIn("equilibrium_gm_t_m", data["values"])
        self.assertEqual(data["values"]["equilibrium_gm_t_m"], nested["equilibrium_gm_m"])
        self.assertTrue(math.isclose(nested["equilibrium_gm_m"], analytic_upright_gm(),
                                     rel_tol=RELATIVE_TOLERANCE, abs_tol=ABSOLUTE_TOLERANCE),
                        f"measured {nested['equilibrium_gm_m']!r} against "
                        f"{analytic_upright_gm()!r}")
        json.dumps(result, allow_nan=False)

    def test_trimmed_case_keeps_the_legacy_field_unavailable_and_reports_the_new_one(self):
        result, data = self.hydrostatics(barge_project(trim_deg=15.0))
        nested = data["small_angle_stability"]
        # The legacy definition is upright-only and must stay unavailable.
        self.assertIsNone(data["values"]["gm_t_m"])
        self.assertIn("inclined", data["gm_definition"])
        self.assertEqual(nested["status"], "completed", nested.get("reason"))
        expected = analytic_trimmed_gm(15.0)
        self.assertEqual(data["values"]["equilibrium_gm_t_m"], nested["equilibrium_gm_m"])
        self.assertTrue(math.isclose(nested["equilibrium_gm_m"], expected,
                                     rel_tol=RELATIVE_TOLERANCE, abs_tol=ABSOLUTE_TOLERANCE),
                        f"measured {nested['equilibrium_gm_m']!r} against analytic {expected!r}")
        # Physical-angle convention, not the waterplane-slope derivative.
        slope_answer = BEAM ** 2 / (12 * MEAN_DRAFT) + buoyancy_centre_xz(15.0)[1] - KG
        self.assertGreater(abs(nested["equilibrium_gm_m"] - slope_answer), 1e-2)
        json.dumps(result, allow_nan=False)

    def test_unavailable_kernel_result_never_fails_valid_hydrostatics(self):
        # Prescribing heel 0.0 forces the attitude, so the kernel must refuse;
        # the upright hydrostatic measures are still valid and must survive.
        result, data = self.hydrostatics(barge_project(),
                                         {"stages": ["hydrostatics"],
                                          "equilibrium": {"heel_deg": 0.0}})
        nested = data["small_angle_stability"]
        self.assertNotEqual(nested["status"], "completed")
        self.assertIsNone(nested["equilibrium_gm_m"])
        self.assertTrue(nested["reason"])
        self.assertIsNone(data["values"]["equilibrium_gm_t_m"])
        self.assertTrue(math.isclose(data["values"]["gm_t_m"], analytic_upright_gm(),
                                     rel_tol=1e-9, abs_tol=1e-9),
                        "valid upright measures must not be dropped by a nested failure")
        self.assertEqual(result["status"], "completed")
        json.dumps(result, allow_nan=False)

    def test_incomplete_loading_blocks_before_the_kernel_is_reached(self):
        project = barge_project()
        project["weight_groups"][0]["items"][0]["mass_t"] = None
        result = compute(project)
        hydrostatics = result["stages"]["hydrostatics"]
        self.assertNotEqual(hydrostatics["status"], "completed")
        self.assertIsNone(hydrostatics["data"])
        self.assertNotEqual(result["status"], "completed")
        self.assertTrue(result["diagnostics"])
        json.dumps(result, allow_nan=False)

    def test_project_and_request_stay_immutable(self):
        project = barge_project(trim_deg=15.0)
        before = copy.deepcopy(project)
        result = compute(project, {"stages": ["equilibrium", "hydrostatics"]})
        self.assertEqual(project, before)
        self.assertEqual(result["input_fingerprint"],
                         loading.resolve_loading(project, "loaded")["input_fingerprint"])
        replay = compute(project, result["request"]["options"])
        self.assertEqual(replay["request_fingerprint"], result["request_fingerprint"])


class MethodIdentityTests(unittest.TestCase):
    """A stale kernel must not be able to present itself as current."""

    def test_kernel_method_version_is_in_stage_metadata_and_request_identity(self):
        result = compute(barge_project(), {"stages": ["equilibrium", "hydrostatics"]})
        self.assertIn(KERNEL_METHOD, result["method_versions"].values())
        self.assertIn(KERNEL_METHOD, result["stages"]["hydrostatics"]["method_versions"].values())
        self.assertIn(KERNEL_METHOD, request_api.VERSIONS.values(),
                      "the request digest is computed from VERSIONS, so the kernel method "
                      "version must live there or a stale result can appear current")
        nested = result["stages"]["hydrostatics"]["data"]["small_angle_stability"]
        self.assertEqual(nested["method_version"], KERNEL_METHOD)

    def test_stale_kernel_identity_changes_the_request_fingerprint(self):
        project = barge_project()
        current = compute(project)
        self.assertIn(KERNEL_METHOD, request_api.VERSIONS.values())
        key = next(k for k, v in request_api.VERSIONS.items() if v == KERNEL_METHOD)
        with patch.dict(request_api.VERSIONS, {key: KERNEL_METHOD + "-stale"}):
            stale = compute(project)
        self.assertNotEqual(stale["request_fingerprint"], current["request_fingerprint"])
        self.assertEqual(stale["input_fingerprint"], current["input_fingerprint"])
        self.assertNotIn(KERNEL_METHOD, stale["method_versions"].values())


class ScalarRollAvailabilityTests(unittest.TestCase):
    """Period availability stays bounded by sourced inertia and by symmetry."""

    def roll(self, project, options=None):
        result = compute(project, options)
        data = result["stages"]["hydrostatics"]["data"]
        self.assertIsNotNone(data, result["stages"]["hydrostatics"].get("reason"))
        return result, data, data["loaded_roll"]

    def test_upright_without_liquids_keeps_the_existing_roll_result(self):
        result, data, roll = self.roll(barge_project())
        self.assertEqual(roll["status"], "completed", roll.get("reason"))
        self.assertEqual(roll["method"], OLD_ROLL_METHOD)
        self.assertEqual(roll["source"], GYRATION_SOURCE)
        beam = data["values"]["waterline_beam_body_y_m"]
        self.assertAlmostEqual(beam, BEAM, places=9)
        expected = 2 * math.pi * GYRATION * beam / math.sqrt(9.80665 * data["values"]["gm_t_m"])
        self.assertAlmostEqual(roll["period_s"], expected, places=9)
        json.dumps(result, allow_nan=False)

    def test_local_waterplane_contact_blocks_the_legacy_period_in_both_solver_modes(self):
        project = barge_project(stations=3, mass=328.0)
        section = [[-4, 0], [4, 0], [4, 12], [1, 12], [1, 2], [-1, 2], [-1, 12], [-4, 12]]
        for row in project['geometry']['offsets']['stations']:
            row[1] = copy.deepcopy(section)
        for equilibrium_options in ({}, {'heel_deg': 0.0}):
            with self.subTest(options=equilibrium_options):
                result, data, roll = self.roll(project, {
                    'stages': ['equilibrium', 'hydrostatics'], 'equilibrium': equilibrium_options})
                solved = result['stages']['equilibrium']['data']
                self.assertTrue(solved['converged'])
                self.assertAlmostEqual(solved['waterline_d_m'], 2.0, places=10)
                self.assertEqual(roll['status'], 'unavailable')
                self.assertIsNone(roll['period_s'])
                self.assertIn('contact', roll['reason'])
                self.assertTrue(roll['symmetry']['symmetry_proved'])
                self.assertFalse(roll['symmetry']['baseline_applicable'])
                json.dumps(result, allow_nan=False)

    def test_smooth_legacy_period_does_not_depend_on_probe_refinement(self):
        with patch.object(analysis.small_angle_stability, 'analyze', return_value={
                'status': 'unavailable', 'reason': 'perturbation refinement failed',
                'equilibrium_gm_m': None}):
            _, _, roll = self.roll(barge_project(stations=3))
        self.assertEqual(roll['status'], 'completed', roll['reason'])
        self.assertEqual(roll['method'], OLD_ROLL_METHOD)

    def test_upright_with_moving_liquid_uses_the_new_method_and_one_correction(self):
        volume, density = 8.0, 1.0
        mass, solid_kg = tank_fill(volume, density)
        options = {"stages": ["equilibrium", "hydrostatics"],
                   "equilibrium": {"liquid_loads": [dict(tank=tank_dict(), volume_m3=volume,
                                                         fluid_density_t_m3=density)]}}
        result, data, roll = self.roll(barge_project(mass=mass, kg=solid_kg), options)
        nested = data["small_angle_stability"]
        self.assertEqual(nested["status"], "completed", nested.get("reason"))
        correction = density * 4.0 * 2.0 ** 3 / 12 / DISPLACEMENT_T
        expected_gm = analytic_upright_gm() - correction
        self.assertTrue(math.isclose(nested["equilibrium_gm_m"], expected_gm,
                                     rel_tol=RELATIVE_TOLERANCE, abs_tol=ABSOLUTE_TOLERANCE),
                        f"measured {nested['equilibrium_gm_m']!r} against {expected_gm!r}")
        # The period must be built from the new restoring height, not the legacy
        # KM - KG, and must not subtract the free-surface correction twice.
        self.assertEqual(roll["status"], "completed", roll.get("reason"))
        self.assertEqual(roll["method"], NEW_ROLL_METHOD)
        beam = data["values"]["waterline_beam_body_y_m"]
        from_new = 2 * math.pi * GYRATION * beam / math.sqrt(9.80665 * nested["equilibrium_gm_m"])
        from_legacy = 2 * math.pi * GYRATION * beam / math.sqrt(9.80665 * data["values"]["gm_t_m"])
        from_double = 2 * math.pi * GYRATION * beam / math.sqrt(
            9.80665 * (nested["equilibrium_gm_m"] - correction))
        self.assertAlmostEqual(roll["period_s"], from_new, places=6)
        self.assertGreater(abs(roll["period_s"] - from_legacy), 1e-3)
        self.assertGreater(abs(roll["period_s"] - from_double), 1e-3)
        self.assertTrue(roll["estimate"])
        json.dumps(result, allow_nan=False)

    def test_nonzero_trim_keeps_the_period_unavailable(self):
        result, data, roll = self.roll(barge_project(trim_deg=15.0))
        self.assertEqual(roll["status"], "unavailable")
        self.assertIsNone(roll["period_s"])
        self.assertTrue(roll["reason"])
        # The static stiffness survives: only the dynamic claim is refused.
        self.assertEqual(data["small_angle_stability"]["status"], "completed")
        self.assertNotEqual(roll["method"], NEW_ROLL_METHOD)
        json.dumps(result, allow_nan=False)

    def test_asymmetric_hull_keeps_the_period_unavailable_despite_zero_tcg(self):
        project = barge_project(shear=SHEAR)
        result, data, roll = self.roll(project)
        nested = data["small_angle_stability"]
        self.assertEqual(nested["status"], "completed", nested.get("reason"))
        expected = analytic_sheared_gm()
        self.assertTrue(math.isclose(nested["equilibrium_gm_m"], expected,
                                     rel_tol=RELATIVE_TOLERANCE, abs_tol=ABSOLUTE_TOLERANCE),
                        f"measured {nested['equilibrium_gm_m']!r} against {expected!r}")
        self.assertEqual(loading.resolve_loading(project, "loaded")["values"]["tcg_m"], 0.0)
        self.assertEqual(roll["status"], "unavailable",
                         "zero total TCG is not a reflection-symmetry proof")
        self.assertIsNone(roll["period_s"])
        self.assertTrue(roll["reason"])
        json.dumps(result, allow_nan=False)

    def test_missing_gyration_source_keeps_the_period_unavailable(self):
        for source in (None, ""):
            project = barge_project(roll_source=source)
            if source is None:
                project["hull"].pop("sources")
            _, _, roll = self.roll(project)
            self.assertEqual(roll["status"], "unavailable", f"source={source!r}")
            self.assertIsNone(roll["period_s"])
            self.assertTrue(roll["reason"])


if __name__ == "__main__":
    unittest.main()
