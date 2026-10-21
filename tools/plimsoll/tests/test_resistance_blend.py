"""The blend weight must be smooth, bounded and honest about a missing side."""
import unittest

from plimsoll import resistance_blend as blend


class BlendShareTests(unittest.TestCase):
    def test_share_is_bounded_and_decreases_with_a_fuller_hull(self):
        shares = [blend.holtrop_share(cb) for cb in (0.40, 0.44, 0.47, 0.50, 0.53, 0.56, 0.60)]
        self.assertTrue(all(0.0 <= share <= 1.0 for share in shares))
        self.assertEqual(shares, sorted(shares, reverse=True))

    def test_a_slender_hull_hands_over_to_holtrop_and_a_full_hull_does_not(self):
        self.assertGreater(blend.holtrop_share(0.44), 0.80)
        self.assertLess(blend.holtrop_share(0.56), 0.20)

    def test_the_transition_is_continuous(self):
        step = 0.001
        for cb in (0.46, 0.49, 0.50, 0.51, 0.54):
            self.assertLess(abs(blend.holtrop_share(cb + step) - blend.holtrop_share(cb)), 0.02)

    def test_a_hull_outside_the_transition_band_belongs_to_one_family(self):
        self.assertGreater(blend.holtrop_share(0.38), 0.95)
        self.assertLess(blend.holtrop_share(0.65), 0.05)

    def test_a_block_coefficient_outside_its_domain_is_rejected(self):
        for bad in (0.0, 1.0, -0.2, 1.4, None, True, "0.5"):
            with self.assertRaises(blend.BlendInputError):
                blend.holtrop_share(bad)


class BlendResistanceTests(unittest.TestCase):
    def test_the_blend_lies_between_the_two_families(self):
        out = blend.blend_resistance(1000.0, 1200.0, 0.50)
        self.assertTrue(out["blended"])
        self.assertAlmostEqual(out["total_resistance_kn"], 1100.0)

    def test_a_missing_side_is_named_rather_than_silently_substituted(self):
        only_holtrop = blend.blend_resistance(None, 1200.0, 0.45)
        self.assertFalse(only_holtrop["blended"])
        self.assertEqual(only_holtrop["total_resistance_kn"], 1200.0)
        self.assertIn("Holtrop", only_holtrop["reason"])
        only_taylor = blend.blend_resistance(1000.0, None, 0.45)
        self.assertFalse(only_taylor["blended"])
        self.assertEqual(only_taylor["total_resistance_kn"], 1000.0)
        neither = blend.blend_resistance(None, None, 0.45)
        self.assertIsNone(neither["total_resistance_kn"])

    def test_a_negative_resistance_is_rejected(self):
        with self.assertRaises(blend.BlendInputError):
            blend.blend_resistance(-1.0, 1200.0, 0.50)


class FittedFormShareTests(unittest.TestCase):
    def test_the_fitted_share_is_bounded(self):
        for cb in (0.35, 0.45, 0.50, 0.56, 0.65):
            for bt in (2.5, 3.0, 3.5, 4.5):
                self.assertTrue(0.0 <= blend.holtrop_share_form(cb, bt) <= 1.0)

    def test_a_fuller_hull_and_a_beamer_hull_both_move_toward_taylor(self):
        self.assertGreater(blend.holtrop_share_form(0.45, 3.0), blend.holtrop_share_form(0.56, 3.0))
        self.assertGreater(blend.holtrop_share_form(0.52, 3.0), blend.holtrop_share_form(0.52, 4.2))

    def test_the_fitted_share_is_continuous_in_both_parameters(self):
        base = blend.holtrop_share_form(0.52, 3.4)
        self.assertLess(abs(blend.holtrop_share_form(0.521, 3.4) - base), 0.03)
        self.assertLess(abs(blend.holtrop_share_form(0.52, 3.41) - base), 0.02)

    def test_a_parameter_outside_its_domain_is_rejected(self):
        for cb, bt in ((0.0, 3.0), (1.0, 3.0), (0.5, 0.0), (0.5, -1.0), (None, 3.0), (0.5, "3")):
            with self.assertRaises(blend.BlendInputError):
                blend.holtrop_share_form(cb, bt)


if __name__ == "__main__":
    unittest.main()
