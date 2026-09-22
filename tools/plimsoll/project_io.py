"""Canonical project creation, validation, migration, and fingerprinting."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any
import uuid

try:
    from . import units, project_extensions
except ImportError:  # Preserve the repository's direct-module import convention.
    import units
    import project_extensions


SCHEMA = "plimsoll-project-1"
DEFAULT_UNITS = {
    "length": "m",
    "mass": "t",
    "speed": "kn",
    "power": "kW",
    "angle": "deg",
}
DEFAULT_COORDINATES = {
    "x_positive": "forward",
    "x_origin": "midships",
    "y_positive": "starboard",
    "z_origin": "keel",
}
_TOP_LEVEL_DEFAULTS = {
    "revision": 0,
    "units": DEFAULT_UNITS,
    "coordinates": DEFAULT_COORDINATES,
    "hull": {},
    "geometry": None,
    "weight_groups": [],
    "loading_conditions": [],
    "systems": {},
    "compartments": [],
    "openings": [],
    "sources": {},
}
_NUMERIC_ITEM_FIELDS = ("mass_t", "x_m", "y_m", "kg_m")
_OVERRIDE_FIELDS = frozenset(_NUMERIC_ITEM_FIELDS)
_RESERVED_RESULT_FIELDS = frozenset(
    {"result", "results", "cache", "cache_key", "input_fingerprint"}
)


class ProjectValidationError(ValueError):
    """Report malformed canonical project input with structured diagnostics."""

    def __init__(self, diagnostics: list[dict]):
        """Initialize the error from one or more validation diagnostics.

        Args:
            diagnostics (list): Structured project validation diagnostics.
        """
        self.diagnostics = copy.deepcopy(diagnostics)
        errors = [item for item in diagnostics if item.get("severity") == "error"]
        detail = "; ".join(f"{item['path']}: {item['message']}" for item in errors[:3])
        super().__init__(f"project validation failed with {len(errors)} error(s): {detail}")


def _diagnostic(
    code: str,
    severity: str,
    path: str,
    message: str,
    *,
    blocking: bool | None = None,
) -> dict:
    return {
        "code": code,
        "severity": severity,
        "path": path,
        "message": message,
        "blocking": severity == "error" if blocking is None else blocking,
    }


def _is_finite_real(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _with_schema_defaults(payload: dict) -> dict:
    project = copy.deepcopy(payload)
    project.setdefault("schema", SCHEMA)
    if "opening_definition" not in project:
        project["opening_definition"] = (
            "unknown" if "openings" not in project else
            "legacy_ambiguous" if project["openings"] == [] else "supplied")
    for key, default in _TOP_LEVEL_DEFAULTS.items():
        project.setdefault(key, copy.deepcopy(default))

    if isinstance(project.get("units"), dict):
        for key, value in DEFAULT_UNITS.items():
            project["units"].setdefault(key, value)
    if isinstance(project.get("coordinates"), dict):
        for key, value in DEFAULT_COORDINATES.items():
            project["coordinates"].setdefault(key, value)

    groups = project.get("weight_groups")
    if isinstance(groups, list):
        for group in groups:
            if not isinstance(group, dict):
                continue
            group.setdefault("label", group.get("id"))
            group.setdefault("required", False)
            group.setdefault("items", [])
            if not isinstance(group["items"], list):
                continue
            for item in group["items"]:
                if not isinstance(item, dict):
                    continue
                for field in _NUMERIC_ITEM_FIELDS:
                    item.setdefault(field, None)
                item.setdefault("source", None)
                item.setdefault("estimate", None)

    conditions = project.get("loading_conditions")
    if isinstance(conditions, list):
        for condition in conditions:
            if not isinstance(condition, dict):
                continue
            condition.setdefault("label", condition.get("id"))
            condition.setdefault("reference_displacement_t", None)
            condition.setdefault("overrides", {})
    return project


def new_project(name: str, project_id: str | None = None) -> dict:
    """Create an editable empty canonical project draft.

    Args:
        name (str): Human-readable project name.
        project_id (str, optional): Stable caller-supplied project identifier.

    Returns:
        (dict): Independent project draft populated with schema defaults.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    if project_id is not None and (not isinstance(project_id, str) or not project_id.strip()):
        raise ValueError("project_id must be a non-empty string when supplied")
    return {
        "schema": SCHEMA,
        "id": project_id or str(uuid.uuid4()),
        "name": name,
        **copy.deepcopy(_TOP_LEVEL_DEFAULTS),
        "opening_definition": "unknown",
    }


def _validate_json_value(value: Any, path: str, diagnostics: list[dict]) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            diagnostics.append(
                _diagnostic("number.nonfinite", "error", path, "JSON numbers must be finite")
            )
        return
    if isinstance(value, list):
        for index, member in enumerate(value):
            _validate_json_value(member, f"{path}[{index}]", diagnostics)
        return
    if isinstance(value, dict):
        for key, member in value.items():
            if not isinstance(key, str):
                diagnostics.append(
                    _diagnostic(
                        "json.key_invalid", "error", path, "JSON object keys must be strings"
                    )
                )
                continue
            _validate_json_value(member, f"{path}.{key}", diagnostics)
        return
    diagnostics.append(
        _diagnostic(
            "json.value_invalid",
            "error",
            path,
            f"value of type {type(value).__name__} is not valid JSON input",
        )
    )


def _validate_identifier(value: Any, path: str, diagnostics: list[dict]) -> bool:
    if isinstance(value, str) and value.strip():
        return True
    diagnostics.append(
        _diagnostic("id.invalid", "error", path, "identifier must be a non-empty string")
    )
    return False


def _validate_optional_number(
    value: Any,
    path: str,
    diagnostics: list[dict],
    *,
    nonnegative: bool = False,
    unknown_warning: bool = False,
) -> None:
    if value is None:
        if unknown_warning:
            diagnostics.append(
                _diagnostic(
                    "value.unknown",
                    "warning",
                    path,
                    "value is unknown; downstream calculations must not substitute zero",
                    blocking=False,
                )
            )
        return
    if not _is_finite_real(value):
        diagnostics.append(
            _diagnostic("number.invalid", "error", path, "value must be a finite real number or null")
        )
    elif nonnegative and value < 0:
        diagnostics.append(
            _diagnostic("number.negative", "error", path, "value must be nonnegative")
        )


def _hull_numeric_key(key: str) -> bool:
    return key.endswith(("_m", "_t", "_kg_m3", "_kn", "_kW", "_deg")) or key in {
        "block_coeff",
        "waterplane_coeff",
        "roll_gyration_coeff",
    }


def _validate_hull(project: dict, diagnostics: list[dict]) -> None:
    hull = project.get("hull")
    if not isinstance(hull, dict):
        diagnostics.append(_diagnostic("hull.invalid", "error", "$.hull", "hull must be an object"))
        return
    dimensional_values = 0
    for key, value in hull.items():
        if not isinstance(key, str):
            continue
        if not _hull_numeric_key(key):
            continue
        path = f"$.hull.{key}"
        nonnegative = not key.startswith(("x_", "y_", "keel_offset"))
        _validate_optional_number(
            value,
            path,
            diagnostics,
            nonnegative=nonnegative,
            unknown_warning=True,
        )
        if _is_finite_real(value):
            dimensional_values += 1
    if dimensional_values == 0:
        diagnostics.append(
            _diagnostic(
                "draft.hull_incomplete",
                "warning",
                "$.hull",
                "draft has no known hull dimensions",
                blocking=False,
            )
        )


def _validate_geometry(project: dict, diagnostics: list[dict]) -> None:
    geometry = project.get("geometry")
    if geometry is None:
        diagnostics.append(
            _diagnostic(
                "draft.geometry_missing",
                "warning",
                "$.geometry",
                "geometry is not yet defined",
                blocking=False,
            )
        )
        return
    if not isinstance(geometry, dict):
        diagnostics.append(
            _diagnostic("geometry.invalid", "error", "$.geometry", "geometry must be an object or null")
        )
        return
    if not isinstance(geometry.get("kind"), str) or not geometry["kind"].strip():
        diagnostics.append(
            _diagnostic("geometry.kind_invalid", "error", "$.geometry.kind", "kind is required")
        )
    source = geometry.get("source")
    if source is None or source == "" or source == {}:
        diagnostics.append(
            _diagnostic(
                "source.missing",
                "warning",
                "$.geometry.source",
                "geometry has no source metadata",
                blocking=False,
            )
        )
    if not isinstance(geometry.get("estimate"), bool):
        diagnostics.append(
            _diagnostic(
                "estimate.invalid", "error", "$.geometry.estimate", "estimate must be boolean"
            )
        )
    _validate_optional_number(
        geometry.get("keel_offset_m"),
        "$.geometry.keel_offset_m",
        diagnostics,
        unknown_warning=True,
    )
    kind = geometry.get("kind")
    payload_field = {
        "offsets_reference": "reference",
        "parameters": "parameters",
        "offsets": "offsets",
    }.get(kind)
    if payload_field is None:
        diagnostics.append(
            _diagnostic(
                "geometry.kind_unsupported",
                "error",
                "$.geometry.kind",
                f"unsupported geometry kind {kind!r}",
            )
        )
        return
    mismatched = [
        field
        for field in ("offsets", "reference", "parameters")
        if field != payload_field and field in geometry
    ]
    if mismatched:
        diagnostics.append(
            _diagnostic(
                "geometry.payload_mismatched",
                "error",
                "$.geometry",
                f"geometry kind {kind!r} cannot use payload field(s) {mismatched!r}",
            )
        )
    payload = geometry.get(payload_field)
    payload_valid = False
    if kind == "offsets_reference":
        payload_valid = (
            isinstance(payload, dict)
            and isinstance(payload.get("path"), str)
            and bool(payload["path"].strip())
        )
    elif kind == "parameters":
        payload_valid = isinstance(payload, dict) and bool(payload)
    elif kind == "offsets":
        payload_valid = (
            isinstance(payload, dict)
            and isinstance(payload.get("stations"), list)
            and bool(payload["stations"])
        )
    if not payload_valid:
        diagnostics.append(
            _diagnostic(
                "geometry.payload_invalid",
                "error",
                f"$.geometry.{payload_field}",
                f"geometry kind {kind!r} requires a non-empty {payload_field} payload",
            )
        )


def _validate_uncertainty(item: dict, path: str, diagnostics: list[dict]) -> None:
    if "uncertainty" not in item:
        return
    uncertainty = item["uncertainty"]
    if not isinstance(uncertainty, dict):
        diagnostics.append(
            _diagnostic(
                "uncertainty.invalid", "error", f"{path}.uncertainty", "uncertainty must be an object"
            )
        )
        return
    for field, bounds in uncertainty.items():
        bounds_path = f"{path}.uncertainty.{field}"
        if field not in _NUMERIC_ITEM_FIELDS:
            diagnostics.append(
                _diagnostic(
                    "uncertainty.field_unknown",
                    "error",
                    bounds_path,
                    f"unsupported uncertainty field {field!r}",
                )
            )
            continue
        if (
            not isinstance(bounds, list)
            or len(bounds) != 2
            or not all(_is_finite_real(bound) for bound in bounds)
        ):
            diagnostics.append(
                _diagnostic(
                    "uncertainty.bounds_invalid",
                    "error",
                    bounds_path,
                    "bounds must be two finite real values [lower, upper]",
                )
            )
            continue
        lower, upper = bounds
        if lower > upper:
            diagnostics.append(
                _diagnostic(
                    "uncertainty.bounds_invalid",
                    "error",
                    bounds_path,
                    "lower bound must not exceed upper bound",
                )
            )
        if field in {"mass_t", "kg_m"} and lower < 0:
            diagnostics.append(
                _diagnostic(
                    "uncertainty.dimension",
                    "error",
                    bounds_path,
                    f"{field} uncertainty bounds must be nonnegative",
                )
            )
        nominal = item.get(field)
        if nominal is None or (_is_finite_real(nominal) and not lower <= nominal <= upper):
            diagnostics.append(
                _diagnostic(
                    "uncertainty.nominal_outside",
                    "error",
                    bounds_path,
                    "bounds must contain the known nominal value inclusively",
                )
            )


def _validate_includes(item: dict, path: str, diagnostics: list[dict]) -> None:
    if "includes" not in item:
        return
    includes = item["includes"]
    if not isinstance(includes, list):
        diagnostics.append(
            _diagnostic(
                "includes.invalid", "error", f"{path}.includes", "includes must be an array"
            )
        )
        return
    seen: set[str] = set()
    for index, token in enumerate(includes):
        token_path = f"{path}.includes[{index}]"
        if not isinstance(token, str) or not token.strip():
            diagnostics.append(
                _diagnostic(
                    "includes.token_invalid",
                    "error",
                    token_path,
                    "component ownership token must be a non-empty string",
                )
            )
        elif token in seen:
            diagnostics.append(
                _diagnostic(
                    "includes.token_duplicate",
                    "error",
                    token_path,
                    f"component ownership token {token!r} is repeated within the item",
                )
            )
        else:
            seen.add(token)


def _validate_weight_groups(project: dict, diagnostics: list[dict]) -> set[str]:
    groups = project.get("weight_groups")
    if not isinstance(groups, list):
        diagnostics.append(
            _diagnostic(
                "weight_groups.invalid", "error", "$.weight_groups", "weight_groups must be an array"
            )
        )
        return set()
    if not groups:
        diagnostics.append(
            _diagnostic(
                "draft.weight_groups_empty",
                "warning",
                "$.weight_groups",
                "draft has no weight groups",
                blocking=False,
            )
        )
    group_ids: set[str] = set()
    item_ids: set[str] = set()
    for group_index, group in enumerate(groups):
        group_path = f"$.weight_groups[{group_index}]"
        if not isinstance(group, dict):
            diagnostics.append(
                _diagnostic("group.invalid", "error", group_path, "weight group must be an object")
            )
            continue
        group_id = group.get("id")
        if _validate_identifier(group_id, f"{group_path}.id", diagnostics):
            if group_id in group_ids:
                diagnostics.append(
                    _diagnostic(
                        "group.id_duplicate",
                        "error",
                        f"{group_path}.id",
                        f"weight group id {group_id!r} is duplicated",
                    )
                )
            group_ids.add(group_id)
        if not isinstance(group.get("label"), str) or not group["label"].strip():
            diagnostics.append(
                _diagnostic("group.label_invalid", "error", f"{group_path}.label", "label is required")
            )
        if not isinstance(group.get("required"), bool):
            diagnostics.append(
                _diagnostic(
                    "group.required_invalid",
                    "error",
                    f"{group_path}.required",
                    "required must be boolean",
                )
            )
        items = group.get("items")
        if not isinstance(items, list):
            diagnostics.append(
                _diagnostic("items.invalid", "error", f"{group_path}.items", "items must be an array")
            )
            continue
        if group.get("required") and not items:
            diagnostics.append(
                _diagnostic(
                    "group.required_empty",
                    "warning",
                    f"{group_path}.items",
                    "required group has no weight items",
                    blocking=False,
                )
            )
        for item_index, item in enumerate(items):
            item_path = f"{group_path}.items[{item_index}]"
            if not isinstance(item, dict):
                diagnostics.append(
                    _diagnostic("item.invalid", "error", item_path, "weight item must be an object")
                )
                continue
            item_id = item.get("id")
            if _validate_identifier(item_id, f"{item_path}.id", diagnostics):
                if item_id in item_ids:
                    diagnostics.append(
                        _diagnostic(
                            "item.id_duplicate",
                            "error",
                            f"{item_path}.id",
                            f"weight item id {item_id!r} is duplicated across groups",
                        )
                    )
                item_ids.add(item_id)
            for field in _NUMERIC_ITEM_FIELDS:
                _validate_optional_number(
                    item.get(field),
                    f"{item_path}.{field}",
                    diagnostics,
                    nonnegative=field in {"mass_t", "kg_m"},
                    unknown_warning=True,
                )
            source = item.get("source")
            if source is None or source == "" or source == {}:
                diagnostics.append(
                    _diagnostic(
                        "source.missing",
                        "warning",
                        f"{item_path}.source",
                        "weight item has no source metadata",
                        blocking=False,
                    )
                )
            estimate = item.get("estimate")
            if estimate is None:
                diagnostics.append(
                    _diagnostic(
                        "estimate.unknown",
                        "warning",
                        f"{item_path}.estimate",
                        "weight item estimate provenance is unknown",
                        blocking=False,
                    )
                )
            elif not isinstance(estimate, bool):
                diagnostics.append(
                    _diagnostic(
                        "estimate.invalid",
                        "error",
                        f"{item_path}.estimate",
                        "estimate must be boolean",
                    )
                )
            _validate_uncertainty(item, item_path, diagnostics)
            _validate_includes(item, item_path, diagnostics)
    return item_ids


def _validate_loading_conditions(
    project: dict, item_ids: set[str], diagnostics: list[dict]
) -> None:
    conditions = project.get("loading_conditions")
    if not isinstance(conditions, list):
        diagnostics.append(
            _diagnostic(
                "loading_conditions.invalid",
                "error",
                "$.loading_conditions",
                "loading_conditions must be an array",
            )
        )
        return
    if not conditions:
        diagnostics.append(
            _diagnostic(
                "draft.loading_conditions_empty",
                "warning",
                "$.loading_conditions",
                "draft has no loading conditions",
                blocking=False,
            )
        )
    loading_ids: set[str] = set()
    for index, condition in enumerate(conditions):
        path = f"$.loading_conditions[{index}]"
        if not isinstance(condition, dict):
            diagnostics.append(
                _diagnostic("loading.invalid", "error", path, "loading condition must be an object")
            )
            continue
        condition_id = condition.get("id")
        if _validate_identifier(condition_id, f"{path}.id", diagnostics):
            if condition_id in loading_ids:
                diagnostics.append(
                    _diagnostic(
                        "loading.id_duplicate",
                        "error",
                        f"{path}.id",
                        f"loading condition id {condition_id!r} is duplicated",
                    )
                )
            loading_ids.add(condition_id)
        if not isinstance(condition.get("label"), str) or not condition["label"].strip():
            diagnostics.append(
                _diagnostic("loading.label_invalid", "error", f"{path}.label", "label is required")
            )
        _validate_optional_number(
            condition.get("reference_displacement_t"),
            f"{path}.reference_displacement_t",
            diagnostics,
            nonnegative=True,
            unknown_warning=True,
        )
        overrides = condition.get("overrides")
        if not isinstance(overrides, dict):
            diagnostics.append(
                _diagnostic("overrides.invalid", "error", f"{path}.overrides", "overrides must be an object")
            )
            continue
        for item_id, override in overrides.items():
            override_path = f"{path}.overrides[{json.dumps(item_id, ensure_ascii=False)}]"
            if item_id not in item_ids:
                diagnostics.append(
                    _diagnostic(
                        "override.item_unknown",
                        "error",
                        override_path,
                        f"override references unknown weight item {item_id!r}",
                    )
                )
            if not isinstance(override, dict):
                diagnostics.append(
                    _diagnostic(
                        "override.invalid", "error", override_path, "item override must be an object"
                    )
                )
                continue
            for field, value in override.items():
                field_path = f"{override_path}.{field}"
                if field not in _OVERRIDE_FIELDS:
                    diagnostics.append(
                        _diagnostic(
                            "override.field_unknown",
                            "error",
                            field_path,
                            f"unsupported override field {field!r}",
                        )
                    )
                    continue
                _validate_optional_number(
                    value,
                    field_path,
                    diagnostics,
                    nonnegative=field in {"mass_t", "kg_m"},
                )
        _validate_override_provenance(condition, path, diagnostics)


def _validate_override_provenance(condition, path, diagnostics):
    metadata = condition.get("override_provenance", {})
    path += ".override_provenance"
    if not isinstance(metadata, dict):
        diagnostics.append(_diagnostic("override_provenance.invalid", "error", path, "must be an object"))
        return
    for item_id, fields in metadata.items():
        item_path = f"{path}[{json.dumps(item_id, ensure_ascii=False)}]"
        override = condition["overrides"].get(item_id)
        if not isinstance(override, dict) or not isinstance(fields, dict):
            diagnostics.append(_diagnostic("override_provenance.orphan", "error", item_path,
                                           "metadata requires a matching item override and field object"))
            continue
        for field, entry in fields.items():
            field_path = f"{item_path}.{field}"
            if field not in override or field not in _OVERRIDE_FIELDS or not isinstance(entry, dict):
                diagnostics.append(_diagnostic("override_provenance.orphan", "error", field_path,
                                               "metadata requires a matching numeric override"))
                continue
            for key in entry.keys() - {"source", "estimate", "uncertainty", "acceptance"}:
                diagnostics.append(_diagnostic("override_provenance.field_unknown", "error",
                    field_path + "." + str(key), "unsupported field provenance property"))
            if entry.get("source") is not None and not isinstance(entry["source"], (str, dict)):
                diagnostics.append(_diagnostic("source.invalid", "error", field_path + ".source",
                                               "source must be string, object or null"))
            if entry.get("estimate") is not None and not isinstance(entry["estimate"], bool):
                diagnostics.append(_diagnostic("estimate.invalid", "error", field_path + ".estimate",
                                               "estimate must be boolean or null"))
            if "uncertainty" in entry:
                _validate_uncertainty({field: override[field], "uncertainty": {field: entry["uncertainty"]}},
                                      field_path, diagnostics)
            if "acceptance" in entry:
                diagnostics.extend(project_extensions.validate_acceptance(
                    entry["acceptance"], condition.get("id"), field, override[field], field_path + ".acceptance"))


def validate_project(payload: Any) -> list[dict]:
    """Validate a canonical project and return structured diagnostics.

    Args:
        payload (Any): Candidate canonical project object.

    Returns:
        (list): Diagnostics with code, severity, path, message, and blocking.
    """
    if not isinstance(payload, dict):
        return [
            _diagnostic("project.invalid", "error", "$", "project payload must be an object")
        ]
    project = _with_schema_defaults(payload)
    diagnostics: list[dict] = []
    _validate_json_value(project, "$", diagnostics)
    if project.get("schema") != SCHEMA:
        diagnostics.append(
            _diagnostic(
                "schema.unsupported",
                "error",
                "$.schema",
                f"schema must be {SCHEMA!r}; received {project.get('schema')!r}",
            )
        )
    _validate_identifier(project.get("id"), "$.id", diagnostics)
    if not isinstance(project.get("name"), str) or not project["name"].strip():
        diagnostics.append(
            _diagnostic("name.invalid", "error", "$.name", "name must be a non-empty string")
        )
    revision = project.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        diagnostics.append(
            _diagnostic(
                "revision.invalid", "error", "$.revision", "revision must be a nonnegative integer"
            )
        )
    units_value = project.get("units")
    if not isinstance(units_value, dict):
        diagnostics.append(_diagnostic("units.invalid", "error", "$.units", "units must be an object"))
    else:
        for key, expected in DEFAULT_UNITS.items():
            if units_value.get(key) != expected:
                diagnostics.append(
                    _diagnostic(
                        "units.noncanonical",
                        "error",
                        f"$.units.{key}",
                        f"canonical {key} unit must be {expected!r}",
                    )
                )
    coordinates = project.get("coordinates")
    if not isinstance(coordinates, dict):
        diagnostics.append(
            _diagnostic("coordinates.invalid", "error", "$.coordinates", "coordinates must be an object")
        )
    else:
        for key, expected in DEFAULT_COORDINATES.items():
            if coordinates.get(key) != expected:
                diagnostics.append(
                    _diagnostic(
                        "coordinates.noncanonical",
                        "error",
                        f"$.coordinates.{key}",
                        f"canonical coordinate value must be {expected!r}",
                    )
                )
    for field in _RESERVED_RESULT_FIELDS.intersection(project):
        diagnostics.append(
            _diagnostic(
                "project.result_field_reserved",
                "error",
                f"$.{field}",
                "stored results and cache keys are outside canonical project input",
            )
        )
    _validate_hull(project, diagnostics)
    _validate_geometry(project, diagnostics)
    item_ids = _validate_weight_groups(project, diagnostics)
    _validate_loading_conditions(project, item_ids, diagnostics)
    definition = project.get("opening_definition")
    if definition not in ("unknown", "supplied", "legacy_ambiguous"):
        diagnostics.append(_diagnostic("openings.definition_invalid", "error", "$.opening_definition",
                                       "opening_definition must be unknown, supplied or legacy_ambiguous"))
    elif definition != "supplied" and project.get("openings") != []:
        diagnostics.append(_diagnostic("openings.definition_conflict", "error", "$.opening_definition",
                                       "unknown or ambiguous definitions require an empty openings array"))
    elif definition != "supplied":
        diagnostics.append(_diagnostic("openings." + definition, "warning", "$.opening_definition",
            "opening knowledge is unknown" if definition == "unknown" else
            "legacy empty openings have ambiguous origin; explicitly declare supplied to mean none"))
    for field, expected_type in (
        ("systems", dict),
        ("compartments", list),
        ("openings", list),
        ("sources", dict),
    ):
        if not isinstance(project.get(field), expected_type):
            diagnostics.append(
                _diagnostic(
                    f"{field}.invalid",
                    "error",
                    f"$.{field}",
                    f"{field} must be a JSON {expected_type.__name__}",
                )
            )
    diagnostics.extend(project_extensions.validate_extensions(project, item_ids))
    return diagnostics


def normalize_project(payload: Any) -> dict:
    """Deep-copy a project, supply schema defaults, and reject malformed input.

    Args:
        payload (Any): Candidate canonical project object.

    Returns:
        (dict): Independent normalized canonical project.

    Raises:
        ProjectValidationError: If any malformed-input diagnostic is produced.
    """
    if not isinstance(payload, dict):
        raise ProjectValidationError(validate_project(payload))
    project = _with_schema_defaults(payload)
    diagnostics = validate_project(project)
    if any(item["severity"] == "error" for item in diagnostics):
        raise ProjectValidationError(diagnostics)
    return project


def _legacy_mass_unit(ship: dict) -> tuple[str, bool]:
    hull = ship.get("hull") if isinstance(ship.get("hull"), dict) else {}
    unit = hull.get("displacement_unit")
    if unit in {"metric_tonne", "tonne", "t"}:
        return "t", bool(hull.get("displacement_unit_is_estimate", False))
    if unit == "long_ton":
        return "long_ton", bool(hull.get("displacement_unit_is_estimate", False))
    if unit is None:
        return "t", True
    raise ValueError(f"unsupported legacy displacement unit: {unit!r}")


def _legacy_project_id(ship: dict, weights: dict | None) -> str:
    if isinstance(ship.get("id"), str) and ship["id"].strip():
        return ship["id"]
    stable_input = json.dumps(
        {"ship": ship, "weights": weights},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return f"legacy-{hashlib.sha256(stable_input.encode('utf-8')).hexdigest()[:12]}"


def migrate_legacy(ship: dict, weights: dict | None = None) -> dict:
    """Migrate legacy ship and weight payloads into a canonical project.

    Args:
        ship (dict): ``plimsoll-ship-1`` payload.
        weights (dict, optional): ``plimsoll-weights-1`` payload.

    Returns:
        (dict): Normalized canonical project retaining verbatim legacy inputs.
    """
    if not isinstance(ship, dict) or ship.get("schema") != "plimsoll-ship-1":
        raise ValueError("ship must use schema 'plimsoll-ship-1'")
    if weights is not None and (
        not isinstance(weights, dict) or weights.get("schema") != "plimsoll-weights-1"
    ):
        raise ValueError("weights must use schema 'plimsoll-weights-1' when supplied")
    name = ship.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("legacy ship name must be a non-empty string")
    project = new_project(name, _legacy_project_id(ship, weights))
    hull = copy.deepcopy(ship.get("hull") or {})
    if not isinstance(hull, dict):
        raise ValueError("legacy hull must be an object")
    mass_unit, unit_estimated = _legacy_mass_unit(ship)
    for field in ("displacement_normal_t", "displacement_deep_t"):
        value = hull.get(field)
        if value is not None:
            hull[field] = units.convert(value, mass_unit, "t")
    if "displacement_unit" in hull:
        hull["displacement_unit"] = "t"
    hull["displacement_unit_is_estimate"] = unit_estimated
    project["hull"] = hull

    offsets_path = hull.get("offsets_path")
    if offsets_path is not None:
        offsets_source = (hull.get("sources") or {}).get("offsets_path")
        project["geometry"] = {
            "kind": "offsets_reference",
            "source": offsets_source or "legacy hull offsets_path",
            "estimate": True,
            "keel_offset_m": None,
            "reference": {"path": offsets_path},
        }

    project["loading_conditions"] = [
        {
            "id": "normal",
            "label": "Normal",
            "reference_displacement_t": hull.get("displacement_normal_t"),
            "overrides": {},
        },
        {
            "id": "deep",
            "label": "Deep",
            "reference_displacement_t": hull.get("displacement_deep_t"),
            "overrides": {},
        },
    ]
    if weights is not None:
        groups = weights.get("groups")
        if not isinstance(groups, list):
            raise ValueError("legacy weights groups must be an array")
        migrated_groups = []
        for group in groups:
            if not isinstance(group, dict):
                raise ValueError("legacy weight group must be an object")
            migrated_items = []
            for item in group.get("items") or []:
                if not isinstance(item, dict):
                    raise ValueError("legacy weight item must be an object")
                migrated = {
                    "id": item.get("id"),
                    "mass_t": copy.deepcopy(item.get("mass_t")),
                    "x_m": copy.deepcopy(item.get("x_m")),
                    "y_m": copy.deepcopy(item.get("y_m")),
                    "kg_m": copy.deepcopy(item.get("kg_m")),
                    "source": copy.deepcopy(item.get("source")),
                    "estimate": item.get("estimate", True),
                }
                for optional in ("uncertainty", "includes"):
                    if optional in item:
                        migrated[optional] = copy.deepcopy(item[optional])
                migrated_items.append(migrated)
            migrated_groups.append(
                {
                    "id": group.get("id"),
                    "label": group.get("label", group.get("id")),
                    "required": True,
                    "items": migrated_items,
                }
            )
        project["weight_groups"] = migrated_groups

    project["sources"] = {
        "migration": {
            "ship_schema": ship["schema"],
            "weights_schema": weights.get("schema") if weights is not None else None,
            "mass_unit_from": mass_unit,
            "mass_unit_to": "t",
            "mass_unit_estimated": unit_estimated,
        }
    }
    project["legacy_inputs"] = {
        "ship": copy.deepcopy(ship),
        "weights": copy.deepcopy(weights),
    }
    return normalize_project(project)


def input_fingerprint(project: dict) -> str:
    """Return a stable SHA-256 fingerprint of canonical project input.

    Args:
        project (dict): Canonical project payload.

    Returns:
        (str): Lowercase hexadecimal SHA-256 digest.
    """
    normalized = normalize_project(project)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
