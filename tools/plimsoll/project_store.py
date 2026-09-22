"""Persist canonical projects without discovering or generating external inputs."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

if __package__:
    from . import project_io
else:  # Support the existing direct-module entrypoints.
    import project_io


def _normalize(payload: object) -> dict:
    if isinstance(payload, dict) and payload.get("schema") == "plimsoll-ship-1":
        return project_io.migrate_legacy(payload)
    return project_io.normalize_project(payload)


def load(path: str | Path) -> dict:
    """Read a UTF-8 project, migrating an explicitly supplied legacy ship.

    Args:
        path (str | Path): Project JSON file to read.

    Returns:
        (dict): Normalized canonical input with declared references preserved.
    """
    with Path(path).open("r", encoding="utf-8") as stream:
        return _normalize(json.load(stream))


def save(path: str | Path, project: dict) -> None:
    """Validate and atomically replace a project file with canonical UTF-8 JSON.

    Args:
        path (str | Path): Destination in an existing directory.
        project (dict): Canonical project or legacy ship payload to migrate.

    Notes:
        Relative references keep their literal paths. Saving in another directory
        changes their resolution base; callers must explicitly import external
        content when they need a self-contained project.
    """
    normalized = _normalize(project)
    encoded = (json.dumps(
        normalized, ensure_ascii=False, indent=2, allow_nan=False,
    ) + "\n").encode("utf-8")
    destination = Path(path).absolute()
    temporary_path = None
    try:
        # Close the owned temporary file before replacement (required on Windows).
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=destination.parent, prefix=".plimsoll-", suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def resolve_geometry_reference(project_path: str | Path, project: dict) -> Path:
    """Resolve the explicitly declared geometry path without reading its content.

    Args:
        project_path (str | Path): Project file whose directory is the reference base.
        project (dict): Canonical project with offsets_reference geometry.

    Returns:
        (Path): Absolute resolved path; existence and geometry are not checked.

    Raises:
        ValueError: If geometry is not an external reference or its path is ambiguous.
    """
    normalized = project_io.normalize_project(project)
    geometry = normalized["geometry"]
    if geometry is None or geometry["kind"] != "offsets_reference":
        raise ValueError("project geometry must have kind 'offsets_reference'")
    reference = Path(geometry["reference"]["path"])
    if reference.anchor and not reference.is_absolute():
        raise ValueError("geometry reference must be project-relative or fully absolute")
    return (Path(project_path).absolute().parent / reference).resolve()
