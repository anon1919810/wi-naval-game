"""Auxiliary weapons mass: torpedoes, mines and depth charges.

A pure function over a finite declared domain. It never touches a project, a
ledger or a file, it never clamps an out-of-domain value, and it never reads an
unknown input as zero: a missing declared fact produces a structured unavailable
diagnostic and a null reading, while a wrong type, a wrong sign, an
out-of-domain number and a fractional count are refused outright.

It is deliberately **not** part of the adapted configuration method and it is
independent of gun batteries and fixed armour. The configuration keeps
``sps-3b3-adapted-v1``; this kernel carries its own
``sps-3b3-auxiliary-weapons-v1``.

Numerical source
----------------
Recovered ``SpringSharpMono`` 3.0.3032.29945, the same original binary the other
concept kernels use (identical assembly string and SHA256, re-exported from
:mod:`concept_estimates`), at ``WeaponControl.cs:325-534`` ``sizeNweight``. The
recovered method is read, not ported: no control graph, event wiring or form state
is reproduced here.

One page, three weapons, two mass expressions
---------------------------------------------
The recovered method branches on the weapon class, not on the unit selector.

* **Torpedo.** ``weaponWeight = (pi * size**2 * length) / ((max(1907 - year, 0)
  + 25) * 937) + 0.004 * (year - 1890)``, then ``*= number``. ``size`` is a
  diameter in **inches**, ``length`` in **feet** and the result is in long tons.
  The whole expression is guarded by ``size > 0 && length > 0 && number > 0``,
  so a known zero in any of the three is a determined zero weapon.
* **Mine and depth charge.** ``weaponWeight = (number + loads) * size / 2240``.
  ``size`` is the **full unit mass** in pounds, not the explosive charge, and
  ``loads`` here really is a reload count added to the carried count.

``loads`` therefore means two different things and this kernel never blurs them:
for a torpedo it is the number of sets, which the recovered mass
expression does not read at all, and for a mine or depth charge it is the reload
count, which it does. The recovered page also rewrites a zero ``loads`` to one
before it computes a *deck area*; that mutation is deliberately **not** carried
over, because rewriting a declared input is not an estimate.

Scope
-----
It is a **mass** reading and nothing else. There is no weapon space, no firing
arc, no reload geometry, no explosive performance, no magazine arrangement and no
whole-program event chain here, and no new strength or space contribution is
invented: the combined weapon-and-mount figure belongs to one existing target
carrying the existing ``other`` balance role, and it is proposed once.

Recovered quirks kept verbatim
------------------------------
* The recovered location factor is a three-way switch that depends on the weapon
  class, and its ``default`` arm is zero. Every declared location is inside the
  recovered range, so the default arm is unreachable here and is never used as a
  fallback for an unknown location.
* A positive weapon with an unknown location has no complete estimate: the mount
  factor multiplies the weapon mass, so it is not a determined number.
* A determined zero weapon needs no location: the factor multiplies a known zero.
* The recovered torpedo denominator is ``(age + 25) * 937``, so a hull year at or
  after 1907 and one before it differ only through the frozen ``age`` floor of
  zero. The year term ``0.004 * (year - 1890)`` is not floored and can be
  negative before 1890; that negative per-weapon figure is what the recovered
  method computes and it is reported, never clamped.

Determinism the original does not have
--------------------------------------
The source is a form: every field carries a value whether or not the reader meant
it. Here ``None`` means *unknown*, ``0`` means a declared zero, and a record may
stay an unfinished draft. An unknown input is never clamped, filled in or read as
zero, and a derived negative, non-finite or impossible mass is reported as
unavailable instead of being proposed.
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

METHOD_VERSION = "sps-3b3-auxiliary-weapons-v1"
SOURCE_LOCATION = "WeaponControl.cs:325-534"
SOURCE_ASSEMBLY = siblings.SOURCE_ASSEMBLY
SOURCE_SHA256 = siblings.SOURCE_SHA256
SOURCE_SCOPE = (
    "Independent empirical mass reading of one declared auxiliary weapon group: a "
    "torpedo tube group, a mine group or a depth charge group, read from the recovered "
    "3b3 sizeNweight expression as that class's own weapon mass plus its own recovered "
    "mount factor, in the original's own inches, feet, pounds and long tons. It is not "
    "weapon space, not a firing arc, not reload geometry, not explosive performance, not "
    "a magazine arrangement, not a strength or space contribution, not whole-program "
    "parity and not validated against any real ship."
)

MM_PER_INCH = siblings.MM_PER_INCH
M_PER_FT = kernels.M_PER_FT
LONG_TON_KG = kernels.LONG_TON_KG
POUND_KG = kernels.KG_PER_LB
# MainForm.cs:28 POUND2TON.
POUNDS_PER_LONG_TON = 2240.0

# WeaponControl.cs:367-368, the recovered torpedo expression.
TORPEDO_AGE_FLOOR_YEAR = 1907
TORPEDO_DENOMINATOR_OFFSET = 25.0
TORPEDO_DENOMINATOR_FACTOR = 937.0
TORPEDO_YEAR_TERM_BASE = 1890
TORPEDO_YEAR_TERM_FACTOR = 0.004

KINDS = ("torpedo", "mine", "depth_charge")
# One combined target per group, carrying the existing balance role. Nothing here
# becomes bare guns, mounts or ammunition, and no new role is introduced.
TARGET_ROLE = "other"
# The recovered location tables (WeaponControl.cs:168-184), kept so a form can offer
# the original's own choices instead of a bare number. They are labels, never parsed.
LOCATION_NAMES = {
    "torpedo": ("deck mounted carriage/fixed tube",
                "deck mounted side rotating tube",
                "deck mounted centre rotating tube",
                "deck mounted reload",
                "submerged bow tube",
                "submerged stern tube",
                "submerged bow & stern tube",
                "submerged side tube",
                "below water reload"),
    "mine": ("Above water - Stern racks/rails", "Below water - bow tubes",
             "Below water - stern tubes", "Below water - side tubes"),
    "depth_charge": ("Stern depth charge racks", "Depth charge throwers",
                     "Hedgehog style A/S mortars", "Squid style A/S mortars"),
}
# WeaponControl.cs:472-527, the recovered mount factors of the three switches.
MOUNT_FACTORS = {
    "torpedo": {0: 0.25, 1: 1.0, 2: 1.0, 3: 0.25, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.0, 8: 0.25},
    "mine": {0: 0.25, 1: 1.0, 2: 1.0, 3: 1.0},
    "depth_charge": {0: 0.25, 1: 0.5, 2: 0.5, 3: 10.0},
}
LOCATION_COUNT_BY_KIND = {kind: len(names) for kind, names in LOCATION_NAMES.items()}

COMMON_FIELDS = ("id", "kind", "system_id", "item_id", "source")
SHARED_FIELDS = ("count", "loads", "location_index")
TORPEDO_FIELDS = ("diameter_mm", "length_m")
UNIT_MASS_FIELDS = ("unit_mass_kg",)
FIELDS_BY_KIND = {
    "torpedo": SHARED_FIELDS + TORPEDO_FIELDS,
    "mine": SHARED_FIELDS + UNIT_MASS_FIELDS,
    "depth_charge": SHARED_FIELDS + UNIT_MASS_FIELDS,
}
ALL_FIELDS = SHARED_FIELDS + TORPEDO_FIELDS + UNIT_MASS_FIELDS

MAX_RECORDS = 50
MAX_COUNT = 1000000
MAX_DIAMETER_MM = 2000.0
MAX_LENGTH_M = 100.0
MAX_UNIT_MASS_KG = 100000.0
MIN_YEAR = 1800
MAX_YEAR = 2100
ID_PATTERN = re.compile(r"\A[A-Za-z0-9_.-]{1,80}\Z")

CONTEXT_FIELDS = ("hull_year",)
KERNEL_BY_KIND = {
    "torpedo": "auxiliary_torpedo_long_tons",
    "mine": "auxiliary_mine_long_tons",
    "depth_charge": "auxiliary_depth_charge_long_tons",
}
FORMULA_BY_KIND = {
    "torpedo": (
        "WeaponControl.cs:360-370: weapon_lt = count * (pi * diameter_in ** 2 * length_ft / "
        "((max(1907 - hull_year, 0) + 25) * 937) + 0.004 * (hull_year - 1890)); mount_lt = "
        "weapon_lt * mount_factor; total_lt = weapon_lt + mount_lt"),
    "mine": (
        "WeaponControl.cs:377-380: weapon_lt = (count + loads) * unit_mass_lb / 2240 where "
        "unit_mass is the full unit mass in pounds and loads is the reload count; "
        "mount_lt = weapon_lt * mount_factor; total_lt = weapon_lt + mount_lt"),
    "depth_charge": (
        "WeaponControl.cs:377-380: weapon_lt = (count + loads) * unit_mass_kg / 0.45359237 / "
        "2240 where unit_mass is the full unit mass and loads is the reload count; "
        "mount_lt = weapon_lt * mount_factor; total_lt = weapon_lt + mount_lt"),
}

ASSUMPTIONS = (
    "one declaration is one auxiliary weapon group with its own independent target; a "
    "torpedo group, a mine group and a depth charge group are never merged, and none of "
    "them is merged into a gun battery or a fixed armour target",
    "lengths are declared in metres and converted to feet exactly once, diameters in "
    "millimetres and converted to inches exactly once, unit masses in kilograms and "
    "converted to pounds exactly once, and the returned mass is the original's own long "
    "tons plus the same figure in metric tonnes",
    "the combined figure is the weapon mass plus the recovered mount factor's share; it is "
    "proposed exactly once, on one target carrying the existing 'other' balance role, and "
    "it is never relabelled as bare guns, mounts or ammunition",
    "no weapon space, firing arc, reload geometry, explosive performance or magazine "
    "arrangement is derived, and no new strength or space contribution is invented",
    "for a torpedo, loads is the number of sets and the recovered mass "
    "expression does not read it, so it is never used as a weight multiplier; for a mine "
    "or depth charge, loads is the reload count and is added to the carried count",
    "the recovered page rewrites a zero loads to one before computing a deck area; that "
    "mutation is not carried over, because rewriting a declared input is not an estimate",
    "a known zero count, diameter or length is a determined zero torpedo weapon, and a "
    "known zero unit mass or a known zero carried-plus-reload count is a determined zero "
    "mine or depth charge weapon; unknown reloads are never read as zero reloads",
    "the recovered mount factor is the three-way switch of its own weapon class, and every "
    "declared location is inside the recovered range; a positive weapon with an unknown "
    "location has no complete estimate, while a determined zero weapon needs no location",
    "the recovered torpedo denominator floors the age term at zero, so a hull year at or "
    "after 1907 and one before it differ only through that floor; the year term itself is "
    "not floored and is reported as the recovered method computes it",
    "an invalid, negative or non-finite derived mass is reported unavailable and is never "
    "clamped, floored or replaced by a zero",
)

UNITS = {
    "declared": {"count": "weapon", "loads": "set (torpedo) / reload (mine, depth charge)",
                 "location_index": "selector", "diameter_mm": "mm", "length_m": "m",
                 "unit_mass_kg": "kg"},
    "context": {"hull_year": "year"},
    "source_expression": {"diameter": "in", "length": "ft", "unit_mass": "lb",
                          "mass": "long ton"},
    "returned_mass": {"weapon_long_tons": "long ton", "mount_long_tons": "long ton",
                      "total_long_tons": "long ton", "mass_t": "t",
                      "mount_factor": "dimensionless"},
}


class AuxiliaryValidationError(ValueError):
    """Report a refused auxiliary declaration with structured diagnostics."""

    def __init__(self, diagnostics):
        self.diagnostics = copy.deepcopy(diagnostics)
        super().__init__("; ".join(d["message"] for d in diagnostics
                                   if d.get("blocking", True)))


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


def _inches(millimetres):
    return millimetres / MM_PER_INCH


def _feet(metres):
    return metres / M_PER_FT


def _pounds(kilograms):
    return kilograms / POUND_KG


def _tonnes(value_lt):
    return value_lt * LONG_TON_KG / 1000.0


# ------------------------------------------------------------- declaration --

def _optional_string(raw, field, path, diagnostics, values=None):
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        diagnostics.append(_diag("auxiliary_weapons.invalid", "must be a non-empty string",
                                 path + "." + field, field))
        return None
    if values is not None and value not in values:
        diagnostics.append(_diag("auxiliary_weapons.enum",
                                 "must be one of %s" % (", ".join(values),),
                                 path + "." + field, field))
        return None
    return value


def _optional_note(raw, field, path, diagnostics):
    """An optional free-text provenance note; a blank note means no note supplied."""
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        diagnostics.append(_diag("auxiliary_weapons.invalid", "must be a string or null",
                                 path + "." + field, field))
        return None
    return value.strip() or None


def _optional_int(raw, field, path, diagnostics, low, high):
    value = raw.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        # A fractional count is refused, never truncated.
        diagnostics.append(_diag("auxiliary_weapons.invalid", "must be an integer",
                                 path + "." + field, field))
        return None
    if value < low or value > high:
        diagnostics.append(_diag("auxiliary_weapons.domain",
                                 "must be an integer in [%d, %d]" % (low, high),
                                 path + "." + field, field))
        return None
    return int(value)


def _optional_number(raw, field, path, diagnostics, *, high):
    value = raw.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        diagnostics.append(_diag("auxiliary_weapons.invalid", "must be a finite number",
                                 path + "." + field, field))
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        diagnostics.append(_diag("auxiliary_weapons.invalid",
                                 "exceeds the supported numeric range",
                                 path + "." + field, field))
        return None
    if not math.isfinite(number):
        diagnostics.append(_diag("auxiliary_weapons.invalid", "must be a finite number",
                                 path + "." + field, field))
        return None
    if number < 0.0:
        diagnostics.append(_diag("auxiliary_weapons.domain", "must be >= 0",
                                 path + "." + field, field))
        return None
    if number > high:
        diagnostics.append(_diag("auxiliary_weapons.domain", "must be <= %r" % (high,),
                                 path + "." + field, field))
        return None
    return number


def _normalize(raw, path, diagnostics):
    if not isinstance(raw, dict):
        diagnostics.append(_diag("auxiliary_weapons.invalid", "must be an object or null",
                                 path))
        return None
    kind = _optional_string(raw, "kind", path, diagnostics, values=KINDS)
    allowed = COMMON_FIELDS + FIELDS_BY_KIND.get(kind, ALL_FIELDS)
    for key in sorted(set(raw) - set(allowed)):
        diagnostics.append(_diag("auxiliary_weapons.unsupported_field",
                                 "unsupported field %r" % (key,), path + "." + key))
    identity = raw.get("id")
    if not isinstance(identity, str) or not ID_PATTERN.match(identity):
        diagnostics.append(_diag(
            "auxiliary_weapons.invalid",
            "must be 1..80 characters of ASCII letters, digits, underscore, dot or hyphen",
            path + ".id", "id"))
        identity = None
    record = {"id": identity, "kind": kind,
              "system_id": _optional_string(raw, "system_id", path, diagnostics),
              "item_id": _optional_string(raw, "item_id", path, diagnostics),
              "source": _optional_note(raw, "source", path, diagnostics)}
    record["count"] = _optional_int(raw, "count", path, diagnostics, 0, MAX_COUNT)
    record["loads"] = _optional_int(raw, "loads", path, diagnostics, 0, MAX_COUNT)
    locations = LOCATION_COUNT_BY_KIND.get(kind, len(LOCATION_NAMES["torpedo"]))
    record["location_index"] = _optional_int(raw, "location_index", path, diagnostics, 0,
                                             locations - 1)
    record["diameter_mm"] = _optional_number(raw, "diameter_mm", path, diagnostics,
                                              high=MAX_DIAMETER_MM)
    record["length_m"] = _optional_number(raw, "length_m", path, diagnostics,
                                          high=MAX_LENGTH_M)
    record["unit_mass_kg"] = _optional_number(raw, "unit_mass_kg", path, diagnostics,
                                              high=MAX_UNIT_MASS_KG)
    return record


def validate_configs(raw, path="$.concept_design.auxiliary_weapons"):
    """Validate the optional ``auxiliary_weapons`` array into normalized records.

    Returns the canonical list. A wrong type, an out-of-range number, an unknown
    kind, a field that does not belong to the chosen kind, a fractional count and a
    duplicate ID are refused with :class:`AuxiliaryValidationError`. An unfinished
    declaration stays saveable: ``None`` always means *unknown* and is never the
    same thing as a declared zero.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AuxiliaryValidationError(
            [_diag("auxiliary_weapons.invalid", "must be an array or null", path)])
    if len(raw) > MAX_RECORDS:
        raise AuxiliaryValidationError([_diag(
            "auxiliary_weapons.domain",
            "at most %d auxiliary weapon records may be declared" % (MAX_RECORDS,), path)])
    records = []
    diagnostics = []
    for position, entry in enumerate(raw):
        rpath = "%s[%d]" % (path, position)
        record = _normalize(entry, rpath, diagnostics)
        if record is None:
            continue
        if record["id"] is not None and any(other["id"] == record["id"] for other in records):
            diagnostics.append(_diag("auxiliary_weapons.duplicate",
                                     "auxiliary weapon record IDs must be unique",
                                     rpath + ".id", "id"))
            record["id"] = None
        records.append(record)
    if diagnostics:
        raise AuxiliaryValidationError(diagnostics)
    return records


def as_record(record):
    """Accept a normalized record or a raw declaration, without ever raising."""
    if isinstance(record, dict):
        return {key: record.get(key) for key in
                ("id", "kind", "system_id", "item_id", "source") + ALL_FIELDS}
    return {key: None for key in ("id", "kind", "system_id", "item_id", "source") + ALL_FIELDS}


# ------------------------------------------------------------------ context

def _fact(context, name):
    """Read one canonical context fact together with its own provenance."""
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


def _year(values, diagnostics, path):
    year = values["hull_year"]
    if year is None:
        diagnostics.append(_unavailable(
            "auxiliary_weapons.unknown", "hull_year", path + ".hull_year",
            "an active torpedo reads the declared hull year, which is unknown"))
        return None
    if not float(year).is_integer():
        diagnostics.append(_unavailable(
            "auxiliary_weapons.invalid", "hull_year", path + ".hull_year",
            "the recovered year branch is defined on whole hull years, so a fractional "
            "hull year is refused rather than truncated"))
        return None
    year = int(year)
    if not MIN_YEAR <= year <= MAX_YEAR:
        diagnostics.append(_unavailable(
            "auxiliary_weapons.domain", "hull_year", path + ".hull_year",
            "hull year %d is outside the supported %d..%d domain" % (year, MIN_YEAR, MAX_YEAR)))
        return None
    return year


# ------------------------------------------------------------------ reading

def values_for(kind):
    """The complete flat reading key set; every key is null until it is derived."""
    return {"weapon_long_tons": None, "mount_long_tons": None, "total_long_tons": None,
            "mass_t": None, "mount_factor": None}


def _missing(record, fields, path, label, diagnostics):
    """Report the first missing declared fact of one expression, if any."""
    names = [field for field in fields if record[field] is None]
    if names:
        listed = ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]
        diagnostics.append(_unavailable(
            "auxiliary_weapons.unknown", names[0], path,
            "the recovered %s mass needs %s; %s is unknown and is never read as zero"
            % (label, listed, "are" if len(names) > 1 else "is")))
    return bool(names)


def _known_zero(fields, record):
    """True when a declared zero makes the recovered guard disjunction false."""
    return any(record[field] == 0 for field in fields if record[field] is not None)


def _torpedo_weapon(record, values, context, diagnostics, path):
    """WeaponControl.cs:360-370, the recovered torpedo expression."""
    # WeaponControl.cs:360 guards the whole expression with size > 0 && length > 0
    # && number > 0, so a known zero in any of the three is a determined zero and
    # needs no hull year. A known zero is checked before the missing facts, because
    # a determined zero is never blocked by an unrelated unknown.
    if _known_zero(("count", "diameter_mm", "length_m"), record):
        return 0.0
    if _missing(record, ("count", "diameter_mm", "length_m"), path, "torpedo", diagnostics):
        return None
    year = _year(context, diagnostics, path)
    if year is None:
        return None
    denominator = ((max(TORPEDO_AGE_FLOOR_YEAR - year, 0) + TORPEDO_DENOMINATOR_OFFSET)
                   * TORPEDO_DENOMINATOR_FACTOR)
    each = (math.pi * _inches(record["diameter_mm"]) ** 2 * _feet(record["length_m"])
            / denominator
            + TORPEDO_YEAR_TERM_FACTOR * (year - TORPEDO_YEAR_TERM_BASE))
    return _finite(each * record["count"], path + ".weapon")


def _unit_mass_weapon(record, values, context, diagnostics, path, label):
    """WeaponControl.cs:377-380, the recovered (count + loads) * unit mass / 2240."""
    if record["count"] == 0 and record["loads"] == 0:
        return 0.0
    if _missing(record, ("unit_mass_kg",), path, label, diagnostics):
        return None
    if record["unit_mass_kg"] == 0.0:
        # A determined zero full unit mass needs neither the count nor the reloads.
        return 0.0
    if record["count"] is None or record["loads"] is None:
        names = [name for name, field in (("count", "count"), ("loads", "loads"))
                 if record[field] is None]
        diagnostics.append(_unavailable(
            "auxiliary_weapons.unknown", names[0], path,
            "the recovered %s mass adds the carried count to the reload count, so %s must "
            "be known; unknown reloads are never read as zero reloads"
            % (label, " and ".join(names))))
        return None
    total_units = record["count"] + record["loads"]
    if total_units == 0:
        return 0.0
    return _finite(total_units * _pounds(record["unit_mass_kg"]) / POUNDS_PER_LONG_TON,
                   path + ".weapon")


def component_breakdown(values, kind):
    """The per-term long-ton contributions the generated model reports."""
    return {"weapon_long_tons": values.get("weapon_long_tons"),
            "mount_long_tons": values.get("mount_long_tons")}


def _declared_numbers(declared, kind):
    """The numeric declared fields that belong to the chosen kind, as flat scalars."""
    allowed = FIELDS_BY_KIND.get(kind, ALL_FIELDS)
    return {key: declared[key] for key in ("count", "loads", "location_index",
                                           "diameter_mm", "length_m", "unit_mass_kg")
            if key in allowed and declared[key] is not None}


def _json_safe(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def evaluate(record, context, path="$.concept_design.auxiliary_weapons"):
    """Evaluate one declared auxiliary weapon group.

    ``record`` is a normalized :func:`validate_configs` record or a raw
    declaration. ``context`` carries the optional **canonical** fact the kernels
    may read, ``hull_year``, as a number or a ``{"value", "source", "estimate"}``
    record whose own provenance travels into the result.

    This never raises for an unfinished declaration and never substitutes a
    default: an unknown fact produces ``status == "unavailable"``, a null reading
    and a structured diagnostic.
    """
    declared = as_record(record)
    kind = declared["kind"]
    values = values_for(kind)
    diagnostics = []
    year, origin = _fact(context, "hull_year")
    facts = {"hull_year": year}
    origins = {"hull_year": origin}
    if kind is None:
        diagnostics.append(_unavailable(
            "auxiliary_weapons.unconfigured", "kind", path + ".kind",
            "no auxiliary weapon kind is chosen, so there is no recovered expression to "
            "evaluate; that is not a known zero"))
    elif kind not in KINDS:
        diagnostics.append(_unavailable(
            "auxiliary_weapons.enum", "kind", path + ".kind",
            "the declared auxiliary weapon kind is outside the recovered table"))
    else:
        try:
            if kind == "torpedo":
                weapon = _torpedo_weapon(declared, values, facts, diagnostics, path)
            else:
                weapon = _unit_mass_weapon(declared, values, facts, diagnostics, path, kind)
        except (ArithmeticError, ValueError) as error:
            diagnostics.append(_unavailable(
                "auxiliary_weapons.unavailable", None, path,
                "the recovered auxiliary weapon expression cannot be evaluated as a finite "
                "real number: %s" % (error,)))
            weapon = None
        if weapon is not None:
            if weapon < 0.0:
                diagnostics.append(_unavailable(
                    "auxiliary_weapons.unavailable", None, path,
                    "the recovered expression gives a negative weapon mass of %.6f long "
                    "tons, which is not a possible mass; it is reported and never proposed, "
                    "clamped or replaced by a zero" % (weapon,)))
            else:
                values["weapon_long_tons"] = weapon
                factor = None
                if weapon == 0.0:
                    # The recovered mount factor multiplies a determined zero, so the
                    # combined mass needs no location. The factor itself stays unknown.
                    values["mount_long_tons"] = 0.0
                    values["total_long_tons"] = 0.0
                    values["mass_t"] = 0.0
                elif declared["location_index"] is None:
                    diagnostics.append(_unavailable(
                        "auxiliary_weapons.unknown", "location_index", path,
                        "the recovered mount factor multiplies a positive weapon mass, so a "
                        "positive weapon without a declared location has no complete "
                        "estimate"))
                else:
                    factor = MOUNT_FACTORS[kind][declared["location_index"]]
                    mount = _finite(weapon * factor, path + ".mount")
                    values["mount_long_tons"] = mount
                    values["total_long_tons"] = _finite(weapon + mount, path + ".total")
                    values["mass_t"] = _tonnes(values["total_long_tons"])
                values["mount_factor"] = factor
    provenance = {
        "kernel": KERNEL_BY_KIND.get(kind, "auxiliary_weapon_unknown"),
        "source_location": SOURCE_LOCATION,
        "source_assembly": SOURCE_ASSEMBLY,
        "source_sha256": SOURCE_SHA256,
        "source_scope": SOURCE_SCOPE,
        "method_version": METHOD_VERSION,
        "formula": FORMULA_BY_KIND.get(kind),
        "target_role": TARGET_ROLE,
        "assumptions": list(ASSUMPTIONS),
        "context": origins,
        "units": copy.deepcopy(UNITS),
        "inputs": {**_declared_numbers(declared, kind),
                   **{key: value for key, value in values.items()
                      if isinstance(value, (int, float)) and not isinstance(value, bool)}},
    }
    return {
        "id": declared["id"],
        "kind": kind,
        "method_version": METHOD_VERSION,
        "status": "available" if values["total_long_tons"] is not None else "unavailable",
        "values": values,
        "diagnostics": diagnostics,
        "provenance": provenance,
        "origin": json.dumps(_json_safe({"record": declared, "context": context,
                                         "provenance": provenance}),
                             ensure_ascii=False, sort_keys=True, allow_nan=False,
                             default=str),
    }
