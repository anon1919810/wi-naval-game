"""Isolated HTTP and database fixtures for the web service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from plimsoll_web.config import Settings
from plimsoll_web.db import make_engine
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
    engine = make_engine(f"sqlite+pysqlite:///{database}")
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


def _signed_in_browser(engine, outbox, email: str):
    app = create_app(Settings(
        database_url=str(engine.url), secret_key="test-secret-only",
        allowed_origins=("http://testserver",), allow_insecure_cookies=True,
    ))
    app.state.mailer = outbox
    browser = TestClient(app)
    browser.headers.update({"Origin": "http://testserver"})
    assert browser.post("/api/auth/request-code", json={"email": email}).status_code == 202
    code = outbox.last_code_for(email)
    assert browser.post("/api/auth/verify-code", json={"email": email, "code": code}).status_code == 200
    browser.headers.update({"X-CSRF-Token": browser.get("/api/me").json()["csrf_token"]})
    return browser


@pytest.fixture
def alice(engine, outbox):
    with _signed_in_browser(engine, outbox, "alice@example.com") as browser:
        yield browser


@pytest.fixture
def bob(engine, outbox):
    with _signed_in_browser(engine, outbox, "bob@example.com") as browser:
        yield browser


@pytest.fixture
def project_id(alice):
    response = alice.post("/api/projects", json={"template": "analytic_box", "name": "解析方箱"})
    assert response.status_code == 201
    return response.json()["project_id"]


@pytest.fixture
def saved_document(alice, project_id):
    return alice.get(f"/api/projects/{project_id}").json()["project"]
