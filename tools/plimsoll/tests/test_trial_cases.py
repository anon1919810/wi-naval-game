"""Measured-trial cases pin the empirical power path against reality.

The set is deliberately tiny and each figure carries its own provenance. It is a
tripwire: if a change moves the error against a measured trial, this fails. It is
not a fitting set, and nothing may be calibrated on five ships.
"""
import json
import unittest
from pathlib import Path

from plimsoll import concept_estimates as ce

FIXTURE = Path(__file__).resolve().parents[1] / "cases" / "trial-cases-2026-10-21.json"
TOLERANCE_PCT = 0.5
FT = 0.3048
LT = 1.0160469088


def _value(result):
    return result[0] if isinstance(result, tuple) else result


def original_power(case):
    """The legacy kernel speaks feet and long tons; the file speaks SI."""
    length_ft = case["lbp_m"] / FT
    beam_ft = case["beam_m"] / FT
    draught_ft = case["draught_m"] / FT
    displacement_lt = case["displacement_t"] / LT
    coefficient = _value(ce.co_sharp(length_ft, beam_ft, case["block_coeff"]))
    effective = _value(ce.effective_length_ft(length_ft, beam_ft, coefficient, "cruiser"))
    wetted = _value(ce.wetted_surface_sqft(length_ft, draught_ft, displacement_lt))
    return _value(ce.speed_hp(case["trial_speed_kt"], length_ft, effective, coefficient,
                              displacement_lt, wetted, 1900))


class TrialCaseTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_every_case_carries_its_own_provenance_and_basis(self):
        self.assertEqual(self.fixture["schema"], "plimsoll-trial-cases-2")
        self.assertTrue(self.fixture["cases"])
        for case in self.fixture["cases"]:
            self.assertIn(case["provenance"], ("trial_record", "trial_record_lower_bound"))
            self.assertTrue(case["source"].strip())
            self.assertGreater(case["trial_shp"], 0)
            self.assertGreater(case["trial_speed_kt"], 15)
            self.assertLess(case["trial_speed_kt"], 40)

    def test_the_recorded_error_against_each_trial_still_holds(self):
        for case in self.fixture["cases"]:
            predicted = original_power(case)
            error = 100 * (predicted - case["trial_shp"]) / case["trial_shp"]
            self.assertAlmostEqual(error, case["error_pct"], delta=TOLERANCE_PCT, msg=case["name"])

    def test_the_set_stays_too_small_to_fit_anything(self):
        self.assertLessEqual(len(self.fixture["cases"]), 8)

    def test_the_file_states_its_units(self):
        self.assertIn("SI", self.fixture["units"])


if __name__ == "__main__":
    unittest.main()
