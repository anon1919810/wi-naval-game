"""Email-code login, session privacy, and browser write protection."""

from datetime import timedelta
import asyncio
import ssl

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from plimsoll_web.config import Settings
from plimsoll_web.main import create_app
from plimsoll_web.mailer import SMTPMailer
from plimsoll_web.models import EmailChallenge, User, UserSession, utc_now


def request_code(client, email="a@example.com"):
    return client.post("/api/auth/request-code", json={"email": email})


def verify(client, code, email="a@example.com"):
    return client.post("/api/auth/verify-code", json={"email": email, "code": code})


def test_code_is_single_use_and_session_is_private(client, outbox, engine):
    assert request_code(client).status_code == 202
    code = outbox.last_code_for("a@example.com")
    with Session(engine) as db:
        challenge = db.scalar(select(EmailChallenge))
        assert challenge.digest != code
    first = verify(client, code)
    assert first.status_code == 200
    assert "httponly" in first.headers["set-cookie"].lower()
    assert "samesite=lax" in first.headers["set-cookie"].lower()
    assert client.get("/api/me").json()["email"] == "a@example.com"
    assert verify(client, code).status_code == 400
    with Session(engine) as db:
        assert db.query(User).count() == 1
        assert db.query(UserSession).count() == 1


def test_expired_code_cannot_create_session(client, outbox, engine):
    assert request_code(client).status_code == 202
    with Session(engine) as db:
        challenge = db.scalar(select(EmailChallenge))
        challenge.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    assert verify(client, outbox.last_code_for("a@example.com")).status_code == 400
    assert client.get("/api/me").status_code == 401


def test_five_bad_codes_exhaust_challenge_and_requests_are_limited(client, outbox):
    assert request_code(client).status_code == 202
    assert request_code(client).status_code == 429
    for _ in range(5):
        assert verify(client, "000000").status_code == 400
    assert verify(client, outbox.last_code_for("a@example.com")).status_code == 400


def test_provider_failure_is_not_login(client, outbox, engine):
    outbox.fail = True
    assert request_code(client).status_code == 503
    assert client.get("/api/me").status_code == 401
    with Session(engine) as db:
        assert db.query(UserSession).count() == 0


def test_authenticated_write_needs_origin_and_csrf(client, outbox):
    assert request_code(client).status_code == 202
    assert verify(client, outbox.last_code_for("a@example.com")).status_code == 200
    me = client.get("/api/me").json()
    assert me["theme"] == "light"
    assert client.patch("/api/me/preferences", json={"theme": "dark"}).status_code == 403
    client.headers.update({"X-CSRF-Token": me["csrf_token"]})
    assert client.patch("/api/me/preferences", json={"theme": "dark"}).json()["theme"] == "dark"
    assert client.get("/api/me").json()["theme"] == "dark"
    assert client.patch("/api/me/preferences", json={"theme": "purple"}).status_code == 422
    client.headers.update({"Origin": "https://evil.example"})
    assert client.patch("/api/me/preferences", json={"theme": "light"}).status_code == 403


def test_unauthenticated_origin_and_content_type_are_rejected(client):
    assert client.post("/api/auth/request-code", content="email=a@example.com").status_code == 415
    client.headers.update({"Origin": "https://evil.example"})
    assert request_code(client).status_code == 403


def test_existing_and_new_address_receive_the_same_external_feedback(client, outbox, engine):
    first = request_code(client)
    assert verify(client, outbox.last_code_for("a@example.com")).status_code == 200
    with Session(engine) as db:
        challenge = db.scalar(select(EmailChallenge))
        challenge.created_at = utc_now() - timedelta(minutes=2)
        db.commit()
    second = request_code(client)
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()


def test_production_cookie_is_secure_and_logout_revokes_session(engine, outbox):
    app = create_app(Settings(
        database_url=str(engine.url), secret_key="test-secret-only",
        allowed_origins=("https://plimsoll.example.com",),
    ))
    app.state.mailer = outbox
    with TestClient(app, base_url="https://plimsoll.example.com") as browser:
        browser.headers.update({"Origin": "https://plimsoll.example.com"})
        assert request_code(browser).status_code == 202
        login = verify(browser, outbox.last_code_for("a@example.com"))
        assert "secure" in login.headers["set-cookie"].lower()
        csrf = browser.get("/api/me").json()["csrf_token"]
        browser.headers.update({"X-CSRF-Token": csrf})
        assert browser.post("/api/auth/logout", json={}).status_code == 200
        assert browser.get("/api/me").status_code == 401


def test_smtp_implicit_tls_verifies_server_certificate(monkeypatch):
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, *, timeout, context):
            captured["context"] = context

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr("plimsoll_web.mailer.smtplib.SMTP_SSL", FakeSMTP)
    settings = Settings(database_url="sqlite:///unused.db", secret_key="test-secret",
                        smtp_host="mail.example.com", smtp_sender="sender@example.com")
    SMTPMailer(settings).send_code("recipient@example.com", "123456")
    assert captured["context"].verify_mode == ssl.CERT_REQUIRED
    assert captured["context"].check_hostname is True
    assert captured["message"]["To"] == "recipient@example.com"


def test_chunked_request_stops_reading_at_limit(client):
    async def exercise():
        messages = []
        received = 0
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "POST", "scheme": "http", "path": "/api/auth/request-code",
            "raw_path": b"/api/auth/request-code", "query_string": b"",
            "root_path": "", "client": ("127.0.0.1", 1234), "server": ("testserver", 80),
            "headers": [(b"origin", b"http://testserver"), (b"content-type", b"application/json")],
        }

        async def receive():
            nonlocal received
            received += 1
            if received > 9:
                raise AssertionError("body reader continued after size limit")
            return {"type": "http.request", "body": b"x" * (1024 * 1024), "more_body": True}

        async def send(message):
            messages.append(message)

        await client.app(scope, receive, send)
        assert messages[0]["status"] == 413
        assert received == 9

    asyncio.run(exercise())
