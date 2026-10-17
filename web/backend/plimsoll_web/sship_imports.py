"""A SpringSharp 3.0 source file, read and saved through the workspace.

A `.sship` file is somebody's ship in a foreign positional format, so this module
is an adapter and nothing more. Everything that decides what the file *means* —
decoding, the header's decimal convention, the positional records, the mapping,
the source archive — belongs to the core readers: the legacy mapping reader in
`plimsoll.sship_import`, and the pure original-format codec in
`plimsoll.sps_file_io`. This module supplies what the web layer owes them:
bounded, strictly decoded bytes, a bare filename, structured refusals, and the
existing owner-scoped import.

Two readers stand behind the two modes. The default (``native=False``) is the
legacy migration: it maps the 3.0 records into a projection and rejects 2.0. The
native mode reads the original 3.0 *and* 2.0 layouts through the pure codec and
saves the source as one native ``ship_design`` project, with no legacy
placeholder rows and no extra upgrade step; the original bytes are still
archived verbatim as the evidence.

Three properties are the reason this file exists at all:

- **The bytes are the evidence.** The source is stored verbatim in the project it
  becomes, and the project can be exported and imported again without losing it.
  So nothing is decoded, normalised or re-encoded here; the digest the preview
  reported is computed from exactly the bytes a save re-reads.
- **The browser is not trusted, and is not believed either.** Nothing a client
  sends about the file — a mapping, a project, a converted document — is read.
  A save reparses the original bytes and compares the digest it computed with
  the one the reader was shown, so a source replaced between preview and save is
  refused before any row exists. That binds the two requests together; it is not
  proof that a human looked at anything, and a caller who sends matching bytes
  and a matching digest is simply saving the file it named.
- **A preview writes nothing.** It reads bytes and returns a description, in the
  same shape as the backup preview the library already speaks.
"""

from __future__ import annotations

import base64
import binascii
import os
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from plimsoll import project_io, ship_design, sps_file_io, sship_import

from . import projects
from .projects import ProjectView


#: The bound the core places on the source itself, restated so the request
#: envelope is bounded before it is decoded rather than after.
MAX_SOURCE_BYTES = sship_import.MAX_BYTES

#: The longest base64 that can carry `MAX_SOURCE_BYTES`, checked before any
#: decode so an oversized request costs a comparison and nothing else.
MAX_ENCODED_CHARS = 4 * ((MAX_SOURCE_BYTES + 2) // 3)

MAX_FILENAME_CHARS = 255

#: The native import's own method identity. It is deliberately distinct from the
#: legacy mapping's version so a reader (and the preview component) can tell a
#: native first-class declaration from the old field-by-field migration.
NATIVE_METHOD_VERSION = "native-sship-import-v1"


def _refused(diagnostics: list[dict], status_code: int = 422) -> HTTPException:
    """Report a refusal in the structured shape every validator here uses."""
    return HTTPException(status_code=status_code, detail=diagnostics)


def _diagnostic(code: str, path: str, message: str, *, severity: str = "error") -> dict:
    return {"code": code, "severity": severity, "path": path, "message": message,
            "blocking": severity == "error"}


def _bare_filename(filename: str) -> str:
    """The name a reader sees in their own chooser, never a path to follow.

    The name is only ever reported and archived, so a bare basename is enough
    and anything that looks like a path is refused rather than stripped: a
    source identified by a directory tells the reader nothing they need, and
    accepting one would make the archive's identity depend on the machine.
    """
    name = filename.strip()
    if (not name or len(name) > MAX_FILENAME_CHARS or name in {".", ".."}
            or "/" in name or "\\" in name or "\0" in name):
        raise _refused([_diagnostic(
            "sship.source.filename_invalid", "$.filename",
            "the file name must be a bare name, not a path")])
    return name


def _decode(filename: str, content_base64: str) -> tuple[str, bytes]:
    """The source bytes exactly as they were chosen, under both bounds."""
    name = _bare_filename(filename)
    if len(content_base64) > MAX_ENCODED_CHARS:
        raise HTTPException(status_code=413, detail="source file too large")
    try:
        data = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise _refused([_diagnostic(
            "sship.source.base64_invalid", "$.content_base64",
            "the source content is not strict standard base64")]) from None
    if len(data) > MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="source file too large")
    return name, data


def _read(name: str, data: bytes) -> dict:
    """One parse of the original bytes, with the core's own refusals intact."""
    try:
        return sship_import.preview(data, filename=name)
    except sship_import.SshipImportError as error:
        raise _refused(error.diagnostics) from error


def _migration_preview(reading: dict) -> dict:
    """The part of the core reading the browser needs, and nothing it does not.

    The converted project is deliberately absent: a preview exists so the reader
    can decide, and a browser that is handed the whole draft would only be
    holding a document the server would refuse to trust back from it.
    """
    return {
        "method_version": reading["method_version"],
        "source": reading["source"],
        "fields": reading["fields"],
        "counts": reading["counts"],
        "diagnostics": reading["diagnostics"],
        "limitations": reading["limitations"],
    }


# ------------------------------------------------------------------- native ---
#
# The native reader is the pure codec in `plimsoll.sps_file_io`, not the legacy
# mapping reader: it understands the original 3.0 records *and* the 2.0 legacy
# layout, and it returns the source's own declaration rather than a projected
# draft full of placeholders. A native import therefore never maps 280 records
# into weight groups, never rejects 2.0, and never creates a manual placeholder
# the reader would then have to upgrade. The original bytes are still archived
# verbatim, because they remain the evidence.


def _canonical_parameter_count() -> int:
    """The 222 effective design fields, or the literal count if unavailable."""
    try:  # The catalogue is the canon; the literal is only a defensive fallback.
        from plimsoll import sps_field_catalog
        return int(sps_field_catalog.EFFECTIVE_FIELD_COUNT)
    except Exception:                                   # pragma: no cover - defensive
        return 222


def _header_text(data: bytes) -> str:
    """The accepted header line, decoded exactly as the codec decoded the file.

    ``sps_file_io.read`` reports the version but not the raw header. The header
    line is read with the same shared record helpers the codec uses, so a comma
    header is reported as itself and never normalised; this is the format-agnostic
    split, not the version-rejecting legacy reader.
    """
    try:
        text, _encoding = sship_import._decode(data)
        records, _tail = sship_import._split_records(text, 1)
    except sship_import.SshipImportError:               # pragma: no cover - defensive
        return ""
    return records[0] if records else ""


def _native_reading(data: bytes) -> dict:
    """One parse of the original bytes through the pure native codec."""
    try:
        return sps_file_io.read(data)
    except sps_file_io.FileIOError as error:
        raise _refused(error.diagnostics) from error


def _native_source_name(design: dict, filename: str) -> str:
    """The source's declared ship name, or the file's stem when it has none."""
    parameters = design.get("parameters") if isinstance(design, dict) else None
    value = parameters.get("ship_name") if isinstance(parameters, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    stem = os.path.splitext(filename)[0].strip()
    return stem or "ship"


def _native_archive(name: str, data: bytes, reading: dict) -> dict:
    """The immutable migration archive: the original bytes and their provenance.

    This is a ``plimsoll-sship-migration-1`` archive so the existing download and
    the future ``from_migration`` readers keep working unchanged. It carries the
    full filename, digest, version, header, encoding, length, the raw record block
    and the notes, but no mapped weight placeholder data: everything that is a
    design fact now lives in the native ``ship_design``.
    """
    source = reading["source"]
    design = reading["design"]
    return {
        "schema": sship_import.MIGRATION_SCHEMA,
        "method_version": NATIVE_METHOD_VERSION,
        "source": {
            "filename": name,
            "sha256": source["sha256"],
            "byte_length": len(data),
            "encoding": source["encoding"],
            "header": _header_text(data),
            "version": source["version"],
        },
        "original_base64": base64.b64encode(data).decode("ascii"),
        "raw_fields": list(reading["raw_records"]),
        "notes": design.get("notes") or "",
        "diagnostics": list(reading["diagnostics"]),
    }


def _native_migration(name: str, data: bytes, reading: dict) -> dict:
    """The native preview's own migration record.

    It reports the source identity in full and the two counts a reader needs —
    the 222 canonical design fields and the raw record count (280 for 3.0, 136
    for 2.0) — kept apart. It never invents a 2.0 source-line index and never
    reports the legacy disposition counts, which describe a projection this
    native import does not perform.
    """
    source = reading["source"]
    return {
        "method_version": NATIVE_METHOD_VERSION,
        "source": {
            "filename": name,
            "sha256": source["sha256"],
            "version": source["version"],
            "header": _header_text(data),
            "encoding": source["encoding"],
            "byte_length": len(data),
        },
        "parameter_count": _canonical_parameter_count(),
        "raw_record_count": len(reading["raw_records"]),
        "diagnostics": list(reading["diagnostics"]),
    }


def _native_draft(name: str, data: bytes, reading: dict) -> dict:
    """Assemble a fresh native project for one already-read source.

    A fresh canonical draft is built by the pure constructor and its declaration
    adopted by the accepted native initializer, so the source becomes one native
    ``ship_design`` fact with its own condition, projection and reconciled ledger.
    The original bytes are archived verbatim alongside it. Nothing from the legacy
    mapping path — a placeholder weight group, a manual mass, an upgrade step — is
    created, because the source is a new project and all of its facts are native.
    """
    project = project_io.new_project(_native_source_name(reading["design"], name))
    reply = ship_design.initialize(project, reading["design"])
    built = reply.get("project") if isinstance(reply, dict) else None
    if not isinstance(built, dict) or not isinstance(built.get("ship_design"), dict):
        diagnostics = reply.get("diagnostics") if isinstance(reply, dict) else None
        raise _refused(diagnostics or [_diagnostic(
            "sship.native.initialize_failed", "$.content_base64",
            "the native ship design could not be initialized from this source")])
    built["migration"] = _native_archive(name, data, reading)
    return built


def _check_digest(computed: str, source_sha256: str) -> None:
    """Refuse a save whose bytes no longer hash to the previewed source."""
    if computed != source_sha256:
        raise _refused([_diagnostic(
            "sship.source_mismatch", "$.source_sha256",
            f"these bytes hash to {computed}, not to the previewed source; preview the "
            "file again before saving it")], status_code=409)


def preview(filename: str, content_base64: str, *, native: bool = False) -> dict:
    """Describe one SpringSharp source. Reads the bytes and writes nothing.

    Args:
        filename (str): The name the reader's chooser showed.
        content_base64 (str): The original file, standard base64.
        native (bool): ``True`` to read the file as a native first-class design
            through the pure codec (3.0 and 2.0), rather than the legacy mapping.

    Returns:
        (dict): The standard backup preview of the resulting draft, plus the
            migration's own source, field, count, diagnostic and limit records.
    """
    name, data = _decode(filename, content_base64)
    if native:
        reading = _native_reading(data)
        described = projects.preview_project_import(_native_draft(name, data, reading))
        return {**described, "migration": _native_migration(name, data, reading)}
    reading = _read(name, data)
    described = projects.preview_project_import(reading["project"])
    return {**described, "migration": _migration_preview(reading)}


def import_source(owner_id: uuid.UUID, filename: str, content_base64: str,
                   source_sha256: str, name: str | None, db: Session, *,
                   native: bool = False) -> ProjectView:
    """Save one SpringSharp source as a new project owned by the current reader.

    The source is parsed again here — the preview is never trusted as input — and
    the digest of the bytes being saved is compared with the digest the reader
    was last shown. A mismatch is refused before a project, a revision or a run
    exists, so replacing a source between preview and save cannot quietly save
    the wrong ship.

    With ``native`` the bytes are read by the pure codec and saved as a native
    ``ship_design`` project with the original file archived verbatim; without it
    the legacy mapping path is unchanged.

    Args:
        owner_id (uuid.UUID): The signed-in reader.
        filename (str): The name the reader's chooser showed.
        content_base64 (str): The original file, standard base64.
        source_sha256 (str): Digest the current preview reported for these bytes.
        name (str | None): The reader's confirmed name for the new project.
        db (Session): Request-scoped session.
        native (bool): ``True`` to import as a native design.

    Returns:
        (ProjectView): A fresh owned project at revision 1 with the source archive.
    """
    source_name, data = _decode(filename, content_base64)
    if native:
        reading = _native_reading(data)
        _check_digest(reading["source"]["sha256"], source_sha256)
        return projects.import_project(owner_id, _native_draft(source_name, data, reading),
                                       name, db)
    reading = _read(source_name, data)
    _check_digest(reading["source"]["sha256"], source_sha256)
    return projects.import_project(owner_id, reading["project"], name, db)