"""The trial dataset is an asset: it must validate, and its pinned errors must hold."""
import copy
import unittest

from plimsoll import trial_dataset as td


class DatasetIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.data = td.load()

    def test_the_file_declares_its_schema_and_units(self):
        self.assertEqual(self.data["schema"], td.SCHEMA)
        self.assertIn("SI", self.data["units"])

    def test_every_record_is_usable(self):
        cases = td.usable_cases(self.data)
        self.assertEqual(len(cases), len(self.data["cases"]))

    def test_a_record_without_provenance_is_refused(self):
        record = copy.deepcopy(self.data["cases"][0])
        record["source"]["quote"] = "  "
        self.assertIn("source.quote must carry the sentence the figure came from", td.validate(record))

    def test_an_implausible_speed_is_refused(self):
        record = copy.deepcopy(self.data["cases"][0])
        record["trial"]["speed_kt"] = 10.0
        problems = td.validate(record)
        self.assertTrue(any("speed_kt outside" in p for p in problems))

    def test_an_implausible_power_per_tonne_is_refused(self):
        record = copy.deepcopy(self.data["cases"][0])
        record["trial"]["shp"] = 4_000_000
        self.assertTrue(any("shp per tonne" in p for p in td.validate(record)))

    def test_a_duplicate_id_is_refused(self):
        data = copy.deepcopy(self.data)
        data["cases"].append(copy.deepcopy(data["cases"][0]))
        with self.assertRaises(td.DatasetError):
            td.usable_cases(data)


class DatasetSummaryTests(unittest.TestCase):
    def test_the_summary_splits_by_form_and_speed(self):
        out = td.summary()
        self.assertEqual(out["overall"]["n"], len(td.usable_cases()))
        self.assertIn("battlecruiser", out["by_type"])
        self.assertIn("30+ kn", out["by_speed"])
        self.assertTrue(out["by_block"])

    def test_the_summary_reports_percent_not_a_hundred_times_percent(self):
        out = td.summary()
        self.assertLess(out["overall"]["mape"], 100.0)
        self.assertLess(out["overall"]["median"], 100.0)

    def test_the_pinned_errors_still_describe_the_dataset(self):
        cases = td.usable_cases()
        by_name = {c["name"]: c for c in cases}
        self.assertAlmostEqual(by_name["Bismarck"]["model"]["error_pct"], -0.43, places=2)
        self.assertAlmostEqual(by_name["HMS Hood"]["model"]["error_pct"], 22.45, places=2)
        self.assertAlmostEqual(by_name["HMS Dreadnought"]["model"]["error_pct"], 9.27, places=2)

    def test_at_high_froude_the_sign_follows_the_block_coefficient(self):
        """The error does not turn on speed; it turns on how fine the hull is.

        At Fr >= 0.28 the finest hull in the set (Furious, Cb 0.396) under-predicts
        while the fuller ones (Cb 0.499-0.539) over-predict. An earlier version of
        this test claimed a 31 kn threshold; adding a carrier at 28.8 kn with a fine
        hull broke that claim, which is exactly what the dataset is for.
        """
        cases = td.usable_cases()
        fast = []
        for case in cases:
            length = case["hull"]["length_m"]
            froude = (0.514444 * case["trial"]["speed_kt"]) / (9.81 * length) ** 0.5
            if froude >= 0.28:
                fast.append((case["hull"]["block_coeff"], case["model"]["error_pct"], case["name"]))
        self.assertGreaterEqual(len(fast), 5, "the fast group needs enough cases to test the claim")
        finest = min(fast)
        fullest = max(fast)
        self.assertLess(finest[1], 0.0, finest[2] + " is the finest hull and should under-predict")
        self.assertGreater(fullest[1], 0.0, fullest[2] + " is the fullest hull and should over-predict")


if __name__ == "__main__":
    unittest.main()
