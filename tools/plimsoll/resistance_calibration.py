"""Auditable per-ship-type calibration for the resistance power.

The factors below were fitted on the 146 public reference cases and scored with a
nested leave-one-out refit, so the quoted error is out-of-sample. They are kept
here as data with their own provenance rather than folded into the kernel: a
reader must be able to see the number, the sample it came from, and what it cost,
before trusting a calibrated power.

See docs/plimsoll-1.0/resistance-benchmark-2026-10-19.md for the full study.
"""

from __future__ import annotations

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
