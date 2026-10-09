"""Explicit unit conversions used by the Plimsoll public data contract."""

from __future__ import annotations

import math


_UNITS = {
    "t": ("mass", 1.0),
    "kg": ("mass", 0.001),
    "long_ton": ("mass", 1.0160469088),
    "m": ("length", 1.0),
    "ft": ("length", 0.3048),
    "kn": ("speed", 1.0),
    "m_s": ("speed", 3600.0 / 1852.0),
    "kW": ("power", 1.0),
    "shp": ("power", 0.7456998715822702),
    "deg": ("angle", 1.0),
    "rad": ("angle", 180.0 / math.pi),
}


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a finite real value between units of the same dimension.

    Args:
        value (float): Finite numeric value to convert.
        from_unit (str): Unit token describing the input value.
        to_unit (str): Unit token describing the returned value.

    Returns:
        (float): Value expressed in ``to_unit``.

    Raises:
        ValueError: If the value or either unit is invalid, or dimensions differ.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"value must be a finite real number, received {value!r}")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError("value is outside the supported numeric range") from exc
    if not math.isfinite(value):
        raise ValueError("value must be a finite real number")
    if from_unit not in _UNITS:
        raise ValueError(f"unsupported source unit: {from_unit!r}")
    if to_unit not in _UNITS:
        raise ValueError(f"unsupported target unit: {to_unit!r}")
    from_dimension, from_factor = _UNITS[from_unit]
    to_dimension, to_factor = _UNITS[to_unit]
    if from_dimension != to_dimension:
        raise ValueError(
            f"cannot convert {from_unit!r} ({from_dimension}) to {to_unit!r} ({to_dimension})"
        )
    result = value * (from_factor / to_factor)
    if not math.isfinite(result):
        raise ValueError("converted value is outside the supported numeric range")
    return result
