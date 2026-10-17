"""SpringSharp 3b3 compatibility endpoints: a bounded, purely-read adapter.

The compatibility design is a second, independent entry point into the
calculation core. Everything that decides what a declaration *means* — the
schema, the parameter registry, the units, the dependency graph, the file
formats — belongs to the core kernels (``plimsoll.sps_*``). This module supplies
only what the web layer owes them:

- **Nothing is written.** No preview, catalog read or migration conversion
  touches a project, a revision or a run. A browser that wants to keep a design
  saves the project through the existing transactional routes.
- **The request is bounded before it is interpreted.** A design or command over
  the shared 1 MiB JSON bound is refused up front; source files reuse the exact
  byte, base64 and filename bounds the ``.sship`` importer already enforces, so a
  compatibility file cannot be a larger door into the same parsers.
- **A missing kernel is honest, not a server fault.** While a sibling kernel is
  not installed the endpoint answers with a structured 503 rather than raising a
  raw ``ImportError`` as a 500. An invalid declaration is a structured 422 in the
  same diagnostic shape every other validator here speaks.
"""

from __future__ import annotations

import base64
import binascii
import json

from fastapi import HTTPException

from plimsoll import _analysis_request

from . import sship_imports


#: The contract bound on a compatibility JSON body (design, command, migration).
MAX_BODY_BYTES = 1 << 20
#: Source-file bounds, restated from the ``.sship`` adapter so both entry points
#: admit exactly the same files.
MAX_FILENAME_CHARS = sship_imports.MAX_FILENAME_CHARS
MAX_SOURCE_BYTES = sship_imports.MAX_SOURCE_BYTES
MAX_ENCODED_CHARS = sship_imports.MAX_ENCODED_CHARS


def _kernel(name: str):
    """Load one compatibility kernel, or ``None`` when it is not installed."""
    return _analysis_request.kernel_module(name)


def _diagnostic(code: str, path: str, message: str, *, severity: str = "error") -> dict:
    return {"code": code, "severity": severity, "path": path, "message": message,
            "blocking": severity == "error"}


def _refused(diagnostics: list[dict], status_code: int = 422) -> HTTPException:
    return HTTPException(status_code=status_code, detail=diagnostics)


def _unavailable(name: str) -> HTTPException:
    return _refused([_diagnostic(
        "sps3b3.kernel_unavailable", "$",
        f"the SpringSharp 3b3 {name} kernel is not available in this installation")],
        status_code=503)


def _bounded(value: object, path: str) -> object:
    """Reject a document whose serialized form exceeds the shared body bound.

    The check is on the serialized bytes rather than the parsed object so a deeply
    nested but syntactically valid payload cannot grow past the bound unnoticed.
    """
    try:
        text = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as error:
        raise _refused([_diagnostic("sps3b3.body_invalid", path,
                                    f"the request is not finite JSON: {error}")]) from error
    if len(text.encode("utf-8")) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="request body too large")
    return value


def catalog() -> dict:
    """The 222 effective compatibility fields, wrapped for the browser."""
    module = _kernel("sps_field_catalog")
    if module is None:
        raise _unavailable("field catalog")
    raw = module.catalog()
    fields = []
    for name, spec in raw["fields"].items():
        entry = dict(spec)
        entry["key"] = name
        fields.append(entry)
    return {"schema": raw.get("schema"), "fields": fields,
            "page_order": raw.get("page_order"), "page_labels": raw.get("page_labels"),
            "pages": raw.get("pages"), "controls": raw.get("controls")}


def default_design() -> dict:
    """A fresh compatibility declaration on the original fresh-window defaults."""
    module = _kernel("sps_file_io")
    if module is None or not hasattr(module, "default_design"):
        raise _unavailable("fresh-design")
    return {"design": _bounded(module.default_design(), "$.design")}


def preview(design: dict, command: dict | None = None) -> dict:
    """Compute one draft, or apply one edit command to it. Writes nothing.

    With no command the whole declaration is computed; with a command the pure
    edit is applied first and its own preview returned. This is a *preview*: the
    answer is never saved and never claimed as the current project result.
    """
    module = _kernel("sps_compat")
    if module is None:
        raise _unavailable("compatibility")
    _bounded(design, "$.design")
    if command is not None:
        _bounded(command, "$.command")
    try:
        if command is None:
            computed = module.compute(design)
            return {"design": computed.get("design"), "preview": computed,
                    "diagnostics": computed.get("diagnostics", []),
                    "status": computed.get("status")}
        edited = module.apply_edit(design, command)
    except Exception as error:                            # pragma: no cover - defensive
        raise _refused([_diagnostic("sps3b3.kernel_error", "$",
                                    f"the compatibility kernel failed: {error}")]) from error
    return {"design": edited.get("design"), "preview": edited.get("preview"),
            "diagnostics": edited.get("diagnostics", []), "status": edited.get("status")}


def _decode(filename: str, content_base64: str) -> tuple[str, bytes]:
    """The chosen source bytes, under the same bounds the .sship importer uses."""
    name = filename.strip() if isinstance(filename, str) else ""
    if (not name or len(name) > MAX_FILENAME_CHARS or name in {".", ".."}
            or "/" in name or "\\" in name or "\0" in name):
        raise _refused([_diagnostic(
            "sps3b3.filename_invalid", "$.filename",
            "the file name must be a bare name, not a path")])
    if not isinstance(content_base64, str) or len(content_base64) > MAX_ENCODED_CHARS:
        raise HTTPException(status_code=413, detail="source file too large")
    try:
        data = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise _refused([_diagnostic(
            "sps3b3.base64_invalid", "$.content_base64",
            "the source content is not strict standard base64")]) from None
    if len(data) > MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="source file too large")
    return name, data


def import_preview(filename: str, content_base64: str) -> dict:
    """Read one chosen SpringSharp source into a compatibility declaration.

    The original bytes are the evidence: the kernel reader owns the format, the
    digest and the source record, and this preview writes nothing.
    """
    module = _kernel("sps_file_io")
    if module is None or not hasattr(module, "read"):
        raise _unavailable("file reader")
    _name, data = _decode(filename, content_base64)
    try:
        reading = module.read(data)
    except Exception as error:
        diagnostics = getattr(error, "diagnostics", None)
        if isinstance(diagnostics, list) and diagnostics:
            raise _refused(list(diagnostics)) from error
        raise _refused([_diagnostic("sps3b3.import_failed", "$.content_base64",
                                    str(error))]) from error
    if not isinstance(reading, dict):
        raise _refused([_diagnostic("sps3b3.import_failed", "$.content_base64",
                                    "the source reader returned no declaration")])
    return {"design": reading.get("design"), "source": reading.get("source"),
            "diagnostics": reading.get("diagnostics", [])}


def from_migration(migration: dict) -> dict:
    """Convert a project's archived original source without mutating the archive.

    The archived migration is deep-copied before it is handed to the kernel, so
    the caller's own archive object can never be rewritten by the conversion.
    """
    module = _kernel("sps_file_io")
    if module is None or not hasattr(module, "from_migration"):
        raise _unavailable("migration reader")
    _bounded(migration, "$.migration")
    working = json.loads(json.dumps(migration, allow_nan=False))
    try:
        design = module.from_migration(working)
    except Exception as error:
        diagnostics = getattr(error, "diagnostics", None)
        if isinstance(diagnostics, list) and diagnostics:
            raise _refused(list(diagnostics)) from error
        raise _refused([_diagnostic("sps3b3.migration_failed", "$.migration",
                                    str(error))]) from error
    return {"design": design}
