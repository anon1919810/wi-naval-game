"""Owner-scoped calculation queue and immutable result access."""

from __future__ import annotations

from datetime import datetime
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from plimsoll import _analysis_request, exports

from .models import CalculationRun, ProjectRevision, User, utc_now
from .projects import RevisionConflict, owned_project


ACTIVE = ("queued", "running")
ANALYSIS_SCHEMA = "plimsoll-analysis-request-1"


def expire_lost_runs(db: Session, owner_id: uuid.UUID | None = None) -> int:
    """Atomically recover only rows that are still running with an expired lease.

    The status predicate is rechecked by the database at the write, including
    SQLite where a preceding SELECT FOR UPDATE would not lock the row.
    """
    now = utc_now()
    statement = update(CalculationRun).where(
        CalculationRun.status == "running",
        CalculationRun.lease_expires_at < now)
    if owner_id is not None:
        statement = statement.where(CalculationRun.owner_id == owner_id)
    result = db.execute(statement.values(status='failed', finished_at=now,
        lease_expires_at=None, result=None,
        error={"code": "run.worker_lost", "message": "calculation worker stopped before reporting a result"}),
        execution_options={'synchronize_session': 'fetch'})
    return result.rowcount


def _expire_lost_runs(db: Session, owner_id: uuid.UUID) -> bool:
    """Recover this owner's expired worker leases during ordinary API traffic."""
    return expire_lost_runs(db, owner_id) > 0


def _run_view(row: CalculationRun, *, include_result: bool = True) -> dict:
    return {
        "id": str(row.id), "project_id": str(row.project_id), "revision": row.revision,
        "condition_id": row.condition_id, "status": row.status,
        "request_fingerprint": row.request_fingerprint,
        "created_at": row.created_at.isoformat() if isinstance(row.created_at, datetime) else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "cancel_requested": row.cancel_requested,
        "result": row.result if include_result else None,
        "error": row.error,
    }


def owned_run(db: Session, owner_id: uuid.UUID, run_id: uuid.UUID, *, lock: bool = False,
              request_schema: str = ANALYSIS_SCHEMA) -> CalculationRun:
    query = select(CalculationRun).where(CalculationRun.id == run_id, CalculationRun.owner_id == owner_id)
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None or row.request.get("schema") != request_schema:
        raise HTTPException(status_code=404, detail="run not found")
    return row


def enqueue_run(
    owner_id: uuid.UUID, project_id: uuid.UUID, revision: int,
    condition_id: str, options: dict, db: Session,
) -> dict:
    project = owned_project(db, owner_id, project_id)
    if project.current_revision != revision:
        raise RevisionConflict(project.current_revision)
    saved = db.get(ProjectRevision, (project_id, revision))
    if saved is None:
        raise RuntimeError("project current revision is missing")
    try:
        snapshot, request, fingerprint = _analysis_request.normalize(saved.document, condition_id, options)
    except _analysis_request.AnalysisInputError as error:
        raise HTTPException(status_code=422, detail=error.diagnostics) from error
    return enqueue_snapshot(owner_id, project_id, revision, condition_id, snapshot, request, fingerprint, db)


def enqueue_snapshot(owner_id, project_id, revision, condition_id, snapshot, request, fingerprint, db):
    """One admission limit across every validated calculation request kind."""
    db.scalar(select(User).where(User.id == owner_id).with_for_update())
    _expire_lost_runs(db, owner_id)
    active = db.scalar(select(func.count()).select_from(CalculationRun).where(
        CalculationRun.owner_id == owner_id, CalculationRun.status.in_(ACTIVE),
    ))
    if active:
        raise HTTPException(status_code=429, detail="one active calculation is allowed per account")
    row = CalculationRun(
        owner_id=owner_id, project_id=project_id, revision=revision,
        condition_id=condition_id, request=request, input_snapshot=snapshot,
        request_fingerprint=fingerprint, status="queued",
    )
    db.add(row)
    db.commit()
    return _run_view(row)


def list_runs(owner_id: uuid.UUID, project_id: uuid.UUID, db: Session) -> list[dict]:
    owned_project(db, owner_id, project_id)
    if _expire_lost_runs(db, owner_id):
        db.commit()
    rows = db.scalars(select(CalculationRun).where(
        CalculationRun.owner_id == owner_id, CalculationRun.project_id == project_id,
        CalculationRun.request["schema"].as_string() == ANALYSIS_SCHEMA,
    ).order_by(CalculationRun.created_at.desc(), CalculationRun.id.desc())).all()
    return [_run_view(row, include_result=False) for row in rows]


def get_run(owner_id: uuid.UUID, run_id: uuid.UUID, db: Session) -> dict:
    row = owned_run(db, owner_id, run_id)
    if _expire_lost_runs(db, owner_id):
        db.commit()
        db.refresh(row)
    return _run_view(row)


def cancel_run(owner_id: uuid.UUID, run_id: uuid.UUID, db: Session) -> dict:
    row = owned_run(db, owner_id, run_id, lock=True)
    _expire_lost_runs(db, owner_id)
    if row.status == "queued":
        row.status = "canceled"
        row.finished_at = utc_now()
        row.error = {"code": "run.canceled", "message": "canceled before calculation started"}
    elif row.status == "running":
        row.cancel_requested = True
    db.commit()
    return _run_view(row)


def export_run(owner_id: uuid.UUID, run_id: uuid.UUID, format: str, db: Session) -> str:
    row = owned_run(db, owner_id, run_id)
    if format not in {"json", "csv"}:
        raise HTTPException(status_code=422, detail="format must be json or csv")
    if row.result is None:
        raise HTTPException(status_code=409, detail="run has no analysis result")
    return exports.serialize_report(row.result, format=format)
