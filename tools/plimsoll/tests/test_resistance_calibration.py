"""The recorded calibration must stay auditable and must refuse what it cannot cover."""
import unittest

from plimsoll import resistance_calibration as cal


class CalibrationRecordTests(unittest.TestCase):
    def test_every_record_carries_its_sample_and_a_nested_score(self):
        for method, record in cal.CALIBRATION.items():
            self.assertGreater(record["sample"], 0, method)
            self.assertLess(record["loocv_mape"], record["baseline_mape"], method)
            self.assertGreaterEqual(record["loocv_mape"], record["in_sample_mape"], method)
            self.assertEqual(set(record["factors"]), {"battleship", "carrier", "cruiser", "destroyer"})

    def test_the_documented_score_is_the_one_stored(self):
        self.assertAlmostEqual(cal.CALIBRATION[cal.TAYLOR_ORIGINAL]["loocv_mape"], 12.11)
        self.assertAlmostEqual(cal.CALIBRATION[cal.BLENDED]["loocv_mape"], 10.62)
        self.assertAlmostEqual(cal.CALIBRATION[cal.BLENDED]["baseline_mape"], 11.86)


class ApplyCalibrationTests(unittest.TestCase):
    def test_a_known_type_is_scaled_and_audited(self):
        out = cal.apply_calibration(30000.0, cal.BLENDED, "destroyer")
        self.assertAlmostEqual(out["power_hp"], 30000.0 * 0.979)
        self.assertEqual(out["factor"], 0.979)
        self.assertEqual(out["sample"], 146)
        self.assertIn("resistance-benchmark", out["source"])

    def test_an_unfitted_ship_type_is_refused_rather_than_treated_as_one(self):
        with self.assertRaises(cal.CalibrationError):
            cal.factor_for(cal.BLENDED, "submarine")

    def test_an_unrecorded_method_is_refused(self):
        with self.assertRaises(cal.CalibrationError):
            cal.calibration_for("some_new_method")

    def test_a_power_that_is_not_a_non_negative_number_is_refused(self):
        for bad in (-1.0, True, "30000", None):
            with self.assertRaises(cal.CalibrationError):
                cal.apply_calibration(bad, cal.BLENDED, "cruiser")


class ClusterFactorTests(unittest.TestCase):
    def test_a_hull_inside_the_cluster_gets_the_level_correction(self):
        deep = cal.cluster_factor(0.55, 260.0, 0.35)
        self.assertAlmostEqual(deep["factor"], cal.CLUSTER_FACTOR, delta=0.02)
        self.assertTrue(deep["applied"])
        # Hood sits inside the band but not at its centre, so she takes most of
        # the correction rather than all of it.
        hood = cal.cluster_factor(0.517, 257.0, 0.329)
        self.assertGreater(hood["factor"], 0.85)
        self.assertLess(hood["factor"], 0.93)
        self.assertTrue(hood["applied"])

    def test_a_hull_outside_the_cluster_is_left_alone(self):
        for args in ((0.565, 128.0, 0.422), (0.532, 149.0, 0.290), (0.396, 240.0, 0.305)):
            out = cal.cluster_factor(*args)
            self.assertAlmostEqual(out["factor"], 1.0, delta=0.02, msg=str(args))
            self.assertFalse(out["applied"], str(args))

    def test_the_correction_fades_rather_than_stepping(self):
        values = [cal.cluster_factor(0.52, length, 0.32)["factor"] for length in (190, 200, 210, 220)]
        self.assertEqual(values, sorted(values, reverse=True))
        for left, right in zip(values, values[1:]):
            self.assertLess(abs(left - right), 0.15)

    def test_the_recorded_evidence_travels_with_the_factor(self):
        out = cal.cluster_factor(0.517, 257.0, 0.329)
        self.assertEqual(out["sample"], cal.CLUSTER_SAMPLE)
        self.assertLess(out["loocv_mae"], out["uncorrected_mae"])
        self.assertIn("resistance-methods-and-data", out["source"])


class FactorIntervalTests(unittest.TestCase):
    def test_both_factors_carry_a_bootstrap_interval_around_the_point_estimate(self):
        for name, factor, ci in (("cluster", cal.CLUSTER_FACTOR, cal.CLUSTER_FACTOR_CI),
                                 ("design", cal.DESIGN_FACTOR, cal.DESIGN_FACTOR_CI)):
            low, high = ci
            self.assertLess(low, factor, name)
            self.assertGreater(high, factor, name)
            self.assertLess(high - low, 0.20, name + ": an interval wider than a fifth of the factor is not usable")

    def test_the_interval_travels_with_the_returned_record(self):
        self.assertEqual(cal.cluster_factor(0.55, 260.0, 0.35)["factor_ci"], cal.CLUSTER_FACTOR_CI)
        self.assertEqual(cal.design_factor()["factor_ci"], cal.DESIGN_FACTOR_CI)


if __name__ == "__main__":
    unittest.main()
