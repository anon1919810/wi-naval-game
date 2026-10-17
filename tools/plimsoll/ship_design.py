# -*- coding: utf-8 -*-
"""Native Plimsoll ship design: the single authoritative declaration.

``project.ship_design`` (schema ``plimsoll-ship-design-1``) is the one editable
fact. It reuses the accepted 222-field source semantics and is turned into a
source-compatibility declaration only through a pure adapter, so the accepted
kernels can run without a second user-facing product mode. Results never flow
back to guess the user's declaration.

The module is pure: no file, network or project-store access, and no input is
mutated. It owns four surfaces:

* :func:`from_source` / :func:`to_source` — the temporary source adapter;
* :func:`initialize` / :func:`preview` — the ``{project, design, preview, status,
  diagnostics}`` reply used by the reusable serial editor, where ``design`` is the
  source-view and ``project.ship_design`` is authoritative;
* :func:`compute` — the native ``plimsoll-ship-design-result-1`` result with the
  source reading, the method-identity report, the unified ledger and the balance;
* :func:`validate` — projection/ownership consistency diagnostics with no
  ``project_io.normalize`` recursion.

Shared SI hull projection and the mass-ledger projection are written here; the
loading resolver that applies the scoped ``design_mass`` overlay is owned by the
parent integration, not by this unit.
"""
from __future__ import annotations

import copy
import math

try:  # As part of the plimsoll package.
    from . import sps_compat, ship_design_mass
except ImportError:  # Direct top-level import (tests/scripts).
    import sps_compat
    import ship_design_mass


SCHEMA = "plimsoll-ship-design-1"
RESULT_SCHEMA = "plimsoll-ship-design-result-1"
METHOD_VERSION = "ship-design-native-v1"
SOURCE_SCHEMA = sps_compat.SCHEMA
DEFAULT_CONDITION_ID = "design-normal"

#: Source internal imperial -> canonical SI.
FT_M = 0.3048
LONG_TON_T = ship_design_mass.LONG_TON_T

#: The canonical hull keys that mirror the authoritative declaration. Everything
#: else in ``project.hull`` (sources, geometry-adjacent metadata) is preserved.
HULL_PROJECTION_KEYS = (
    "lwl_m", "loa_m", "beam_m", "beam_bulges_m", "draught_normal_m",
    "draught_deep_m", "block_coeff", "waterplane_coeff",
)


class ShipDesignError(ValueError):
    """Report a rejected source declaration with structured diagnostics."""

    def __init__(self, diagnostics):
        self.diagnostics = copy.deepcopy(diagnostics)
        errors = [d for d in self.diagnostics if d.get("severity", "error") == "error"]
        detail = "; ".join(d.get("message", "") for d in errors[:3])
        super().__init__("ship-design input rejected: " + detail)


def _diag(code, message, path="$.ship_design", severity="error"):
    return {"code": code, "severity": severity, "path": path, "message": message,
            "blocking": severity == "error"}


# --------------------------------------------------------------- adapters

def _extract_source(source):
    if not isinstance(source, dict):
        raise ShipDesignError([_diag("ship_design.source_invalid",
                                     "source must be an object", "$.ship_design.source")])
    if isinstance(source.get("sps_3b3_design"), dict):
        return source["sps_3b3_design"]
    if isinstance(source.get("ship_design"), dict):
        return to_source(source["ship_design"])
    return source


def from_source(source, condition_id=DEFAULT_CONDITION_ID):
    """Build an authoritative native declaration from one source-view design.

    Accepts a source-view declaration, a legacy project carrying
    ``sps_3b3_design``, or a native declaration (idempotent re-import).
    """
    design = _extract_source(source)
    normalized = sps_compat.normalize(design)
    if normalized["status"] == "unavailable" or normalized["design"].get("schema") != SOURCE_SCHEMA:
        raise ShipDesignError(normalized["diagnostics"] or [
            _diag("ship_design.source_schema",
                  "source must use schema %r" % (SOURCE_SCHEMA,), "$.ship_design.source")])
    if not isinstance(condition_id, str) or not condition_id.strip():
        raise ShipDesignError([_diag("ship_design.condition_invalid",
                                     "condition_id must be a non-empty string",
                                     "$.ship_design.condition_id")])
    view = normalized["design"]
    return {
        "schema": SCHEMA,
        "source": view.get("source"),
        "parameters": copy.deepcopy(view.get("parameters") or {}),
        "editing": copy.deepcopy(view.get("editing") or {}),
        "notes": view.get("notes"),
        "condition_id": condition_id,
        "mass_bindings": {},
    }


def to_source(native):
    """Return the reusable source-view declaration for the existing widgets."""
    if not isinstance(native, dict):
        native = {}
    return {
        "schema": SOURCE_SCHEMA,
        "source": native.get("source"),
        "parameters": copy.deepcopy(native.get("parameters") or {}),
        "editing": copy.deepcopy(native.get("editing") or {}),
        "notes": native.get("notes"),
    }


def _blank_native(condition_id=DEFAULT_CONDITION_ID):
    try:
        from . import sps_file_io
    except ImportError:  # Direct-module use.
        import sps_file_io
    return from_source(sps_file_io.default_design(), condition_id)


# --------------------------------------------------------------- projection

def _projection(source_result):
    hull = source_result.get("hull") if isinstance(source_result, dict) else None
    perf = source_result.get("performance") if isinstance(source_result, dict) else None

    def metres(value):
        if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(float(value)):
            return None
        return float(value) * FT_M

    def number(value):
        if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value) if math.isfinite(float(value)) else None

    return {
        "lwl_m": metres(hull.get("length") if isinstance(hull, dict) else None),
        "loa_m": metres(hull.get("lengthOA") if isinstance(hull, dict) else None),
        "beam_m": metres(hull.get("beam") if isinstance(hull, dict) else None),
        "beam_bulges_m": metres(hull.get("beamBulges") if isinstance(hull, dict) else None),
        "draught_normal_m": metres(hull.get("draught") if isinstance(hull, dict) else None),
        "draught_deep_m": metres(perf.get("draughtDeep") if isinstance(perf, dict) else None),
        "block_coeff": number(hull.get("block") if isinstance(hull, dict) else None),
        "waterplane_coeff": number(hull.get("coWaterPlane") if isinstance(hull, dict) else None),
    }


def _apply_projection(project, projection):
    hull = project.get("hull")
    if not isinstance(hull, dict):
        hull = {}
        project["hull"] = hull
    for key in HULL_PROJECTION_KEYS:
        hull[key] = projection.get(key)
    return hull


# --------------------------------------------------------------- conditions

def _conditions(project):
    conditions = project.get("loading_conditions")
    if not isinstance(conditions, list):
        conditions = []
        project["loading_conditions"] = conditions
    return conditions


def _non_derived(project):
    return [c for c in _conditions(project)
            if isinstance(c, dict) and "definition" not in c and isinstance(c.get("id"), str)]


def _owner_condition(project, condition_id):
    for condition in _conditions(project):
        if isinstance(condition, dict) and condition.get("id") == condition_id:
            return condition
    return None


def _condition_id_in_use(project):
    return {c.get("id") for c in _conditions(project) if isinstance(c, dict)}


def _unique_condition_id(project, base):
    """A free non-colliding condition ID, so a derived study is never reused."""
    in_use = _condition_id_in_use(project)
    if base not in in_use:
        return base
    index = 2
    while "%s-%d" % (base, index) in in_use:
        index += 1
    return "%s-%d" % (base, index)


def _ensure_condition(project, desired_id, diagnostics):
    """Choose an existing non-derived condition or create the native owner one.

    A derived study may never own the design ledger: if the desired ID is taken by a
    derived condition and no other non-derived condition exists, the owner gets a
    fresh non-colliding ID so the derived study is left exactly as it was.
    """
    desired_id = desired_id if isinstance(desired_id, str) and desired_id.strip() \
        else DEFAULT_CONDITION_ID
    existing = _owner_condition(project, desired_id)
    if isinstance(existing, dict) and "definition" not in existing:
        return desired_id
    if isinstance(existing, dict):
        diagnostics.append(_diag(
            "ship_design.condition_derived",
            "the design condition %r is a derived study and cannot own the design ledger"
            % (desired_id,), "$.ship_design.condition_id"))
    available = _non_derived(project)
    if available:
        return available[0]["id"]
    owner_id = _unique_condition_id(project, desired_id)
    condition = {"id": owner_id, "label": owner_id, "reference_displacement_t": None,
                 "overrides": {}, "override_provenance": {}}
    _conditions(project).append(condition)
    return owner_id


def _write_owner_override(project, condition_id, item_id, value, source):
    condition = _owner_condition(project, condition_id)
    if condition is None:
        return False
    overrides = condition.get("overrides")
    if not isinstance(overrides, dict):
        overrides = {}
        condition["overrides"] = overrides
    overrides[item_id] = {"mass_t": value}
    provenance = condition.get("override_provenance")
    if not isinstance(provenance, dict):
        provenance = {}
        condition["override_provenance"] = provenance
    entry = provenance.setdefault(item_id, {})
    entry["mass_t"] = {"source": copy.deepcopy(source), "estimate": False}
    return True


# ------------------------------------------------------------- report/status

def _build_report(source_result):
    try:
        from . import sps_report
    except ImportError:  # pragma: no cover - direct import
        try:
            import sps_report
        except ImportError:
            return None
    if not hasattr(sps_report, "build"):
        return None
    try:
        return sps_report.build(source_result)
    except Exception:  # pragma: no cover - defensive
        return None


def _status(source_result, ledger_summary, diagnostics):
    if any(d.get("severity") == "error" and d.get("blocking", True) for d in diagnostics):
        return "partial"
    if ledger_summary and (ledger_summary.get("needs_binding")
                           or ledger_summary.get("selected_mass_t") is None):
        return "partial"
    return source_result.get("status") or "unavailable"


def _reply(project, native, preview, status, diagnostics):
    return {"project": project, "design": to_source(native) if native else None,
            "preview": preview, "status": status, "diagnostics": diagnostics}


def _merge_diagnostics(source_result, diagnostics):
    """Source diagnostics first, then this unit's, de-duplicated by identity.

    A source error or warning may never vanish just because the native layer also
    ran, and an edit-only diagnostic may legitimately differ from a plain recompute,
    so both sets are kept in order.
    """
    merged = []
    seen = set()
    source_diagnostics = source_result.get("diagnostics") if isinstance(source_result, dict) else None
    for group in (source_diagnostics, diagnostics):
        for entry in group or []:
            if not isinstance(entry, dict):
                continue
            key = (entry.get("code"), entry.get("path"), entry.get("message"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(entry)
    return merged


def _native_result(source_result, requested_condition_id, basis_condition_id, ledger,
                   diagnostics):
    """Build the ``plimsoll-ship-design-result-1`` result.

    The result carries the native identity (source adapter declaration, report,
    ledger, balance) *and* lifts the accepted source sections to the top level so
    existing hull/weights/freeboard widgets keep reading the same keys they always
    have. ``condition_id`` is the requested physical run; ``basis_condition_id`` is
    always the design's own non-derived owner condition, so a selected study can
    never impersonate the design basis. Source diagnostics and native diagnostics are
    merged so neither can disappear.
    """
    combined = _merge_diagnostics(source_result, diagnostics)
    return {
        "schema": RESULT_SCHEMA,
        "method_version": METHOD_VERSION,
        "status": _status(source_result, ledger, combined),
        "condition_id": requested_condition_id,
        "basis_condition_id": basis_condition_id,
        "source_design": source_result.get("design"),
        "design": source_result.get("design"),
        "source_result": source_result,
        "hull": source_result.get("hull"),
        "freeboard": source_result.get("freeboard"),
        "guns": source_result.get("guns"),
        "auxiliary": source_result.get("auxiliary"),
        "armour": source_result.get("armour"),
        "engine": source_result.get("engine"),
        "performance": source_result.get("performance"),
        "review": source_result.get("review"),
        "hull_projection": _projection(source_result),
        "report": _build_report(source_result),
        "ledger": ledger,
        "balance": _balance(ledger),
        "diagnostics": combined,
        "provenance": _provenance(),
    }


def _finalize(project, native, diagnostics):
    """Recompute projection + ledger and build a complete reply from a draft."""
    project = copy.deepcopy(project)
    project["ship_design"] = copy.deepcopy(native)
    source_view = to_source(native)
    source_result = sps_compat.compute(source_view)
    _apply_projection(project, _projection(source_result))
    basis_condition_id = native.get("condition_id") or DEFAULT_CONDITION_ID
    reconciled = ship_design_mass.reconcile(
        project, source_result, basis_condition_id, native.get("mass_bindings") or None)
    project = reconciled["project"]
    project["ship_design"]["mass_bindings"] = copy.deepcopy(reconciled["bindings"])
    diagnostics = list(diagnostics) + reconciled["diagnostics"]
    ledger = reconciled["summary"]
    result = _native_result(source_result, basis_condition_id, basis_condition_id, ledger,
                            diagnostics)
    return _reply(project, project["ship_design"], result, result["status"],
                  result["diagnostics"])


# --------------------------------------------------------------- initialize

def initialize(project, source=None):
    """Return a coherent draft with the authoritative native design in place.

    Upgrades a legacy ``sps_3b3_design`` by removing the old active section in
    the returned draft only; saved revisions and original migration bytes are
    never touched. A project that already carries the native declaration is kept.
    """
    diagnostics = []
    if not isinstance(project, dict):
        return _reply({}, None, None, "unavailable",
                      [_diag("ship_design.project_invalid", "project must be an object", "$")])
    out = copy.deepcopy(project)
    native = out.get("ship_design")
    legacy = out.get("sps_3b3_design")
    if isinstance(native, dict) and native.get("schema") == SCHEMA and legacy is not None:
        diagnostics.append(_diag(
            "ship_design.dual_declaration",
            "both ship_design and the legacy sps_3b3_design are present; the active "
            "declaration cannot be guessed", "$.ship_design"))
        return _reply(out, native, None, "partial", diagnostics)
    try:
        if source is not None:
            previous = native if isinstance(native, dict) and native.get("schema") == SCHEMA else None
            native = from_source(source, (previous or {}).get("condition_id") or DEFAULT_CONDITION_ID)
            if previous:
                native["mass_bindings"] = copy.deepcopy(previous.get("mass_bindings") or {})
        elif isinstance(native, dict) and native.get("schema") == SCHEMA:
            native = copy.deepcopy(native)
        elif legacy is not None:
            native = from_source(legacy)
        else:
            native = _blank_native()
    except ShipDesignError as error:
        diagnostics.extend(error.diagnostics)
        return _reply(out, None, None, "unavailable", diagnostics)
    out["ship_design"] = native
    out.pop("sps_3b3_design", None)
    native["condition_id"] = _ensure_condition(out, native.get("condition_id"), diagnostics)
    return _finalize(out, native, diagnostics)


# ------------------------------------------------------------- commands

def _apply_bind_mass(project, native, command, diagnostics):
    role = command.get("role")
    mode = command.get("mode")
    ids = command.get("item_ids")
    path = "$.command"
    if role not in ship_design_mass.ROLES:
        diagnostics.append(_diag("ship_design.binding_role_unknown",
                                 "unknown mass role %r" % (role,), path))
        return
    if mode not in ("estimated", "declared"):
        diagnostics.append(_diag("ship_design.binding_mode_invalid",
                                 "mode must be 'estimated' or 'declared'", path))
        return
    if (not isinstance(ids, list) or not ids
            or not all(isinstance(item_id, str) and item_id.strip() for item_id in ids)):
        diagnostics.append(_diag("ship_design.binding_ids_invalid",
                                 "item_ids must be a non-empty list of IDs", path))
        return
    ids = list(dict.fromkeys(ids))
    if mode == "estimated" and len(ids) != 1:
        diagnostics.append(_diag("ship_design.binding_estimated_multiple",
                                 "an estimated role permits exactly one managed target", path))
        return
    # Every bound item must exist. The only exception is the canonical managed
    # target for this very role, which reconcile creates; any other unknown ID is a
    # mismatched target and is refused rather than silently accepted.
    managed_id = ship_design_mass.MANAGED_ITEM_PREFIX + role
    for item_id in ids:
        exists = isinstance(ship_design_mass._find_item(project, item_id), dict)
        if not exists and not (mode == "estimated" and item_id == managed_id):
            diagnostics.append(_diag(
                "ship_design.binding_item_unknown",
                "item %r is not in the ledger and is not the managed target for role %r"
                % (item_id, role), path))
            return
    bindings = native.get("mass_bindings")
    if not isinstance(bindings, dict):
        bindings = {}
        native["mass_bindings"] = bindings
    owned = {item_id: other for other, entry in bindings.items()
             for item_id in (entry.get("item_ids") or []) if isinstance(entry, dict)}
    for item_id in ids:
        holder = owned.get(item_id)
        if holder is not None and holder != role:
            diagnostics.append(_diag(
                "ship_design.binding_duplicate_item",
                "item %r is already owned by role %r; one item may belong to only one role"
                % (item_id, holder), path))
            return
    bindings[role] = {"item_ids": ids, "mode": mode}

    condition_id = native.get("condition_id") or DEFAULT_CONDITION_ID
    if mode == "declared":
        explicit = command.get("mass_t", command.get("value"))
        explicit_ok = (isinstance(explicit, (int, float)) and not isinstance(explicit, bool)
                       and math.isfinite(float(explicit)))
        for item_id in ids:
            item = ship_design_mass._find_item(project, item_id)
            if not isinstance(item, dict):
                continue
            if len(ids) == 1 and explicit_ok:
                _write_owner_override(project, condition_id, item_id, float(explicit),
                                      {"owner": ship_design_mass.OWNER,
                                       "kind": "declared_mass", "manual": True})
            else:
                # Retain the then-effective mass rather than falling back to a
                # managed row's exclusion zero. A previously estimated item keeps
                # its overlay as the declared mass; an already declared item keeps
                # its own condition override and is left untouched.
                design_mass = item.get("design_mass")
                if isinstance(design_mass, dict) and design_mass.get("mass_t") is not None:
                    _write_owner_override(project, condition_id, item_id,
                                          float(design_mass["mass_t"]),
                                          {"owner": ship_design_mass.OWNER,
                                           "kind": "retained_selected_mass", "manual": True})
            item.pop("design_mass", None)


def _apply_set_declared_mass(project, native, command, diagnostics):
    item_id = command.get("item_id")
    value = command.get("value")
    path = "$.command"
    if not isinstance(item_id, str) or not item_id.strip():
        diagnostics.append(_diag("ship_design.declared_item_invalid",
                                 "item_id must be a non-empty string", path))
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        diagnostics.append(_diag("ship_design.declared_value_invalid",
                                 "value must be a finite real number", path))
        return
    item = ship_design_mass._find_item(project, item_id)
    if not isinstance(item, dict):
        diagnostics.append(_diag("ship_design.declared_item_unknown",
                                 "item %r is not in the ledger" % (item_id,), path))
        return
    # A declared mass may not silently flip an estimated role: the caller must
    # explicitly switch the role to declared with bind_mass first, exactly as the
    # spec requires. Otherwise a stray edit could desynchronise the managed
    # estimate without an explicit binding decision.
    bindings = native.get("mass_bindings")
    if isinstance(bindings, dict):
        for role, entry in bindings.items():
            if isinstance(entry, dict) and item_id in (entry.get("item_ids") or []):
                if entry.get("mode") == "estimated":
                    diagnostics.append(_diag(
                        "ship_design.declared_requires_binding",
                        "item %r is bound as an estimated role (%r); bind that role as "
                        "declared with bind_mass before setting a declared mass"
                        % (item_id, role), path))
                    return
                break
    condition_id = native.get("condition_id") or DEFAULT_CONDITION_ID
    if not _write_owner_override(project, condition_id, item_id, float(value),
                                 {"owner": ship_design_mass.OWNER,
                                  "kind": "set_declared_mass", "manual": True,
                                  "condition_id": condition_id}):
        diagnostics.append(_diag("ship_design.condition_missing",
                                 "the owner condition %r is missing" % (condition_id,), path))
        return
    # The role is already declared, so the manual override is authoritative; drop
    # any stale managed overlay but never alter the binding mode here.
    item.pop("design_mass", None)


def _adopt_source_view(native, design, diagnostics):
    """Adopt a caller-supplied authoritative source view (a commandless replace).

    The frontend's ``queue.replace`` posts the whole current source view without a
    command. Its ``source``, ``notes``, ``parameters`` and ``editing`` are
    authoritative and replace the native source view exactly, while the native basis
    condition and mass bindings are preserved (they are native identity, not source
    fields) and manual loading overrides live outside the declaration entirely. The
    view is validated through the accepted source normalizer: a view that is not a
    source-usable declaration leaves the existing declaration untouched and reports
    why, and normalizer findings are surfaced rather than dropped.
    """
    try:
        view = _extract_source(design)
    except ShipDesignError as error:
        diagnostics.extend(error.diagnostics)
        return False
    normalized = sps_compat.normalize(view)
    if normalized["status"] == "unavailable" or \
            normalized["design"].get("schema") != SOURCE_SCHEMA:
        diagnostics.extend(normalized["diagnostics"] or [
            _diag("ship_design.source_schema",
                  "the supplied source view must use schema %r" % (SOURCE_SCHEMA,),
                  "$.design")])
        return False
    for entry in normalized.get("diagnostics", []):
        diagnostics.append(copy.deepcopy(entry))
    adopted = normalized["design"]
    native["source"] = adopted.get("source")
    native["parameters"] = copy.deepcopy(adopted.get("parameters") or {})
    native["editing"] = copy.deepcopy(adopted.get("editing") or {})
    native["notes"] = adopted.get("notes")
    return True


def preview(project, command=None, design=None):
    """Pure, no-write preview reply.

    ``design`` supplies the latest confirmed source-view base. It is authoritative for
    the whole source view when no command is present (the frontend's commandless
    ``queue.replace``), and is the base an edit command is applied to; either way the
    native basis condition and mass bindings survive. The returned project always
    carries the re-projected hull and the reconciled ledger.
    """
    diagnostics = []
    if not isinstance(project, dict):
        return _reply({}, None, None, "unavailable",
                      [_diag("ship_design.project_invalid", "project must be an object", "$")])
    out = copy.deepcopy(project)
    native = out.get("ship_design")
    legacy = out.get("sps_3b3_design")
    # The same authority rule as initialize: a project carrying both the native and
    # the legacy declaration cannot be previewed, and must never silently return a
    # mixed success from whichever declaration it happened to prefer.
    if isinstance(native, dict) and native.get("schema") == SCHEMA and legacy is not None:
        diagnostics.append(_diag(
            "ship_design.dual_declaration",
            "both ship_design and the legacy sps_3b3_design are present; the active "
            "declaration cannot be guessed", "$.ship_design"))
        return _reply(out, native, None, "partial", diagnostics)
    if not isinstance(native, dict) or native.get("schema") != SCHEMA:
        try:
            native = from_source(legacy) if legacy is not None else (_blank_native())
        except ShipDesignError as error:
            diagnostics.extend(error.diagnostics)
            return _reply(out, None, None, "unavailable", diagnostics)
        out["ship_design"] = native
        out.pop("sps_3b3_design", None)
    native["condition_id"] = _ensure_condition(out, native.get("condition_id"), diagnostics)

    kind = command.get("kind") if isinstance(command, dict) else None
    if kind == "bind_mass":
        _apply_bind_mass(out, native, command, diagnostics)
    elif kind == "set_declared_mass":
        _apply_set_declared_mass(out, native, command, diagnostics)
    elif isinstance(command, dict):
        base = design if isinstance(design, dict) else to_source(native)
        edited = sps_compat.apply_edit(base, command)
        view = edited["design"]
        native["source"] = view.get("source")
        native["parameters"] = copy.deepcopy(view.get("parameters") or {})
        native["editing"] = copy.deepcopy(view.get("editing") or {})
        native["notes"] = view.get("notes")
        diagnostics.extend(edited.get("diagnostics", []))
    elif command is not None:
        diagnostics.append(_diag("ship_design.command_invalid",
                                 "command must be an object or null", "$.command"))
    elif design is not None:
        _adopt_source_view(native, design, diagnostics)
    return _finalize(out, native, diagnostics)


# --------------------------------------------------------------- compute

def _balance(ledger):
    if not isinstance(ledger, dict):
        return None
    return {
        "condition_id": ledger.get("condition_id"),
        "basis_condition_id": ledger.get("basis_condition_id"),
        "selected_mass_t": ledger.get("selected_mass_t"),
        "estimated_mass_t": ledger.get("estimated_mass_t"),
        "target_displacement_t": ledger.get("target_displacement_t"),
        "difference_t": ledger.get("difference_t"),
        "needs_binding": list(ledger.get("needs_binding") or []),
        "complete": ledger.get("complete"),
    }


def compute(project, condition_id=None):
    """Return the native ``plimsoll-ship-design-result-1`` result.

    The result carries the source adapter declaration, the method-identity report,
    the unified ledger and the balance, plus the accepted source sections lifted to
    the top level for the existing widgets. The ledger and balance are always
    reconciled against the design's own condition: a requested physical condition is
    reported as ``condition_id`` only and never becomes the overlay scope, so a
    selected study can never impersonate the design basis.
    """
    diagnostics = []
    native = project.get("ship_design") if isinstance(project, dict) else None
    if not isinstance(native, dict) or native.get("schema") != SCHEMA:
        empty = _native_result({}, condition_id, condition_id, None, None)
        empty["diagnostics"] = [_diag("ship_design.missing",
                                      "the project has no native ship_design declaration",
                                      "$.ship_design")]
        empty["status"] = "unavailable"
        return empty
    source_result = sps_compat.compute(to_source(native))
    basis_condition_id = native.get("condition_id") or DEFAULT_CONDITION_ID
    reconciled = ship_design_mass.reconcile(
        project, source_result, basis_condition_id, native.get("mass_bindings") or None)
    ledger = reconciled["summary"]
    diagnostics.extend(reconciled["diagnostics"])
    requested_condition_id = condition_id or basis_condition_id
    return _native_result(source_result, requested_condition_id, basis_condition_id, ledger,
                          diagnostics)


def _provenance():
    return {
        "method_version": METHOD_VERSION,
        "source_schema": SOURCE_SCHEMA,
        "source_method_version": sps_compat.METHOD_VERSION,
        "units": "source readings ft/in/lb/long ton; native masses and dimensions metric",
        "note": ("The native declaration is the authority; the source-view is a pure "
                 "adapter. The balance is an empirical source-method screen, not a "
                 "physical hydrostatics or GM claim."),
    }


# --------------------------------------------------------------- validate

def validate(project):
    """Return structural + projection consistency diagnostics.

    Never calls ``project_io`` and never mutates. The save/analysis integrity
    boundary is strict: it rejects a malformed or null native declaration, a missing
    or derived owner condition, a malformed binding (invalid role/mode/IDs), a
    duplicate binding, an estimated role without its managed target, overlay or
    matching scoped estimate, an unbound managed overlay, a hull projection that is
    missing or in conflict when the declaration knows the value, and a real
    aggregate-ownership overlap. A legacy-only project yields one non-blocking
    warning.
    """
    diagnostics = []
    if not isinstance(project, dict):
        return [_diag("ship_design.project_invalid", "project must be an object", "$")]
    legacy = project.get("sps_3b3_design")
    if "ship_design" not in project:
        for _gi, _ii, item in ship_design_mass._group_items(project):
            overlay = item.get("design_mass")
            if isinstance(overlay, dict) and overlay.get("owner") == ship_design_mass.OWNER:
                diagnostics.append(_diag("ship_design.orphan_overlay",
                    "a managed mass requires its authoritative ship_design declaration",
                    "$.weight_groups.%s.design_mass" % item.get("id")))
        if legacy is not None:
            diagnostics.append(_diag(
                "ship_design.legacy_active",
                "the project still carries the legacy sps_3b3_design declaration; upgrade "
                "it explicitly through initialize/preview before saving a native identity",
                "$.sps_3b3_design", "warning"))
        return diagnostics
    native = project.get("ship_design")
    if not isinstance(native, dict):
        diagnostics.append(_diag(
            "ship_design.schema_invalid",
            "ship_design must be an object with schema %r" % (SCHEMA,), "$.ship_design"))
        return diagnostics
    if legacy is not None:
        diagnostics.append(_diag("ship_design.dual_declaration",
                                 "both ship_design and sps_3b3_design are present",
                                 "$.ship_design"))
    if native.get("schema") != SCHEMA:
        diagnostics.append(_diag("ship_design.schema_invalid",
                                 "schema must be %r" % (SCHEMA,), "$.ship_design.schema"))
        return diagnostics

    condition_id = native.get("condition_id")
    if not isinstance(condition_id, str) or not condition_id.strip():
        diagnostics.append(_diag("ship_design.condition_invalid",
                                 "condition_id must be a non-empty string",
                                 "$.ship_design.condition_id"))
        condition_id = None
    else:
        condition = _owner_condition(project, condition_id)
        if not isinstance(condition, dict):
            diagnostics.append(_diag("ship_design.condition_missing",
                                     "the owner condition %r does not exist" % (condition_id,),
                                     "$.ship_design.condition_id"))
        elif "definition" in condition:
            diagnostics.append(_diag("ship_design.condition_derived",
                                     "the owner condition %r is a derived study" % (condition_id,),
                                     "$.ship_design.condition_id"))

    bindings = native.get("mass_bindings")
    estimated_roles = {}
    owned = {}
    if not isinstance(bindings, dict):
        diagnostics.append(_diag("ship_design.bindings_invalid",
                                 "mass_bindings must be an object of role -> binding",
                                 "$.ship_design.mass_bindings"))
        bindings = {}
    else:
        for role, entry in bindings.items():
            path = "$.ship_design.mass_bindings[%r]" % (role,)
            if role not in ship_design_mass.ROLES:
                diagnostics.append(_diag("ship_design.binding_role_unknown",
                                         "unknown mass role %r" % (role,), path))
                continue
            if not isinstance(entry, dict):
                diagnostics.append(_diag("ship_design.binding_invalid",
                                         "a binding must be an object with item_ids and mode",
                                         path))
                continue
            mode = entry.get("mode")
            if mode not in ("estimated", "declared"):
                diagnostics.append(_diag("ship_design.binding_mode_invalid",
                                         "mode must be 'estimated' or 'declared'", path))
                continue
            ids = entry.get("item_ids")
            if (not isinstance(ids, list) or not ids
                    or not all(isinstance(i, str) and i.strip() for i in ids)
                    or len(set(ids)) != len(ids)):
                diagnostics.append(_diag("ship_design.binding_ids_invalid",
                                         "item_ids must be a non-empty list of unique IDs",
                                         path))
                continue
            if mode == "estimated":
                if len(ids) != 1:
                    diagnostics.append(_diag(
                        "ship_design.binding_estimated_multiple",
                        "an estimated role permits exactly one managed target", path))
                estimated_roles[role] = ids
            for item_id in ids:
                if ship_design_mass._find_item(project, item_id) is None:
                    diagnostics.append(_diag("ship_design.binding_item_unknown",
                        "binding names missing ledger item %r" % item_id, path))
                if item_id in owned and owned[item_id] != role:
                    diagnostics.append(_diag(
                        "ship_design.binding_duplicate_item",
                        "item %r is bound to roles %r and %r" % (item_id, owned[item_id], role),
                        path))
                owned[item_id] = role

    source_view = to_source(native)
    normalized = sps_compat.normalize(source_view)
    for diagnostic in normalized.get("diagnostics", []):
        if diagnostic.get("severity") == "error":
            diagnostics.append(copy.deepcopy(diagnostic))
    source_result = sps_compat.compute(source_view)
    projection = _projection(source_result)
    hull = project.get("hull")
    if isinstance(hull, dict):
        for key in HULL_PROJECTION_KEYS:
            expected = projection.get(key)
            if expected is None:
                if hull.get(key) is not None:
                    diagnostics.append(_diag("ship_design.projection_conflict",
                        "unknown design dimension cannot retain a previous known projection",
                        "$.hull." + key))
                continue
            actual = hull.get(key)
            if key not in hull or actual is None:
                diagnostics.append(_diag(
                    "ship_design.projection_missing",
                    "hull.%s is missing from the shared SI projection even though the "
                    "declaration knows the value" % key, "$.hull." + key))
            elif actual != expected:
                diagnostics.append(_diag(
                    "ship_design.projection_conflict",
                    "hull.%s (%r) disagrees with the declaration projection (%r); use "
                    "an edit command instead of editing the projection directly"
                    % (key, actual, expected), "$.hull." + key))

    detail = ship_design_mass.estimate_detail(source_result)
    estimated_targets = set()
    for role, ids in estimated_roles.items():
        item_id = ids[0]
        estimated_targets.add(item_id)
        item = ship_design_mass._find_item(project, item_id)
        if not isinstance(item, dict):
            diagnostics.append(_diag(
                "ship_design.estimated_target_missing",
                "estimated role %r has no ledger item %r" % (role, item_id),
                "$.ship_design.mass_bindings[%r]" % (role,)))
            continue
        design_mass = item.get("design_mass")
        if not isinstance(design_mass, dict):
            diagnostics.append(_diag(
                "ship_design.estimated_overlay_missing",
                "estimated role %r target %r has no scoped design_mass overlay"
                % (role, item_id), "$.weight_groups.%s.design_mass" % item_id))
            continue
        if design_mass.get("owner") != ship_design_mass.OWNER:
            diagnostics.append(_diag(
                "ship_design.estimated_owner_invalid",
                "the scoped overlay for %r is owned by %r, not %r"
                % (item_id, design_mass.get("owner"), ship_design_mass.OWNER),
                "$.weight_groups.%s.design_mass.owner" % item_id))
        if condition_id is not None and design_mass.get("condition_id") != condition_id:
            diagnostics.append(_diag(
                "ship_design.estimated_scope_invalid",
                "estimated overlay for %r names condition %r, not the design basis %r"
                % (item_id, design_mass.get("condition_id"), condition_id),
                "$.weight_groups.%s.design_mass" % item_id))
        mass = design_mass.get("mass_t")
        if mass is not None and (isinstance(mass, bool) or not isinstance(mass, (int, float))):
            diagnostics.append(_diag(
                "ship_design.estimated_mass_type",
                "the scoped estimate for role %r must be a real number or null, not %r"
                % (role, mass), "$.weight_groups.%s.design_mass.mass_t" % item_id))
        elif mass != detail["masses"].get(role):
            diagnostics.append(_diag(
                "ship_design.estimated_mass_altered",
                "the scoped estimate for role %r was modified directly (%r vs %r); "
                "switch the role to declared instead"
                % (role, mass, detail["masses"].get(role)),
                "$.weight_groups.%s.design_mass" % item_id))

    for _gi, _ii, item in ship_design_mass._group_items(project):
        item_id = item.get("id")
        if not isinstance(item_id, str):
            continue
        design_mass = item.get("design_mass")
        if isinstance(design_mass, dict) and item_id not in estimated_targets:
            diagnostics.append(_diag(
                "ship_design.unbound_overlay",
                "item %r carries a managed overlay but is not the target of an estimated "
                "role binding; the overlay must be removed or the role bound explicitly"
                % (item_id,), "$.weight_groups.%s.design_mass" % item_id))

    _validate_aggregate_ownership(project, diagnostics)
    return diagnostics


def _active_item(item):
    """True when an item contributes a non-zero mass in any visible representation."""
    for source in (item, item.get("design_mass")):
        if not isinstance(source, dict):
            continue
        mass = source.get("mass_t")
        if isinstance(mass, (int, float)) and not isinstance(mass, bool) and mass != 0:
            return True
    return False


def _validate_aggregate_ownership(project, diagnostics):
    owners = {}
    for _gi, _ii, item in ship_design_mass._group_items(project):
        item_id = item.get("id")
        if not isinstance(item_id, str) or not _active_item(item):
            continue
        tokens = {item_id}
        includes = item.get("includes")
        if isinstance(includes, list):
            tokens.update(t for t in includes if isinstance(t, str))
        for token in tokens:
            owners.setdefault(token, set()).add(item_id)
    for token, item_ids in sorted(owners.items()):
        if len(item_ids) > 1:
            diagnostics.append(_diag(
                "ship_design.aggregate_conflict",
                "ledger items %s both claim component token %r; ownership must be unique"
                % (sorted(item_ids), token), "$.weight_groups"))


__all__ = ["SCHEMA", "RESULT_SCHEMA", "METHOD_VERSION", "SOURCE_SCHEMA",
           "DEFAULT_CONDITION_ID", "HULL_PROJECTION_KEYS", "ShipDesignError",
           "from_source", "to_source", "initialize", "preview", "compute",
           "validate"]
