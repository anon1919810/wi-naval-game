"""Versioned empirical concept-estimate kernels adapted from SpringSharp 3b3.

These are pure functions over a finite declared domain. They never touch a
project, a ledger or a file, and they never clamp an out-of-domain value: an
invalid or unknown input is rejected so the caller can report it.

Numerical source
----------------
Recovered ``SpringSharpMono`` 3.0.3032.29945, executable SHA256
``82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc``:

* ``GunControl.cs:480`` ``weightAdjCalc``/``perMountCalc``
* ``GunControl.cs:793`` ``shellWeightCalc``
* ``GunControl.cs:808`` ``magazineCalc``
* ``GunControl.cs:815`` ``gunWeightCalc``
* ``HullControl.cs:1269`` wetted surface, ``:1272`` crew band
* ``HullControl.cs:1313`` ``waterplaneAreaCalc``, ``:1345`` ``coSharpCalc``
* ``EngineControl.cs:386`` friction/wave, ``:438`` ``speedHpCalc``
* ``EngineControl.cs:538`` ``engineCalc``, ``:888`` ``bunkerCalc``
* ``PerformanceControl.cs:265`` ``roomHullCalc``, ``:307`` ``roomDeckCalc``
* ``PerformanceControl.cs:332`` ``stabilityCalc``, ``:403`` ``seaboatCalc``
* ``PerformanceControl.cs:498`` ``structWeightCalc``
* ``PerformanceControl.cs:546`` ``strengthCrossCalc``, ``:591`` ``strengthLongCalc``,
  ``:610`` ``strengthCompCalc``

The original is ``float``. This module is ``float64``; the source's float32
rounding is the stated tolerance, verified against independent original-assembly
vectors in ``tests/test_concept_estimates.py``.

Scope
-----
This is an **adapted concept method**, not whole-program parity. It replaces
SpringSharp's hidden residual bookkeeping with an explicit selected ledger, and
``sps-3b3-adapted-v1`` says so in every result. It carries no claim about any
real ship, and it is kept strictly separate from physical hydrostatics, GM, GZ,
trim and roll.
"""

from __future__ import annotations

import math

METHOD_VERSION = "sps-3b3-adapted-v1"
SOURCE_ASSEMBLY = "SpringSharpMono 3.0.3032.29945"
SOURCE_SHA256 = "82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc"
SOURCE_SCOPE = (
    "Adapted empirical concept method from the recovered 3b3 binary; not whole-program "
    "parity and not validated against any real ship."
)

# Canonical conversions. The recovered program converts internally to imperial
# units; that is explicit here, never implicit.
M_PER_FT = 0.3048
FT_PER_M = 1.0 / M_PER_FT
M_PER_INCH = 0.0254
INCH_PER_M = 1.0 / M_PER_INCH
KG_PER_LB = 0.45359237
LONG_TON_KG = 1016.0469088
LB_PER_LONG_TON = 2240.0
KW_PER_HP = 0.746
# MainForm.TON = 35. One long ton of seawater occupies 2240 lb / 64 lb/ft^3 = 35
# cubic feet, so this is the specific volume in ft^3 per long ton, NOT a density.
SEAWATER_CUBIC_FT_PER_LONG_TON = 35.0

GUN_TYPES = ("muzzle_loading", "breech_loading", "quick_firing", "anti_air",
             "dual_purpose", "automatic", "machine_gun")
MOUNT_TYPES = ("broadside", "coles_turret", "open_barbette", "turret_barbette",
               "deck_hoist", "deck", "casemate")
ENGINE_KINDS = ("simple", "compound", "turbine")
STERN_TYPES = ("cruiser", "small_transom", "large_transom", "round")

# GunControl.cs:1098 mountChoiceSelectedIndexChanged.
MOUNT_ADJUSTMENT = (0.5, 1.0, 0.7, 1.0, 1.0, 0.5, 0.5)
# GunControl.cs:480 weightAdjCalc: the recovered mount-class weight adjustment.
# 1.0 unless the guns-per-mount combo index is 3, 6, 9 or 12 (perMountCalc :636
# gives those 2, 3, 4 and 5 barrels per mount).
SHARED_CRADLE_WEIGHT_ADJUSTMENT = 0.75
# GunControl.cs:828-846 base mount mass coefficients, in long tons per unit.
MOUNT_BASE = (0.83, None, 3.33, None, 3.15, 1.08, 1.08)
# GunControl.cs:847-891 gun-type multipliers, keyed by (gun_type, mountAdj<0.6).
GUN_TYPE_LOW_MOUNT = {0: 0.9, 2: 1.35, 3: 1.44, 4: 1.57, 5: 2.16}
GUN_TYPE_HIGH_MOUNT = {0: 0.98, 4: 1.1, 5: 1.5}

MIN_YEAR = 1850
MAX_YEAR = 1950
# Declared configuration bounds. 1000 mounts x 10 barrels per mount is the
# largest legal installed count in v1.
MAX_MOUNTS = 1000
MAX_BARRELS_PER_MOUNT = 10
MAX_INSTALLED_GUNS = MAX_MOUNTS * MAX_BARRELS_PER_MOUNT
MAX_ROUNDS_PER_GUN = 10000
MIN_BLOCK_COEFF = 0.3


def _fail(message: str, path: str) -> None:
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


def _year(value, path, low=MIN_YEAR, high=MAX_YEAR):
    return _count(value, path, low=low, high=high)


# --------------------------------------------------------------- conversions

def metres_to_feet(value_m, path="$.value_m"):
    return _number(value_m, path, positive=True) / M_PER_FT


def millimetres_to_inches(value_mm, path="$.value_mm"):
    """1 inch is exactly 25.4 mm, so 25.4 mm is 1 inch."""
    return _number(value_mm, path, positive=True) / (M_PER_INCH * 1000.0)


def metres_to_inches(value_m, path="$.value_m"):
    return _number(value_m, path, positive=True) * INCH_PER_M


def long_tons_to_tonnes(value_lt, path="$.value_lt"):
    return _number(value_lt, path) * LONG_TON_KG / 1000.0


def long_tons_to_kg(value_lt, path="$.value_lt"):
    return _number(value_lt, path) * LONG_TON_KG


def kg_to_long_tons(value_kg, path="$.value_kg"):
    return _number(value_kg, path) / LONG_TON_KG


def kilograms_to_pounds(value_kg, path="$.value_kg"):
    return _number(value_kg, path) / KG_PER_LB


def pounds_to_kilograms(value_lb, path="$.value_lb"):
    return _number(value_lb, path) * KG_PER_LB


def hp_to_kw(value_hp, path="$.value_hp"):
    return _number(value_hp, path, nonnegative=True) * KW_PER_HP


def _provenance(method, source_location, formula, inputs):
    return {
        "method": METHOD_VERSION,
        "kernel": method,
        "source_assembly": SOURCE_ASSEMBLY,
        "source_sha256": SOURCE_SHA256,
        "source_location": source_location,
        "source_scope": SOURCE_SCOPE,
        "formula": formula,
        "inputs": dict(inputs),
    }


# ----------------------------------------------------------------- gun kernel

def gun_date_factor(year, path="$.year"):
    """GunControl.cs:429 via MainForm.dateAdjCalc; sqrt branch ends at 1890."""
    value = _year(year, path)
    if value < 1890:
        return math.sqrt(1.0 - (1890.0 - value) / 66.666664)
    return 1.0


def estimated_shell_lb(calibre_in, barrel_calibres, date_factor,
                        path="$.battery"):
    """GunControl.cs:793 shellWeightCalc. Always the formula estimate."""
    calibre = _number(calibre_in, path + ".calibre_in", positive=True)
    length = _number(barrel_calibres, path + ".barrel_calibres", positive=True, low=1.0, high=100.0)
    factor = _number(date_factor, path + ".date_factor", positive=True)
    weight = calibre ** 3.0 / 1.9830943211886
    offset = length - 45.0
    weight *= (45.0 + (math.copysign(math.sqrt(abs(offset)), offset) if offset else 0.0)) / 45.0
    return weight * factor


def gun_mass_long_tons(calibre_in, barrel_calibres, date_factor, installed_guns, path="$.battery"):
    """GunControl.cs:817-825. Always uses the estimated shell, never an override."""
    calibre = _number(calibre_in, path + ".calibre_in", positive=True)
    length = _number(barrel_calibres, path + ".barrel_calibres", positive=True, low=1.0, high=100.0)
    count = _count(installed_guns, path + ".installed_guns", low=0, high=MAX_INSTALLED_GUNS)
    shell = estimated_shell_lb(calibre, length, date_factor, path)
    mass = shell * (length / 812.389434917877
                    * (1.0 + (1.0 / calibre) ** 2.3297949327695) * count)
    return mass


def mount_mass_long_tons(gun_mass_lt, calibre_in, gun_type, mount_type,
                         mount_adjustment=None, weight_adjustment=1.0,
                         shared_cradle=False, path="$.battery"):
    """GunControl.cs:826-905 plus the declared v1 shared-cradle selector.

    The 0.75 factor is the recovered ``weightAdjCalc`` (:480) value: it is the
    adjustment the original applies to the mount classes selected by
    ``gunsInMount`` indices 3, 6, 9 and 12 (``perMountCalc`` :636 gives those
    classes 2, 3, 4 and 5 barrels per mount). v1 does not reproduce the
    15-index selection table, because that table belongs to the two-group layout
    model this method does not claim; the recovered *value* is exposed through an
    explicit declared boolean instead.
    """
    calibre = _number(calibre_in, path + ".calibre_in", positive=True)
    gun_type_index = _enum(gun_type, GUN_TYPES, path + ".gun_type")
    mount_type_index = _enum(mount_type, MOUNT_TYPES, path + ".mount_type")
    if mount_adjustment is None:
        adjustment = MOUNT_ADJUSTMENT[mount_type_index]
    else:
        adjustment = _number(mount_adjustment, path + ".mount_adjustment", positive=True)
    weight_adj = _number(weight_adjustment, path + ".weight_adjustment", positive=True)
    if not isinstance(shared_cradle, bool):
        _fail("must be a boolean", path + ".shared_cradle")
    gun_mass = _number(gun_mass_lt, path, nonnegative=True)
    if calibre <= 1.0:
        mount = gun_mass
    else:
        base = MOUNT_BASE[mount_type_index]
        mount = 3.5 if base is None else base
        if adjustment < 0.6:
            mount *= GUN_TYPE_LOW_MOUNT.get(gun_type_index, 1.0)
        else:
            mount *= GUN_TYPE_HIGH_MOUNT.get(gun_type_index, 1.0)
        mount += 1.0 / calibre ** 0.313068808543972
        mount *= gun_mass
        if calibre > 10.0:
            mount *= 1.0 - 2.1623769 * calibre / 100.0
    mount *= weight_adj
    if shared_cradle:
        mount *= SHARED_CRADLE_WEIGHT_ADJUSTMENT
    return mount


def ammunition_long_tons(installed_guns, rounds_per_gun, shell_lb, path="$.battery"):
    """GunControl.cs:808-813, using the *effective* shell mass."""
    count = _count(installed_guns, path + ".installed_guns", low=0, high=MAX_INSTALLED_GUNS)
    rounds = _count(rounds_per_gun, path + ".rounds_per_gun", low=0, high=MAX_ROUNDS_PER_GUN)
    shell = _number(shell_lb, path + ".shell_lb", positive=True)
    return count * rounds * shell / LB_PER_LONG_TON * 1.2444444


def automatic_borne_weight_long_tons(gun_mass_lt, mount_adjustment, path="$.battery"):
    """Contract rule: 2 x gun_mass x mountAdj, per EngineControl.dispFactor.

    This automatic estimate feeds the machinery estimate only. It is never the
    balance borne weight, which comes from selected ledger masses.
    """
    mass = _number(gun_mass_lt, path, nonnegative=True)
    adjustment = _number(mount_adjustment, path + ".mount_adjustment", positive=True)
    return 2.0 * mass * adjustment


def balance_borne_weight_long_tons(selected_bare_gun_mass_lt, mount_adjustment, path="$.battery"):
    """Contract rule: selected BARE GUN mass x 2 x mountAdj, never mounts/armour."""
    return automatic_borne_weight_long_tons(selected_bare_gun_mass_lt, mount_adjustment, path)


def battery_estimates(calibre_mm, barrel_calibres, year, gun_type, mount_type, mount_count,
                      barrels_per_mount, rounds_per_gun, shell_mass_kg=None,
                      shared_cradle=False, path="$.battery"):
    """One battery row -> mutually exclusive gun, mount and ammunition estimates.

    The installed count is always ``mount_count x barrels_per_mount``; it is a
    declared installed count, never a broadside count.
    """
    calibre_mm_value = _number(calibre_mm, path + ".calibre_mm", positive=True, high=500.0)
    calibre_in = millimetres_to_inches(calibre_mm_value, path + ".calibre_mm")
    date_factor = gun_date_factor(_year(year, path + ".year"), path + ".year")
    estimated_lb = estimated_shell_lb(calibre_in, barrel_calibres, date_factor, path)
    if shell_mass_kg is None:
        effective_lb = estimated_lb
        shell_origin = "formula_estimate_sps_3b3"
    else:
        effective_lb = kilograms_to_pounds(
            _number(shell_mass_kg, path + ".shell_mass_kg", positive=True), path + ".shell_mass_kg")
        shell_origin = "declared_manual_override"
    mounts = _count(mount_count, path + ".mount_count", low=0, high=MAX_MOUNTS)
    per_mount = _count(barrels_per_mount, path + ".barrels_per_mount", low=1,
                       high=MAX_BARRELS_PER_MOUNT)
    if not isinstance(shared_cradle, bool):
        _fail("must be a boolean", path + ".shared_cradle")
    if shared_cradle and not 2 <= per_mount <= 5:
        _fail("a shared cradle is only declared for 2..5 barrels per mount", path + ".shared_cradle")
    count = mounts * per_mount
    if count > MAX_INSTALLED_GUNS:
        _fail("installed count exceeds the declared %d barrel limit" % (MAX_INSTALLED_GUNS,),
              path + ".mount_count")
    gun_lt = gun_mass_long_tons(calibre_in, barrel_calibres, date_factor, count, path)
    mount_lt = mount_mass_long_tons(gun_lt, calibre_in, gun_type, mount_type,
                                    shared_cradle=shared_cradle, path=path)
    ammunition_lt = ammunition_long_tons(count, rounds_per_gun, effective_lb, path)
    values = {
        "calibre_in": calibre_in,
        "calibre_mm": calibre_mm_value,
        "date_factor": date_factor,
        "shell_estimated_lb": estimated_lb,
        "shell_effective_lb": effective_lb,
        "shell_effective_kg": pounds_to_kilograms(effective_lb),
        "shell_origin": shell_origin,
        "mount_count": mounts,
        "barrels_per_mount": per_mount,
        "installed_guns": count,
        "guns_long_tons": gun_lt,
        "guns_t": long_tons_to_tonnes(gun_lt),
        "mounts_long_tons": mount_lt,
        "mounts_t": long_tons_to_tonnes(mount_lt),
        "ammunition_long_tons": ammunition_lt,
        "ammunition_t": long_tons_to_tonnes(ammunition_lt),
        "mount_adjustment": MOUNT_ADJUSTMENT[_enum(mount_type, MOUNT_TYPES, path + ".mount_type")],
        "automatic_borne_weight_long_tons": automatic_borne_weight_long_tons(
            gun_lt, MOUNT_ADJUSTMENT[_enum(mount_type, MOUNT_TYPES, path + ".mount_type")], path),
    }
    for key, value in values.items():
        if isinstance(value, float):
            _finite(value, "%s.%s" % (path, key))
    return {
        "values": values,
        "provenance": {
            "guns": _provenance("gun_mass_long_tons", "GunControl.cs:815",
                "gun_lt = shell_estimated_lb x barrel_calibres/812.389434917877 x "
                "(1 + (1/calibre_in)^2.3297949327695) x installed_guns",
                dict(calibre_in=calibre_in, barrel_calibres=barrel_calibres,
                     date_factor=date_factor, installed_guns=count)),
            "mounts": _provenance("mount_mass_long_tons", "GunControl.cs:826-905",
                "mount_lt = (mount base x gun-type factor + calibre^-0.313068808543972) x "
                "gun_lt x (1 - 2.1623769 x calibre/100 if calibre > 10) x weight_adj "
                "x (0.75 when a shared cradle is declared)",
                dict(calibre_in=calibre_in, gun_type=gun_type, mount_type=mount_type,
                     shared_cradle=bool(shared_cradle))),
            "ammunition": _provenance("ammunition_long_tons", "GunControl.cs:808",
                "ammunition_lt = installed_guns x rounds_per_gun x shell_effective_lb "
                "/ 2240 x 1.2444444",
                dict(installed_guns=count, rounds_per_gun=rounds_per_gun,
                     shell_effective_lb=effective_lb, shell_origin=shell_origin)),
        },
    }


# ------------------------------------------------------- hull proxy and power

def co_sharp(length_ft, beam_bulges_ft, block_coeff, path="$.hull"):
    """HullControl.cs:1347."""
    length = _number(length_ft, path + ".length_ft", positive=True)
    beam = _number(beam_bulges_ft, path + ".beam_bulges_ft", positive=True)
    block = _number(block_coeff, path + ".block_coeff", positive=True)
    return 0.4 * (beam / length * 6.0) ** (1.0 / 3.0) * math.sqrt(block / 0.52)


def effective_length_ft(length_ft, beam_bulges_ft, coefficient, stern, path="$.hull"):
    """HullControl.cs:1350-1361. Stern-conditioned, never a function of LWL alone."""
    length = _number(length_ft, path + ".length_ft", positive=True)
    beam = _number(beam_bulges_ft, path + ".beam_bulges_ft", positive=True)
    index = _enum(stern, STERN_TYPES, path + ".stern")
    if coefficient <= 0.0 or not math.isfinite(coefficient):
        _fail("coSharp must be positive and finite", path + ".co_sharp")
    if index == 2:
        return beam / coefficient + length
    if index == 1:
        return beam * 0.5 / coefficient + length
    return length


def natural_speed_kn(effective_length, path="$.hull.effective_length_ft"):
    """HullControl.cs:1362. Versioned SPS-derived indicator, not the Froude helper."""
    return math.sqrt(_number(effective_length, path, positive=True))


def waterplane_coefficient(block_coeff, stern, screws, path="$.hull"):
    """HullControl.cs:1313-1334.

    The recovered correction term is ``(block - 0.3) ** 1.55``; below a block
    coefficient of 0.3 that is a negative base with a fractional exponent, which
    the original evaluates to NaN. v1 reports that domain as unavailable rather
    than emitting NaN, a complex number or a made-up coefficient.
    """
    block = _number(block_coeff, path + ".block_coeff", positive=True)
    index = _enum(stern, STERN_TYPES, path + ".stern")
    count = _count(screws, path + ".screws", low=1, high=8)
    if block < MIN_BLOCK_COEFF:
        _fail("block coefficient %.6f is below the declared %.1f domain of the waterplane "
              "correction term" % (block, MIN_BLOCK_COEFF), path + ".block_coeff")
    effective = max(block, 0.4)
    ratio = effective / (1.006 - 0.0056 * effective ** -3.56)
    if index == 2:
        coefficient = min(0.262 + 0.81 * ratio, 1.0)
    elif index == 1:
        coefficient = min(0.262 + 0.79 * ratio, 1.0)
    elif count < 2 or block >= 0.75:
        coefficient = min(0.175 + 0.875 * ratio, 1.0)
    else:
        coefficient = 0.262 + 0.76 * ratio
    if block < 0.4:
        coefficient -= 0.0281 - (block - 0.3) ** 1.55
    return _finite(coefficient, path + ".co_waterplane")


def _finite(value, path, message="the derived result is not a finite real number"):
    if isinstance(value, complex) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _fail(message, path)
    return float(value)


def waterplane_area_sqft(coefficient, length_ft, beam_ft, path="$.hull"):
    """HullControl.cs:1335."""
    return (_number(coefficient, path + ".co_waterplane", positive=True)
            * _number(length_ft, path + ".length_ft", positive=True)
            * _number(beam_ft, path + ".beam_ft", positive=True))


def wetted_surface_sqft(length_ft, draught_ft, displacement_lt, path="$.hull"):
    """HullControl.cs:1269."""
    length = _number(length_ft, path + ".length_ft", positive=True)
    draught = _number(draught_ft, path + ".draught_ft", positive=True)
    displacement = _number(displacement_lt, path + ".displacement_long_tons", positive=True)
    return (length * draught) * 1.7 + (displacement * SEAWATER_CUBIC_FT_PER_LONG_TON / draught)


def crew_band(displacement_lt, path="$.hull"):
    """HullControl.cs:1272-1273."""
    displacement = _number(displacement_lt, path + ".displacement_long_tons", positive=True)
    maximum = int(displacement ** 0.75 * 0.65)
    return {"crew_max": maximum, "crew_min": int(maximum * 0.7692)}


def power_length_ft(speed_kn, length_ft, effective_length, path="$.speed"):
    """EngineControl.cs:440-451, reproducing the original branch verbatim."""
    speed = _number(speed_kn, path + ".speed_kn", positive=True, high=50.0)
    length = _number(length_ft, path + ".length_ft", positive=True)
    effect = _number(effective_length, path + ".effective_length_ft", positive=True)
    if speed <= 15.0:
        return length - (effect - length)
    if speed >= 25.0:
        return effect
    return (effect - length) * ((speed - 20.0) / 5.0) + length


def speed_hp(speed_kn, length_ft, effective_length, coefficient, displacement_lt,
             wetted_sqft_value, engine_year, path="$.power"):
    """EngineControl.cs:438-458."""
    length_hp = power_length_ft(speed_kn, length_ft, effective_length, path)
    if length_hp <= 0.0:
        _fail("effective power length must be positive", path + ".length_hp_ft")
    speed = _number(speed_kn, path + ".speed_kn", positive=True, high=50.0)
    displacement = _number(displacement_lt, path + ".displacement_long_tons", positive=True)
    wetted = _number(wetted_sqft_value, path + ".wetted_surface_sqft", positive=True)
    coefficient = _number(coefficient, path + ".co_sharp", positive=True)
    year = _year(engine_year, path + ".engine_year")
    power = ((displacement ** (2.0 / 3.0) / length_hp * coefficient * speed ** 4.0
              + 0.01 * wetted * speed ** 1.83) * speed / 184.1666667)
    if year < 1890:
        power *= 1.0 + (1890.0 - year) / 100.0
    return _finite(power, path + ".hp"), _finite(length_hp, path + ".length_hp_ft")


def resistance_split(speed_kn, length_ft, coefficient, displacement_lt, wetted_sqft_value,
                     path="$.power"):
    """EngineControl.cs:386-411. The wave term uses L, not the power length."""
    speed = _number(speed_kn, path + ".speed_kn", positive=True, high=50.0)
    length = _number(length_ft, path + ".length_ft", positive=True)
    displacement = _number(displacement_lt, path + ".displacement_long_tons", positive=True)
    wetted = _number(wetted_sqft_value, path + ".wetted_surface_sqft", positive=True)
    coefficient = _number(coefficient, path + ".co_sharp", positive=True)
    friction = 0.01 * wetted * speed ** 1.83
    wave = displacement ** (2.0 / 3.0) / length * coefficient * speed ** 4.0
    total = friction + wave
    if total <= 0.0:
        return {"friction_hp_factor": friction, "wave_hp_factor": wave,
                "friction_fraction": None, "friction_fraction_status": "unavailable"}
    fraction = friction / total
    return {"friction_hp_factor": friction, "wave_hp_factor": wave,
            "friction_fraction": fraction, "friction_fraction_status": "completed"}


# ------------------------------------------------------------------ machinery

def engine_coefficient(kind, year, path="$.machinery"):
    """EngineControl.cs:542-601; exactly one selected kind."""
    index = _enum(kind, ENGINE_KINDS, path + ".kind")
    value = _year(year, path + ".year")
    if index == 0:
        if value < 1885:
            return 1.2 + (value - 1860) * 0.05
        if value < 1950:
            return 2.45 + (value - 1885) * 0.025
        return 4.075
    if index == 1:
        if value < 1906:
            return 1.2 + (value - 1860) * 0.05
        if value < 1911:
            return 3.5 + (value - 1906)
        if value < 1950:
            return 7.5 + (value - 1910) * 0.025
        return 8.5
    if value < 1898:
        return 1.2 + (value - 1860) * 0.05
    if value < 1903:
        return 1.0 + (value - 1898) * 0.5
    if value < 1910:
        return 4 + (value - 1903)
    if value < 1950:
        return 11.0 + (value - 1910) * 0.2
    return 19.0


def machinery_long_tons(hp_max, year, kind, coal_pct, displacement_lt, borne_lt,
                        armour_lt, misc_lt, path="$.machinery"):
    """EngineControl.cs:602-624 with the declared selected-mass inputs.

    ``borne_lt`` is the *automatic* battery estimate, ``armour_lt`` and
    ``misc_lt`` are explicitly classified selected masses. Nothing here reads a
    residual or any hidden internal state.
    """
    power = _number(hp_max, path + ".hp_max", positive=True)
    value = _year(year, path + ".year")
    coal = _number(coal_pct, path + ".coal_pct", nonnegative=True, low=0.0, high=100.0)
    displacement = _number(displacement_lt, path + ".displacement_long_tons", positive=True)
    borne = _number(borne_lt, path + ".borne_long_tons", nonnegative=True)
    armour = _number(armour_lt, path + ".armour_long_tons", nonnegative=True)
    misc = _number(misc_lt, path + ".misc_long_tons", nonnegative=True)
    denominator = engine_coefficient(kind, value, path) * (1.1 - coal / 1000.0)
    if denominator <= 0.0:
        _fail("the engine coefficient must stay positive", path + ".kind")
    raw = power / denominator
    if value < 1890:
        raw /= 1.0 + (1890.0 - value) / 100.0
    load = raw + borne * 8.0 + armour + misc
    if load <= 0.0:
        _fail("the machinery load term must stay positive", path + ".displacement_long_tons")
    displacement_factor = min(displacement / load, 10.0)
    weight = raw / 2.0
    if 600.0 <= displacement < 5000.0 and displacement_factor < 1.0:
        weight *= displacement_factor ** (1.0 - displacement / 5000.0)
    elif displacement < 600.0 and displacement_factor < 1.0:
        weight *= displacement_factor ** 0.88
    return {"raw_engine_long_tons": _finite(raw, path + ".raw_engine_long_tons"),
            "displacement_factor": _finite(displacement_factor, path + ".displacement_factor"),
            "machinery_long_tons": _finite(weight, path + ".machinery_long_tons")}


def bunker_normal_long_tons(year, kind, range_nm, coal_pct, displacement_lt, hp_cruise,
                            cruise_speed_kn, path="$.fuel"):
    """EngineControl.cs:888-917. Normal bunker only; 1.8x is a display estimate."""
    distance = _number(range_nm, path + ".range_nm", positive=True)
    coal = _number(coal_pct, path + ".coal_pct", nonnegative=True, low=0.0, high=100.0)
    value = _year(year, path + ".year")
    index = _enum(kind, ENGINE_KINDS, path + ".kind")
    displacement = _number(displacement_lt, path + ".displacement_long_tons", positive=True)
    power = _number(hp_cruise, path + ".hp_cruise", positive=True)
    speed = _number(cruise_speed_kn, path + ".cruise_speed_kn", positive=True)
    bunker = distance / (1.0 + 0.4 * (100.0 - coal) / 100.0)
    if index in (0, 1):
        bunker /= 1.0 - (1910.0 - value) / 70.0
    elif value < 1898:
        bunker /= 1.0 - (1910.0 - value) / 70.0
    elif value < 1920:
        bunker /= 1.0 + (value - 1910.0) / 20.0
    elif value < 1950:
        bunker /= 1.5 + (value - 1920.0) / 60.0
    else:
        bunker /= 2.0
    bunker /= 1.8 / power * 7000.0 * speed * 0.1
    bunker += displacement * 0.005
    return _finite(bunker, path + ".normal_bunker_long_tons")


# -------------------------------------------------------- structural strength

def structure_surface_density_lb_sqft(structure_lt, wetted_sqft_value, length_ft,
                                     freeboard_ft, waterplane_sqft, path="$.structure"):
    """PerformanceControl.cs:508. Result is lb/ft^2, an SPS source convention."""
    structure = _number(structure_lt, path + ".structure_long_tons", nonnegative=True)
    wetted = _number(wetted_sqft_value, path + ".wetted_surface_sqft", positive=True)
    length = _number(length_ft, path + ".length_ft", positive=True)
    freeboard = _number(freeboard_ft, path + ".freeboard_ft", positive=True)
    waterplane = _number(waterplane_sqft, path + ".waterplane_area_sqft", positive=True)
    denominator = wetted + 2.0 * length * freeboard + waterplane
    if denominator <= 0.0:
        _fail("the protected surface must stay positive", path + ".wetted_surface_sqft")
    return _finite(structure * LB_PER_LONG_TON / denominator, path + ".structure_lb_sqft")


def strength_date_factor(hull_year, path="$.structure.hull_year"):
    value = _year(hull_year, path)
    return 1.0 - (1900.0 - value) / 100.0 if value < 1900 else 1.0


def strength_cross_coefficient(wetted_sqft_value, length_ft, freeboard_ft, waterplane_sqft,
                               beam_ft, draught_ft, displacement_lt, broadside_lb, borne_lt,
                               armour_lt, conning_lt, hp_max, concentration, super_factor,
                               hull_year, path="$.structure"):
    """Per LONG TON of structure, from PerformanceControl.cs:546-563.

    ``broadside_lb`` is projectile POUNDS while every other mass in the same
    empirical expression is LONG TONS. That mixed-unit convention is the
    recovered source's own; it is preserved deliberately and never converted.
    """
    wetted = _number(wetted_sqft_value, path + ".wetted_surface_sqft", positive=True)
    length = _number(length_ft, path + ".length_ft", positive=True)
    freeboard = _number(freeboard_ft, path + ".freeboard_ft", positive=True)
    waterplane = _number(waterplane_sqft, path + ".waterplane_area_sqft", positive=True)
    beam = _number(beam_ft, path + ".beam_ft", positive=True)
    draught = _number(draught_ft, path + ".draught_ft", positive=True)
    displacement = _number(displacement_lt, path + ".displacement_long_tons", positive=True)
    broadside = _number(broadside_lb, path + ".broadside_lb", nonnegative=True)
    borne = _number(borne_lt, path + ".borne_long_tons", nonnegative=True)
    armour = _number(armour_lt, path + ".armour_long_tons", nonnegative=True)
    conning = _number(conning_lt, path + ".conning_long_tons", nonnegative=True)
    power = _number(hp_max, path + ".hp_max", nonnegative=True)
    factor = _number(concentration, path + ".concentration", positive=True)
    super_factor = _number(super_factor, path + ".super_factor", positive=True)
    denominator = wetted + 2.0 * length * freeboard + waterplane
    if denominator <= 0.0:
        _fail("the protected surface must stay positive", path + ".wetted_surface_sqft")
    section = beam * (draught + freeboard)
    if section <= 0.0:
        _fail("beam x (draught + freeboard) must be positive", path + ".beam_ft")
    load = displacement + ((broadside + borne + armour + conning) * (factor * super_factor)
                           + max(power, 0.0) / 100.0)
    if load <= 0.0 or displacement <= 0.0:
        _fail("the cross-section load term must stay positive", path + ".displacement_long_tons")
    per_ton = (LB_PER_LONG_TON / denominator) / math.sqrt(section) / (load / displacement) * 0.6
    return per_ton * strength_date_factor(hull_year, path + ".hull_year")


def strength_long_coefficient(length_ft, draught_ft, freeboard_ft, displacement_lt, belt_ends_lt,
                              borne_lt, armour_lt, super_factor_long, hull_year,
                              path="$.structure"):
    """Per LONG TON of structure, from PerformanceControl.cs:591-607."""
    length = _number(length_ft, path + ".length_ft", positive=True)
    draught = _number(draught_ft, path + ".draught_ft", positive=True)
    freeboard = _number(freeboard_ft, path + ".freeboard_ft", positive=True)
    displacement = _number(displacement_lt, path + ".displacement_long_tons", positive=True)
    belt_ends = _number(belt_ends_lt, path + ".belt_ends_long_tons", nonnegative=True)
    borne = _number(borne_lt, path + ".borne_long_tons", nonnegative=True)
    armour = _number(armour_lt, path + ".armour_long_tons", nonnegative=True)
    super_long = _number(super_factor_long, path + ".super_factor_long", positive=True)
    depth = draught + freeboard
    if depth <= 0.0:
        _fail("draught + freeboard must be positive", path + ".draught_ft")
    load = (length / depth) ** 2.0 * (displacement + belt_ends * 3.0
                                      + (borne + armour) * super_long * 2.0)
    if load <= 0.0:
        _fail("the longitudinal load term must stay positive", path + ".displacement_long_tons")
    per_ton = 850.0 / load * strength_date_factor(hull_year, path + ".hull_year")
    return per_ton


def strength_composite(cross, longitudinal, path="$.structure"):
    """PerformanceControl.cs:610-622."""
    cross_value = _number(cross, path + ".cross", nonnegative=True)
    long_value = _number(longitudinal, path + ".long", nonnegative=True)
    if cross_value <= 0.0 or long_value <= 0.0:
        _fail("both strength scores must be positive", path + ".composite")
    if cross_value > long_value:
        return _finite(long_value * (cross_value / long_value) ** 0.25, path + ".composite")
    return _finite(cross_value * (long_value / cross_value) ** 0.1, path + ".composite")


def composite_coefficient(cross_coefficient, long_coefficient, path="$.structure"):
    """The composite score is linear in structure mass; invert it directly."""
    cross_value = _number(cross_coefficient, path + ".cross_coefficient", positive=True)
    long_value = _number(long_coefficient, path + ".long_coefficient", positive=True)
    if cross_value > long_value:
        return _finite(long_value * (cross_value / long_value) ** 0.25, path + ".composite_coefficient")
    return _finite(cross_value * (long_value / cross_value) ** 0.1, path + ".composite_coefficient")


def required_structure_long_tons(target_composite, cross_coefficient, long_coefficient,
                                 path="$.structure"):
    """Required adjustable structure from UNIT coefficients, never from a residual."""
    target = _number(target_composite, path + ".strength_target", positive=True)
    coefficient = composite_coefficient(cross_coefficient, long_coefficient, path)
    return _finite(target / coefficient, path + ".required_structure_long_tons")


# ------------------------------------------------- adapted concept performance

def room_hull_ratio(magazine_lt, displacement_lt, borne_lt, machinery_lt, misc_vital_lt,
                    misc_hull_lt, space_hull_fraction, bulkhead_beam_m=None, beam_m=None,
                    bulkhead_lt=None, path="$.balance"):
    """PerformanceControl.cs:265-305 with explicit selected masses.

    The recovered program keys the beam restriction on bulkhead mass. Here
    that mass is the explicitly selected bulkhead allocation:
    the narrowing applies only when the selected bulkhead mass exceeds 0.1 long
    ton. Beam is in metres, because the restriction is applied against a declared
    metric bulkhead beam.
    """
    magazine = _number(magazine_lt, path + ".magazine_long_tons", nonnegative=True)
    displacement = _number(displacement_lt, path + ".displacement_long_tons", positive=True)
    borne = _number(borne_lt, path + ".borne_long_tons", nonnegative=True)
    machinery = _number(machinery_lt, path + ".machinery_long_tons", nonnegative=True)
    vital = _number(misc_vital_lt, path + ".misc_vital_long_tons", nonnegative=True)
    hull_misc = _number(misc_hull_lt, path + ".misc_hull_long_tons", nonnegative=True)
    space = _number(space_hull_fraction, path + ".space_hull_fraction", low=0.0)
    if space >= 1.0:
        _fail("must be below 1", path + ".space_hull_fraction")
    ratio = (magazine + displacement * 0.02 + borne * 6.4 + machinery * 3.0 + vital + hull_misc) \
        / (displacement * 0.94) / (1.0 - space)
    if bulkhead_beam_m is not None:
        mass = 0.0 if bulkhead_lt is None else _number(bulkhead_lt, path + ".bulkhead_long_tons",
                                                        nonnegative=True)
        if mass > 0.1:
            beam = _number(beam_m, path + ".beam_m", positive=True)
            bulkhead = _number(bulkhead_beam_m, path + ".bulkhead_beam_m", positive=True)
            if bulkhead > beam:
                _fail("must not exceed beam_m", path + ".bulkhead_beam_m")
            ratio *= beam / bulkhead
    return _finite(ratio, path + ".room_hull")


def room_deck_ratio(waterplane_sqft, space_deck_fraction, crew_min, freeboard_ft,
                    path="$.balance"):
    """PerformanceControl.cs:307-330. The single declared representative freeboard."""
    waterplane = _number(waterplane_sqft, path + ".waterplane_area_sqft", positive=True)
    space = _number(space_deck_fraction, path + ".space_deck_fraction", low=0.0)
    if space >= 1.0:
        _fail("must be below 1", path + ".space_deck_fraction")
    crew = _count(crew_min, path + ".crew_min", low=1, high=1000000)
    freeboard = _number(freeboard_ft, path + ".freeboard_ft", positive=True)
    return waterplane / SEAWATER_CUBIC_FT_PER_LONG_TON / 15.0 * (1.0 - space) / crew * freeboard


def stability_score(conning_lt, borne_lt, battery_armour_lt, misc_hull_lt, misc_deck_lt,
                    misc_above_lt, belt_upper_lt, belt_main_lt, belt_ends_lt, deck_lt,
                    structure_lt, room_deck, machinery_lt, misc_vital_lt, misc_void_lt,
                    displacement_lt, beam_bulges_ft, length_beam, draught_ft, freeboard_ft,
                    super_factor, steadiness, path="$.balance"):
    """PerformanceControl.cs:332-343 with the structural bracket replaced.

    The whole ``(engine.hullWeight + guns.gunsWeight - guns.borneWeight)`` term
    of the recovered expression is replaced by the selected structural mass.
    No residual and no hidden double accounting survives.
    """
    conning = _number(conning_lt, path + ".conning_long_tons", nonnegative=True)
    borne = _number(borne_lt, path + ".borne_long_tons", nonnegative=True)
    battery_armour = _number(battery_armour_lt, path + ".battery_armour_long_tons", nonnegative=True)
    misc_hull = _number(misc_hull_lt, path + ".misc_hull_long_tons", nonnegative=True)
    misc_deck = _number(misc_deck_lt, path + ".misc_deck_long_tons", nonnegative=True)
    misc_above = _number(misc_above_lt, path + ".misc_above_long_tons", nonnegative=True)
    belt_upper = _number(belt_upper_lt, path + ".belt_upper_long_tons", nonnegative=True)
    belt_main = _number(belt_main_lt, path + ".belt_main_long_tons", nonnegative=True)
    belt_ends = _number(belt_ends_lt, path + ".belt_ends_long_tons", nonnegative=True)
    deck = _number(deck_lt, path + ".armour_deck_long_tons", nonnegative=True)
    structure = _number(structure_lt, path + ".structure_long_tons", nonnegative=True)
    deck_ratio = _number(room_deck, path + ".room_deck", nonnegative=True)
    machinery = _number(machinery_lt, path + ".machinery_long_tons", nonnegative=True)
    vital = _number(misc_vital_lt, path + ".misc_vital_long_tons", nonnegative=True)
    void = _number(misc_void_lt, path + ".misc_void_long_tons", nonnegative=True)
    displacement = _number(displacement_lt, path + ".displacement_long_tons", positive=True)
    beam = _number(beam_bulges_ft, path + ".beam_bulges_ft", positive=True)
    ratio = _number(length_beam, path + ".length_beam", positive=True)
    draught = _number(draught_ft, path + ".draught_ft", positive=True)
    freeboard = _number(freeboard_ft, path + ".freeboard_ft", positive=True)
    super_value = _number(super_factor, path + ".super_factor", positive=True)
    steadiness_value = _number(steadiness, path + ".steadiness", low=0.0, high=100.0)
    score = (conning * 5.0 + (borne + battery_armour) * (2.0 * super_value - 1.0) * 4.0
             + misc_hull * 2.0 + misc_deck * 3.0 + misc_above * 4.0 + belt_upper * 2.0
             + belt_main + belt_ends + deck
             + structure * 1.5 * freeboard / draught)
    if deck_ratio < 1.0:
        score += (machinery + vital + void) * (1.0 - deck_ratio) ** 2.0
    if score > 0.0:
        score = (math.sqrt(displacement * (beam / draught) / score * 0.5)
                 * (8.76755 / ratio) ** 0.25)
    adjusted = score * ((50.0 - steadiness_value) / 150.0 + 1.0)
    return {"stability_score": _finite(score, path + ".stability_score"),
            "stability_adjusted": _finite(adjusted, path + ".stability_adjusted")}


def seaboat_score(stability, freeboard_ft, displacement_lt, beam_bulges_ft, length_ft,
                  belt_ends_lt, structure_lt, borne_lt, battery_armour_lt, super_factor_long,
                  draught_ft, friction_fraction, path="$.balance"):
    """PerformanceControl.cs:403-419, with hullWeight/3 replaced by structure/3."""
    stability_value = _number(stability, path + ".stability_score", positive=True)
    freeboard = _number(freeboard_ft, path + ".freeboard_ft", positive=True)
    displacement = _number(displacement_lt, path + ".displacement_long_tons", positive=True)
    beam = _number(beam_bulges_ft, path + ".beam_bulges_ft", positive=True)
    length = _number(length_ft, path + ".length_ft", positive=True)
    belt_ends = _number(belt_ends_lt, path + ".belt_ends_long_tons", nonnegative=True)
    structure = _number(structure_lt, path + ".structure_long_tons", nonnegative=True)
    borne = _number(borne_lt, path + ".borne_long_tons", nonnegative=True)
    armour = _number(battery_armour_lt, path + ".battery_armour_long_tons", nonnegative=True)
    super_long = _number(super_factor_long, path + ".super_factor_long", positive=True)
    draught = _number(draught_ft, path + ".draught_ft", positive=True)
    denominator = displacement + belt_ends * 3.0 + structure / 3.0 + (borne + armour) * super_long
    if denominator <= 0.0:
        _fail("the seaboat load term must stay positive", path + ".displacement_long_tons")
    score = (math.sqrt(freeboard / (2.4 * displacement ** 0.2))
             * ((stability_value * 5.0 * (beam / length)) ** 0.2
                * math.sqrt(freeboard / length * 20.0)
                * (displacement / denominator)) * 8.0)
    if draught / beam < 0.3:
        score *= math.sqrt((draught / beam) / 0.3)
    if friction_fraction is None:
        score *= 0.3025
        fraction_used = None
    else:
        fraction = _number(friction_fraction, path + ".friction_fraction", nonnegative=True)
        if fraction < 0.55:
            score *= fraction ** 2.0
        else:
            score *= 0.3025
        fraction_used = fraction
    return (_finite(min(score, 2.0), path + ".seaboat"), fraction_used)


def steadiness_score(steadiness, seaboat, path="$.balance"):
    """PerformanceControl.cs:419. A 0..100 score, never a period in seconds."""
    declared = _number(steadiness, path + ".steadiness", low=0.0, high=100.0)
    value = _number(seaboat, path + ".seaboat", positive=True)
    return min(declared * value, 100.0)


def seakeeping_score(seaboat, steadiness_adjusted, path="$.balance"):
    """PerformanceControl.cs:441-448."""
    value = _number(seaboat, path + ".seaboat", positive=True)
    adjusted = _number(steadiness_adjusted, path + ".steadiness_adjusted", nonnegative=True)
    return value * adjusted / 50.0 if adjusted < 50.0 else value
