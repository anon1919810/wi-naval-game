"""Strict, source-preserving import of explicitly supplied geometry content."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

try:
    from . import project_io, stability
except ImportError:  # Preserve the repository's direct-module convention.
    import project_io
    import stability


METHOD_VERSION = "geometry-content-import-1"
_SCHEMAS = {
    "legacy-offsets-5": "plimsoll-offsets-1",
    "plimsoll-section-polygons-1": "plimsoll-section-polygons-1",
}


def _diagnostic(code: str, path: str, message: str) -> dict:
    return {
        "code": code,
        "severity": "error",
        "path": path,
        "message": message,
        "blocking": True,
    }


class GeometryImportError(ValueError):
    """Report one or more structured geometry import failures."""

    def __init__(self, diagnostics: list[dict]):
        self.diagnostics = copy.deepcopy(diagnostics)
        detail = "; ".join(
            f"{item.get('path', '$')}: {item.get('message', 'invalid input')}"
            for item in diagnostics[:3]
        )
        super().__init__(detail or "geometry import failed")


class _StrictJSONError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _StrictJSONError(
                "geometry_import.duplicate_key", f"duplicate object key {key!r}")
        result[key] = value
    return result


def _float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise _StrictJSONError(
            "geometry_import.number_nonfinite", f"nonfinite JSON number {token!r}")
    return value


def _integer(token: str) -> int:
    value = int(token)
    try:
        representable = math.isfinite(value)
    except OverflowError as error:
        raise _StrictJSONError(
            "geometry_import.number_out_of_range",
            "JSON integer is outside the supported finite numeric range",
        ) from error
    if not representable:
        raise _StrictJSONError(
            "geometry_import.number_out_of_range",
            "JSON integer is outside the supported finite numeric range",
        )
    return value


def _constant(token: str):
    raise _StrictJSONError(
        "geometry_import.number_nonfinite", f"nonfinite JSON constant {token!r}")


def _validate_unicode(value: Any, path: str) -> None:
    if isinstance(value, str):
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise GeometryImportError([_diagnostic(
                "geometry_import.unicode_scalar_invalid", path,
                "JSON text contains an unpaired Unicode surrogate",
            )]) from error
    elif isinstance(value, list):
        for index, member in enumerate(value):
            _validate_unicode(member, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, member in value.items():
            _validate_unicode(key, path)
            _validate_unicode(member, f"{path}.{key}")


def _parse_content(content_bytes: bytes) -> dict:
    if not isinstance(content_bytes, bytes):
        raise GeometryImportError([_diagnostic(
            "geometry_import.content_type", "$.content",
            "content_bytes must be bytes",
        )])
    try:
        text = content_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise GeometryImportError([_diagnostic(
            "geometry_import.utf8_invalid", "$.content",
            f"content is not strict UTF-8: {error}",
        )]) from error
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_object,
            parse_float=_float,
            parse_int=_integer,
            parse_constant=_constant,
        )
    except _StrictJSONError as error:
        raise GeometryImportError([_diagnostic(
            error.code, "$.content", str(error),
        )]) from error
    except (json.JSONDecodeError, RecursionError) as error:
        location = (f" at line {error.lineno}, column {error.colno}"
                    if isinstance(error, json.JSONDecodeError) else "")
        message = error.msg if isinstance(error, json.JSONDecodeError) else str(error)
        raise GeometryImportError([_diagnostic(
            "geometry_import.json_invalid", "$.content",
            f"invalid JSON{location}: {message}",
        )]) from error
    if not isinstance(payload, dict):
        raise GeometryImportError([_diagnostic(
            "geometry_import.object_required", "$.content",
            "geometry content must be a JSON object",
        )])
    _validate_unicode(payload, "$.content")
    return payload


def _number(value: Any, path: str) -> float:
    valid = not isinstance(value, bool) and isinstance(value, (int, float))
    if valid:
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
    if not valid:
        raise GeometryImportError([_diagnostic(
            "geometry_import.number_invalid", path,
            "value must be a finite nonboolean number",
        )])
    return float(value)


def _source(value: Any) -> str | dict:
    if not ((isinstance(value, str) and value.strip())
            or (isinstance(value, dict) and value)):
        raise GeometryImportError([_diagnostic(
            "geometry_import.source_invalid", "$.source",
            "source must be a nonempty string or object",
        )])
    return copy.deepcopy(value)


def _normalized_project(project: Any) -> dict:
    try:
        return project_io.normalize_project(project)
    except project_io.ProjectValidationError as error:
        raise GeometryImportError(error.diagnostics) from error


def import_geometry_content(project, content_bytes, *, format, keel_offset_m,
                            source, estimate) -> dict:
    """Import explicitly supplied UTF-8 JSON as self-contained geometry.

    Args:
        project (dict): Canonical project whose geometry is replaced in a copy.
        content_bytes (bytes): Exact UTF-8 JSON content selected by the caller.
        format (str): Explicit accepted content format identifier.
        keel_offset_m (float): Declared keel ordinate in the geometry datum.
        source (str | dict): Nonempty provenance for the caller's selection.
        estimate (bool): Estimate state to retain on imported geometry.

    Returns:
        (dict): New normalized project containing materialized offsets.

    Raises:
        GeometryImportError: If the project, declaration, content, or geometry
            is invalid.
    """
    normalized = _normalized_project(project)
    if not isinstance(format, str) or format not in _SCHEMAS:
        raise GeometryImportError([_diagnostic(
            "geometry_import.format_unsupported", "$.format",
            f"unsupported geometry content format {format!r}",
        )])
    keel = _number(keel_offset_m, "$.keel_offset_m")
    declared_source = _source(source)
    if not isinstance(estimate, bool):
        raise GeometryImportError([_diagnostic(
            "geometry_import.estimate_invalid", "$.estimate",
            "estimate must be boolean",
        )])
    payload = _parse_content(content_bytes)
    expected_schema = _SCHEMAS[format]
    if payload.get("schema") != expected_schema:
        raise GeometryImportError([_diagnostic(
            "geometry_import.schema_mismatch", "$.content.schema",
            f"format {format!r} requires schema {expected_schema!r}",
        )])

    trace = {
        "method": "geometry_content_import",
        "method_version": METHOD_VERSION,
        "format": format,
        "raw_content_sha256": hashlib.sha256(content_bytes).hexdigest(),
        "keel_offset_m": keel,
        "input_source": declared_source,
        "input_estimate": estimate,
    }
    payload_provenance = {
        key: copy.deepcopy(payload[key])
        for key in ("source", "sources", "estimate") if key in payload
    }
    if payload_provenance:
        trace["payload_provenance"] = payload_provenance
    prior = normalized.get("geometry")
    if isinstance(prior, dict) and prior.get("kind") == "offsets_reference":
        trace["prior_offsets_reference"] = copy.deepcopy(prior)
    trace["representation"] = (
        "legacy_offsets_5_section_generator"
        if format == "legacy-offsets-5" else "explicit_section_polygons"
    )
    geometry = {
        "kind": "offsets",
        "keel_offset_m": keel,
        "source": trace,
        "estimate": estimate,
        "offsets": copy.deepcopy(payload),
    }
    try:
        stability.prepare_geometry(geometry)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError) as error:
        raise GeometryImportError([_diagnostic(
            "geometry_import.geometry_invalid", "$.content",
            f"geometry validation failed: {error}",
        )]) from error
    normalized["geometry"] = geometry
    return _normalized_project(normalized)
