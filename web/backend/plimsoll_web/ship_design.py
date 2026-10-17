"""Native ship design endpoints: a bounded, purely-read adapter.

The native declaration is the product's own entry point into the calculation
core. Everything that decides what a declaration *means* — the schema, the
parameter registry, the units, the SI hull projection and the managed mass scope
— belongs to the pure native kernel (``plimsoll.ship_design``). This module
supplies only what the web layer owes it:

- **Nothing is written.** No preview, initialization, source import or migration
  conversion touches a project, a revision or a run. A browser that wants to keep
  a design saves the project through the existing transactional routes.
- **The request is bounded before it is interpreted.** A project, design,
  command or migration over the shared 1 MiB JSON bound is refused up front; a
  chosen source file reuses the exact byte, base64 and filename bounds the
  ``.sship`` importer already enforces, so the native reader is not a larger door
  into the same parsers.
- **A missing kernel is honest, not a server fault.** While the sibling kernel is
  still being written the endpoint answers with a structured 503 rather than
  raising a raw ``ImportError`` as a 500. An invalid declaration is a structured
  422 in the same diagnostic shape every other validator here speaks.
"""

from __future__ import annotations

import json

from fastapi import HTTPException

from plimsoll import _analysis_request

from . import sps3b3


#: The contract bound on a native JSON body (project, design, command, migration).
MAX_BODY_BYTES = 1 << 20


def _kernel(name: str = "ship_design"):
    """Load the native kernel, or ``None`` when it is not installed."""
    return _analysis_request.kernel_module(name)


def _diagnostic(code: str, path: str, message: str, *, severity: str = "error") -> dict:
    return {"code": code, "severity": severity, "path": path, "message": message,
            "blocking": severity == "error"}


def _refused(diagnostics: list[dict], status_code: int = 422) -> HTTPException:
    return HTTPException(status_code=status_code, detail=diagnostics)


def _unavailable(name: str) -> HTTPException:
    return _refused([_diagnostic(
        "ship_design.kernel_unavailable", "$",
        f"the native ship design {name} is not available in this installation")],
        status_code=503)


def _bounded(value: object, path: str) -> object:
    """Reject a document whose serialized form exceeds the shared body bound.

    The check is on the serialized bytes rather than the parsed object so a deeply
    nested but syntactically valid payload cannot grow past the bound unnoticed.
    """
    try:
        text = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as error:
        raise _refused([_diagnostic("ship_design.body_invalid", path,
                                    f"the request is not finite JSON: {error}")]) from error
    if len(text.encode("utf-8")) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="request body too large")
    return value


def _call(function, *args):
    """Run one kernel call, mapping its own refusals to a structured 422."""
    try:
        return function(*args)
    except Exception as error:                            # pragma: no cover - defensive
        diagnostics = getattr(error, "diagnostics", None)
        if isinstance(diagnostics, list) and diagnostics:
            raise _refused(list(diagnostics)) from error
        raise _refused([_diagnostic("ship_design.kernel_error", "$",
                                    f"the native ship design kernel failed: {error}")]) from error


def _reply(reply: object) -> dict:
    if not isinstance(reply, dict):
        raise _refused([_diagnostic("ship_design.reply_invalid", "$",
                                    "the native ship design kernel returned no reply")])
    return reply


def catalog() -> dict:
    """The native field registry, wrapped for the browser.

    The registry itself is the existing source-field catalogue the compatibility
    reader already publishes; the native declaration reuses that field vocabulary
    rather than inventing a second one, so this endpoint is the same read-only
    wrapper under the product's own route.
    """
    return sps3b3.catalog()


def initialize(project: dict, source: dict | None = None) -> dict:
    """Initialize or upgrade a native declaration from one project draft.

    With no source the kernel seeds a fresh native blank; with a chosen source
    declaration — an adapted original source, or a converted archived migration —
    it adopts that declaration as the native design. Either way this is a *preview
    of the resulting project*: the answer is returned and never saved, and no
    external file is read or written.
    """
    module = _kernel()
    if module is None:
        raise _unavailable("initialization")
    _bounded(project, "$.project")
    if source is not None:
        _bounded(source, "$.source")
    return _reply(_call(module.initialize, project, source))


def preview(project: dict, command: dict | None = None, design: dict | None = None) -> dict:
    """Compute one native draft, or apply one edit command. Writes nothing.

    The whole project is supplied so the kernel can project the authoritative
    declaration onto the shared hull and ledger; the optional ``design`` is the
    last confirmed native declaration, and the optional ``command`` is one pure
    edit applied before the preview is computed. This is a *preview*: the answer is
    never saved and never claimed as the current project result.
    """
    module = _kernel()
    if module is None:
        raise _unavailable("preview")
    _bounded(project, "$.project")
    if command is not None:
        _bounded(command, "$.command")
    if design is not None:
        _bounded(design, "$.design")
    return _reply(_call(module.preview, project, command, design))


def _decode_reading(reading: object, code: str, path: str) -> dict:
    design = reading.get("design") if isinstance(reading, dict) else None
    if not isinstance(design, dict):
        raise _refused([_diagnostic(code, path,
                                    "the source reader returned no declaration")])
    return design


def import_preview(project: dict, filename: str, content_base64: str) -> dict:
    """Adapt one chosen source file into a native declaration. Writes nothing.

    The chosen bytes are decoded, bounded and parsed by the existing source
    reader, which owns the file format and the source record; the resulting
    declaration is then adopted by the native kernel. Nothing external is written
    and no project is saved.
    """
    module = _kernel()
    if module is None:
        raise _unavailable("source reader")
    _bounded(project, "$.project")
    reading = sps3b3.import_preview(filename, content_base64)
    design = _decode_reading(reading, "ship_design.import_failed", "$.content_base64")
    return _reply(_call(module.initialize, project, design))


def from_migration(project: dict, migration: dict) -> dict:
    """Adapt a project's archived original source without mutating the archive.

    The archive is deep-copied and converted by the existing migration reader, so
    the caller's own archive object can never be rewritten; the resulting
    declaration is then adopted by the native kernel.
    """
    module = _kernel()
    if module is None:
        raise _unavailable("migration reader")
    _bounded(project, "$.project")
    _bounded(migration, "$.migration")
    converted = sps3b3.from_migration(migration)
    design = _decode_reading(converted, "ship_design.migration_failed", "$.migration")
    return _reply(_call(module.initialize, project, design))
