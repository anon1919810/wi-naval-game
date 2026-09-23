"""PostgreSQL-specific row locking for one-time email challenges."""

from concurrent.futures import ThreadPoolExecutor
import os
import uuid

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from plimsoll_web import auth
from plimsoll_web.config import Settings
from plimsoll_web.models import Base, User, UserSession


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="disposable PostgreSQL URL not configured")
def test_concurrent_verification_consumes_one_code_once():
    url = os.environ["TEST_DATABASE_URL"]
    assert url.startswith("postgresql"), "TEST_DATABASE_URL must be PostgreSQL"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    address = f"concurrency-{uuid.uuid4().hex}@example.com"
    settings = Settings(database_url=url, secret_key="test-secret-only")

    class Outbox:
        code = ""

        def send_code(self, email: str, code: str) -> None:
            self.code = code

    outbox = Outbox()
    with Session(engine) as db:
        auth.request_code(address, "127.0.0.1", db, outbox, settings)

    def attempt() -> str:
        with Session(engine) as db:
            try:
                auth.verify_code(address, outbox.code, db, settings)
                return "accepted"
            except HTTPException as error:
                return f"rejected-{error.status_code}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: attempt(), range(2)))
    assert sorted(outcomes) == ["accepted", "rejected-400"]
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == address))
        assert user is not None
        assert len(db.scalars(select(UserSession).where(UserSession.user_id == user.id)).all()) == 1
    engine.dispose()
