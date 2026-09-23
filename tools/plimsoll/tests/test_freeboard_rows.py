"""Declared deck-segment freeboard projection: weighted mean, coverage, honest unknowns.

Ship-agnostic synthetic decks except the single Queen Mary integration check at
the end. The projection is a *declared-input* view: it never reads z_m, never
uses the sealed-envelope top, and never treats an unknown freeboard as zero.
"""

import sys
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
TOOLS = PKG.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import page_rows, project_store  # noqa: E402


def fb(value, source="declared fixture", estimate=True):
    """A declared freeboard fact."""
    return {"value": value, "source": source, "estimate": estimate}


def point(point_id, x, freeboard=None):
    p = {"id": point_id, "x_m": x, "y_m": 0.0, "z_m": 15.0}
    if freeboard is not None:
        p["freeboard_m"] = freeboard
    return p


def deck(points, segments, reference_length=200.0):
    d = {"estimate": True, "source": "synthetic fixture",
         "points": points, "segments": segments}
    if reference_length is not None:
        d["reference_length_m"] = {"value": reference_length, "source": "synthetic fixture",
                                   "estimate": True}
    return d


class FreeboardProjectionTests(unittest.TestCase):
    def test_segment_mean_and_length_weighted_only_over_declared(self):
        d = deck(
            points=[point("P0", -100.0, fb(5.0)), point("P1", 0.0, fb(7.0)),
                    point("P2", 100.0)],  # P2 has no declared freeboard
            segments=[
                {"id": "S0", "aft_point_id": "P0", "fore_point_id": "P1"},
                {"id": "S1", "aft_point_id": "P1", "fore_point_id": "P2"},
            ])
        result = page_rows.freeboard_rows(d)
        codes = {diag["code"] for diag in result["diagnostics"]}

        s0, s1 = result["segments"]
        # S0: both endpoints declared
        self.assertEqual(s0["status"], "declared")
        self.assertAlmostEqual(s0["length_m"], 100.0, places=9)
        self.assertAlmostEqual(s0["length_percent"], 50.0, places=9)
        self.assertAlmostEqual(s0["freeboard_aft_m"], 5.0, places=9)
        self.assertAlmostEqual(s0["freeboard_fore_m"], 7.0, places=9)
        self.assertAlmostEqual(s0["segment_mean_freeboard_m"], 6.0, places=9)
        # S1: fore endpoint freeboard unknown -> not in the weighted mean
        self.assertEqual(s1["status"], "unknown_missing_freeboard")
        self.assertAlmostEqual(s1["length_m"], 100.0, places=9)
        self.assertAlmostEqual(s1["length_percent"], 50.0, places=9)
        self.assertAlmostEqual(s1["freeboard_aft_m"], 7.0, places=9)
        self.assertIsNone(s1["freeboard_fore_m"])
        self.assertIsNone(s1["segment_mean_freeboard_m"])

        # Weighted mean uses only S0: (100*6)/100 = 6.0
        self.assertAlmostEqual(result["values"]["weighted_mean_freeboard_m"], 6.0, places=9)
        self.assertTrue(result["values"]["weighted_mean_estimate"])
        # Coverage: 100 m of 200 m of declared segments known
        self.assertAlmostEqual(result["values"]["coverage_fraction"], 0.5, places=9)
        self.assertEqual(result["values"]["known_segment_ids"], ["S0"])
        self.assertEqual(result["values"]["unknown_segment_ids"], ["S1"])
        self.assertIn("page_rows.freeboard_unknown", codes)
        self.assertNotIn("page_rows.reference_length_unknown", codes)

    def test_unknown_reference_length_nulls_percent_and_warns(self):
        d = deck(
            points=[point("P0", -100.0, fb(5.0)), point("P1", 100.0, fb(7.0))],
            segments=[{"id": "S0", "aft_point_id": "P0", "fore_point_id": "P1"}],
            reference_length=None)  # no reference_length_m at all
        result = page_rows.freeboard_rows(d)
        codes = {diag["code"] for diag in result["diagnostics"]}
        self.assertIn("page_rows.reference_length_unknown", codes)
        # length itself is still known; only the percentage is null
        self.assertAlmostEqual(result["segments"][0]["length_m"], 200.0, places=9)
        self.assertIsNone(result["segments"][0]["length_percent"])
        self.assertIsNone(result["values"]["reference_length_m"])
        # weighted mean is still computable from lengths
        self.assertAlmostEqual(result["values"]["weighted_mean_freeboard_m"], 6.0, places=9)

    def test_segment_referencing_unknown_point_is_reported(self):
        d = deck(
            points=[point("P0", -100.0, fb(5.0)), point("P1", 100.0, fb(7.0))],
            segments=[{"id": "S0", "aft_point_id": "P0", "fore_point_id": "ghost"}])
        result = page_rows.freeboard_rows(d)
        codes = {diag["code"] for diag in result["diagnostics"]}
        self.assertIn("page_rows.segment_points_unknown", codes)
        self.assertEqual(result["segments"][0]["status"], "unknown_missing_endpoint")
        self.assertIsNone(result["segments"][0]["length_m"])
        # the broken segment must not leak into the weighted mean
        self.assertIsNone(result["values"]["weighted_mean_freeboard_m"])
        # no segment has a computable length here, so coverage is unknown (None)
        self.assertIsNone(result["values"]["coverage_fraction"])
        self.assertEqual(result["values"]["unknown_segment_ids"], ["S0"])


class QueenMaryIntegrationTests(unittest.TestCase):
    """Queen Mary's deck is a sealed-envelope study top, NOT a surveyed freeboard.

    The projection must report freeboard *unknown* and must never derive a
    freeboard value from z_m (15.0) or the envelope top.
    """

    @classmethod
    def setUpClass(cls):
        case = (PKG / "cases" / "projects" / "queen_mary_1913.project.json")
        cls.project = project_store.load(case)
        cls.deck = cls.project["deck"]

    def test_queen_mary_freeboard_is_unknown_not_invented(self):
        result = page_rows.freeboard_rows(self.deck)
        seg = result["segments"][0]
        self.assertEqual(seg["id"], "centreline-profile")
        # No freeboard was declared on any point -> unknown, never derived.
        self.assertEqual(seg["status"], "unknown_missing_freeboard")
        self.assertIsNone(seg["freeboard_aft_m"])
        self.assertIsNone(seg["freeboard_fore_m"])
        self.assertIsNone(seg["segment_mean_freeboard_m"])
        # Geometry is still honest: length = 213.4 m, percent of ref = 100%.
        self.assertAlmostEqual(seg["length_m"], 213.4, places=9)
        self.assertAlmostEqual(seg["length_percent"], 100.0, places=9)
        # No freeboard number was invented anywhere.
        self.assertIsNone(result["values"]["weighted_mean_freeboard_m"])
        self.assertAlmostEqual(result["values"]["coverage_fraction"], 0.0, places=9)
        self.assertEqual(result["values"]["known_segment_ids"], [])
        self.assertEqual(result["values"]["unknown_segment_ids"], ["centreline-profile"])
        # Explicitly: nothing equals the sealed-envelope z (15.0).
        envelope_z = 15.0
        fb_numbers = [seg["freeboard_aft_m"], seg["freeboard_fore_m"],
                      seg["segment_mean_freeboard_m"],
                      result["values"]["weighted_mean_freeboard_m"]]
        for n in fb_numbers:
            self.assertNotEqual(n, envelope_z)
        # reference length is known for QM, so no reference_length_unknown warning
        self.assertNotIn("page_rows.reference_length_unknown",
                         {d["code"] for d in result["diagnostics"]})


if __name__ == "__main__":
    unittest.main()
