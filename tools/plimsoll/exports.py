"""Deterministic serialization and atomic persistence of analysis results."""

from __future__ import annotations

import csv
from io import StringIO
import json
import math
import os
from pathlib import Path
import tempfile


_CSV_COLUMNS = (
    "path", "parent_path", "key", "index", "value_type", "value",
    "container_size", "stage", "stage_status", "record_path",
    "analysis_status", "project_id", "condition_id", "project_fingerprint",
    "input_fingerprint", "request_fingerprint",
)


def _validate_format(format: object) -> str:
    if format not in ("json", "csv"):
        raise ValueError(f"unsupported report format: {format!r}")
    return format


def _validate_document(document: object) -> dict:
    if not isinstance(document, dict):
        raise ValueError("document must be a JSON object")
    _validate_json_value(document, "$", set())
    return document


def _validate_json_value(value: object, path: str, ancestors: set[int]) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Out of range float values are not JSON compliant")
        return
    if isinstance(value, (dict, list)):
        identity = id(value)
        if identity in ancestors:
            raise ValueError(f"circular reference at {path}")
        ancestors.add(identity)
        try:
            if isinstance(value, dict):
                for key, child in value.items():
                    if not isinstance(key, str):
                        raise TypeError(f"JSON object keys must be strings at {path}")
                    _validate_json_value(
                        child,
                        f"{path}[{json.dumps(key, ensure_ascii=False)}]",
                        ancestors,
                    )
            else:
                for index, child in enumerate(value):
                    _validate_json_value(child, f"{path}[{index}]", ancestors)
        finally:
            ancestors.remove(identity)
        return
    raise TypeError(f"unsupported JSON value type at {path}: {type(value).__name__}")


def _validate_result(result: object) -> dict:
    if not isinstance(result, dict) or result.get("schema") != "plimsoll-analysis-1":
        raise ValueError("result must be a plimsoll-analysis-1 object")
    return result


def _json_text(document: dict) -> str:
    text = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    text.encode("utf-8")
    return text


def _path_key(key: str) -> str:
    return json.dumps(key, ensure_ascii=False)


def _value_fields(value: object) -> tuple[str, str, str]:
    if value is None:
        return "null", "", ""
    if isinstance(value, bool):
        return "boolean", "true" if value else "false", ""
    if isinstance(value, int):
        return "integer", str(value), ""
    if isinstance(value, float):
        return "number", json.dumps(value, allow_nan=False), ""
    if isinstance(value, str):
        return "string", value, ""
    if isinstance(value, dict):
        return "object", "", str(len(value))
    if isinstance(value, list):
        return "array", "", str(len(value))
    raise TypeError(f"unsupported report value type: {type(value).__name__}")


def _context_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (bool, int, float)):
        return json.dumps(value, allow_nan=False)
    return ""


def _csv_text(document: dict) -> str:
    # Validate the complete tree before writing any CSV cells. This rejects
    # cycles, non-finite numbers and text that cannot be emitted as UTF-8.
    _json_text(document)
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=_CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    stages = document.get("stages")
    stage_map = stages if isinstance(stages, dict) else {}
    identities = {
        "analysis_status": _context_value(document.get("status")),
        "project_id": _context_value(document.get("project_id")),
        "condition_id": _context_value(document.get("condition_id")),
        "project_fingerprint": _context_value(document.get("project_fingerprint")),
        "input_fingerprint": _context_value(document.get("input_fingerprint")),
        "request_fingerprint": _context_value(document.get("request_fingerprint")),
    }

    def visit(
        value: object,
        path: str,
        parent_path: str,
        *,
        key: str = "",
        index: str = "",
        stage: str = "",
        stage_status: str = "",
        record_path: str = "",
    ) -> None:
        if parent_path == '$["stages"]' and key:
            stage = key
            envelope = stage_map.get(stage)
            stage_status = (
                _context_value(envelope.get("status"))
                if isinstance(envelope, dict) else ""
            )
        if parent_path == '$["diagnostics"]' and isinstance(value, dict):
            diagnostic_stage = value.get("stage")
            if isinstance(diagnostic_stage, str):
                stage = diagnostic_stage
                envelope = stage_map.get(stage)
                stage_status = (
                    _context_value(envelope.get("status"))
                    if isinstance(envelope, dict) else ""
                )

        value_type, cell, container_size = _value_fields(value)
        writer.writerow({
            "path": path,
            "parent_path": parent_path,
            "key": key,
            "index": index,
            "value_type": value_type,
            "value": cell,
            "container_size": container_size,
            "stage": stage,
            "stage_status": stage_status,
            "record_path": record_path,
            **identities,
        })
        if isinstance(value, dict):
            for child_key in sorted(value):
                if not isinstance(child_key, str):
                    raise TypeError("report object keys must be strings")
                child_path = f"{path}[{_path_key(child_key)}]"
                visit(
                    value[child_key], child_path, path, key=child_key,
                    stage=stage, stage_status=stage_status,
                    record_path=record_path,
                )
        elif isinstance(value, list):
            for child_index, child in enumerate(value):
                child_path = f"{path}[{child_index}]"
                visit(
                    child, child_path, path, index=str(child_index),
                    stage=stage, stage_status=stage_status,
                    record_path=child_path,
                )

    visit(document, "$", "")
    text = output.getvalue()
    text.encode("utf-8")
    return text


def serialize_document(document: dict, format: str = "json") -> str:
    """Serialize an arbitrary finite JSON object without schema assumptions."""
    checked_format = _validate_format(format)
    checked = _validate_document(document)
    if checked_format == "json":
        return _json_text(checked)
    return _csv_text(checked)


def _sps_kernel(name: str):
    """Import one sibling SpringSharp 3b3 kernel, or ``None`` when absent.

    The compatibility kernels are authored as bare siblings of this module; the
    shared loader owns how that directory becomes importable.
    """
    try:
        from . import _analysis_request
    except ImportError:                                   # direct-module entrypoints
        import _analysis_request
    return _analysis_request.kernel_module(name)


def _sps_saved_result(result: dict) -> dict:
    """The immutable compatibility stage of one saved analysis result.

    Every new export reads this and only this: the stored run's own
    ``stages.sps_compat.data``. The current draft and the current project are
    never consulted, so an edit cannot relabel an old report as current.
    """
    if not isinstance(result, dict) or result.get("schema") != "plimsoll-analysis-1":
        raise ValueError("result must be a plimsoll-analysis-1 object")
    stages = result.get("stages")
    stage = stages.get("sps_compat") if isinstance(stages, dict) else None
    data = stage.get("data") if isinstance(stage, dict) else None
    if not isinstance(data, dict):
        raise ValueError("run has no saved SpringSharp 3b3 compatibility result")
    return data


def _ship_design_saved_result(result: dict) -> dict | None:
    """The immutable native ship design stage of one saved result, or ``None``.

    A native run owns both its frozen report and its source declaration. Every
    export reads this and only this: the current draft and the current project are
    never consulted, so an edit cannot relabel an old report as current. A
    ``partial`` stage is still usable: the spec keeps the basic report available
    while the ledger is pending binding, so a stage that produced its own frozen
    report or source declaration is accepted. Only a stage that never produced a
    usable payload — failed, canceled, not requested or otherwise unavailable — is
    refused, and a non-native run returns ``None`` so the caller can fall back to
    the legacy compatibility stage.
    """
    if not isinstance(result, dict) or result.get("schema") != "plimsoll-analysis-1":
        raise ValueError("result must be a plimsoll-analysis-1 object")
    stages = result.get("stages")
    stage = stages.get("ship_design") if isinstance(stages, dict) else None
    if not isinstance(stage, dict) or stage.get("status") not in ("completed", "partial"):
        return None
    data = stage.get("data")
    return data if isinstance(data, dict) else None


def serialize_report(result: dict, format: str = "json") -> str:
    """Serialize one already-computed ``plimsoll-analysis-1`` result.

    ``json`` and ``csv`` describe the whole result exactly as before. ``txt``,
    ``rtf``, ``ssr`` and ``sship`` prefer the stored native ``ship_design`` stage
    and fall back to the stored ``sps_compat`` stage for old runs: both read only
    the saved stage, never a recomputed or current draft.
    """
    if format in ("json", "csv"):
        checked = _validate_result(result)
        return serialize_document(checked, format=format)
    if format in ("txt", "rtf", "ssr"):
        module = _sps_kernel("sps_report")
        if module is None or not hasattr(module, "serialize"):
            raise ValueError("the SpringSharp 3b3 report serializer is not available")
        native = _ship_design_saved_result(result)
        if native is not None and isinstance(native.get("report"), dict):
            return module.serialize(native["report"], format=format)
        data = _sps_saved_result(result)
        return module.serialize(data.get('report') or data, format=format)
    if format == "sship":
        native = _ship_design_saved_result(result)
        if native is not None and isinstance(native.get("source_design"), dict):
            design = native["source_design"]
        else:
            design = _sps_saved_result(result).get("design")
        if not isinstance(design, dict):
            raise ValueError("run has no saved SpringSharp 3b3 design declaration")
        module = _sps_kernel("sps_file_io")
        if module is None or not hasattr(module, "dumps"):
            raise ValueError("the SpringSharp 3b3 file serializer is not available")
        document = module.dumps(design)
        return document.decode("utf-8") if isinstance(document, (bytes, bytearray)) else str(document)
    raise ValueError(f"unsupported report format: {format!r}")


def _write_text(text: str, path: str | Path) -> None:
    encoded = text.encode("utf-8")
    destination = Path(path).absolute()
    temporary_path = None
    try:
        # The temporary file is closed before replacement for Windows support.
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=".plimsoll-report-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, destination)
    except BaseException as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                error.add_note(
                    f"Owned temporary file cleanup failed at {temporary_path}: "
                    f"{cleanup_error}"
                )
        raise


def write_document(document: dict, path: str | Path, format: str = "json") -> None:
    """Atomically write an arbitrary finite JSON object into an existing directory."""
    _write_text(serialize_document(document, format=format), path)


def write_report(result: dict, path: str | Path, format: str = "json") -> None:
    """Atomically write a serialized analysis result into an existing directory."""
    _write_text(serialize_report(result, format=format), path)
