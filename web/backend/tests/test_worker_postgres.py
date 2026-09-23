"""Verify SKIP LOCKED against a disposable PostgreSQL database."""

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from plimsoll_web.models import Base, CalculationRun, Project, ProjectRevision, User
from plimsoll_web.worker import claim_next_run


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="disposable PostgreSQL URL not configured")
def test_two_transactions_cannot_claim_the_same_run():
    url = os.environ["TEST_DATABASE_URL"]
    assert url.startswith("postgresql"), "TEST_DATABASE_URL must be PostgreSQL"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    user_id, project_id, run_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with Session(engine) as db:
        db.add(User(id=user_id, email=f"claim-{uuid.uuid4().hex}@example.com"))
        db.flush()
        db.add(Project(id=project_id, owner_id=user_id, name="claim fixture", current_revision=1))
        db.flush()
        db.add(ProjectRevision(project_id=project_id, revision=1, document={"schema": "plimsoll-project-1"}))
        db.flush()
        db.add(CalculationRun(
            id=run_id, owner_id=user_id, project_id=project_id, revision=1,
            condition_id="loaded", request={"options": {}}, input_snapshot={},
            request_fingerprint="0" * 64, status="queued",
        ))
        db.commit()
    with Session(engine) as first, Session(engine) as second:
        assert claim_next_run(first).id == run_id
        assert claim_next_run(second) is None
        first.commit()
        second.rollback()
    engine.dispose()
