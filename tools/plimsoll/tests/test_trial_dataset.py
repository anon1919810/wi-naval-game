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

    def test_the_error_turns_positive_above_thirty_one_knots(self):
        """The boundary is a speed one, and it is above 30 kn.

        Bismarck at 30.1 kn lands at -0.43 %, while every ship at 31.7 kn or
        faster over-predicts by 20-26 %. A 30 kn cut would blur that, so the
        dataset records the speeds and this test states where the turn happens.
        """
        cases = td.usable_cases()
        fast = [c for c in cases if c["trial"]["speed_kt"] >= 31.0]
        slow = [c for c in cases if c["trial"]["speed_kt"] < 31.0]
        self.assertTrue(fast, "the dataset needs ships above 31 kn to pin this")
        for case in fast:
            self.assertGreater(case["model"]["error_pct"], 0.0, case["name"])
        for case in slow:
            self.assertLess(abs(case["model"]["error_pct"]), 15.0, case["name"])


if __name__ == "__main__":
    unittest.main()
