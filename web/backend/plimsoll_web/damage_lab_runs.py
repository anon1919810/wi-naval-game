"""Owner-scoped laboratory setup and immutable queue results."""
import json
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from plimsoll.damage_lab import default_experiment, normalize_request
from plimsoll.damage_lab.exports import serialize_report
from plimsoll.damage_lab.request import SCHEMA
import plimsoll

from . import runs
from .models import CalculationRun, ProjectRevision, utc_now
from .projects import RevisionConflict, owned_project


def view(row, include_result=True):
    return {**runs._run_view(row, include_result=include_result), "request": row.request, "has_result": row.result is not None}


def setup(owner_id, project_id, db):
    project = owned_project(db, owner_id, project_id)
    saved = db.get(ProjectRevision, (project_id, project.current_revision))
    try:
        experiment = default_experiment(saved.document)
        # Admission is cheap; don't present an unusable layout as runnable.
        normalize_request(saved.document, saved.document["loading_conditions"][0]["id"], experiment)
        return dict(revision=project.current_revision, experiment=experiment, diagnostics=[])
    except ValueError as error:
        return dict(revision=project.current_revision, experiment=None,
                    diagnostics=getattr(error, "diagnostics", [{"message": str(error)}]))


def demo():
    path = Path(plimsoll.__file__).resolve().parent / "cases/damage_lab"
    return dict(project=json.loads((path / "synthetic-vessel.project.json").read_text(encoding="utf-8")),
                experiment=json.loads((path / "synthetic-vessel.experiment.json").read_text(encoding="utf-8")))


def prepare(owner_id, project_id, revision, condition_id, experiment, db):
    project = owned_project(db, owner_id, project_id)
    if project.current_revision != revision:
        raise RevisionConflict(project.current_revision)
    saved = db.get(ProjectRevision, (project_id, revision))
    if saved is None:
        raise RuntimeError("project current revision is missing")
    try:
        snapshot, request, fingerprint = normalize_request(saved.document, condition_id, experiment)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=getattr(error, "diagnostics", [{"message": str(error)}])) from error
    return snapshot, request, fingerprint


def preview(owner_id, project_id, revision, condition_id, experiment, db):
    _, request, fingerprint = prepare(owner_id, project_id, revision, condition_id, experiment, db)
    return dict(experiment=request["experiment"], request_fingerprint=fingerprint)


def enqueue(owner_id, project_id, revision, condition_id, experiment, db):
    snapshot, request, fingerprint = prepare(owner_id, project_id, revision, condition_id, experiment, db)
    result = runs.enqueue_snapshot(owner_id, project_id, revision, condition_id, snapshot, request, fingerprint, db)
    return {**result, "request": request, "has_result": False}


def list_runs(owner_id, project_id, db):
    owned_project(db, owner_id, project_id)
    if runs._expire_lost_runs(db, owner_id):
        db.commit()
    rows = db.scalars(select(CalculationRun).where(CalculationRun.owner_id == owner_id,
        CalculationRun.project_id == project_id, CalculationRun.request["schema"].as_string() == SCHEMA)
        .order_by(CalculationRun.created_at.desc(), CalculationRun.id.desc()).limit(50)).all()
    return [view(row, False) for row in rows]


def get(owner_id, run_id, db):
    row = runs.owned_run(db, owner_id, run_id, request_schema=SCHEMA)
    if runs._expire_lost_runs(db, owner_id):
        db.commit()
        db.refresh(row)
    return view(row)


def cancel(owner_id, run_id, db):
    row = runs.owned_run(db, owner_id, run_id, lock=True, request_schema=SCHEMA)
    runs._expire_lost_runs(db, owner_id)
    if row.status == "queued":
        row.status, row.finished_at = "canceled", utc_now()
        row.error = {"code": "run.canceled", "message": "canceled before calculation started"}
    elif row.status == "running":
        row.cancel_requested = True
    db.commit()
    return view(row)


def export(owner_id, run_id, format, db):
    row = runs.owned_run(db, owner_id, run_id, request_schema=SCHEMA)
    if format not in {"json", "csv"}:
        raise HTTPException(status_code=422, detail="format must be json or csv")
    if row.result is None:
        raise HTTPException(status_code=409, detail="run has no laboratory result")
    return serialize_report(row.result, format)
