"""Owner-scoped canonical projects and immutable saved revisions."""

from __future__ import annotations

import copy
from importlib import resources
import json
from typing import TypedDict
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from plimsoll import project_io

from .models import Project, ProjectRevision, utc_now


TEMPLATES = {
    "analytic_box": "analytic_box.project.json",
    "generic_steamer": "generic_steamer.project.json",
    "queen_mary_1913": "queen_mary_1913.project.json",
}

MAX_PROJECT_NAME = 200


class ProjectView(TypedDict):
    project_id: str
    revision: int
    project: dict


class ImportCounts(TypedDict):
    loading_conditions: int
    weight_groups: int
    weight_items: int
    damage_scenarios: int
    compartments: int
    openings: int


class ImportPreview(TypedDict):
    """What a backup actually contains, without the document itself.

    A preview is a summary a reader confirms before anything is saved, so it
    carries identity, shape and counts rather than a second copy of a document
    that can be a megabyte long.
    """

    source_id: str
    name: str
    source_revision: int
    geometry_kind: str | None
    counts: ImportCounts
    diagnostics: list[dict]


class RevisionConflict(Exception):
    def __init__(self, current_revision: int):
        self.current_revision = current_revision


def _normalize(document: dict) -> dict:
    if isinstance(document.get("geometry"), dict) and document["geometry"].get("kind") == "offsets_reference":
        raise HTTPException(status_code=422, detail="external geometry paths are unavailable on the web")
    try:
        return project_io.normalize_project(document)
    except project_io.ProjectValidationError as error:
        raise HTTPException(status_code=422, detail=error.diagnostics) from error


def _view(row: Project, revision: ProjectRevision) -> ProjectView:
    return {"project_id": str(row.id), "revision": revision.revision,
            "project": copy.deepcopy(revision.document)}


def owned_project(db: Session, owner_id: uuid.UUID, project_id: uuid.UUID, *, lock: bool = False) -> Project:
    query = select(Project).where(Project.id == project_id, Project.owner_id == owner_id)
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise HTTPException(status_code=404, detail="project not found")
    return row


def create_project(owner_id: uuid.UUID, template: str | None, name: str, db: Session) -> ProjectView:
    project_id = uuid.uuid4()
    if template is None:
        document = project_io.new_project(name, project_id=str(project_id))
    else:
        filename = TEMPLATES.get(template)
        if filename is None:
            raise HTTPException(status_code=422, detail="unknown project template")
        with resources.files("plimsoll").joinpath("cases", "projects", filename).open("r", encoding="utf-8") as stream:
            document = json.load(stream)
        document["id"] = str(project_id)
        document["name"] = name
    document["revision"] = 1
    normalized = _normalize(document)
    row = Project(id=project_id, owner_id=owner_id, name=name, current_revision=1)
    saved = ProjectRevision(project_id=project_id, revision=1, document=normalized)
    db.add_all((row, saved))
    db.commit()
    return _view(row, saved)


def list_projects(owner_id: uuid.UUID, db: Session) -> list[dict]:
    rows = db.scalars(
        select(Project).where(Project.owner_id == owner_id)
        .order_by(Project.updated_at.desc(), Project.id)
    ).all()
    return [{"project_id": str(row.id), "name": row.name,
             "revision": row.current_revision, "updated_at": row.updated_at.isoformat()}
            for row in rows]


def get_project(owner_id: uuid.UUID, project_id: uuid.UUID, db: Session) -> ProjectView:
    row = owned_project(db, owner_id, project_id)
    revision = db.get(ProjectRevision, (row.id, row.current_revision))
    if revision is None:
        raise RuntimeError("project current revision is missing")
    return _view(row, revision)


def save_project(
    owner_id: uuid.UUID, project_id: uuid.UUID, base_revision: int,
    payload: dict, db: Session,
) -> ProjectView:
    row = owned_project(db, owner_id, project_id, lock=True)
    if row.current_revision != base_revision:
        raise RevisionConflict(row.current_revision)
    if payload.get("id") != str(project_id):
        raise HTTPException(status_code=422, detail="project id cannot change")
    next_revision = base_revision + 1
    document = copy.deepcopy(payload)
    document["revision"] = next_revision
    normalized = _normalize(document)
    saved = ProjectRevision(project_id=project_id, revision=next_revision, document=normalized)
    db.add(saved)
    row.current_revision = next_revision
    row.name = normalized["name"]
    row.updated_at = utc_now()
    db.commit()
    return _view(row, saved)


def delete_project(owner_id: uuid.UUID, project_id: uuid.UUID, db: Session) -> None:
    row = owned_project(db, owner_id, project_id, lock=True)
    db.delete(row)
    db.commit()


# --- restoring a backup ------------------------------------------------------
#
# A downloaded project JSON is input only. Restoring it therefore never looks
# the source identity up: it is not an update, it is a new project that happens
# to hold the same input. The source document is validated exactly as it was
# written before any of its identity is replaced, so a backup with a malformed
# `id` or `revision` fails on its own terms rather than being quietly repaired.

def _lengths(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _import_counts(project: dict) -> ImportCounts:
    groups = project.get("weight_groups")
    groups = groups if isinstance(groups, list) else []
    return {
        "loading_conditions": _lengths(project.get("loading_conditions")),
        "weight_groups": len(groups),
        "weight_items": sum(
            _lengths(group.get("items")) for group in groups if isinstance(group, dict)
        ),
        "damage_scenarios": _lengths(project.get("flooding_scenarios")),
        "compartments": _lengths(project.get("compartments")),
        "openings": _lengths(project.get("openings")),
    }


def _import_preview(normalized: dict) -> ImportPreview:
    geometry = normalized.get("geometry")
    return {
        "source_id": normalized["id"],
        "name": normalized["name"],
        "source_revision": normalized["revision"],
        "geometry_kind": geometry["kind"] if isinstance(geometry, dict) else None,
        "counts": _import_counts(normalized),
        # The source passed normalization, so everything left here is a warning
        # the reader should see rather than a defect that stopped the import.
        "diagnostics": project_io.validate_project(normalized),
    }


def preview_project_import(document: dict) -> ImportPreview:
    """Validate a backup and describe it. Reads nothing and writes nothing.

    Args:
        document (dict): The backup exactly as it was downloaded.

    Returns:
        (ImportPreview): Identity, geometry, counts and canonical diagnostics.
    """
    return _import_preview(_normalize(document))


def _confirmed_name(name: str | None, fallback: str) -> str:
    """The reader's own name for the restored project, or the backup's.

    The stored column is 200 characters, so the bound is checked on whichever
    name is actually going to be written — including a backup's own over-length
    name, which is refused before a row exists rather than at the database.
    """
    trimmed = fallback if name is None else name.strip()
    if not trimmed:
        raise HTTPException(status_code=422, detail="project name cannot be blank")
    if len(trimmed) > MAX_PROJECT_NAME:
        raise HTTPException(
            status_code=422,
            detail=f"project name cannot exceed {MAX_PROJECT_NAME} characters",
        )
    return trimmed


def import_project(
    owner_id: uuid.UUID, document: dict, name: str | None, db: Session,
) -> ProjectView:
    """Save a backup as a new project owned by the current reader.

    The source is revalidated before anything is copied, then a fresh server
    identity replaces only `id`, `revision` and `name`. No run, fingerprint or
    cached result travels with a backup, and no failure part-way through can
    leave a project behind: validation happens before the first write.
    """
    source = _normalize(document)
    project_id = uuid.uuid4()
    restored = copy.deepcopy(source)
    restored["id"] = str(project_id)
    restored["revision"] = 1
    restored["name"] = _confirmed_name(name, source["name"])
    normalized = _normalize(restored)
    row = Project(id=project_id, owner_id=owner_id, name=normalized["name"], current_revision=1)
    saved = ProjectRevision(project_id=project_id, revision=1, document=normalized)
    db.add_all((row, saved))
    db.commit()
    return _view(row, saved)
