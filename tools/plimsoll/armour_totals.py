"""Declared-versus-selected armour totals, as an independent kernel.

This is a pure function over a finite declared domain. It never touches a
project, a ledger or a file, it never clamps an out-of-domain value and it never
reads an unknown input as zero: a component with no derived mass keeps
``mass_t = None``, a wrong type is refused structurally, and a duplicate or a
contradictory declaration is refused rather than reconciled.

It carries its own ``sps-3b3-armour-totals-v1`` identity, separate from every
component kernel it reads and from the adapted configuration method.

What it does
------------
``concept_design`` adapts the declared armour **estimates** into a flat list of
components (each with its own ``fixed:``/``layout:``/``battery:`` namespaced
identity, its role ``kind``, its owned ``target_id``, the component method that
produced it and its ``mass_t``) beside the selected ledger's canonical role
masses. This kernel turns those two views into two clearly separated readings:

* the **declared estimate** — ``estimated_belts_t`` (main/upper/ends) and
  ``estimated_total_t`` — which is complete only when the declaration is
  confirmed complete and no component is unknown, and otherwise is ``None``;
* the **selected ledger actual** — ``selected_belts_t`` (main/upper/ends) and
  ``selected_total_t`` (all nine roles) — which is unknown whenever a required
  role is unknown or the ledger is not fully classified;
* ``known_estimate_subtotal_t`` — the sum of the declared components whose mass
  is known, a partial figure that never masquerades as a complete one.

The estimate and the actual are named apart and are never substituted for one
another. A component whose estimate exists but is outside a proposal comparison
tolerance, is not yet bound to a ledger item, or has already been adopted is
still part of the declared estimate: a proposal list is never used to infer the
complete total.

A mass that has no recovered source estimate is never made up from the ledger.
``rotating_armour`` is exactly such a role in this round: it appears in the
selected actual (it is one of the nine balance roles) but never in the declared
estimate, because no component kernel derives it and the ledger value is never
copied across.

Scope
-----
This is an accounting boundary over already-derived component estimates and
already-selected ledger masses. It derives no physical mass of its own, it is not
an armour geometry or a structural strength calculation, and it makes no claim
about any real ship.
"""

from __future__ import annotations

import copy
import math

try:
    from . import concept_estimates as kernels
except ImportError:                                   # pragma: no cover - direct import
    import concept_estimates as kernels

METHOD_VERSION = "sps-3b3-armour-totals-v1"
SOURCE_SCOPE = (
    "Accounting sum over already-derived armour component estimates and the "
    "selected ledger's canonical armour role masses; it reproduces no recovered "
    "expression of its own, it is not armour geometry, not a protection rating, "
    "not structural strength, not whole-program parity and not validated against "
    "any real ship."
)

# concept_design.ARMOUR_ROLES, repeated here so the kernel has no import cycle on
# the adapter it serves. The adapter keeps the authority for the role table.
BELT_ROLES = ("belt_main", "belt_upper", "belt_ends")
TOTAL_ROLES = ("belt_main", "belt_upper", "belt_ends", "bulkhead", "armour_bulge",
               "armour_deck", "conning", "rotating_armour", "gun_mount_armour")
COMPONENT_FIELDS = ("id", "kind", "target_id", "method_version", "mass_t")
SELECTED_FIELDS = TOTAL_ROLES + ("classification_complete",)
VALUE_KEYS = ("estimated_belts_t", "estimated_total_t", "selected_belts_t",
              "selected_total_t", "known_estimate_subtotal_t")
ID = "ship_armour"
DEFAULT_PATH = "$.concept_design.mass_summary"

ASSUMPTIONS = (
    "a component is one declared armour estimate, already derived by its own kernel "
    "and named with its own method version; this kernel reproduces no recovered "
    "expression and copies no ledger value into the declared estimate",
    "the three belts are main, upper and ends; the full armour adds bulkhead, bulge, "
    "deck, conning and the gun-mount armour; a barbette inside the gun-mount armour is "
    "fixed structure and is counted exactly once",
    "the declared complete figures are known only when the declaration is confirmed "
    "complete AND every declared component's mass is known; a single unknown component "
    "leaves both complete figures unknown, and the known subtotal states the uncovered "
    "component IDs beside it",
    "the selected actual is the current condition's canonical role mass; the belt "
    "actual needs its three belt roles and the full actual needs all nine roles and a "
    "fully classified ledger, so an unclassified mass or any unknown required role "
    "leaves the full actual unknown rather than read as zero",
    "a role with no recovered component estimate, such as rotating_armour, appears only "
    "in the selected actual and is never filled from the ledger into the declared "
    "estimate",
    "component identities are namespaced by family, so two families' identical local "
    "IDs stay distinct; a duplicated identity or a duplicated non-null target is refused "
    "as a contradiction, and a null target is never guessed into another component's",
)


class ArmourTotalsError(ValueError):
    """Report a refused armour-totals declaration with structured diagnostics."""

    def __init__(self, diagnostics):
        self.diagnostics = copy.deepcopy(diagnostics)
        super().__init__("; ".join(d["message"] for d in diagnostics if d.get("blocking", True)))


def _diag(code, message, path, field=None, blocking=True):
    return {"code": code, "severity": "error" if blocking else "warning", "field": field,
            "path": path, "message": message, "blocking": blocking}


def _unavailable(code, field, path, message):
    return {"code": code, "severity": "warning", "field": field, "path": path,
            "message": message, "blocking": False}


def _bounded_sum(terms, field, path, diagnostics):
    """The finite sum of the terms, or ``None`` with a structured range diagnostic.

    The pure interface accepts any finite component mass, and the selected roles
    may each be finite, so a sum can still overflow to an infinity that no JSON
    writer can carry. Every aggregate passes through here and is reported unknown
    rather than serialized as a non-finite number. Each aggregate keeps its own
    fate: an overflowing total never erases a belt figure that is still finite.
    """
    total = 0.0
    for term in terms:
        total += term
        if not math.isfinite(total):
            diagnostics.append(_unavailable(
                "armour_totals.range", field, path,
                "the %s sum exceeds the finite numeric range, so it is reported unknown rather "
                "than a non-finite number" % (field,)))
            return None
    return total


def _mass(value, path, diagnostics):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        diagnostics.append(_diag("armour_totals.invalid", "mass_t must be a finite number or null",
                                 path + ".mass_t", "mass_t"))
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        diagnostics.append(_diag("armour_totals.invalid",
                                 "mass_t exceeds the supported numeric range",
                                 path + ".mass_t", "mass_t"))
        return None
    if not math.isfinite(number):
        diagnostics.append(_diag("armour_totals.invalid", "mass_t must be a finite number or null",
                                 path + ".mass_t", "mass_t"))
        return None
    if number < 0.0:
        diagnostics.append(_diag("armour_totals.domain", "mass_t must not be negative",
                                 path + ".mass_t", "mass_t"))
        return None
    return number


def _text(value, path, field, diagnostics):
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        diagnostics.append(_diag("armour_totals.invalid",
                                 "%s must be a non-empty string or null" % (field,), path, field))
        return None
    return value


def validate_components(components, path=DEFAULT_PATH):
    """Normalize and validate the declared armour components.

    Every component must carry a unique namespaced ``id`` and a known role
    ``kind``. A duplicated identity, a duplicated non-null target and a wrong type
    are refused with :class:`ArmourTotalsError`; an unknown ``target_id`` and a
    null ``mass_t`` stay exactly as declared.
    """
    if components is None:
        return []
    if not isinstance(components, list):
        raise ArmourTotalsError(
            [_diag("armour_totals.invalid", "must be an array or null", path)])
    diagnostics = []
    normalized = []
    seen_ids = set()
    seen_targets = {}
    for position, raw in enumerate(components):
        cpath = "%s[%d]" % (path, position)
        if not isinstance(raw, dict):
            diagnostics.append(_diag("armour_totals.invalid", "must be an object", cpath))
            continue
        for key in sorted(set(raw) - set(COMPONENT_FIELDS)):
            diagnostics.append(_diag("armour_totals.unsupported_field",
                                     "unsupported field %r" % (key,), cpath + "." + key))
        identity = _text(raw.get("id"), cpath + ".id", "id", diagnostics)
        if identity is None:
            diagnostics.append(_diag("armour_totals.invalid",
                                     "id must be a non-empty namespaced string", cpath + ".id",
                                     "id"))
        elif identity in seen_ids:
            diagnostics.append(_diag("armour_totals.duplicate",
                                     "component id %r is declared twice; component estimates are "
                                     "never added twice" % (identity,), cpath + ".id", "id"))
        else:
            seen_ids.add(identity)
        kind = _text(raw.get("kind"), cpath + ".kind", "kind", diagnostics)
        if kind is not None and kind not in TOTAL_ROLES:
            diagnostics.append(_diag("armour_totals.enum",
                                     "kind must name a declared armour role",
                                     cpath + ".kind", "kind"))
        target = _text(raw.get("target_id"), cpath + ".target_id", "target_id", diagnostics)
        if target is not None:
            owner = seen_targets.get(target)
            if owner is not None:
                diagnostics.append(_diag(
                    "armour_totals.duplicate",
                    "target %r is already carried by component %r; one target is weighed once, "
                    "and unknown targets are never merged into each other" % (target, owner),
                    cpath + ".target_id", "target_id"))
            else:
                seen_targets[target] = identity
        normalized.append({
            "id": identity,
            "kind": kind,
            "target_id": target,
            "method_version": _text(raw.get("method_version"), cpath + ".method_version",
                                    "method_version", diagnostics),
            "mass_t": _mass(raw.get("mass_t"), cpath, diagnostics),
        })
    if diagnostics:
        raise ArmourTotalsError(diagnostics)
    return normalized


def _read_selected(selected_roles, path):
    """The nine canonical role masses plus the classification flag, if declared."""
    if selected_roles is None:
        return None
    if not isinstance(selected_roles, dict):
        raise ArmourTotalsError(
            [_diag("armour_totals.invalid", "selected_roles must be an object or null", path)])
    diagnostics = []
    values = {}
    for role in TOTAL_ROLES:
        values[role] = _mass(selected_roles.get(role), path + "." + role, diagnostics)
    complete = selected_roles.get("classification_complete")
    if complete is not None and not isinstance(complete, bool):
        diagnostics.append(_diag("armour_totals.invalid",
                                 "classification_complete must be a boolean or null",
                                 path + ".classification_complete", "classification_complete"))
        complete = None
    if diagnostics:
        raise ArmourTotalsError(diagnostics)
    values["classification_complete"] = complete
    return values


def evaluate(components, selected_roles, *, declared_complete, source, path=DEFAULT_PATH):
    """The declared-estimate and selected-actual armour totals.

    ``components`` is the adapter's list of declared armour estimates (each with
    ``id, kind, target_id, method_version, mass_t``). ``selected_roles`` is the
    current condition's canonical role mass for each of the nine armour roles,
    plus ``classification_complete``. ``declared_complete`` is the declaration's
    ``armour_scope_complete`` flag: only ``True`` says the declaration is the
    complete scope and every unlisted category is a declared zero. ``source`` is
    the declared source text.

    Returns a JSON-serialisable dict with at least ``id``, ``method_version``,
    ``status``, ``values``, ``coverage``, ``diagnostics`` and ``provenance``.
    """
    normalized = validate_components(components, path)
    selected = _read_selected(selected_roles, path)
    if declared_complete is not None and not isinstance(declared_complete, bool):
        raise ArmourTotalsError([_diag("armour_totals.invalid",
                                       "declared_complete must be a boolean or null",
                                       path, "armour_scope_complete")])
    source_text = _text(source, path + ".source", "source", []) if source is not None else None

    diagnostics = []
    declared = declared_complete is True
    unknown = [c for c in normalized if c["mass_t"] is None]
    known = [c for c in normalized if c["mass_t"] is not None]
    belts = [c for c in normalized if c["kind"] in BELT_ROLES]

    estimated_total = None
    estimated_belts = None
    if declared and not unknown:
        estimated_total = _bounded_sum([c["mass_t"] for c in normalized],
                                       "estimated_total_t", path, diagnostics)
        estimated_belts = _bounded_sum([c["mass_t"] for c in belts],
                                       "estimated_belts_t", path, diagnostics)
    elif not declared:
        diagnostics.append(_unavailable(
            "armour_totals.incomplete_declaration", "armour_scope_complete", path,
            "the declared armour scope is not confirmed complete, so the complete declared "
            "totals stay unknown; only the known subtotal and the uncovered components are "
            "reported"))
    else:
        diagnostics.append(_unavailable(
            "armour_totals.unknown_component", "mass_t", path,
            "%d declared component(s) have no derived mass, so a complete declared total would "
            "be a partial sum; the complete figures stay unknown and the uncovered component IDs "
            "are listed" % (len(unknown),)))

    if unknown and not known:
        subtotal = None
    else:
        subtotal = _bounded_sum([c["mass_t"] for c in known],
                                "known_estimate_subtotal_t", path, diagnostics)

    selected_belts = None
    selected_total = None
    if selected is not None:
        belt_values = [selected[role] for role in BELT_ROLES]
        if all(value is not None for value in belt_values):
            selected_belts = _bounded_sum(belt_values, "selected_belts_t", path, diagnostics)
        else:
            diagnostics.append(_unavailable(
                "armour_totals.selected_unknown", "belt_main", path,
                "the selected belt actual needs the main, upper and end belt roles, and at least "
                "one is unknown; it is never read as zero"))
        total_values = [selected[role] for role in TOTAL_ROLES]
        if selected["classification_complete"] is True and all(value is not None
                                                                for value in total_values):
            selected_total = _bounded_sum(total_values, "selected_total_t", path, diagnostics)
        else:
            diagnostics.append(_unavailable(
                "armour_totals.selected_unknown", "gun_mount_armour", path,
                "the selected full actual needs all nine armour roles and a fully classified "
                "ledger; an unclassified mass or any unknown required role leaves it unknown"))
    else:
        diagnostics.append(_unavailable(
            "armour_totals.selected_unknown", None, path,
            "no canonical role masses are declared, so the selected actual is unknown; it is "
            "never read as zero"))

    values = {
        "estimated_belts_t": estimated_belts,
        "estimated_total_t": estimated_total,
        "selected_belts_t": selected_belts,
        "selected_total_t": selected_total,
        "known_estimate_subtotal_t": subtotal,
    }
    coverage = {
        "declared_components": len(normalized),
        "known_components": len(known),
        "uncovered_component_ids": [c["id"] for c in unknown],
    }
    known_values = [value for value in values.values() if value is not None]
    if estimated_total is not None and selected_total is not None:
        status = "available"
    elif known_values:
        status = "partial"
    else:
        status = "unavailable"
    provenance = {
        "method": METHOD_VERSION,
        "kernel": "armour_totals_declared_and_selected",
        "source_assembly": kernels.SOURCE_ASSEMBLY,
        "source_sha256": kernels.SOURCE_SHA256,
        "source_location": "concept_design armour components and the selected balance roles",
        "source_scope": SOURCE_SCOPE,
        "formula": (
            "estimated_belts_t = sum of the belt_main, belt_upper and belt_ends component "
            "estimates when the declaration is complete and every component is known; "
            "estimated_total_t = sum of every component estimate under the same condition; "
            "selected_belts_t = the selected belt_main + belt_upper + belt_ends role masses; "
            "selected_total_t = the selected sum of all nine armour role masses when the ledger "
            "is fully classified; known_estimate_subtotal_t = the sum of the known component "
            "estimates"),
        "assumptions": " ".join(ASSUMPTIONS),
        "inputs": {
            "id": ID, "source": source_text, "declared_complete": declared_complete,
            "component_count": len(normalized),
            "belt_component_ids": [c["id"] for c in belts],
            "uncovered_component_ids": [c["id"] for c in unknown],
            "selected_roles": None if selected is None else dict(selected),
        },
    }
    return {"id": ID, "method_version": METHOD_VERSION, "status": status, "source": source_text,
            "values": values, "coverage": coverage, "diagnostics": diagnostics,
            "provenance": provenance}
