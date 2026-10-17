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
    from . import armour_geometry as armour_geometry_kernel
    from . import armour_review as armour_review_kernel
    from . import armour_defaults as armour_defaults_kernel
    from . import auxiliary_space as auxiliary_space_kernel
    from . import armour_totals as armour_totals_kernel
    from . import auxiliary_weapons as auxiliary_kernel
    from . import battery_armour as armour_kernel
    from . import battery_layout as layout_kernel
    from . import battery_mass_allocation as allocation_kernel
    from . import battery_totals as battery_totals_kernel
    from . import concept_cost as cost_kernel
    from . import concept_estimates as kernels
    from . import fixed_armour as fixed_armour_kernel
except ImportError:                                   # pragma: no cover - direct import
    import armour_geometry as armour_geometry_kernel
    import armour_review as armour_review_kernel
    import armour_defaults as armour_defaults_kernel
    import auxiliary_space as auxiliary_space_kernel
    import armour_totals as armour_totals_kernel
    import auxiliary_weapons as auxiliary_kernel
    import battery_armour as armour_kernel
    import battery_layout as layout_kernel
    import battery_mass_allocation as allocation_kernel
    import battery_totals as battery_totals_kernel
    import concept_cost as cost_kernel
    import concept_estimates as kernels
    import fixed_armour as fixed_armour_kernel

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

# The optional whole-battery mount allocation section. It selects existing
# layouts explicitly, suppresses their old per-row mount models and registers one
# allocation model per bound mount target. The declaration and the policy live in
# :mod:`battery_mass_allocation`; this module only wires the section into the
# concept model, the generated models and the balance reading.
BATTERY_MASS_ALLOCATION_FIELDS = ("source", "layout_ids")
BATTERY_MASS_ALLOCATION_SCOPE = (
    "Product allocation policy: the recovered source provides one whole-battery "
    "mounts estimate and no per-group split. This component divides that source "
    "across the selected layout's referenced rows in the proportion of each row's "
    "own independent mount estimate (proportional-row-mounts-v1). It is a declared "
    "product decision, never the original program's own per-group allocation, and "
    "it claims no gun, ammunition or complete layout-armour mass."
)

# The optional per-battery armour block. It is an independent component: its own
# owned target, its own kernel identity, and no dependence on the ammunition
# inputs the three original estimates share.
ARMOUR_FIELDS = ("system_id", "item_id", "face_mm", "rear_roof_mm", "barbette_mm",
                 "freeboard_m", "super_factor")

# The optional two-group layout section. A layout only *references* existing
# battery rows, so the normalization, the recovered selector and layout tables and
# the whole numerical reading belong to the layout kernel. This module owns the
# system and item ownership of the layout's own armour target and the role that
# target must carry, exactly as it does for the per-battery armour block.
LAYOUT_ARMOUR_ROLE = "gun_mount_armour"

# The optional fixed-armour section. The seven recovered regions, their declared
# domain, their recovered expressions and the whole numerical reading belong to
# the fixed-armour kernel. This module owns only what belongs to the concept
# model: the minimal canonical context each reading may use, the one owned target
# each record must have and the one balance role that target must carry.
#
# That context is deliberately **not** built behind :func:`hull_proxy`. The
# design hull proxy needs a declared freeboard, stern and screw count as well as
# the four canonical hull keys, while a simple planar plate and a conning tower
# read none of those. Putting every fixed-armour reading behind it would disable
# exactly the regions that need the least context, so each kernel reads the
# smallest canonical fact set it actually needs.
FIXED_ARMOUR_MODEL_PREFIX = "concept_fixed_armour"

# The optional armour-panel geometry family. It selects an existing eligible fixed
# region and replaces that region's old SPS mass model with a declared
# rectangular-plate model. The physical systems method recomputes the pure panel
# kernel from the complete declaration; the concept model is only a presentation
# and proposal carrier and is never an opaque mass.
GEOMETRY_MODEL_PREFIX = "concept_geometry"
ARMOUR_PANELS_METHOD = "armour_panels_mass_v1"

# The optional empirical cost reading. Money is a reading and never a weight:
# there is no ledger target, no cost model and no adoption path for it.
COST_FIELDS = ("source",)

# The optional auxiliary-weapon section. Torpedoes, mines and depth charges are
# independent of gun batteries and fixed armour: the recovered page owns their
# whole reading, and this module adds only the one owned target and the one
# existing balance role that target must carry. ``other`` is deliberately not in
# SUPPORTING_ROLES, MISC_ROLES or ARMOUR_ROLES, so a combined auxiliary mass
# contributes to the selected ledger without inventing a strength or space term.
AUXILIARY_MODEL_PREFIX = "concept_auxiliary"

# The optional component families a design-balance result may declare the method
# version of. These keys are what a saved report and a saved comparison gate on;
# they are deliberately *not* global request identities, and they are absent
# whenever no optional section is declared.
METHOD_FAMILY_BY_SECTION = ("fixed_armour", "armour_geometry", "layout", "cost", "auxiliary_weapons",
                             "armour_review", "battery_totals", "battery_mass_allocation",
                             "armour_totals", "armour_defaults", "auxiliary_space")

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
                "freeboard_m", "stern", "screws", "batteries", "battery_layouts",
                "battery_mass_allocation",
                "fixed_armour", "armour_geometry", "auxiliary_weapons", "armour_review", "cost", "machinery", "fuel",
                "balance", "mass_summary", "armour_defaults", "auxiliary_space"},
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
    if raw.get('armour_review') is not None:
        try:
            config['armour_review'] = armour_review_kernel.validate_config(raw['armour_review'])
        except armour_review_kernel.ReviewValidationError as error:
            diagnostics.extend(error.diagnostics)

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

    # The optional two-group layouts. An absent or empty section leaves every
    # existing result exactly as it was, so the key is only added when the
    # declaration exists.
    if "battery_layouts" in raw and raw["battery_layouts"] is not None:
        config["battery_layouts"] = _battery_layouts(
            raw["battery_layouts"], config["batteries"], path + ".battery_layouts", known,
            owned_targets, diagnostics, owned_by)

    # The optional whole-battery mount allocation section. It selects existing
    # layout IDs explicitly; absent or null it adds no family and changes no prior
    # model, so nothing here is set unless the declaration exists.
    if "battery_mass_allocation" in raw and raw["battery_mass_allocation"] is not None:
        config["battery_mass_allocation"] = _battery_mass_allocation(
            raw["battery_mass_allocation"], config.get("battery_layouts") or [],
            config["batteries"], path + ".battery_mass_allocation", diagnostics)

    # The optional fixed-armour regions, added before the balance section so a
    # fixed-armour target can never steal the adjustable-structure target and the
    # adjustable structure can never take a fixed-armour one.
    if "fixed_armour" in raw and raw["fixed_armour"] is not None:
        config["fixed_armour"] = _fixed_armour(
            raw["fixed_armour"], path + ".fixed_armour", known, owned_targets, diagnostics,
            owned_by)

    # The optional armour-panel geometry declaration, normalized only against the
    # existing fixed regions. It owns no ledger target of its own: it selects an
    # existing eligible fixed region and replaces that one region's old SPS mass
    # model with a declared rectangular-plate model. An absent or null section
    # preserves the complete old shape and every old empirical model.
    if "armour_geometry" in raw and raw["armour_geometry"] is not None:
        try:
            config["armour_geometry"] = armour_geometry_kernel.normalize(
                raw["armour_geometry"], config.get("fixed_armour") or [],
                path + ".armour_geometry")
        except armour_geometry_kernel.ArmourGeometryError as error:
            diagnostics.extend(error.diagnostics)

    # The optional auxiliary weapon groups, added before the balance section so an
    # auxiliary target can never steal the adjustable-structure target either.
    if "auxiliary_weapons" in raw and raw["auxiliary_weapons"] is not None:
        config["auxiliary_weapons"] = _auxiliary_weapons(
            raw["auxiliary_weapons"], path + ".auxiliary_weapons", known, owned_targets,
            diagnostics, owned_by)

    # The optional mass-summary declaration. It is a scope statement with no
    # ledger target of its own: absent or null adds no result family at all, and
    # present it turns on the two read-only whole-battery and armour-totals
    # readings. Nothing here is ever adopted as mass.
    if "mass_summary" in raw and raw["mass_summary"] is not None:
        config["mass_summary"] = _mass_summary(
            raw["mass_summary"], path + ".mass_summary", diagnostics)

    if raw.get("armour_defaults") is not None:
        try:
            config["armour_defaults"] = armour_defaults_kernel.validate_config(
                raw["armour_defaults"], path + ".armour_defaults")
        except armour_defaults_kernel.ArmourDefaultsError as error:
            diagnostics.extend(error.diagnostics)

    if raw.get("auxiliary_space") is not None:
        try:
            space = auxiliary_space_kernel.validate_config(raw["auxiliary_space"],
                config.get("auxiliary_weapons") or [], path + ".auxiliary_space")
            beam = _hull_number(project, "beam_m")
            width = space["bulged_beam_m"]
            if width is not None and beam is not None and width < beam:
                diagnostics.append(_diag("concept_design.domain",
                    "bulged_beam_m must be at least the canonical beam_m", path + ".auxiliary_space.bulged_beam_m"))
            config["auxiliary_space"] = space
        except auxiliary_space_kernel.AuxiliarySpaceError as error:
            diagnostics.extend(error.diagnostics)

    config["machinery"] = _machinery(raw.get("machinery"), path + ".machinery", known, leaves,
                                     owned_targets, diagnostics, owned_by)
    config["fuel"] = _fuel(raw.get("fuel"), path + ".fuel", known, leaves, owned_targets,
                           config["machinery"], diagnostics, owned_by)
    config["cost"] = _cost(raw.get("cost"), path + ".cost", diagnostics)
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
        for layout in config.get("battery_layouts") or []:
            armour = layout.get("armour")
            # The layout's own target is complete two-group gun-mount armour, so
            # it carries the same role as a single-group target and nothing else.
            required_roles.append(((armour or {}).get("item_id"), LAYOUT_ARMOUR_ROLE))
        for record in config.get("fixed_armour") or []:
            # Each fixed region keeps the one role its own recovered identity
            # carries: a conning tower is fixed structure, a bulge is its own
            # compartment, and none of the seven is ever merged into another.
            role = fixed_armour_kernel.ROLE_BY_KIND.get(record.get("kind"))
            if role is not None:
                required_roles.append((record.get("item_id"), role))
        for record in config.get("auxiliary_weapons") or []:
            # One combined weapon-and-mount mass on one target, under the existing
            # 'other' role. It is never relabelled as guns, mounts or ammunition,
            # and it contributes no strength or space term of its own.
            required_roles.append((record.get("item_id"), auxiliary_kernel.TARGET_ROLE))
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


def _battery_layouts(raw, batteries, path, known, owned_targets, diagnostics, owned_by):
    """The optional two-group layout declarations, with their own ownership rules.

    The declaration itself is normalized by the layout kernel, which owns the
    recovered selector tables, the reference checks and the numeric domain. This
    module only adds what belongs to the concept model: an independent owned
    target for the layout's complete two-group armour, and the refusal to let one
    battery group's armour be weighed twice under two models.
    """
    try:
        layouts = layout_kernel.validate_layouts(raw, batteries, path)
    except layout_kernel.LayoutValidationError as error:
        for entry in error.diagnostics:
            diagnostics.append(_diag(entry.get("code", "concept_design.invalid"),
                                     entry["message"], entry.get("path", path),
                                     blocking=entry.get("blocking", True)))
        return []
    by_id = {battery["id"]: battery for battery in batteries if battery.get("id")}
    for position, layout in enumerate(layouts):
        armour = layout.get("armour")
        lpath = "%s[%d]" % (path, position)
        if not isinstance(armour, dict):
            continue
        identity = layout.get("id") or "layout %d" % position
        owner = "%s layout armour" % (identity,)
        system_id = _string(armour.get("system_id"), lpath + ".armour.system_id", diagnostics,
                            nullable=True)
        item = _unbound_item(armour.get("item_id"), lpath + ".armour.item_id", known, diagnostics)
        if item is not None:
            if item in owned_targets:
                diagnostics.append(_diag("concept_design.duplicate_target",
                                         "item %r is already owned by %s" % (
                                             item, owned_targets[item]),
                                         lpath + ".armour.item_id"))
            else:
                owned_targets[item] = owner
                owned_by(system_id, item, lpath + ".armour.item_id", owner)
        # The complete two-group armour and the single-group v1 estimate of the
        # same row would weigh the same guns twice, so they are mutually exclusive.
        for field in ("group1", "group2"):
            group = layout.get(field)
            battery_id = group.get("battery_id") if isinstance(group, dict) else None
            battery = by_id.get(battery_id)
            if battery is not None and battery.get("armour") is not None:
                diagnostics.append(_diag(
                    "concept_design.duplicate_target",
                    "battery %r is already weighted by its own armour estimate, so this "
                    "layout may not weight the same group's armour a second time"
                    % (battery_id,), lpath + ".%s.battery_id" % (field,)))
    return layouts


def _battery_mass_allocation(raw, layouts, batteries, path, diagnostics):
    """The optional whole-battery mount allocation selection.

    ``layout_ids`` names the layouts whose old per-row mount models this product
    policy replaces with one proportional whole-battery allocation. A null
    selection is *unknown* and an empty list is an explicit *no layouts*; only
    explicit, existing layout IDs opt in. The declaration is normalized here and
    only here -- the allocation policy itself belongs to
    :mod:`battery_mass_allocation`, and this never imports a source total, a
    weight or a target.
    """
    if not _object(raw, path, diagnostics):
        return {"source": None, "layout_ids": None}
    _keys(raw, set(BATTERY_MASS_ALLOCATION_FIELDS), path, diagnostics)
    source = _string(raw.get("source"), path + ".source", diagnostics, nullable=True)
    by_id = {layout.get("id"): layout for layout in layouts if isinstance(layout, dict)}
    tol = {battery.get("id"): battery.get("mounts_item_id") for battery in batteries
           if isinstance(battery, dict)}
    declared = raw.get("layout_ids")
    if declared is None:
        return {"source": source, "layout_ids": None}
    if not isinstance(declared, list):
        diagnostics.append(_diag("concept_design.invalid",
                                 "must be an array of layout IDs or null", path + ".layout_ids"))
        return {"source": source, "layout_ids": None}
    selected = []
    battery_claims = {}
    targets = {}
    for position, value in enumerate(declared):
        where = "%s.layout_ids[%d]" % (path, position)
        if not isinstance(value, str) or not value:
            diagnostics.append(_diag("concept_design.invalid",
                                     "must be a non-empty layout ID", where))
            continue
        if value in selected:
            diagnostics.append(_diag("concept_design.duplicate",
                                     "layout %r is selected more than once" % (value,), where))
            continue
        layout = by_id.get(value)
        if layout is None:
            diagnostics.append(_diag("concept_design.reference_unknown",
                                     "must name a declared concept_design battery layout", where))
            continue
        # One selected layout owns each referenced battery row and each mount
        # target exactly once. Two selected layouts may never claim the same
        # battery or the same mount target, or the same row's weight would be
        # allocated twice and one target would receive two allocations.
        for name in ("group1", "group2"):
            group = layout.get(name)
            battery_id = group.get("battery_id") if isinstance(group, dict) else None
            if battery_id is None:
                continue
            owner = battery_claims.get(battery_id)
            if owner is not None:
                diagnostics.append(_diag(
                    "concept_design.duplicate_target",
                    "battery %r is already claimed by selected layout %r; a selected layout "
                    "allocates its referenced rows once" % (battery_id, owner), where))
            else:
                battery_claims[battery_id] = value
            target = tol.get(battery_id)
            if target is None:
                continue
            target_owner = targets.get(target)
            if target_owner is not None:
                diagnostics.append(_diag(
                    "concept_design.duplicate_target",
                    "mount target %r is already claimed by selected layout %r; one target "
                    "receives one allocation" % (target, target_owner), where))
            else:
                targets[target] = value
        selected.append(value)
    return {"source": source, "layout_ids": selected}


def _fixed_armour(raw, path, known, owned_targets, diagnostics, owned_by):
    """The optional fixed-armour declarations, with their own ownership rules.

    The declaration itself is normalized by the fixed-armour kernel, which owns
    the seven recovered kinds, the recovered selector table, the numeric domain
    and the whole reading. This module only adds what belongs to the concept
    model: an independent owned target per record and the refusal to let one
    fixed region, a layout component or a legacy battery component weigh the
    same ledger item twice.

    An unfinished binding is a legal editable state: it is never refused and
    never filled in, so a draft project stays saveable.
    """
    try:
        records = fixed_armour_kernel.validate_configs(raw, path)
    except fixed_armour_kernel.ArmourValidationError as error:
        for entry in error.diagnostics:
            diagnostics.append(_diag(entry.get("code", "concept_design.invalid"),
                                     entry["message"], entry.get("path", path),
                                     blocking=entry.get("blocking", True)))
        return []
    for position, record in enumerate(records):
        rpath = "%s[%d]" % (path, position)
        system_id = _string(record.get("system_id"), rpath + ".system_id", diagnostics,
                            nullable=True)
        item = _unbound_item(record.get("item_id"), rpath + ".item_id", known, diagnostics)
        if item is None:
            continue
        owner = "%s fixed armour" % (record.get("id") or "record %d" % position,)
        if item in owned_targets:
            diagnostics.append(_diag("concept_design.duplicate_target",
                                     "item %r is already owned by %s" % (
                                         item, owned_targets[item]), rpath + ".item_id"))
            continue
        owned_targets[item] = owner
        owned_by(system_id, item, rpath + ".item_id", owner)
    return records


def _auxiliary_weapons(raw, path, known, owned_targets, diagnostics, owned_by):
    """The optional auxiliary weapon groups, with their own ownership rules.

    The recovered page owns the three kinds, their declared domain and the whole
    reading. This module only adds what belongs to the concept model: one
    independent owned target per group and the refusal to let an auxiliary group,
    a battery component, a layout component, a fixed region or the adjustable
    structure weigh the same ledger item twice.
    """
    try:
        records = auxiliary_kernel.validate_configs(raw, path)
    except auxiliary_kernel.AuxiliaryValidationError as error:
        for entry in error.diagnostics:
            diagnostics.append(_diag(entry.get("code", "concept_design.invalid"),
                                     entry["message"], entry.get("path", path),
                                     blocking=entry.get("blocking", True)))
        return []
    for position, record in enumerate(records):
        rpath = "%s[%d]" % (path, position)
        system_id = _string(record.get("system_id"), rpath + ".system_id", diagnostics,
                            nullable=True)
        item = _unbound_item(record.get("item_id"), rpath + ".item_id", known, diagnostics)
        if item is None:
            continue
        owner = "%s auxiliary weapons" % (record.get("id") or "record %d" % position,)
        if item in owned_targets:
            diagnostics.append(_diag("concept_design.duplicate_target",
                                     "item %r is already owned by %s" % (
                                         item, owned_targets[item]), rpath + ".item_id"))
            continue
        owned_targets[item] = owner
        owned_by(system_id, item, rpath + ".item_id", owner)
    return records


def _mass_summary(raw, path, diagnostics):
    """The optional mass-summary declaration: a source text and a scope flag.

    It owns no ledger target and no mass of its own, so nothing here is claimed,
    bound or refused beyond the section's own shape. ``armour_scope_complete`` is
    ``null`` until the reader confirms it: only ``True`` says the declarations
    cover every armour category and every category left out is a declared zero. A
    ``null`` or ``false`` flag keeps the known subtotal readable but never
    produces a complete estimated total.
    """
    if not _object(raw, path, diagnostics):
        return None
    _keys(raw, {"source", "armour_scope_complete"}, path, diagnostics)
    source = _string(raw.get("source"), path + ".source", diagnostics, nullable=True)
    complete = raw.get("armour_scope_complete")
    if complete is not None and not isinstance(complete, bool):
        diagnostics.append(_diag("concept_design.invalid",
                                 "armour_scope_complete must be a boolean or null",
                                 path + ".armour_scope_complete"))
        complete = None
    return {"source": source, "armour_scope_complete": complete}


def _cost(raw, path, diagnostics):
    """The optional empirical cost declaration: an explicit on/off and a source.

    An absent or null section is disabled and adds no field anywhere. The cost
    reading owns no ledger target, so there is nothing here to claim, bind or
    refuse beyond the section's own shape.
    """
    if raw is None:
        return None
    if not _object(raw, path, diagnostics):
        return None
    _keys(raw, set(COST_FIELDS), path, diagnostics)
    return {"source": _string(raw.get("source"), path + ".source", diagnostics, nullable=True)}


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

    suppressed = _suppressed_mount_batteries(config)
    for battery in config["batteries"]:
        _battery_models(config, battery, register, diagnostics, suppressed)
    # The layout armour is generated independently of, and before, the design
    # hull proxy: a project whose hull is not physical yet still gets its own
    # layout reading, exactly as it still gets its own battery estimates.
    _layout_models(config, register, diagnostics)
    # The whole-battery mount allocation is generated here too. It reads the
    # recovered source total and the row weights but no hull fact, and it is the
    # selected layouts' replacement for the per-row mount models suppressed
    # above; an unavailable allocation contributes a diagnostic instead.
    _allocation_models(config, register, diagnostics)
    # The fixed armour is generated the same way and for the same reason: a
    # simple planar plate and a conning tower read none of the hull proxy's
    # freeboard, stern or screw facts, so they must not be behind it.
    _fixed_armour_models(project, config, state, register, diagnostics)
    # Auxiliary weapon groups read no hull geometry at all, so they are generated
    # here too rather than behind the design hull proxy.
    _auxiliary_models(config, register, diagnostics)
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


def _exact_whole_battery_comparison(active):
    """Explicit whole mode exposes small differences without changing formulas."""
    return ({"comparison_tolerance": {"relative": 0.0, "absolute_t": 0.0},
             "comparison_policy": "whole-battery-exact-alignment-v1"} if active else {})


def _battery_models(config, battery, register, diagnostics, suppressed=frozenset()):
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
                if key == "mounts" and battery["id"] in suppressed:
                    # A selected layout now owns this row's mount mass through the
                    # whole-battery allocation; the old per-row model is retired
                    # even when the allocation itself is still unavailable.
                    continue
                provenance = estimates["provenance"][kernel]
                register(battery["system_id"], _model(
                    "%s.%s" % (prefix, key), battery[field],
                    estimates["values"][key + "_long_tons"],
                    provenance["kernel"], provenance["source_location"], provenance["formula"],
                    provenance["inputs"], config["source"],
                    extra={"concept_battery_id": battery["id"], "concept_component": key,
                           **_exact_whole_battery_comparison(key == "guns" and battery["id"] in suppressed)}))
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


def _layout_models(config, register, diagnostics):
    """One ``concept_layout.<id>.armour`` model per declared layout, if it has one.

    The layout kernel owns the whole reading: this stage only registers a model on
    the layout's own already-validated target, in the layout's own method, and
    keeps an unavailable or unadopted declaration a diagnostic instead of a model.
    """
    for layout in config.get("battery_layouts") or []:
        armour = layout.get("armour")
        if not isinstance(armour, dict) or None in (armour.get("system_id"),
                                                     armour.get("item_id")):
            continue
        identity = layout.get("id")
        exact_alignment = identity in ((config.get("battery_mass_allocation") or {}).get("layout_ids") or [])
        path = "$.concept_design.battery_layouts[%s].armour" % (identity,)
        try:
            result = layout_kernel.evaluate(layout, config["batteries"], path)
        except (ValueError, ArithmeticError) as error:
            diagnostics.append(_diag("concept_design.layout_unavailable", str(error), path,
                                     blocking=False))
            continue
        for entry in result.get("diagnostics", ()):
            diagnostics.append(_diag(entry.get("code", "concept_design.layout_unavailable"),
                                     entry["message"], entry.get("path", path),
                                     blocking=False))
        armour_result = result.get("armour")
        if not isinstance(armour_result, dict):
            continue
        values = armour_result["values"]
        if values.get("total_long_tons") is None:
            continue
        # The existing empirical pipeline converts LT via kg before tonnes. Do not
        # register a model whose otherwise finite LT would overflow that boundary.
        if not math.isfinite(values["total_long_tons"] * kernels.LONG_TON_KG):
            diagnostics.append(_diag(
                "concept_design.layout_unavailable",
                "the derived layout armour mass exceeds the supported weight-conversion range",
                path, blocking=False))
            continue
        provenance = armour_result["provenance"]
        register(armour["system_id"], _model(
            "concept_layout.%s.armour" % (identity,), armour["item_id"],
            values["total_long_tons"], provenance["kernel"], provenance["source_location"],
            provenance["formula"], provenance["inputs"], config["source"],
            method_version=layout_kernel.ARMOUR_METHOD_VERSION,
            boundary=layout_kernel.ARMOUR_SOURCE_SCOPE,
            extra={"concept_layout_id": identity, "concept_component": "armour",
                   **_exact_whole_battery_comparison(exact_alignment),
                   "assumptions": provenance["assumptions"],
                   "component_breakdown": {
                       "face_long_tons": values["face_long_tons"],
                       "rear_roof_long_tons": values["rear_roof_long_tons"],
                       "barbette_long_tons": values["barbette_long_tons"]},
                   "guns_in_mount_selector_g1": values["guns_in_mount_selector_g1"],
                   "guns_in_mount_selector_g2": values["guns_in_mount_selector_g2"],
                   "per_mounts": values["per_mounts"],
                   "freeboard_m": result.get("freeboard_m"),
                   "super_factor": result.get("super_factor"),
                   "note": ("complete gun-house and barbette armour of both recovered mount "
                            "groups of this layout, read with both recovered diameter classes; "
                            "it is not the sum of the per-row gun, mount and ammunition "
                            "estimates, which stay sps-3b3-adapted-v1, and it contains no part "
                            "of either mount's mass. A barbette is fixed structure, not "
                            "rotating armour. A reader who already carries this armour inside "
                            "a mount item must split the target first; no split is generated "
                            "and nothing is deducted from a declared mount mass automatically")}))


# ------------------------------------------------- the mount allocation --

def _suppressed_mount_batteries(config):
    """The battery rows whose old per-row mount model a selected layout replaces.

    Suppression is by **layout scope**, not by whether the new estimate exists:
    once a layout is selected, its referenced rows' old mount models are retired
    even while the whole-battery allocation itself is still unavailable, so an
    unavailable group never silently falls back to the old per-row number. Guns,
    ammunition and layout-armour formulas are never replaced. Explicit whole
    mode exposes even in-tolerance gun/layout-armour differences for alignment.
    """
    selection = config.get("battery_mass_allocation")
    if not selection:
        return frozenset()
    selected = set(selection.get("layout_ids") or [])
    if not selected:
        return frozenset()
    rows = set()
    for layout in config.get("battery_layouts") or []:
        if layout.get("id") not in selected:
            continue
        for name in ("group1", "group2"):
            group = layout.get(name)
            if isinstance(group, dict) and group.get("battery_id") is not None:
                rows.add(group["battery_id"])
    return frozenset(rows)


def _row_mount_weight_t(battery, path):
    """One row's own independent mount estimate in tonnes, or ``None`` if unknown.

    The weight reads only the facts the recovered mount expression needs -- the
    calibre, the barrel length, the year, the gun and mount classes, the mount
    count and the cradle. It deliberately reads **no** ammunition input, so the
    allocation can never depend on ``rounds_per_gun`` or on a shell override.
    """
    mounts = battery.get("mount_count")
    if mounts == 0:
        # A declared zero mount count multiplies the recovered expression into a
        # determined zero, exactly as the per-row estimate reads it.
        return 0.0
    numeric = (battery.get("calibre_mm"), battery.get("barrel_calibres"), battery.get("year"),
               battery.get("gun_type"), battery.get("mount_type"), mounts,
               battery.get("barrels_per_mount"))
    shared = battery.get("shared_cradle")
    if any(value is None or isinstance(value, bool) for value in numeric) \
            or not isinstance(shared, bool):
        return None
    try:
        calibre_in = kernels.millimetres_to_inches(battery["calibre_mm"], path)
        date_factor = kernels.gun_date_factor(battery["year"], path)
        count = mounts * battery["barrels_per_mount"]
        gun_lt = kernels.gun_mass_long_tons(calibre_in, battery["barrel_calibres"], date_factor,
                                            count, path)
        mounts_lt = kernels.mount_mass_long_tons(
            gun_lt, calibre_in, battery["gun_type"], battery["mount_type"],
            shared_cradle=shared, path=path)
        return kernels.long_tons_to_tonnes(mounts_lt, path)
    except (ValueError, ArithmeticError):
        return None


def _allocation_context(config, layout, batteries_by_id, source, layout_reading=None,
                        diagnostics=None):
    """The referenced rows, the recovered source total and the proportional split.

    The source total is the recovered whole-battery **mounts** estimate of this
    layout, in tonnes, read from :mod:`battery_totals` -- never the gun or the
    ammunition total, and never a per-row figure. The weight of a row is that
    row's own independent mount estimate. The split is decided by
    :func:`battery_mass_allocation.allocate`, which owns the product policy.
    """
    identity = layout.get("id")
    path = "$.concept_design.battery_mass_allocation[%s]" % (identity,)
    referenced = []
    seen = set()
    unresolved = False
    for name in ("group1", "group2"):
        if name not in layout:
            continue
        group = layout.get(name)
        if group is None:
            continue
        battery_id = group.get("battery_id") if isinstance(group, dict) else None
        battery = batteries_by_id.get(battery_id) if battery_id is not None else None
        if battery is None:
            # A declared, non-empty group whose referenced row is unresolved opens
            # the selected boundary: the membership of what it carries cannot be
            # closed, so the parent mount subtotal is unknown even while a
            # surviving row's own bound actual stays readable. This mirrors the
            # battery-totals selected mirror exactly.
            unresolved = True
            continue
        if battery["id"] not in seen:
            seen.add(battery["id"])
            referenced.append(battery)
    source_t = None
    try:
        source_t = battery_totals_kernel.evaluate(
            layout, config["batteries"], layout_reading, path)["values"]["mounts_t"]
    except (ValueError, ArithmeticError) as error:
        if diagnostics is not None:
            diagnostics.append(_diag("concept_design.battery_mass_allocation_unavailable",
                                     str(error), path, blocking=False))
    rows = [{"battery_id": battery["id"], "target_id": battery.get("mounts_item_id"),
             "weight_t": _row_mount_weight_t(battery, path)} for battery in referenced]
    known = [row["weight_t"] for row in rows if row["weight_t"] is not None]
    legacy_t = (sum(known) if rows and not unresolved and len(known) == len(rows) else None)
    allocation = None
    # A required mount target that is not bound, or a declared group that never
    # resolved to a row, blocks the whole allocation: the policy could still
    # divide, but the boundary of what the split would cover cannot be closed.
    if rows and not unresolved and all(row["target_id"] is not None for row in rows):
        try:
            allocation = allocation_kernel.allocate(identity, source_t, rows, source=source)
        except allocation_kernel.AllocationError as error:
            if diagnostics is not None:
                diagnostics.extend(
                    _diag(entry.get("code", "concept_design.battery_mass_allocation_invalid"),
                          entry["message"], entry.get("path", path), blocking=False)
                    for entry in error.diagnostics)
            allocation = None
    return {"layout_id": identity, "source": source, "rows": rows, "referenced": referenced,
            "source_t": source_t, "legacy_t": legacy_t, "unresolved": unresolved,
            "allocation": allocation}


def _allocation_reading(context, state):
    """The read-only allocation record, merged with the independent selected mirror."""
    allocation = context["allocation"]
    pure_by_id = ({record["id"]: record for record in allocation["records"]}
                  if allocation is not None else {})
    records = []
    for row in context["rows"]:
        target_id = row["target_id"]
        pure = pure_by_id.get(row["battery_id"])
        records.append({
            "id": row["battery_id"],
            "method_version": allocation_kernel.METHOD_VERSION,
            "target_id": target_id,
            "weight_t": row["weight_t"],
            "share": pure["share"] if pure is not None else None,
            "allocated_mass_t": pure["allocated_mass_t"] if pure is not None else None,
            "selected_mass_t": _mass_of(state, target_id) if target_id is not None else None,
        })
    targets = [row["target_id"] for row in context["rows"] if row["target_id"] is not None]
    # The parent subtotal is closed only when every declared group resolved to a
    # bound target. An unresolved declared group, or a resolved row whose mount
    # target is unbound, leaves it unknown rather than reporting a smaller sum --
    # the same boundary the battery-totals selected mirror draws.
    if context["unresolved"] or any(row["target_id"] is None for row in context["rows"]):
        selected_mounts_t = None
    else:
        selected_mounts_t = _selected_target_t(state, targets)
    values = {
        "source_mounts_t": context["source_t"],
        "legacy_mounts_t": (allocation["values"]["legacy_mounts_t"]
                            if allocation is not None else context["legacy_t"]),
        "allocated_total_t": (allocation["values"]["allocated_total_t"]
                              if allocation is not None else None),
        "selected_mounts_t": selected_mounts_t,
    }
    status = ("available" if allocation is not None and allocation["status"] == "available"
              else "unavailable")
    if status != "available" and (selected_mounts_t is not None
                                  or any(record["selected_mass_t"] is not None
                                         for record in records)):
        # The source or a weight could not be closed, but the selected ledger
        # actuals are independent of it, so the record is partial rather than
        # unavailable and the ledger is never written into the missing values.
        status = "partial"
    return {
        "id": context["layout_id"],
        "method_version": allocation_kernel.METHOD_VERSION,
        "status": status,
        "values": values,
        "records": records,
        "diagnostics": list(allocation["diagnostics"]) if allocation is not None else [],
        "provenance": (allocation["provenance"] if allocation is not None else {
            "source_method_version": allocation_kernel.SOURCE_METHOD_VERSION,
            "allocation_policy": allocation_kernel.POLICY,
            "declared_source": context["source"]}),
    }


def _allocation_readings(config, layout_readings, state, diagnostics):
    """One allocation reading per explicitly selected layout, in layout order."""
    selection = config.get("battery_mass_allocation") or {}
    selected = set(selection.get("layout_ids") or [])
    if not selected:
        return []
    by_id = {reading.get("id"): reading for reading in layout_readings
             if isinstance(reading, dict)}
    batteries_by_id = {battery["id"]: battery for battery in config["batteries"]
                       if battery.get("id")}
    readings = []
    for layout in config.get("battery_layouts") or []:
        if layout.get("id") not in selected:
            continue
        context = _allocation_context(config, layout, batteries_by_id, selection.get("source"),
                                      by_id.get(layout.get("id")), diagnostics)
        readings.append(_allocation_reading(context, state))
    return readings


def _allocation_model(config, layout, battery, record, context, target_ids, long_tons):
    """One zero-tolerance allocation model on a bound existing mount target.

    The model carries the recomputed cohort metadata in its own ``inputs`` (the
    group, the policy, the target list and the source and weight details), so the
    server can rebuild the cohort from an immutable snapshot and never trust a
    client-supplied one.
    """
    identity = layout.get("id")
    group_id = "battery-mounts:%s" % (identity,)
    inputs = {
        "battery_id": battery["id"],
        "layout_id": identity,
        "target_id": record["target_id"],
        "weight_t": record["weight_t"],
        "share": record["share"],
        "source_mounts_t": context["source_t"],
        "legacy_mounts_t": context["legacy_t"],
        "allocated_mass_t": record["allocated_mass_t"],
        "allocation_group_id": group_id,
        "allocation_policy": allocation_kernel.POLICY,
        "allocation_target_ids": list(target_ids),
        "source_method_version": allocation_kernel.SOURCE_METHOD_VERSION,
        "declared_source": context["source"],
    }
    return _model(
        "concept_allocation.%s.%s" % (identity, battery["id"]), record["target_id"], long_tons,
        "battery_mount_allocation_long_tons",
        "product policy proportional-row-mounts-v1 over the recovered whole-battery mounts",
        "allocated_lt = recovered whole-battery mounts x (row weight / legacy row weight sum); "
        "a zero-weight row is an explicit zero and the floating residual goes to the last "
        "positive row",
        inputs, config["source"],
        method_version=allocation_kernel.METHOD_VERSION,
        boundary=BATTERY_MASS_ALLOCATION_SCOPE,
        extra={"concept_battery_id": battery["id"], "concept_layout_id": identity,
               "concept_component": "allocation", "allocation_group_id": group_id,
               "allocation_policy": allocation_kernel.POLICY,
               "allocation_target_ids": list(target_ids),
               "comparison_tolerance": {"relative": 0.0, "absolute_t": 0.0},
               "note": ("a declared product split of the recovered whole-battery mount estimate "
                        "across this layout's referenced rows, in proportion to each row's own "
                        "independent mount estimate; it is not the recovered program's own "
                        "per-group allocation, it claims no gun, ammunition or complete "
                        "layout-armour mass, and the whole cohort is adopted together or not "
                        "at all")})


def _allocation_models(config, register, diagnostics):
    """One allocation model per bound mount target of every selected layout.

    A selected layout whose allocation is unavailable registers no substitute
    model -- its old per-row mount models are already suppressed -- and a target
    that is not bound is never invented.
    """
    selection = config.get("battery_mass_allocation") or {}
    selected = set(selection.get("layout_ids") or [])
    if not selected:
        return
    batteries_by_id = {battery["id"]: battery for battery in config["batteries"]
                       if battery.get("id")}
    for layout in config.get("battery_layouts") or []:
        if layout.get("id") not in selected:
            continue
        context = _allocation_context(config, layout, batteries_by_id, selection.get("source"),
                                      None, diagnostics)
        allocation = context["allocation"]
        if allocation is None or allocation["status"] != "available":
            continue
        target_ids = [row["target_id"] for row in context["rows"]
                      if row["target_id"] is not None]
        for record in allocation["records"]:
            if record["allocated_mass_t"] is None:
                continue
            battery = batteries_by_id.get(record["id"])
            if battery is None or battery.get("system_id") is None:
                continue
            long_tons = record["allocated_mass_t"] * 1000.0 / kernels.LONG_TON_KG
            if not math.isfinite(long_tons * kernels.LONG_TON_KG):
                diagnostics.append(_diag(
                    "concept_design.battery_mass_allocation_unavailable",
                    "the allocated mount mass exceeds the supported weight-conversion range",
                    "$.concept_design.battery_mass_allocation[%s]" % (layout.get("id"),),
                    blocking=False))
                continue
            register(battery["system_id"], _allocation_model(
                config, layout, battery, record, context, target_ids, long_tons))


# ------------------------------------------------------- the fixed armour --

def _hull_number(project, key):
    value = (project.get("hull") or {}).get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _declared_fact(value, source, estimate=False):
    """One canonical context fact with its own recorded provenance."""
    return None if value is None else {"value": value, "source": source, "estimate": estimate}


def _selected_role_mass_t(resolved, role):
    """The selected ledger mass of one explicit balance role, in metric tonnes.

    An empty explicitly allocated role is a determined zero. An unknown selected
    mass stays ``None``: it is never read as zero, because the recovered box-deck
    expression keeps a positive margin for a known zero and that margin would
    read as a real machinery box.
    """
    if resolved is None:
        return None
    entries = resolved["by_role"].get(role) or []
    if any(mass is None for _item, mass in entries):
        return None
    return sum(float(mass) for _item, mass in entries)


def _auxiliary_space_context(project, config, diagnostics):
    """Only the space denominators' dependencies; freeboard is unrelated."""
    length = _hull_number(project, "lwl_m")
    beam = _hull_number(project, "beam_m")
    block = _hull_number(project, "block_coeff")
    context = {key: _declared_fact(value, origin) for key, value, origin in (
        ("length_m", length, "canonical $.hull.lwl_m"),
        ("beam_m", beam, "canonical $.hull.beam_m"),
        ("draught_m", _hull_number(project, "draught_normal_m"), "canonical $.hull.draught_normal_m"),
        ("block_coeff", block, "canonical $.hull.block_coeff"))}
    area = None
    if (length is not None and length > 0 and beam is not None and beam > 0 and block is not None
            and config.get("stern") and config.get("screws") is not None):
        try:
            coefficient = kernels.waterplane_coefficient(block, config["stern"], config["screws"], "$.hull")
            area = kernels.waterplane_area_sqft(coefficient, kernels.metres_to_feet(length, "$.hull.lwl_m"),
                kernels.metres_to_feet(beam, "$.hull.beam_m"), "$.hull") * kernels.M_PER_FT**2
            if not math.isfinite(area):
                raise ValueError("waterplane area proxy exceeds the finite domain")
        except (ValueError, OverflowError) as error:
            area = None
            diagnostics.append(_diag("concept_design.auxiliary_space_context", str(error), "$.hull", blocking=False))
    context["waterplane_area_m2"] = _declared_fact(area,
        "sps-3b3-adapted-v1 waterplane proxy from L, ordinary B, Cb, stern and screws; not measured geometry", True)
    return context


def _fixed_armour_context(project, config, state, diagnostics):
    """The minimal canonical context the fixed-armour kernels may read.

    The waterplane facts come from the same versioned proxy helpers
    :func:`hull_proxy` uses, but they are read directly here so a project without
    a declared freeboard, stern or screw count still gets its simple planar
    plates, belts and conning towers. A helper that cannot evaluate one of its
    own inputs leaves exactly that fact unknown with a non-blocking diagnostic
    instead of failing the stage.
    """
    length_m = _hull_number(project, "lwl_m")
    beam_m = _hull_number(project, "beam_m")
    block = _hull_number(project, "block_coeff")
    context = {
        "length_m": _declared_fact(length_m, "canonical hull key $.hull.lwl_m"),
        "beam_m": _declared_fact(beam_m, "canonical hull key $.hull.beam_m"),
        "displacement_t": _declared_fact(
            config.get("target_displacement_t"),
            "declared concept target $.concept_design.target_displacement_t"),
    }
    coefficient = None
    if (length_m is not None and beam_m is not None and length_m > 0.0 and beam_m > 0.0
            and block is not None and config.get("stern") and config.get("screws") is not None):
        try:
            coefficient = kernels.waterplane_coefficient(
                block, config["stern"], config["screws"], "$.hull")
        except ValueError as error:
            diagnostics.append(_diag("concept_design.fixed_armour_context", str(error),
                                     "$.hull", blocking=False))
    context["co_waterplane"] = _declared_fact(
        coefficient,
        "recovered sps-3b3-adapted-v1 waterplane proxy from $.hull.block_coeff, "
        "$.concept_design.stern and $.concept_design.screws", True)
    waterplane_m2 = None
    if coefficient is not None:
        waterplane_m2 = kernels.waterplane_area_sqft(
            coefficient, kernels.metres_to_feet(length_m, "$.hull.lwl_m"),
            kernels.metres_to_feet(beam_m, "$.hull.beam_m"),
            "$.hull") * kernels.M_PER_FT * kernels.M_PER_FT
    context["waterplane_area_m2"] = _declared_fact(
        waterplane_m2,
        "recovered sps-3b3-adapted-v1 waterplane area = co_waterplane x length x beam, "
        "converted to square metres", True)
    resolved = _role_masses(config, state)
    context["machinery_mass_t"] = _declared_fact(
        _selected_role_mass_t(resolved, "machinery"),
        "selected ledger items mapped to the declared 'machinery' balance role")
    context["ammunition_mass_t"] = _declared_fact(
        _selected_role_mass_t(resolved, "ammunition"),
        "selected ledger items mapped to the declared 'ammunition' balance role")
    return context


def _fixed_armour_note(kind):
    return (
        "independent recovered estimate of this one fixed armour region (%s), in its own "
        "sps-3b3-fixed-armour-v1 method and its own long tons. It is not the sum of any "
        "other component and it contains no part of any other item's mass. A reader who "
        "already carries this armour inside another weight must split that target first; "
        "no split is generated and nothing is deducted from a declared mass automatically. "
        "No armour mesh, inclination, protection rating or centre of gravity is created"
        % (kind,))


def _fixed_armour_models(project, config, state, register, diagnostics):
    """One ``concept_fixed_armour.<id>`` model per bound, available fixed region.

    These models are generated before the design hull proxy on purpose: a simple
    planar plate and a conning tower need none of the hull proxy's freeboard,
    stern or screw facts, so a project whose design hull is not physical yet
    still gets its own fixed-armour reading.

    A fixed region that the armour-panel geometry selects is suppressed here even
    when its geometry is incomplete or unsourced: an opted region never keeps its
    old empirical model as a hidden fallback. Its replacement, when the geometry
    is adoptable and its mass is known, is registered by :func:`_geometry_models`.
    """
    records = config.get("fixed_armour") or []
    if not records:
        return
    opted = _geometry_opted_ids(config)
    context = _fixed_armour_context(project, config, state, diagnostics)
    for record in records:
        identity = record.get("id")
        if identity in opted:
            continue
        path = "$.concept_design.fixed_armour[%s]" % (identity,)
        try:
            result = fixed_armour_kernel.evaluate(record, context, path)
        except (ValueError, ArithmeticError) as error:
            diagnostics.append(_diag("concept_design.fixed_armour_unavailable", str(error),
                                     path, blocking=False))
            continue
        for entry in result["diagnostics"]:
            diagnostics.append(_diag(entry.get("code", "concept_design.fixed_armour_unavailable"),
                                     entry["message"], entry.get("path", path), blocking=False))
        if identity is None or None in (record.get("system_id"), record.get("item_id")):
            continue
        values = result["values"]
        if values["total_long_tons"] is None:
            continue
        # The existing empirical pipeline converts LT via kg before tonnes. Do not
        # register a model whose otherwise finite LT would overflow that boundary.
        if not math.isfinite(values["total_long_tons"] * kernels.LONG_TON_KG):
            diagnostics.append(_diag(
                "concept_design.fixed_armour_unavailable",
                "the derived fixed armour mass exceeds the supported weight-conversion range",
                path, blocking=False))
            continue
        provenance = result["provenance"]
        # Persisted mass receipts accept a flat scalar input map. The whole
        # declaration, the whole context and the whole provenance travel as
        # explicit origin text instead of widening the receipt schema.
        model_inputs = dict(provenance["inputs"], origin=result["origin"])
        register(record["system_id"], _model(
            "%s.%s" % (FIXED_ARMOUR_MODEL_PREFIX, identity,), record["item_id"],
            values["total_long_tons"], provenance["kernel"], provenance["source_location"],
            provenance["formula"], model_inputs, config["source"],
            method_version=fixed_armour_kernel.METHOD_VERSION,
            boundary=fixed_armour_kernel.SOURCE_SCOPE,
            extra={"concept_component": "fixed_armour",
                   "assumptions": provenance["assumptions"],
                   "component_breakdown": fixed_armour_kernel.component_breakdown(
                       values, record.get("kind")),
                   "note": _fixed_armour_note(record.get("kind"))}))
    _geometry_models(config, register, diagnostics)


def _geometry_opted_ids(config):
    """The fixed-armour ids the armour-panel geometry selects, even if unfinished."""
    geometry = config.get("armour_geometry")
    if not geometry:
        return set()
    return {region.get("fixed_armour_id") for region in geometry.get("regions") or []
            if region.get("fixed_armour_id") is not None}


def _geometry_note(region, kind):
    return (
        "declared rectangular-plate geometry of this one fixed armour region (%s), "
        "recomputed by the pure plimsoll-armour-panels-v1 kernel from the complete "
        "plate declaration; it replaces this region's old empirical SPS reading rather "
        "than adding to it. Area sums every declared layer and is never a coverage "
        "union; there is no fabrication allowance, taper, support, fastener or curved "
        "area and no centre of gravity." % (kind,))


def _geometry_model(region, kind, source, record, config_source):
    """One physical ``armour_panels_mass_v1`` model carrying the complete region.

    The inputs are exactly the four pinned keys, so a receipt recomputes the panel
    model from the declaration itself instead of trusting an opaque mass.
    """
    inputs = {
        "method_version": armour_geometry_kernel.METHOD_VERSION,
        "region_kind": kind,
        "geometry_source": source,
        "region": copy.deepcopy(region),
    }
    provenance_source = source if isinstance(source, str) and source.strip() else config_source
    return dict(
        id="%s.%s" % (GEOMETRY_MODEL_PREFIX, region.get("fixed_armour_id")),
        method=ARMOUR_PANELS_METHOD, linked_weight_item_id=record["item_id"],
        inputs=inputs,
        source=dict(
            source=declaration_of(source, "plimsoll-armour-panels-v1",
                                  "declared plate geometry"),
            method_version=armour_geometry_kernel.METHOD_VERSION),
        estimate=True,
        input_provenance={key: dict(source=provenance_source, estimate=True) for key in inputs},
        comparison_tolerance={"relative": 0.0, "absolute_t": 0.0},
        comparison_policy=COMPARISON_POLICY,
        boundary=("declared rectangular armour plate geometry; no fabrication allowance, "
                  "fastener, curved area, coverage union or centre of gravity"),
        concept_component="fixed_armour",
        component_breakdown={"plate_count": len(region.get("plates") or [])},
        note=_geometry_note(region, kind),
    )


def _geometry_models(config, register, diagnostics):
    """One physical geometry model per opted region whose reading is adoptable.

    A region whose reading is not adoptable, or whose complete mass is unknown,
    produces no model: it still suppresses the old SPS model and still exposes its
    own design-balance reading, but it never contributes a mass anywhere.
    """
    geometry = config.get("armour_geometry")
    if not geometry:
        return
    source = geometry.get("source")
    by_id = {record.get("id"): record for record in config.get("fixed_armour") or []}
    for region in geometry.get("regions") or []:
        record = by_id.get(region.get("fixed_armour_id"))
        if not isinstance(record, dict):
            continue
        if record.get("system_id") is None or record.get("item_id") is None:
            continue
        kind = record.get("kind")
        if kind not in armour_geometry_kernel.ELIGIBLE_KINDS:
            continue
        result = armour_geometry_kernel.evaluate(region, kind, source=source)
        if not result["adoptable"]:
            continue
        mass = result["values"]["mass_t"]
        if mass is None or not math.isfinite(mass):
            continue
        register(record["system_id"], _geometry_model(region, kind, source, record, config["source"]))


def _auxiliary_context(config):
    """The one canonical fact an auxiliary weapon reading may read.

    An active torpedo reads the declared hull year; a mine or depth charge does not
    read it at all, so a missing or refused year never disables those two.
    """
    return {"hull_year": _declared_fact(config.get("hull_year"),
                                        "declared concept hull year")}


def _auxiliary_models(config, register, diagnostics):
    """One ``concept_auxiliary.<id>`` model per bound, available auxiliary group.

    These models are generated before the design hull proxy for the same reason
    the fixed armour ones are: an auxiliary weapon group's mass reads no hull
    geometry at all, so it must not sit behind a proxy it does not use.
    """
    records = config.get("auxiliary_weapons") or []
    if not records:
        return
    context = _auxiliary_context(config)
    for record in records:
        identity = record.get("id")
        path = "$.concept_design.auxiliary_weapons[%s]" % (identity,)
        try:
            result = auxiliary_kernel.evaluate(record, context, path)
        except (ValueError, ArithmeticError) as error:
            diagnostics.append(_diag("concept_design.auxiliary_unavailable", str(error),
                                     path, blocking=False))
            continue
        for entry in result["diagnostics"]:
            diagnostics.append(_diag(entry.get("code", "concept_design.auxiliary_unavailable"),
                                     entry["message"], entry.get("path", path), blocking=False))
        if identity is None or None in (record.get("system_id"), record.get("item_id")):
            continue
        values = result["values"]
        if values["total_long_tons"] is None:
            continue
        if not math.isfinite(values["total_long_tons"] * kernels.LONG_TON_KG):
            diagnostics.append(_diag(
                "concept_design.auxiliary_unavailable",
                "the derived auxiliary weapon mass exceeds the supported "
                "weight-conversion range", path, blocking=False))
            continue
        provenance = result["provenance"]
        # Persisted mass receipts accept a flat scalar input map, so the whole
        # declaration, context and provenance travel as their own origin text.
        model_inputs = dict(provenance["inputs"], origin=result["origin"])
        register(record["system_id"], _model(
            "%s.%s" % (AUXILIARY_MODEL_PREFIX, identity,), record["item_id"],
            values["total_long_tons"], provenance["kernel"], provenance["source_location"],
            provenance["formula"], model_inputs, config["source"],
            method_version=auxiliary_kernel.METHOD_VERSION,
            boundary=auxiliary_kernel.SOURCE_SCOPE,
            extra={"concept_component": "auxiliary_weapons",
                   "assumptions": provenance["assumptions"],
                   "component_breakdown": auxiliary_kernel.component_breakdown(
                       values, record.get("kind")),
                   "note": _auxiliary_note(record.get("kind"))}))


def _auxiliary_note(kind):
    return (
        "independent recovered mass reading of this one auxiliary weapon group (%s), in "
        "its own sps-3b3-auxiliary-weapons-v1 method and its own long tons: the group's "
        "weapon mass plus its own recovered mount factor, counted once on one target "
        "carrying the existing 'other' balance role. It is not bare guns, not mounts and "
        "not ammunition, it contributes no strength or space term, and it contains no "
        "weapon space, firing arc, reload geometry or explosive performance. A reader who "
        "already carries these weapons inside another item must split that target first; "
        "no split is generated and nothing is deducted from a declared mass automatically"
        % (kind,))


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
                if _mass_of(state, item) is None or float(_mass_of(state, item)) > 0]
    if positive:
        diagnostics.append(_diag(
            "concept_design.guns_role_unbound",
            "guns-role items %r have a positive or unknown selected mass but are not bound to a declared "
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

def _layout_readings(config, diagnostics):
    """One derived reading per declared layout, in declaration order.

    The readings are the server's own returned values: the caller never recomputes
    a freeboard, a height factor or a mass on the client.
    """
    readings = []
    for layout in config.get("battery_layouts") or []:
        path = "$.concept_design.battery_layouts[%s]" % (layout.get("id"),)
        try:
            readings.append(layout_kernel.evaluate(layout, config["batteries"], path))
        except (ValueError, ArithmeticError) as error:
            diagnostics.append(_diag("concept_design.layout_unavailable", str(error), path,
                                     blocking=False))
    return readings


def _fixed_armour_readings(project, config, state, diagnostics):
    """One derived reading per declared fixed region, in declaration order.

    These are the server's own returned values: the caller never recomputes an
    area, a thickness or a mass on the client. They are exposed before every
    early return in :func:`evaluate`, so a project without a physical design
    hull or without a balance section still reports what its declared fixed
    regions actually derive.
    """
    records = config.get("fixed_armour") or []
    if not records:
        return []
    opted = _geometry_opted_ids(config)
    context = _fixed_armour_context(project, config, state, diagnostics)
    readings = []
    for record in records:
        path = "$.concept_design.fixed_armour[%s]" % (record.get("id"),)
        try:
            reading = fixed_armour_kernel.evaluate(record, context, path)
        except (ValueError, ArithmeticError) as error:
            diagnostics.append(_diag("concept_design.fixed_armour_unavailable", str(error),
                                     path, blocking=False))
            continue
        if record.get("id") in opted:
            # The old SPS reading stays its own numbers and its own method, but it
            # is explicitly inactive for adoption: the opted geometry is the one
            # active model for this region, even while it is incomplete.
            reading["active_mass_model"] = "geometry"
            reading["geometry_selected"] = True
            reading["adoption_notice"] = (
                "this region's armour geometry is selected, so this empirical SPS reading "
                "is an inactive numerical comparison; it is never adopted in place of the "
                "selected geometry")
        readings.append(reading)
    return readings


def _geometry_readings(config):
    """One pure panel reading per opted region, in declaration order.

    The reading is exposed independently of the empirical fixed-armour readings and
    before every hull and balance early return. Its values keep the complete mass
    unknown whenever any declared plate is unknown; the known subtotal is never a
    substitute for the complete mass.
    """
    geometry = config.get("armour_geometry")
    if not geometry:
        return []
    source = geometry.get("source")
    by_id = {record.get("id"): record for record in config.get("fixed_armour") or []}
    readings = []
    for region in geometry.get("regions") or []:
        record = by_id.get(region.get("fixed_armour_id"))
        kind = record.get("kind") if isinstance(record, dict) else None
        if kind not in armour_geometry_kernel.ELIGIBLE_KINDS:
            continue
        readings.append(armour_geometry_kernel.evaluate(region, kind, source=source))
    return readings


def _auxiliary_readings(config, diagnostics):
    """One derived reading per declared auxiliary group, in declaration order.

    These are the server's own returned values: the caller never recomputes a
    mass or a mount factor on the client. They are exposed before every early
    return in :func:`evaluate`, so a project without a physical design hull or
    without a balance section still reports what its groups actually derive.
    """
    context = _auxiliary_context(config)
    readings = []
    for record in config.get("auxiliary_weapons") or []:
        path = "$.concept_design.auxiliary_weapons[%s]" % (record.get("id"),)
        try:
            readings.append(auxiliary_kernel.evaluate(record, context, path))
        except (ValueError, ArithmeticError) as error:
            diagnostics.append(_diag("concept_design.auxiliary_unavailable", str(error),
                                     path, blocking=False))
    return readings


def _long_tons_to_t(value_lt):
    """A long-ton mass as metric tonnes, or ``None`` for an unknown one."""
    if value_lt is None:
        return None
    try:
        number = float(value_lt)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number * kernels.LONG_TON_KG / 1000.0


def _armour_components(config, state, diagnostics, fixed_readings, layout_readings):
    """Every declared armour estimate, namespaced by its own family.

    The three families never share a local id, so a fixed region, a layout and a
    single-group battery estimate with the same local name stay three distinct
    components. A component whose owning kernel cannot evaluate it stays in the
    list with ``mass_t = None``: it is never dropped, because dropping it would
    turn an incomplete declaration into an apparently complete one, and the ledger
    value is never copied into its place.
    """
    components = []
    fixed_by_id = {reading.get("id"): reading for reading in fixed_readings
                   if isinstance(reading, dict)}
    geometry_readings = ({reading.get("id"): reading
                          for reading in _geometry_readings(config)}
                         if config.get("armour_geometry") is not None else {})
    for record in config.get("fixed_armour") or []:
        # One chosen component per fixed region: the opted geometry when the region
        # is selected, otherwise the old SPS reading. An unknown geometry mass stays
        # unknown and never falls back to a known SPS mass, and the two are never
        # added together.
        chosen = geometry_readings.get(record.get("id"))
        if chosen is not None:
            mass_t = chosen["values"]["mass_t"]
            method_version = armour_geometry_kernel.METHOD_VERSION
        else:
            reading = fixed_by_id.get(record.get("id"))
            mass_t = None
            if isinstance(reading, dict):
                mass_t = _long_tons_to_t((reading.get("values") or {}).get("total_long_tons"))
            method_version = fixed_armour_kernel.METHOD_VERSION
        components.append({
            "id": "fixed:%s" % (record.get("id"),),
            # The fixed kernel's kind is its own recovered vocabulary; the role the
            # armour-totals kernel reads is the balance role (bulge -> armour_bulge,
            # deck -> armour_deck). They are mapped here rather than passed through.
            "kind": fixed_armour_kernel.ROLE_BY_KIND.get(record.get("kind"), record.get("kind")),
            "target_id": record.get("item_id"),
            "method_version": method_version, "mass_t": mass_t})
    layout_by_id = {reading.get("id"): reading for reading in layout_readings
                    if isinstance(reading, dict)}
    covered = set()
    for layout in config.get("battery_layouts") or []:
        armour = layout.get("armour")
        if not isinstance(armour, dict):
            continue
        reading = layout_by_id.get(layout.get("id"))
        mass_t = None
        if isinstance(reading, dict) and isinstance(reading.get("armour"), dict):
            mass_t = _long_tons_to_t(
                (reading["armour"].get("values") or {}).get("total_long_tons"))
        components.append({
            "id": "layout:%s" % (layout.get("id"),), "kind": LAYOUT_ARMOUR_ROLE,
            "target_id": armour.get("item_id"),
            "method_version": layout_kernel.ARMOUR_METHOD_VERSION, "mass_t": mass_t})
        for name in ("group1", "group2"):
            group = layout.get(name)
            battery_id = group.get("battery_id") if isinstance(group, dict) else None
            if battery_id is not None:
                covered.add(battery_id)
    for battery in config["batteries"]:
        armour = battery.get("armour")
        if armour is None:
            continue
        # A battery already weighted by its layout's complete two-group armour is
        # not weighed a second time through its own old single-group estimate.
        if battery.get("id") in covered:
            continue
        mass_t = None
        path = "$.concept_design.batteries[%s].armour" % (battery.get("id"),)
        try:
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
            diagnostics.append(_diag("concept_design.armour_totals_unavailable", str(error),
                                     path, blocking=False))
        else:
            mass_t = _long_tons_to_t(result["values"].get("total_long_tons"))
        components.append({
            "id": "battery:%s" % (battery.get("id"),), "kind": "gun_mount_armour",
            "target_id": armour.get("item_id"),
            "method_version": armour_kernel.METHOD_VERSION, "mass_t": mass_t})
    return components


def _armour_selected_roles(config, state):
    """The nine canonical armour-role masses in tonnes, plus the classification flag."""
    resolved = _role_masses(config, state)
    if resolved is None:
        return None
    roles = {role: _long_tons_to_t(resolved["totals"].get(role)) for role in ARMOUR_ROLES}
    roles["classification_complete"] = not resolved["unclassified"]
    return roles


def _selected_target_t(state, item_ids):
    """The selected tonne mass of a set of DISTINCT ledger targets, or unknown."""
    if not item_ids:
        return None
    total = 0.0
    for item_id in item_ids:
        value = _mass_of(state, item_id)
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        total += number
    return total


def _battery_selected_values(layout, batteries_by_id, state):
    """The current condition's gun, mount and armour target masses for one layout.

    The targets are collected by leaf item id and never by array position, an
    ammunition target is never counted, and a duplicated id is counted once. The
    declared boundary is tracked for each output category separately, so an open
    boundary is never silently closed into a subtotal:

    * a group the layout does not declare at all (absent, or a null group)
      contributes nothing;
    * a group the layout *does* declare whose membership is unresolved (no chosen
      row, or a row that does not exist) leaves its guns and mounts unknown,
      because the boundary of what it carries cannot be closed;
    * a declared but unbound target -- a row binding with no leaf id, an armour
      block with no leaf id -- leaves its own category unknown rather than
      dropping it and reporting the remaining bound targets as a subtotal.

    The layout's own bound armour covers the whole battery, so an unresolved group
    leaves the armour known when the layout declares that bound target and unknown
    when it does not. A referenced row's existing ledger mass is always counted,
    including a zero-count row: an unfinished membership is never read as a zero.
    """
    guns, mounts, armour_targets = [], [], []
    unbound = set()
    unresolved = False
    for name in ("group1", "group2"):
        if name not in layout:
            continue
        group = layout.get(name)
        if group is None:
            continue
        battery_id = group.get("battery_id") if isinstance(group, dict) else None
        battery = batteries_by_id.get(battery_id)
        if battery is None:
            unresolved = True
            continue
        for bucket, field in ((guns, "guns_item_id"), (mounts, "mounts_item_id")):
            item = battery.get(field)
            if item is None:
                unbound.add(field)
            elif item not in bucket:
                bucket.append(item)
        record = battery.get("armour")
        if isinstance(record, dict):
            item = record.get("item_id")
            if item is None:
                unbound.add("armour_item_id")
            elif item not in armour_targets:
                armour_targets.append(item)
    record = layout.get("armour")
    layout_armour_bound = False
    if isinstance(record, dict):
        item = record.get("item_id")
        if item is None:
            unbound.add("armour_item_id")
        else:
            layout_armour_bound = True
            if item not in armour_targets:
                armour_targets.append(item)
    if unresolved and not layout_armour_bound:
        unbound.add("armour_item_id")
    guns_t = None if unresolved or "guns_item_id" in unbound else _selected_target_t(state, guns)
    mounts_t = (None if unresolved or "mounts_item_id" in unbound
                else _selected_target_t(state, mounts))
    armour_t = (None if "armour_item_id" in unbound
                else _selected_target_t(state, armour_targets))
    total_t = (guns_t + mounts_t + armour_t
               if None not in (guns_t, mounts_t, armour_t) else None)
    return {"guns_t": guns_t, "mounts_t": mounts_t, "armour_t": armour_t, "total_t": total_t}


def _battery_totals_readings(config, layout_readings, state, diagnostics):
    """One whole-battery source estimate per declared layout, with its selected mirror."""
    readings = []
    layout_by_id = {reading.get("id"): reading for reading in layout_readings
                    if isinstance(reading, dict)}
    batteries_by_id = {battery["id"]: battery for battery in config["batteries"]
                       if battery.get("id")}
    for layout in config.get("battery_layouts") or []:
        layout_reading = layout_by_id.get(layout.get("id"))
        if not isinstance(layout_reading, dict):
            continue
        path = "$.concept_design.battery_layouts[%s]" % (layout.get("id"),)
        try:
            reading = battery_totals_kernel.evaluate(layout, config["batteries"],
                                                     layout_reading, path)
        except (ValueError, ArithmeticError) as error:
            diagnostics.append(_diag("concept_design.battery_totals_unavailable", str(error),
                                     path, blocking=False))
            continue
        reading["selected_values"] = _battery_selected_values(layout, batteries_by_id, state)
        if reading["status"] == "unavailable" and _has_known_selected(reading["selected_values"]):
            # The source estimate could not be closed, but the selected ledger
            # actuals are independent of it. The record is partial rather than
            # refused, so the known selected figures can still be compared; the
            # source values stay null and the ledger is never written into them.
            reading["status"] = "partial"
        readings.append(reading)
    return readings


def _has_known_selected(selected_values):
    """Whether any of a layout's four selected actual figures is known."""
    return any(selected_values.get(key) is not None
               for key in ("guns_t", "mounts_t", "armour_t", "total_t"))


def _armour_totals_reading(config, state, diagnostics, fixed_readings, layout_readings):
    """The declared-estimate and selected-actual armour totals for one project."""
    summary = config.get("mass_summary") or {}
    components = _armour_components(config, state, diagnostics, fixed_readings, layout_readings)
    selected_roles = _armour_selected_roles(config, state)
    path = "$.concept_design.mass_summary"
    try:
        return armour_totals_kernel.evaluate(
            components, selected_roles, declared_complete=summary.get("armour_scope_complete"),
            source=summary.get("source"), path=path)
    except armour_totals_kernel.ArmourTotalsError as error:
        diagnostics.extend(_diag(entry.get("code", "concept_design.armour_totals_invalid"),
                                 entry["message"], entry.get("path", path), blocking=False)
                           for entry in error.diagnostics)
        return None


def _cost_reading(config, state, diagnostics):
    """The optional empirical cost reading, built from SELECTED masses only.

    Nothing is adopted, nothing is proposed and no target is created: the reading
    is a display value in the source's own historical currency labels. A proposed
    or estimated mass, and another condition's mass, can never become the current
    cost, so every input here is resolved from the selected ledger and the
    declared balance roles.
    """
    declared = config.get("cost") or {}
    path = "$.concept_design.cost"
    blocked = []
    resolved = _role_masses(config, state)
    if resolved is None:
        blocked.append(_diag(
            "concept_design.cost_unavailable",
            "the cost reading classifies the selected ledger through the declared balance "
            "roles, and no balance section is declared; the reading is unavailable rather "
            "than zero", path, blocking=False))
        inputs = {name: None for name in cost_kernel.INPUT_FIELDS}
    else:
        unclassified = resolved["unclassified"]
        notes = []
        borne, _resolved = _selected_borne(config, state, notes)
        if unclassified:
            blocked.append(_diag(
                "concept_design.cost_unavailable",
                "classify every positive or unknown selected mass before reading a cost: %r is "
                "unclassified and is never read as a zero cost" % (unclassified,), path,
                blocking=False))
        if borne is None:
            blocked.append(_diag(
                "concept_design.cost_borne_unavailable",
                "the recovered cost reads the selected bare-gun borne weight; it is "
                "unavailable here: %s" % ("; ".join(
                    entry["message"] for entry in notes) or
                    "no balance roles are declared"), path, blocking=False))
        inputs = {
            "displacement_t": config.get("target_displacement_t"),
            "hull_year": config.get("hull_year"),
            "machinery_mass_t": _selected_role_mass_t(resolved, "machinery"),
            "ammunition_mass_t": _selected_role_mass_t(resolved, "ammunition"),
            "fuel_mass_t": _selected_role_mass_t(resolved, "fuel"),
            "borne_mass_t": None if borne is None else borne * kernels.LONG_TON_KG / 1000.0,
        }
    facts = {
        "displacement_t": _declared_fact(inputs["displacement_t"],
                                         "declared concept target displacement"),
        "hull_year": _declared_fact(inputs["hull_year"], "declared concept hull year"),
        "machinery_mass_t": _declared_fact(
            inputs["machinery_mass_t"],
            "selected ledger items mapped to the declared 'machinery' balance role"),
        "ammunition_mass_t": _declared_fact(
            inputs["ammunition_mass_t"],
            "selected ledger items mapped to the declared 'ammunition' balance role"),
        "fuel_mass_t": _declared_fact(
            inputs["fuel_mass_t"],
            "selected ledger items mapped to the declared 'fuel' balance role"),
        "borne_mass_t": _declared_fact(
            inputs["borne_mass_t"],
            "selected bare-gun borne weight of the declared batteries, converted from the "
            "recovered long tons to metric tonnes"),
    }
    result = cost_kernel.evaluate(facts, path)
    result["source"] = declared.get("source")
    result["note"] = ("an empirical historical reading in the source's own million-dollar and "
                      "million-pound labels; it is not a modern price, a live exchange rate, "
                      "an inflation-adjusted value or a budget, and it adopts nothing")
    if blocked:
        # An unclassified selected mass or an unbound guns-role item leaves the
        # whole reading unavailable. The inputs it did read stay visible, so the
        # reason is auditable, but no figure is offered.
        result = dict(result, status="unavailable",
                      values=dict.fromkeys(result["values"]))
    for entry in result["diagnostics"] + blocked:
        diagnostics.append(_diag(entry["code"], entry["message"], entry["path"],
                                 blocking=False))
    return result


def _armour_review_reading(project, config, result):
    hull = project.get('hull') or {}
    return armour_review_kernel.evaluate(config.get('fixed_armour') or [], {
        'length_m': hull.get('lwl_m'), 'draught_m': hull.get('draught_normal_m'),
        'freeboard_m': config.get('freeboard_m'),
        'room_hull_ratio': result.get('space', {}).get('hull_ratio'),
        'composite_strength': result.get('strength', {}).get('composite'),
    }, config['armour_review'])


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
    # The layout readings are exposed before every early return below, so a
    # project without a physical design hull or without a balance section still
    # reports what its declared layout identity actually derives. A project that
    # declares no layout keeps the previous result structure unchanged.
    if config.get("battery_layouts"):
        result["battery_layouts"] = _layout_readings(config, diagnostics)
    layout_readings = result.get("battery_layouts") or []
    # The optional component families this result declares, and the method version
    # each one owns. A saved report or a saved comparison gates on these instead of
    # on a global request identity, so a stale or mismatched component method can
    # never be compared as a delta. Nothing here is declared when neither new
    # section is: a project without fixed armour or cost keeps the previous result
    # shape exactly, and the coordinator's own versions stay untouched.
    methods = {}
    if config.get("fixed_armour"):
        methods["fixed_armour"] = fixed_armour_kernel.METHOD_VERSION
    if config.get("armour_geometry") is not None:
        methods["armour_geometry"] = armour_geometry_kernel.METHOD_VERSION
    if config.get("battery_layouts"):
        methods["layout"] = layout_kernel.METHOD_VERSION
    if config.get("cost") is not None:
        methods["cost"] = cost_kernel.METHOD_VERSION
    if config.get("auxiliary_weapons"):
        methods["auxiliary_weapons"] = auxiliary_kernel.METHOD_VERSION
    if config.get('armour_review') is not None:
        methods['armour_review'] = armour_review_kernel.METHOD_VERSION
    # The mass-summary families are appended last, so a project that never enabled
    # the section keeps exactly the methods map it already had. The whole-battery
    # family is only named when there is a layout to produce its one row per layout.
    if config.get("mass_summary") is not None:
        if config.get("battery_layouts"):
            methods["battery_totals"] = battery_totals_kernel.METHOD_VERSION
        methods["armour_totals"] = armour_totals_kernel.METHOD_VERSION
    # The whole-battery mount allocation is a family of its own, named whenever
    # the section is declared -- even with no selected layout, so a saved report
    # and a saved comparison can gate on its independent method version.
    if config.get("battery_mass_allocation") is not None:
        methods["battery_mass_allocation"] = allocation_kernel.METHOD_VERSION
    if config.get("armour_defaults") is not None:
        methods["armour_defaults"] = armour_defaults_kernel.METHOD_VERSION
    if config.get("auxiliary_space") is not None:
        methods["auxiliary_space"] = auxiliary_space_kernel.METHOD_VERSION
    if methods:
        result["methods"] = methods
    # The fixed-armour and cost readings are exposed on the same footing, before
    # every early return below, for the same reason. A project that declares no
    # fixed region and no cost section keeps the previous result structure
    # exactly: neither key is added at all.
    if config.get("fixed_armour"):
        result["fixed_armour"] = _fixed_armour_readings(project, config, state, diagnostics)
    # The armour-panel geometry readings are exposed independently, on the same
    # footing and before every early return below: an opted region reports its own
    # complete or known-subtotal mass even when its old SPS reading is inactive or
    # its geometry is unfinished.
    if config.get("armour_geometry") is not None:
        result["armour_geometry"] = _geometry_readings(config)
    if config.get("auxiliary_weapons"):
        result["auxiliary_weapons"] = _auxiliary_readings(config, diagnostics)
    if config.get("cost") is not None:
        result["cost"] = _cost_reading(config, state, diagnostics)
    if config.get('armour_review') is not None:
        result['armour_review'] = _armour_review_reading(project, config, result)
    # The mass-summary readings are exposed here too, before every early return
    # below: a project whose design hull is not physical yet still gets the
    # whole-battery source estimate and the declared-versus-selected armour totals
    # it declared. Neither key is added while the section is absent.
    if config.get("mass_summary") is not None:
        if config.get("battery_layouts"):
            result["battery_totals"] = _battery_totals_readings(
                config, layout_readings, state, diagnostics)
        result["armour_totals"] = _armour_totals_reading(
            config, state, diagnostics, result.get("fixed_armour") or [], layout_readings)
    # The whole-battery mount allocation reading is exposed on the same footing
    # and before every early return below: it reads no hull fact, so a project
    # whose hull is not physical yet still gets its proportional split and its
    # independent selected mirror. Nothing is added while the section is absent.
    if config.get("battery_mass_allocation") is not None:
        result["battery_mass_allocation"] = _allocation_readings(
            config, layout_readings, state, diagnostics)
    if config.get("armour_defaults") is not None:
        result["armour_defaults"] = armour_defaults_kernel.evaluate(config["armour_defaults"], {
            "length_m": _declared_fact(_hull_number(project, "lwl_m"), "canonical $.hull.lwl_m"),
            "beam_m": _declared_fact(_hull_number(project, "beam_m"), "canonical $.hull.beam_m"),
            "draught_m": _declared_fact(_hull_number(project, "draught_normal_m"), "canonical $.hull.draught_normal_m"),
            "block_coeff": _declared_fact(_hull_number(project, "block_coeff"), "canonical $.hull.block_coeff"),
            "freeboard_m": _declared_fact(config.get("freeboard_m"), "declared concept freeboard", True),
        })
    if config.get("auxiliary_space") is not None:
        result["auxiliary_space"] = auxiliary_space_kernel.evaluate(
            config.get("auxiliary_weapons") or [], _auxiliary_space_context(project, config, diagnostics),
            config["auxiliary_space"])
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
    if config.get('armour_review') is not None:
        result['armour_review'] = _armour_review_reading(project, config, result)
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
