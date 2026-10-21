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


if __name__ == "__main__":
    unittest.main()
