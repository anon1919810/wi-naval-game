"""Blend weight between the two empirical resistance families.

The two methods are complementary over the historical record rather than one
being better: over the 146-case audit reproduced from the Rust reimplementation
(MIT), Taylor-Gertler wins 24 of 27 battleships but only 5 of 36 destroyers,
while Holtrop-Mennen wins the destroyers 31 of 36. The split follows the hull
form, not the speed: a full hull keeps the Taylor-Gertler family, a slender
high-speed hull hands over to Holtrop.

Choosing on form rather than on speed is what keeps a power curve continuous.
A criterion that read the speed would step the method at the crossing point and
leave a discontinuity in the very quantity the reader is plotting.

The criterion is a logistic in the block coefficient, centred between the two
populations the audit separates (destroyers near 0.44, cruisers and battleships
near 0.53-0.57). The half-width is deliberately wide enough that a hull in
between is blended instead of switched.
"""

from __future__ import annotations

import math

# Population centres taken from the 146-case class audit (see
# docs/plimsoll-1.0/resistance-benchmark-2026-10-19.md): destroyers ~0.44,
# cruisers/battleships ~0.53-0.57.
SLENDER_BLOCK_COEFF = 0.44
FULL_BLOCK_COEFF = 0.56
# Width of the transition, in block coefficient. A hull within this band is
# blended; outside it one family owns the answer.
TRANSITION_HALF_WIDTH = 0.035

# The audit rows behind those centres, so a later refit changes one place.
AUDIT = {
    "battleship": {"cases": 27, "taylor_wins": 24},
    "cruiser": {"cases": 42, "taylor_wins": 24},
    "carrier": {"cases": 23, "taylor_wins": 15},
    "destroyer": {"cases": 36, "taylor_wins": 5},
}


class BlendInputError(ValueError):
    """A form parameter that cannot be interpreted."""


def _number(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BlendInputError("%s must be a finite number" % what)
    out = float(value)
    if not math.isfinite(out):
        raise BlendInputError("%s must be finite" % what)
    return out


def holtrop_share(block_coeff) -> float:
    """Weight in [0, 1] for Holtrop-Mennen; the rest belongs to Taylor-Gertler.

    Zero means a full hull (Taylor-Gertler owns it), one means a slender hull
    (Holtrop owns it). The transition is a logistic in the block coefficient, so
    a hull between the two populations is blended instead of switched.
    """
    cb = _number(block_coeff, "block_coeff")
    if not 0.0 < cb < 1.0:
        raise BlendInputError("block_coeff must be inside (0, 1)")
    centre = 0.5 * (SLENDER_BLOCK_COEFF + FULL_BLOCK_COEFF)
    # Larger Cb means a fuller hull, so a smaller share for Holtrop.
    z = (cb - centre) / TRANSITION_HALF_WIDTH
    return 1.0 / (1.0 + math.exp(z))


def blend_resistance(taylor_kn, holtrop_kn, block_coeff=None, share=None) -> dict:
    """Blend one speed total resistance and say how it was blended.

    A side that could not be computed is named rather than silently replaced:
    the surviving side is reported with its own weight and blended=False, so a
    caller cannot mistake it for agreement between two models.
    """
    if share is None:
        share = holtrop_share(block_coeff)
    else:
        share = _number(share, "share")
        if not 0.0 <= share <= 1.0:
            raise BlendInputError("share must lie in [0, 1]")
    taylor = None if taylor_kn is None else _number(taylor_kn, "taylor_kn")
    holtrop = None if holtrop_kn is None else _number(holtrop_kn, "holtrop_kn")
    if taylor is not None and taylor < 0.0:
        raise BlendInputError("taylor_kn must not be negative")
    if holtrop is not None and holtrop < 0.0:
        raise BlendInputError("holtrop_kn must not be negative")
    if taylor is None and holtrop is None:
        return dict(total_resistance_kn=None, holtrop_share=share, blended=False,
                    reason="neither family produced a resistance at this speed")
    if holtrop is None:
        return dict(total_resistance_kn=taylor, holtrop_share=share, blended=False,
                    reason="only the Taylor-Gertler family covers this speed")
    if taylor is None:
        return dict(total_resistance_kn=holtrop, holtrop_share=share, blended=False,
                    reason="only the Holtrop family covers this speed")
    return dict(total_resistance_kn=(1.0 - share) * taylor + share * holtrop,
                holtrop_share=share, blended=True, reason=None)


# Coefficients fitted 2026-10-19 on the 146-case set by a coarse grid search over
# a linear form score, scored with a nested leave-one-out refit. The search put
# the whole weight on the block coefficient and the beam/draught ratio: the
# length-displacement ratio and the Froude number contributed nothing measurable.
# Signed so that a fuller hull and a beamier hull both move toward Taylor-Gertler.
FITTED_CENTRE_BLOCK_COEFF = 0.50
FITTED_CENTRE_BEAM_DRAUGHT = 3.0
FITTED_BLOCK_WEIGHT = -20.0
FITTED_BEAM_DRAUGHT_WEIGHT = -1.0
FITTED_OFFSET = 1.0


def holtrop_share_form(block_coeff, beam_draft_ratio):
    """The fitted two-parameter share, kept as an option next to the default rule.

    Nested leave-one-out on the 146 cases: 11.51 % against 11.86 % for the
    block-coefficient-only rule. A third of a point does not justify replacing a
    rule whose direction matches the per-class evidence, so this stays available
    rather than becoming the default.
    """
    cb = _number(block_coeff, "block_coeff")
    bt = _number(beam_draft_ratio, "beam_draft_ratio")
    if not 0.0 < cb < 1.0:
        raise BlendInputError("block_coeff must be inside (0, 1)")
    if bt <= 0.0:
        raise BlendInputError("beam_draft_ratio must be positive")
    z = (FITTED_BLOCK_WEIGHT * (cb - FITTED_CENTRE_BLOCK_COEFF)
         + FITTED_BEAM_DRAUGHT_WEIGHT * (bt - FITTED_CENTRE_BEAM_DRAUGHT)
         + FITTED_OFFSET)
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


# Boundaries read off the 24-case trial dataset (docs/plimsoll-1.0/
# resistance-methods-and-data-2026-10-21.md section 16): every hull of 200 m or
# more with Cb >= 0.49 running at Fr >= 0.30 over-predicts under the original
# method, and Holtrop halves that error on the same eight hulls (7.17 % against
# 15.03 %) while being worse on everything else (11.78 % against 9.17 %).
CLUSTER_LENGTH_M = 200.0
CLUSTER_BLOCK_COEFF = 0.49
CLUSTER_FROUDE = 0.30
# Widths and end points chosen by a coarse search over the 24 trial cases and
# then scored by leaving each case out and re-running the search: 9.24 % MAPE
# (median 6.43 %) against 11.13 % for the original method alone, 10.24 % for
# Holtrop alone and 11.08 % for the block-coefficient-only rule. The search space
# was five width sets by four end-point pairs, so the honest number is close to
# the tuned one.
CLUSTER_WIDTH_LENGTH = 12.0
CLUSTER_WIDTH_BLOCK = 0.015
CLUSTER_WIDTH_FROUDE = 0.010
CLUSTER_OUTSIDE_SHARE = 0.05
CLUSTER_SPAN = 0.90
CLUSTER_BLEND_LOOCV_MAPE = 9.24


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def holtrop_share_cluster(block_coeff, length_m, froude):
    """Share for Holtrop from three hull-form parameters, as a smooth AND.

    The three conditions multiply, so a hull has to satisfy all of them to hand
    over; failing any one keeps it on the original method. Each factor is a
    sigmoid, so the share stays continuous in every parameter and the same hull
    always gets the same weight - the weight is a property of the ship, never of
    the speed being evaluated.
    """
    cb = _number(block_coeff, "block_coeff")
    length = _number(length_m, "length_m")
    fr = _number(froude, "froude")
    if not 0.0 < cb < 1.0:
        raise BlendInputError("block_coeff must be inside (0, 1)")
    if length <= 0.0:
        raise BlendInputError("length_m must be positive")
    if fr <= 0.0:
        raise BlendInputError("froude must be positive")
    long_enough = _sigmoid((length - CLUSTER_LENGTH_M) / CLUSTER_WIDTH_LENGTH)
    full_enough = _sigmoid((cb - CLUSTER_BLOCK_COEFF) / CLUSTER_WIDTH_BLOCK)
    fast_enough = _sigmoid((fr - CLUSTER_FROUDE) / CLUSTER_WIDTH_FROUDE)
    inside = long_enough * full_enough * fast_enough
    # Nearly all Holtrop inside the cluster, nearly none outside. The small
    # outside value keeps a trace of the second method so the transition has no
    # cliff at the boundary.
    return CLUSTER_OUTSIDE_SHARE + CLUSTER_SPAN * inside
