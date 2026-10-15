"""Optional concept-design configuration, generated mass models and balance screen.

``concept_design`` is an **optional** project section. A project without it keeps
every existing default and result unchanged. With it, this module

* validates a finite declared configuration and rejects anything out of domain
  rather than clamping it;
* generates standard ``systems`` mass models from one battery, machinery, fuel
  and adjustable-structure definition;
* resolves the selected loading ledger into explicit design roles and evaluates
  the adapted concept screen.

It replaces SpringSharp's hidden residual bookkeeping with the explicit selected
ledger. That is an *adapted* method, not whole-program parity, and it is kept
strictly apart from the physical hydrostatics, GM, GZ, trim and roll stages.

Two rules matter throughout:

* **Actual is actual.** Strength, stability and seakeeping are evaluated at the
  *selected* structural allocation. The strength-derived requirement is reported
  beside them and is never substituted for what the ship actually carries.
* **Unknown is unknown.** A missing or unclassified mass makes a dependent screen
  unavailable. It is never read as zero and never silently allocated.
"""

from __future__ import annotations

import copy
import math

try:
    from . import battery_armour as armour_kernel
    from . import concept_estimates as kernels
except ImportError:                                   # pragma: no cover - direct import
    import battery_armour as armour_kernel
    import concept_estimates as kernels

SCHEMA = "plimsoll-concept-design-1"
BALANCE_SCHEMA = "plimsoll-concept-balance-1"
METHOD = kernels.METHOD_VERSION

ROLES = (
    "structure", "guns", "mounts", "ammunition", "machinery", "fuel",
    "belt_main", "belt_upper", "belt_ends", "armour_bulge", "armour_deck",
    "conning", "bulkhead", "rotating_armour", "gun_mount_armour",
    "misc_vital", "misc_hull", "misc_deck", "misc_above", "misc_void",
    "other",
)
# armour_bulge, rotating_armour and gun_mount_armour are each counted exactly once
# here. This aggregate feeds the machinery displacement factor only; the strength
# and space expressions read GUN_ARMOUR_ROLES on their own, as the recovered
# guns.armWeight term does.
ARMOUR_ROLES = ("belt_main", "belt_upper", "belt_ends", "bulkhead",
                "armour_bulge", "armour_deck", "conning", "rotating_armour",
                "gun_mount_armour")
# The recovered guns.armWeight load term: complete rotating armour plus the
# gun-house and barbette armour. A barbette is fixed structure, so this is a sum
# of two distinct roles and neither one is relabelled as the other.
GUN_ARMOUR_ROLES = ("rotating_armour", "gun_mount_armour")
# All five miscellaneous roles, misc_void included.
MISC_ROLES = ("misc_vital", "misc_hull", "misc_deck", "misc_above", "misc_void")
# Roles the strength and space screen reads. 'other' is deliberately absent: it is
# never silently allocated into a named load.
SUPPORTING_ROLES = (("guns", "mounts", "ammunition", "machinery", "fuel", "conning",
                     "belt_ends") + GUN_ARMOUR_ROLES + MISC_ROLES)
BULKHEAD_NARROWING_MIN_LT = 0.1

EMPIRICAL_METHOD = "empirical_estimate_v1"
COMPARISON_TOLERANCE = {"relative": 0.05, "absolute_t": 0.5}
COMPARISON_POLICY = "empirical_concept_screening_tolerance"

# The optional per-battery armour block. It is an independent component: its own
# owned target, its own kernel identity, and no dependence on the ammunition
# inputs the three original estimates share.
ARMOUR_FIELDS = ("system_id", "item_id", "face_mm", "rear_roof_mm", "barbette_mm",
                 "freeboard_m", "super_factor")

# Declared bands, used only to raise a visible warning. The design never iterates
# towards a preferred rating.
SHORTFALL_COMPOSITE = 0.995
TENDER_COMPOSITE = 0.5
CRAMPED_HULL_RATIO = 1.1111112
CRAMPED_DECK_RATIO = 0.9
POOR_SEAKEPING = 0.7
WEAK_SEAKEEPING = 0.995
OVERWEIGHT_RATIO = 1.0


class ConceptDesignError(ValueError):
    """Report a rejected concept configuration with structured diagnostics."""

    def __init__(self, diagnostics):
        self.diagnostics = copy.deepcopy(diagnostics)
        super().__init__("; ".join(d["message"] for d in diagnostics if d.get("blocking")))


def _diag(code, message, path, blocking=True):
    return {"code": code, "severity": "error" if blocking else "warning",
            "message": message, "path": path, "blocking": blocking}


def _object(value, path, diagnostics):
    if not isinstance(value, dict):
        diagnostics.append(_diag("concept_design.invalid", "must be an object", path))
        return False
    return True


def _keys(value, allowed, path, diagnostics):
    for key in sorted(value.keys() - set(allowed)):
        diagnostics.append(_diag("concept_design.unsupported_field",
                                 "unsupported field %r" % (key,), path + "." + key))


def _number(value, path, diagnostics, *, positive=False, low=None, high=None, integer=False,
            nullable=True):
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        diagnostics.append(_diag("concept_design.invalid", "must be a finite number", path))
        return None
    if integer and not isinstance(value, int):
        # A fractional count or year is rejected, never truncated.
        diagnostics.append(_diag("concept_design.invalid", "must be an integer", path))
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        diagnostics.append(_diag("concept_design.invalid", "exceeds the supported numeric range", path))
        return None
    if not math.isfinite(number):
        diagnostics.append(_diag("concept_design.invalid", "must be a finite number", path))
        return None
    if positive and number <= 0:
        diagnostics.append(_diag("concept_design.domain", "must be positive", path))
        return None
    if low is not None and number < low:
        diagnostics.append(_diag("concept_design.domain", "must be >= %r" % (low,), path))
        return None
    if high is not None and number > high:
        diagnostics.append(_diag("concept_design.domain", "must be <= %r" % (high,), path))
        return None
    # An integer field stays an integer; it is never returned as a float.
    return int(value) if integer else number


def _string(value, path, diagnostics, choices=None, *, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        diagnostics.append(_diag("concept_design.invalid", "must be a non-empty string", path))
        return None
    if choices is not None and value not in choices:
        diagnostics.append(_diag("concept_design.enum",
                                 "must be one of %r" % (list(choices),), path))
        return None
    return value


def _item(value, path, item_ids, diagnostics):
    if not isinstance(value, str) or not value or value not in item_ids:
        diagnostics.append(_diag("concept_design.item_unknown",
                                 "must name an existing selected-ledger item", path))
        return None
    return value


def _unbound_item(value, path, item_ids, diagnostics):
    """A binding that may be absent. An absent one is an unfinished input.

    Unlike :func:`_item` this never refuses ``None``: a target that has not been
    chosen yet is a legitimate editable state that produces no estimate, and
    refusing it would make an unfinished project unsaveable.
    """
    if value is None:
        return None
    return _item(value, path, item_ids, diagnostics)


# ------------------------------------------------------------- configuration

def config_diagnostics(project, item_ids):
    """Return every optional concept_design diagnostic; never mutate anything."""
    try:
        validate_config(project, item_ids)
    except ConceptDesignError as error:
        return error.diagnostics
    return []


def _declared_system_leaves(systems, prefix=""):
    leaves = {}
    if not isinstance(systems, dict):
        return leaves
    for key, value in systems.items():
        if not isinstance(value, dict):
            continue
        identifier = "%s.%s" % (prefix, key) if prefix else key
        if any(field in value for field in ("weight_item_ids", "status", "mass_models")):
            leaves[identifier] = value.get("weight_item_ids") or []
        else:
            leaves.update(_declared_system_leaves(value, identifier))
    return leaves


def validate_config(project, item_ids=None):
    """Return the normalized optional configuration, or ``None`` when absent.

    ``item_ids`` is the set of selected-ledger item IDs used to check existence.
    Ownership is checked against the project's declared systems, so a generated
    model can never attach itself to an item or system that does not exist.
    """
    raw = project.get("concept_design") if isinstance(project, dict) else None
    if raw is None:
        return None
    diagnostics = []
    path = "$.concept_design"
    if not _object(raw, path, diagnostics):
        raise ConceptDesignError(diagnostics)
    _keys(raw, {"schema", "method", "source", "estimate", "target_displacement_t", "hull_year",
                "freeboard_m", "stern", "screws", "batteries", "machinery", "fuel", "balance"},
          path, diagnostics)
    if raw.get("schema") != SCHEMA:
        diagnostics.append(_diag("concept_design.schema", "schema must be %r" % (SCHEMA,),
                                 path + ".schema"))
    if raw.get("method") != METHOD:
        diagnostics.append(_diag("concept_design.method", "method must be %r" % (METHOD,),
                                 path + ".method"))
    source = _string(raw.get("source"), path + ".source", diagnostics)
    if raw.get("estimate") is not True:
        diagnostics.append(_diag("concept_design.estimate",
                                 "estimate must be explicitly true; this section is an estimate",
                                 path + ".estimate"))
    target_t = _number(raw.get("target_displacement_t"), path + ".target_displacement_t",
                       diagnostics, positive=True)
    hull_year = _number(raw.get("hull_year"), path + ".hull_year", diagnostics, integer=True,
                        low=1850, high=1950)
    freeboard_m = _number(raw.get("freeboard_m"), path + ".freeboard_m", diagnostics, positive=True)
    stern = _string(raw.get("stern"), path + ".stern", diagnostics, kernels.STERN_TYPES, nullable=True)
    screws = _number(raw.get("screws"), path + ".screws", diagnostics, integer=True, low=1, high=8)

    config = dict(
        schema=SCHEMA, method=METHOD, source=source, estimate=True,
        target_displacement_t=target_t, hull_year=hull_year,
        freeboard_m=freeboard_m, stern=stern, screws=screws,
        batteries=[], machinery=None, fuel=None, balance=None)

    known = set(item_ids or ())
    leaves = _declared_system_leaves(project.get("systems"))
    owned_targets = {}

    def owned_by(system_id, item, where, owner):
        """A concept component must be owned by exactly one declared system."""
        if not isinstance(system_id, str) or not system_id:
            return
        if system_id not in leaves:
            diagnostics.append(_diag(
                "concept_design.system_unknown",
                "system %r is not a declared systems leaf, so the generated model would "
                "have nowhere to appear" % (system_id,), where))
            return
        if item not in leaves[system_id]:
            diagnostics.append(_diag(
                "concept_design.item_not_owned",
                "item %r must be linked by the declared system %r, which owns %r"
                % (item, system_id, leaves[system_id]), where))
            return
        owners = [name for name, ids in leaves.items() if item in ids]
        if len(owners) > 1:
            diagnostics.append(_diag(
                "concept_design.item_not_owned",
                "item %r is claimed by %r but is linked by several systems %r"
                % (item, owner, owners), where))

    batteries = raw.get("batteries", [])
    if not isinstance(batteries, list):
        diagnostics.append(_diag("concept_design.invalid", "must be an array", path + ".batteries"))
        batteries = []
    for index, battery in enumerate(batteries):
        bpath = "%s.batteries[%d]" % (path, index)
        if not _object(battery, bpath, diagnostics):
            continue
        _keys(battery, {"id", "system_id", "guns_item_id", "mounts_item_id",
                        "ammunition_item_id", "calibre_mm", "barrel_calibres", "year",
                        "gun_type", "mount_type", "mount_count", "barrels_per_mount",
                        "shared_cradle", "rounds_per_gun", "shell_mass_kg", "broadside_guns",
                        "armour"},
              bpath, diagnostics)
        identity = _string(battery.get("id"), bpath + ".id", diagnostics)
        if identity is not None and any(b["id"] == identity for b in config["batteries"]):
            diagnostics.append(_diag("concept_design.duplicate", "battery IDs must be unique",
                                     bpath + ".id"))
            identity = None
        system_id = _string(battery.get("system_id"), bpath + ".system_id", diagnostics)
        # Keyed by field so the record can read it back, with a separate set for
        # duplicate detection.
        targets = {}
        claimed = set()
        for field in ("guns_item_id", "mounts_item_id", "ammunition_item_id"):
            value = _item(battery.get(field), bpath + "." + field, known, diagnostics)
            if value is None:
                continue
            if value in claimed:
                diagnostics.append(_diag("concept_design.duplicate_target",
                                         "guns, mounts and ammunition must be three distinct items",
                                         bpath + "." + field))
                continue
            if value in owned_targets:
                diagnostics.append(_diag("concept_design.duplicate_target",
                                         "item %r is already owned by %s" % (
                                             value, owned_targets[value]),
                                         bpath + "." + field))
                continue
            claimed.add(value)
            targets[field] = value
            owned_targets[value] = identity or "battery %d" % index
            owned_by(system_id, value, bpath + "." + field, identity or "this battery")
        mount_count = _number(battery.get("mount_count"), bpath + ".mount_count", diagnostics,
                              integer=True, low=0, high=kernels.MAX_MOUNTS)
        per_mount = _number(battery.get("barrels_per_mount"), bpath + ".barrels_per_mount",
                            diagnostics, integer=True, low=1, high=kernels.MAX_BARRELS_PER_MOUNT)
        shared = battery.get("shared_cradle")
        if shared is not None and not isinstance(shared, bool):
            diagnostics.append(_diag("concept_design.invalid", "must be a boolean",
                                     bpath + ".shared_cradle"))
            shared = False
        if shared and per_mount is not None and not 2 <= per_mount <= 5:
            diagnostics.append(_diag("concept_design.domain",
                                     "a shared cradle requires 2..5 barrels per mount",
                                     bpath + ".barrels_per_mount"))
        installed = (mount_count * per_mount
                     if mount_count is not None and per_mount is not None else None)
        record = dict(
            id=identity, system_id=system_id, guns_item_id=targets.get("guns_item_id"),
            mounts_item_id=targets.get("mounts_item_id"),
            ammunition_item_id=targets.get("ammunition_item_id"),            calibre_mm=_number(battery.get("calibre_mm"), bpath + ".calibre_mm", diagnostics,
                               positive=True, high=500),
            barrel_calibres=_number(battery.get("barrel_calibres"), bpath + ".barrel_calibres",
                                    diagnostics, positive=True, low=1, high=100),
            year=_number(battery.get("year"), bpath + ".year", diagnostics, integer=True,
                         low=1850, high=1950),
            gun_type=_string(battery.get("gun_type"), bpath + ".gun_type", diagnostics,
                             kernels.GUN_TYPES, nullable=True),
            mount_type=_string(battery.get("mount_type"), bpath + ".mount_type", diagnostics,
                               kernels.MOUNT_TYPES, nullable=True),
            mount_count=mount_count, barrels_per_mount=per_mount, shared_cradle=shared,
            installed_guns=installed,
            rounds_per_gun=_number(battery.get("rounds_per_gun"), bpath + ".rounds_per_gun",
                                   diagnostics, integer=True, low=0,
                                   high=kernels.MAX_ROUNDS_PER_GUN),
            shell_mass_kg=_number(battery.get("shell_mass_kg"), bpath + ".shell_mass_kg",
                                  diagnostics, positive=True, nullable=True),
        )
        broadside = battery.get("broadside_guns")
        if broadside is None:
            # An omitted broadside count falls back explicitly to the installed
            # count and says so, so the screening assumption stays visible.
            record["broadside_guns"] = installed
            record["broadside_basis"] = "omitted; the installed count is used for the screen"
        else:
            value = _number(broadside, bpath + ".broadside_guns", diagnostics, integer=True,
                            low=0, high=kernels.MAX_INSTALLED_GUNS)
            if value is not None and installed is not None and value > installed:
                diagnostics.append(_diag(
                    "concept_design.domain",
                    "broadside_guns %d exceeds the installed count %d; it is rejected, not "
                    "clamped" % (value, installed), bpath + ".broadside_guns"))
            record["broadside_guns"] = value
            record["broadside_basis"] = "declared broadside count"
        # The armour block is optional and independent: an omitted or null one
        # leaves every existing result exactly as it was.
        record["armour"] = _battery_armour(
            battery.get("armour"), bpath + ".armour", known, leaves, owned_targets,
            claimed, diagnostics, owned_by, identity or "battery %d" % index)
        config["batteries"].append(record)

    config["machinery"] = _machinery(raw.get("machinery"), path + ".machinery", known, leaves,
                                     owned_targets, diagnostics, owned_by)
    config["fuel"] = _fuel(raw.get("fuel"), path + ".fuel", known, leaves, owned_targets,
                           config["machinery"], diagnostics, owned_by)
    config["balance"] = _balance(raw.get("balance"), path + ".balance", known, leaves,
                                 owned_targets, diagnostics, owned_by)
    if config["balance"] is not None:
        roles = config["balance"]["roles"]
        bulkhead_beam = config["balance"].get("bulkhead_beam_m")
        beam = (project.get("hull") or {}).get("beam_m")
        if bulkhead_beam is not None and isinstance(beam, (int, float)) and bulkhead_beam > beam:
            diagnostics.append(_diag("concept_design.domain", "bulkhead_beam_m must not exceed beam_m",
                                     path + ".balance.bulkhead_beam_m"))
        required_roles = []
        for battery in config["batteries"]:
            required_roles.extend((battery.get(field), role) for field, role in (
                ("guns_item_id", "guns"), ("mounts_item_id", "mounts"),
                ("ammunition_item_id", "ammunition")))
            armour = battery.get("armour")
            if armour is not None:
                # A barbette is fixed structure, so the target must carry the
                # complete-armour role rather than the rotating one.
                required_roles.append((armour.get("item_id"), "gun_mount_armour"))
        for key in ("machinery", "fuel"):
            if config[key] is not None:
                required_roles.append((config[key].get("item_id"), key))
        for item, role in required_roles:
            if item is not None and roles.get(item) != role:
                diagnostics.append(_diag("concept_design.role_mismatch",
                    "component item %r must have role %r" % (item, role), path + ".balance.roles"))
    if any(item["blocking"] for item in diagnostics):
        raise ConceptDesignError(diagnostics)
    return config


def _battery_armour(raw, path, known, leaves, owned_targets, claimed, diagnostics,
                    owned_by, owner):
    """One battery's optional gun-house and barbette armour declaration.

    Every number may be ``None``, which means *unknown* and never the same thing
    as a declared zero. ``system_id`` and ``item_id`` may also be ``None``: an
    unfinished binding is a legal editable state that simply produces no
    estimate, so it is never refused and never filled in.
    """
    if raw is None:
        return None
    if not _object(raw, path, diagnostics):
        return None
    _keys(raw, set(ARMOUR_FIELDS), path, diagnostics)
    system_id = _string(raw.get("system_id"), path + ".system_id", diagnostics, nullable=True)
    item = _unbound_item(raw.get("item_id"), path + ".item_id", known, diagnostics)
    if item is not None:
        if item in claimed:
            diagnostics.append(_diag("concept_design.duplicate_target",
                                     "guns, mounts, ammunition and armour must be four "
                                     "distinct items", path + ".item_id"))
        elif item in owned_targets:
            diagnostics.append(_diag("concept_design.duplicate_target",
                                     "item %r is already owned by %s" % (
                                         item, owned_targets[item]), path + ".item_id"))
        else:
            claimed.add(item)
            owned_targets[item] = "%s armour" % (owner,)
            owned_by(system_id, item, path + ".item_id", "%s armour" % (owner,))
    return dict(
        system_id=system_id, item_id=item,
        face_mm=_number(raw.get("face_mm"), path + ".face_mm", diagnostics,
                        low=0, high=armour_kernel.MAX_THICKNESS_MM),
        rear_roof_mm=_number(raw.get("rear_roof_mm"), path + ".rear_roof_mm", diagnostics,
                             low=0, high=armour_kernel.MAX_THICKNESS_MM),
        barbette_mm=_number(raw.get("barbette_mm"), path + ".barbette_mm", diagnostics,
                            low=0, high=armour_kernel.MAX_THICKNESS_MM),
        freeboard_m=_number(raw.get("freeboard_m"), path + ".freeboard_m", diagnostics,
                            low=0, high=armour_kernel.MAX_FREEBOARD_M),
        super_factor=_number(raw.get("super_factor"), path + ".super_factor", diagnostics,
                             low=0, high=armour_kernel.MAX_SUPER_FACTOR),
    )


def _machinery(raw, path, known, leaves, owned_targets, diagnostics, owned_by):
    if raw is None:
        return None
    if not _object(raw, path, diagnostics):
        return None
    _keys(raw, {"system_id", "item_id", "year", "kind", "coal_pct", "speed_kn",
                "shaft_power_kw"}, path, diagnostics)
    item = _item(raw.get("item_id"), path + ".item_id", known, diagnostics)
    system_id = _string(raw.get("system_id"), path + ".system_id", diagnostics)
    if item is not None:
        if item in owned_targets:
            diagnostics.append(_diag("concept_design.duplicate_target",
                                     "item %r is already owned by %s" % (
                                         item, owned_targets[item]), path + ".item_id"))
        else:
            owned_targets[item] = "machinery"
        owned_by(system_id, item, path + ".item_id", "machinery")
    return dict(
        system_id=system_id, item_id=item,
        year=_number(raw.get("year"), path + ".year", diagnostics, integer=True, low=1850, high=1950),
        kind=_string(raw.get("kind"), path + ".kind", diagnostics, kernels.ENGINE_KINDS, nullable=True),
        coal_pct=_number(raw.get("coal_pct"), path + ".coal_pct", diagnostics, low=0.0, high=100.0),
        speed_kn=_number(raw.get("speed_kn"), path + ".speed_kn", diagnostics, positive=True,
                         high=50.0),
        shaft_power_kw=_number(raw.get("shaft_power_kw"), path + ".shaft_power_kw", diagnostics,
                               positive=True, nullable=True),
    )


def _fuel(raw, path, known, leaves, owned_targets, machinery, diagnostics, owned_by):
    if raw is None:
        return None
    if not _object(raw, path, diagnostics):
        return None
    _keys(raw, {"system_id", "item_id", "range_nm", "cruise_speed_kn"}, path, diagnostics)
    if machinery is None:
        diagnostics.append(_diag("concept_design.fuel_without_machinery",
                                 "fuel requires a declared machinery section", path))
    item = _item(raw.get("item_id"), path + ".item_id", known, diagnostics)
    system_id = _string(raw.get("system_id"), path + ".system_id", diagnostics)
    if item is not None:
        if item in owned_targets:
            diagnostics.append(_diag("concept_design.duplicate_target",
                                     "item %r is already owned by %s" % (
                                         item, owned_targets[item]), path + ".item_id"))
        else:
            owned_targets[item] = "fuel"
        owned_by(system_id, item, path + ".item_id", "fuel")
    cruise = _number(raw.get("cruise_speed_kn"), path + ".cruise_speed_kn", diagnostics,
                     positive=True)
    if (cruise is not None and machinery is not None and machinery.get("speed_kn") is not None
            and cruise > machinery["speed_kn"]):
        diagnostics.append(_diag("concept_design.domain",
                                 "cruise speed must not exceed the declared machinery speed",
                                 path + ".cruise_speed_kn"))
    return dict(
        system_id=system_id, item_id=item,
        range_nm=_number(raw.get("range_nm"), path + ".range_nm", diagnostics, positive=True),
        cruise_speed_kn=cruise,
    )


# Every balance assumption must be declared. The GUI may pre-fill editable
# estimates later; the core never invents one.
BALANCE_REQUIRED = ("steadiness", "space_hull_fraction", "space_deck_fraction", "super_factor",
                    "super_factor_long", "concentration", "strength_target")


def _balance(raw, path, known, leaves, owned_targets, diagnostics, owned_by):
    if raw is None:
        return None
    if not _object(raw, path, diagnostics):
        return None
    _keys(raw, {"roles", "structure_system_id", "structure_item_id", "bulkhead_beam_m",
                "assumption_source"} | set(BALANCE_REQUIRED), path, diagnostics)
    roles = raw.get("roles")
    resolved = {}
    if not isinstance(roles, dict) or not roles:
        diagnostics.append(_diag("concept_design.invalid",
                                 "roles must explicitly map ledger item IDs", path + ".roles"))
    else:
        for item_id in sorted(roles):
            rpath = path + ".roles[%r]" % (item_id,)
            if item_id not in known:
                diagnostics.append(_diag("concept_design.item_unknown",
                                         "must name an existing selected-ledger item", rpath))
                continue
            role = _string(roles[item_id], rpath, diagnostics, ROLES)
            if role is not None:
                resolved[item_id] = role
    # Empty role membership is zero; evaluation checks unmapped ledger items.
    structure_item = _item(raw.get("structure_item_id"), path + ".structure_item_id", known,
                           diagnostics)
    structure_system = _string(raw.get("structure_system_id"), path + ".structure_system_id",
                               diagnostics)
    if structure_item is not None:
        if structure_item in owned_targets:
            diagnostics.append(_diag("concept_design.duplicate_target",
                                     "the adjustable structure item is already owned by %s" % (
                                         owned_targets[structure_item],),
                                     path + ".structure_item_id"))
        else:
            owned_targets[structure_item] = "adjustable structure"
        owned_by(structure_system, structure_item, path + ".structure_item_id",
                 "adjustable structure")
        if resolved.get(structure_item) != "structure":
            diagnostics.append(_diag("concept_design.item_not_owned",
                                     "the adjustable structure item must be mapped to the "
                                     "'structure' role", path + ".structure_item_id"))
    balance = dict(
        roles=resolved, structure_system_id=structure_system, structure_item_id=structure_item,
        assumption_source=_string(raw.get("assumption_source"), path + ".assumption_source",
                                  diagnostics),
    )
    limits = {"steadiness": (0.0, 100.0), "space_hull_fraction": (0.0, None),
              "space_deck_fraction": (0.0, None), "super_factor": (0.0, None),
              "super_factor_long": (0.0, None), "concentration": (0.0, None),
              "strength_target": (0.0, None)}
    for key in BALANCE_REQUIRED:
        low, high = limits[key]
        balance[key] = _number(raw.get(key), path + "." + key, diagnostics, low=low, high=high)
        if key in ("space_hull_fraction", "space_deck_fraction") and balance[key] is not None \
                and balance[key] >= 1.0:
            diagnostics.append(_diag("concept_design.domain", "must be below 1", path + "." + key))
        if key in ("super_factor", "super_factor_long", "concentration", "strength_target") \
                and balance[key] is not None and balance[key] <= 0:
            diagnostics.append(_diag("concept_design.domain", "must be positive", path + "." + key))
    balance["bulkhead_beam_m"] = _number(raw.get("bulkhead_beam_m"), path + ".bulkhead_beam_m",
                                         diagnostics, positive=True, nullable=True)
    return balance


# --------------------------------------------------------------- hull proxy

def _require(values, fields, path):
    missing = [field for field in fields if values.get(field) is None]
    if missing:
        raise ConceptDesignError([_diag("concept_design.input_required",
            "declare %s to calculate this estimate" % field, path + "." + field)
            for field in missing])


def _calculation_diagnostics(error, path):
    return (error.diagnostics if isinstance(error, ConceptDesignError) else
            [_diag("concept_design.outside_model", str(error), path)])

def hull_proxy(project, config, path="$.concept_design"):
    """Imperial design proxy derived from the canonical hull keys.

    The beam at the bulges is not a canonical key, so the declared moulded beam
    is used for both. That is an explicit v1 assumption, not an inferred fact, and
    the physical geometry is never replaced or materialized here.
    """
    _require(config, ("target_displacement_t", "freeboard_m", "stern", "screws"), path)
    hull = project.get("hull") or {}
    missing = [key for key in ("lwl_m", "beam_m", "draught_normal_m", "block_coeff")
               if not isinstance(hull.get(key), (int, float)) or isinstance(hull.get(key), bool)]
    if missing:
        raise ConceptDesignError([_diag(
            "concept_design.hull_unknown",
            "the design proxy needs the canonical hull keys %s" % (missing,),
            "$.hull", blocking=False)])
    length_ft = kernels.metres_to_feet(hull["lwl_m"], "$.hull.lwl_m")
    beam_ft = kernels.metres_to_feet(hull["beam_m"], "$.hull.beam_m")
    draught_ft = kernels.metres_to_feet(hull["draught_normal_m"], "$.hull.draught_normal_m")
    block = float(hull["block_coeff"])
    coefficient = kernels.co_sharp(length_ft, beam_ft, block, "$.hull")
    effective = kernels.effective_length_ft(length_ft, beam_ft, coefficient,
                                            config["stern"], "$.concept_design")
    freeboard_ft = kernels.metres_to_feet(config["freeboard_m"], path + ".freeboard_m")
    displacement_lt = config["target_displacement_t"] * 1000.0 / kernels.LONG_TON_KG
    wetted = kernels.wetted_surface_sqft(length_ft, draught_ft, displacement_lt, "$.hull")
    waterplane_coefficient = kernels.waterplane_coefficient(block, config["stern"],
                                                            config["screws"], "$.hull")
    waterplane = kernels.waterplane_area_sqft(waterplane_coefficient, length_ft, beam_ft, "$.hull")
    return {
        "length_ft": length_ft, "beam_ft": beam_ft, "beam_m": hull["beam_m"],
        "draught_ft": draught_ft, "block_coeff": block, "co_sharp": coefficient,
        "effective_length_ft": effective, "freeboard_ft": freeboard_ft,
        "displacement_long_tons": displacement_lt, "wetted_surface_sqft": wetted,
        "co_waterplane": waterplane_coefficient, "waterplane_area_sqft": waterplane,
        "length_beam": length_ft / beam_ft,
        "natural_speed_kn": kernels.natural_speed_kn(effective, "$.hull.effective_length_ft"),
        "assumption": ("beam at the bulges is represented by the declared moulded beam; the "
                       "representative flat freeboard is the declared freeboard_m"),
    }


# --------------------------------------------------------- generated models

def _model(identity, item_id, long_tons, kernel, source_location, formula, inputs, source,
           extra=None, method_version=METHOD, boundary=kernels.SOURCE_SCOPE):
    """One generated ``systems`` mass model on the standard empirical pipeline.

    ``method_version`` defaults to the enclosing adapted method so every model
    this module generated before the battery-armour kernel keeps its identity.
    A component produced by a separate kernel passes its own version, which is
    recorded in both ``inputs`` and ``source`` — the same two method-identity
    fields every other model, and every acceptance record, already carries.
    """
    model_inputs = dict(inputs, estimate_long_tons=long_tons, kernel=kernel,
                        source_location=source_location, formula=formula,
                        method_version=method_version, source_sha256=kernels.SOURCE_SHA256)
    model = dict(
        id=identity, method=EMPIRICAL_METHOD, linked_weight_item_id=item_id,
        inputs=model_inputs, source=dict(source=declaration_of(source, kernel, source_location),
                                         assembly=kernels.SOURCE_ASSEMBLY,
                                         sha256=kernels.SOURCE_SHA256,
                                         method_version=method_version),
        estimate=True,
        input_provenance={key: dict(source=source, estimate=True) for key in model_inputs},
        comparison_tolerance=dict(COMPARISON_TOLERANCE),
        comparison_policy=COMPARISON_POLICY, boundary=boundary,
    )
    if extra:
        model.update(copy.deepcopy(extra))
    return model


def declaration_of(source, kernel, source_location):
    return "%s [%s at %s]" % (source, kernel, source_location)


def generated_models(project, state, item_ids=None):
    """Standard ``systems`` mass models keyed by system ID.

    Returns ``{"systems": {system_id: [model, ...]}, "diagnostics": [...]}``. This
    never calls ``systems.summary``, so the two cannot recurse.
    """
    item_ids = set(item_ids if item_ids is not None else
                   (entry["id"] for entry in state.get("effective_items", [])))
    config = validate_config(project, item_ids)
    if config is None:
        return {"systems": {}, "diagnostics": []}
    source = config["source"]
    out = {}
    diagnostics = []

    def register(system_id, model):
        out.setdefault(system_id, []).append(model)

    for battery in config["batteries"]:
        _battery_models(config, battery, register, diagnostics)
    try:
        hull = hull_proxy(project, config)
    except ValueError as error:
        diagnostics.extend(_calculation_diagnostics(error, "$.hull"))
        return {"systems": out, "diagnostics": diagnostics, "hull_proxy": None, "config": config}
    try:
        power = _power(config, hull)
    except ConceptDesignError as error:
        diagnostics.extend(error.diagnostics)
        power = {"method": "concept_speed_power_v1", "method_version": METHOD,
                 "status": "unavailable", "reason": str(error)}
    machinery = config["machinery"]
    if machinery is not None and machinery.get("item_id") and machinery.get("system_id"):
        try:
            result = _machinery_estimate(config, hull, power, state, item_ids, diagnostics)
        except ValueError as error:
            diagnostics.extend(_calculation_diagnostics(error, "$.concept_design.machinery"))
            result = None
        if result is not None:
            register(machinery["system_id"], _model(
                "concept.machinery", machinery["item_id"], result["machinery_long_tons"],
                "machinery_long_tons", "EngineControl.cs:538",
                "machinery_lt = (hp_max / (engine coefficient x (1.1 - coal_pct/1000)) x "
                "pre-1890 correction) / 2, then the declared small-ship displacement "
                "correction", result["inputs"], source,
                extra={"concept_component": "machinery", "note": result["note"]}))
    fuel = config["fuel"]
    if fuel is not None and fuel.get("item_id") and fuel.get("system_id") and machinery is not None:
        try:
            result = _fuel_estimate(config, hull, power)
        except ValueError as error:
            diagnostics.extend(_calculation_diagnostics(error, "$.concept_design.fuel"))
            result = None
        if result is not None:
            register(fuel["system_id"], _model(
                "concept.fuel", fuel["item_id"], result["normal_bunker_long_tons"],
                "bunker_normal_long_tons", "EngineControl.cs:888",
                "bunker_lt = range_nm / (1 + 0.4 x (100 - coal_pct)/100) / year factor / "
                "(1.8 / hp_cruise x 7000 x cruise_speed x 0.1) + displacement x 0.005",
                result["inputs"], source,
                extra={"concept_component": "fuel", "capacity_display_factor": 1.8,
                       "capacity_note": "1.8 x normal bunker is a displayed capacity estimate, "
                                        "not another ledger item"}))
    balance_models = []
    try:
        balance_models, balance_diagnostics = _balance_models(config, state, hull, item_ids,
                                                              [])
    except (ValueError, ConceptDesignError) as error:
        # A kernel domain failure is an unavailable component, not a dead stage.
        balance_diagnostics = [{"code": "concept_design.structure_unavailable",
                                "severity": "warning", "blocking": False,
                                "path": "$.concept_design.balance",
                                "message": str(error)}]
        balance_models = []
    diagnostics.extend(balance_diagnostics)
    for system_id, model in balance_models:
        register(system_id, model)
    return {"systems": out, "diagnostics": diagnostics, "hull_proxy": hull, "config": config,
            "power": power}


def _battery_models(config, battery, register, diagnostics):
    # The three original components keep their own all-or-nothing behaviour:
    # nothing about the armour block may change when they are generated.
    if None not in (battery["system_id"], battery["guns_item_id"],
                    battery["mounts_item_id"], battery["ammunition_item_id"]):
        try:
            _require(battery, ("calibre_mm", "barrel_calibres", "year", "gun_type", "mount_type",
                     "mount_count", "barrels_per_mount", "rounds_per_gun", "shared_cradle"),
                     "$.concept_design.batteries[%s]" % battery["id"])
            estimates = kernels.battery_estimates(
                calibre_mm=battery["calibre_mm"], barrel_calibres=battery["barrel_calibres"],
                year=battery["year"], gun_type=battery["gun_type"],
                mount_type=battery["mount_type"], mount_count=battery["mount_count"],
                barrels_per_mount=battery["barrels_per_mount"],
                rounds_per_gun=battery["rounds_per_gun"],
                shell_mass_kg=battery["shell_mass_kg"], shared_cradle=battery["shared_cradle"])
        except (ValueError, ArithmeticError) as error:
            diagnostics.append(_diag("concept_design.battery_unavailable", str(error),
                                     "$.concept_design.batteries[%s]" % (battery["id"],)))
        else:
            prefix = "concept.%s" % (battery["id"],)
            for key, field, kernel in (("guns", "guns_item_id", "guns"),
                                      ("mounts", "mounts_item_id", "mounts"),
                                      ("ammunition", "ammunition_item_id", "ammunition")):
                provenance = estimates["provenance"][kernel]
                register(battery["system_id"], _model(
                    "%s.%s" % (prefix, key), battery[field],
                    estimates["values"][key + "_long_tons"],
                    provenance["kernel"], provenance["source_location"], provenance["formula"],
                    provenance["inputs"], config["source"],
                    extra={"concept_battery_id": battery["id"], "concept_component": key}))
    _battery_armour_model(config, battery, register, diagnostics)


def _battery_armour_model(config, battery, register, diagnostics):
    """The optional ``concept.<battery>.armour`` model, generated independently.

    It reads no ammunition input and no barrel length, it is attached to its own
    owned target rather than to the mount item, and an absent, unbound or
    incomplete declaration produces a diagnostic and no model instead of
    blocking the three estimates above.
    """
    armour = battery.get("armour")
    if armour is None or None in (armour["system_id"], armour["item_id"]):
        return
    path = "$.concept_design.batteries[%s].armour" % (battery["id"],)
    try:
        _require(battery, ("calibre_mm", "year", "gun_type", "mount_type", "mount_count",
                           "barrels_per_mount", "shared_cradle"), path)
        result = armour_kernel.estimate(
            calibre_mm=battery["calibre_mm"], year=battery["year"],
            gun_type=battery["gun_type"], mount_type=battery["mount_type"],
            mount_count=battery["mount_count"],
            barrels_per_mount=battery["barrels_per_mount"],
            shared_cradle=battery["shared_cradle"],
            face_mm=armour["face_mm"], rear_roof_mm=armour["rear_roof_mm"],
            barbette_mm=armour["barbette_mm"], freeboard_m=armour["freeboard_m"],
            super_factor=armour["super_factor"], path=path)
    except (ValueError, ArithmeticError) as error:
        # A declared input the recovered expression cannot evaluate is an
        # unavailable component, never a failed stage and never a raw
        # interpreter error. ``ArithmeticError`` covers overflow and
        # divide-by-zero; the kernel already converts its own, and this is the
        # boundary that keeps a numerical blow-up from ever leaving this stage.
        diagnostics.append(_diag("concept_design.armour_unavailable", str(error), path,
                                 blocking=False))
        return
    for entry in result["diagnostics"]:
        diagnostics.append(_diag(entry["code"], entry["message"], entry["path"],
                                 blocking=False))
    values = result["values"]
    if values["total_long_tons"] is None:
        return
    # The existing empirical pipeline converts LT via kg before tonnes. Do not
    # register a model whose otherwise finite LT would overflow that boundary.
    if not math.isfinite(values["total_long_tons"] * kernels.LONG_TON_KG):
        diagnostics.append(_diag(
            "concept_design.armour_unavailable",
            "the derived armour mass exceeds the supported weight-conversion range",
            path, blocking=False))
        return
    provenance = result["provenance"]
    register(armour["system_id"], _model(
        "concept.%s.armour" % (battery["id"],), armour["item_id"],
        values["total_long_tons"], provenance["kernel"], provenance["source_location"],
        provenance["formula"], provenance["inputs"], config["source"],
        method_version=armour_kernel.METHOD_VERSION,
        boundary=armour_kernel.SOURCE_SCOPE,
        extra={"concept_battery_id": battery["id"], "concept_component": "armour",
               "assumptions": provenance["assumptions"],
               "component_breakdown": {
                   "face_long_tons": values["face_long_tons"],
                   "rear_roof_long_tons": values["rear_roof_long_tons"],
                   "barbette_long_tons": values["barbette_long_tons"]},
               "guns_in_mount_selector": values["guns_in_mount_selector"],
               "note": ("gun-house and barbette armour of this homogeneous group; a barbette "
                        "is fixed structure, not rotating armour, and this estimate does not "
                        "contain any part of the mount mass. A reader who already carries "
                        "this armour inside the mount item must split the target first; no "
                        "split is generated and nothing is deducted from a declared mount "
                        "mass automatically. One homogeneous row only: multi-row and mixed "
                        "arrangements are outside this method")}))


def _power(config, hull):
    """Versioned SPS-derived speed/power indicators from the declared speed."""
    result = {"method": "concept_speed_power_v1", "method_version": METHOD,
              "source_location": "EngineControl.cs:438",
              "natural_speed_kn": hull["natural_speed_kn"]}
    machinery = config.get("machinery")
    if not machinery or machinery.get("speed_kn") is None:
        result["status"] = "unavailable"
        result["reason"] = "no declared machinery speed"
        result["diagnostics"] = [_diag("concept_design.input_required", result["reason"],
                                         "$.concept_design.machinery.speed_kn")]
        return result
    declared = machinery.get("shaft_power_kw")
    if declared is not None:
        # An explicitly supplied power is the declared value; the empirical speed
        # estimate is not silently substituted for it.
        result.update(status="completed", power_origin="declared_shaft_power_kw",
                      hp_max=declared / kernels.KW_PER_HP,
                      hp_max_kw=declared)
    else:
        try:
            hp, length_hp = kernels.speed_hp(
                machinery["speed_kn"], hull["length_ft"], hull["effective_length_ft"],
                hull["co_sharp"], hull["displacement_long_tons"], hull["wetted_surface_sqft"],
                machinery["year"])
        except ValueError as error:
            result.update(status="unavailable", power_origin="unavailable", reason=str(error))
            return result
        result.update(status="completed", power_origin="empirical_speed_hp_estimate",
                      hp_max=hp, hp_max_kw=kernels.hp_to_kw(hp), length_hp_ft=length_hp)
    try:
        split = kernels.resistance_split(machinery["speed_kn"], hull["length_ft"],
                                         hull["co_sharp"], hull["displacement_long_tons"],
                                         hull["wetted_surface_sqft"])
        result.update(friction_fraction=split["friction_fraction"],
                      friction_fraction_status=split["friction_fraction_status"])
    except ValueError as error:
        result.update(friction_fraction=None, friction_fraction_status="unavailable",
                      friction_fraction_reason=str(error))
    return result


def _mass_of(state, item_id):
    for entry in state.get("effective_items", []):
        if entry["id"] == item_id:
            return entry.get("mass_t")
    return None


def _role_masses(config, state):
    """Resolve the selected ledger into explicit role totals, in long tons."""
    balance = config.get("balance")
    if balance is None:
        return None
    by_role = {role: [] for role in ROLES}
    unclassified = []
    for entry in state.get("effective_items", []):
        mass = entry.get("mass_t")
        role = balance["roles"].get(entry["id"])
        if role is None:
            if mass is None or float(mass) > 0:
                unclassified.append(entry["id"])
            continue
        by_role[role].append((entry["id"], mass))
    totals = {}
    for role, entries in by_role.items():
        if any(mass is None for _, mass in entries):
            totals[role] = None
        else:
            totals[role] = sum(float(mass) for _, mass in entries) / kernels.LONG_TON_KG * 1000.0
    return {"by_role": by_role, "totals": totals, "unclassified": unclassified}


def _aggregate(totals, roles, path, diagnostics, label):
    """An aggregate is known only when every member role is explicitly supplied."""
    missing = [role for role in roles if totals.get(role) is None]
    if missing:
        diagnostics.append(_diag("concept_design.aggregate_unknown",
                                 "%s needs every member role to be supplied with a known mass, "
                                 "or an explicit declared zero; unknown: %s" % (label, missing),
                                 path))
        return None
    return sum(totals[role] for role in roles)


def _gun_armour_long_tons(totals):
    """The recovered guns.armWeight load term: rotating armour plus gun-mount armour.

    Each role is summed exactly once. The barbette inside ``gun_mount_armour`` is
    fixed structure: it is added to the same recovered term, and it is never
    relabelled as part of the rotating total. ``None`` when either role is
    unknown, so an unknown gun-mount armour mass makes the dependent term
    unavailable rather than zero.
    """
    values = [totals.get(role) for role in GUN_ARMOUR_ROLES]
    if any(value is None for value in values):
        return None
    return sum(values)


def _selected_borne(config, state, diagnostics):
    """Balance borne weight from SELECTED bare-gun mass, never mounts or armour.

    A positive guns-role item that is not one of the declared battery gun items
    has no declared arrangement model, so the dependent metrics are unavailable.
    """
    resolved = _role_masses(config, state)
    if resolved is None:
        return None, None
    bound = set()
    total = 0.0
    for battery in config["batteries"]:
        guns_item = battery.get("guns_item_id")
        if guns_item is None:
            return None, resolved
        bound.add(guns_item)
        if battery["mount_type"] is None:
            diagnostics.append(_diag("concept_design.input_required", "declare the battery mount type",
                                     "$.concept_design.batteries[%s].mount_type" % battery["id"]))
            return None, resolved
        mass = _mass_of(state, guns_item)
        if mass is None:
            diagnostics.append(_diag("concept_design.borne_unknown",
                                     "the battery bare-gun item %r has unknown selected mass"
                                     % (guns_item,), "$.concept_design.balance.roles"))
            return None, resolved
        adjustment = kernels.MOUNT_ADJUSTMENT[kernels.MOUNT_TYPES.index(battery["mount_type"])]
        total += kernels.balance_borne_weight_long_tons(
            float(mass) * 1000.0 / kernels.LONG_TON_KG, adjustment)
    stray = [item for item, mass in resolved["by_role"]["guns"] if item not in bound]
    positive = [item for item in stray
                if _mass_of(state, item) is not None and float(_mass_of(state, item)) > 0]
    if positive:
        diagnostics.append(_diag(
            "concept_design.guns_role_unbound",
            "guns-role items %r have a positive selected mass but are not bound to a declared "
            "battery, so no borne weight can be derived for them" % (positive,),
            "$.concept_design.balance.roles"))
        return None, resolved
    return total, resolved


def _balance_models(config, state, hull, item_ids, diagnostics):
    """The shared pure allocation helper used by both the model and the balance."""
    balance = config.get("balance")
    if balance is None:
        return [], diagnostics
    if balance.get("structure_item_id") is None or balance.get("structure_system_id") is None:
        return [], diagnostics
    borne, resolved = _selected_borne(config, state, diagnostics)
    if borne is None or resolved is None:
        return [], diagnostics
    demand = _structure_demand(config, state, hull, borne, resolved, diagnostics, power=None)
    if demand is None:
        return [], diagnostics
    structure_item = balance["structure_item_id"]
    current = _mass_of(state, structure_item)
    current_lt = None if current is None else float(current) * 1000.0 / kernels.LONG_TON_KG
    model = _model(
        "concept.structure", structure_item, demand["required_adjustable_long_tons"],
        "required_structure_long_tons", "PerformanceControl.cs:546,591,610",
        "required_adjustable_lt = strength_target / composite unit coefficient "
        "- other selected structure items",
        dict(strength_target=balance["strength_target"],
             cross_coefficient=demand["cross_coefficient"],
             long_coefficient=demand["long_coefficient"],
             other_structure_long_tons=demand["other_structure_long_tons"]),
        config["source"],
        extra={"concept_component": "structure",
               "current_structure_long_tons": current_lt,
               "inversion": "unit structural mass coefficients are inverted directly; no "
                            "displacement residual is used"})
    return [(balance["structure_system_id"], model)], diagnostics


def _power_for_loads(config, hull, diagnostics):
    """The hp used by the strength expression; a failure is unavailable, never zero."""
    machinery = config.get("machinery")
    if machinery is None or machinery.get("speed_kn") is None:
        diagnostics.append(_diag("concept_design.power_unavailable",
                                 "the strength expression needs a declared machinery speed",
                                 "$.concept_design.machinery.speed_kn"))
        return None, None
    declared = machinery.get("shaft_power_kw")
    if declared is not None:
        return declared / kernels.KW_PER_HP, "declared_shaft_power_kw"
    try:
        hp, _ = kernels.speed_hp(machinery["speed_kn"], hull["length_ft"],
                                 hull["effective_length_ft"], hull["co_sharp"],
                                 hull["displacement_long_tons"], hull["wetted_surface_sqft"],
                                 machinery["year"])
    except ValueError as error:
        diagnostics.append(_diag("concept_design.power_unavailable", str(error),
                                 "$.concept_design.machinery.speed_kn"))
        return None, None
    return hp, "empirical_speed_hp_estimate"


def _broadside_lb(config):
    """Screening broadside mass in POUNDS, using the effective shell mass."""
    total = 0.0
    detail = []
    for battery in config["batteries"]:
        _require(battery, ("broadside_guns", "year", "calibre_mm", "barrel_calibres"),
                 "$.concept_design.batteries[%s]" % battery["id"])
        count = battery.get("broadside_guns")
        if count is None:
            continue
        factor = kernels.gun_date_factor(battery["year"])
        calibre_in = kernels.millimetres_to_inches(battery["calibre_mm"])
        estimated = kernels.estimated_shell_lb(calibre_in, battery["barrel_calibres"], factor)
        if battery.get("shell_mass_kg") is None:
            effective_lb = estimated
            origin = "formula_estimate_sps_3b3"
        else:
            effective_lb = kernels.kilograms_to_pounds(battery["shell_mass_kg"])
            origin = "declared_manual_override"
        total += count * effective_lb
        detail.append(dict(battery_id=battery["id"], broadside_guns=count,
                           shell_lb=effective_lb, shell_origin=origin,
                           broadside_basis=battery["broadside_basis"]))
    return total, detail


def _structure_demand(config, state, hull, borne, resolved, diagnostics, power=None):
    """Strength-derived structural requirement, inverted from unit coefficients."""
    balance = config["balance"]
    totals = resolved["totals"]
    if resolved["unclassified"]:
        diagnostics.append(_diag("concept_design.screening_incomplete",
            "classify all positive or unknown selected masses before calculating structure: %r"
            % resolved["unclassified"], "$.concept_design.balance.roles"))
        return None
    # Every supporting load must be known and mapped. 'other' is not a named load.
    unknown_supporting = [role for role in ROLES if role != "structure" and totals.get(role) is None]
    if unknown_supporting:
        diagnostics.append(_diag(
            "concept_design.supporting_load_unknown",
            "the structural screen needs every supporting role to be known: %r"
            % (unknown_supporting,), "$.concept_design.balance.roles"))
        return None
    # Other fixed structure is summed directly, so an unknown adjustable item
    # still yields an independent demand.
    other_structure = 0.0
    adjustable = balance["structure_item_id"]
    for item_id, mass in resolved["by_role"]["structure"]:
        if item_id == adjustable:
            continue
        if mass is None:
            diagnostics.append(_diag(
                "concept_design.structure_unknown",
                "fixed structure item %r has unknown selected mass" % (item_id,),
                "$.concept_design.balance.roles"))
            return None
        other_structure += float(mass) * 1000.0 / kernels.LONG_TON_KG
    try:
        _require(config, ("hull_year",), "$.concept_design")
        _require(balance, ("strength_target", "concentration", "super_factor", "super_factor_long"),
                 "$.concept_design.balance")
        broadside_lb, broadside_detail = _broadside_lb(config)
    except ValueError as error:
        diagnostics.extend(_calculation_diagnostics(error, "$.concept_design.balance"))
        return None
    hp, hp_origin = _power_for_loads(config, hull, diagnostics)
    if hp is None:
        return None
    # The recovered cross and longitudinal expressions use guns.armWeight, which
    # is the complete rotating armour term plus the gun-house and barbette
    # armour, each counted once.
    gun_armour_lt = _gun_armour_long_tons(totals)
    try:
        cross_coefficient = kernels.strength_cross_coefficient(
            hull["wetted_surface_sqft"], hull["length_ft"], hull["freeboard_ft"],
            hull["waterplane_area_sqft"], hull["beam_ft"], hull["draught_ft"],
            hull["displacement_long_tons"], broadside_lb, borne, gun_armour_lt,
            totals["conning"], hp, balance["concentration"], balance["super_factor"],
            config["hull_year"])
        long_coefficient = kernels.strength_long_coefficient(
            hull["length_ft"], hull["draught_ft"], hull["freeboard_ft"],
            hull["displacement_long_tons"], totals["belt_ends"], borne,
            gun_armour_lt, balance["super_factor_long"], config["hull_year"])
        required_total = kernels.required_structure_long_tons(
            balance["strength_target"], cross_coefficient, long_coefficient)
    except ValueError as error:
        diagnostics.append(_diag("concept_design.structure_demand_unavailable", str(error),
                                 "$.concept_design.balance"))
        return None
    required_adjustable = required_total - other_structure
    if required_adjustable < 0.0:
        diagnostics.append(_diag(
            "concept_design.structure_oversupplied",
            "the other selected structure items already exceed the strength demand by %.3f "
            "long tons; the adjustable item is not silently reduced" % (-required_adjustable,),
            "$.concept_design.balance.structure_item_id"))
        return None
    return {"required_total_long_tons": required_total,
            "required_adjustable_long_tons": required_adjustable,
            "other_structure_long_tons": other_structure,
            "cross_coefficient": cross_coefficient, "long_coefficient": long_coefficient,
            "broadside_lb": broadside_lb, "broadside_detail": broadside_detail,
            "borne_long_tons": borne, "hp_max": hp, "hp_origin": hp_origin}


def _actual_structure_lt(config, state, resolved, diagnostics):
    """The selected structural allocation as it actually is."""
    adjustable = config["balance"]["structure_item_id"]
    total = 0.0
    unknown = []
    for item_id, mass in resolved["by_role"]["structure"]:
        if mass is None:
            unknown.append(item_id)
            continue
        total += float(mass) * 1000.0 / kernels.LONG_TON_KG
    if unknown:
        diagnostics.append(_diag(
            "concept_design.structure_unknown",
            "structure items %r have unknown selected mass, so the current strength scores are "
            "unavailable" % (unknown,), "$.concept_design.balance.roles"))
        return None, (adjustable, None)
    adjustable_mass = _mass_of(state, adjustable)
    current_adjustable = (None if adjustable_mass is None
                          else float(adjustable_mass) * 1000.0 / kernels.LONG_TON_KG)
    return total, [adjustable, current_adjustable]


def _machinery_estimate(config, hull, power, state, item_ids, diagnostics):
    machinery = config["machinery"]
    _require(machinery, ("year", "kind", "coal_pct"), "$.concept_design.machinery")
    if power.get("hp_max") is None:
        raise ConceptDesignError([_diag("concept_design.machinery_unavailable",
                                        "a declared speed or power is required for the "
                                        "machinery estimate", "$.concept_design.machinery")])
    balance = config.get("balance")
    if balance is None:
        raise ConceptDesignError([_diag("concept_design.machinery_unavailable",
                                        "the machinery estimate needs a declared balance screen",
                                        "$.concept_design.balance")])
    _, resolved = _selected_borne(config, state, diagnostics)
    automatic = 0.0
    for battery in config["batteries"]:
        try:
            estimates = kernels.battery_estimates(
                calibre_mm=battery["calibre_mm"], barrel_calibres=battery["barrel_calibres"],
                year=battery["year"], gun_type=battery["gun_type"],
                mount_type=battery["mount_type"], mount_count=battery["mount_count"],
                barrels_per_mount=battery["barrels_per_mount"],
                rounds_per_gun=battery["rounds_per_gun"],
                shell_mass_kg=battery["shell_mass_kg"], shared_cradle=battery["shared_cradle"])
        except (ValueError, ArithmeticError) as error:
            raise ConceptDesignError(_calculation_diagnostics(error, "$.concept_design.batteries")) from error
        automatic += estimates["values"]["automatic_borne_weight_long_tons"]
    if resolved is None:
        raise ConceptDesignError([_diag("concept_design.machinery_unavailable",
                                        "a declared balance screen is required",
                                        "$.concept_design.balance")])
    totals = resolved["totals"]
    if resolved["unclassified"]:
        raise ConceptDesignError([_diag("concept_design.screening_incomplete",
            "classify all positive or unknown selected masses before estimating machinery: %r"
            % resolved["unclassified"], "$.concept_design.balance.roles")])
    armour_lt = _aggregate(totals, ARMOUR_ROLES, "$.concept_design.balance.roles", diagnostics,
                           "the armour aggregate")
    misc_lt = _aggregate(totals, MISC_ROLES, "$.concept_design.balance.roles", diagnostics,
                         "the miscellaneous aggregate")
    if armour_lt is None or misc_lt is None:
        raise ConceptDesignError([d for d in diagnostics if d["blocking"]])
    result = kernels.machinery_long_tons(
        power["hp_max"], machinery["year"], machinery["kind"], machinery["coal_pct"],
        hull["displacement_long_tons"], automatic, armour_lt, misc_lt)
    result["inputs"] = dict(
        hp_max=power["hp_max"], hp_origin=power.get("power_origin"), year=machinery["year"],
        kind=machinery["kind"], coal_pct=machinery["coal_pct"],
        displacement_long_tons=hull["displacement_long_tons"],
        automatic_borne_weight_long_tons=automatic, selected_armour_long_tons=armour_lt,
        selected_misc_long_tons=misc_lt)
    result["note"] = ("the displacement factor uses the automatic battery borne estimate and the "
                      "aggregate of all armour including armour_bulge, rotating_armour and "
                      "gun_mount_armour, each counted exactly once, and all five "
                      "miscellaneous roles; 'other' is in neither sum")
    return result


def _fuel_estimate(config, hull, power):
    fuel = config["fuel"]
    machinery = config["machinery"]
    _require(fuel, ("range_nm", "cruise_speed_kn"), "$.concept_design.fuel")
    _require(machinery, ("year", "kind", "coal_pct"), "$.concept_design.machinery")
    if power.get("hp_max") is None:
        raise ConceptDesignError([_diag("concept_design.fuel_unavailable",
                                        "a declared speed or power is required for the fuel "
                                        "estimate", "$.concept_design.machinery.speed_kn")])
    hp, _ = kernels.speed_hp(fuel["cruise_speed_kn"], hull["length_ft"],
                             hull["effective_length_ft"], hull["co_sharp"],
                             hull["displacement_long_tons"], hull["wetted_surface_sqft"],
                             machinery["year"])
    bunker = kernels.bunker_normal_long_tons(
        machinery["year"], machinery["kind"], fuel["range_nm"], machinery["coal_pct"],
        hull["displacement_long_tons"], hp, fuel["cruise_speed_kn"])
    return {"normal_bunker_long_tons": bunker,
            "inputs": dict(range_nm=fuel["range_nm"], coal_pct=machinery["coal_pct"],
                           year=machinery["year"], kind=machinery["kind"],
                           displacement_long_tons=hull["displacement_long_tons"],
                           hp_cruise=hp, cruise_speed_kn=fuel["cruise_speed_kn"])}


# ------------------------------------------------------------------- balance

def evaluate(project, state, systems_summary):
    """Evaluate the adapted concept screen from the selected loading ledger.

    This runs from loading and systems only. It never needs a complete CG and
    never reads a physical stability, trim or roll result.
    """
    item_ids = {entry["id"] for entry in state.get("effective_items", [])}
    try:
        config = validate_config(project, item_ids)
    except ConceptDesignError as error:
        return {"schema": BALANCE_SCHEMA, "status": "unavailable",
                "method_version": METHOD, "method_scope": kernels.SOURCE_SCOPE,
                "historical_validated": None,
                "reason": "; ".join(d["message"] for d in error.diagnostics),
                "values": {}, "diagnostics": error.diagnostics, "screening_complete": False}
    if config is None:
        return {"schema": BALANCE_SCHEMA, "status": "not_configured",
                "method_version": METHOD, "method_scope": kernels.SOURCE_SCOPE,
                "historical_validated": None,
                "reason": "the project declares no concept_design",
                "values": {}, "diagnostics": [], "screening_complete": False}
    diagnostics = []
    result = dict(schema=BALANCE_SCHEMA, status="completed", method_version=METHOD,
                  method_scope=kernels.SOURCE_SCOPE, historical_validated=None,
                  basis="declared design displacement, selected ledger allocations",
                  assumption_source=config["balance"].get("assumption_source") if config.get("balance") else None,
                  values={}, diagnostics=diagnostics, screening_complete=False)
    selected_total_t = state.get("values", {}).get("total_mass_t")
    result["values"]["selected_total_mass_t"] = selected_total_t
    result["values"]["target_displacement_t"] = config["target_displacement_t"]
    result["values"]["difference_t"] = (None if selected_total_t is None or config["target_displacement_t"] is None
                                         else config["target_displacement_t"] - selected_total_t)
    try:
        hull = hull_proxy(project, config)
    except ValueError as error:
        diagnostics.extend(_calculation_diagnostics(error, "$.hull"))
        result["status"] = "unavailable"
        result["reason"] = "the design hull proxy is unavailable"
        return result
    result["hull_proxy"] = hull
    result["crew"] = dict(kernels.crew_band(hull["displacement_long_tons"]), unit="persons",
                          basis="HullControl.cs:1272; target displacement")
    balance = config.get("balance")
    if balance is None:
        diagnostics.append(_diag("concept_design.balance_missing",
                                 "no balance section is declared; no screen is produced",
                                 "$.concept_design.balance"))
        result["status"] = "unavailable"
        result["reason"] = "the concept screen needs a declared balance section"
        return result
    result["power"] = _power(config, hull)
    declared_totals = (_role_masses(config, state) or {}).get("totals", {})
    if balance.get("bulkhead_beam_m") is None:
        bulkhead = declared_totals.get("bulkhead")
        if bulkhead is not None and bulkhead > BULKHEAD_NARROWING_MIN_LT:
            diagnostics.append(_diag(
                "concept_design.bulkhead_beam_required",
                "the selected bulkhead mass of %.3f long tons exceeds %.1f, so the recovered "
                "roomHull beam restriction applies and bulkhead_beam_m must be declared"
                % (bulkhead, BULKHEAD_NARROWING_MIN_LT),
                "$.concept_design.balance.bulkhead_beam_m"))
    borne, resolved = _selected_borne(config, state, diagnostics)
    result["selected_borne_weight_long_tons"] = borne
    demand = None
    actual_structure = None
    if resolved is not None:
        result["roles"] = resolved["totals"]
        result["unclassified_item_ids"] = resolved["unclassified"]
        if resolved["unclassified"]:
            diagnostics.append(_diag(
                "concept_design.screening_incomplete",
                "unclassified positive selected mass %r is not allocated" % (
                    resolved["unclassified"],), "$.concept_design.balance.roles"))
        nonstructure = 0.0
        complete_roles = not resolved["unclassified"]
        for role, total in resolved["totals"].items():
            if role == "structure":
                continue
            if total is None:
                complete_roles = False
                continue
            if role != "structure":
                nonstructure += total
        result["values"]["nonstructure_mass_long_tons"] = nonstructure if complete_roles else None
        result["values"]["remaining_structural_budget_long_tons"] = (
            config["target_displacement_t"] * 1000.0 / kernels.LONG_TON_KG - nonstructure
            if complete_roles else None)
        result["screening_complete"] = (complete_roles and resolved["totals"]["structure"] is not None)
        if borne is not None:
            demand = _structure_demand(config, state, hull, borne, resolved, diagnostics)
            total, (adjustable, current_adjustable) = _actual_structure_lt(
                config, state, resolved, diagnostics)
            actual_structure = total
    if demand is not None:
        margin = None if actual_structure is None else actual_structure - demand["required_total_long_tons"]
        result["structure"] = {
            "current_structure_long_tons": actual_structure,
            "structure_item_id": adjustable if demand else None,
            "current_adjustable_structure_long_tons": current_adjustable,
            "other_structure_long_tons": demand["other_structure_long_tons"],
            "required_total_long_tons": demand["required_total_long_tons"],
            "required_adjustable_long_tons": demand["required_adjustable_long_tons"],
            "structure_margin_long_tons": margin,
            "strength_target": balance["strength_target"],
            "cross_coefficient": demand["cross_coefficient"],
            "long_coefficient": demand["long_coefficient"],
            "hp_max": demand["hp_max"], "hp_origin": demand["hp_origin"],
            "broadside_lb": demand["broadside_lb"],
            "broadside_detail": demand["broadside_detail"],
            "inversion": "unit structural mass coefficients; the displacement residual is a "
                         "separate budget, never the structural requirement",
        }
        result["values"]["structure_demand_long_tons"] = demand["required_total_long_tons"]
        result["values"]["structure_margin_long_tons"] = margin
    strength = _strength_scores(balance, demand, actual_structure)
    if strength is not None:
        result["strength"] = strength
    result.update(_performance(config, hull, result["power"], borne, resolved, demand,
                               actual_structure, strength, diagnostics))
    if selected_total_t is not None and selected_total_t > config["target_displacement_t"]:
        result.setdefault("design_warnings", []).append(dict(
            code="design_balance.overweight",
            message="the selected ledger totals %.3f t against a declared target of %.3f t"
                    % (selected_total_t, config["target_displacement_t"])))
    elif selected_total_t is not None and selected_total_t < config["target_displacement_t"]:
        result.setdefault("design_warnings", []).append(dict(
            code="design_balance.underweight",
            message="the selected ledger totals %.3f t against a declared target of %.3f t"
                    % (selected_total_t, config["target_displacement_t"])))
    result["status"] = _status(result, diagnostics, demand, strength)
    if result["status"] != "completed":
        result["reason"] = ("one or more declared inputs are unknown or out of domain"
                            if any(d["blocking"] for d in diagnostics)
                            else "the screen is incomplete because selected mass is unclassified")
    result["validity"] = {"complete": result["status"] == "completed",
                          "numerical_convergence": None,
                          "model_applicable": True if result["status"] == "completed" else None,
                          "historical_validated": None}
    return result


def _status(result, diagnostics, demand, strength):
    if any(d["blocking"] for d in diagnostics):
        return "unavailable"
    if demand is None or strength is None or not result["screening_complete"]:
        return "partial"
    return "completed"


def _strength_scores(balance, demand, actual_structure):
    """Current strength at the SELECTED structure; the demand stays separate."""
    if demand is None or actual_structure is None:
        return None
    cross = demand["cross_coefficient"] * actual_structure
    long_value = demand["long_coefficient"] * actual_structure
    try:
        composite = kernels.strength_composite(cross, long_value)
    except ValueError as error:
        return None
    return {
        "cross": cross, "longitudinal": long_value, "composite": composite,
        "evaluated_at_structure_long_tons": actual_structure,
        "composite_target": balance["strength_target"],
        "broadside_lb": demand["broadside_lb"],
        "unit_convention": ("cross strength uses projectile POUNDS for the broadside term while "
                            "every other mass in the same empirical expression is LONG TONS; "
                            "structure surface density is lb/ft^2; the gun-armour term is "
                            "the selected rotating_armour plus gun_mount_armour, each counted "
                            "once, as the recovered guns.armWeight is. The barbette inside "
                            "gun_mount_armour is fixed structure and is not part of the "
                            "rotating total; this is a sum of two named roles, not a single "
                            "rotating figure."),
        "note": "empirical structural scores, not a physical safety certification",
    }


def _performance(config, hull, power, borne, resolved, demand, actual_structure, strength,
                 diagnostics):
    if borne is None or resolved is None or strength is None or demand is None \
            or actual_structure is None:
        return {}
    balance = config["balance"]
    totals = resolved["totals"]
    structure_lt = actual_structure
    # The recovered stability and seaboat terms read the same guns.armWeight
    # aggregate the strength terms do.
    gun_armour_lt = _gun_armour_long_tons(totals)
    try:
        _require(balance, BALANCE_REQUIRED, "$.concept_design.balance")
        if totals["bulkhead"] > BULKHEAD_NARROWING_MIN_LT:
            _require(balance, ("bulkhead_beam_m",), "$.concept_design.balance")
        room_hull = kernels.room_hull_ratio(
            magazine_lt=totals["ammunition"], displacement_lt=hull["displacement_long_tons"],
            borne_lt=borne, machinery_lt=totals["machinery"],
            misc_vital_lt=totals["misc_vital"], misc_hull_lt=totals["misc_hull"],
            space_hull_fraction=balance["space_hull_fraction"],
            bulkhead_beam_m=balance["bulkhead_beam_m"], beam_m=hull["beam_m"],
            bulkhead_lt=totals["bulkhead"])
        crew = kernels.crew_band(hull["displacement_long_tons"])
        room_deck = kernels.room_deck_ratio(hull["waterplane_area_sqft"],
                                             balance["space_deck_fraction"], crew["crew_min"],
                                             hull["freeboard_ft"])
        stability = kernels.stability_score(
            conning_lt=totals["conning"], borne_lt=borne,
            battery_armour_lt=gun_armour_lt, misc_hull_lt=totals["misc_hull"],
            misc_deck_lt=totals["misc_deck"], misc_above_lt=totals["misc_above"],
            belt_upper_lt=totals["belt_upper"], belt_main_lt=totals["belt_main"],
            belt_ends_lt=totals["belt_ends"], deck_lt=totals["armour_deck"],
            structure_lt=structure_lt, room_deck=room_deck, machinery_lt=totals["machinery"],
            misc_vital_lt=totals["misc_vital"], misc_void_lt=totals["misc_void"],
            displacement_lt=hull["displacement_long_tons"], beam_bulges_ft=hull["beam_ft"],
            length_beam=hull["length_beam"], draught_ft=hull["draught_ft"],
            freeboard_ft=hull["freeboard_ft"], super_factor=balance["super_factor"],
            steadiness=balance["steadiness"])
        seaboat, fraction = kernels.seaboat_score(
            stability["stability_score"], hull["freeboard_ft"],
            hull["displacement_long_tons"], hull["beam_ft"], hull["length_ft"],
            totals["belt_ends"], structure_lt, borne, gun_armour_lt,
            balance["super_factor_long"], hull["draught_ft"], power.get("friction_fraction"))
    except ValueError as error:
        diagnostics.append(_diag("concept_design.performance_unavailable", str(error),
                                 "$.concept_design.balance"))
        return {}
    steadiness_adjusted = kernels.steadiness_score(balance["steadiness"], seaboat)
    seakeeping = kernels.seakeeping_score(seaboat, steadiness_adjusted)
    composite = strength["composite"]
    warnings = []
    if composite < TENDER_COMPOSITE:
        warnings.append(dict(code="design_balance.structure_failure",
                             message="composite strength %.3f is below %.2f: the declared hull "
                                     "structure cannot carry the declared loads"
                                     % (composite, TENDER_COMPOSITE)))
    elif composite < balance["strength_target"]:
        warnings.append(dict(code="design_balance.structure_shortfall",
                             message="composite strength %.3f is below the declared target %.3f"
                                     % (composite, balance["strength_target"])))
    else:
        warnings.append(dict(code="design_balance.structure_sufficient",
                             message="composite strength %.3f meets the declared target %.3f"
                                     % (composite, balance["strength_target"])))
    if room_hull > CRAMPED_HULL_RATIO:
        warnings.append(dict(code="design_balance.hull_space_cramped",
                             message="hull space ratio %.3f is above %.4f: machinery, storage and "
                                     "compartmentation space is cramped" % (room_hull,
                                                                           CRAMPED_HULL_RATIO)))
    if room_deck < CRAMPED_DECK_RATIO:
        warnings.append(dict(code="design_balance.deck_room_cramped",
                             message="deck room ratio %.3f is below %.2f: accommodation and "
                                     "workspace room is cramped" % (room_deck, CRAMPED_DECK_RATIO)))
    if seakeeping < POOR_SEAKEPING:
        warnings.append(dict(code="design_balance.poor_seakeeping",
                             message="seakeeping score %.3f is below %.2f" % (seakeeping,
                                                                             POOR_SEAKEPING)))
    elif seakeeping < WEAK_SEAKEEPING:
        warnings.append(dict(code="design_balance.weak_seakeeping",
                             message="seakeeping score %.3f is below %.3f" % (seakeeping,
                                                                             WEAK_SEAKEEPING)))
    return {
        "space": {"hull_ratio": room_hull, "deck_ratio": room_deck,
                  "basis": "declared representative freeboard and declared space fractions"},
        "stability": {"score": stability["stability_score"],
                      "adjusted": stability["stability_adjusted"],
                      "note": "empirical score, not a physical GM and not a safety certificate"},
        "seakeeping": {"seaboat": seaboat, "steadiness_score": steadiness_adjusted,
                       "score": seakeeping, "friction_fraction_used": fraction},
        "crew": dict(crew, unit="persons",
                     basis="HullControl.cs:1272 crew band from the target displacement"),
        "design_warnings": warnings,
    }
