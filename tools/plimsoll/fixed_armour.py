"""Fixed (non-rotating) armour mass estimates from the recovered ArmourControl page.

This is a pure function over a finite declared domain. It never touches a
project, a ledger or a file, it never clamps an out-of-domain value, and it never
reads an unknown input as zero: a missing declared fact produces a structured
unavailable diagnostic and a null reading, while a wrong type, a wrong sign, an
out-of-domain number and a fractional selector are refused outright.

It is deliberately **not** part of the adapted configuration method. The
configuration keeps ``sps-3b3-adapted-v1``; this kernel carries its own
``sps-3b3-fixed-armour-v1``, so a reader can always tell which numbers came from
which method.

Numerical source
----------------
Recovered ``SpringSharpMono`` 3.0.3032.29945, the same original binary the
adapted concept kernels, :mod:`battery_armour` and :mod:`battery_layout` use
(identical assembly string and SHA256, re-exported from :mod:`concept_estimates`
so the two can never drift apart):

* ``ArmourControl.cs:602-608`` ``weightBeltMainCalc``
* ``ArmourControl.cs:610-618`` ``weightBeltEndsCalc``
* ``ArmourControl.cs:620-626`` ``weightBeltUpperCalc``
* ``ArmourControl.cs:654-669`` ``weightBulkheadCalc``
* ``ArmourControl.cs:671-686`` ``weightBulgeCalc``
* ``ArmourControl.cs:694-725`` ``weightDeckCalc`` and its seven coverage selectors
* ``ArmourControl.cs:727-735`` ``weightConningCalc``

Units
-----
Every project declaration stays canonical: metres, millimetres and metric
tonnes. The recovered expressions themselves are written in **feet**, **inches**
and **long tons**, and the ``INCH = 0.0185`` empirical mass constant
(``MainForm.cs:22``) is the original's own. Each conversion happens exactly once
and exactly where the original changes unit; nothing is converted twice and
nothing is rounded to a display precision.

Scope
-----
The recovered original keeps **seven** fixed armour regions: main, upper and end
belts, a torpedo bulkhead, a bulge, an armour deck and the conning towers. This
kernel reads that structure instead of merging it: each region keeps its own
recovered identity, its own selector where the source has one, and its own
declared extent. Deck selectors 0-3 are four genuinely different readings of the
recovered seven-way switch, and selectors 4-6 are the recovered machinery-box
and magazine-box areas.

It is **not** a form, a centre of gravity, an inclined plate, a protection
rating, a developed armour area, a real ship's armour or a whole-program event
chain, and it makes no claim about any real ship.

Recovered quirks kept verbatim
------------------------------
* The source's belt **inclination** only feeds the ``weightBeltsCalc`` warning
  ``maxBeltHeight``; no angle multiplier is applied to the belt mass here. The
  original adds no inclination factor to ``weightBeltMain``/``weightBeltUpper``
  and neither does this kernel.
* The belt expression keeps its taper term
  ``((hull.length - belt.length) / hull.length) ** (1 - coWaterPlane) * beam``.
  It is the original's own mixed-unit term: the inner ratio is dimensionless and
  multiplies a **beam in feet**, and the whole thing is added to a length in feet.
* ``weightDeckCalc`` never merges the coverage choices. The seven-way switch
  replaces only the **central** area: selectors 0-3 read the recovered waterplane
  area less the forecastle and quarter-deck areas, multiplied by the recovered
  ``1.01`` margin, and selectors 4-6 read the recovered
  ``(... + 16) * (beam + 16) - 256`` box expression. The recovered method then
  adds the forecastle and quarter-deck plate terms **after** the switch, for
  every selector including the three box ones, so a box deck is the box *plus*
  its two upper plates. A **known zero** selected component keeps that box margin
  instead of collapsing the box away, and an **unknown** one leaves the box area
  unknown; they are never the same.
* ``weightConningCalc`` returns one combined fore-plus-aft mass. This kernel also
  reports the two contributions so a reader can see the split, but the proposed
  mass is the combined figure counted exactly once.
* The original's ``float`` intermediates are ``float64`` here. The source's
  ``float32`` rounding is the stated tolerance of this kernel, exactly as it is
  for :mod:`concept_estimates`.

Determinism the original does not have
--------------------------------------
The source is a form: every field carries a value whether or not the reader meant
it. Here ``None`` means *unknown*, ``0`` means a declared zero, and a record may
stay an unfinished draft. An unknown input is never clamped, filled in or read
as zero, and a derived negative, non-finite or geometrically impossible mass is
reported as unavailable instead of being proposed.
"""

from __future__ import annotations

import copy
import json
import math
import re

try:
    from . import battery_armour as siblings
    from . import concept_estimates as kernels
except ImportError:                                   # pragma: no cover - direct import
    import battery_armour as siblings
    import concept_estimates as kernels

METHOD_VERSION = "sps-3b3-fixed-armour-v1"
SOURCE_LOCATION = ("ArmourControl.cs:602-626, 654-685, 694-725, 727-735")
SOURCE_ASSEMBLY = siblings.SOURCE_ASSEMBLY
SOURCE_SHA256 = siblings.SOURCE_SHA256
SOURCE_SCOPE = (
    "Independent empirical estimate of the recovered fixed armour masses of one "
    "declared region: a main, upper or end belt, a torpedo bulkhead, a bulge, an "
    "armour deck under one of the recovered seven coverage selectors, or the "
    "combined fore-plus-aft conning tower; reproduced from the recovered 3b3 "
    "weightBeltMainCalc, weightBeltEndsCalc, weightBeltUpperCalc, "
    "weightBulkheadCalc, weightBulgeCalc, weightDeckCalc and weightConningCalc "
    "expressions with the original's own feet, inches and long tons and its own "
    "INCH = 0.0185 mass constant. It is not a form, not a centre of gravity, not "
    "an inclined plate, not a protection rating, not developed armour geometry, "
    "not structural strength, not whole-program parity and not validated against "
    "any real ship."
)

# MainForm.cs:22 and concept_estimates.M_PER_INCH, re-exported so the empirical
# constant and the two unit conversions have exactly one definition.
EMPIRICAL_MASS_CONSTANT = siblings.EMPIRICAL_MASS_CONSTANT
MM_PER_INCH = siblings.MM_PER_INCH
M_PER_FT = kernels.M_PER_FT
LONG_TON_KG = kernels.LONG_TON_KG

# The recovered seven-way deck coverage switch (ArmourControl.cs:861), kept so a
# form can offer the original's own selectors instead of a number. They are
# labels, never parsed.
DECK_SELECTOR_NAMES = (
    "Armoured deck - multiple decks", "Armoured deck - single deck",
    "Protected deck - multiple decks", "Protected deck - single deck",
    "Box over machinery", "Box over magazines", "Box over machinery & magazines",
)
DECK_SELECTOR_COUNT = len(DECK_SELECTOR_NAMES)
# Selectors 0-3 read the waterplane-area branch; 4-6 read the recovered box area.
DECK_AREA_SELECTORS = (0, 1, 2, 3)
DECK_MACHINERY_SELECTOR = 4
DECK_AMMUNITION_SELECTOR = 5
DECK_COMBINED_SELECTOR = 6
# ArmourControl.cs:702 the recovered 1.01 margin on the remaining central area.
DECK_CENTRAL_MARGIN = 1.01

# The recovered box expression's own margin (ArmourControl.cs:705-711).
DECK_BOX_CONSTANT = 16.0
DECK_BOX_AREA_OFFSET = 256.0
DECK_BOX_MACHINERY_MULTIPLIER = 3.0
DECK_BOX_AMMUNITION_DISPLACEMENT_FACTOR = 0.94
DECK_BOX_LENGTH_COEFFICIENT = 0.65
# ArmourControl.cs:729 the recovered conning tower expression.
CONNING_COEFFICIENT = 10.0
CONNING_DISPLACEMENT_REFERENCE = 10000.0
CONNING_DISPLACEMENT_EXPONENT = 2.0 / 3.0

KINDS = ("belt_main", "belt_upper", "belt_ends", "bulkhead", "bulge", "deck", "conning")
# The one canonical balance role each kind's own target must carry. A conning
# tower is fixed structure, not rotating armour, and a bulge is a separate
# compartment rather than a belt; neither is ever merged into another role.
ROLE_BY_KIND = {
    "belt_main": "belt_main", "belt_upper": "belt_upper", "belt_ends": "belt_ends",
    "bulkhead": "bulkhead", "bulge": "armour_bulge", "deck": "armour_deck",
    "conning": "conning",
}
# Kinds whose recovered expression multiplies a declared zero thickness into
# every term, so a declared zero is a determined zero and not a missing number.
PLATE_KINDS = ("belt_main", "belt_upper", "belt_ends", "bulkhead", "bulge")
BELT_KINDS = ("belt_main", "belt_upper")
# The recovered end belt, the torpedo bulkhead and the bulge are each counted
# twice: once for each end, each transverse or each side of the ship.
DOUBLED_PLATE_KINDS = ("belt_ends", "bulkhead", "bulge")

COMMON_FIELDS = ("id", "kind", "system_id", "item_id", "source")
PLATE_FIELDS = ("thickness_mm", "length_m", "height_m")
DECK_FIELDS = ("thickness_mm", "coverage_index", "forecastle_fraction",
               "quarterdeck_fraction", "forecastle_mm", "quarterdeck_mm")
CONNING_FIELDS = ("thickness_mm", "aft_mm")
FIELDS_BY_KIND = {
    "belt_main": PLATE_FIELDS, "belt_upper": PLATE_FIELDS, "belt_ends": PLATE_FIELDS,
    "bulkhead": PLATE_FIELDS, "bulge": PLATE_FIELDS, "deck": DECK_FIELDS,
    "conning": CONNING_FIELDS,
}
ALL_FIELDS = ("thickness_mm", "length_m", "height_m", "coverage_index",
              "forecastle_fraction", "quarterdeck_fraction", "forecastle_mm",
              "quarterdeck_mm", "aft_mm")

MAX_RECORDS = 50
MAX_THICKNESS_MM = 2000.0
MAX_EXTENT_M = 5000.0
MAX_HEIGHT_M = 100.0
ID_PATTERN = re.compile(r"\A[A-Za-z0-9_.-]{1,80}\Z")

CONTEXT_FIELDS = ("length_m", "beam_m", "co_waterplane", "waterplane_area_m2",
                  "displacement_t", "machinery_mass_t", "ammunition_mass_t")

KERNEL_BY_KIND = {
    "belt_main": "fixed_armour_belt_main_long_tons",
    "belt_upper": "fixed_armour_belt_upper_long_tons",
    "belt_ends": "fixed_armour_belt_ends_long_tons",
    "bulkhead": "fixed_armour_bulkhead_long_tons",
    "bulge": "fixed_armour_bulge_long_tons",
    "deck": "fixed_armour_deck_long_tons",
    "conning": "fixed_armour_conning_long_tons",
}
FORMULA_BY_KIND = {
    "belt_main": (
        "ArmourControl.cs:602-608 weightBeltMainCalc: "
        "w_lt = (length_ft + ((hull_length_ft - length_ft) / hull_length_ft) ** "
        "(1 - co_waterplane) * hull_beam_ft) * height_ft * thickness_in * 0.0185 * 2"),
    "belt_upper": (
        "ArmourControl.cs:620-626 weightBeltUpperCalc: "
        "w_lt = (length_ft + ((hull_length_ft - length_ft) / hull_length_ft) ** "
        "(1 - co_waterplane) * hull_beam_ft) * height_ft * thickness_in * 0.0185 * 2"),
    "belt_ends": (
        "ArmourControl.cs:610-618 weightBeltEndsCalc: "
        "w_lt = 2 * length_ft * height_ft * thickness_in * 0.0185"),
    "bulkhead": (
        "ArmourControl.cs:654-669 weightBulkheadCalc: "
        "w_lt = 2 * length_ft * height_ft * thickness_in * 0.0185"),
    "bulge": (
        "ArmourControl.cs:671-686 weightBulgeCalc: "
        "w_lt = 2 * length_ft * height_ft * thickness_in * 0.0185"),
    "deck": (
        "ArmourControl.cs:694-725 weightDeckCalc: fore_area_sqft = (2a) ** (1 - C**2) * B * L "
        "* a / 2 and quarter_area_sqft = q ** (1 - C) * B * L * q / 4 + (q ** (1 - C) + "
        "(2q) ** (1 - C)) * B * L * q / 4 with a the declared forecastle fraction and q the "
        "declared quarter-deck fraction; selectors 0-3 central_area_sqft = "
        "(waterplane_area_sqft - fore_area_sqft - quarter_area_sqft) * 1.01, selector 4 "
        "central_area_sqft = (machinery_lt * 3 / (displacement_lt * 0.94) * 0.65 * L + 16) * "
        "(B + 16) - 256, selector 5 replaces machinery_lt * 3 with ammunition_lt, selector 6 "
        "adds them; the recovered method then adds the forecastle and quarter-deck terms after "
        "the switch for EVERY selector, so total_lt = (central_area_sqft * "
        "central_thickness_in + fore_area_sqft * forecastle_thickness_in + quarter_area_sqft * "
        "quarterdeck_thickness_in) * 0.0185"),
    "conning": (
        "ArmourControl.cs:727-735 weightConningCalc: "
        "w_lt = 10 * (displacement_lt / 10000) ** (2/3) * (forecastle_thickness_in + "
        "aft_thickness_in)"),
}

ASSUMPTIONS = (
    "every fixed region keeps its own recovered identity and its own owned target; the "
    "seven regions are never merged and a conning tower is never merged into a belt",
    "lengths are declared in metres and converted to feet exactly once, thicknesses are "
    "declared in millimetres and converted to inches exactly once, and the returned mass "
    "is the original's own long tons plus the same figure in metric tonnes",
    "the belt taper term is the original's own mixed-unit term: the dimensionless "
    "(hull_length - length) / hull_length ratio raised to (1 - co_waterplane) multiplies a "
    "beam in feet and is added to a length in feet; no inclination multiplier is invented, "
    "because the original uses the belt inclination only for its own height warning",
    "a belt whose declared length exceeds the declared hull length is unavailable: the "
    "recovered exponent would then be a negative base with a fractional power, and it is "
    "reported rather than evaluated as NaN, a complex number or a made-up area",
    "the recovered deck coverage switch replaces only the central area and is never "
    "merged into one option: all seven stay distinct, declared choices. Selectors "
    "0-3 fall through to the one recovered waterplane expression with its 1.01 "
    "remaining-area margin, so four different labels legitimately read the same "
    "recovered central area, and selectors 4-6 read the recovered box expression "
    "with its own +16 and -256 margin. The forecastle and quarter-deck plate terms "
    "are added after the switch for EVERY selector, so a box deck is the recovered "
    "box plus its two upper plates and changing either fraction changes the total",
    "a known zero selected machinery or ammunition mass keeps the recovered box margin "
    "instead of collapsing the box area, and an unknown one leaves the box area unknown; a "
    "known zero fraction is a determined zero area and an unknown fraction is not",
    "the conning towers are returned as one combined fore-plus-aft mass counted exactly once, "
    "with the two contributions reported beside it; no conning tower height, width, position "
    "or centre of gravity is inferred",
    "a declared zero thickness multiplies every term of its recovered expression, so it is a "
    "determined zero mass that does not need the unrelated hull context it would otherwise read",
    "a derived negative, non-finite or geometrically impossible mass is reported unavailable "
    "and never proposed, clamped or replaced by an invented minimum",
    "the record carries its own owned ledger target and its own balance role; nothing is "
    "deducted from another item and a reader who already carries this armour inside another "
    "weight must split that target first",
)

UNITS = {
    "declared": {"thickness_mm": "mm", "length_m": "m", "height_m": "m",
                 "coverage_index": "selector", "forecastle_fraction": "fraction",
                 "quarterdeck_fraction": "fraction", "forecastle_mm": "mm",
                 "quarterdeck_mm": "mm", "aft_mm": "mm"},
    "context": {"length_m": "m", "beam_m": "m", "co_waterplane": "coefficient",
                "waterplane_area_m2": "m^2", "displacement_t": "t",
                "machinery_mass_t": "t", "ammunition_mass_t": "t"},
    "source_expression": {"length": "ft", "thickness": "in", "mass": "long ton",
                          "area": "ft^2"},
    "returned_mass": {"total_long_tons": "long ton", "mass_t": "t"},
}


class ArmourValidationError(ValueError):
    """Report a refused fixed-armour declaration with structured diagnostics."""

    def __init__(self, diagnostics):
        self.diagnostics = copy.deepcopy(diagnostics)
        super().__init__("; ".join(d["message"] for d in diagnostics if d.get("blocking", True)))


# ------------------------------------------------------------------ helpers

def _diag(code, message, path, field=None):
    return {"code": code, "severity": "error", "field": field, "path": path,
            "message": message, "blocking": True}


def _unavailable(code, field, path, message):
    return {"code": code, "severity": "warning", "field": field, "path": path,
            "message": message, "blocking": False}


def _finite(value, path):
    if isinstance(value, complex) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("%s: the derived result is not a finite real number" % (path,))
    return float(value)


def _inches(value_mm):
    return value_mm / MM_PER_INCH


def _feet(value_m):
    return value_m / M_PER_FT


def _sqft(value_m2):
    return value_m2 / (M_PER_FT * M_PER_FT)


def _tonnes(value_lt):
    return value_lt * LONG_TON_KG / 1000.0


def _long_tons(value_t):
    return value_t * 1000.0 / LONG_TON_KG


# ------------------------------------------------------------- declaration --

def _optional_string(raw, field, path, diagnostics, values=None):
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        diagnostics.append(_diag("fixed_armour.invalid", "must be a non-empty string",
                                 path + "." + field, field))
        return None
    if values is not None and value not in values:
        diagnostics.append(_diag("fixed_armour.enum",
                                 "must name a declared %s" % (", ".join(sorted(values)),),
                                 path + "." + field, field))
        return None
    return value


def _optional_note(raw, field, path, diagnostics):
    """An optional free-text provenance note.

    A blank note means *no note supplied*, which is a legitimate state for a
    declaration a reader has not yet annotated. It is read as absent, never as a
    claim, and it never refuses an otherwise saveable draft.
    """
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        diagnostics.append(_diag("fixed_armour.invalid", "must be a string or null",
                                 path + "." + field, field))
        return None
    return value.strip() or None


def _optional_int(raw, field, path, diagnostics, low, high):
    value = raw.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        # A fractional selector is refused, never truncated.
        diagnostics.append(_diag("fixed_armour.invalid", "must be an integer",
                                 path + "." + field, field))
        return None
    if value < low or value > high:
        diagnostics.append(_diag("fixed_armour.domain",
                                 "must be an integer in [%d, %d]" % (low, high),
                                 path + "." + field, field))
        return None
    return int(value)


def _optional_number(raw, field, path, diagnostics, *, low=None, high=None):
    value = raw.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        diagnostics.append(_diag("fixed_armour.invalid", "must be a finite number",
                                 path + "." + field, field))
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        diagnostics.append(_diag("fixed_armour.invalid",
                                 "exceeds the supported numeric range",
                                 path + "." + field, field))
        return None
    if not math.isfinite(number):
        diagnostics.append(_diag("fixed_armour.invalid", "must be a finite number",
                                 path + "." + field, field))
        return None
    if low is not None and number < low:
        diagnostics.append(_diag("fixed_armour.domain", "must be >= %r" % (low,),
                                 path + "." + field, field))
        return None
    if high is not None and number > high:
        diagnostics.append(_diag("fixed_armour.domain", "must be <= %r" % (high,),
                                 path + "." + field, field))
        return None
    return number


def _object(raw, path, diagnostics, allowed):
    if not isinstance(raw, dict):
        diagnostics.append(_diag("fixed_armour.invalid", "must be an object or null", path))
        return False
    for key in sorted(set(raw) - set(allowed)):
        diagnostics.append(_diag("fixed_armour.unsupported_field",
                                 "unsupported field %r" % (key,), path + "." + key))
    return True


def _normalize(raw, path, diagnostics):
    """One declared record in the canonical shape, whatever its kind."""
    if not isinstance(raw, dict):
        _object(raw, path, diagnostics, COMMON_FIELDS + ALL_FIELDS)
        return None
    kind = _optional_string(raw, "kind", path, diagnostics, values=KINDS)
    allowed = COMMON_FIELDS + FIELDS_BY_KIND.get(kind, ALL_FIELDS)
    if not _object(raw, path, diagnostics, allowed):
        return None
    identity = raw.get("id")
    if not isinstance(identity, str) or not ID_PATTERN.match(identity):
        diagnostics.append(_diag(
            "fixed_armour.invalid",
            "must be 1..80 characters of ASCII letters, digits, underscore, dot or hyphen",
            path + ".id", "id"))
        identity = None
    record = {"id": identity, "kind": kind,
              "system_id": _optional_string(raw, "system_id", path, diagnostics),
              "item_id": _optional_string(raw, "item_id", path, diagnostics),
              "source": _optional_note(raw, "source", path, diagnostics)}
    record["thickness_mm"] = _optional_number(raw, "thickness_mm", path, diagnostics,
                                              low=0.0, high=MAX_THICKNESS_MM)
    if "length_m" in allowed:
        record["length_m"] = _optional_number(raw, "length_m", path, diagnostics,
                                              low=0.0, high=MAX_EXTENT_M)
        record["height_m"] = _optional_number(raw, "height_m", path, diagnostics,
                                              low=0.0, high=MAX_HEIGHT_M)
    else:
        record["length_m"] = record["height_m"] = None
    if "coverage_index" in allowed:
        record["coverage_index"] = _optional_int(raw, "coverage_index", path, diagnostics,
                                                  0, DECK_SELECTOR_COUNT - 1)
        forecastle = _optional_number(raw, "forecastle_fraction", path, diagnostics,
                                      low=0.0, high=1.0)
        quarterdeck = _optional_number(raw, "quarterdeck_fraction", path, diagnostics,
                                       low=0.0, high=1.0)
        if forecastle is not None and quarterdeck is not None and forecastle + quarterdeck > 1.0:
            diagnostics.append(_diag(
                "fixed_armour.domain",
                "the forecastle and quarter-deck fractions together must not exceed 1; they "
                "are refused, not clamped", path + ".forecastle_fraction", "forecastle_fraction"))
        record["forecastle_fraction"] = forecastle
        record["quarterdeck_fraction"] = quarterdeck
        record["forecastle_mm"] = _optional_number(raw, "forecastle_mm", path, diagnostics,
                                                   low=0.0, high=MAX_THICKNESS_MM)
        record["quarterdeck_mm"] = _optional_number(raw, "quarterdeck_mm", path, diagnostics,
                                                    low=0.0, high=MAX_THICKNESS_MM)
    else:
        record["coverage_index"] = None
        record["forecastle_fraction"] = record["quarterdeck_fraction"] = None
        record["forecastle_mm"] = record["quarterdeck_mm"] = None
    if "aft_mm" in allowed:
        record["aft_mm"] = _optional_number(raw, "aft_mm", path, diagnostics,
                                            low=0.0, high=MAX_THICKNESS_MM)
    else:
        record["aft_mm"] = None
    return record


def validate_configs(raw, path="$.concept_design.fixed_armour"):
    """Validate the optional ``fixed_armour`` array into normalized records.

    Returns the canonical list. A wrong type, an out-of-range number, an unknown
    kind, a field that does not belong to the chosen kind, a fractional selector
    and a duplicate ID are refused with :class:`ArmourValidationError`. An
    unfinished declaration stays saveable and simply has no reading: ``None``
    always means *unknown* and is never the same thing as a declared zero.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ArmourValidationError(
            [_diag("fixed_armour.invalid", "must be an array or null", path)])
    if len(raw) > MAX_RECORDS:
        raise ArmourValidationError([_diag(
            "fixed_armour.domain",
            "at most %d fixed armour records may be declared" % (MAX_RECORDS,), path)])
    records = []
    diagnostics = []
    for position, entry in enumerate(raw):
        rpath = "%s[%d]" % (path, position)
        record = _normalize(entry, rpath, diagnostics)
        if record is None:
            continue
        if record["id"] is not None and any(other["id"] == record["id"] for other in records):
            diagnostics.append(_diag("fixed_armour.duplicate",
                                     "fixed armour record IDs must be unique",
                                     rpath + ".id", "id"))
            record["id"] = None
        records.append(record)
    if diagnostics:
        raise ArmourValidationError(diagnostics)
    return records


def as_record(record):
    """Accept a normalized record or a raw declaration, without ever raising."""
    if isinstance(record, dict):
        known = {key: record.get(key) for key in ("id", "kind", "system_id", "item_id", "source")}
        for key in ALL_FIELDS:
            known[key] = record.get(key)
        return known
    return {"id": None, "kind": None, "system_id": None, "item_id": None, "source": None,
            **{key: None for key in ALL_FIELDS}}


# ------------------------------------------------------------------ context

def _fact(context, name):
    """Read one canonical context fact together with its own provenance.

    A fact is either a bare number, whose own origin is then unknown and recorded
    as ``None``, or a ``{"value", "source", "estimate"}`` record whose origin
    travels all the way into the returned provenance.
    """
    raw = context.get(name) if isinstance(context, dict) else None
    if raw is None:
        return None, None
    if isinstance(raw, dict):
        value = raw.get("value")
        origin = {"source": raw.get("source"), "estimate": raw.get("estimate")}
    else:
        value, origin = raw, None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, origin
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return None, origin
    if not math.isfinite(number):
        return None, origin
    return number, origin


def _read_context(context):
    """Every canonical fact the kernels may read, with its own provenance."""
    values, origins = {}, {}
    for name in CONTEXT_FIELDS:
        value, origin = _fact(context, name)
        values[name] = value
        origins[name] = origin
    return values, origins


def _plate_inches(area, thickness_mm, field, path, label):
    """The recovered per-area plate thickness, where a determined zero area needs none."""
    if area == 0.0:
        return 0.0, None
    if thickness_mm is None:
        return None, _unavailable(
            "fixed_armour.unknown", field, path,
            "the recovered %s mass multiplies a non-zero area by its own plate thickness, so "
            "%s must be known; an unknown plate is never read as a zero plate" % (label, field))
    return _inches(thickness_mm), None


# ------------------------------------------------------------------ reading

def _plate_values():
    return {"total_long_tons": None, "mass_t": None, "plate_long_tons": None,
            "thickness_mm": None, "length_m": None, "height_m": None,
            "length_ft": None, "height_ft": None, "thickness_in": None,
            "area_sqft": None, "area_m2": None}


def _belt_values():
    values = _plate_values()
    values.update({"hull_length_ft": None, "hull_beam_ft": None, "co_waterplane": None,
                   "taper_factor": None})
    return values


def _deck_values():
    return {"total_long_tons": None, "mass_t": None,
            "central_long_tons": None, "fore_long_tons": None, "quarter_long_tons": None,
            "coverage_index": None, "thickness_mm": None, "forecastle_mm": None,
            "quarterdeck_mm": None, "forecastle_fraction": None, "quarterdeck_fraction": None,
            "central_area_sqft": None, "fore_area_sqft": None, "quarter_area_sqft": None,
            "total_area_sqft": None, "hull_length_ft": None, "hull_beam_ft": None,
            "co_waterplane": None, "waterplane_area_sqft": None,
            "displacement_long_tons": None, "machinery_long_tons": None,
            "ammunition_long_tons": None}


def _conning_values():
    return {"total_long_tons": None, "mass_t": None, "fore_long_tons": None,
            "aft_long_tons": None, "thickness_mm": None, "aft_mm": None,
            "fore_thickness_in": None, "aft_thickness_in": None,
            "displacement_long_tons": None, "scale_factor": None}


def values_for(kind):
    """The complete flat reading key set of one kind; irrelevant keys stay null."""
    if kind in BELT_KINDS:
        return _belt_values()
    if kind in PLATE_KINDS:
        return _plate_values()
    if kind == "deck":
        return _deck_values()
    if kind == "conning":
        return _conning_values()
    return {"total_long_tons": None, "mass_t": None}


def _unknown_thickness(path, field, diagnostics, label):
    diagnostics.append(_unavailable(
        "fixed_armour.unknown",  field,  path, 
        "the declared %s thickness is unknown, so this fixed armour has no derived mass; it "
        "is not read as a zero thickness" % (label,)))
    return None


def _plate(record, values, context, diagnostics, path, kind):
    """ArmourControl.cs:610-618 and :654-686, the planar doubled plates."""
    thickness = record["thickness_mm"]
    length = record["length_m"]
    height = record["height_m"]
    values.update(thickness_mm=thickness, length_m=length, height_m=height)
    if thickness is None:
        return _unknown_thickness(path, "thickness_mm", diagnostics, "plate")
    if thickness == 0.0:
        # Every term of the recovered expression carries this declared zero.
        values.update(length_ft=_feet(length) if length is not None else None,
                      height_ft=_feet(height) if height is not None else None,
                      thickness_in=0.0)
        return 0.0
    missing = [name for name, value in (("length_m", length), ("height_m", height))
               if value is None]
    if missing:
        diagnostics.append(_unavailable(
            "fixed_armour.unknown",  missing[0],  path, 
            "the recovered planar-plate expression needs both declared extents; %s is unknown "
            "and is not read as a zero extent" % (", ".join(missing),)))
        return None
    length_ft, height_ft = _feet(length), _feet(height)
    thickness_in = _inches(thickness)
    area = (2.0 if kind in DOUBLED_PLATE_KINDS else 1.0) * length_ft * height_ft
    values.update(length_ft=length_ft, height_ft=height_ft, thickness_in=thickness_in,
                  area_sqft=area, area_m2=area * M_PER_FT * M_PER_FT)
    return _finite(area * thickness_in * EMPIRICAL_MASS_CONSTANT, path)


def _belt(record, values, context, diagnostics, path):
    """ArmourControl.cs:602-608 and :620-626, the tapered main and upper belts."""
    thickness = record["thickness_mm"]
    length = record["length_m"]
    height = record["height_m"]
    values.update(thickness_mm=thickness, length_m=length, height_m=height)
    if thickness is None:
        return _unknown_thickness(path, "thickness_mm", diagnostics, "belt")
    if thickness == 0.0:
        values.update(length_ft=_feet(length) if length is not None else None,
                      height_ft=_feet(height) if height is not None else None,
                      thickness_in=0.0)
        return 0.0
    missing = [name for name, value in (("length_m", length), ("height_m", height))
               if value is None]
    if missing:
        diagnostics.append(_unavailable(
            "fixed_armour.unknown",  missing[0],  path, 
            "the recovered belt expression needs both declared extents; %s is unknown and is "
            "not read as a zero extent" % (", ".join(missing),)))
        return None
    hull_length_m = context["length_m"]
    beam_m = context["beam_m"]
    cwp = context["co_waterplane"]
    missing = [name for name, value in (("length_m", hull_length_m), ("beam_m", beam_m),
                                       ("co_waterplane", cwp)) if value is None]
    if missing:
        diagnostics.append(_unavailable(
            "fixed_armour.unknown",  "co_waterplane",  path, 
            "a positive belt reads the hull length, the hull beam and the recovered waterplane "
            "coefficient; %s is unknown, and a simple planar plate is never blocked by that "
            "missing hull context" % (", ".join(missing),)))
        return None
    if hull_length_m <= 0.0 or beam_m <= 0.0:
        diagnostics.append(_unavailable(
            "fixed_armour.unavailable",  "length_m",  path, 
            "the recovered belt expression divides by the declared hull length, so a "
            "determined zero hull length leaves it undefined; it is reported, not clamped"))
        return None
    if length > hull_length_m:
        diagnostics.append(_unavailable(
            "fixed_armour.unavailable",  "length_m",  path + ".length_m", 
            "the declared belt length exceeds the declared hull length, so the recovered taper "
            "would raise a negative base to a fractional power; the reading is unavailable "
            "rather than NaN"))
        return None
    length_ft, height_ft = _feet(length), _feet(height)
    hull_length_ft, beam_ft = _feet(hull_length_m), _feet(beam_m)
    taper = ((hull_length_ft - length_ft) / hull_length_ft) ** (1.0 - cwp)
    thickness_in = _inches(thickness)
    area = (length_ft + taper * beam_ft) * height_ft * 2.0
    values.update(length_ft=length_ft, height_ft=height_ft, thickness_in=thickness_in,
                  hull_length_ft=hull_length_ft, hull_beam_ft=beam_ft, co_waterplane=cwp,
                  taper_factor=taper, area_sqft=area, area_m2=area * M_PER_FT * M_PER_FT)
    return _finite(area * thickness_in * EMPIRICAL_MASS_CONSTANT, path)


def _deck(record, values, context, diagnostics, path):
    """ArmourControl.cs:694-725, the complete seven-selector deck expression."""
    selector = record["coverage_index"]
    central_mm = record["thickness_mm"]
    fore_mm = record["forecastle_mm"]
    quarter_mm = record["quarterdeck_mm"]
    forecastle = record["forecastle_fraction"]
    quarterdeck = record["quarterdeck_fraction"]
    values.update(coverage_index=selector, thickness_mm=central_mm, forecastle_mm=fore_mm,
                  quarterdeck_mm=quarter_mm, forecastle_fraction=forecastle,
                  quarterdeck_fraction=quarterdeck)
    if selector is None:
        diagnostics.append(_unavailable(
            "fixed_armour.unknown",  "coverage_index",  path, 
            "no recovered deck coverage selector is declared, so the covered plan area is "
            "unknown; it is not inferred as selector 0"))
        return None
    if central_mm is None:
        return _unknown_thickness(path, "thickness_mm", diagnostics, "central deck")
    if central_mm == 0.0 and fore_mm == 0.0 and quarter_mm == 0.0:
        # Every recovered area term carries a declared zero thickness.
        return 0.0
    displacement_t = context["displacement_t"]
    hull_length_m = context["length_m"]
    beam_m = context["beam_m"]
    cwp = context["co_waterplane"]
    missing = [name for name, value in (("length_m", hull_length_m), ("beam_m", beam_m))
               if value is None]
    if missing:
        diagnostics.append(_unavailable(
            "fixed_armour.unknown",  "co_waterplane",  path, 
            "the recovered deck area needs the hull length, the hull beam and the recovered "
            "waterplane coefficient; %s is unknown" % (", ".join(missing),)))
        return None
    if hull_length_m <= 0.0 or beam_m <= 0.0:
        diagnostics.append(_unavailable(
            "fixed_armour.unavailable",  "length_m",  path, 
            "the recovered deck area divides by a determined zero hull length; it is "
            "reported, not clamped"))
        return None
    length_ft, beam_ft = _feet(hull_length_m), _feet(beam_m)
    values.update(hull_length_ft=length_ft, hull_beam_ft=beam_ft, co_waterplane=cwp)
    # ArmourControl.cs:718-719 adds the forecastle and quarter-deck terms after the
    # switch, for EVERY selector. The recovered coverage choice only replaces the
    # *central* area; it never removes the two plate layers above it.
    missing = [name for name, value in (("forecastle_fraction", forecastle),
                                       ("quarterdeck_fraction", quarterdeck))
               if value is None]
    if missing:
        diagnostics.append(_unavailable(
            "fixed_armour.unknown",  missing[0],  path,
            "the recovered deck adds the forecastle and quarter-deck areas after the "
            "coverage switch for every selector, so %s must be known; an unknown fraction "
            "is never read as a zero fraction" % (", ".join(missing),)))
        return None
    if cwp is None and (forecastle != 0.0 or quarterdeck != 0.0):
        diagnostics.append(_unavailable("fixed_armour.unknown", "co_waterplane", path,
                                       "non-zero end-deck areas need the waterplane coefficient"))
        return None
    fore_area = (0.0 if forecastle == 0.0 else
                 math.pow(2.0 * forecastle, 1.0 - cwp ** 2) * beam_ft * length_ft * forecastle / 2.0)
    quarter_area = (0.0 if quarterdeck == 0.0 else
                   math.pow(quarterdeck, 1.0 - cwp) * beam_ft * length_ft * quarterdeck / 4.0
                    + (math.pow(quarterdeck, 1.0 - cwp) + math.pow(2.0 * quarterdeck, 1.0 - cwp))
                    * beam_ft * length_ft * quarterdeck / 4.0)
    if central_mm == 0.0:
        # The mass term is known zero; the unevaluated central geometry remains
        # unknown in the public readings rather than pretending its area is zero.
        central_area = 0.0
    elif selector in DECK_AREA_SELECTORS:
        waterplane_m2 = context["waterplane_area_m2"]
        if waterplane_m2 is None:
            diagnostics.append(_unavailable(
                "fixed_armour.unknown",  "waterplane_area_m2",  path,
                "the recovered central area is the recovered waterplane area less the "
                "forecastle and quarter-deck areas, so the waterplane area must be known"))
            return None
        waterplane_sqft = _sqft(waterplane_m2)
        central_area = (waterplane_sqft - fore_area - quarter_area) * DECK_CENTRAL_MARGIN
        values["waterplane_area_sqft"] = waterplane_sqft
    else:
        if displacement_t is None:
            diagnostics.append(_unavailable(
                "fixed_armour.unknown",  "displacement_t",  path,
                "the recovered box deck divides by the declared displacement, so a box "
                "coverage selector needs a known displacement"))
            return None
        displacement_lt = _long_tons(displacement_t)
        if displacement_lt <= 0.0:
            diagnostics.append(_unavailable(
                "fixed_armour.unavailable",  "displacement_t",  path,
                "the recovered box deck divides by the declared displacement, so a determined "
                "zero displacement leaves it undefined; it is reported, not clamped"))
            return None
        loads = []
        if selector in (DECK_MACHINERY_SELECTOR, DECK_COMBINED_SELECTOR):
            mass = context["machinery_mass_t"]
            loads.append(("machinery_long_tons", "machinery_mass_t",
                          DECK_BOX_MACHINERY_MULTIPLIER * _long_tons(mass)
                          if mass is not None else None))
        if selector in (DECK_AMMUNITION_SELECTOR, DECK_COMBINED_SELECTOR):
            mass = context["ammunition_mass_t"]
            loads.append(("ammunition_long_tons", "ammunition_mass_t",
                          _long_tons(mass) if mass is not None else None))
        unknown = [field for _reading, field, value in loads if value is None]
        if unknown:
            diagnostics.append(_unavailable(
                "fixed_armour.unknown",  unknown[0],  path,
                "the recovered box deck scales its central area by the selected %s, so that "
                "selected mass must be known; an unknown selected mass is never read as a "
                "zero, which would keep the recovered box margin and read as a real box"
                % ("machinery and ammunition masses" if len(unknown) > 1
                   else "%s mass" % (unknown[0],))))
            return None
        for reading, _field, value in loads:
            values[reading] = value
        # Only the central area is the recovered box: the forecastle and quarter-deck
        # plates stay separate layers on top of it.
        central_area = (
            (sum(value for _r, _f, value in loads)
             / (displacement_lt * DECK_BOX_AMMUNITION_DISPLACEMENT_FACTOR)
             * DECK_BOX_LENGTH_COEFFICIENT * length_ft + DECK_BOX_CONSTANT)
            * (beam_ft + DECK_BOX_CONSTANT) - DECK_BOX_AREA_OFFSET)
        values["displacement_long_tons"] = displacement_lt
    if any(area < 0.0 for area in (central_area, fore_area, quarter_area)):
        raise ValueError("a recovered deck area is negative; positive end plates cannot offset it")
    fore_in, fore_diag = _plate_inches(fore_area, fore_mm, "forecastle_mm", path,
                                        "forecastle deck")
    quarter_in, quarter_diag = _plate_inches(quarter_area, quarter_mm, "quarterdeck_mm", path,
                                              "quarter-deck")
    central_in, central_diag = _plate_inches(central_area, central_mm, "thickness_mm", path,
                                             "central deck")
    for diagnostic in (fore_diag, quarter_diag, central_diag):
        if diagnostic is not None:
            diagnostics.append(diagnostic)
    if fore_diag is not None or quarter_diag is not None or central_diag is not None:
        return None
    values.update(central_area_sqft=central_area if central_mm != 0.0 else None, fore_area_sqft=fore_area,
                  quarter_area_sqft=quarter_area,
                  total_area_sqft=central_area + fore_area + quarter_area if central_mm != 0.0 else None)
    values["central_long_tons"] = _finite(central_area * central_in * EMPIRICAL_MASS_CONSTANT,
                                          path + ".central")
    values["fore_long_tons"] = _finite(fore_area * fore_in * EMPIRICAL_MASS_CONSTANT,
                                       path + ".forecastle")
    values["quarter_long_tons"] = _finite(quarter_area * quarter_in * EMPIRICAL_MASS_CONSTANT,
                                          path + ".quarterdeck")
    return _finite(values["central_long_tons"] + values["fore_long_tons"]
                   + values["quarter_long_tons"], path)


def _conning(record, values, context, diagnostics, path):
    """ArmourControl.cs:727-735, the combined fore-plus-aft conning tower."""
    fore_mm = record["thickness_mm"]
    aft_mm = record["aft_mm"]
    values.update(thickness_mm=fore_mm, aft_mm=aft_mm)
    if fore_mm is None and aft_mm is None:
        return _unknown_thickness(path, "thickness_mm", diagnostics, "conning tower")
    if fore_mm == 0.0 and aft_mm == 0.0:
        # The recovered displacement factor multiplies a declared zero thickness sum.
        return 0.0
    missing = [field for field, value in (("thickness_mm", fore_mm), ("aft_mm", aft_mm))
               if value is None]
    if missing:
        diagnostics.append(_unavailable(
            "fixed_armour.unknown",  missing[0],  path, 
            "the recovered conning tower expression adds the fore and aft plate thicknesses, "
            "so %s must be known; an unknown plate is never read as a zero plate"
            % (", ".join(missing),)))
        return None
    displacement_t = context["displacement_t"]
    if displacement_t is None:
        diagnostics.append(_unavailable(
            "fixed_armour.unknown",  "displacement_t",  path, 
            "the recovered conning tower scales its mass by the declared displacement, which "
            "is unknown"))
        return None
    displacement_lt = _long_tons(displacement_t)
    if displacement_lt <= 0.0:
        diagnostics.append(_unavailable(
            "fixed_armour.unavailable",  "displacement_t",  path, 
            "the recovered conning tower expression raises a non-positive displacement ratio to "
            "a fractional power; it is reported, not clamped"))
        return None
    scale = CONNING_COEFFICIENT * math.pow(displacement_lt / CONNING_DISPLACEMENT_REFERENCE,
                                            CONNING_DISPLACEMENT_EXPONENT)
    fore_in, aft_in = _inches(fore_mm), _inches(aft_mm)
    values.update(displacement_long_tons=displacement_lt, scale_factor=scale,
                  fore_thickness_in=fore_in, aft_thickness_in=aft_in)
    values["fore_long_tons"] = _finite(scale * fore_in, path + ".fore")
    values["aft_long_tons"] = _finite(scale * aft_in, path + ".aft")
    # The recovered proposal is the combined figure, counted exactly once.
    return _finite(scale * (fore_in + aft_in), path)


def component_breakdown(values, kind):
    """The per-term long-ton contributions the generated model reports."""
    total = values.get("total_long_tons")
    if kind == "deck":
        return {"central_long_tons": values.get("central_long_tons"),
                "fore_long_tons": values.get("fore_long_tons"),
                "quarter_long_tons": values.get("quarter_long_tons")}
    if kind == "conning":
        return {"fore_long_tons": values.get("fore_long_tons"),
                "aft_long_tons": values.get("aft_long_tons")}
    if kind in KINDS:
        return {"plate_long_tons": total}
    return {}


def _json_safe(value):
    """Keep the origin text plain JSON, even when a caller supplies a non-finite.

    A rejected non-finite context fact is *unknown*, and an unknown number has no
    JSON literal. It is written as its own text here so the origin stays readable
    and parseable instead of being dropped or silently replaced by zero.
    """
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _origin_text(record, context, provenance):
    """The whole declaration, context and provenance as one scalar JSON text.

    Persisted mass receipts accept a flat scalar input map, so nothing nested is
    written into the receipt itself: the complete declaration travels as its own
    origin text instead of widening the receipt schema.
    """
    return json.dumps(_json_safe({"record": record, "context": context,
                                  "provenance": provenance}),
                      ensure_ascii=False, sort_keys=True, allow_nan=False, default=str)


def evaluate(record, context, path="$.concept_design.fixed_armour"):
    """Evaluate one declared fixed-armour region against its canonical context.

    ``record`` is a normalized :func:`validate_configs` record or a raw
    declaration. ``context`` carries the optional **canonical** facts the kernels
    may read; each is either a number or a ``{"value", "source", "estimate"}``
    record whose own provenance travels into the result.

    This never raises for an unfinished declaration and never substitutes a
    default: an unknown fact produces ``status == "unavailable"``, a null
    reading and a structured diagnostic. Irrelevant missing context does not
    disable a simple planar plate or a determined known-zero result.
    """
    declared = as_record(record)
    kind = declared["kind"]
    context_values, origins = _read_context(context)
    diagnostics = []
    values = values_for(kind)
    if kind is None:
        diagnostics.append(_unavailable(
            "fixed_armour.unconfigured",  "kind",  path + ".kind", 
            "no fixed armour kind is chosen, so there is no recovered expression to evaluate; "
            "that is not a known zero"))
    elif kind not in KINDS:
        diagnostics.append(_unavailable(
            "fixed_armour.enum",  "kind",  path + ".kind", 
            "the declared fixed armour kind is outside the recovered table"))
    else:
        try:
            if kind in BELT_KINDS:
                total = _belt(declared, values, context_values, diagnostics, path)
            elif kind in PLATE_KINDS:
                total = _plate(declared, values, context_values, diagnostics, path, kind)
            elif kind == "deck":
                total = _deck(declared, values, context_values, diagnostics, path)
            else:
                total = _conning(declared, values, context_values, diagnostics, path)
        except (ArithmeticError, ValueError) as error:
            diagnostics.append(_unavailable(
                "fixed_armour.unavailable",  None,  path, 
                "the recovered fixed armour expression cannot be evaluated as a finite real "
                "number: %s" % (error,)))
            total = None
        if total is not None:
            if total < 0.0:
                diagnostics.append(_unavailable(
                    "fixed_armour.unavailable",  None,  path, 
                    "the recovered expression gives a negative mass of %.6f long tons, which is "
                    "not a possible armour mass; it is reported and never proposed, clamped or "
                    "replaced by a zero" % (total,)))
                total = None
            else:
                values["total_long_tons"] = total
                if "plate_long_tons" in values:
                    values["plate_long_tons"] = total
                values["mass_t"] = _tonnes(total)
    if any(isinstance(value, float) and not math.isfinite(value)
           for value in values.values()):
        diagnostics.append(_unavailable(
            "fixed_armour.unavailable", None, path,
            "a derived reading overflowed; no mass is available for adoption"))
        values = {key: (None if isinstance(value, float) and not math.isfinite(value)
                        else value) for key, value in values.items()}
        values["total_long_tons"] = None
        values["mass_t"] = None
    provenance = {
        "kernel": KERNEL_BY_KIND.get(kind, "fixed_armour_unknown"),
        "source_location": SOURCE_LOCATION,
        "source_assembly": SOURCE_ASSEMBLY,
        "source_sha256": SOURCE_SHA256,
        "source_scope": SOURCE_SCOPE,
        "method_version": METHOD_VERSION,
        "formula": FORMULA_BY_KIND.get(kind),
        "assumptions": list(ASSUMPTIONS),
        "context": origins,
        "units": copy.deepcopy(UNITS),
        "inputs": {key: value for key, value in values.items()
                   if isinstance(value, (int, float)) and not isinstance(value, bool)},
    }
    return {
        "id": declared["id"],
        "kind": kind,
        "method_version": METHOD_VERSION,
        "status": "available" if values["total_long_tons"] is not None else "unavailable",
        "values": values,
        "diagnostics": diagnostics,
        "provenance": provenance,
        "origin": _origin_text(declared, context, provenance),
    }
