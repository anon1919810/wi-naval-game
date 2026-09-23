"""Isolated HTTP and database fixtures for the web service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from plimsoll_web.config import Settings
from plimsoll_web.main import create_app
from plimsoll_web.models import Base


class Outbox:
    def __init__(self):
        self.messages: list[tuple[str, str]] = []
        self.fail = False

    def send_code(self, email: str, code: str) -> None:
        if self.fail:
            raise RuntimeError("mail provider unavailable")
        self.messages.append((email, code))

    def last_code_for(self, email: str) -> str:
        return next(code for address, code in reversed(self.messages) if address == email)


@pytest.fixture
def outbox():
    return Outbox()


@pytest.fixture
def engine(tmp_path):
    database = tmp_path / "web.db"
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine, outbox):
    app = create_app(Settings(
        database_url=str(engine.url), secret_key="test-secret-only",
        allowed_origins=("http://testserver",), allow_insecure_cookies=True,
    ))
    app.state.mailer = outbox
    with TestClient(app) as browser:
        browser.headers.update({"Origin": "http://testserver"})
        yield browser
