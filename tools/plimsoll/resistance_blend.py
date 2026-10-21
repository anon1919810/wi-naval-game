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


def blend_resistance(taylor_kn, holtrop_kn, block_coeff) -> dict:
    """Blend one speed total resistance and say how it was blended.

    A side that could not be computed is named rather than silently replaced:
    the surviving side is reported with its own weight and blended=False, so a
    caller cannot mistake it for agreement between two models.
    """
    share = holtrop_share(block_coeff)
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
