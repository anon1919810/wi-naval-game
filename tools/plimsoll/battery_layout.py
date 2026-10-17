"""Two-group battery layout identity, position-weighted freeboard and height
factor, plus one complete two-group armour estimate.

This is a pure function over a finite declared domain. It never touches a
project, a ledger or a file, it never clamps an out-of-domain value, and it
never reads an unknown input as zero: a missing declared input produces a
structured unavailable diagnostic and an unknown reading, while a wrong type, a
wrong sign, an out-of-domain number and a fractional count are refused.

It is deliberately **not** part of the adapted configuration method. The
configuration keeps ``sps-3b3-adapted-v1``; this kernel carries its own
``sps-3b3-battery-layout-v1`` and its armour carries
``sps-3b3-battery-armour-v2``, so a reader can always tell which numbers came
from which method.

Numerical source
----------------
Recovered ``SpringSharpMono`` 3.0.3032.29945, the same original binary the
adapted concept kernels and :mod:`battery_armour` use (identical assembly string
and SHA256, re-exported from :mod:`concept_estimates` so the two can never drift
apart):

* ``GunControl.cs:564`` ``mountsCalc``
* ``GunControl.cs:636`` ``perMountCalc``
* ``GunControl.cs:678`` ``freeGunCalc``
* ``GunControl.cs:908`` ``layoutCalc``
* ``GunControl.cs:1127`` ``armWeightCalc`` and ``:1238`` ``diameterCalc``
* ``FreeboardControl.cs:471-472`` the two deck midpoints ``freeFD``/``freeAD``

Scope
-----
The recovered original keeps **two mount groups** (``mountsG1``/``mountsG2``) and
one **fifteen-entry** ``gunsInMount`` selector per group, so one weapon can
describe, for example, a superfiring pair or two different mount configurations. This
kernel reads that structure instead of averaging it away: each group keeps its
own selector, its own recovered barrels-per-mount identity, its own eighteen
layout reading and its own elevated/deck/depressed split, and the armour is the
complete two-group expression rather than the sum of two single-group ones.

It is **not** a form, a centre of gravity, a firing arc, a collision, a real
ship's developed armour area or a whole-program event chain, and it makes no
claim about any real ship.

Recovered quirks kept verbatim
------------------------------
* ``Math.Round(mounts * 0.5, 0)`` is **ties to even**, so three mounts split as
  two/one and five mounts split as two/three; it is never a floor or a ceiling.
* Layouts 0 and 9 branch on ``free.fcLength + free.fdLength >= 0.5`` and their
  one-mount case is inside that branch, so a flush deck moves a single mount from
  the forward deck to the aft deck.
* The two groups' freeboard is combined by **mount count**, while the height
  factor counts **barrels** in the elevated and depressed groups.
* ``armWeightCalc`` averages the two groups' per-mount barrel counts with an
  **integer** division, and above a 0.5 mount adjustment it caps that average at
  four while at or below 0.5 it writes ``perMountG1`` instead of ``perMounts``, so
  ``perMounts`` itself reaches the barbette expression **uncapped**. Capping it
  everywhere would silently drop the negative barbette case the original has.
* The barbette expression multiplies its own coefficient twice, takes the fourth
  root of the date adjustment, and reads the position-weighted freeboard in
  **feet**.
* ``freeGun`` keeps its old value for an empty battery; ``super`` becomes one
  when there are no barrels. This kernel does not inherit stale freeboard: two
  configured groups with a known zero mount count return a determined freeboard
  of ``0`` and a height factor of ``1``, and a declared zero calibre or a zero
  thickness is a real zero rather than a missing number.

Determinism the original does not have
--------------------------------------
The source is a form: every field carries a value whether or not the reader meant
it. Here ``None`` means *unknown*, ``0`` means a declared zero, a group may be
``None`` to mean a group the source never had, and a group that is present but
has no chosen battery row is an unfinished input rather than an empty group.
"""

from __future__ import annotations

import copy
import json
import math
import struct
import re

try:
    from . import battery_armour as siblings
    from . import concept_estimates as kernels
except ImportError:                                   # pragma: no cover - direct import
    import battery_armour as siblings
    import concept_estimates as kernels

METHOD_VERSION = "sps-3b3-battery-layout-v1"
ARMOUR_METHOD_VERSION = "sps-3b3-battery-armour-v2"
SOURCE_LOCATION = "GunControl.cs:564-758, 908-1096, 1127-1292; FreeboardControl.cs:471-472"
SOURCE_ASSEMBLY = siblings.SOURCE_ASSEMBLY
SOURCE_SHA256 = siblings.SOURCE_SHA256
SOURCE_SCOPE = (
    "Independent empirical reading of a two-group battery layout identity, its "
    "position-weighted deck freeboard, its superstructure height factor and its "
    "complete two-group gun-house and barbette armour, reproduced from the "
    "recovered 3b3 mountsCalc, freeGunCalc, armWeightCalc and diameterCalc "
    "expressions; not a form, not a centre of gravity, not developed armour "
    "geometry, not structural strength, not whole-program parity and not "
    "validated against any real ship."
)
ARMOUR_SOURCE_SCOPE = (
    "Independent empirical estimate of the COMPLETE gun-house and barbette armour "
    "of one two-group battery layout, read from the recovered 3b3 armWeightCalc "
    "expression with both recovered diameter classes and both mount counts; it is "
    "not the sum of two single-group estimates, not armour geometry "
    "reconstruction, not structural strength, not whole-program parity and not "
    "validated against any real ship. The per-group gun, mount and ammunition "
    "estimates stay sps-3b3-adapted-v1 per row and no whole-battery mount mass is "
    "claimed from them."
)

# MainForm.cs:22, re-exported so the empirical constant has one definition.
EMPIRICAL_MASS_CONSTANT = siblings.EMPIRICAL_MASS_CONSTANT
MM_PER_INCH = siblings.MM_PER_INCH
M_PER_FT = kernels.M_PER_FT

GUN_TYPES = siblings.GUN_TYPES
MOUNT_TYPES = siblings.MOUNT_TYPES
MOUNT_ADJUSTMENT = siblings.MOUNT_ADJUSTMENT
MAX_MOUNTS = siblings.MAX_MOUNTS
MAX_BARRELS_PER_MOUNT = kernels.MAX_BARRELS_PER_MOUNT
MIN_YEAR = kernels.MIN_YEAR
MAX_YEAR = kernels.MAX_YEAR
MAX_CALIBRE_MM = siblings.MAX_CALIBRE_MM
MAX_THICKNESS_MM = siblings.MAX_THICKNESS_MM
MAX_FREEBOARD_M = siblings.MAX_FREEBOARD_M
MAX_SUPER_FACTOR = siblings.MAX_SUPER_FACTOR

# GunControl.cs:636 perMountCalc, the fifteen recovered gunsInMount selectors.
PER_MOUNT_BY_SELECTOR = (1, 2, 4, 2, 2, 4, 3, 3, 6, 4, 4, 8, 5, 5, 10)
# GunControl.cs:480 weightAdjCalc, the four shared-cradle selectors.
SHARED_CRADLE_SELECTORS = frozenset({3, 6, 9, 12})
# GunControl.cs:1238 diameterCalc, keyed by the same selector.
DIAMETER_CLASS_BY_SELECTOR = siblings.DIAMETER_CLASS_BY_SELECTOR
WEIGHT_ADJUSTMENT_BY_SELECTOR = siblings.WEIGHT_ADJUSTMENT_BY_SELECTOR
# GunControl.cs:1106-1220 the barbette coefficient per mount class.
BARBETTE_COEFFICIENT = siblings.BARBETTE_COEFFICIENT

MOUNT_INDEX_BROADSIDE = siblings.MOUNT_INDEX_BROADSIDE
MOUNT_INDEX_COLES = siblings.MOUNT_INDEX_COLES
MOUNT_INDEX_OPEN_BARBETTE = siblings.MOUNT_INDEX_OPEN_BARBETTE
MOUNT_INDEX_CASEMATE = siblings.MOUNT_INDEX_CASEMATE
GUN_INDEX_ANTI_AIR = siblings.GUN_INDEX_ANTI_AIR
GUN_INDEX_MACHINE_GUN = siblings.GUN_INDEX_MACHINE_GUN
GUN_HOUSE_MIN_FT = siblings.GUN_HOUSE_MIN_FT
GUN_HOUSE_PER_CALIBRE = siblings.GUN_HOUSE_PER_CALIBRE
GUN_HOUSE_COLE_DOUBLING = siblings.GUN_HOUSE_COLE_DOUBLING
ANTI_AIR_FACE_FACTOR = siblings.ANTI_AIR_FACE_FACTOR
SMALL_CALIBRE_INCHES = siblings.SMALL_CALIBRE_INCHES
LARGE_CALIBRE_INCHES = siblings.LARGE_CALIBRE_INCHES
SHARED_CRADLE_DIAMETER_FACTOR = siblings.SHARED_CRADLE_DIAMETER_FACTOR
BARBETTE_CALIBRE_EXPONENT = siblings.BARBETTE_CALIBRE_EXPONENT
BARBETTE_FREEBOARD_DIVISOR = siblings.BARBETTE_FREEBOARD_DIVISOR
BARBETTE_CALIBRE_TOTAL = siblings.BARBETTE_CALIBRE_TOTAL
BARBETTE_PER_MOUNT_CAP = siblings.BARBETTE_PER_MOUNT_CAP

# The recovered combo names, kept so a form can offer the original's own
# selectors instead of a number. They are labels, never parsed.
MOUNT_SELECTOR_NAMES = (
    "Single mount", "2 row twin mount", "4 row quad mount", "Twin mount",
    "2-gun mount", "2 row quad mount", "Triple mount", "3-gun mount",
    "2 row sextuple mount", "Quad mount", "4-gun mount", "2 row octuple mount",
    "Quintuple mount", "5-gun mount", "2 row decuple mount",
)
LAYOUT_NAMES = (
    "Centreline - distributed", "Centreline - ends (fore >= aft)",
    "Centreline - ends (aft >= fore)", "Centreline - fore deck forward",
    "Centreline - fore deck", "Centreline - fore deck aft",
    "Centreline - aft deck forward", "Centreline - aft deck",
    "Centreline - aft deck aft", "Sides - distributed",
    "Sides - ends (fore >= aft)", "Sides - ends (aft >= fore)",
    "Sides - fore deck forward", "Sides - fore deck", "Sides - fore deck aft",
    "Sides - aft deck forward", "Sides - aft deck", "Sides - aft deck aft",
    "None",
)
SELECTOR_COUNT = len(PER_MOUNT_BY_SELECTOR)
LAYOUT_COUNT = len(LAYOUT_NAMES) - 1
# The recovered combo's own "None" entry. It is a real saved selection that means
# *no layout*, never a default that is inferred as layout 0.
LAYOUT_NOT_SET = LAYOUT_COUNT

MAX_LAYOUTS = 50
MAX_LAYER_COUNT = 1000
MAX_GROUP_MOUNTS = 1000
MAX_TOTAL_MOUNTS = 1000
MAX_TOTAL_BARRELS = 10000
ID_PATTERN = re.compile(r"\A[A-Za-z0-9_.-]{1,80}\Z")

LAYOUT_FIELDS = ("id", "source", "group1", "group2", "group2_double_elevation",
                 "group2_double_depression", "deck_profile", "armour")
GROUP_FIELDS = ("battery_id", "mount_selector", "layout_index", "elevated_mounts",
                "deck_mounts", "depressed_mounts")
DECK_PROFILE_FIELDS = ("forecastle_fraction", "forward_deck_fraction", "forward_fore_m",
                       "forward_aft_m", "aft_fore_m", "aft_aft_m")
LAYOUT_ARMOUR_FIELDS = ("system_id", "item_id", "face_mm", "rear_roof_mm", "barbette_mm")
# The rows a group reads its identity from. The recovered layout never restates
# them: a group references an existing battery row.
BATTERY_FACT_FIELDS = ("calibre_mm", "year", "gun_type", "mount_type", "mount_count",
                       "barrels_per_mount", "shared_cradle")

ASSUMPTIONS = (
    "each group references an existing battery row and keeps its own recovered "
    "gunsInMount selector and eighteen-way layout reading; the two groups are "
    "never averaged into one group and never merged",
    "the recovered gunsInMount selector is the authority for the per-mount "
    "diameter class, the recovered per-mount barrel count and the shared-cradle "
    "weight adjustment, so a two-row selector and a single-row selector of the "
    "same barrel count stay geometrically distinct instead of being "
    "reverse-derived from the barrel count alone",
    "the referenced row supplies calibre, year, gun class, mount class, mount "
    "count, barrels per mount and shared cradle; a declared selector that "
    "disagrees with that row is refused, not preferred",
    "Math.Round(mounts * 0.5, 0) is ties to even; an odd count does not always "
    "put its extra mount on the same side, unlike a floor or a ceiling",
    "layouts 0 and 9 read whether the forecastle and forward-deck fractions "
    "together reach 0.5, and a flush deck moves their single mount from the "
    "forward deck to the aft deck",
    "the two groups' position-weighted freeboard is combined by mount count and "
    "the height factor counts barrels in the elevated and depressed groups; "
    "neither substitutes for the other",
    "the deck profile is an empirical deck parameter read in metres; it is not a "
    "hull form, it creates no geometry, and no centre of gravity is assigned",
    "the recovered expression reads the position-weighted freeboard in FEET; "
    "freeboard_m is declared and returned in metres and converted exactly once",
    "the source's integer division of the two groups' per-mount barrel counts is "
    "kept, and above a 0.5 mount adjustment the average is capped at four while "
    "at or below 0.5 only perMountG1 is written, so perMounts itself reaches the "
    "barbette expression uncapped",
    "the barbette coefficient appears twice in its own expression and the "
    "barbette year factor is the fourth root of the recovered date adjustment",
    "a negative derived armour component, a non-finite result and a division by "
    "zero produce an unavailable diagnostic; nothing is clamped, floored or "
    "replaced by an invented minimum",
    "a barbette is fixed structure and not a rotating structure, so this mass "
    "belongs to its own design role and is not part of the mount item",
)


class LayoutValidationError(ValueError):
    """Report a refused layout declaration with structured diagnostics."""

    def __init__(self, diagnostics):
        self.diagnostics = copy.deepcopy(diagnostics)
        super().__init__("; ".join(d["message"] for d in diagnostics if d.get("blocking", True)))


class _Unknown:
    """A declared input that was not supplied. Never zero."""

    __slots__ = ()

    def __repr__(self):                                 # pragma: no cover - debugging aid
        return "<unknown>"


UNKNOWN = _Unknown()


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


def _round_half_even(value):
    """``Math.Round(value, 0)`` — the recovered midpoint rule is ties to even."""
    return float(round(value))


# ------------------------------------------------------------- declaration --

def _optional_string(raw, field, path, diagnostics, values=None):
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        diagnostics.append(_diag("battery_layout.invalid", "must be a non-empty string",
                                 path + "." + field, field))
        return None
    if values is not None and value not in values:
        diagnostics.append(_diag("battery_layout.reference_unknown",
                                 "must name a declared %s" % (", ".join(sorted(values)),),
                                 path + "." + field, field))
        return None
    return value


def _optional_int(raw, field, path, diagnostics, low, high):
    value = raw.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        diagnostics.append(_diag("battery_layout.invalid", "must be an integer",
                                 path + "." + field, field))
        return None
    if value < low or value > high:
        diagnostics.append(_diag("battery_layout.domain",
                                 "must be an integer in [%d, %d]" % (low, high),
                                 path + "." + field, field))
        return None
    return int(value)


def _optional_number(raw, field, path, diagnostics, *, low=None, high=None):
    value = raw.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        diagnostics.append(_diag("battery_layout.invalid", "must be a finite number",
                                 path + "." + field, field))
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        diagnostics.append(_diag("battery_layout.invalid",
                                 "exceeds the supported numeric range", path + "." + field, field))
        return None
    if not math.isfinite(number):
        diagnostics.append(_diag("battery_layout.invalid", "must be a finite number",
                                 path + "." + field, field))
        return None
    if low is not None and number < low:
        diagnostics.append(_diag("battery_layout.domain", "must be >= %r" % (low,),
                                 path + "." + field, field))
        return None
    if high is not None and number > high:
        diagnostics.append(_diag("battery_layout.domain", "must be <= %r" % (high,),
                                 path + "." + field, field))
        return None
    return number


def _optional_flag(raw, field, path, diagnostics):
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, bool):
        diagnostics.append(_diag("battery_layout.invalid", "must be a boolean or null",
                                 path + "." + field, field))
        return None
    return value


def _object(raw, path, diagnostics, allowed):
    if not isinstance(raw, dict):
        diagnostics.append(_diag("battery_layout.invalid", "must be an object or null", path))
        return False
    for key in sorted(set(raw) - set(allowed)):
        diagnostics.append(_diag("battery_layout.unsupported_field",
                                 "unsupported field %r" % (key,), path + "." + key))
    return True


def _deck_profile(raw, path, diagnostics):
    if raw is None:
        return None
    if not _object(raw, path, diagnostics, DECK_PROFILE_FIELDS):
        return None
    profile = {
        "forecastle_fraction": _optional_number(raw, "forecastle_fraction", path, diagnostics,
                                                low=0.0, high=1.0),
        "forward_deck_fraction": _optional_number(raw, "forward_deck_fraction", path, diagnostics,
                                                 low=0.0, high=1.0),
    }
    for field in ("forward_fore_m", "forward_aft_m", "aft_fore_m", "aft_aft_m"):
        profile[field] = _optional_number(raw, field, path, diagnostics, low=0.0,
                                          high=MAX_FREEBOARD_M)
    fore = [profile["forecastle_fraction"], profile["forward_deck_fraction"]]
    if all(value is not None for value in fore) and sum(fore) > 1.0:
        diagnostics.append(_diag(
            "battery_layout.domain",
            "the forecastle and forward-deck fractions together must not exceed 1; they "
            "are refused, not clamped", path, "forecastle_fraction"))
    return profile


def _layout_armour(raw, path, diagnostics):
    if raw is None:
        return None
    if not _object(raw, path, diagnostics, LAYOUT_ARMOUR_FIELDS):
        return None
    return {
        "system_id": _optional_string(raw, "system_id", path, diagnostics),
        "item_id": _optional_string(raw, "item_id", path, diagnostics),
        "face_mm": _optional_number(raw, "face_mm", path, diagnostics, low=0.0,
                                    high=MAX_THICKNESS_MM),
        "rear_roof_mm": _optional_number(raw, "rear_roof_mm", path, diagnostics, low=0.0,
                                         high=MAX_THICKNESS_MM),
        "barbette_mm": _optional_number(raw, "barbette_mm", path, diagnostics, low=0.0,
                                        high=MAX_THICKNESS_MM),
    }


def _normalize_group(raw, path, diagnostics, known_ids):
    return {
        "battery_id": _optional_string(raw, "battery_id", path, diagnostics, values=known_ids),
        "mount_selector": _optional_int(raw, "mount_selector", path, diagnostics, 0,
                                        SELECTOR_COUNT - 1),
        "layout_index": _optional_int(raw, "layout_index", path, diagnostics, 0, LAYOUT_COUNT - 1),
        "elevated_mounts": _optional_int(raw, "elevated_mounts", path, diagnostics, 0,
                                         MAX_LAYER_COUNT),
        "deck_mounts": _optional_int(raw, "deck_mounts", path, diagnostics, 0, MAX_LAYER_COUNT),
        "depressed_mounts": _optional_int(raw, "depressed_mounts", path, diagnostics, 0,
                                          MAX_LAYER_COUNT),
    }


def _battery_index(batteries):
    """The declared battery rows a layout may reference."""
    index = {}
    for battery in batteries or ():
        if not isinstance(battery, dict):
            continue
        identifier = battery.get("id")
        if isinstance(identifier, str) and identifier and identifier not in index:
            index[identifier] = battery
    return index


def validate_layouts(raw, batteries, path="$.concept_design.battery_layouts"):
    """Validate the optional ``battery_layouts`` array into normalized layouts.

    Returns the canonical list. A wrong type, an out-of-range number, an unknown
    reference and a contradiction between two simultaneously known declared facts
    are refused with :class:`LayoutValidationError`; an unfinished declaration
    stays saveable and simply has no reading.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise LayoutValidationError(
            [_diag("battery_layout.invalid", "must be an array or null", path)])
    if len(raw) > MAX_LAYOUTS:
        raise LayoutValidationError([_diag(
            "battery_layout.domain", "at most %d layouts may be declared" % (MAX_LAYOUTS,), path)])
    index = _battery_index(batteries)
    layouts = []
    claimed_rows = {}
    diagnostics = []
    for position, entry in enumerate(raw):
        lpath = "%s[%d]" % (path, position)
        if not _object(entry, lpath, diagnostics, LAYOUT_FIELDS):
            continue
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not ID_PATTERN.match(identifier):
            diagnostics.append(_diag(
                "battery_layout.invalid",
                "must be 1..80 characters of ASCII letters, digits, underscore, dot or "
                "hyphen", lpath + ".id", "id"))
            identifier = None
        elif any(layout["id"] == identifier for layout in layouts):
            diagnostics.append(_diag("battery_layout.duplicate", "layout IDs must be unique",
                                     lpath + ".id", "id"))
            identifier = None
        layout = {
            "id": identifier,
            "source": _optional_string(entry, "source", lpath, diagnostics),
            "group1": None, "group2": None,
            "group2_double_elevation": _optional_flag(entry, "group2_double_elevation", lpath,
                                                      diagnostics),
            "group2_double_depression": _optional_flag(entry, "group2_double_depression", lpath,
                                                       diagnostics),
            "deck_profile": _deck_profile(entry.get("deck_profile"), lpath + ".deck_profile",
                                          diagnostics),
            "armour": _layout_armour(entry.get("armour"), lpath + ".armour", diagnostics),
        }
        for field in ("group1", "group2"):
            raw_group = entry.get(field)
            gpath = "%s.%s" % (lpath, field)
            if raw_group is not None and _object(raw_group, gpath, diagnostics, GROUP_FIELDS):
                layout[field] = _normalize_group(raw_group, gpath, diagnostics, index)
        _check_layout(layout, index, lpath, diagnostics, claimed_rows)
        layouts.append(layout)
    if diagnostics:
        raise LayoutValidationError(diagnostics)
    return layouts


def _check_layout(layout, index, path, diagnostics, claimed_rows):
    """Refuse only simultaneous contradictions; unknown never blocks a draft."""
    resolved = {}
    for field in ("group1", "group2"):
        group = layout[field]
        gpath = "%s.%s" % (path, field)
        if group is None:
            resolved[field] = (None, None)
            continue
        battery_id = group["battery_id"]
        if battery_id is None:
            resolved[field] = (group, None)
            continue
        battery = index.get(battery_id)
        if battery is None:
            diagnostics.append(_diag("battery_layout.reference_unknown",
                                     "must name an existing concept_design battery row",
                                     gpath + ".battery_id", "battery_id"))
            resolved[field] = (group, None)
            continue
        owner = claimed_rows.get(battery_id)
        if owner is not None:
            diagnostics.append(_diag(
                "battery_layout.reference_conflict",
                "battery %r is already referenced by layout %r; one battery row belongs "
                "to one layout" % (battery_id, owner), gpath + ".battery_id", "battery_id"))
        else:
            claimed_rows[battery_id] = path
        _check_group_facts(group, battery, gpath, diagnostics)
        resolved[field] = (group, battery)
    first = resolved["group1"]
    second = resolved["group2"]
    if first[0] is not None and second[0] is not None:
        if first[0]["battery_id"] is not None and first[0]["battery_id"] == second[0]["battery_id"]:
            diagnostics.append(_diag(
                "battery_layout.reference_conflict",
                "one layout must not reference the same battery row twice",
                "%s.group2.battery_id" % (path,), "battery_id"))
    seen = {}
    for field in ("group1", "group2"):
        group, battery = resolved[field]
        if group is None or battery is None or battery.get("mount_count") == 0:
            continue
        for fact in ("calibre_mm", "year", "gun_type", "mount_type"):
            value = battery.get(fact)
            if value is None:
                continue
            previous = seen.get(fact)
            if previous is not None and previous[1] != value:
                diagnostics.append(_diag(
                    "battery_layout.domain",
                    "%s of %s is %r but %s declares %r; two groups of one layout must "
                    "agree when both are known"
                    % (fact, previous[0], previous[1], field, value),
                    "%s.%s.battery_id" % (path, field), fact))
            else:
                seen[fact] = (field, value)
    def count(battery, key):
        value = battery.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0
    mount_total = sum(count(b, "mount_count") for _, b in resolved.values() if b)
    barrel_total = sum(count(b, "mount_count") * count(b, "barrels_per_mount")
                       for _, b in resolved.values() if b)
    if mount_total > MAX_TOTAL_MOUNTS or barrel_total > MAX_TOTAL_BARRELS:
        diagnostics.append(_diag("battery_layout.domain", "two-group total exceeds the supported count limit", path))


def _check_group_facts(group, battery, path, diagnostics):
    mounts = _optional_int(battery, "mount_count", path, diagnostics, 0, MAX_MOUNTS)
    if battery.get("mount_count") is not None and mounts is None:
        return
    counts = [group["elevated_mounts"], group["deck_mounts"], group["depressed_mounts"]]
    declared = sum(counts) if all(count is not None for count in counts) else None
    partial = sum(value for value in counts if value is not None)
    if mounts is not None and (partial > mounts or (declared is not None and declared != mounts)):
        diagnostics.append(_diag(
            "battery_layout.domain",
            "the elevated, deck and depressed mounts total %s but the referenced battery "
            "declares %s mounts; they are refused, not reconciled" % (declared, mounts),
            path + ".deck_mounts", "deck_mounts"))
    if mounts == 0:
        return
    _optional_int(battery, "barrels_per_mount", path, diagnostics, 1, MAX_BARRELS_PER_MOUNT)
    _optional_int(battery, "year", path, diagnostics, MIN_YEAR, MAX_YEAR)
    _optional_flag(battery, "shared_cradle", path, diagnostics)
    calibre = _optional_number(battery, "calibre_mm", path, diagnostics, low=0, high=MAX_CALIBRE_MM)
    if calibre == 0:
        diagnostics.append(_diag("battery_layout.domain", "calibre must be positive", path + ".calibre_mm"))
    _optional_string(battery, "gun_type", path, diagnostics, values=GUN_TYPES)
    _optional_string(battery, "mount_type", path, diagnostics, values=MOUNT_TYPES)
    per_mount = battery.get("barrels_per_mount")
    selector = group["mount_selector"]
    if selector is not None and per_mount is not None and PER_MOUNT_BY_SELECTOR[selector] != per_mount:
        diagnostics.append(_diag(
            "battery_layout.domain",
            "the recovered gunsInMount selector %d carries %d barrels per mount but the "
            "referenced battery declares %s; the selector and the row must agree"
            % (selector, PER_MOUNT_BY_SELECTOR[selector], per_mount),
            path + ".mount_selector", "mount_selector"))
    cradle = battery.get("shared_cradle")
    if selector is not None and cradle is not None:
        if (selector in SHARED_CRADLE_SELECTORS) != bool(cradle):
            diagnostics.append(_diag(
                "battery_layout.domain",
                "the recovered gunsInMount selector %d %s a shared cradle but the referenced "
                "battery declares shared_cradle %r"
                % (selector, "declares" if selector in SHARED_CRADLE_SELECTORS
                   else "does not declare", cradle),
                path + ".mount_selector", "mount_selector"))


# ------------------------------------------------------------------ reading

def _fact(battery, name):
    if battery is None:
        return None
    value = battery.get(name)
    if isinstance(value, bool):
        return None
    return value


def mounts_for(layout_index, mounts, fore_length_reaches_half):
    """GunControl.cs:680-695, the recovered ``mountsFor`` branches."""
    centre_distributed = layout_index in (0, 9)
    forward_reaches = centre_distributed and fore_length_reaches_half
    if ((forward_reaches and mounts == 1) or (layout_index in (1, 10) and mounts == 1)
            or 2 < layout_index < 6 or 11 < layout_index < 15):
        return float(mounts)
    if forward_reaches or layout_index in (1, 10):
        return _round_half_even(mounts * 0.5)
    if ((centre_distributed and not fore_length_reaches_half and mounts == 1)
            or (layout_index in (2, 11) and mounts == 1)
            or 5 < layout_index < 9 or layout_index > 14):
        return 0.0
    return float(mounts) - _round_half_even(mounts * 0.5)


def _deck_midpoints(profile):
    """FreeboardControl.cs:471-472, the two recovered deck midpoints."""
    forward = (profile["forward_fore_m"]
               + (profile["forward_aft_m"] - profile["forward_fore_m"]) * 0.5)
    aft = profile["aft_fore_m"] + (profile["aft_aft_m"] - profile["aft_fore_m"]) * 0.5
    return forward, aft


def free_gun_m(layout_index, mounts, profile):
    """GunControl.cs:696-757 ``freeGunCalc``, declared and returned in metres.

    The recovered expression is written in feet; the deck profile is declared in
    metres, so no unit conversion happens inside this function at all.
    """
    if mounts <= 0:
        return 0.0
    try:
        reaches_half = False
        if layout_index in (0, 9):
            reaches_half = _fore_reaches_half(profile)
        placed = mounts_for(layout_index, mounts, reaches_half)
        rest = mounts - placed
        def midpoint(prefix):
            return (profile[prefix + "_fore_m"] + profile[prefix + "_aft_m"]) / 2
        def end(prefix, which, count):
            mid = midpoint(prefix)
            value = profile[prefix + "_" + which + "_m"]
            return (value - mid) / count * .5 + (value + mid) * .5
        if layout_index in (0, 9):
            return ((midpoint("forward") * placed if placed else 0)
                    + (midpoint("aft") * rest if rest else 0)) / mounts
        if layout_index in (1, 2, 10, 11):
            return ((placed * end("forward", "fore", placed) if placed else 0)
                    + (rest * end("aft", "aft", rest) if rest else 0)) / mounts
        if layout_index in (3, 12):
            return end("forward", "fore", placed) if placed else 0.0
        if layout_index in (4, 13):
            return midpoint("forward")
        if layout_index in (5, 14):
            return end("forward", "aft", placed) if placed else 0.0
        if layout_index in (6, 15):
            return end("aft", "fore", rest) if rest else 0.0
        if layout_index in (7, 16):
            return midpoint("aft")
        if layout_index in (8, 17):
            return end("aft", "aft", rest) if rest else 0.0
    except (KeyError, TypeError, ArithmeticError, ValueError, struct.error):
        return None
    return None


def _fore_reaches_half(profile):
    """The original adds two Single fields before its >=0.5 comparison."""
    single = lambda value: struct.unpack("f", struct.pack("f", value))[0]
    return single(single(profile["forecastle_fraction"])
                  + single(profile["forward_deck_fraction"])) >= .5


def _empty_group_reading():
    return {"battery_id": None, "state": "absent", "mount_selector": None,
            "layout_index": None, "elevated_mounts": 0, "deck_mounts": 0,
            "depressed_mounts": 0, "mounts": 0, "barrels_per_mount": 0,
            "barrels": 0, "per_mount": 0, "weight_adjustment": 1,
            "diameter_ft": None, "mounts_for": 0, "freeboard_m": 0.0}


def _group_reading(group, battery, path, diagnostics):
    """Resolve one group against its referenced row, without inventing anything."""
    reading = _empty_group_reading()
    if group is None:
        # A null group is a group the source never had. It contributes nothing and
        # needs no selector, layout, shared fact or doubled flag.
        return reading
    reading["battery_id"] = group.get("battery_id")
    reading["mount_selector"] = group.get("mount_selector")
    layout_index = group.get("layout_index")
    reading["layout_index"] = (None if layout_index is None or layout_index == LAYOUT_NOT_SET
                               else layout_index)
    reading["elevated_mounts"] = group.get("elevated_mounts")
    reading["deck_mounts"] = group.get("deck_mounts")
    reading["depressed_mounts"] = group.get("depressed_mounts")
    if battery is None:
        # An object with no chosen row is an unfinished input, not an empty group.
        reading["state"] = "unfinished"
        reading.update(mounts=None, barrels=None, per_mount=None, freeboard_m=None)
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "battery_id", "%s.battery_id" % (path,),
            "this group has no referenced battery row, so its mount count, calibre and "
            "per-mount barrel count are unknown; it is not read as an empty group"))
        return reading
    mounts = _fact(battery, "mount_count")
    per_mount = _fact(battery, "barrels_per_mount")
    if mounts == 0:
        reading.update(state="empty", mounts=0, barrels=0, per_mount=0, freeboard_m=0.0)
        return reading
    if mounts is None or per_mount is None:
        reading["state"] = "unknown_facts"
        reading.update(mounts=mounts, barrels=None, per_mount=None, freeboard_m=None)
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "mount_count", "%s.battery_id" % (path,),
            "the referenced battery row does not declare both its mount count and its "
            "barrels per mount, so this group has no derived mount count"))
        return reading
    mounts = int(mounts)
    per_mount = int(per_mount)
    reading["mounts"] = mounts
    reading["barrels_per_mount"] = per_mount
    reading["barrels"] = mounts * per_mount
    selector = reading["mount_selector"]
    if selector is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "mount_selector", "%s.mount_selector" % (path,),
            "the recovered gunsInMount selector is unknown, so the diameter class, the "
            "weight adjustment and the per-mount barrel identity stay unknown; they are "
            "not reverse-derived from the barrels per mount alone"))
    else:
        reading["per_mount"] = PER_MOUNT_BY_SELECTOR[selector]
        reading["weight_adjustment"] = WEIGHT_ADJUSTMENT_BY_SELECTOR[selector]
    reading["state"] = "declared"
    return reading


def _group_freeboard(reading, profile, path, diagnostics):
    """One group's own position-weighted freeboard reading."""
    mounts = reading["mounts"]
    if mounts is None:
        return None
    if mounts == 0:
        # The recovered expression skips its own switch and returns a zero.
        return 0.0
    if reading["layout_index"] is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "layout_index", path + ".layout_index",
            "the recovered eighteen-way layout reading of this group is unknown, so its "
            "position-weighted freeboard is unknown; it is not inferred as layout 0"))
        return None
    value = None if profile is None else free_gun_m(reading["layout_index"], mounts, profile)
    if value is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "deck_profile", path + ".deck_profile",
            "the deck profile or one of its four freeboard readings is unknown, so the "
            "position-weighted freeboard is unknown"))
        return None
    fractions = [profile.get(k) for k in ("forecastle_fraction", "forward_deck_fraction")]
    if reading["layout_index"] not in (0, 9) or all(x is not None for x in fractions):
        reading["mounts_for"] = mounts_for(reading["layout_index"], mounts,
                                           _fore_reaches_half(profile) if reading["layout_index"] in (0, 9) else False)
    return value


def _barrel_counts(reading):
    """The recovered per-mount count and the elevated/depressed mounts of a group."""
    if reading["mounts"] is None:
        return None, None, None
    if reading["mounts"] == 0:
        # GunControl.cs:1139-1146 zeroes the recovered per-mount count of an empty
        # group, so an empty group never enters the integer average.
        return 0, 0, 0
    if reading["per_mount"] is None:
        return None, None, None
    return reading["per_mount"], reading["elevated_mounts"], reading["depressed_mounts"]


def _doubled(layout, field, group_two_mounts, path, diagnostics):
    """GunControl.cs:604-618: an unknown checkbox is unknown, never unchecked."""
    if not group_two_mounts:
        # Nothing for the flag to weight, so an unknown flag cannot change it.
        return 1
    flag = layout.get(field)
    if flag is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", field, "%s.%s" % (path, field),
            "group 2 carries %d mounts of this kind, so the recovered doubled flag is "
            "needed and an unknown flag is not read as unchecked" % (group_two_mounts,)))
        return None
    return 2 if flag else 1


def _height_factor(layout, groups, calibre_mm, freeboard_m, barrels, path, diagnostics):
    """GunControl.cs:604-628, the recovered superstructure height factor."""
    if barrels == 0:
        # The source's own empty-battery branch, returned as a determined value
        # instead of the stale field a form would keep.
        return 1.0
    if freeboard_m is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "freeboard_m", path,
            "the height factor reads the position-weighted freeboard, which is unknown"))
        return None
    if freeboard_m <= 0.0:
        diagnostics.append(_unavailable(
            "battery_layout.unavailable", "freeboard_m", path,
            "the recovered height factor divides by the position-weighted freeboard, so a "
            "determined zero freeboard leaves it undefined; it is reported, not clamped"))
        return None
    if calibre_mm is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "calibre_mm", path,
            "the height factor reads the recovered calibre, which is unknown"))
        return None
    first = groups["group1"]
    second = groups["group2"]
    per_mount_1, elevated_1, depressed_1 = _barrel_counts(first)
    per_mount_2, elevated_2, depressed_2 = _barrel_counts(second)
    for name, reading, per_mount, elevated, depressed in (
            ("group1", first, per_mount_1, elevated_1, depressed_1),
            ("group2", second, per_mount_2, elevated_2, depressed_2)):
        if per_mount is None:
            diagnostics.append(_unavailable(
                "battery_layout.unknown", "mount_selector",
                "%s.%s.mount_selector" % (path, name),
                "the height factor counts this group's barrels through its recovered "
                "gunsInMount selector, which is unknown"))
            return None
        if elevated is None or depressed is None:
            diagnostics.append(_unavailable(
                "battery_layout.unknown", "elevated_mounts", "%s.%s" % (path, name),
                "the height factor counts the group's elevated and depressed mounts, and "
                "at least one of them is unknown"))
            return None
        del reading
    doubled_elevated = _doubled(layout, "group2_double_elevation", elevated_2, path, diagnostics)
    doubled_depressed = _doubled(layout, "group2_double_depression", depressed_2, path,
                                 diagnostics)
    if doubled_elevated is None or doubled_depressed is None:
        return None
    ratio = (elevated_1 * per_mount_1 + elevated_2 * per_mount_2 * doubled_elevated
             - depressed_1 * per_mount_1 - depressed_2 * per_mount_2 * doubled_depressed) / barrels
    calibre_in = calibre_mm / MM_PER_INCH
    freeboard_ft = freeboard_m / M_PER_FT
    try:
        return _finite((ratio * max(GUN_HOUSE_MIN_FT, calibre_in * 0.6) + freeboard_ft)
                       / freeboard_ft, path + ".super_factor")
    except (ArithmeticError, ValueError) as error:
        diagnostics.append(_unavailable(
            "battery_layout.unavailable", "super_factor", path,
            "the recovered height factor cannot be evaluated as a finite real number: %s"
            % (error,)))
        return None


# --------------------------------------------------------------- the armour

def _diameter_ft(calibre_in, selector, weight_adjustment):
    """GunControl.cs:1238-1292 ``diameterCalc`` for one group's selector."""
    num, num2 = DIAMETER_CLASS_BY_SELECTOR[selector]
    diameter = num * calibre_in * (1.0 + (1.0 / calibre_in) ** num2)
    if calibre_in < SMALL_CALIBRE_INCHES:
        diameter += SMALL_CALIBRE_INCHES / calibre_in
    if calibre_in > LARGE_CALIBRE_INCHES and weight_adjustment < 1.0:
        diameter *= SHARED_CRADLE_DIAMETER_FACTOR
    return diameter


def _gun_house_height_ft(calibre_in, mount_index):
    """GunControl.cs:1131-1138."""
    if mount_index == MOUNT_INDEX_COLES:
        return max(GUN_HOUSE_MIN_FT,
                   GUN_HOUSE_PER_CALIBRE * calibre_in * GUN_HOUSE_COLE_DOUBLING)
    return max(GUN_HOUSE_MIN_FT, GUN_HOUSE_PER_CALIBRE * calibre_in)


def _face_coefficient(mount_index, rear_is_zero):
    """GunControl.cs:1149-1168. Returns ``(coefficient, reads_rear_thickness)``."""
    if mount_index in (MOUNT_INDEX_BROADSIDE, MOUNT_INDEX_CASEMATE):
        return 1.0, False
    if mount_index == MOUNT_INDEX_COLES:
        return math.pi / 2.0, False
    if mount_index == MOUNT_INDEX_OPEN_BARBETTE:
        return 0.0, False
    return (1.5 if rear_is_zero else 0.5), True


def _face_reduced_by_gun_type(gun_index, rear_is_zero):
    """GunControl.cs:1170-1173. Returns ``(factor, reads_rear_thickness)``."""
    if gun_index == GUN_INDEX_ANTI_AIR:
        return ANTI_AIR_FACE_FACTOR, False
    if gun_index == GUN_INDEX_MACHINE_GUN:
        # The recovered condition is (gunType == 6 && armBack == 0), so this one gun
        # class genuinely reads whether the side/roof thickness is a zero.
        return (ANTI_AIR_FACE_FACTOR, True) if rear_is_zero else (1.0, True)
    return 1.0, False


def _rear_coefficient(mount_index):
    """GunControl.cs:1174-1176: the side/roof area term before the thickness."""
    return 2.5 if 2 < mount_index < 6 else 0.0


def _per_mounts_average(readings, mount_index):
    """GunControl.cs:1194-1205, the recovered integer average of two groups.

    Returns ``{"per_mounts", "barbette_per_mounts", "per_mount_g1_after"}``. Above
    a 0.5 mount adjustment the average itself is capped at four; at or below 0.5
    the source writes ``perMountG1`` instead of ``perMounts``, so the average
    reaches the barbette expression uncapped. That write is kept, not corrected.
    """
    weighted = 0
    mounts_total = 0
    for reading in readings:
        if reading["mounts"] is None:
            return {"per_mounts": None, "barbette_per_mounts": None, "per_mount_g1_after": None}
        if reading["mounts"] == 0:
            continue
        if reading["per_mount"] is None:
            return {"per_mounts": None, "barbette_per_mounts": None, "per_mount_g1_after": None}
        weighted += reading["per_mount"] * reading["mounts"]
        mounts_total += reading["mounts"]
    if mounts_total == 0:
        return {"per_mounts": 0, "barbette_per_mounts": 0, "per_mount_g1_after": 0}
    per_mounts = weighted // mounts_total
    if MOUNT_ADJUSTMENT[mount_index] > 0.5:
        return {"per_mounts": per_mounts,
                "barbette_per_mounts": min(BARBETTE_PER_MOUNT_CAP, per_mounts),
                "per_mount_g1_after": None}
    return {"per_mounts": per_mounts, "barbette_per_mounts": per_mounts,
            "per_mount_g1_after": min(5, per_mounts)}


def _empty_armour_values():
    return {
        "status": "unavailable", "mounts_group1": None, "mounts_group2": None,
        "barrels": None, "diameter_g1_ft": None, "diameter_g2_ft": None,
        "gun_house_height_ft": None, "guns_in_mount_selector_g1": None,
        "guns_in_mount_selector_g2": None, "shared_cradle_weight_adjustment_g1": None,
        "shared_cradle_weight_adjustment_g2": None, "per_mounts": None,
        "barbette_per_mounts": None, "per_mount_g1_after": None, "mount_adjustment": None,
        "face_mm": None, "rear_roof_mm": None, "barbette_mm": None, "face_in": None,
        "rear_roof_in": None, "barbette_in": None, "face_coefficient": None,
        "face_gun_type_factor": None, "rear_roof_coefficient": None,
        "barbette_coefficient": None, "freeboard_ft": None, "date_factor": None,
        "barbette_date_factor": None, "face_long_tons": None, "rear_roof_long_tons": None,
        "barbette_long_tons": None, "total_long_tons": None,
    }


def _finish_armour(values, diagnostics, path):
    """A total is a complete sum or nothing; it is never a partial sum."""
    components = (values["face_long_tons"], values["rear_roof_long_tons"],
                  values["barbette_long_tons"])
    if any(value is None for value in components):
        values["status"] = "unavailable"
        diagnostics.append(_unavailable(
            "battery_layout.unknown", None, path,
            "the total armour mass is unknown because at least one of the three components "
            "is unknown; it is never a partial sum"))
        return values
    values["total_long_tons"] = _finite(sum(components), path + ".total_long_tons")
    values["status"] = "available"
    return values


def _mixed_armour(layout, groups, shared, freeboard_m, super_factor, path, diagnostics):
    """The complete two-group ``armWeightCalc`` expression.

    Both diameter classes and both mount counts enter the face, side/roof and
    barbette terms, and the integer average of the two groups' per-mount barrel
    counts enters the barbette term. This is deliberately **not** the sum of two
    single-group estimates.
    """
    declared = layout.get("armour")
    if declared is None:
        return None
    provenance = _armour_provenance(declared, shared, freeboard_m, super_factor)
    values = _empty_armour_values()
    first, second = groups["group1"], groups["group2"]
    face_mm, rear_mm = declared["face_mm"], declared["rear_roof_mm"]
    barbette_mm = declared["barbette_mm"]
    values.update(face_mm=face_mm, rear_roof_mm=rear_mm, barbette_mm=barbette_mm)
    known_barrels = first["barrels"] is not None and second["barrels"] is not None
    barrels = (first["barrels"] or 0) + (second["barrels"] or 0) if known_barrels else None
    values.update(mounts_group1=first["mounts"], mounts_group2=second["mounts"],
                  barrels=barrels)
    if known_barrels and barrels == 0:
        # Every term of the recovered expression is multiplied by a zero mount
        # count, so the complete answer is a determined zero, not a missing one.
        values.update(per_mounts=0, barbette_per_mounts=0, per_mount_g1_after=0,
                      freeboard_ft=0.0)
        for name, thickness in (("face", face_mm), ("rear_roof", rear_mm),
                                ("barbette", barbette_mm)):
            values["%s_long_tons" % (name,)] = 0.0
        return {"values": _finish_armour(values, diagnostics, path),
                "provenance": provenance, "diagnostics": diagnostics}

    calibre_mm, gun_index, mount_index = shared["calibre_mm"], shared["gun_index"], shared["mount_index"]
    if calibre_mm is None or gun_index is None or mount_index is None or barrels is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", None, path,
            "the complete two-group armour needs one shared calibre, gun class and mount "
            "class and both groups' mount counts; at least one of them is unknown"))
        values["status"] = "unavailable"
        return {"values": values, "provenance": provenance, "diagnostics": diagnostics}
    calibre_in = calibre_mm / MM_PER_INCH
    diameters = []
    for name, reading in (("group1", first), ("group2", second)):
        if reading["mount_selector"] is None and reading["mounts"] != 0:
            diagnostics.append(_unavailable(
                "battery_layout.unknown", "mount_selector", "%s.%s.mount_selector" % (path, name),
                "the complete two-group armour needs both recovered diameter classes and "
                "this group's gunsInMount selector is unknown"))
            values["status"] = "unavailable"
            return {"values": values, "provenance": provenance, "diagnostics": diagnostics}
        diameters.append(0.0 if reading["mount_selector"] is None
                         else _diameter_ft(calibre_in, reading["mount_selector"],
                                           reading["weight_adjustment"]))
    average = _per_mounts_average((first, second), mount_index)
    values.update(guns_in_mount_selector_g1=first["mount_selector"],
                  guns_in_mount_selector_g2=second["mount_selector"],
                  shared_cradle_weight_adjustment_g1=first["weight_adjustment"],
                  shared_cradle_weight_adjustment_g2=second["weight_adjustment"],
                  per_mounts=average["per_mounts"],
                  barbette_per_mounts=average["barbette_per_mounts"],
                  per_mount_g1_after=average["per_mount_g1_after"],
                  mount_adjustment=MOUNT_ADJUSTMENT[mount_index],
                  barbette_coefficient=BARBETTE_COEFFICIENT.get(mount_index, 0.0),
                  face_in=None if face_mm is None else face_mm / MM_PER_INCH,
                  rear_roof_in=None if rear_mm is None else rear_mm / MM_PER_INCH,
                  barbette_in=None if barbette_mm is None else barbette_mm / MM_PER_INCH,
                  freeboard_ft=None if freeboard_m is None else freeboard_m / M_PER_FT)
    year = shared["year"]
    date_factor = kernels.gun_date_factor(year, path) if year is not None else None
    values.update(date_factor=date_factor,
                  barbette_date_factor=None if date_factor is None else math.sqrt(date_factor))
    try:
        diameter_1, diameter_2 = diameters
        summed = diameter_1 * (first["mounts"] or 0) + diameter_2 * (second["mounts"] or 0)
        disc = (math.pi * (diameter_1 / 2.0) ** 2 * (first["mounts"] or 0)
                + math.pi * (diameter_2 / 2.0) ** 2 * (second["mounts"] or 0))
        height = _gun_house_height_ft(calibre_in, mount_index)
        values.update(diameter_g1_ft=_finite(diameter_1, path),
                      diameter_g2_ft=_finite(diameter_2, path),
                      gun_house_height_ft=_finite(height, path))
        face, coefficient, reduction = _face_mass(face_mm, rear_mm, gun_index, mount_index,
                                                 summed, height, path, diagnostics)
        rear, rear_coefficient = _rear_mass(rear_mm, mount_index, summed, disc, height, path,
                                           diagnostics)
        barbette = _barbette_mass(barbette_mm, freeboard_m, super_factor, average["barbette_per_mounts"],
                                  calibre_in, barrels, mount_index, date_factor, path,
                                  diagnostics)
    except (ArithmeticError, ValueError) as error:
        diagnostics.append(_unavailable(
            "battery_layout.unavailable", None, path,
            "the recovered armour expression cannot be evaluated as a finite real number: %s"
            % (error,)))
        values["status"] = "unavailable"
        return {"values": values, "provenance": provenance, "diagnostics": diagnostics}
    values.update(face_long_tons=face, face_coefficient=coefficient,
                  face_gun_type_factor=reduction, rear_roof_long_tons=rear,
                  rear_roof_coefficient=rear_coefficient, barbette_long_tons=barbette)
    return {"values": _finish_armour(values, diagnostics, path), "provenance": provenance,
            "diagnostics": diagnostics}


def _face_mass(face, rear, gun_index, mount_index, summed, height, path, diagnostics):
    """GunControl.cs:1147-1173 with both recovered diameter classes at once."""
    if face is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "face_mm", path + ".face_mm",
            "the gun-house face thickness is unknown, so the face mass is unknown"))
        return None, None, None
    rear_is_zero = rear is not None and rear == 0.0
    coefficient, reads_rear = _face_coefficient(mount_index, rear_is_zero)
    reduction, reads_rear_reduction = _face_reduced_by_gun_type(gun_index, rear_is_zero)
    if rear is None and (reads_rear or reads_rear_reduction):
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "rear_roof_mm", path + ".rear_roof_mm",
            "the recovered face expression reads whether the side/roof thickness is exactly "
            "zero for this mount and gun, so the face mass is unknown until it is declared"))
        return None, coefficient, reduction
    mass = coefficient * summed * height * (face / MM_PER_INCH) * EMPIRICAL_MASS_CONSTANT
    if mass * reduction == 0 and face > 0 and coefficient > 0 and summed > 0:
        diagnostics.append(_unavailable("battery_layout.unavailable", "face_mm", path,
                                       "a positive face thickness underflows the mass expression"))
        return None, coefficient, reduction
    return _finite(mass * reduction, path + ".face_long_tons"), coefficient, reduction


def _rear_mass(rear, mount_index, summed, disc, height, path, diagnostics):
    """GunControl.cs:1174-1191 with both recovered diameter classes at once."""
    if rear is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "rear_roof_mm", path + ".rear_roof_mm",
            "the side/roof thickness is unknown, so its mass is unknown"))
        return None, None
    if mount_index == MOUNT_INDEX_COLES:
        mass, coefficient = disc, math.pi
    else:
        coefficient = _rear_coefficient(mount_index)
        mass = coefficient * summed * height + disc * 0.75
    value = mass * (rear / MM_PER_INCH) * EMPIRICAL_MASS_CONSTANT
    if value == 0 and rear > 0 and mass > 0:
        diagnostics.append(_unavailable("battery_layout.unavailable", "rear_roof_mm", path,
                                       "a positive rear/roof thickness underflows the mass expression"))
        return None, coefficient
    return _finite(value, path + ".rear_roof_long_tons"), coefficient


def _barbette_mass(barbette, freeboard, super_value, per_mounts, calibre_in, barrels,
                   mount_index, date_factor, path, diagnostics):
    """GunControl.cs:1192-1227 with the integer average of the two groups."""
    coefficient = BARBETTE_COEFFICIENT.get(mount_index, 0.0)
    if barbette is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "barbette_mm", path + ".barbette_mm",
            "the barbette/below-deck thickness is unknown, so the barbette mass is unknown"))
        return None
    if barbette == 0.0 or coefficient == 0.0:
        # A declared zero thickness or a mount class the original gives a zero
        # coefficient is a real zero, not a missing number.
        return 0.0
    if freeboard is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "freeboard_m", path + ".freeboard_m",
            "the recovered barbette expression reads the derived position-weighted deck "
            "freeboard, which is unknown"))
        return None
    if freeboard <= 0.0:
        # GunControl.cs:1192-1227 gates the whole term on freeGun > 0.
        return 0.0
    if super_value is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "super_factor", path + ".super_factor",
            "the recovered barbette expression reads the derived height factor, which is "
            "unknown"))
        return None
    if per_mounts is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "mount_selector", path + ".mount_selector",
            "the recovered barbette expression reads the integer average of the two groups' "
            "per-mount barrel counts, which is unknown"))
        return None
    if date_factor is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "year", path + ".year",
            "the recovered barbette expression reads the date adjustment of the referenced "
            "battery year, which is unknown"))
        return None
    adjusted = (1.0 - (per_mounts - 2.0) / 6.0) * (barbette / MM_PER_INCH * barrels
                                                   * calibre_in ** BARBETTE_CALIBRE_EXPONENT
                                                   * coefficient * (freeboard / M_PER_FT)
                                                   / BARBETTE_FREEBOARD_DIVISOR * super_value
                                                   * coefficient * BARBETTE_CALIBRE_TOTAL
                                                   * math.sqrt(date_factor))
    if not math.isfinite(adjusted):
        diagnostics.append(_unavailable(
            "battery_layout.unavailable", "barbette_mm", path + ".barbette_long_tons",
            "the recovered barbette expression cannot be evaluated as a finite real number"))
        return None
    if adjusted == 0 and barbette > 0 and barrels > 0 and super_value > 0 and per_mounts != 8:
        diagnostics.append(_unavailable("battery_layout.unavailable", "barbette_mm", path,
                                       "a nonzero barbette mass underflows the expression"))
        return None
    if adjusted < 0.0:
        # The uncapped integer average can drive the recovered barbette term
        # negative. That is refused as a mass, never clamped to a zero mass.
        diagnostics.append(_unavailable(
            "battery_layout.armour_negative", "barbette_mm", path + ".barbette_long_tons",
            "the uncapped integer average of %d barrels per mount makes the recovered "
            "barbette term negative; a negative armour component is refused rather than "
            "clamped" % (per_mounts,)))
        return None
    return float(adjusted)


def _armour_provenance(declared, shared, freeboard_m, super_factor):
    return {
        "method": ARMOUR_METHOD_VERSION,
        "kernel": "battery_layout_mixed_armour_long_tons",
        "source_assembly": SOURCE_ASSEMBLY,
        "source_sha256": SOURCE_SHA256,
        "source_location": "GunControl.cs:1127-1292",
        "source_scope": ARMOUR_SOURCE_SCOPE,
        "formula": (
            "diameter_ft(x) = class(x) x calibre_in x (1 + (1/calibre_in)^num2), plus "
            "12/calibre_in below twelve inches and x0.9 for a shared-cradle selector above "
            "one inch; summed = diameter_g1_ft x mounts_g1 + diameter_g2_ft x mounts_g2; "
            "disc = pi x (diameter_g1_ft/2)^2 x mounts_g1 + pi x (diameter_g2_ft/2)^2 x "
            "mounts_g2; gun_house_height_ft = max(7.5, 0.625 x calibre_in x "
            "(2 for a Coles turret, otherwise 1)); face_lt = face_coefficient x summed x gun_house_height_ft x "
            "face_in x 0.0185, then x0.333 for an anti-air gun or a machine gun with a "
            "zero side/roof thickness; rear_roof_lt = (rear_coefficient x summed x "
            "gun_house_height_ft + 0.75 x disc) x rear_roof_in x 0.0185, or disc alone for "
            "a Coles turret; barbette_lt = (1 - (per_mounts - 2)/6) x barbette_in x barrels "
            "x calibre_in^1.2 x barbette_coefficient x freeboard_ft / 16 x super_factor x "
            "barbette_coefficient x 2 x sqrt(sqrt(dateAdjCalc(year))), with freeboard_ft = "
            "freeboard_m / 0.3048 and per_mounts the capped or uncapped integer average of "
            "the two groups' per-mount barrel counts"),
        "assumptions": " ".join(ASSUMPTIONS),
        "inputs": {
            "calibre_mm": shared["calibre_mm"], "year": shared["year"],
            "gun_type": shared["gun_type"], "mount_type": shared["mount_type"],
            "guns_in_mount_selector_g1": shared["selector_g1"],
            "guns_in_mount_selector_g2": shared["selector_g2"],
            "mounts_g1": shared["mounts_g1"], "mounts_g2": shared["mounts_g2"],
            "barrels": shared["barrels"], "face_mm": declared["face_mm"],
            "rear_roof_mm": declared["rear_roof_mm"], "barbette_mm": declared["barbette_mm"],
            "freeboard_m": freeboard_m, "super_factor": super_factor},
    }


# -------------------------------------------------------------------- entry

def evaluate(layout, batteries, path="$.concept_design.battery_layouts"):
    """One layout's derived freeboard, height factor and mixed armour reading.

    Returns a JSON-serialisable dict with at least ``id``, ``method_version``,
    ``status``, ``groups``, ``freeboard_m``, ``super_factor``, ``armour``,
    ``diagnostics`` and ``provenance``. An unknown field is ``None``; a layout
    with no declared armour still produces its layout readings.
    """
    diagnostics = []
    normalized = validate_layouts([layout], batteries, path)[0]
    index = _battery_index(batteries)
    first = _group_reading(normalized["group1"], _row(index, battery_id(normalized["group1"])),
                           path + ".group1", diagnostics)
    second = _group_reading(normalized["group2"], _row(index, battery_id(normalized["group2"])),
                            path + ".group2", diagnostics)
    groups = {"group1": first, "group2": second}
    profile = normalized["deck_profile"]
    first["freeboard_m"] = _group_freeboard(first, profile, path + ".group1", diagnostics)
    second["freeboard_m"] = _group_freeboard(second, profile, path + ".group2", diagnostics)
    if first["state"] == "absent" and second["state"] == "absent":
        diagnostics.append(_unavailable(
            "battery_layout.unconfigured", None, path,
            "neither mount group is configured, so the layout has no mount count, no derived "
            "freeboard and no height factor; that is not a known zero"))
        return {"id": normalized["id"], "method_version": METHOD_VERSION,
                "status": "unavailable", "groups": groups, "mounts": None, "barrels": None,
                "freeboard_m": None, "super_factor": None, "armour": None,
                "diagnostics": diagnostics,
                "provenance": _provenance(normalized, None, None)}
    mounts_total = barrels = None
    if first["barrels"] is not None and second["barrels"] is not None:
        mounts_total = (first["mounts"] or 0) + (second["mounts"] or 0)
        barrels = first["barrels"] + second["barrels"]
    shared = _shared_facts(groups, index)
    freeboard_m = None
    if mounts_total is not None:
        if mounts_total == 0:
            freeboard_m = 0.0
        elif first["freeboard_m"] is None or second["freeboard_m"] is None:
            diagnostics.append(_unavailable(
                "battery_layout.unknown", "layout_index", path,
                "the two groups' freeboard are combined by mount count, so one unknown group "
                "leaves the position-weighted freeboard unknown"))
        else:
            freeboard_m = (first["freeboard_m"] * first["mounts"]
                           + second["freeboard_m"] * second["mounts"]) / float(mounts_total)
    super_factor = (None if barrels is None else
                    _height_factor(normalized, groups, shared["calibre_mm"], freeboard_m,
                                   barrels, path, diagnostics))
    if barrels is None:
        diagnostics.append(_unavailable(
            "battery_layout.unknown", "barrels", path,
            "the recovered barrel count of both groups is unknown, so the height factor and "
            "the complete armour are unknown"))
    try:
        armour = _mixed_armour(normalized, groups, shared, freeboard_m, super_factor, path,
                               diagnostics)
    except (ArithmeticError, ValueError) as error:
        diagnostics.append(_unavailable("battery_layout.unavailable", None, path,
                                       "the armour expression exceeds the numerical range: %s" % error))
        armour = None if normalized["armour"] is None else {
            "values": _empty_armour_values(), "diagnostics": copy.deepcopy(diagnostics),
            "provenance": _armour_provenance(normalized["armour"], shared, freeboard_m, super_factor)}
    if armour is not None:
        # Persisted mass receipts accept a flat scalar input map. Keep the full
        # declaration, including irrelevant unknowns, as explicit source text;
        # omit unknown scalar values rather than inventing numerical defaults.
        inputs = armour["provenance"]["inputs"]
        inputs["origin"] = json.dumps({
            "layout": normalized,
            "batteries": [{key: row.get(key) for key in BATTERY_FACT_FIELDS + ("id",)}
                          for group in (normalized["group1"], normalized["group2"])
                          if group and (row := index.get(group["battery_id"])) is not None]},
            ensure_ascii=False, sort_keys=True, allow_nan=False)
        armour["provenance"]["inputs"] = {key: value for key, value in inputs.items() if value is not None}
        if any(reading["mounts"] for reading in groups.values()) and any(
                shared[field] is None for field in ("calibre_mm", "year", "gun_type", "mount_type")):
            armour["values"]["total_long_tons"] = None
            armour["values"]["status"] = "unavailable"
    status = "unavailable"
    if freeboard_m is not None and super_factor is not None:
        status = "available"
    elif freeboard_m is not None or super_factor is not None:
        status = "partial"
    return {"id": normalized["id"], "method_version": METHOD_VERSION, "status": status,
            "groups": groups, "mounts": mounts_total, "barrels": barrels,
            "freeboard_m": freeboard_m, "super_factor": super_factor, "armour": armour,
            "diagnostics": diagnostics,
            "provenance": _provenance(normalized, freeboard_m, super_factor)}


def battery_id(group):
    return None if group is None else group.get("battery_id")


def _row(index, identifier):
    return None if identifier is None else index.get(identifier)


def _as_layout(layout):
    """Accept a normalized layout or a raw declaration, without ever raising."""
    if layout is None:
        return {"id": None, "source": None, "group1": None, "group2": None,
                "group2_double_elevation": None, "group2_double_depression": None,
                "deck_profile": None, "armour": None}
    if not isinstance(layout, dict):
        raise ValueError("a layout must be an object")
    normalized = {"id": layout.get("id"), "source": layout.get("source"),
                  "group2_double_elevation": layout.get("group2_double_elevation"),
                  "group2_double_depression": layout.get("group2_double_depression")}
    for field in ("group1", "group2", "deck_profile", "armour"):
        value = layout.get(field)
        normalized[field] = None if value is None else dict(value)
    return normalized


def _shared_facts(groups, index):
    """One calibre, year, gun class and mount class shared by both groups."""
    facts = {"calibre_mm": None, "year": None, "gun_type": None, "mount_type": None,
             "gun_index": None, "mount_index": None, "selector_g1": None,
             "selector_g2": None, "mounts_g1": None, "mounts_g2": None, "barrels": None}
    for name in ("group1", "group2"):
        reading = groups[name]
        suffix = name[-1]
        facts["selector_g%s" % (suffix,)] = reading["mount_selector"]
        facts["mounts_g%s" % (suffix,)] = reading["mounts"]
        battery = _row(index, reading["battery_id"])
        if battery is None or reading["mounts"] == 0:
            continue
        for key in ("calibre_mm", "year", "gun_type", "mount_type"):
            if facts[key] is None:
                facts[key] = _fact(battery, key)
    active_rows = [_row(index, reading["battery_id"]) for reading in groups.values()
                   if reading["mounts"] != 0]
    for key in ("calibre_mm", "year", "gun_type", "mount_type"):
        if any(row is None or _fact(row, key) is None for row in active_rows):
            facts[key] = None
    if groups["group1"]["barrels"] is not None and groups["group2"]["barrels"] is not None:
        facts["barrels"] = groups["group1"]["barrels"] + groups["group2"]["barrels"]
    if facts["gun_type"] in GUN_TYPES:
        facts["gun_index"] = GUN_TYPES.index(facts["gun_type"])
    if facts["mount_type"] in MOUNT_TYPES:
        facts["mount_index"] = MOUNT_TYPES.index(facts["mount_type"])
    return facts


def _provenance(layout, freeboard_m, super_factor):
    return {
        "method": METHOD_VERSION,
        "kernel": "battery_layout_freeboard_and_super",
        "source_assembly": SOURCE_ASSEMBLY,
        "source_sha256": SOURCE_SHA256,
        "source_location": SOURCE_LOCATION,
        "source_scope": SOURCE_SCOPE,
        "formula": (
            "group freeboard_m = freeGunCalc(layout_index, group mounts, deck profile), "
            "where mountsFor = round_ties_to_even(mounts / 2) on the recovered branches and "
            "0 for a flush-deck single mount on layouts 0 and 9; freeboard_m = "
            "(freeboard_m_g1 x mounts_g1 + freeboard_m_g2 x mounts_g2) / (mounts_g1 + "
            "mounts_g2); super_factor = (super_ratio x max(7.5, 0.6 x calibre_in) + "
            "freeboard_ft) / freeboard_ft with super_ratio = (elevated barrels + doubled "
            "elevated group-2 barrels - depressed barrels - doubled depressed group-2 "
            "barrels) / barrels and freeboard_ft = freeboard_m / 0.3048; a determined zero "
            "barrel count returns freeboard 0 and super 1"),
        "assumptions": " ".join(ASSUMPTIONS),
        "inputs": {
            "id": layout["id"], "source": layout["source"],
            "group1": _declared(layout["group1"]), "group2": _declared(layout["group2"]),
            "group2_double_elevation": layout["group2_double_elevation"],
            "group2_double_depression": layout["group2_double_depression"],
            "deck_profile": layout["deck_profile"], "armour": layout["armour"],
            "freeboard_m": freeboard_m, "super_factor": super_factor},
    }


def _declared(group):
    return None if group is None else {field: group.get(field) for field in GROUP_FIELDS}
