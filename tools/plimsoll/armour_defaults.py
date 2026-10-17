"""Recovered default armour dimensions for the four belt and bulkhead regions.

This is a pure function over a finite declared domain. It never touches a project,
a ledger or a file, it never clamps an out-of-domain value, and it never reads an
unknown input as zero: a missing declared fact produces a structured unavailable
diagnostic and a null dimension, while a wrong type, a wrong sign and an
out-of-domain number are reported structurally and are never silently guessed.

It is deliberately **not** part of the adapted configuration method. The concept
configuration keeps ``sps-3b3-adapted-v1``; this kernel carries its own
``sps-3b3-armour-defaults-v1``, so a reader can always tell which numbers came
from which method. It writes no mass, creates no record and adopts no weight: the
copy into a fixed-armour record is an ordinary front-end draft edit.

Numerical source
----------------
Recovered ``SpringSharpMono`` 3.0.3032.29945, the same original binary the adapted
concept kernels use (identical assembly string and SHA256, re-exported through
:mod:`concept_estimates` so the two can never drift apart):

* ``ArmourControl.cs:422-445`` ``beltButtonClick`` — five Est fields written into
  eight default-dimension textboxes
* ``HullControl.cs:1210-1248`` ``draughtCalc`` — ``draughtSide`` is assigned at
  ``:1246`` and the ``beltButtonClick`` main height reads it
* ``MainForm.FEET2METRES`` — the single ``0.3048`` the source multiplies an Est
  field by before formatting it at source scale 1

Recovered expressions, evaluated in feet and converted once to metres
--------------------------------------------------------------------
* ``side_draught_ft = ((1.006 - 0.0056 * Cb ** -3.56) * 2 - 1) * T_ft`` — this is
  the original numeric dependency, *not* the normal draught;
* ``main_length_ft = (1 - fc - qd) * L_ft``;
* ``ends_length_ft = L_ft - main_length_ft - 0.02`` — the fixed 0.02 ft end
  allowance is preserved;
* ``main_height_ft = min(1.2 * sqrt(B_ft), side_draught_ft + F_ft)``;
* ``ends_height_ft = main_height_ft``;
* ``upper_length_ft = bulkhead_length_ft = main_length_ft``;
* ``upper_height_ft = min(8 ft, F_ft)`` — the 8 ft cap is preserved;
* ``bulkhead_height_ft = side_draught_ft``.

The canonical recommendation is the **unrounded** value in metres. The source's
``ToString("n2")`` textbox rounding is deliberately outside this method and is not
reproduced.

Scope
-----
This is a recommendation of eight declared *sizes*. It is not a mass model, not a
mass adoption, not a protection rating, not developed armour geometry, not a form,
not whole-program parity and not validated against any real ship.
"""

from __future__ import annotations

import math
import json

try:
    from . import concept_estimates as source
except ImportError:                                   # pragma: no cover - direct import
    import concept_estimates as source

METHOD_VERSION = "sps-3b3-armour-defaults-v1"
ID = "armour_defaults"
SOURCE_LOCATION = ("ArmourControl.cs:422-445 beltButtonClick; HullControl.cs:1210-1248 "
                   "draughtCalc (draughtSide at 1246); MainForm.FEET2METRES")
SOURCE_ASSEMBLY = source.SOURCE_ASSEMBLY
SOURCE_SHA256 = source.SOURCE_SHA256
SOURCE_SCOPE = (
    "Independent empirical recommendation of the eight recovered belt and bulkhead default "
    "dimensions for one declared armour-default declaration, evaluated in the source's own "
    "feet with the recovered draughtCalc side draught and converted once to metres. It "
    "reproduces no mass, adopts no weight, creates no record and is not a form, not a "
    "protection rating, not developed armour geometry, not whole-program parity and not "
    "validated against any real ship. The source n2 textbox rounding is deliberately not "
    "reproduced."
)

DEFAULT_PATH = "$.concept_design.armour_defaults"

# The three declared fields of the optional section.
CONFIG_KEYS = ("source", "forecastle_fraction", "quarterdeck_fraction")
# The five canonical facts the recovered expression reads, and no others. The stern,
# the screw count, the deck profile and the loading are deliberately absent.
CONTEXT_KEYS = ("length_m", "beam_m", "draught_m", "block_coeff", "freeboard_m")

# The eight dimensions the recovered expression returns, in the recovered order.
VALUE_KEYS = ("main_length_m", "main_height_m", "ends_length_m", "ends_height_m",
              "upper_length_m", "upper_height_m", "bulkhead_length_m", "bulkhead_height_m")
LENGTH_KEYS = ("main_length_m", "ends_length_m", "upper_length_m", "bulkhead_length_m")
HEIGHT_KEYS = ("main_height_m", "ends_height_m", "upper_height_m", "bulkhead_height_m")

# The source evaluates in feet; ``0.3048`` is the original's single FEET2METRES.
M_PER_FT = source.M_PER_FT
END_ALLOWANCE_FT = 0.02
UPPER_HEIGHT_CAP_FT = 8.0
MAIN_HEIGHT_FACTOR = 1.2
SIDE_FACTOR_OFFSET = 1.006
SIDE_FACTOR_COEFF = 0.0056
SIDE_FACTOR_EXPONENT = -3.56

# The existing fixed-armour editor's own declared domain, per metric dimension. A
# recommendation outside it is not copied; it is a reason to withhold, not a number
# to save and let the editor refuse afterwards.
LENGTH_DOMAIN = (0.0, 5000.0)
HEIGHT_DOMAIN = (0.0, 100.0)

ASSUMPTIONS = (
    "the recovered expression is evaluated in feet and converted to metres with the single "
    "0.3048 m/ft the original FEET2METRES uses; the two-decimal textbox rounding is not "
    "reproduced, so the canonical recommendation is the unrounded metre value",
    "the side draught is the recovered HullControl.cs:1246 expression "
    "((1.006 - 0.0056 * Cb ** -3.56) * 2 - 1) * T and deliberately not the normal draught; a "
    "non-positive or unknown block coefficient leaves every dependent height unknown",
    "the main height is min(1.2 * sqrt(beam_ft), side_draught_ft + freeboard_ft) and the upper "
    "height is min(8 ft, freeboard_ft); the 8 ft cap is preserved",
    "the end length keeps the original fixed 0.02 ft end allowance: ends = length - main - 0.02",
    "a negative, non-finite or out-of-domain result withholds only that one field; a known length "
    "is never invalidated by an unknown height and nothing is clamped to zero",
    "the five default dimensions depend only on length, beam, draught, block coefficient and "
    "freeboard; the stern, the screw count, the deck profile and the loading are never read",
)

# Fields no default may ever fill, so no length or height is ever suggested for them: a
# deck, a conning tower and a bulge carry no recovered default dimension.
DEFAULT_KINDS = ("belt_main", "belt_ends", "belt_upper", "bulkhead")


class ArmourDefaultsError(ValueError):
    """Report a rejected armour-default declaration with structured diagnostics."""

    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__("; ".join(d["message"] for d in diagnostics if d.get("blocking")))


def _diag(code, message, path, field=None, blocking=False):
    return {"code": code, "severity": "error" if blocking else "warning", "field": field,
            "path": path, "message": message, "blocking": blocking}


def _fraction(raw, field, path, diagnostics):
    """One declared fraction: null, or a finite number in [0, 1]; anything else is refused."""
    value = raw.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        diagnostics.append(_diag("armour_defaults.invalid",
                                 "%s must be a finite number in [0, 1] or null" % (field,),
                                 path + "." + field, field, True))
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        number = float("inf")
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        diagnostics.append(_diag("armour_defaults.invalid",
                                 "%s must be a finite number in [0, 1] or null" % (field,),
                                 path + "." + field, field, True))
        return None
    return number


def validate_config(raw, path=DEFAULT_PATH):
    """Normalize the optional armour-default declaration, or ``None`` when absent.

    ``source`` is nullable text. ``forecastle_fraction`` and ``quarterdeck_fraction``
    are ``null`` or finite numbers in ``[0, 1]``, and when both are known their sum
    must be at most ``1``: a declaration whose fractions cannot both bound the hull
    is a structural contradiction and is refused, never silently trimmed.

    Raises :class:`ArmourDefaultsError` with structured diagnostics on a wrong type,
    a non-finite number, an out-of-range fraction, an unsupported field or a known
    fraction sum above ``1``.
    """
    if raw is None:
        return None
    diagnostics = []
    if not isinstance(raw, dict):
        diagnostics.append(_diag("armour_defaults.invalid", "must be an object or null",
                                 path, blocking=True))
        raise ArmourDefaultsError(diagnostics)
    for key in sorted(set(raw) - set(CONFIG_KEYS)):
        diagnostics.append(_diag("armour_defaults.invalid",
                                 "unsupported field %r" % (key,), path + "." + key, key, True))
    note = raw.get("source")
    if note is not None and (not isinstance(note, str) or not note.strip()):
        diagnostics.append(_diag("armour_defaults.invalid",
                                 "source must be non-empty text or null", path + ".source",
                                 "source", True))
        note = None
    forecastle = _fraction(raw, "forecastle_fraction", path, diagnostics)
    quarterdeck = _fraction(raw, "quarterdeck_fraction", path, diagnostics)
    if forecastle is not None and quarterdeck is not None and forecastle + quarterdeck > 1.0:
        diagnostics.append(_diag(
            "armour_defaults.domain",
            "the forecastle and quarterdeck fractions must sum to at most 1; %r + %r is %r"
            % (forecastle, quarterdeck, forecastle + quarterdeck),
            path + ".forecastle_fraction", "forecastle_fraction", True))
    if diagnostics:
        raise ArmourDefaultsError(diagnostics)
    return {"source": note, "forecastle_fraction": forecastle,
            "quarterdeck_fraction": quarterdeck}


def _fraction_read(config, field):
    """A validated fraction read defensively, so a raw dict never raises."""
    value = config.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and 0.0 <= number <= 1.0 else None


def _context_fact(context, key, path, diagnostics):
    """One declared context fact and its own recorded origin, if any.

    A fact may be a plain finite number, or the ``{"value", "source", "estimate"}``
    shape a declared-fact helper produces. A wrong type or a non-finite number is a
    structural diagnostic and leaves that fact unknown; a negative number is kept,
    so the recovered expression's own negative result is reported per field rather
    than pre-empted here.
    """
    if not isinstance(context, dict):
        return None, None
    declared = context.get(key)
    origin = None
    if isinstance(declared, dict):
        origin = declared.get("source")
        try:
            origin = json.loads(json.dumps(origin, allow_nan=False))
        except (TypeError, ValueError, OverflowError, RecursionError):
            origin = None
            diagnostics.append(_diag("armour_defaults.invalid_origin",
                "the optional fact origin is not finite JSON and was withheld", path + "." + key, key))
        declared = declared.get("value")
    if declared is None:
        return None, origin
    if isinstance(declared, bool) or not isinstance(declared, (int, float)):
        diagnostics.append(_diag(
            "armour_defaults.invalid",
            "the declared %s is not a finite number, so every default dimension that needs it "
            "is unknown" % (key,), path + "." + key, key))
        return None, origin
    try:
        number = float(declared)
    except (OverflowError, ValueError):
        number = float("inf")
    if not math.isfinite(number):
        diagnostics.append(_diag(
            "armour_defaults.range",
            "the declared %s exceeds the finite numeric range, so every default dimension that "
            "needs it is unknown" % (key,), path + "." + key, key))
        return None, origin
    if number < 0.0:
        diagnostics.append(_diag(
            "armour_defaults.domain",
            "the declared %s is negative (%r); the recovered expression reproduces the source's "
            "own negative result rather than assuming a positive fact" % (key, number),
            path + "." + key, key))
    return number, origin


def _feet(value, key, path, diagnostics):
    if value is None:
        return None
    result = value / M_PER_FT
    if not math.isfinite(result):
        diagnostics.append(_diag("armour_defaults.range",
            "the declared %s exceeds the finite feet-conversion range" % key, path + "." + key, key))
        return None
    return result


def _side_draught_ft(block, draught_ft):
    """The recovered ``draughtCalc`` side draught, or ``(None, reason)``.

    A non-positive or unknown block coefficient cannot raise to a fractional power,
    and a very small positive one can overflow; both leave the side draught unknown
    with its own reason instead of a non-finite number.
    """
    if block is None:
        return None, ("the recovered side draught needs the declared block coefficient; it is "
                      "unknown")
    if not block > 0.0:
        return None, ("the recovered side draught needs a positive declared block coefficient; "
                      "%r is not positive" % (block,))
    if draught_ft is None:
        return None, "the recovered side draught needs the declared draught; it is unknown"
    try:
        side = ((SIDE_FACTOR_OFFSET - SIDE_FACTOR_COEFF * block ** SIDE_FACTOR_EXPONENT) * 2.0
                - 1.0) * draught_ft
    except (ArithmeticError, OverflowError, ValueError, ZeroDivisionError):
        return None, "the recovered side draught overflows the finite numeric range"
    if not math.isfinite(side):
        return None, "the recovered side draught overflows the finite numeric range"
    return side, None


def evaluate(config, context, path=DEFAULT_PATH):
    """The eight recovered default dimensions, each with its own availability.

    ``config`` is the declaration :func:`validate_config` returns. ``context`` is the
    canonical hull geometry plus the declared freeboard, with exactly the keys
    ``length_m, beam_m, draught_m, block_coeff, freeboard_m``; a value may be a plain
    number or a declared-fact mapping. The stern, the screw count, the deck profile
    and the loading are never read.

    Returns a JSON-serialisable dict with ``id``, ``method_version``, ``status``,
    ``values``, ``availability``, ``diagnostics`` and ``provenance``. ``values``
    carries the eight dimensions in metres; a dimension the expression cannot derive,
    or one outside the existing fixed-field domain, is ``None`` with an
    ``availability`` entry naming its own reason. ``status`` is ``available`` when all
    eight are, ``unavailable`` when none is, and ``partial`` otherwise.
    """
    diagnostics = []
    config = validate_config(config, path) or {}
    declared_source = config.get("source")
    forecastle = _fraction_read(config, "forecastle_fraction")
    quarterdeck = _fraction_read(config, "quarterdeck_fraction")
    facts = {}
    origins = {}
    for key in CONTEXT_KEYS:
        facts[key], origins[key] = _context_fact(context, key, path, diagnostics)
    length_m, beam_m, draught_m = facts["length_m"], facts["beam_m"], facts["draught_m"]
    block, freeboard = facts["block_coeff"], facts["freeboard_m"]
    length_ft, beam_ft, draught_ft, freeboard_ft = (
        _feet(facts[key], key, path, diagnostics)
        for key in ("length_m", "beam_m", "draught_m", "freeboard_m"))

    # --- the lengths ------------------------------------------------------------
    length_reason = None
    main_ft = None
    if length_ft is None or forecastle is None or quarterdeck is None:
        missing = []
        if length_ft is None:
            missing.append("length_m")
        if forecastle is None:
            missing.append("forecastle_fraction")
        if quarterdeck is None:
            missing.append("quarterdeck_fraction")
        length_reason = ("the recovered lengths need the declared %s; at least one is unknown"
                         % (", ".join(missing),))
    else:
        main_ft = (1.0 - forecastle - quarterdeck) * length_ft
    end_ft = None
    if main_ft is not None:
        end_ft = length_ft - main_ft - END_ALLOWANCE_FT

    # --- the side draught and the three heights ---------------------------------
    side_ft, side_reason = _side_draught_ft(block, draught_ft)
    main_h_ft = None
    main_h_reason = None
    if side_ft is None:
        main_h_reason = side_reason
    elif beam_ft is None or freeboard_ft is None:
        missing = []
        if beam_ft is None:
            missing.append("beam_m")
        if freeboard_ft is None:
            missing.append("freeboard_m")
        main_h_reason = ("the recovered main height needs the declared %s; at least one is unknown"
                         % (", ".join(missing),))
    elif beam_ft < 0.0:
        main_h_reason = "the recovered 1.2*sqrt(beam) arm needs a non-negative declared beam"
    else:
        candidate = MAIN_HEIGHT_FACTOR * math.sqrt(beam_ft)
        arm = side_ft + freeboard_ft
        main_h_ft = min(candidate, arm)
        if not math.isfinite(main_h_ft):
            main_h_ft = None
            main_h_reason = "the recovered main height overflows the finite numeric range"

    upper_ft = None
    upper_reason = None
    if freeboard_ft is None:
        upper_reason = "the recovered upper height needs the declared freeboard; it is unknown"
    else:
        upper_ft = min(UPPER_HEIGHT_CAP_FT, freeboard_ft)
        if not math.isfinite(upper_ft):
            upper_ft = None
            upper_reason = "the recovered upper height overflows the finite numeric range"

    # Each dimension shares its group's reason when the recovered expression could not
    # produce a value at all.
    groups = {
        "length": (main_ft, length_reason),
        "main_height": (main_h_ft, main_h_reason),
        "upper_height": (upper_ft, upper_reason),
        "bulkhead_height": (side_ft, side_reason),
    }
    plan = {
        "main_length_m": ("length", main_ft),
        "main_height_m": ("main_height", main_h_ft),
        "ends_length_m": ("length", end_ft),
        "ends_height_m": ("main_height", main_h_ft),
        "upper_length_m": ("length", main_ft),
        "upper_height_m": ("upper_height", upper_ft),
        "bulkhead_length_m": ("length", main_ft),
        "bulkhead_height_m": ("bulkhead_height", side_ft),
    }

    values = {}
    availability = {}
    for key in VALUE_KEYS:
        group, feet = plan[key]
        if feet is None:
            values[key] = None
            availability[key] = {"state": "unavailable",
                                 "reason": groups[group][1] or
                                 "the recovered %s is unavailable" % (key,)}
            continue
        metres = feet * M_PER_FT
        low, high = LENGTH_DOMAIN if key in LENGTH_KEYS else HEIGHT_DOMAIN
        if not math.isfinite(metres):
            reason = "the recovered %s is not a finite number" % (key,)
            values[key] = None
            availability[key] = {"state": "unavailable", "reason": reason}
            diagnostics.append(_diag("armour_defaults.range", reason, path, key))
        elif metres < low:
            reason = ("the recovered %s is negative (%.6f m); a negative dimension is reported "
                      "unavailable and is never clamped to zero" % (key, metres))
            values[key] = None
            availability[key] = {"state": "unavailable", "reason": reason}
            diagnostics.append(_diag("armour_defaults.domain", reason, path, key))
        elif metres > high:
            reason = ("the recovered %s is %.4f m, above the existing fixed-field domain "
                      "0..%g m; it is reported unavailable and is never clamped" % (key, metres, high))
            values[key] = None
            availability[key] = {"state": "unavailable", "reason": reason}
            diagnostics.append(_diag("armour_defaults.domain", reason, path, key))
        else:
            values[key] = metres
            availability[key] = {"state": "available", "reason": None}

    known = [key for key in VALUE_KEYS if availability[key]["state"] == "available"]
    if len(known) == len(VALUE_KEYS):
        status = "available"
    elif known:
        status = "partial"
    else:
        status = "unavailable"

    provenance = {
        "method_version": METHOD_VERSION,
        "method": METHOD_VERSION,
        "kernel": "armour_defaults_recovered_dimensions_m",
        "source_assembly": SOURCE_ASSEMBLY,
        "source_sha256": SOURCE_SHA256,
        "source_location": SOURCE_LOCATION,
        "source_scope": SOURCE_SCOPE,
        "declared_source": declared_source,
        "formula": (
            "side_draught_ft = ((1.006 - 0.0056 * Cb ** -3.56) * 2 - 1) * T_ft; "
            "main_length_ft = (1 - fc - qd) * L_ft; ends_length_ft = L_ft - main_length_ft - "
            "0.02; main_height_ft = min(1.2 * sqrt(B_ft), side_draught_ft + F_ft); "
            "ends_height_ft = main_height_ft; upper_length_ft = bulkhead_length_ft = "
            "main_length_ft; upper_height_ft = min(8, F_ft); bulkhead_height_ft = "
            "side_draught_ft; then each dimension is multiplied once by 0.3048 m/ft"),
        "units": ("the recovered expression is evaluated in feet and converted once to metres "
                  "with the original FEET2METRES 0.3048; the source n2 textbox rounding is not "
                  "reproduced"),
        "assumptions": " ".join(ASSUMPTIONS),
        "default_kinds": list(DEFAULT_KINDS),
        "inputs": {
            "forecastle_fraction": forecastle,
            "quarterdeck_fraction": quarterdeck,
            "length_m": length_m,
            "beam_m": beam_m,
            "draught_m": draught_m,
            "block_coeff": block,
            "freeboard_m": freeboard,
            "length_ft": length_ft,
            "beam_ft": beam_ft,
            "draught_ft": draught_ft,
            "freeboard_ft": freeboard_ft,
            "side_draught_ft": side_ft,
            "end_allowance_ft": END_ALLOWANCE_FT,
            "upper_height_cap_ft": UPPER_HEIGHT_CAP_FT,
            "domain": {"length_m": list(LENGTH_DOMAIN), "height_m": list(HEIGHT_DOMAIN)},
            "context_origins": {key: origins[key] for key in CONTEXT_KEYS},
        },
    }
    return {"id": ID, "method_version": METHOD_VERSION, "status": status,
            "values": values, "availability": availability,
            "diagnostics": diagnostics, "provenance": provenance}
