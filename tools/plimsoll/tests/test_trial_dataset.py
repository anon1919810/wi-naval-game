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

    def test_no_single_form_parameter_explains_the_sign(self):
        """Documented with n=19: neither Froude number nor block coefficient does it.

        Battlecruisers at Fr 0.31-0.33 over-predict 2-26 %, light cruisers at Fr
        0.40-0.42 under-predict 1-4 %, and ships inside the same block-coefficient
        band land on both sides of zero. Two earlier hypotheses (a 31 kn threshold,
        then the block coefficient) were falsified by new data; this test keeps the
        dataset honest about that rather than encoding a third guess.
        """
        cases = td.usable_cases()
        over = [c for c in cases if c["model"]["error_pct"] > 10]
        under = [c for c in cases if c["model"]["error_pct"] < -5]
        self.assertGreaterEqual(len(over), 4, "the dataset must keep its over-predicting cases")
        self.assertGreaterEqual(len(under), 2, "and its under-predicting ones")
        band = [c for c in cases if 0.50 <= c["hull"]["block_coeff"] < 0.55]
        signs = {c["model"]["error_pct"] > 0 for c in band}
        self.assertEqual(signs, {True, False},
                         "the central block-coefficient band must contain both signs, or the "
                         "claim that Cb sets the sign would stand")


if __name__ == "__main__":
    unittest.main()
