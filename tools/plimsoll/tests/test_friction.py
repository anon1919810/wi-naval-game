"""Independent friction-line checks and compatibility routing."""

from __future__ import annotations

import math
import os
import sys
import unittest

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PKG)

import resistance as R  # noqa: E402


class SchoenherrImplicitTests(unittest.TestCase):
    def test_official_ittc_table_2_at_printed_precision(self):
        """Catch substitution of an explicit fit for the implicit line."""
        anchors = (
            (1e5, 0.007179),
            (1e6, 0.004409),
            (5e6, 0.003294),
            (1e7, 0.002934),
            (1e8, 0.002072),
            (1e9, 0.001531),
            (1e10, 0.001172),
        )
        for reynolds, expected in anchors:
            value = R.friction_coefficient(reynolds, method="schoenherr_implicit_ittc_0.242")
            self.assertAlmostEqual(value["values"]["cf"], expected, delta=5e-7)
            self.assertEqual(value["method"], "schoenherr_implicit_ittc_0.242")

    def test_inverse_identity_and_equation_residual(self):
        """Catch a solver that only fits the rounded table anchors."""
        for expected_cf in (0.009, 0.006, 0.004, 0.003, 0.002, 0.001):
            reynolds = 10 ** (0.242 / math.sqrt(expected_cf)) / expected_cf
            result = R.friction_coefficient(reynolds, method="schoenherr_implicit_ittc_0.242")
            cf = result["values"]["cf"]
            self.assertTrue(math.isclose(cf, expected_cf, rel_tol=1e-10))
            self.assertLess(abs(0.242 / math.sqrt(cf) - math.log10(reynolds * cf)), 1e-10)

    def test_conn_compatibility_method_preserves_legacy_value(self):
        """Catch silently redefining the legacy schoenherr_cf API."""
        reynolds = 1e8
        legacy = R.schoenherr_cf(reynolds)
        named = R.friction_coefficient(reynolds, method="conn_1953_schoenherr_approx")
        expected = 0.4631 / math.log10(reynolds) ** 2.6
        self.assertEqual(legacy["values"]["cf"], expected)
        self.assertEqual(named["values"]["cf"], expected)
        self.assertEqual(named["method"], "conn_1953_schoenherr_approx")
        self.assertNotEqual(
            named["values"]["cf"],
            R.friction_coefficient(reynolds, method="schoenherr_implicit_ittc_0.242")["values"]["cf"],
        )

    def test_bad_or_unrepresentable_reynolds_is_rejected(self):
        """Catch bool/nonfinite values and raw integer-conversion overflow."""
        for value in (True, None, "1000000", math.nan, math.inf, -1, 0, 1, 10**400):
            with self.assertRaises(ValueError, msg=value):
                R.friction_coefficient(value, method="schoenherr_implicit_ittc_0.242")

    def test_unknown_method_is_rejected(self):
        """Catch accidental fallback to a default friction convention."""
        with self.assertRaises(ValueError):
            R.friction_coefficient(1e8, method="schoenherr")


if __name__ == "__main__":
    unittest.main()
