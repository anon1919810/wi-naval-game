"""Two sea-trial cases pin the model's error against measured power.

The set is deliberately tiny. It exists so a change to the empirical power path
cannot silently move our error against real trials: it is a tripwire, not a
benchmark, and nothing may be fitted on five ships.
"""
import json
import unittest
from pathlib import Path

from plimsoll import concept_estimates as ce

FIXTURE = Path(__file__).resolve().parents[1] / "cases" / "trial-cases-2026-10-19.json"
TOLERANCE_PCT = 0.5


def _value(result):
    return result[0] if isinstance(result, tuple) else result


def original_power(case):
    coefficient = _value(ce.co_sharp(case["length_ft"], case["beam_ft"], case["block_coeff"]))
    effective = _value(ce.effective_length_ft(case["length_ft"], case["beam_ft"], coefficient, "cruiser"))
    wetted = _value(ce.wetted_surface_sqft(case["length_ft"], case["draught_ft"], case["displacement_lt"]))
    return _value(ce.speed_hp(case["trial_speed_kt"], case["length_ft"], effective, coefficient,
                              case["displacement_lt"], wetted, 1900))


class TrialCaseTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_every_case_carries_its_own_provenance(self):
        self.assertEqual(self.fixture["schema"], "plimsoll-trial-cases-1")
        self.assertTrue(self.fixture["cases"])
        for case in self.fixture["cases"]:
            self.assertIn("provenance", case)
            self.assertTrue(case["source"].strip())
            self.assertGreater(case["trial_shp"], 0)
            self.assertGreater(case["trial_speed_kt"], 0)

    def test_the_recorded_error_against_each_trial_still_holds(self):
        for case in self.fixture["cases"]:
            predicted = original_power(case)
            error = 100 * (predicted - case["trial_shp"]) / case["trial_shp"]
            self.assertAlmostEqual(error, case["expected_error_pct"], delta=TOLERANCE_PCT,
                                   msg=case["name"])

    def test_the_set_stays_too_small_to_fit_anything(self):
        # A wider set would invite fitting; this one may only be a tripwire.
        self.assertLessEqual(len(self.fixture["cases"]), 5)


if __name__ == "__main__":
    unittest.main()
