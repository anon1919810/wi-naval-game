"""Whole-battery gun, mount and layout-armour totals, as an independent kernel.

This is a pure function over a finite declared domain. It never touches a
project, a ledger or a file, it never clamps an out-of-domain value, and it never
reads an unknown input as zero: a missing declared fact produces a structured
unavailable diagnostic and a null reading, while a wrong type, a wrong sign and
an out-of-domain number are refused.

It is deliberately **not** part of the adapted configuration method and it is not
the two-group layout method either. The configuration keeps
``sps-3b3-adapted-v1`` and the layout keeps ``sps-3b3-battery-layout-v1``; this
kernel carries its own ``sps-3b3-battery-totals-v1``, so a reader can always tell
which numbers came from which method.

Numerical source
----------------
Recovered ``SpringSharpMono`` 3.0.3032.29945, the same original binary the
adapted concept kernels and :mod:`battery_layout` use (identical assembly string
and SHA256, re-exported through :mod:`battery_layout` so the three can never
drift apart):

* ``GunControl.cs:564-634`` ``mountsCalc`` — the whole-battery assembly of the
  two mount groups, the mount-count weighted ``weightAdj`` and the final
  ``totalWeight = gunWeight + mountWeight + armWeight``
* ``GunControl.cs:815-906`` ``gunWeightCalc`` — the installed-barrel gun mass and
  the single ``mountWeight *= weightAdj``
* ``GunControl.cs:1127-1292`` ``armWeightCalc``/``diameterCalc`` — the complete
  two-group gun-house and barbette armour already reproduced by the layout kernel
* ``MainForm.cs:22`` the empirical mass constant ``INCH``

What this kernel adds over :mod:`battery_layout`
------------------------------------------------
The layout kernel reads one layout's position-weighted freeboard, its height
factor and its complete gun-house/barbette armour. It deliberately claims **no
whole-battery gun or mount mass**. This kernel reads the same recovered
assembly's ``gunWeightCalc`` once for the whole battery:

* the installed barrel count is the sum of the two groups' installed barrels
  (``mounts x barrels_per_mount`` each), never a broadside count;
* the mount mass is one ``mountWeight`` for the whole battery, multiplied by the
  **mount-count weighted** ``weightAdj = (wa1 x mounts1 + wa2 x mounts2) /
  (mounts1 + mounts2)`` the recovered ``mountsCalc`` computes at ``:592``;
* the 0.75 shared-cradle factor is already inside ``weightAdj``, so this kernel
  passes ``shared_cradle=False`` and never multiplies it a second time;
* the source total is ``guns + mounts + complete layout armour`` and excludes
  ammunition (``magazineWeight`` is a separate recovered field).

Recovered quirks kept verbatim
-----------------------------
* ``weightAdj`` is combined by **mount count**, not by barrel count. Two mounts
  of a shared-cradle twin and one mount of a single gun give ``(2 x 0.75 + 1) /
  3``, not ``0.8`` and not a second ``x 0.75``.
* the mount-count weighted average divides by the total mount count and falls
  back to ``1`` only when ``mounts1 + mounts2 == 0``.
* two groups whose referenced rows declare **different barrel lengths** are an
  older engineering the layout armour model still reads. This whole-battery
  total is then **unavailable**, because the recovered ``gunWeightCalc`` reads
  one ``calLength``; the project is not refused and the layout armour is not
  erased.
* a declared zero mount count multiplies every term of the recovered gun and
  mount expressions, so it is a determined zero and not a missing number.

Scope
-----
This is an independent empirical *estimate* of one whole battery's gun, mount and
layout-armour mass. It is not a form, not a centre of gravity, not a firing arc,
not a developed armour area, not structural strength, not whole-program parity
and not validated against any real ship.
"""

from __future__ import annotations

import math

try:
    from . import battery_layout as layout_kernel
    from . import concept_estimates as kernels
except ImportError:                                   # pragma: no cover - direct import
    import battery_layout as layout_kernel
    import concept_estimates as kernels

METHOD_VERSION = "sps-3b3-battery-totals-v1"
SOURCE_LOCATION = ("GunControl.cs:564-634, 815-906, 1127-1292; MainForm.cs:22")
SOURCE_ASSEMBLY = layout_kernel.SOURCE_ASSEMBLY
SOURCE_SHA256 = layout_kernel.SOURCE_SHA256
SOURCE_SCOPE = (
    "Independent empirical whole-battery estimate of the recovered gun, mount and "
    "complete two-group gun-house/barbette armour masses of one declared layout, "
    "reproduced once for the whole battery from the recovered 3b3 mountsCalc and "
    "gunWeightCalc expressions with the mount-count weighted weightAdj; it is not "
    "a form, not a centre of gravity, not a firing arc, not developed armour "
    "geometry, not structural strength, not whole-program parity and not validated "
    "against any real ship. The per-row gun, mount and ammunition estimates stay "
    "sps-3b3-adapted-v1 and the layout freeboard, height factor and mixed armour "
    "stay sps-3b3-battery-layout-v1."
)

DEFAULT_PATH = "$.concept_design.battery_layouts"

ASSUMPTIONS = (
    "the installed barrel count of the whole battery is the sum of the two groups' "
    "installed barrels, each group being its mount count times its recovered "
    "barrels per mount; it is never a broadside count and never an ammunition input",
    "the mount mass is one recovered mountWeight for the whole battery, multiplied by "
    "the mount-count weighted weightAdj = (wa1 x mounts1 + wa2 x mounts2) / (mounts1 + "
    "mounts2) that the recovered mountsCalc computes; the weighting is by mount count, "
    "never by barrel count, so two shared twin mounts and one single mount give "
    "(2 x 0.75 + 1) / 3",
    "the shared-cradle 0.75 factor is already inside weightAdj, so this kernel passes "
    "shared_cradle=False and never multiplies the recovered factor a second time",
    "the two active groups must agree on one calibre, one barrel length, one year, one "
    "gun class and one mount class; an older layout whose two referenced rows declare "
    "different barrel lengths keeps its layout armour reading but has no whole-battery "
    "gun or mount total, and the project is not refused",
    "a manual shell mass and the ammunition rounds do not enter the gun or mount "
    "expressions; the recovered gunWeightCalc always reads the estimated shell",
    "the source total is guns + mounts + complete layout armour and excludes "
    "ammunition; an unknown armour blocks only that total and never erases a known gun "
    "or mount reading",
    "an absent group and a declared zero group are different: two absent groups leave "
    "the whole battery unknown, while a declared zero mount count multiplies every term "
    "of the recovered gun and mount expressions into a determined zero",
    "the recovered original is float32; this kernel is float64, so the source's float32 "
    "rounding is the stated comparison tolerance and no case is clamped to reach it",
)

# The exported value keys. Everything else in ``values`` is supporting provenance.
VALUE_KEYS = ("guns_t", "mounts_t", "armour_t", "total_t")


def _diag(code, message, path, field=None, blocking=False):
    return {"code": code, "severity": "error" if blocking else "warning", "field": field,
            "path": path, "message": message, "blocking": blocking}


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _group(reading, name):
    """One group reading, or a safe absent stand-in when it is missing."""
    groups = reading.get("groups") if isinstance(reading, dict) else None
    group = groups.get(name) if isinstance(groups, dict) else None
    if not isinstance(group, dict):
        return {"state": "absent", "battery_id": None, "mounts": 0, "barrels": 0,
                "per_mount": 0, "mount_selector": None, "weight_adjustment": 1}
    return group


def _empty_values():
    return {
        "guns_t": None, "mounts_t": None, "armour_t": None, "total_t": None,
        "guns_long_tons": None, "mounts_long_tons": None, "armour_long_tons": None,
        "total_long_tons": None, "installed_guns": None, "mounts": None,
        "weight_adjustment": None, "calibre_mm": None, "calibre_in": None,
        "barrel_calibres": None, "year": None, "date_factor": None, "gun_type": None,
        "mount_type": None,
    }


def _tonnes(value_lt, path):
    if value_lt is None:
        return None
    return kernels.long_tons_to_tonnes(value_lt, path + ".long_tons")


def _no_facts():
    """The shared fact set before (or after failing) agreement."""
    return {"calibre_mm": None, "barrel_calibres": None, "year": None, "gun_type": None,
            "mount_type": None}


def _shared_facts(groups, index, path, diagnostics, provenance):
    """One calibre, barrel length, year, gun class and mount class for the battery.

    Only the **active** groups (a known positive mount count) are read, exactly as
    the recovered expression reads them. The barrel length is deliberately kept
    out of the layout kernel's own agreement check, so two rows that disagree on it
    are reported here rather than refused there.
    """
    facts = _no_facts()
    seen = {}
    for group in groups:
        mounts = _count(group.get("mounts"))
        if not mounts:
            continue
        row = index.get(group.get("battery_id"))
        if row is None:
            diagnostics.append(_diag(
                "battery_totals.unknown",
                "an active group has no referenced battery row, so its calibre, barrel length, "
                "year, gun class and mount class are unknown", path))
            return _no_facts(), provenance
        for key in facts:
            value = row.get(key)
            if isinstance(value, bool) or value is None:
                diagnostics.append(_diag(
                    "battery_totals.unknown",
                    "an active group's referenced row does not declare its %s, so the whole "
                    "battery total is unknown" % (key,), path))
                return _no_facts(), provenance
            previous = seen.get(key)
            if previous is not None and previous[1] != value:
                diagnostics.append(_diag(
                    "battery_totals.contradiction",
                    "%s of the active groups disagrees (%r and %r); the recovered gun and mount "
                    "expressions read one shared value, so the whole-battery total is unavailable "
                    "rather than guessed. The layout armour reading is not affected"
                    % (key, previous[1], value), path, key))
                # One contradicted shared fact makes every shared fact unusable: a
                # partially filled set would let the caller pair a stale value with
                # the new one and silently blur two different batteries together.
                return _no_facts(), provenance
            seen[key] = (group.get("battery_id"), value)
            facts[key] = value
    return facts, provenance


def _weight_adjustment(groups, mounts_total, path, diagnostics):
    """mountsCalc ``:590-597``: weighted by mount count, ``1`` when there are none."""
    if mounts_total == 0:
        return 1.0
    weighted = 0.0
    counted = 0
    for group in groups:
        mounts = _count(group.get("mounts"))
        if not mounts:
            continue
        selector = group.get("mount_selector")
        if selector is None:
            diagnostics.append(_diag(
                "battery_totals.unknown",
                "an active group's recovered gunsInMount selector is unknown, so the whole-battery "
                "weight adjustment is unknown; it is not reverse-derived from the barrel count",
                path))
            return None
        weighted += layout_kernel.WEIGHT_ADJUSTMENT_BY_SELECTOR[selector] * mounts
        counted += mounts
    if counted == 0:
        return 1.0
    return weighted / float(counted)


def _provenance(identity, groups, layout_provenance):
    return {
        "method": METHOD_VERSION,
        "kernel": "battery_totals_whole_battery_long_tons",
        "source_assembly": SOURCE_ASSEMBLY,
        "source_sha256": SOURCE_SHA256,
        "source_location": SOURCE_LOCATION,
        "source_scope": SOURCE_SCOPE,
        "formula": (
            "installed_guns = sum over the two groups of mounts x barrels_per_mount; "
            "weight_adjustment = (wa1 x mounts1 + wa2 x mounts2) / (mounts1 + mounts2), or 1 "
            "when there are no mounts; guns_lt = gun_mass_long_tons(calibre_in, "
            "barrel_calibres, gun_date_factor(year), installed_guns); mounts_lt = "
            "mount_mass_long_tons(guns_lt, calibre_in, gun_type, mount_type, weight_adjustment, "
            "shared_cradle=False); armour_lt = the layout kernel's complete two-group armour; "
            "total_lt = guns_lt + mounts_lt + armour_lt, excluding ammunition"),
        "assumptions": " ".join(ASSUMPTIONS),
        "inputs": {
            "layout_id": identity,
            "shared_cradle": False,
            "group1": {"battery_id": groups[0].get("battery_id"),
                       "mounts": _count(groups[0].get("mounts")),
                       "barrels": _count(groups[0].get("barrels")),
                       "mount_selector": groups[0].get("mount_selector")},
            "group2": {"battery_id": groups[1].get("battery_id"),
                       "mounts": _count(groups[1].get("mounts")),
                       "barrels": _count(groups[1].get("barrels")),
                       "mount_selector": groups[1].get("mount_selector")},
            "layout_method_version": (layout_provenance or {}).get("method"),
        },
    }


def evaluate(layout, batteries, layout_reading=None, path=DEFAULT_PATH):
    """One whole battery's gun, mount and layout-armour totals.

    ``layout`` and ``batteries`` are the same declarations
    :func:`battery_layout.evaluate` reads. ``layout_reading`` is that kernel's own
    result; it is recomputed here only when it is not supplied, so the caller
    never recomputes a freeboard, a height factor or an armour mass on the client.

    Returns a JSON-serialisable dict with at least ``id``, ``method_version``,
    ``status``, ``values``, ``diagnostics`` and ``provenance``. ``values`` carries
    ``guns_t``, ``mounts_t``, ``armour_t`` and ``total_t`` (plus the same figures
    in the source's long tons). An unknown value is ``None`` and is never read as
    a zero.
    """
    diagnostics = []
    reading = layout_reading
    if not isinstance(reading, dict):
        reading = layout_kernel.evaluate(layout, batteries, path)
    identity = reading.get("id")
    if identity is None and isinstance(layout, dict):
        identity = layout.get("id")
    first = _group(reading, "group1")
    second = _group(reading, "group2")
    groups = (first, second)
    values = _empty_values()
    index = layout_kernel._battery_index(batteries)
    facts = _no_facts()
    provenance = _provenance(identity, groups, reading.get("provenance"))

    def finish(status):
        provenance["inputs"].update(
            calibre_mm=facts["calibre_mm"], calibre_in=values["calibre_in"],
            barrel_calibres=facts["barrel_calibres"], year=facts["year"],
            date_factor=values["date_factor"], gun_type=facts["gun_type"],
            mount_type=facts["mount_type"],
            installed_guns=values["installed_guns"], mounts=values["mounts"],
            weight_adjustment=values["weight_adjustment"])
        for key in VALUE_KEYS:
            provenance["inputs"][key] = values[key]
        return {"id": identity, "method_version": METHOD_VERSION, "status": status,
                "values": values, "diagnostics": diagnostics, "provenance": provenance}

    if first.get("state") == "absent" and second.get("state") == "absent":
        diagnostics.append(_diag(
            "battery_totals.unconfigured",
            "neither mount group is configured, so the whole battery has no mount count and no "
            "gun or mount total; that is not a known zero", path))
        return finish("unavailable")

    m1, m2 = _count(first.get("mounts")), _count(second.get("mounts"))
    b1, b2 = _count(first.get("barrels")), _count(second.get("barrels"))
    mounts_total = m1 + m2 if m1 is not None and m2 is not None else None
    barrels_total = b1 + b2 if b1 is not None and b2 is not None else None
    values["mounts"] = mounts_total
    values["installed_guns"] = barrels_total

    if barrels_total is None or mounts_total is None:
        diagnostics.append(_diag(
            "battery_totals.unknown",
            "the recovered installed barrel count or mount count of at least one group is "
            "unknown, so the whole-battery gun and mount total is unknown", path))

    weight_adjustment = None
    if mounts_total is not None:
        weight_adjustment = _weight_adjustment(groups, mounts_total, path, diagnostics)
    values["weight_adjustment"] = weight_adjustment

    if barrels_total is not None and barrels_total > 0:
        facts, provenance = _shared_facts(groups, index, path, diagnostics, provenance)

    guns_lt = mounts_lt = None
    if barrels_total == 0 and mounts_total == 0:
        # Every term of the recovered gun and mount expressions carries the zero
        # barrel count, so the whole answer is a determined zero.
        guns_lt = mounts_lt = 0.0
    elif barrels_total is not None and mounts_total is not None:
        missing = [name for name in ("calibre_mm", "barrel_calibres", "year", "gun_type",
                                     "mount_type") if facts[name] is None]
        if missing:
            diagnostics.append(_diag(
                "battery_totals.unknown",
                "the recovered gun and mount expressions need one shared %s; at least one is "
                "unknown, so the whole-battery gun and mount total is unknown"
                % (", ".join(missing),), path))
        else:
            calibre_in = facts["calibre_mm"] / layout_kernel.MM_PER_INCH
            values["calibre_mm"] = facts["calibre_mm"]
            values["calibre_in"] = calibre_in
            values["barrel_calibres"] = facts["barrel_calibres"]
            values["year"] = facts["year"]
            values["gun_type"] = facts["gun_type"]
            values["mount_type"] = facts["mount_type"]
            try:
                date_factor = kernels.gun_date_factor(facts["year"], path)
                values["date_factor"] = date_factor
                guns_lt = kernels.gun_mass_long_tons(calibre_in, facts["barrel_calibres"],
                                                     date_factor, barrels_total, path)
            except (ValueError, ArithmeticError) as error:
                diagnostics.append(_diag("battery_totals.unavailable",
                                         "the recovered gun mass cannot be evaluated: %s"
                                         % (error,), path))
                guns_lt = None
            if guns_lt is not None:
                if weight_adjustment is None:
                    diagnostics.append(_diag(
                        "battery_totals.unknown",
                        "the mount mass is unknown because the whole-battery weight adjustment is "
                        "unknown", path))
                else:
                    try:
                        mounts_lt = kernels.mount_mass_long_tons(
                            guns_lt, calibre_in, facts["gun_type"], facts["mount_type"],
                            weight_adjustment=weight_adjustment, shared_cradle=False, path=path)
                    except (ValueError, ArithmeticError) as error:
                        diagnostics.append(_diag("battery_totals.unavailable",
                                                 "the recovered mount mass cannot be evaluated: %s"
                                                 % (error,), path))
                        mounts_lt = None

    armour_lt = None
    armour = reading.get("armour")
    if isinstance(armour, dict) and isinstance(armour.get("values"), dict):
        armour_lt = armour["values"].get("total_long_tons")
    if armour_lt is None:
        diagnostics.append(_diag(
            "battery_totals.unknown",
            "the complete layout armour is unknown, so only the total is unknown; a known gun or "
            "mount mass stays readable", path))

    total_lt = None
    if guns_lt is not None and mounts_lt is not None and armour_lt is not None:
        total_lt = guns_lt + mounts_lt + armour_lt

    values.update(guns_long_tons=guns_lt, mounts_long_tons=mounts_lt,
                  armour_long_tons=armour_lt, total_long_tons=total_lt,
                  guns_t=_tonnes(guns_lt, path + ".guns"),
                  mounts_t=_tonnes(mounts_lt, path + ".mounts"),
                  armour_t=_tonnes(armour_lt, path + ".armour"),
                  total_t=_tonnes(total_lt, path + ".total"))

    known = [value for value in (guns_lt, mounts_lt, armour_lt) if value is not None]
    if total_lt is not None:
        status = "available"
    elif known:
        status = "partial"
    else:
        status = "unavailable"
    return finish(status)
