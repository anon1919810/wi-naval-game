"""Resolve canonical loading conditions into three-axis mass properties."""

from __future__ import annotations

import copy
import hashlib
import json
import math

try:
    from . import project_io
except ImportError:  # Preserve the repository's direct-module import convention.
    import project_io


SCHEMA = "plimsoll-loading-1"
_AXIS_FIELDS = {"x": "x_m", "y": "y_m", "z": "kg_m"}
_CG_FIELDS = {"x": "lcg_m", "y": "tcg_m", "z": "kg_m"}


def _diagnostic(
    code: str,
    severity: str,
    path: str,
    message: str,
    *,
    blocking: bool = False,
) -> dict:
    return {
        "code": code,
        "severity": severity,
        "path": path,
        "message": message,
        "blocking": blocking,
    }


class LoadingConditionError(ValueError):
    """Report an unknown requested loading condition with a diagnostic."""

    def __init__(self, condition_id: object):
        """Initialize the error for the requested identifier.

        Args:
            condition_id (object): Requested loading-condition identifier.
        """
        self.diagnostics = [
            _diagnostic(
                "loading.condition_unknown",
                "error",
                "$.loading_conditions",
                f"unknown loading condition {condition_id!r}",
                blocking=True,
            )
        ]
        super().__init__(self.diagnostics[0]["message"])


def _result_fingerprint(project_fingerprint: str, condition_id: str) -> str:
    encoded = json.dumps(
        {"condition_id": condition_id, "project_fingerprint": project_fingerprint},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class LoadingRangeError(ValueError):
    """Finite input fields produced an unrepresentable ledger quantity."""


def _finite_derived(value, path):
    if not math.isfinite(value):
        raise LoadingRangeError(f"loading arithmetic is outside the numeric range at {path}")
    return value


def _summarize(items: list[dict]) -> dict:
    known_mass = 0.0
    mass_complete = True
    known_moments = {axis: 0.0 for axis in _AXIS_FIELDS}
    axis_complete = {axis: True for axis in _AXIS_FIELDS}
    for item in items:
        mass = item["mass_t"]
        if mass is None:
            mass_complete = False
            axis_complete = {axis: False for axis in _AXIS_FIELDS}
            continue
        known_mass = _finite_derived(known_mass+mass, 'total_mass_t')
        if mass == 0:
            continue
        for axis, field in _AXIS_FIELDS.items():
            position = item[field]
            if position is None:
                axis_complete[axis] = False
            else:
                contribution = _finite_derived(mass*position, f"item.{item['id']}.{field}.moment")
                known_moments[axis] = _finite_derived(known_moments[axis]+contribution, axis+'.moment_sum')

    total_mass = known_mass if mass_complete else None
    moments = {
        axis: known_moments[axis] if mass_complete and complete else None
        for axis, complete in axis_complete.items()
    }
    cgs = {
        _CG_FIELDS[axis]: (
            _finite_derived(moments[axis] / total_mass, axis+'.cg')
            if moments[axis] is not None and total_mass is not None and total_mass > 0
            else None
        )
        for axis in _AXIS_FIELDS
    }
    return {
        "known_mass_t": known_mass,
        "total_mass_t": total_mass,
        "known_moments_t_m": known_moments,
        "moments_t_m": moments,
        "axis_complete": axis_complete,
        **cgs,
    }


def _ownership_diagnostics(items: list[dict]) -> list[dict]:
    owners: dict[str, list[str]] = {}
    for item in items:
        if item["mass_t"] == 0:
            continue
        tokens = {item["id"], *item.get("includes", [])}
        for token in tokens:
            owners.setdefault(token, []).append(item["id"])
    diagnostics = []
    for token, item_ids in sorted(owners.items()):
        if len(item_ids) > 1:
            diagnostics.append(
                _diagnostic(
                    "loading.ownership_overlap",
                    "error",
                    "$.weight_groups",
                    f"active items {item_ids!r} both own component token {token!r}",
                    blocking=True,
                )
            )
    return diagnostics


def _coverage(reference: float | None, total_mass: float | None) -> tuple[dict, list[dict]]:
    result = {
        "reference_displacement_t": reference,
        "ratio": None,
        "percent": None,
        "unallocated_mass_t": None,
    }
    diagnostics = []
    if reference is None or total_mass is None:
        return result, diagnostics
    result["unallocated_mass_t"] = reference - total_mass
    if reference == 0:
        if total_mass > 0:
            diagnostics.append(
                _diagnostic(
                    "loading.coverage_reference_zero",
                    "warning",
                    "$.loading_conditions",
                    "coverage ratio is undefined for a zero reference displacement",
                )
            )
        return result, diagnostics
    result["ratio"] = _finite_derived(total_mass / reference, 'coverage.ratio')
    result["percent"] = _finite_derived(100.0 * result["ratio"], 'coverage.percent')
    if result["ratio"] < 0.95:
        diagnostics.append(
            _diagnostic(
                "loading.coverage_low",
                "warning",
                "$.loading_conditions",
                "modeled mass is below 95% of the selected reference displacement",
            )
        )
    elif result["ratio"] > 1.05:
        diagnostics.append(
            _diagnostic(
                "loading.coverage_high",
                "warning",
                "$.loading_conditions",
                "modeled mass is above 105% of the selected reference displacement",
            )
        )
    return result, diagnostics


def _multiply_intervals(first: list[float], second: list[float]) -> list[float]:
    products = [
        first[0] * second[0],
        first[0] * second[1],
        first[1] * second[0],
        first[1] * second[1],
    ]
    for value in products:
        _finite_derived(value, 'uncertainty.moment_product')
    return [min(products), max(products)]


def _divide_intervals(numerator: list[float], denominator: list[float]) -> list[float]:
    quotients = [
        numerator[0] / denominator[0],
        numerator[0] / denominator[1],
        numerator[1] / denominator[0],
        numerator[1] / denominator[1],
    ]
    for value in quotients:
        _finite_derived(value, 'uncertainty.cg_quotient')
    return [min(quotients), max(quotients)]


def _source_unknown(source):
    return not ((isinstance(source, str) and source.strip())
                or (isinstance(source, dict) and source))


def _provenance_summary(items: list[dict]) -> dict:
    def missing_source(item):
        return any(_source_unknown(field.get("source"))
                   for field in item["provenance"]["fields"].values())

    def unknown_estimate(item):
        return any(field.get("estimate") is None for field in item["provenance"]["fields"].values())

    source_missing = [
        item["id"] for item in items if missing_source(item)
    ]
    estimate_counts = {
        "estimated": sum(item["estimate"] is True for item in items),
        "confirmed_non_estimated": sum(item["estimate"] is False for item in items),
        "unknown": sum(item["estimate"] is None for item in items),
    }
    unverified = [
        item["id"]
        for item in items
        if missing_source(item) or unknown_estimate(item)
    ]
    return {
        "item_count": len(items),
        "sourced_item_count": len(items) - len(source_missing),
        "source_missing_item_ids": source_missing,
        "estimate_counts": estimate_counts,
        "contains_estimates": estimate_counts["estimated"] > 0,
        "unverified_item_ids": unverified,
        "provenance_complete": not unverified,
    }


def _uncertainty_summary(
    items: list[dict],
    item_paths: dict[str, str],
    *,
    semantic_block: bool,
) -> tuple[dict, list[dict]]:
    conditional_fields: list[str] = []
    missing_estimate_bounds = []
    mass_interval = [0.0, 0.0]
    mass_complete = True
    moment_intervals = {axis: [0.0, 0.0] for axis in _AXIS_FIELDS}
    moment_complete = {axis: True for axis in _AXIS_FIELDS}
    diagnostics = []

    for item in items:
        item_path = item_paths[item["id"]]
        uncertainty = item.get("uncertainty", {})
        mass = item["mass_t"]
        if mass is None:
            mass_complete = False
            moment_complete = {axis: False for axis in _AXIS_FIELDS}
            continue
        if "mass_t" in uncertainty:
            item_mass_interval = list(uncertainty["mass_t"])
        else:
            item_mass_interval = [mass, mass]
            conditional_fields.append(f"{item_path}.mass_t")
        mass_interval[0] = _finite_derived(mass_interval[0]+item_mass_interval[0], 'uncertainty.mass_lower')
        mass_interval[1] = _finite_derived(mass_interval[1]+item_mass_interval[1], 'uncertainty.mass_upper')

        missing_fields = []
        if item["provenance"]["fields"]["mass_t"]["estimate"] is True and "mass_t" not in uncertainty:
            missing_fields.append("mass_t")
        for axis, field in _AXIS_FIELDS.items():
            if item_mass_interval[1] == 0:
                continue
            position = item[field]
            if position is None:
                moment_complete[axis] = False
                continue
            if field in uncertainty:
                position_interval = list(uncertainty[field])
            else:
                position_interval = [position, position]
                conditional_fields.append(f"{item_path}.{field}")
                if item["provenance"]["fields"][field]["estimate"] is True:
                    missing_fields.append(field)
            contribution = _multiply_intervals(item_mass_interval, position_interval)
            moment_intervals[axis][0] = _finite_derived(moment_intervals[axis][0]+contribution[0], 'uncertainty.'+axis+'.lower')
            moment_intervals[axis][1] = _finite_derived(moment_intervals[axis][1]+contribution[1], 'uncertainty.'+axis+'.upper')
        if missing_fields:
            missing_fields.sort()
            missing_estimate_bounds.append(
                {"item_id": item["id"], "fields": missing_fields}
            )
            diagnostics.append(
                _diagnostic(
                    "loading.estimated_without_uncertainty",
                    "warning",
                    item_path,
                    f"estimated item {item['id']!r} lacks uncertainty bounds for {missing_fields!r}",
                )
            )

    if not mass_complete or semantic_block:
        total_interval = None
        output_moments = {axis: None for axis in _AXIS_FIELDS}
    else:
        total_interval = mass_interval
        output_moments = {
            axis: moment_intervals[axis] if complete else None
            for axis, complete in moment_complete.items()
        }
    cg_intervals = {axis: None for axis in _AXIS_FIELDS}
    if total_interval is not None and total_interval[0] > 0:
        cg_intervals = {
            axis: (
                _divide_intervals(interval, total_interval)
                if interval is not None
                else None
            )
            for axis, interval in output_moments.items()
        }
    elif total_interval is not None:
        diagnostics.append(
            _diagnostic(
                "loading.uncertainty_mass_not_strictly_positive",
                "warning",
                "$.weight_groups",
                "CG intervals require a strictly positive lower total-mass bound",
                blocking=True,
            )
        )

    summary = {
        "kind": "conservative_engineering_interval",
        "is_confidence_interval": False,
        "method": (
            "independent interval arithmetic over nonnegative mass and signed position bounds; "
            "correlation is not retained and intervals may overbound"
        ),
        "total_mass_t": total_interval,
        "moments_t_m": output_moments,
        "cg_m": cg_intervals,
        "conditional_on_nominal_fields": sorted(set(conditional_fields)),
        "missing_estimate_bounds": missing_estimate_bounds,
        "certified": total_interval is not None
        and all(interval is not None for interval in cg_intervals.values())
        and not missing_estimate_bounds,
    }
    return summary, diagnostics


def resolve_loading(project: dict, condition_id: str) -> dict:
    """Apply one condition and synthesize full three-axis mass properties.

    Args:
        project (dict): Canonical ``plimsoll-project-1`` input.
        condition_id (str): Existing loading-condition identifier.

    Returns:
        (dict): Derived ``plimsoll-loading-1`` loading state.

    Raises:
        ProjectValidationError: If project input is malformed.
        LoadingConditionError: If condition_id is not present.
    """
    normalized = project_io.normalize_project(project)
    condition = next(
        (entry for entry in normalized["loading_conditions"] if entry["id"] == condition_id),
        None,
    )
    if condition is None:
        raise LoadingConditionError(condition_id)
    condition_index = normalized["loading_conditions"].index(condition)
    definition = condition.get("definition")
    if definition is not None:
        # A validated one-level rule inherits the selected base's overrides,
        # then removes only the explicitly named items. No category is guessed.
        base = next(c for c in normalized["loading_conditions"] if c["id"] == definition["base_condition_id"])
        condition = copy.deepcopy(condition)
        condition["overrides"] = copy.deepcopy(base["overrides"])
        condition["override_provenance"] = copy.deepcopy(base.get("override_provenance", {}))
        for item_id in definition["excluded_item_ids"]:
            condition["overrides"].setdefault(item_id, {})["mass_t"] = 0.0
            condition["override_provenance"].setdefault(item_id, {})["mass_t"] = {
                "source": copy.deepcopy(definition["source"]), "estimate": definition["estimate"]}

    diagnostics = copy.deepcopy(project_io.validate_project(normalized))
    effective_items = []
    item_paths = {}
    group_rows = []
    required_group_empty = False
    for group_index, group in enumerate(normalized["weight_groups"]):
        group_items = []
        if group["required"] and not group["items"]:
            required_group_empty = True
            diagnostics.append(
                _diagnostic(
                    "loading.required_group_empty",
                    "error",
                    f"$.weight_groups[{group_index}].items",
                    f"required weight group {group['id']!r} has no items",
                    blocking=True,
                )
            )
        for item_index, base_item in enumerate(group["items"]):
            item = copy.deepcopy(base_item)
            override = condition["overrides"].get(item["id"], {})
            field_provenance = {field: {"source": copy.deepcopy(item["source"]),
                                      "estimate": item["estimate"], "origin": "base"}
                                for field in ("mass_t", "x_m", "y_m", "kg_m")}
            declared_provenance = condition.get("override_provenance", {}).get(item["id"], {})
            override_path = (f"$.loading_conditions[{condition_index}].overrides"
                             f"[{json.dumps(item['id'], ensure_ascii=False)}]")
            for field, value in override.items():
                item[field] = value
                uncertainty = item.get("uncertainty")
                if isinstance(uncertainty, dict) and field in uncertainty:
                    del uncertainty[field]
                    diagnostics.append(
                        _diagnostic(
                            "loading.uncertainty_override_cleared",
                            "warning",
                            f"{override_path}.{field}",
                            "base uncertainty was cleared because the field was overridden; update uncertainty metadata",
                        )
                    )
                metadata = copy.deepcopy(declared_provenance.get(field, {}))
                metadata.setdefault("source", None)
                metadata.setdefault("estimate", None)
                metadata["origin"] = "selected_condition"
                field_provenance[field] = metadata
                if "uncertainty" in metadata:
                    item.setdefault("uncertainty", {})[field] = copy.deepcopy(metadata["uncertainty"])
                if _source_unknown(metadata["source"]) or metadata["estimate"] is None:
                    diagnostics.append(_diagnostic("loading.override_provenance_unknown", "warning",
                        f"{override_path}.{field}", "override has unknown field provenance; base source is not inherited"))
            estimates = [entry["estimate"] for entry in field_provenance.values()]
            item["estimate"] = True if True in estimates else None if None in estimates else False
            if override:
                item["source"] = {"fields": {field: copy.deepcopy(entry["source"])
                                             for field, entry in field_provenance.items()}}
            item["group_id"] = group["id"]
            item["group_label"] = group["label"]
            item["overridden_fields"] = sorted(override)
            item["provenance"] = {
                "source": copy.deepcopy(item["source"]),
                "estimate": item["estimate"],
                "fields": field_provenance,
            }
            group_items.append(item)
            effective_items.append(item)
            item_path = f"$.weight_groups[{group_index}].items[{item_index}]"
            item_paths[item["id"]] = item_path
            if item["mass_t"] is None:
                diagnostics.append(
                    _diagnostic(
                        "loading.mass_unknown",
                        "error",
                        f"{item_path}.mass_t",
                        f"effective mass for item {item['id']!r} is unknown",
                        blocking=True,
                    )
                )
            elif item["mass_t"] > 0:
                for axis, field in _AXIS_FIELDS.items():
                    if item[field] is None:
                        diagnostics.append(
                            _diagnostic(
                                "loading.position_unknown",
                                "warning",
                                f"{item_path}.{field}",
                                f"{axis}-axis position for positive-mass item {item['id']!r} is unknown",
                                blocking=True,
                            )
                        )

        summary = _summarize(group_items)
        group_rows.append(
            {
                "id": group["id"],
                "label": group["label"],
                "required": group["required"],
                "item_count": len(group_items),
                **summary,
                "complete_mass": summary["total_mass_t"] is not None
                and not (group["required"] and not group_items),
                "complete_cg": summary["total_mass_t"] is not None
                and summary["total_mass_t"] > 0
                and all(summary["axis_complete"].values()),
            }
        )

    ownership_diagnostics = _ownership_diagnostics(effective_items)
    diagnostics.extend(ownership_diagnostics)
    ownership_overlap = bool(ownership_diagnostics)
    summary = _summarize(effective_items)
    total_mass = None if required_group_empty else summary["total_mass_t"]
    complete_mass = total_mass is not None and not ownership_overlap
    axis_complete = {
        axis: complete_mass and complete
        for axis, complete in summary["axis_complete"].items()
    }
    moments = {
        axis: summary["known_moments_t_m"][axis] if complete else None
        for axis, complete in axis_complete.items()
    }
    values = {
        "known_mass_t": summary["known_mass_t"],
        "total_mass_t": total_mass,
        "known_moments_t_m": summary["known_moments_t_m"],
        "moments_t_m": moments,
    }
    for axis, cg_field in _CG_FIELDS.items():
        values[cg_field] = (
            moments[axis] / total_mass
            if moments[axis] is not None and total_mass is not None and total_mass > 0
            else None
        )

    if total_mass == 0:
        diagnostics.append(
            _diagnostic(
                "loading.zero_total_mass",
                "error",
                "$.weight_groups",
                "a zero-mass design has no defined centre of gravity and cannot float",
                blocking=True,
            )
        )
    coverage, coverage_diagnostics = _coverage(
        condition["reference_displacement_t"], total_mass
    )
    diagnostics.extend(coverage_diagnostics)
    uncertainty, uncertainty_diagnostics = _uncertainty_summary(
        effective_items,
        item_paths,
        semantic_block=required_group_empty or ownership_overlap,
    )
    diagnostics.extend(uncertainty_diagnostics)
    provenance = _provenance_summary(effective_items)
    uncertainty['certified'] = uncertainty['certified'] and provenance['provenance_complete']
    project_fingerprint = project_io.input_fingerprint(normalized)
    result = {
        "schema": SCHEMA,
        "project_id": normalized["id"],
        "condition_id": condition_id,
        "units": copy.deepcopy(normalized["units"]),
        "coordinates": copy.deepcopy(normalized["coordinates"]),
        "project_fingerprint": project_fingerprint,
        "input_fingerprint": _result_fingerprint(project_fingerprint, condition_id),
        "effective_items": effective_items,
        "groups": group_rows,
        "values": values,
        "coverage": coverage,
        "provenance": provenance,
        "uncertainty": uncertainty,
        "axis_complete": axis_complete,
        "complete_mass": complete_mass,
        "complete_cg": total_mass is not None
        and total_mass > 0
        and all(axis_complete.values()),
        "diagnostics": diagnostics,
    }
    if definition is not None:
        result["definition"] = dict(copy.deepcopy(definition), method="explicit_base_loading_item_exclusion_v1",
                                    boundary="user-defined subtraction study; no automatic SPS category deductions")
    return result
