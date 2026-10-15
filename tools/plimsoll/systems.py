"""Summarize ship systems against the selected canonical loading ledger."""

from __future__ import annotations

import copy
import math

SCHEMA = "plimsoll-systems-summary-1"


def _diagnostic(code: str, severity: str, path: str, message: str, blocking: bool = False) -> dict:
    return {
        "code": code,
        "severity": severity,
        "path": path,
        "message": message,
        "blocking": blocking,
    }


def _number(value, path: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be a finite number")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{path} exceeds the supported numeric range") from exc
    if not math.isfinite(number):
        raise ValueError(f"{path} must be a finite number")
    if positive and number <= 0.0 or nonnegative and number < 0.0:
        raise ValueError(f"{path} is outside the required numeric domain")
    return number


def _count(value, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{path} must be a nonnegative integer")
    return value


def _physical_model_metadata(model: dict, path: str) -> None:
    source = model.get("source")
    structured_source = (
        isinstance(source, dict)
        and any(isinstance(value, str) and value.strip() for value in source.values())
    )
    if not ((isinstance(source, str) and source.strip()) or structured_source):
        raise ValueError(f"{path}.source must be a non-empty string or object")
    estimate = model.get("estimate")
    if not isinstance(estimate, bool):
        raise ValueError(f"{path}.estimate must be boolean")
    inputs = model.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError(f"{path}.inputs must be an object")
    if not estimate:
        return
    provenance = model.get("input_provenance")
    if not isinstance(provenance, dict) or not provenance:
        raise ValueError(f"{path}.input_provenance is required for an estimated model")
    missing = sorted(set(inputs or {}) - set(provenance))
    if missing:
        raise ValueError(f"{path}.input_provenance is missing inputs {missing!r}")
    for key in inputs:
        declared = provenance[key]
        if not isinstance(declared, dict):
            raise ValueError(f"{path}.input_provenance.{key} must be an object")
        declared_source = declared.get("source")
        if not isinstance(declared_source, str) or not declared_source.strip():
            raise ValueError(f"{path}.input_provenance.{key}.source must be non-empty")
        if not isinstance(declared.get("estimate"), bool):
            raise ValueError(f"{path}.input_provenance.{key}.estimate must be boolean")


def _declared_count(inputs: dict, system: dict, path: str) -> tuple[int, str]:
    has_field = "count_field" in inputs
    has_value = "count_value" in inputs
    if has_field == has_value:
        raise ValueError(f"{path} must declare exactly one of count_field or count_value")
    if has_value:
        basis = inputs.get("count_basis")
        if not isinstance(basis, str) or not basis:
            raise ValueError(f"{path}.count_basis is required with count_value")
        return _count(inputs["count_value"], f"{path}.count_value"), basis
    field = inputs["count_field"]
    if field not in ("installed_count", "installed_guns", "installed_tubes"):
        raise ValueError(
            f"{path}.count_field must name an installed count, never a broadside count"
        )
    return _count(system.get(field), f"{path}.{field}"), field


def _calculated_mass(model: dict, system: dict, path: str) -> tuple[float, str]:
    inputs = model.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError(f"{path}.inputs must be an object")
    method = model.get("method")
    if method == "volume_density_mass":
        volume = _number(inputs.get("volume_m3"), f"{path}.inputs.volume_m3", nonnegative=True)
        density = _number(inputs.get("density_kg_m3"), f"{path}.inputs.density_kg_m3", positive=True)
        return volume * density / 1000.0, "mass_t = volume_m3 × density_kg_m3 / 1000"
    if method == "plate_area_thickness_density_mass":
        area = _number(inputs.get("area_m2"), f"{path}.inputs.area_m2", nonnegative=True)
        thickness = _number(inputs.get("thickness_m"), f"{path}.inputs.thickness_m", nonnegative=True)
        density = _number(inputs.get("density_kg_m3"), f"{path}.inputs.density_kg_m3", positive=True)
        return area * thickness * density / 1000.0, (
            "mass_t = area_m2 × thickness_m × density_kg_m3 / 1000"
        )
    if method == "counted_unit_mass":
        unit_mass = _number(inputs.get("unit_mass_t"), f"{path}.inputs.unit_mass_t", nonnegative=True)
        count, basis = _declared_count(inputs, system, f"{path}.inputs")
        return unit_mass * count, f"mass_t = unit_mass_t × {basis}"
    if method == "counted_ammunition_mass":
        count, count_basis = _declared_count(inputs, system, f"{path}.inputs")
        rounds_field = inputs.get("rounds_field")
        if rounds_field != "rounds_per_gun":
            raise ValueError(f"{path}.inputs.rounds_field must be 'rounds_per_gun'")
        rounds = _count(system.get(rounds_field), f"{path}.{rounds_field}")
        projectile = _number(
            inputs.get("projectile_mass_kg"),
            f"{path}.inputs.projectile_mass_kg",
            nonnegative=True,
        )
        charge = _number(
            inputs.get("charge_mass_kg"),
            f"{path}.inputs.charge_mass_kg",
            nonnegative=True,
        )
        mass = count * rounds * (projectile + charge) / 1000.0
        return mass, (
            f"mass_t = {count_basis} × rounds_per_gun × "
            "(projectile_mass_kg + charge_mass_kg) / 1000"
        )
    if method == "empirical_estimate_v1":
        # A versioned concept estimate arrives in long tons because the recovered
        # methods are imperial. It is a model, never a ledger mass.
        estimate = _number(inputs.get("estimate_long_tons"),
                           f"{path}.inputs.estimate_long_tons", nonnegative=True)
        return estimate * 1016.0469088 / 1000.0, (
            "mass_t = estimate_long_tons x 1016.0469088 / 1000 "
            "(versioned empirical concept estimate, not a ledger mass)"
        )
    raise ValueError(f"{path}.method has unsupported value {method!r}")


def _system_leaves(systems: dict, prefix: str = "") -> list[tuple[str, dict]]:
    leaves = []
    for key, value in systems.items():
        identifier = f"{prefix}.{key}" if prefix else key
        if not isinstance(key, str) or not key:
            raise ValueError("system IDs must be non-empty strings")
        if not isinstance(value, dict):
            raise ValueError(f"$.systems.{identifier} must be an object")
        if any(field in value for field in ("weight_item_ids", "status", "mass_models")):
            leaves.append((identifier, value))
        else:
            leaves.extend(_system_leaves(value, identifier))
    return leaves


def _generated_from_project(project: dict, state: dict) -> tuple:
    """Compose the optional concept models, ignoring an unconfigured project.

    A project without ``concept_design`` keeps exactly its previous behaviour, and
    a configuration this stage cannot evaluate reports diagnostics rather than
    removing the existing physical models.
    """
    if not isinstance(project.get("concept_design"), dict):
        return {}, []
    try:
        from . import concept_design
    except ImportError:                                   # pragma: no cover - direct import
        import concept_design
    try:
        generated = concept_design.generated_models(project, state)
    except concept_design.ConceptDesignError as error:
        return {}, error.diagnostics
    return generated.get("systems", {}), generated.get("diagnostics", [])


def summary(project: dict, state: dict, generated_models: dict | None = None) -> dict:
    """Summarize system rows without changing authoritative loading masses.

    Args:
        project (dict): Canonical project containing an optional systems object.
        state (dict): Selected ``plimsoll-loading-1`` result.
        generated_models (dict, optional): Versioned concept models keyed by
            system ID, supplied by ``concept_design``. They are models, never
            ledger mass, and they never displace a declared model.

    Returns:
        (dict): Linked ledger masses, physical checks, proposals, and diagnostics.
    """
    if not isinstance(project, dict):
        raise ValueError("project must be an object")
    if not isinstance(state, dict) or state.get("schema") != "plimsoll-loading-1":
        raise ValueError("state must be a plimsoll-loading-1 result")
    declared = project.get("systems")
    if not isinstance(declared, dict):
        raise ValueError("project.systems must be an object")
    if generated_models is None:
        generated_models, concept_diagnostics = _generated_from_project(project, state)
    else:
        concept_diagnostics = []
    effective_items = state.get("effective_items")
    if not isinstance(effective_items, list):
        raise ValueError("state.effective_items must be an array")
    item_by_id = {}
    for item in effective_items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("state.effective_items contains an invalid row")
        item_by_id[item["id"]] = item

    diagnostics = []
    diagnostics.extend(copy.deepcopy(concept_diagnostics))
    loading_diagnostics = copy.deepcopy(state.get("diagnostics", []))
    if not state.get("complete_mass", False):
        diagnostics.append(
            _diagnostic(
                "systems.loading_incomplete",
                "error",
                "$.state",
                "The selected loading ledger is incomplete; system mass totals are unavailable.",
                True,
            )
        )
    rows = {}
    proposals = []
    owners: dict[str, list[str]] = {}
    unique_linked_ids = set()
    unknown_linked_mass = False

    system_leaves = _system_leaves(declared)
    if not system_leaves:
        diagnostics.append(
            _diagnostic(
                "systems.none_declared",
                "error",
                "$.systems",
                "No system rows are declared; absence must be explicit per system.",
                True,
            )
        )
    for system_id, system in system_leaves:
        path = f"$.systems.{system_id}"
        status = system.get("status", "present" if "weight_item_ids" in system else None)
        if status not in ("present", "absent"):
            raise ValueError(f"{path}.status must be 'present' or 'absent'")
        row = {
            "status": status,
            "source": copy.deepcopy(
                system.get("source", (system.get("raw_design_power") or {}).get("source"))
            ),
            "estimate": system.get("estimate"),
            "installed_count": None,
            "broadside_count": None,
            "linked_items": [],
            "ledger_mass_t": None,
            "mass_models": [],
        }
        if status == "absent":
            reason = system.get("reason")
            if not isinstance(reason, str) or not reason:
                raise ValueError(f"{path}.reason is required for an absent system")
            row["reason"] = reason
            rows[system_id] = row
            continue

        installed_field = next(
            (field for field in ("installed_count", "installed_guns", "installed_tubes") if field in system),
            None,
        )
        broadside_field = next(
            (field for field in ("broadside_count", "broadside_guns") if field in system),
            None,
        )
        if installed_field:
            row["installed_count"] = _count(system[installed_field], f"{path}.{installed_field}")
            row["installed_count_field"] = installed_field
        if broadside_field:
            row["broadside_count"] = _count(system[broadside_field], f"{path}.{broadside_field}")
            row["broadside_count_field"] = broadside_field
        weight_item_ids = system.get("weight_item_ids")
        if not isinstance(weight_item_ids, list):
            raise ValueError(f"{path}.weight_item_ids must be an array")
        seen_here = set()
        known_mass = 0.0
        row_complete = True
        if not weight_item_ids:
            diagnostics.append(
                _diagnostic(
                    "systems.present_without_weight_items",
                    "error",
                    f"{path}.weight_item_ids",
                    "A present system must own at least one selected-ledger weight item; "
                    "use status='absent' for an explicit absence.",
                    True,
                )
            )
            row_complete = False
        for item_id in weight_item_ids:
            if not isinstance(item_id, str) or not item_id:
                raise ValueError(f"{path}.weight_item_ids must contain non-empty strings")
            if item_id in seen_here:
                diagnostics.append(
                    _diagnostic(
                        "systems.weight_item_duplicate",
                        "error",
                        f"{path}.weight_item_ids",
                        f"Weight item {item_id!r} is repeated within system {system_id!r}.",
                        True,
                    )
                )
                row_complete = False
                continue
            seen_here.add(item_id)
            owners.setdefault(item_id, []).append(system_id)
            item = item_by_id.get(item_id)
            if item is None:
                diagnostics.append(
                    _diagnostic(
                        "systems.weight_item_unknown",
                        "error",
                        f"{path}.weight_item_ids",
                        f"Weight item {item_id!r} is not in the selected loading ledger.",
                        True,
                    )
                )
                row_complete = False
                continue
            unique_linked_ids.add(item_id)
            mass = item.get("mass_t")
            linked = {
                "id": item_id,
                "mass_t": mass,
                "includes": copy.deepcopy(item.get("includes", [])),
                "provenance": copy.deepcopy(
                    item.get("provenance", {"source": item.get("source"), "estimate": item.get("estimate")})
                ),
            }
            row["linked_items"].append(linked)
            if mass is None:
                row_complete = False
                unknown_linked_mass = True
                diagnostics.append(
                    _diagnostic(
                        "systems.weight_mass_unknown",
                        "error",
                        f"{path}.weight_item_ids",
                        f"Weight item {item_id!r} has unknown effective mass.",
                        True,
                    )
                )
            else:
                known_mass += _number(mass, f"state.effective_items[{item_id}].mass_t", nonnegative=True)
        row["ledger_known_mass_t"] = known_mass
        row["ledger_mass_t"] = known_mass if row_complete else None

        mass_models = system.get("mass_models", [])
        if not isinstance(mass_models, list):
            raise ValueError(f"{path}.mass_models must be an array")
        mass_models = list(mass_models)
        generated = (generated_models or {}).get(system_id, [])
        model_ids = {model["id"] for model in mass_models if isinstance(model, dict)}
        usable = []
        for model in generated:
            if model["id"] in model_ids:
                diagnostics.append(
                    _diagnostic(
                        "systems.generated_model_duplicate",
                        "error",
                        f"{path}.mass_models",
                        f"Generated model {model['id']!r} collides with a declared model ID; "
                        "generated and user model IDs must be distinct.",
                        True,
                    )
                )
                continue
            usable.append(model)
        # A physical and an empirical model may compare the same item; both stay
        # visible and neither becomes the mass authority.
        mass_models = mass_models + usable
        seen_model_ids = set()
        for model_index, model in enumerate(mass_models):
            model_path = f"{path}.mass_models[{model_index}]"
            if not isinstance(model, dict) or not isinstance(model.get("id"), str):
                raise ValueError(f"{model_path} must have a string id")
            if model["id"] in seen_model_ids:
                raise ValueError(f"{model_path}.id is duplicated")
            seen_model_ids.add(model["id"])
            linked_id = model.get("linked_weight_item_id")
            if linked_id not in seen_here:
                raise ValueError(f"{model_path}.linked_weight_item_id must be linked by this system")
            _physical_model_metadata(model, model_path)
            calculated, formula = _calculated_mass(model, system, model_path)
            linked_item = item_by_id.get(linked_id)
            ledger_mass = linked_item.get("mass_t") if linked_item else None
            comparison = model.get("comparison_tolerance")
            if not isinstance(comparison, dict):
                raise ValueError(f"{model_path}.comparison_tolerance must be an object")
            relative = _number(comparison.get("relative"), f"{model_path}.comparison_tolerance.relative",
                               nonnegative=True)
            absolute = _number(comparison.get("absolute_t"),
                               f"{model_path}.comparison_tolerance.absolute_t", nonnegative=True)
            difference = None if ledger_mass is None else calculated - ledger_mass
            tolerance = None if ledger_mass is None else max(absolute, relative * abs(ledger_mass))
            check = {
                "id": model["id"],
                "method": model["method"],
                "formula": formula,
                "inputs": copy.deepcopy(model["inputs"]),
                "linked_weight_item_id": linked_id,
                "ledger_mass_t": ledger_mass,
                "calculated_mass_t": calculated,
                "difference_t": difference,
                "comparison_tolerance_t": tolerance,
                "source": copy.deepcopy(model.get("source")),
                "estimate": model.get("estimate"),
                "boundary": model.get("boundary"),
                "input_provenance": copy.deepcopy(model.get("input_provenance")),
                "comparison_policy": model.get("comparison_policy"),
            }
            for key in ("concept_component", "concept_battery_id", "capacity_display_factor",
                        "capacity_note", "note", "inversion",
                        "component_breakdown", "guns_in_mount_selector", "assumptions"):
                if key in model:
                    check[key] = copy.deepcopy(model[key])
            if model.get("concept_component") == "fuel":
                check["capacity_estimate_t"] = calculated * model["capacity_display_factor"]
            row["mass_models"].append(check)
            # An unknown target is a legitimate proposal: the current mass and the
            # difference stay null and the review decides.
            if difference is None or abs(difference) > tolerance:
                if difference is not None:
                    diagnostics.append(
                        _diagnostic(
                            "systems.mass_mismatch",
                            "warning",
                            model_path,
                            f"Declared model {model['id']!r} differs from ledger item {linked_id!r} by {difference} t.",
                        )
                    )
                proposals.append(
                    {
                        "operation": "replace_weight_item_mass",
                        "item_id": linked_id,
                        "current_mass_t": ledger_mass,
                        "proposed_mass_t": calculated,
                        "difference_t": difference,
                        "source_system_id": system_id,
                        "source_model_id": model["id"],
                        "requires_review": True,
                        "reason": ("A declared model estimates a value for an unknown target mass."
                                   if difference is None else
                                   "A declared formula differs from the selected ledger mass."),
                    }
                )
        rows[system_id] = row

    shared_ids = set()
    for item_id, system_ids in owners.items():
        if len(system_ids) > 1:
            shared_ids.add(item_id)
            diagnostics.append(
                _diagnostic(
                    "systems.weight_item_shared",
                    "error",
                    "$.systems",
                    f"Weight item {item_id!r} is linked by multiple systems {system_ids!r}.",
                    True,
                )
            )

    linked_known_mass = sum(
        _number(item_by_id[item_id]["mass_t"], f"state.effective_items[{item_id}].mass_t", nonnegative=True)
        for item_id in unique_linked_ids
        if item_by_id[item_id].get("mass_t") is not None
    )
    blocking = any(diagnostic["blocking"] for diagnostic in diagnostics)
    complete = not blocking and not unknown_linked_mass and state.get("complete_mass", False)
    return {
        "schema": SCHEMA,
        "project_id": state.get("project_id", project.get("id")),
        "condition_id": state.get("condition_id"),
        "project_fingerprint": state.get("project_fingerprint"),
        "input_fingerprint": state.get("input_fingerprint"),
        "mass_authority": "selected_loading_weight_ledger",
        "complete": complete,
        "systems": rows,
        "values": {
            "linked_known_mass_t": linked_known_mass,
            "linked_total_mass_t": linked_known_mass if complete else None,
            "linked_item_count": len(unique_linked_ids),
        },
        "update_proposals": proposals,
        "diagnostics": diagnostics,
        "loading_diagnostics": loading_diagnostics,
        "provenance": {
            "selected_condition": state.get("condition_id"),
            "source_system_count": len(system_leaves),
            "shared_weight_item_ids": sorted(shared_ids),
        },
    }
