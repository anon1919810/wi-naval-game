"""Battery gun-house and barbette armour mass, as an independent versioned kernel.

This is a pure function over a finite declared domain. It never touches a
project, a ledger or a file, it never clamps an out-of-domain value, and it never
reads an unknown input as zero: a missing declared input produces a structured
unavailable diagnostic and an unknown component, while a wrong type, a wrong
sign, an out-of-domain number and a fractional count are refused.

It is deliberately **not** part of the adapted configuration method. The
configuration keeps ``sps-3b3-adapted-v1``; this kernel carries its own
``sps-3b3-battery-armour-v1`` and is recorded as a *component* method on every
model it produces, so a reader can tell which numbers came from which method.

Numerical source
----------------
Recovered ``SpringSharpMono`` 3.0.3032.29945, the same original binary the
adapted concept kernels use (identical assembly string and SHA256, re-exported
from :mod:`concept_estimates` so the two can never drift apart):

* ``GunControl.cs:1127-1236`` ``armWeightCalc``
* ``GunControl.cs:1238-1292`` ``diameterCalc``
* ``GunControl.cs:480`` ``weightAdjCalc``, ``:636`` ``perMountCalc``
* ``MainForm.cs:22`` the empirical mass constant ``INCH``
* ``MainForm.cs:1669`` ``dateAdjCalc``, reached through ``GunControl.cs:429``

Every unit is the original's own: calibre, thicknesses and diameters are inches
and feet, and the position-weighted freeboard the barbette expression reads is
**feet**. That freeboard is declared in metres on this interface and converted
once, explicitly, here; feeding metres into the recovered expression is a
factor-of-0.3048 error and was caught by comparing against the original
assembly.

Three recovered quirks are preserved verbatim rather than "rationalised" away,
because reproducing the original method means reproducing what it computes:

* the barbette expression multiplies **its own coefficient twice**, so the
  coefficient enters squared;
* the barbette year factor is ``sqrt(dateGunAdj)`` while ``dateGunAdj`` is
  already ``sqrt(dateAdjCalc(year))``, so it is the **fourth** root of the date
  adjustment, not the square root the shell and gun mass kernels use;
* the low-mount branch writes ``perMountG1`` instead of ``perMounts``, so for a
  homogeneous 1..5 barrel row the mount count reaching the barbette expression
  is **uncapped**.

Scope
-----
This is an independent empirical *estimate* of the armour belonging to one
battery group. It is not armour geometry reconstruction, not a structural
strength calculation and not whole-program parity, and it carries no claim about
any real ship.

Declared single-group reading
-----------------------------
The original keeps two mount groups (``mountsG1``/``mountsG2``) so one weapon
can describe, for example, a superfiring pair. This kernel supports a single
homogeneous group row and **excludes multi-row and mixed arrangements**, so the
second group is empty: ``mountsG1 = mount_count``, ``mountsG2 = 0``,
``perMountG1 = barrels_per_mount``, ``perMountG2 = 0``. The integer average the
original takes of the two groups is therefore exactly the row's barrels per
mount, and a 6..10 barrels-per-mount group has no declared selector here and is
reported unsupported rather than approximated.

The recovered ``gunsInMount`` selector
--------------------------------------
``diameterCalc`` (:1238) and ``weightAdjCalc`` (:480) are both keyed by the
original's ``gunsInMount`` combo index, a fifteen-entry table that belongs to
the two-group layout model. For one homogeneous row the selector is pinned to:

===============  =====================  ===============
barrels per mount  selector           weight adjust.
===============  =====================  ===============
1                0                     1.0
2                4 (3 shared)          1.0 (0.75)
3                7 (6 shared)          1.0 (0.75)
4                10 (9 shared)         1.0 (0.75)
5                13 (12 shared)        1.0 (0.75)
===============  =====================  ===============

The shared-cradle selectors 3/6/9/12 are exactly the four ``weightAdjCalc``
returns 0.75 for, and each pair shares one diameter class, so the declared
boolean is the recovered 0.75 factor rather than a second, invented selector.
"""

from __future__ import annotations

import math

try:
    from . import concept_estimates as siblings
except ImportError:                                   # pragma: no cover - direct import
    import concept_estimates as siblings

METHOD_VERSION = "sps-3b3-battery-armour-v1"
SOURCE_LOCATION = "GunControl.cs:1127-1294"
SOURCE_ASSEMBLY = siblings.SOURCE_ASSEMBLY
SOURCE_SHA256 = siblings.SOURCE_SHA256
SOURCE_SCOPE = (
    "Independent empirical estimate of one homogeneous battery group's armour, "
    "reproduced from the recovered 3b3 armWeightCalc expression; not armour "
    "geometry reconstruction, not structural strength, not whole-program parity "
    "and not validated against any real ship."
)

# MainForm.cs:22. The recovered empirical mass constant. It turns the source's
# inch thicknesses into feet inside an expression that is already in feet, so it
# is not a density and is never restated as one.
EMPIRICAL_MASS_CONSTANT = 0.0185
MM_PER_INCH = siblings.M_PER_INCH * 1000.0
GUN_HOUSE_MIN_FT = 7.5
GUN_HOUSE_PER_CALIBRE = 0.625
GUN_HOUSE_COLE_DOUBLING = 2.0
ANTI_AIR_FACE_FACTOR = 0.333
BARBETTE_CALIBRE_EXPONENT = 1.2
BARBETTE_FREEBOARD_DIVISOR = 16.0
BARBETTE_CALIBRE_TOTAL = 2.0
BARBETTE_PER_MOUNT_CAP = 4

GUN_TYPES = siblings.GUN_TYPES
MOUNT_TYPES = siblings.MOUNT_TYPES
MOUNT_ADJUSTMENT = siblings.MOUNT_ADJUSTMENT
MAX_MOUNTS = siblings.MAX_MOUNTS
MAX_CALIBRE_MM = 500.0
MAX_THICKNESS_MM = 1000.0
MAX_FREEBOARD_M = 100.0
MAX_SUPER_FACTOR = 10.0

# GunControl.cs:1100-1123 mountChoiceSelectedIndexChanged.
MOUNT_INDEX_BROADSIDE = 0
MOUNT_INDEX_COLES = 1
MOUNT_INDEX_OPEN_BARBETTE = 2
MOUNT_INDEX_DECK = 5
MOUNT_INDEX_CASEMATE = 6
GUN_INDEX_ANTI_AIR = 3
GUN_INDEX_MACHINE_GUN = 6

# GunControl.cs:1106-1220 barbette coefficients. Mount types with no entry are
# the ones the original gives a zero coefficient, and a zero coefficient makes
# the whole barbette term zero whatever the thickness is.
BARBETTE_COEFFICIENT = {
    MOUNT_INDEX_OPEN_BARBETTE: 0.6416,
    3: 0.5,
    4: 0.1,
    MOUNT_INDEX_CASEMATE: 0.1,
}

# GunControl.cs:1238-1274 diameterCalc, the five (num, num2) classes, keyed by
# the recovered ``gunsInMount`` selector the method actually receives.
DIAMETER_CLASS_BY_SELECTOR = {}
for _selector in range(15):
    if _selector <= 2:
        DIAMETER_CLASS_BY_SELECTOR[_selector] = (1.44, 0.609725)
    elif _selector <= 5:
        DIAMETER_CLASS_BY_SELECTOR[_selector] = (1.52, 0.4205)
    elif _selector <= 8:
        DIAMETER_CLASS_BY_SELECTOR[_selector] = (1.64, 0.29)
    elif _selector <= 11:
        DIAMETER_CLASS_BY_SELECTOR[_selector] = (1.8, 0.2)
    else:
        DIAMETER_CLASS_BY_SELECTOR[_selector] = (2.0, 0.14)

# GunControl.cs:480 weightAdjCalc returns 0.75 for the gunsInMount indices
# 3, 6, 9 and 12 and 1.0 everywhere else. The sibling mount-mass kernel already
# publishes that same recovered value as SHARED_CRADLE_WEIGHT_ADJUSTMENT.
WEIGHT_ADJUSTMENT_BY_SELECTOR = {index: (0.75 if index in (3, 6, 9, 12) else 1.0)
                                  for index in range(15)}
SHARED_CRADLE_WEIGHT_ADJUSTMENT = siblings.SHARED_CRADLE_WEIGHT_ADJUSTMENT

# The recovered gunsInMount selector for ONE homogeneous row: the non-shared
# selectors 0/4/7/10/13 and the shared-cradle selectors 3/6/9/12.
GUNS_IN_MOUNT_SELECTOR = {
    1: {False: 0, True: None},
    2: {False: 4, True: 3},
    3: {False: 7, True: 6},
    4: {False: 10, True: 9},
    5: {False: 13, True: 12},
}
SUPPORTED_BARRELS_PER_MOUNT = tuple(sorted(GUNS_IN_MOUNT_SELECTOR))
DIAMETER_CLASS_BY_BARRELS_PER_MOUNT = {
    per_mount: DIAMETER_CLASS_BY_SELECTOR[GUNS_IN_MOUNT_SELECTOR[per_mount][False]]
    for per_mount in GUNS_IN_MOUNT_SELECTOR
}
SHARED_CRADLE_DIAMETER_FACTOR = 0.9
SMALL_CALIBRE_INCHES = 12.0
LARGE_CALIBRE_INCHES = 1.0

ASSUMPTIONS = (
    "one homogeneous mount group row; multi-row and mixed arrangements are "
    "excluded, the recovered second mount group is empty, and the source's "
    "integer average of the two groups is this row's barrels per mount",
    "the recovered gunsInMount selector is pinned to 0 for one barrel and to "
    "4/7/10/13 without a shared cradle or 3/6/9/12 with one, which are the "
    "selectors the recovered weightAdjCalc and diameterCalc tables hold for a "
    "single homogeneous row; the fifteen-entry table itself belongs to the "
    "two-group layout model",
    "the recovered position-weighted freeboard the barbette expression reads is "
    "in FEET; freeboard_m is declared in metres and converted once, explicitly",
    "freeboard_m is the position-weighted deck freeboard at the gun position, "
    "declared by the reader; it is neither the centre of gravity nor a "
    "representative whole-ship freeboard",
    "super_factor is the recovered height factor super, declared by the reader; "
    "it is not derived from a layout or from a physical heel",
    "the recovered barbette coefficient appears twice in its own expression, so "
    "the coefficient enters squared",
    "the barbette year factor is the fourth root of the recovered date "
    "adjustment, because the expression takes sqrt(dateGunAdj) and dateGunAdj "
    "is already a square root",
    "the recovered low-mount branch writes perMountG1 instead of perMounts, so "
    "for a 1..5 barrel row the barbette mount count is uncapped there",
    "a barbette is fixed structure and not a rotating structure; this mass "
    "belongs to its own design role, separate from complete rotating armour",
)


class _Unknown:
    """A declared input that was not supplied. Never zero."""

    __slots__ = ()

    def __repr__(self):                                 # pragma: no cover - debugging aid
        return "<unknown>"


UNKNOWN = _Unknown()


class _NumericUnavailable(Exception):
    """A legal declared input whose recovered expression cannot be evaluated.

    ``ArithmeticError`` covers the interpreter's own overflow and
    divide-by-zero, and ``ValueError`` covers this module's own non-finite
    result check. Both are converted into a structured unavailable diagnostic at
    the entry point, so a declared value never escapes as a raw interpreter
    error and is never clamped or replaced by a floor.
    """

    def __init__(self, field, message):
        self.field = field
        super().__init__(message)


def _guard(field, function, *args):
    """Run one recovered expression inside the numerical-error boundary."""
    try:
        return function(*args)
    except _NumericUnavailable:
        raise
    except (ArithmeticError, ValueError) as error:
        raise _NumericUnavailable(field, str(error)) from error


def _fail(message, path):
    raise ValueError("%s: %s" % (path, message))


def _number(value, path, *, positive=False, nonnegative=False, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("must be a finite number", path)
    try:
        number = float(value)
    except (OverflowError, ValueError):
        _fail("exceeds the supported numeric range", path)
    if not math.isfinite(number):
        _fail("must be a finite number", path)
    if positive and number <= 0.0:
        _fail("must be positive", path)
    if nonnegative and number < 0.0:
        _fail("must not be negative", path)
    if low is not None and number < low:
        _fail("must be >= %r" % (low,), path)
    if high is not None and number > high:
        _fail("must be <= %r" % (high,), path)
    return number


def _count(value, path, *, low=0, high=None):
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("must be an integer", path)
    if value < low or (high is not None and value > high):
        _fail("must be an integer in [%d, %s]" % (low, "inf" if high is None else high), path)
    return int(value)


def _enum(value, options, path):
    if not isinstance(value, str) or value not in options:
        _fail("must be one of %r" % (list(options),), path)
    return options.index(value)


def _finite(value, path):
    if isinstance(value, complex) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _fail("the derived result is not a finite real number", path)
    return float(value)


def _optional_number(value, path, *, low, high, unknown):
    """A declared number that may be absent. Absence stays absence."""
    if value is None:
        return unknown
    return _number(value, path, low=low, high=high)


def _unavailable(code, field, path, message):
    return {"code": code, "field": field, "path": path, "message": message}


def _millimetres(value, path, unknown, field):
    return _optional_number(value, path + "." + field, low=0.0, high=MAX_THICKNESS_MM,
                            unknown=unknown)


# ------------------------------------------------------------------ geometry

def _diameter_ft(calibre_in, barrels_per_mount, shared_cradle, path):
    """GunControl.cs:1238-1292 for one homogeneous group.

    The source adds ``12 / calibre`` below twelve inches and applies the shared
    cradle's 0.75 weight adjustment as a tenth off the diameter, both kept.
    """
    selector = GUNS_IN_MOUNT_SELECTOR[barrels_per_mount][bool(shared_cradle)]
    weight_adjustment = WEIGHT_ADJUSTMENT_BY_SELECTOR[selector]
    num, num2 = DIAMETER_CLASS_BY_SELECTOR[selector]
    diameter = num * calibre_in * (1.0 + (1.0 / calibre_in) ** num2)
    if calibre_in < SMALL_CALIBRE_INCHES:
        diameter += SMALL_CALIBRE_INCHES / calibre_in
    factor = 1.0
    if calibre_in > LARGE_CALIBRE_INCHES and weight_adjustment < 1.0:
        factor = SHARED_CRADLE_DIAMETER_FACTOR
        diameter *= factor
    return _finite(diameter, path), selector, factor


def _disc_area(diameter_ft, mounts, path="$.batteries"):
    """pi x (diameter / 2)^2 x mounts; the source's own area term."""
    return math.pi * (diameter_ft / 2.0) ** 2 * mounts


def _gun_house_height_ft(calibre_in, mount_index, path):
    """GunControl.cs:1131-1138: the Coles turret doubles it, the floor is 7.5."""
    if mount_index == MOUNT_INDEX_COLES:
        height = GUN_HOUSE_PER_CALIBRE * calibre_in * GUN_HOUSE_COLE_DOUBLING
    else:
        height = GUN_HOUSE_PER_CALIBRE * calibre_in
    return _finite(max(GUN_HOUSE_MIN_FT, height), path)


def _barbette_per_mounts(mounts, barrels_per_mount, mount_adjustment):
    """GunControl.cs:1194-1205, written as the original writes it.

    The original averages the two groups' per-mount barrel counts as integers,
    which for one homogeneous row is the row's own barrels per mount. Above a
    0.5 mount adjustment it caps the average; at or below 0.5 it writes
    ``perMountG1`` instead of ``perMounts`` and the average reaches the barbette
    expression uncapped. That write is preserved, not corrected.
    """
    if mounts <= 0:
        # The source skips the average entirely and keeps whatever the control
        # held. Nothing reads it here: zero mounts and zero barrels make the
        # barbette product zero regardless, so the row's own value is used and
        # every output stays finite.
        return barrels_per_mount
    per_mounts = barrels_per_mount
    if mount_adjustment > 0.5:
        per_mounts = min(BARBETTE_PER_MOUNT_CAP, per_mounts)
    return per_mounts


def _face_reduced_by_gun_type(gun_index, rear_is_zero):
    """GunControl.cs:1170-1173. Returns ``(factor, reads_rear_thickness)``."""
    if gun_index == GUN_INDEX_ANTI_AIR:
        return ANTI_AIR_FACE_FACTOR, False
    if gun_index == GUN_INDEX_MACHINE_GUN:
        # The recovered condition is (gunType == 6 && armBack == 0), so this one
        # gun class genuinely reads whether the side/roof thickness is a zero.
        return (ANTI_AIR_FACE_FACTOR, True) if rear_is_zero else (1.0, True)
    return 1.0, False


def _face_coefficient(mount_index, rear_is_zero):
    """GunControl.cs:1149-1168. Returns ``(coefficient, reads_rear_thickness)``."""
    if mount_index in (MOUNT_INDEX_BROADSIDE, MOUNT_INDEX_CASEMATE):
        return 1.0, False
    if mount_index == MOUNT_INDEX_COLES:
        return math.pi / 2.0, False
    if mount_index == MOUNT_INDEX_OPEN_BARBETTE:
        return 0.0, False
    return (1.5 if rear_is_zero else 0.5), True


def _rear_coefficient(mount_index):
    """GunControl.cs:1174-1190: the side/roof area term before the thickness."""
    return 2.5 if 2 < mount_index < 6 else 0.0


# ------------------------------------------------------------------- estimate

def estimate(calibre_mm, year, gun_type, mount_type, mount_count, barrels_per_mount,
             shared_cradle, face_mm, rear_roof_mm, barbette_mm, freeboard_m=None,
             super_factor=None, path="$.batteries"):
    """One homogeneous battery group's face, side/roof and barbette armour mass.

    ``face_mm``, ``rear_roof_mm`` and ``barbette_mm`` are millimetres and may be
    ``None``, which means *unknown* and never the same thing as a declared zero.
    ``freeboard_m`` and ``super_factor`` are only read by the barbette term, so a
    mount with no barbette coefficient, or a declared zero barbette thickness,
    does not need them.

    Returns ``{"values": {...}, "provenance": {...}, "diagnostics": [...]}``. Every
    returned number is finite and non-negative; an unknown component is ``None``
    and the total is ``None`` rather than a partial sum.
    """
    calibre = _number(calibre_mm, path + ".calibre_mm", positive=True, high=MAX_CALIBRE_MM)
    calibre_in = calibre / MM_PER_INCH
    year_value = _count(year, path + ".year", low=siblings.MIN_YEAR, high=siblings.MAX_YEAR)
    gun_index = _enum(gun_type, GUN_TYPES, path + ".gun_type")
    mount_index = _enum(mount_type, MOUNT_TYPES, path + ".mount_type")
    mounts = _count(mount_count, path + ".mount_count", low=0, high=MAX_MOUNTS)
    per_mount = _count(barrels_per_mount, path + ".barrels_per_mount", low=1,
                       high=siblings.MAX_BARRELS_PER_MOUNT)
    if not isinstance(shared_cradle, bool):
        _fail("must be a boolean", path + ".shared_cradle")
    if shared_cradle and not 2 <= per_mount <= 5:
        _fail("a shared cradle is only declared for 2..5 barrels per mount",
              path + ".barrels_per_mount")
    face = _millimetres(face_mm, path, UNKNOWN, "face_mm")
    rear = _millimetres(rear_roof_mm, path, UNKNOWN, "rear_roof_mm")
    barbette = _millimetres(barbette_mm, path, UNKNOWN, "barbette_mm")
    freeboard = _optional_number(freeboard_m, path + ".freeboard_m", low=0.0,
                                high=MAX_FREEBOARD_M, unknown=UNKNOWN)
    super_value = _optional_number(super_factor, path + ".super_factor", low=0.0,
                                   high=MAX_SUPER_FACTOR, unknown=UNKNOWN)

    provenance = _provenance(calibre_mm=calibre, calibre_in=calibre_in, year=year_value,
                             gun_type=gun_type, mount_type=mount_type, mount_count=mounts,
                             barrels_per_mount=per_mount,
                             barrels=mounts * per_mount, shared_cradle=shared_cradle,
                             face_mm=face_mm, rear_roof_mm=rear_roof_mm,
                             barbette_mm=barbette_mm, freeboard_m=freeboard_m,
                             super_factor=super_factor)
    diagnostics = []
    values = _empty_values(calibre_mm=calibre, calibre_in=calibre_in, year=year_value,
                           gun_type=gun_type, mount_type=mount_type, mount_count=mounts,
                           barrels_per_mount=per_mount, barrels=mounts * per_mount,
                           shared_cradle=shared_cradle, face_mm=face_mm,
                           rear_roof_mm=rear_roof_mm, barbette_mm=barbette_mm,
                           freeboard_m=freeboard_m, super_factor=super_factor)

    if barrels_per_mount not in GUNS_IN_MOUNT_SELECTOR:
        # A 6..10 barrel group is a valid declared battery and keeps every other
        # estimate; only this one has no recovered selector here.
        diagnostics.append(_unavailable(
            "battery_armour.unsupported", "barrels_per_mount", path + ".barrels_per_mount",
            "the recovered armour expression is defined for 1..5 barrels per mount in one "
            "homogeneous row; %d barrels per mount has no recovered gunsInMount selector "
            "here and is not approximated" % (barrels_per_mount,)))
        return {"values": values, "provenance": provenance, "diagnostics": diagnostics}

    mount_adjustment = MOUNT_ADJUSTMENT[mount_index]
    try:
        diameter, selector, cradle_factor = _guard("calibre_mm", _diameter_ft, calibre_in,
                                                  barrels_per_mount, shared_cradle,
                                                  path + ".diameter_ft")
        height = _guard("calibre_mm", _gun_house_height_ft, calibre_in, mount_index,
                        path + ".gun_house_height_ft")
        summed = diameter * mounts
        disc = _guard("calibre_mm", _disc_area, diameter, mounts)
    except _NumericUnavailable as error:
        diagnostics.append(_unavailable("battery_armour.unavailable", error.field, path,
                                        "the recovered expression cannot be evaluated as a "
                                        "finite real number for this declared calibre: %s"
                                        % (error,)))
        return {"values": values, "provenance": provenance, "diagnostics": diagnostics}
    date_factor = siblings.gun_date_factor(year_value, path + ".year")
    barbette_date_factor = math.sqrt(date_factor)
    # The recovered barbette expression reads the position-weighted freeboard in
    # FEET. It is declared in metres here and converted exactly once.
    freeboard_ft = None if freeboard is UNKNOWN else freeboard / siblings.M_PER_FT

    values.update(diameter_ft=diameter, gun_house_height_ft=height,
                  guns_in_mount_selector=selector, mount_adjustment=mount_adjustment,
                  shared_cradle_weight_adjustment=WEIGHT_ADJUSTMENT_BY_SELECTOR[selector],
                  shared_cradle_diameter_factor=cradle_factor,
                  face_in=None if face is UNKNOWN else face / MM_PER_INCH,
                  rear_roof_in=None if rear is UNKNOWN else rear / MM_PER_INCH,
                  barbette_in=None if barbette is UNKNOWN else barbette / MM_PER_INCH,
                  barbette_coefficient=BARBETTE_COEFFICIENT.get(mount_index, 0.0),
                  freeboard_ft=freeboard_ft,
                  date_factor=date_factor, barbette_date_factor=barbette_date_factor,
                  barbette_per_mounts=_barbette_per_mounts(mounts, barrels_per_mount,
                                                          mount_adjustment))

    try:
        faced = _guard("calibre_mm", _face_mass, face, rear, gun_index, mount_index, summed,
                       height, path, diagnostics)
        face_lt = None if faced is None else faced[0]
        face_coefficient = None if faced is None else faced[1]
        face_reduction = None if faced is None else faced[2]
        reared = _guard("calibre_mm", _rear_mass, rear, mount_index, summed, disc, height,
                        path, diagnostics)
        rear_lt = None if reared is None else reared[0]
        rear_coefficient = None if reared is None else reared[1]
        barbette_lt = _guard("calibre_mm", _barbette_mass, barbette, freeboard, super_value,
                             values, per_mount, calibre_in, mounts, mount_index, year_value,
                             path, diagnostics)
    except _NumericUnavailable as error:
        diagnostics.append(_unavailable("battery_armour.unavailable", error.field, path,
                                        "the recovered expression cannot be evaluated as a "
                                        "finite real number for this declared calibre: %s"
                                        % (error,)))
        return {"values": values, "provenance": provenance, "diagnostics": diagnostics}
    values.update(face_long_tons=face_lt, rear_roof_long_tons=rear_lt,
                  barbette_long_tons=barbette_lt,
                  face_coefficient=face_coefficient, face_gun_type_factor=face_reduction,
                  rear_roof_coefficient=rear_coefficient)
    if face_lt is None or rear_lt is None or barbette_lt is None:
        diagnostics.append(_unavailable(
            "battery_armour.unknown", None, path,
            "the total armour mass is unknown because at least one of the three "
            "components is unknown; it is never a partial sum"))
    else:
        values["total_long_tons"] = _finite(face_lt + rear_lt + barbette_lt,
                                            path + ".total_long_tons")
    return {"values": values, "provenance": provenance, "diagnostics": diagnostics}


def _face_mass(face, rear, gun_index, mount_index, summed, height, path, diagnostics):
    """GunControl.cs:1147-1173. ``(mass, coefficient, gun-type factor)``."""
    if face is UNKNOWN:
        diagnostics.append(_unavailable(
            "battery_armour.unknown", "face_mm", path + ".face_mm",
            "the gun-house face thickness is unknown, so the face mass is unknown"))
        return None
    rear_is_zero = rear is not UNKNOWN and rear == 0.0
    coefficient, reads_rear = _face_coefficient(mount_index, rear_is_zero)
    reduction, reads_rear_reduction = _face_reduced_by_gun_type(gun_index, rear_is_zero)
    if rear is UNKNOWN and (reads_rear or reads_rear_reduction):
        diagnostics.append(_unavailable(
            "battery_armour.unknown", "rear_roof_mm", path + ".rear_roof_mm",
            "the recovered face expression reads whether the side/roof thickness is "
            "exactly zero for this mount and gun, so the face mass is unknown until it "
            "is declared"))
        return None
    mass = coefficient * summed * height * (face / MM_PER_INCH) * EMPIRICAL_MASS_CONSTANT
    return _finite(mass * reduction, path + ".face_long_tons"), coefficient, reduction


def _rear_mass(rear, mount_index, summed, disc, height, path, diagnostics):
    """GunControl.cs:1174-1191. ``(mass, coefficient)``.

    The recovered expression adds the 0.75 disc term whether the area
    coefficient is 2.5 or zero, so a mount class with a zero coefficient still
    carries side/roof mass. That is the source's own behaviour.
    """
    if rear is UNKNOWN:
        diagnostics.append(_unavailable(
            "battery_armour.unknown", "rear_roof_mm", path + ".rear_roof_mm",
            "the side/roof thickness is unknown, so its mass is unknown"))
        return None
    if mount_index == MOUNT_INDEX_COLES:
        mass, coefficient = disc, math.pi
    else:
        coefficient = _rear_coefficient(mount_index)
        mass = coefficient * summed * height + disc * 0.75
    return (_finite(mass * (rear / MM_PER_INCH) * EMPIRICAL_MASS_CONSTANT,
                    path + ".rear_roof_long_tons"), coefficient)


def _barbette_mass(barbette, freeboard, super_value, values, per_mount, calibre_in,
                   mounts, mount_index, year_value, path, diagnostics):
    """GunControl.cs:1192-1227, coefficient squared and fourth-root year factor."""
    coefficient = BARBETTE_COEFFICIENT.get(mount_index, 0.0)
    if barbette is UNKNOWN:
        diagnostics.append(_unavailable(
            "battery_armour.unknown", "barbette_mm", path + ".barbette_mm",
            "the barbette/below-deck thickness is unknown, so the barbette mass is "
            "unknown"))
        return None
    if barbette == 0.0 or coefficient == 0.0:
        # Nothing to read: a declared zero thickness or a mount class the original
        # gives a zero coefficient is a real zero, not a missing number.
        return 0.0
    if freeboard is UNKNOWN:
        diagnostics.append(_unavailable(
            "battery_armour.unknown", "freeboard_m", path + ".freeboard_m",
            "the recovered barbette expression reads the position-weighted deck "
            "freeboard, which is unknown"))
        return None
    if freeboard <= 0.0:
        return 0.0
    if super_value is UNKNOWN:
        diagnostics.append(_unavailable(
            "battery_armour.unknown", "super_factor", path + ".super_factor",
            "the recovered barbette expression reads the declared height factor "
            "super, which is unknown"))
        return None
    per_mounts = values["barbette_per_mounts"]
    freeboard_ft = freeboard / siblings.M_PER_FT
    mass = ((1.0 - (per_mounts - 2.0) / 6.0)
            * (barbette / MM_PER_INCH * (mounts * per_mount)
               * calibre_in ** BARBETTE_CALIBRE_EXPONENT * coefficient * freeboard_ft
               / BARBETTE_FREEBOARD_DIVISOR * super_value * coefficient
               * BARBETTE_CALIBRE_TOTAL * math.sqrt(
                   siblings.gun_date_factor(year_value, path + ".year"))))
    return _finite(mass, path + ".barbette_long_tons")


# ----------------------------------------------------------------- provenance

def _empty_values(**declared):
    values = dict(declared)
    values.update(diameter_ft=None, gun_house_height_ft=None, guns_in_mount_selector=None,
                  mount_adjustment=None, shared_cradle_weight_adjustment=None,
                  shared_cradle_diameter_factor=None, face_in=None, rear_roof_in=None,
                  barbette_in=None, face_coefficient=None, face_gun_type_factor=None,
                  rear_roof_coefficient=None, barbette_coefficient=None, freeboard_ft=None,
                  date_factor=None, barbette_date_factor=None, barbette_per_mounts=None,
                  face_long_tons=None, rear_roof_long_tons=None, barbette_long_tons=None,
                  total_long_tons=None)
    return values


def _provenance(**inputs):
    return {
        "method": METHOD_VERSION,
        "kernel": "battery_armour_long_tons",
        "source_assembly": SOURCE_ASSEMBLY,
        "source_sha256": SOURCE_SHA256,
        "source_location": SOURCE_LOCATION,
        "source_scope": SOURCE_SCOPE,
        "formula": (
            "face_lt = face_coefficient x (diameter_ft x mounts) x gun_house_height_ft x "
            "face_in x 0.0185, then x 0.333 for an anti-air gun or a machine gun with a "
            "zero side/roof thickness; rear_roof_lt = (rear_coefficient x (diameter_ft x "
            "mounts) x gun_house_height_ft + 0.75 x pi x (diameter_ft/2)^2 x mounts) x "
            "rear_roof_in x 0.0185, or the disc term alone for a Coles turret; "
            "barbette_lt = (1 - (barbette_per_mounts - 2)/6) x barbette_in x barrels x "
            "calibre_in^1.2 x barbette_coefficient x freeboard_ft / 16 x super_factor x "
            "barbette_coefficient x 2 x sqrt(sqrt(dateAdjCalc(year))), with "
            "freeboard_ft = freeboard_m / 0.3048"),
        "assumptions": " ".join(ASSUMPTIONS),
        "inputs": dict(inputs),
    }