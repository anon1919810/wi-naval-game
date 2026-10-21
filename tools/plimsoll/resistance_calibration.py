"""Auditable per-ship-type calibration for the resistance power.

The factors below were fitted on the 146 public reference cases and scored with a
nested leave-one-out refit, so the quoted error is out-of-sample. They are kept
here as data with their own provenance rather than folded into the kernel: a
reader must be able to see the number, the sample it came from, and what it cost,
before trusting a calibrated power.

See docs/plimsoll-1.0/resistance-benchmark-2026-10-19.md for the full study.
"""

from __future__ import annotations

try:
    from . import resistance_blend
except ImportError:  # imported as a top-level module by the test harness
    import resistance_blend

TAYLOR_ORIGINAL = "taylor_gertler_source_axis_strict"
BLENDED = "blended_taylor_holtrop_v1"

# Fitted 2026-10-19 on the 146-case public reference set. That set carries no case
# verified against a trial or model-test report, so these numbers are relative to
# the reference, not absolute accuracy. The nested leave-one-out score sits beside
# the in-sample one so the optimistic column is not quoted by accident.
CALIBRATION = {
    TAYLOR_ORIGINAL: {
        "sample": 146,
        "factors": {"battleship": 0.923, "carrier": 0.970, "cruiser": 1.020, "destroyer": 0.816},
        "in_sample_mape": 11.79,
        "loocv_mape": 12.11,
        "loocv_median": 10.55,
        "baseline_mape": 15.93,
    },
    BLENDED: {
        "sample": 146,
        "factors": {"battleship": 0.924, "carrier": 0.963, "cruiser": 1.056, "destroyer": 0.979},
        "in_sample_mape": 10.33,
        "loocv_mape": 10.62,
        "loocv_median": 8.24,
        "baseline_mape": 11.86,
    },
}


class CalibrationError(ValueError):
    """A calibration request that cannot be honoured without inventing a factor."""


def calibration_for(method):
    """The recorded calibration for one resistance method, or a named failure."""
    try:
        return CALIBRATION[method]
    except KeyError:
        raise CalibrationError("no recorded calibration for method %r" % (method,))


def factor_for(method, ship_type):
    """The multiplicative factor for one ship type, or a named failure.

    An unknown ship type is refused rather than silently treated as 1.0: a
    calibrated result must never be presented for a type the fit did not cover.
    """
    record = calibration_for(method)
    try:
        return record["factors"][ship_type]
    except KeyError:
        raise CalibrationError("ship type %r is outside the fitted set for %s" % (ship_type, method))


def scale_value(value, method, ship_type):
    """Scale any non-negative magnitude and return the audit record.

    Calibration is a pure multiplier, so the caller keeps its own unit. This is
    the entry point a stage uses; apply_calibration stays as the hp-named
    convenience for callers that already speak in horsepower.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalibrationError("value must be a number")
    if value < 0:
        raise CalibrationError("value must not be negative")
    record = calibration_for(method)
    factor = factor_for(method, ship_type)
    return dict(value=float(value) * factor, factor=factor, ship_type=ship_type, method=method,
                sample=record["sample"], loocv_mape=record["loocv_mape"],
                source="docs/plimsoll-1.0/resistance-benchmark-2026-10-19.md")


def apply_calibration(power_hp, method, ship_type):
    """Scale one power by the recorded factor and return the audit record."""
    if isinstance(power_hp, bool) or not isinstance(power_hp, (int, float)):
        raise CalibrationError("power_hp must be a number")
    if power_hp < 0:
        raise CalibrationError("power_hp must not be negative")
    record = calibration_for(method)
    factor = factor_for(method, ship_type)
    return dict(power_hp=float(power_hp) * factor, factor=factor, ship_type=ship_type,
                method=method, sample=record["sample"], loocv_mape=record["loocv_mape"],
                source="docs/plimsoll-1.0/resistance-benchmark-2026-10-19.md")


# Supersedes the per-type table above for the trial-measured data. On the 29
# provenance-checked trial cases a global factor makes the error worse
# (11.17 % against 11.08 %) and so does a factor outside the fast-large cluster
# (10.21 against 9.58), while inside it a single level correction takes the error
# from 15.03 % to 9.16 % out of sample. The cluster rule is shared with the blend
# so the two cannot drift apart.
CLUSTER_FACTOR = 0.851
CLUSTER_SAMPLE = 8
# Bootstrap 95 % interval on the mean trial error (2000 resamples, seed 20261021):
# the point estimate 0.851 sits inside it, and the width is why this is offered as
# a range in the product rather than as a fixed number.
CLUSTER_FACTOR_CI = (0.792, 0.921)
CLUSTER_LOOCV_MAE = 9.16
CLUSTER_UNCORRECTED_MAE = 15.03
CLUSTER_SOURCE = "docs/plimsoll-1.0/resistance-methods-and-data-2026-10-21.md section 19"


def cluster_factor(block_coeff, length_m, froude):
    """Level correction for the fast-large cluster, faded in by the shared rule.

    The correction is a level bias, not a shape error: inside the cluster a single
    constant beats switching to Holtrop (7.01 % against 9.61 % on the
    battlecruisers). Applying it through the same smooth share as the blend keeps
    it continuous and keeps the one without a factor untouched.
    """
    share = resistance_blend.holtrop_share_cluster(block_coeff, length_m, froude)
    # Normalise the share to [0, 1] first: without that the fade would stop short
    # of the measured factor even for a hull sitting deep inside the cluster.
    span = resistance_blend.CLUSTER_SPAN
    outside = resistance_blend.CLUSTER_OUTSIDE_SHARE
    weight = max(0.0, min(1.0, (share - outside) / span))
    factor = 1.0 + weight * (CLUSTER_FACTOR - 1.0)
    return dict(factor=factor, factor_ci=CLUSTER_FACTOR_CI, cluster_share=share, cluster_weight=weight, applied=weight > 0.5,
                sample=CLUSTER_SAMPLE, loocv_mae=CLUSTER_LOOCV_MAE,
                uncorrected_mae=CLUSTER_UNCORRECTED_MAE, source=CLUSTER_SOURCE)


# Fitted on the 27 cases that carry both a rated and a measured figure. In design
# mode the error is a pure level shift: the model sits 8-50 % above the rated
# value on every ship, so one factor takes the error from 23.04 % to 10.56 %
# (nested leave-one-out). This is the opposite of trial mode, where a global
# factor is harmful because the errors change sign with hull form.
DESIGN_FACTOR = 0.8079
DESIGN_SAMPLE = 27
DESIGN_FACTOR_CI = (0.790, 0.872)
DESIGN_LOOCV_MAPE = 10.56
DESIGN_UNCORRECTED_MAPE = 23.04
DESIGN_SOURCE = "docs/plimsoll-1.0/resistance-methods-and-data-2026-10-21.md section 23"


def design_factor():
    """The single level correction for a rated-value target."""
    return dict(factor=DESIGN_FACTOR, factor_ci=DESIGN_FACTOR_CI, sample=DESIGN_SAMPLE, loocv_mape=DESIGN_LOOCV_MAPE,
                uncorrected_mape=DESIGN_UNCORRECTED_MAPE, source=DESIGN_SOURCE)