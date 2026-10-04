"""Anonymous browser workspaces: private per-cookie ownership, one mint per browser."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from plimsoll_web import auth
from plimsoll_web.config import Settings
from plimsoll_web.main import create_app
from plimsoll_web.models import User, UserSession, utc_now
from plimsoll_web.worker import work_one

ORIGIN = "http://testserver"


def _request_with_cookie(value: str) -> Request:
    """A raw latin-1 cookie header, which the ASGI layer decodes as-is."""
    return Request({"type": "http", "method": "GET", "path": "/api/me", "headers": [
        (b"host", b"testserver"),
        (b"cookie", f"plimsoll_session={value}".encode("latin-1")),
    ]})


def _force_cookie(browser, value: str) -> None:
    try:
        browser.cookies.delete("plimsoll_session")
    except KeyError:
        pass
    browser.cookies.set("plimsoll_session", value)


def _browser(engine, *, mailer=None, **overrides):
    settings = dict(
        database_url=str(engine.url), secret_key="test-secret-only",
        allowed_origins=(ORIGIN,), allow_insecure_cookies=True,
        auth_mode="anonymous",
    )
    settings.update(overrides)
    app = create_app(Settings(**settings))
    if mailer is not None:
        app.state.mailer = mailer
    browser = TestClient(app)
    browser.headers.update({"Origin": ORIGIN})
    return browser


@pytest.fixture(autouse=True)
def reset_creation_window():
    """The anonymous throttle is process-local; give each test a clean counter."""
    auth._ANONYMOUS_CREATIONS.clear()
    yield
    auth._ANONYMOUS_CREATIONS.clear()


@pytest.fixture
def workspace(engine):
    with _browser(engine) as browser:
        yield browser


def _bootstrap(browser):
    return _bootstrap_with_token(browser)[0]


def _bootstrap_with_token(browser) -> tuple[dict, str]:
    response = browser.post("/api/auth/anonymous", json={})
    assert response.status_code == 200, response.text
    body = response.json()
    browser.headers.update({"X-CSRF-Token": body["csrf_token"]})
    return body, response.cookies.get("plimsoll_session")


def test_public_auth_config_reports_mode_without_identity(workspace):
    response = workspace.get("/api/auth/config")
    assert response.status_code == 200
    assert response.json() == {"mode": "anonymous"}


def test_bootstrap_sets_secure_httponly_samesite_cookie(engine):
    with _browser(engine, allow_insecure_cookies=False) as browser:
        response = browser.post("/api/auth/anonymous", json={})
        assert response.status_code == 200
        raw = response.headers["set-cookie"]
        assert "Secure" in raw and "HttpOnly" in raw and "SameSite=lax" in raw
        assert "anonymous.invalid" in response.json()["email"]
        assert response.json()["label"] == auth.ANONYMOUS_LABEL


def test_repeated_bootstrap_reuses_the_same_owner(workspace):
    first = _bootstrap(workspace)
    second = _bootstrap(workspace)
    assert first["id"] == second["id"]
    assert workspace.get("/api/me").json()["id"] == first["id"]


def test_invalid_cookie_yields_a_fresh_workspace(workspace):
    first = _bootstrap(workspace)
    _force_cookie(workspace, "not-a-real-token")
    assert workspace.get("/api/me").status_code == 401
    assert _bootstrap(workspace)["id"] != first["id"]


def test_workspaces_are_isolated_between_browser_cookies(engine, workspace):
    mine = _bootstrap(workspace)
    project = workspace.post("/api/projects", json={"template": "analytic_box", "name": "我的方箱"})
    assert project.status_code == 201
    project_id = project.json()["project_id"]

    with _browser(engine) as other:
        assert _bootstrap(other)["id"] != mine["id"]
        assert other.get("/api/projects").json() == []
        assert other.get(f"/api/projects/{project_id}").status_code == 404
        assert other.get(f"/api/projects/{project_id}/runs").status_code == 404


def test_owner_can_save_run_and_export_inside_its_workspace(engine, workspace):
    _bootstrap(workspace)
    project_id = workspace.post(
        "/api/projects", json={"template": "analytic_box", "name": "我的方箱"},
    ).json()["project_id"]
    document = workspace.get(f"/api/projects/{project_id}").json()["project"]
    document["name"] = "修订后的方箱"
    saved = workspace.put(f"/api/projects/{project_id}", json={"base_revision": 1, "project": document})
    assert saved.status_code == 200 and saved.json()["revision"] == 2

    enqueued = workspace.post(f"/api/projects/{project_id}/runs", json={
        "revision": 2, "condition_id": "loaded", "options": {"stages": ["loading"]},
    })
    assert enqueued.status_code == 202
    assert work_one(workspace.app.state.session_factory) is True
    run_id = enqueued.json()["id"]
    assert workspace.get(f"/api/runs/{run_id}").json()["status"] == "completed"
    assert workspace.get(f"/api/runs/{run_id}/export?format=json").status_code == 200

    with _browser(engine) as stranger:
        _bootstrap(stranger)
        assert stranger.get(f"/api/runs/{run_id}").status_code == 404
        assert stranger.get(f"/api/runs/{run_id}/export?format=json").status_code == 404


def test_bootstrap_requires_same_origin_and_json(workspace):
    assert workspace.post("/api/auth/anonymous", json={},
                          headers={"Origin": "https://evil.example"}).status_code == 403
    assert workspace.post("/api/auth/anonymous", content=b"{}",
                          headers={"Content-Type": "text/plain"}).status_code == 415


def test_bootstrap_needs_no_csrf_but_owner_writes_do(workspace):
    body = workspace.post("/api/auth/anonymous", json={}).json()
    assert workspace.post("/api/projects", json={"template": "analytic_box", "name": "无 CSRF"}).status_code == 403
    allowed = workspace.post("/api/projects", json={"template": "analytic_box", "name": "有 CSRF"},
                             headers={"X-CSRF-Token": body["csrf_token"]})
    assert allowed.status_code == 201


def test_email_routes_are_unavailable_in_anonymous_mode(workspace):
    assert workspace.post("/api/auth/request-code", json={"email": "a@example.com"}).status_code == 404
    assert workspace.post("/api/auth/verify-code",
                          json={"email": "a@example.com", "code": "000000"}).status_code == 404


def test_bootstrap_is_unavailable_in_email_mode(engine):
    with _browser(engine, auth_mode="email") as browser:
        assert browser.get("/api/auth/config").json() == {"mode": "email"}
        assert browser.post("/api/auth/anonymous", json={}).status_code == 404


def test_switching_to_anonymous_does_not_adopt_an_email_account(engine, outbox):
    with _browser(engine, mailer=outbox, auth_mode="email") as email_browser:
        assert email_browser.post("/api/auth/request-code",
                                  json={"email": "carol@example.com"}).status_code == 202
        code = outbox.last_code_for("carol@example.com")
        assert email_browser.post("/api/auth/verify-code",
                                  json={"email": "carol@example.com", "code": code}).status_code == 200
        email_browser.headers.update(
            {"X-CSRF-Token": email_browser.get("/api/me").json()["csrf_token"]})
        assert email_browser.post("/api/projects", json={
            "template": "analytic_box", "name": "邮箱项目"}).status_code == 201
        carried = email_browser.cookies.get("plimsoll_session")

    with _browser(engine) as browser:
        browser.cookies.set("plimsoll_session", carried)
        assert browser.get("/api/me").status_code == 401
        assert browser.get("/api/projects").status_code == 401
        assert _bootstrap(browser)["mode"] == "anonymous"
        assert browser.get("/api/projects").json() == []

    with Session(engine) as db:
        owners = {row.email for row in db.scalars(select(User)).all()}
    assert "carol@example.com" in owners
    assert any(address.endswith("@" + auth.ANONYMOUS_EMAIL_DOMAIN) for address in owners)


def test_bootstrap_creation_is_throttled_per_address(engine):
    with _browser(engine) as browser:
        for _ in range(auth.ANONYMOUS_HOURLY_LIMIT):
            assert browser.post("/api/auth/anonymous", json={}).status_code == 200
            browser.cookies.clear()
        assert browser.post("/api/auth/anonymous", json={}).status_code == 429


def test_malformed_cookie_is_unauthorized_not_a_server_error(engine, workspace):
    _bootstrap(workspace)
    # Hashing must tolerate any cookie bytes; a dropped or over-long cookie is
    # simply unauthenticated, so the browser bootstraps a fresh workspace.
    assert auth._token_hash("café") == auth._token_hash("café")
    with Session(engine) as db:
        assert auth._browsable_token(_request_with_cookie("café")) == "café"
        assert auth._browsable_token(_request_with_cookie("x" * auth.MAX_TOKEN_LENGTH)) == "x" * auth.MAX_TOKEN_LENGTH
        assert auth._browsable_token(_request_with_cookie("x" * (auth.MAX_TOKEN_LENGTH + 1))) is None
        # A latin-1 cookie hashes without raising and simply misses the lookup.
        assert auth._browser_owner(db, _request_with_cookie("café")) is None
        assert auth._browser_owner(db, _request_with_cookie("x" * (auth.MAX_TOKEN_LENGTH + 1))) is None
    _force_cookie(workspace, "x" * (auth.MAX_TOKEN_LENGTH + 1))
    assert workspace.get("/api/me").status_code == 401
    assert workspace.get("/api/projects").status_code == 401
    assert _bootstrap(workspace)["mode"] == "anonymous"


def test_expired_and_revoked_cookies_start_a_fresh_workspace(engine, workspace):
    first, token = _bootstrap_with_token(workspace)
    with Session(engine) as db:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == auth._token_hash(token)))
        session.revoked_at = utc_now()
        db.commit()
    _force_cookie(workspace, token)
    assert workspace.get("/api/me").status_code == 401
    second, second_token = _bootstrap_with_token(workspace)
    assert second["id"] != first["id"]

    with Session(engine) as db:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == auth._token_hash(second_token)))
        session.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    _force_cookie(workspace, second_token)
    assert workspace.get("/api/me").status_code == 401
    assert _bootstrap(workspace)["id"] != second["id"]


def test_creation_throttle_purges_expired_addresses(engine):
    with _browser(engine) as browser:
        assert browser.post("/api/auth/anonymous", json={}).status_code == 200
        long_ago = utc_now() - timedelta(hours=2)
        auth._ANONYMOUS_CREATIONS["198.51.100.7"] = [long_ago]
        auth._ANONYMOUS_CREATIONS["198.51.100.8"] = [long_ago]
        browser.cookies.clear()
        assert browser.post("/api/auth/anonymous", json={}).status_code == 200
    assert "198.51.100.7" not in auth._ANONYMOUS_CREATIONS
    assert "198.51.100.8" not in auth._ANONYMOUS_CREATIONS


def test_invalid_env_auth_mode_fails_loudly(monkeypatch, engine):
    monkeypatch.setenv("PLIMSOLL_DATABASE_URL", str(engine.url))
    monkeypatch.setenv("PLIMSOLL_SECRET_KEY", "test-secret-only")
    monkeypatch.setenv("PLIMSOLL_ALLOWED_ORIGINS", ORIGIN)
    monkeypatch.setenv("PLIMSOLL_AUTH_MODE", "anonymous, please")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_auth_mode_defaults_to_email_and_reads_env(monkeypatch, engine):
    monkeypatch.setenv("PLIMSOLL_DATABASE_URL", str(engine.url))
    monkeypatch.setenv("PLIMSOLL_SECRET_KEY", "test-secret-only")
    monkeypatch.setenv("PLIMSOLL_ALLOWED_ORIGINS", ORIGIN)
    monkeypatch.delenv("PLIMSOLL_AUTH_MODE", raising=False)
    assert Settings.from_env().auth_mode == "email"
    monkeypatch.setenv("PLIMSOLL_AUTH_MODE", "anonymous")
    assert Settings.from_env().auth_mode == "anonymous"