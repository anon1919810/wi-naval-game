"""One bounded database-claimed calculation worker."""

from __future__ import annotations

from datetime import timedelta
import multiprocessing
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from plimsoll import analysis, exports

from .config import Settings
from .db import make_session_factory
from .models import CalculationRun, utc_now


MAX_SECONDS = 120
MAX_RESULT_BYTES = 32 * 1024 * 1024
CANCEL_GRACE_SECONDS = 2


def recover_expired_runs(factory: sessionmaker[Session]) -> int:
    """Keep a lost process visible as failed rather than running forever."""
    with factory.begin() as db:
        rows = db.scalars(
            select(CalculationRun).where(
                CalculationRun.status == "running",
                CalculationRun.lease_expires_at < utc_now(),
            ).with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            row.status = "failed"
            row.finished_at = utc_now()
            row.error = {"code": "run.worker_lost", "message": "calculation worker stopped before reporting a result"}
        return len(rows)


def claim_next_run(db: Session) -> CalculationRun | None:
    """Claim one queue row in the caller's transaction."""
    row = db.scalar(
        select(CalculationRun).where(CalculationRun.status == "queued")
        .order_by(CalculationRun.created_at, CalculationRun.id)
        .with_for_update(skip_locked=True).limit(1)
    )
    if row is not None:
        row.status = "running"
        row.started_at = utc_now()
        row.lease_expires_at = row.started_at + timedelta(seconds=MAX_SECONDS)
        db.flush()
    return row


def _compute_child(snapshot: dict, request: dict, stop, writer) -> None:
    try:
        result = analysis.compute_project(
            snapshot, request["condition_id"], request["options"],
            cancel_check=stop.is_set,
        )
        writer.send(("result", result))
    except Exception as error:
        writer.send(("error", {"code": "run.calculation_failed", "message": str(error)[:500],
                               "diagnostics": getattr(error, "diagnostics", [])}))
    finally:
        writer.close()


def _run_bounded(snapshot: dict, request: dict, check_cancel) -> tuple[str, dict]:
    context = multiprocessing.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    stop = context.Event()
    process = context.Process(target=_compute_child, args=(snapshot, request, stop, writer), daemon=True)
    process.start()
    writer.close()
    deadline = time.monotonic() + MAX_SECONDS
    canceled_at = None
    outcome: tuple[str, dict] | None = None
    try:
        while True:
            if reader.poll(0.2):
                try:
                    outcome = reader.recv()
                except EOFError:
                    outcome = None
                break
            if not process.is_alive():
                break
            if check_cancel() and canceled_at is None:
                stop.set()
                canceled_at = time.monotonic()
            if canceled_at is not None and time.monotonic() - canceled_at > CANCEL_GRACE_SECONDS:
                return ("canceled", {"code": "run.canceled", "message": "canceled during calculation"})
            if time.monotonic() > deadline:
                return ("error", {"code": "run.timeout", "message": "calculation exceeded its time limit"})
        if outcome is not None:
            return outcome
        return ("error", {"code": "run.worker_failed", "message": "calculation process exited without a result"})
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=3)
        if process.is_alive():
            process.kill()
            process.join(timeout=3)
        reader.close()


def execute_run(run_id: uuid.UUID, factory: sessionmaker[Session], cancel_check=None) -> None:
    with factory() as db:
        row = db.get(CalculationRun, run_id)
        if row is None or row.status != "running":
            return
        snapshot, request, fingerprint = row.input_snapshot, row.request, row.request_fingerprint

    def canceled() -> bool:
        if cancel_check is not None and cancel_check():
            return True
        with factory() as db:
            row = db.get(CalculationRun, run_id)
            return row is None or row.cancel_requested or row.status != "running"

    try:
        kind, payload = _run_bounded(snapshot, request, canceled)
        if kind == "result":
            serialized = exports.serialize_report(payload, format="json")
            if len(serialized.encode("utf-8")) > MAX_RESULT_BYTES:
                kind, payload = "error", {"code": "run.result_too_large", "message": "analysis result exceeds storage limit"}
            elif payload.get("request_fingerprint") != fingerprint:
                kind, payload = "error", {"code": "run.identity_mismatch", "message": "analysis request identity changed"}
    except Exception as error:
        kind, payload = "error", {"code": "run.worker_failed", "message": str(error)[:500]}

    with factory.begin() as db:
        row = db.get(CalculationRun, run_id)
        if row is None or row.status != "running":
            return
        row.finished_at = utc_now()
        row.lease_expires_at = None
        if kind == "result":
            row.result = payload
            row.status = payload["status"]
            row.error = None
        elif kind == "canceled":
            row.status = "canceled"
            row.error = payload
        else:
            row.status = "failed"
            row.error = payload


def work_one(factory: sessionmaker[Session]) -> bool:
    recover_expired_runs(factory)
    with factory.begin() as db:
        row = claim_next_run(db)
        run_id = row.id if row is not None else None
    if run_id is None:
        return False
    execute_run(run_id, factory)
    return True


def main() -> None:
    factory = make_session_factory(Settings.from_env().database_url)
    while True:
        if not work_one(factory):
            time.sleep(1)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
