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


class ProjectView(TypedDict):
    project_id: str
    revision: int
    project: dict


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
