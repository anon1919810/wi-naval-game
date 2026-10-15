"""A SpringSharp 3.0 source file, read and saved through the workspace.

A `.sship` file is somebody's ship in a foreign positional format, so this module
is an adapter and nothing more. Everything that decides what the file *means* —
decoding, the header's decimal convention, the 280 positions, the mapping, the
source archive — belongs to the core importer in `plimsoll.sship_import`. This
module supplies what the web layer owes it: bounded, strictly decoded bytes, a
bare filename, structured refusals, and the existing owner-scoped import.

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
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from plimsoll import sship_import

from . import projects
from .projects import ProjectView


#: The bound the core places on the source itself, restated so the request
#: envelope is bounded before it is decoded rather than after.
MAX_SOURCE_BYTES = sship_import.MAX_BYTES

#: The longest base64 that can carry `MAX_SOURCE_BYTES`, checked before any
#: decode so an oversized request costs a comparison and nothing else.
MAX_ENCODED_CHARS = 4 * ((MAX_SOURCE_BYTES + 2) // 3)

MAX_FILENAME_CHARS = 255


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


def preview(filename: str, content_base64: str) -> dict:
    """Describe one SpringSharp source. Reads the bytes and writes nothing.

    Args:
        filename (str): The name the reader's chooser showed.
        content_base64 (str): The original file, standard base64.

    Returns:
        (dict): The standard backup preview of the projected draft, plus the
            migration's own source, field, count, diagnostic and limit records.
    """
    name, data = _decode(filename, content_base64)
    reading = _read(name, data)
    described = projects.preview_project_import(reading["project"])
    return {**described, "migration": _migration_preview(reading)}


def import_source(owner_id: uuid.UUID, filename: str, content_base64: str,
                   source_sha256: str, name: str | None, db: Session) -> ProjectView:
    """Save one SpringSharp source as a new project owned by the current reader.

    The source is parsed again here — the preview is never trusted as input — and
    the digest of the bytes being saved is compared with the digest the reader
    was last shown. A mismatch is refused before a project, a revision or a run
    exists, so replacing a source between preview and save cannot quietly save
    the wrong ship.

    Args:
        owner_id (uuid.UUID): The signed-in reader.
        filename (str): The name the reader's chooser showed.
        content_base64 (str): The original file, standard base64.
        source_sha256 (str): Digest the current preview reported for these bytes.
        name (str | None): The reader's confirmed name for the new project.
        db (Session): Request-scoped session.

    Returns:
        (ProjectView): A fresh owned project at revision 1 with the source archive.
    """
    source_name, data = _decode(filename, content_base64)
    reading = _read(source_name, data)
    computed = reading["source"]["sha256"]
    if computed != source_sha256:
        raise _refused([_diagnostic(
            "sship.source_mismatch", "$.source_sha256",
            f"these bytes hash to {computed}, not to the previewed source; preview the "
            "file again before saving it")], status_code=409)
    return projects.import_project(owner_id, reading["project"], name, db)