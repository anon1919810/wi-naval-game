"""Independent checks for the versioned Holtrop--Mennen 1982 kernel."""

from __future__ import annotations

import copy
import math
import os
import sys
import unittest

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PKG)

import holtrop  # noqa: E402


def benchmark() -> dict:
    """Return the source-fixed 1982 comparison inputs."""
    return {
        "lwl_m": 205.0,
        "beam_m": 32.0,
        "draft_fore_m": 10.0,
        "draft_aft_m": 10.0,
        "displacement_volume_m3": 37_500.0,
        "midship_coeff": 0.98,
        "waterplane_coeff": 0.75,
        "lcb_percent_lwl": -0.75,
        "c_stern": 10.0,
        "bulb_area_m2": 20.0,
        "bulb_height_m": 4.0,
        "transom_area_m2": 16.0,
        "appendages": [{"area_m2": 50.0, "factor": 1.5}],
        "speed_kn": 25.0,
        "density_kg_m3": 1025.0,
        "gravity_m_s2": 9.81,
        "kinematic_viscosity_m2_s": 1.188e-6,
        "bow_thruster": {"present": False},
        "additional_roughness_delta_ca": 0.0,
        "input_provenance": {
            "midship_coeff": {"source": "Holtrop and Mennen 1982 p. 170", "estimate": False}
        },
    }


class HoltropBenchmarkTests(unittest.TestCase):
    def test_independent_ntua_1982_components_at_source_fixed_tolerance(self):
        """Catch coefficient or unit changes hidden by a total-only check."""
        values = holtrop.compute(benchmark())["values"]
        expected = {
            "rf_kn": 869.47,
            "rapp_kn": 8.83,
            "rw_kn": 556.63,
            "rb_kn": 0.049,
            "rtr_kn": 0.0,
            "ra_kn": 220.53,
            "total_resistance_kn": 1791.54,
            "effective_power_kw": 23039.0,
        }
        for key, reference in expected.items():
            floor = 0.5 if key == "effective_power_kw" else 0.005
            if key == "rb_kn":
                floor = 0.0005
            self.assertTrue(
                math.isclose(values[key], reference, rel_tol=0.001, abs_tol=floor),
                (key, values[key], reference),
            )
        self.assertEqual(values["rtr_kn"], 0.0)

    def test_total_power_and_density_scaling_are_independent_identities(self):
        """Catch applying the form factor twice or converting N/kN incorrectly."""
        case = benchmark()
        values = holtrop.compute(case)["values"]
        expected = values["rf_kn"] * values["one_plus_k1"] + sum(
            values[key]
            for key in ("rapp_kn", "rw_kn", "rb_kn", "rtr_kn", "ra_kn", "rbto_kn", "roughness_kn")
        )
        self.assertTrue(math.isclose(expected, values["total_resistance_kn"], rel_tol=1e-10))
        self.assertTrue(
            math.isclose(
                expected * 25.0 * 1852.0 / 3600.0,
                values["effective_power_kw"],
                rel_tol=1e-10,
            )
        )
        case["density_kg_m3"] *= 2.0
        doubled = holtrop.compute(case)["values"]["total_resistance_kn"]
        self.assertTrue(math.isclose(doubled, 2.0 * expected, rel_tol=1e-10))

    def test_explicit_area_and_multi_appendage_force_identity(self):
        """Catch use of unweighted appendage area or hidden area estimation."""
        case = benchmark()
        case["wetted_surface_m2"] = 5000.0
        case["appendages"] = [
            {"area_m2": 10.0, "factor": 2.0},
            {"area_m2": 30.0, "factor": 1.5},
        ]
        result = holtrop.compute(case)
        values = result["values"]
        speed = 25.0 * 1852.0 / 3600.0
        q = 0.5 * 1025.0 * speed**2
        expected_rf = q * 5000.0 * values["cf"] / 1000.0
        expected_rapp = q * 65.0 * values["cf"] / 1000.0
        self.assertTrue(math.isclose(values["rf_kn"], expected_rf, rel_tol=1e-10))
        self.assertTrue(math.isclose(values["rapp_kn"], expected_rapp, rel_tol=1e-10))
        self.assertEqual(result["wetted_surface_method"], "explicit_input")

    def test_input_is_not_mutated_and_provenance_survives(self):
        """Catch destructive normalization or provenance loss."""
        case = benchmark()
        before = copy.deepcopy(case)
        result = holtrop.compute(case)
        self.assertEqual(case, before)
        self.assertEqual(result["method"], "holtrop_mennen_1982")
        self.assertEqual(result["input_provenance"], case["input_provenance"])
        self.assertEqual(result["units"]["resistance"], "kN")
        self.assertEqual(result["applicability"]["algebraic_status"], "valid")


class HoltropBranchTests(unittest.TestCase):
    def test_all_published_piecewise_boundaries_choose_declared_branch(self):
        """Catch shifted thresholds or silent smoothing of rounded coefficients."""
        for ratio in (0.019999, 0.02, 0.020001, 0.049999, 0.05, 0.050001, 0.08):
            expected = (
                0.479948
                if ratio < 0.02
                else 48.2 * (ratio - 0.02) ** 2.078 + 0.479948
                if ratio <= 0.05
                else ratio**0.2228446
            )
            self.assertAlmostEqual(holtrop.c12(ratio), expected, places=14)
        for ratio in (0.109999, 0.11, 0.110001, 0.249999, 0.25, 0.250001, 0.30):
            expected = (
                0.229577 * ratio ** (1.0 / 3.0)
                if ratio < 0.11
                else ratio
                if ratio <= 0.25
                else 0.5 - 0.0625 / ratio
            )
            self.assertAlmostEqual(holtrop.c7(ratio), expected, places=14)
        for slenderness in (511.99, 512.0, 512.01, 1726.99, 1727.0, 1727.01, 2000.0):
            length_volume = slenderness ** (1.0 / 3.0)
            expected = (
                -1.69385
                if slenderness < 512.0
                else -1.69385 + (length_volume - 8.0) / 2.36
                if slenderness <= 1727.0
                else 0.0
            )
            self.assertAlmostEqual(holtrop.c15(slenderness), expected, places=13)
        for cp in (0.799999, 0.8, 0.800001):
            expected = (
                8.07981 * cp - 13.8673 * cp**2 + 6.984388 * cp**3
                if cp <= 0.8
                else 1.73014 - 0.7067 * cp
            )
            self.assertAlmostEqual(holtrop.c16(cp), expected, places=14)
        self.assertAlmostEqual(holtrop.wave_lambda(0.6, 11.999), 1.446 * 0.6 - 0.03 * 11.999)
        self.assertAlmostEqual(holtrop.wave_lambda(0.6, 12.0), 1.446 * 0.6 - 0.36)
        self.assertEqual(holtrop.c4(0.04), 0.04)
        self.assertEqual(holtrop.c4(0.040001), 0.04)
        self.assertAlmostEqual(holtrop.c6(4.999999), 0.2 * (1.0 - 0.2 * 4.999999))
        self.assertEqual(holtrop.c6(5.0), 0.0)

    def test_declared_zero_geometry_short_circuits_singular_formulas(self):
        """Catch treating declared absence as a tiny positive area."""
        case = benchmark()
        case.update(bulb_area_m2=0.0, bulb_height_m=None, transom_area_m2=0.0, appendages=[])
        values = holtrop.compute(case)["values"]
        for key in ("rb_kn", "rtr_kn", "rapp_kn"):
            self.assertEqual(values[key], 0.0)
        self.assertEqual(values["c2"], 1.0)
        self.assertEqual(values["c5"], 1.0)

    def test_positive_and_zero_transom_coefficient_branches(self):
        """Catch rejecting c5=0 or using the wrong transom-Froude threshold."""
        low_speed = benchmark()
        low_speed["speed_kn"] = 10.0
        values = holtrop.compute(low_speed)["values"]
        self.assertTrue(math.isclose(values["rtr_kn"], 24.541711223514703, rel_tol=1e-10))
        zero_c5 = benchmark()
        zero_c5["transom_area_m2"] = 32.0 * 10.0 * 0.98 / 0.8
        self.assertEqual(holtrop.compute(zero_c5)["values"]["c5"], 0.0)

    def test_negative_pb_is_real_but_zero_divisor_is_rejected(self):
        """Catch imposing the 1984 hB recommendation as 1982 algebraic domain."""
        case = benchmark()
        case["bulb_height_m"] = 7.0
        values = holtrop.compute(case)["values"]
        self.assertLess(values["pb"], 0.0)
        self.assertTrue(math.isclose(values["rb_kn"], 136.03149710014387, rel_tol=1e-10))
        case["bulb_height_m"] = 10.0 / 1.5
        with self.assertRaises(holtrop.HoltropInputError):
            holtrop.compute(case)

    def test_fore_draft_terms_do_not_use_mean_draft(self):
        """Catch replacing TF-only bulb/correlation terms with mean draft."""
        fore_deep = benchmark()
        fore_deep.update(draft_fore_m=12.0, draft_aft_m=8.0)
        aft_deep = benchmark()
        aft_deep.update(draft_fore_m=8.0, draft_aft_m=12.0)
        fore_values = holtrop.compute(fore_deep)["values"]
        aft_values = holtrop.compute(aft_deep)["values"]
        self.assertEqual(fore_values["c12"], aft_values["c12"])
        self.assertEqual(fore_values["one_plus_k1"], aft_values["one_plus_k1"])
        self.assertNotEqual(fore_values["c4"], aft_values["c4"])
        self.assertNotEqual(fore_values["rb_kn"], aft_values["rb_kn"])


class HoltropDomainAndEligibilityTests(unittest.TestCase):
    def test_missing_is_not_declared_zero(self):
        """Catch fabrication of absent empirical geometry."""
        for key in ("bulb_area_m2", "transom_area_m2", "appendages", "lcb_percent_lwl"):
            case = benchmark()
            del case[key]
            with self.assertRaises(holtrop.HoltropInputError, msg=key):
                holtrop.compute(case)

    def test_invalid_and_extreme_inputs_raise_contextual_kernel_errors(self):
        """Catch raw OverflowError/ZeroDivisionError and nonfinite output leakage."""
        for key, value in (
            ("speed_kn", 0),
            ("beam_m", True),
            ("lwl_m", math.nan),
            ("displacement_volume_m3", math.inf),
            ("midship_coeff", 0),
            ("waterplane_coeff", 1),
            ("transom_area_m2", 50_000),
            ("speed_kn", 1e200),
            ("speed_kn", 10**400),
            ("transom_area_m2", 5e-324),
        ):
            case = benchmark()
            case[key] = value
            with self.assertRaises(holtrop.HoltropError, msg=(key, value)):
                holtrop.compute(case)

    def test_kernel_errors_carry_structured_blocking_diagnostics(self):
        """Catch callers having to parse exception text to report unavailability."""
        case = benchmark()
        case["speed_kn"] = 1e200
        with self.assertRaises(holtrop.HoltropNumericalError) as caught:
            holtrop.compute(case)
        diagnostic = caught.exception.diagnostics[0]
        self.assertEqual(diagnostic["code"], "holtrop.numerical_domain")
        self.assertEqual(diagnostic["severity"], "error")
        self.assertTrue(diagnostic["blocking"])
        self.assertIn("path", diagnostic)

    def test_tiny_positive_bulb_area_returns_finite_result_or_contextual_error(self):
        """Catch raw overflow from PB inverse-square evaluation."""
        case = benchmark()
        case["bulb_area_m2"] = 5e-324
        try:
            result = holtrop.compute(case)
        except holtrop.HoltropError:
            return
        self.assertTrue(all(value is None or math.isfinite(value) for value in result["values"].values()))

    def test_low_reynolds_and_high_froude_are_not_primary_results(self):
        """Catch equating a finite equation evaluation with empirical eligibility."""
        low_re = benchmark()
        speed_mps = 25.0 * 1852.0 / 3600.0
        low_re["kinematic_viscosity_m2_s"] = speed_mps * 205.0 / 101.0
        result = holtrop.compute(low_re)
        self.assertFalse(result["applicability"]["primary_result"])
        self.assertEqual(result["applicability"]["turbulent_policy"], "project_policy_reynolds_ge_1e5")
        self.assertTrue(any(d["code"] == "holtrop.low_reynolds_project_policy" for d in result["diagnostics"]))
        high_fn = benchmark()
        high_fn["speed_kn"] = 55.0
        result = holtrop.compute(high_fn)
        self.assertFalse(result["applicability"]["primary_result"])
        self.assertTrue(any(d["code"] == "holtrop.high_froude_1982" for d in result["diagnostics"]))

    def test_unknown_optional_terms_make_scenario_incomplete(self):
        """Catch silently assuming absent roughness or bow-thruster increments."""
        case = benchmark()
        del case["bow_thruster"]
        del case["additional_roughness_delta_ca"]
        result = holtrop.compute(case)
        self.assertFalse(result["scenario"]["complete"])
        self.assertFalse(result["applicability"]["primary_result"])
        self.assertTrue(any(d["code"] == "holtrop.optional_terms_unknown" for d in result["diagnostics"]))

    def test_optional_bow_thruster_and_roughness_are_applied_once(self):
        """Catch dropping or double-counting optional 1982 additions."""
        case = benchmark()
        case["bow_thruster"] = {"present": True, "diameter_m": 2.0, "coefficient": 0.006}
        case["additional_roughness_delta_ca"] = 0.0001
        values = holtrop.compute(case)["values"]
        speed = 25.0 * 1852.0 / 3600.0
        expected_thruster = 1025.0 * speed**2 * math.pi * 2.0**2 * 0.006 / 1000.0
        expected_roughness = 0.5 * 1025.0 * speed**2 * values["wetted_surface_m2"] * 0.0001 / 1000.0
        self.assertTrue(math.isclose(values["rbto_kn"], expected_thruster, rel_tol=1e-10))
        self.assertTrue(math.isclose(values["roughness_kn"], expected_roughness, rel_tol=1e-10))


if __name__ == "__main__":
    unittest.main()
