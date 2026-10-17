# -*- coding: utf-8 -*-
"""Pure native ship-design mass ledger bridge.

This unit turns the accepted source-compatibility calculation into method-bearing
metric-tonne mass suggestions, one per explicit design role, and reconciles them
with the project's existing ledger. It is deliberately free of coordinates: it
never invents a centre of gravity.

Two rules from the design spec drive everything here:

* **One item owns one role.** An estimated role has exactly one managed target;
  a declared role may accumulate several manual items. A ledger item ID may never
  appear under two roles.
* **Manual is manual.** Existing hand-entered masses stay ``declared`` and are
  never overwritten. Managed replacement mass for the design condition is recorded
  on the item as ``design_mass`` (a condition-scoped overlay), so the base mass,
  source, positions, original overrides and derived definitions are untouched, and
  no other loading condition can be impersonated.

The role set and the recovered split are frozen by the spec: ``structure`` is the
source residual ``engine.hullWeightDisplayed`` (H0), **not** the strength-side H1
``engine.hullWeight``; ``stores`` is ``loadWeight - bunker - magazine`` and the
whole ``loadWeight`` is never counted twice; the seven fixed armour regions are
summed once and ``guns.armWeight`` is a separate ``gun_armour`` role, never added
into the fixed total again.

No project file is read or written here; callers own persistence.
"""
from __future__ import annotations

import copy

try:  # As part of the plimsoll package.
    from . import sps_compat
except ImportError:  # Direct top-level import (tests/scripts).
    import sps_compat


METHOD_VERSION = "ship-design-mass-v1"
LEDGER_SCHEMA = "plimsoll-ship-design-ledger-1"

#: One long ton in metric tonnes (source-internal LT -> reportable t).
LONG_TON_T = 1.0160469088

OWNER = "ship_design"
AUTO_GROUP_ID = "ship-design-estimates"
AUTO_GROUP_LABEL = "Ship design estimates"
MANAGED_ITEM_PREFIX = "sd-"
DESIGN_MASS_SOURCE = "ship-design-native-v1:source-method-leading-mass"

#: The explicit native role set: sixteen named roles, the five miscellaneous ones,
#: and a native ``other`` role. ``other`` carries no source estimate: it exists so
#: arbitrary existing payload can be classified explicitly, and it never absorbs a
#: legacy concept ``other`` aggregate (that stays ``needs_binding``).
ROLES = (
    "structure", "guns", "mounts", "gun_armour", "ammunition", "machinery", "fuel",
    "stores", "auxiliary", "belt_main", "belt_ends", "belt_upper", "bulkhead",
    "bulge", "deck", "conning",
    "misc_vital", "misc_hull", "misc_deck", "misc_above", "misc_void",
    "other",
)
#: Roles with a source-method estimate. ``other`` is deliberately excluded: it has
#: no source reading and only exists as an explicit payload classification.
SOURCE_ROLES = tuple(role for role in ROLES if role != "other")

#: Existing concept-design balance roles that map unambiguously onto a native
#: role. Any role absent here (or an item without a declared role) is left
#: unclassified and forces ``needs_binding`` rather than being guessed. Mixed or
#: overlapping aggregate ownership is never renamed into detail rows here. A legacy
#: ``other`` aggregate is deliberately absent: it may hold arbitrary payload and
#: must be classified explicitly, never inferred as auxiliary.
CONCEPT_ROLE_MAP = {
    "structure": "structure",
    "guns": "guns",
    "mounts": "mounts",
    "ammunition": "ammunition",
    "machinery": "machinery",
    "fuel": "fuel",
    "belt_main": "belt_main",
    "belt_ends": "belt_ends",
    "belt_upper": "belt_upper",
    "bulkhead": "bulkhead",
    "conning": "conning",
    "armour_bulge": "bulge",
    "armour_deck": "deck",
    "rotating_armour": "gun_armour",
    "gun_mount_armour": "gun_armour",
    "misc_vital": "misc_vital",
    "misc_hull": "misc_hull",
    "misc_deck": "misc_deck",
    "misc_above": "misc_above",
    "misc_void": "misc_void",
}

_MISSING = object()


# --------------------------------------------------------------- diagnostics

def _diag(code, message, path="$.ship_design", severity="error"):
    return {"code": code, "severity": severity, "path": path, "message": message,
            "blocking": severity == "error"}


# ------------------------------------------------------------ source reading

def _source_result(result):
    """Accept either a native ship-design result or a raw source result."""
    if not isinstance(result, dict):
        return {}
    if isinstance(result.get("source_result"), dict):
        return result["source_result"]
    if "engine" in result and "guns" in result:
        return result
    return result


def _num(section, *names):
    if not isinstance(section, dict):
        return None
    for name in names:
        if name in section:
            value = section[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            return float(value)
    return None


def _lt_to_t(value):
    return None if value is None else value * LONG_TON_T


# --------------------------------------------------------------- estimate

def estimate_detail(source_result):
    """Return ``{masses, diagnostics, displacement_t}`` for one source result.

    ``masses`` maps every native role to its metric-tonne suggestion or ``None``
    when the source is unknown. A negative residual is reported as unknown with a
    diagnostic; a fabricated nonnegative mass is never substituted. This is a
    suggestion only: nothing here reads or writes a project.
    """
    result = _source_result(source_result)
    hull = result.get("hull") if isinstance(result, dict) else None
    guns = result.get("guns") if isinstance(result, dict) else None
    auxiliary = result.get("auxiliary") if isinstance(result, dict) else None
    armour = result.get("armour") if isinstance(result, dict) else None
    engine = result.get("engine") if isinstance(result, dict) else None

    diagnostics = []

    def reading(role, value, *, residual=False):
        value_t = _lt_to_t(value)
        if value is None:
            diagnostics.append(_diag(
                "ship_design.mass_unknown",
                "the %s estimate is unavailable because the source reading is unknown; "
                "no zero is substituted" % role,
                "$.ship_design.mass.%s" % role, "warning"))
            return None
        if value < 0:
            diagnostics.append(_diag(
                "ship_design.mass_negative",
                "the source %s residual is negative (%r); it is kept unknown rather than "
                "written as a negative canonical mass" % (role, value),
                "$.ship_design.mass.%s" % role, "warning"))
            return None
        return value_t

    load_weight = _num(engine, "loadWeight", "load_weight")
    bunker = _num(engine, "bunker")
    magazine = _num(guns, "magazine")
    if None not in (load_weight, bunker, magazine):
        stores_lt = load_weight - bunker - magazine
    else:
        stores_lt = None

    masses = {
        # H0 residual, explicitly not the H1 strength-side hull weight.
        "structure": reading("structure", _num(engine, "hullWeightDisplayed", "hull_weight_displayed"),
                              residual=True),
        "guns": reading("guns", _num(guns, "gunWeight", "gun_weight")),
        "mounts": reading("mounts", _num(guns, "mountWeight", "mount_weight")),
        "gun_armour": reading("gun_armour", _num(guns, "armWeight", "arm_weight")),
        "ammunition": reading("ammunition", magazine),
        "machinery": reading("machinery", _num(engine, "engineWeight", "engine_weight")),
        "fuel": reading("fuel", bunker),
        "stores": reading("stores", stores_lt),
        "auxiliary": reading("auxiliary", _num(auxiliary, "weight")),
        "belt_main": reading("belt_main", _num(armour, "weightBeltMain", "beltMainWeight")),
        "belt_ends": reading("belt_ends", _num(armour, "weightBeltEnds", "beltEndsWeight")),
        "belt_upper": reading("belt_upper", _num(armour, "weightBeltUpper", "beltUpperWeight")),
        "bulkhead": reading("bulkhead", _num(armour, "weightBulkhead", "bulkheadWeight")),
        "bulge": reading("bulge", _num(armour, "weightBulge", "bulgeWeight")),
        "deck": reading("deck", _num(armour, "weightDeck", "deckWeight")),
        "conning": reading("conning", _num(armour, "weightConning", "conningWeight")),
        "misc_vital": reading("misc_vital", _num(auxiliary, "miscWeightVital", "misc_weight_vital")),
        "misc_hull": reading("misc_hull", _num(auxiliary, "miscWeightHull", "misc_weight_hull")),
        "misc_deck": reading("misc_deck", _num(auxiliary, "miscWeightDeck", "misc_weight_deck")),
        "misc_above": reading("misc_above", _num(auxiliary, "miscWeightAbove", "misc_weight_above")),
        "misc_void": reading("misc_void", _num(auxiliary, "voidWeight", "misc_weight_void")),
        # The explicit payload role has no source reading; its estimate is an
        # explicit zero, and an additional payload is added only by a declared
        # binding, never inferred from a legacy combined aggregate.
        "other": 0.0,
    }
    displacement_lt = _num(hull, "displacement")
    return {
        "masses": masses,
        "displacement_t": _lt_to_t(displacement_lt),
        "displacement_lt": displacement_lt,
        "diagnostics": diagnostics,
        "method_version": METHOD_VERSION,
    }


def estimate(source_result):
    """Role -> metric-tonne suggestion (``None`` where the source is unknown)."""
    return estimate_detail(source_result)["masses"]


# ------------------------------------------------------------- ledger access

def _group_items(project):
    groups = project.get("weight_groups")
    if not isinstance(groups, list):
        return []
    rows = []
    for group_index, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        items = group.get("items")
        if not isinstance(items, list):
            continue
        for item_index, item in enumerate(items):
            if isinstance(item, dict):
                rows.append((group_index, item_index, item))
    return rows


def _auto_group(project, create):
    groups = project.get("weight_groups")
    if not isinstance(groups, list):
        if not create:
            return None
        groups = []
        project["weight_groups"] = groups
    for group in groups:
        if isinstance(group, dict) and group.get("id") == AUTO_GROUP_ID:
            return group
    if not create:
        return None
    group = {"id": AUTO_GROUP_ID, "label": AUTO_GROUP_LABEL, "required": False,
             "owner": OWNER, "items": []}
    groups.append(group)
    return group


def _find_item(project, item_id):
    for _gi, _ii, item in _group_items(project):
        if item.get("id") == item_id:
            return item
    return None


def _managed(item):
    design_mass = item.get("design_mass")
    source = item.get("source")
    return (isinstance(design_mass, dict) and design_mass.get("owner") == OWNER) \
        or (isinstance(source, dict) and source.get("owner") == OWNER)


def _new_managed_item(role):
    return {
        "id": MANAGED_ITEM_PREFIX + role,
        "mass_t": 0.0,          # explicit: not carried by any other condition
        "x_m": None,
        "y_m": None,
        "kg_m": None,
        "source": {"owner": OWNER, "role": role, "origin": "managed_estimate"},
        "estimate": True,
    }


def _design_mass(condition_id, mass_t):
    return {"owner": OWNER, "condition_id": condition_id, "mass_t": mass_t,
            "source": DESIGN_MASS_SOURCE}


def _owner_condition(project, condition_id):
    conditions = project.get("loading_conditions")
    if not isinstance(conditions, list):
        return None
    for condition in conditions:
        if isinstance(condition, dict) and condition.get("id") == condition_id:
            return condition
    return None


def _owner_override(condition, item_id):
    if not isinstance(condition, dict):
        return _MISSING
    overrides = condition.get("overrides")
    if isinstance(overrides, dict):
        entry = overrides.get(item_id)
        if isinstance(entry, dict) and "mass_t" in entry:
            return entry["mass_t"]
    return _MISSING


def _effective_mass(item, mode, condition):
    """Effective selected mass for one item in the design condition.

    The scoped ``design_mass`` overlay is applied before any ordinary owner
    override, exactly as the loading resolver applies it after inheritance and
    overrides. A declared item uses its own override/base mass.
    """
    if mode == "estimated":
        design_mass = item.get("design_mass")
        if isinstance(design_mass, dict):
            return design_mass.get("mass_t")
    override = _owner_override(condition, item.get("id"))
    if override is not _MISSING:
        return override
    return item.get("mass_t")


# ------------------------------------------------------------ binding logic

def _concept_roles(project):
    concept = project.get("concept_design")
    if isinstance(concept, dict):
        balance = concept.get("balance")
        if isinstance(balance, dict) and isinstance(balance.get("roles"), dict):
            return balance["roles"]
    return {}


def infer_bindings(project):
    """Bind existing items from an explicit concept balance role map only.

    Returns ``(bindings, unclassified)``. An item whose concept role is unknown, an
    aggregate whose ``includes`` component tokens do not all belong to that same
    single role (recognized role aliases naming another role, or unknown tokens), or
    whose ownership token is shared with another item, is left unclassified:
    renaming an aggregate into detail rows is never assumed, and claiming a mixed
    whole as one detail role would double-count the parts it already contains.
    """
    roles = _concept_roles(project)
    rows = _group_items(project)
    owners = {}
    for _gi, _ii, item in rows:
        tokens = {item.get("id")}
        includes = item.get("includes")
        if isinstance(includes, list):
            tokens.update(token for token in includes if isinstance(token, str))
        for token in tokens:
            owners.setdefault(token, set()).add(item.get("id"))
    bindings = {}
    unclassified = []
    for _gi, _ii, item in rows:
        item_id = item.get("id")
        if not isinstance(item_id, str):
            continue
        if _managed(item):
            continue
        role = CONCEPT_ROLE_MAP.get(roles.get(item_id))
        includes = item.get("includes")
        overlap = isinstance(includes, list) and any(
            len(owners.get(token, ())) > 1 for token in includes if isinstance(token, str))
        # An aggregate may only be claimed as one detail role when every component
        # token it names is itself a recognized role equal to that same role. A
        # recognized alias for a different role, or an unrecognized token, means the
        # true ownership is mixed or unknown and must stay pending.
        mixed = False
        if isinstance(includes, list):
            for token in includes:
                if not isinstance(token, str):
                    continue
                if _token_role(token) != role:
                    mixed = True
                    break
        if role is None or mixed or overlap:
            unclassified.append(item_id)
            continue
        entry = bindings.setdefault(role, {"item_ids": [], "mode": "declared"})
        entry["item_ids"].append(item_id)
    for entry in bindings.values():
        entry["item_ids"] = sorted(set(entry["item_ids"]))
    return bindings, unclassified


def _token_role(token):
    """Map a component token to its native role, or ``None`` when unrecognized."""
    if token in CONCEPT_ROLE_MAP:
        return CONCEPT_ROLE_MAP[token]
    if token in ROLES:
        return token
    return None


def _coerce_bindings(raw, diagnostics):
    """Validate a caller-supplied binding map; never mutate it.

    Returns ``(bindings, ok)``. ``ok`` is ``False`` when any entry was rejected,
    which makes the caller refuse automatic managed additions rather than proceed
    on a half-trusted map.
    """
    if raw is None:
        return {}, True
    if not isinstance(raw, dict):
        diagnostics.append(_diag("ship_design.bindings_invalid",
                                 "mass_bindings must be an object of role -> binding",
                                 "$.ship_design.mass_bindings"))
        return {}, False
    out = {}
    owned = {}
    ok = True
    for role in sorted(raw):
        entry = raw[role]
        path = "$.ship_design.mass_bindings[%r]" % (role,)
        if role not in ROLES:
            diagnostics.append(_diag("ship_design.binding_role_unknown",
                                     "unknown mass role %r" % (role,), path))
            ok = False
            continue
        if not isinstance(entry, dict):
            diagnostics.append(_diag("ship_design.binding_invalid",
                                     "a binding must be an object with item_ids and mode", path))
            ok = False
            continue
        mode = entry.get("mode")
        if mode not in ("estimated", "declared"):
            diagnostics.append(_diag("ship_design.binding_mode_invalid",
                                     "mode must be 'estimated' or 'declared'", path))
            ok = False
            continue
        ids = entry.get("item_ids")
        if (not isinstance(ids, list) or not ids
                or not all(isinstance(item_id, str) and item_id.strip() for item_id in ids)
                or len(set(ids)) != len(ids)):
            diagnostics.append(_diag("ship_design.binding_ids_invalid",
                                     "item_ids must be a non-empty list of unique IDs", path))
            ok = False
            continue
        if mode == "estimated" and len(ids) != 1:
            diagnostics.append(_diag("ship_design.binding_estimated_multiple",
                                     "an estimated role permits exactly one managed target",
                                     path))
            ok = False
            continue
        for item_id in ids:
            if item_id in owned:
                diagnostics.append(_diag(
                    "ship_design.binding_duplicate_item",
                    "item %r is already owned by role %r; one item may belong to only one role"
                    % (item_id, owned[item_id]), path))
                ok = False
            owned[item_id] = role
        out[role] = {"item_ids": list(ids), "mode": mode}
    return out, ok


# --------------------------------------------------------------- reconcile

def reconcile(project, result, condition_id, bindings):
    """Reconcile the source estimates with the project ledger.

    Returns ``{project, bindings, summary, diagnostics}``. The returned project
    carries managed ``design_mass`` overlays; the base mass, source, positions,
    overrides and definitions it did not own are preserved exactly.
    """
    project = copy.deepcopy(project)
    diagnostics = []
    source = _source_result(result)
    detail = estimate_detail(source)
    masses = detail["masses"]
    diagnostics.extend(detail["diagnostics"])
    native = project.get("ship_design") if isinstance(project.get("ship_design"), dict) else {}

    provided = bindings if bindings is not None else native.get("mass_bindings")
    binding_map, bindings_ok = _coerce_bindings(provided, diagnostics)
    inferred, unclassified = infer_bindings(project)

    # Merge inferred declared bindings only where the caller left the role open.
    for role, entry in inferred.items():
        if role not in binding_map:
            binding_map[role] = entry
    # Any item that carries a concept role but is already managed stays as-is.

    # Recompute the set of still-unbound manual items after the merge.
    condition = _owner_condition(project, condition_id)
    bound_ids = {item_id for entry in binding_map.values() for item_id in entry["item_ids"]}
    remaining = []
    for _gi, _ii, item in _group_items(project):
        item_id = item.get("id")
        if not isinstance(item_id, str) or item_id in bound_ids:
            continue
        if not _managed(item):
            remaining.append(item_id)
            continue
        # A formerly-managed row is only genuinely inactive while its effective basis
        # mass is an excluded zero. Once it carries a selected-condition override, or
        # an unknown mass, the loading resolver still counts it (an unbound item's
        # ``design_mass`` is ignored), so it must be classified explicitly rather than
        # skipped as an empty automatic row: otherwise the native balance would claim
        # a total the loaded project contradicts.
        value = _effective_mass(item, "declared", condition)
        if value is None or value != 0:
            remaining.append(item_id)
    # An item the caller explicitly bound is classified by definition, even when it
    # carries no explicit concept role (for example arbitrary payload bound to the
    # native ``other`` role). Excluding bound IDs lets the remaining bindings be
    # completed without the bound items forcing ``needs_binding`` forever.
    unclassified = sorted((set(unclassified) - bound_ids) | set(remaining))
    if unclassified:
        diagnostics.append(_diag(
            "ship_design.needs_binding",
            "existing ledger items have no explicit role yet; managed estimates are not "
            "added until they are classified: %s" % (unclassified,),
            "$.weight_groups", "warning"))

    # Only once every old manual row is classified may the missing supported roles
    # be created automatically. A rejected binding map also blocks new additions.
    # ``other`` is never auto-created: it has no source estimate and exists only
    # for an explicit additional-payload binding.
    if not unclassified and bindings_ok:
        for role in SOURCE_ROLES:
            if role in binding_map:
                continue
            binding_map[role] = {"item_ids": [MANAGED_ITEM_PREFIX + role], "mode": "estimated"}

    # Apply the bindings: ensure estimated targets exist, refresh their overlay,
    # and never touch a declared base mass.
    for role, entry in binding_map.items():
        if entry["mode"] == "estimated":
            item_id = entry["item_ids"][0]
            item = _find_item(project, item_id)
            if item is None:
                item = _new_managed_item(role)
                _auto_group(project, create=True).setdefault("items", []).append(item)
            # A managed target carries a mass suggestion only; its coordinates
            # stay exactly as they were (null for a freshly created row).
            item["design_mass"] = _design_mass(condition_id, masses.get(role))
        else:
            for item_id in entry["item_ids"]:
                item = _find_item(project, item_id)
                if isinstance(item, dict):
                    # Switching a row to declared removes the managed overlay so a
                    # manual override is authoritative.
                    item.pop("design_mass", None)

    # A managed overlay is only meaningful on the current estimated target. Any
    # stale overlay this unit owns (for example the auto row of a role that was
    # switched to declared) is cleared so the ledger never carries an unbound,
    # hand-editable overlay that validate would have to reject.
    estimated_targets = {entry["item_ids"][0] for entry in binding_map.values()
                         if entry["mode"] == "estimated"}
    for _gi, _ii, item in _group_items(project):
        design_mass = item.get("design_mass")
        if isinstance(design_mass, dict) and design_mass.get("owner") == OWNER \
                and item.get("id") not in estimated_targets:
            item.pop("design_mass", None)

    roles_summary = {}
    selected_total = 0.0
    selected_complete = not unclassified
    for role in ROLES:
        entry = binding_map.get(role)
        if entry is None:
            # A missing optional role carries no mass once ownership is known.
            # While manual rows await classification, no role is falsely shown
            # as zero and the total stays pending.
            roles_summary[role] = {"mode": None, "item_ids": [],
                                   "estimate_t": masses.get(role),
                                   "selected_mass_t": None if unclassified else 0.0}
            continue
        role_ids = list(entry["item_ids"])
        mode = entry["mode"]
        selected = 0.0
        role_complete = True
        for item_id in role_ids:
            item = _find_item(project, item_id)
            value = _effective_mass(item, mode, condition) if isinstance(item, dict) else None
            if value is None:
                role_complete = False
                continue
            selected += float(value)
        if role_complete:
            selected_total += selected
        else:
            selected_complete = False
        roles_summary[role] = {
            "mode": mode,
            "item_ids": role_ids,
            "estimate_t": masses.get(role),
            "selected_mass_t": selected if role_complete else None,
        }

    estimated_total = 0.0
    estimated_complete = True
    for role in ROLES:
        value = masses.get(role)
        if value is None:
            estimated_complete = False
        else:
            estimated_total += value

    target = detail["displacement_t"]
    summary = {
        "schema": LEDGER_SCHEMA,
        "owner": OWNER,
        "condition_id": condition_id,
        "basis_condition_id": condition_id,
        "group_id": AUTO_GROUP_ID,
        "roles": roles_summary,
        "selected_mass_t": selected_total if selected_complete else None,
        "estimated_mass_t": estimated_total if estimated_complete else None,
        "target_displacement_t": target,
        "difference_t": (selected_total - target)
            if selected_complete and target is not None else None,
        "needs_binding": unclassified,
        "complete": not unclassified and selected_complete and estimated_complete,
    }

    if isinstance(project.get("ship_design"), dict):
        project["ship_design"]["mass_bindings"] = copy.deepcopy(binding_map)
    return {"project": project, "bindings": binding_map, "summary": summary,
            "diagnostics": diagnostics}


__all__ = ["estimate", "estimate_detail", "reconcile", "infer_bindings",
           "ROLES", "SOURCE_ROLES", "CONCEPT_ROLE_MAP", "LONG_TON_T", "AUTO_GROUP_ID",
           "MANAGED_ITEM_PREFIX", "OWNER", "METHOD_VERSION", "LEDGER_SCHEMA"]
