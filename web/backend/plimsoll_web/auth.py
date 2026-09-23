"""Email challenges, owner sessions, and same-origin write checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import uuid

from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings
from .mailer import MailUnavailable
from .models import EmailChallenge, User, UserSession, utc_now


CODE_LIFETIME = timedelta(minutes=10)
SESSION_LIFETIME = timedelta(days=14)
REQUEST_GAP = timedelta(seconds=60)
IP_HOURLY_LIMIT = 10
MAX_ATTEMPTS = 5


@dataclass(frozen=True)
class LoginSession:
    user: User
    token: str
    csrf_token: str


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def normalize_email(email: str) -> str:
    try:
        return validate_email(email.strip(), check_deliverability=False).normalized.lower()
    except (EmailNotValidError, AttributeError) as error:
        raise HTTPException(status_code=422, detail="invalid email address") from error


def _code_digest(settings: Settings, challenge: EmailChallenge, code: str) -> str:
    payload = f"{challenge.id}:{challenge.email}:{code}".encode("utf-8")
    return hmac.new(settings.secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def require_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin not in request.app.state.settings.allowed_origins:
        raise HTTPException(status_code=403, detail="untrusted request origin")


def require_json(request: Request) -> None:
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        raise HTTPException(status_code=415, detail="JSON content type required")


def request_code(email: str, requester_ip: str, db: Session, mailer, settings: Settings) -> None:
    address = normalize_email(email)
    now = utc_now()
    last = db.scalar(select(EmailChallenge).where(EmailChallenge.email == address).order_by(EmailChallenge.created_at.desc()).limit(1))
    if last is not None and _aware(last.created_at) >= now - REQUEST_GAP:
        raise HTTPException(status_code=429, detail="please wait before requesting another code")
    count = db.scalar(select(func.count()).select_from(EmailChallenge).where(
        EmailChallenge.requester_ip == requester_ip,
        EmailChallenge.created_at >= now - timedelta(hours=1),
    ))
    if count is not None and count >= IP_HOURLY_LIMIT:
        raise HTTPException(status_code=429, detail="too many code requests")
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = EmailChallenge(
        email=address, requester_ip=requester_ip, digest="", expires_at=now + CODE_LIFETIME,
    )
    challenge.id = uuid.uuid4()
    challenge.digest = _code_digest(settings, challenge, code)
    db.add(challenge)
    db.commit()
    try:
        mailer.send_code(address, code)
    except (MailUnavailable, RuntimeError):
        challenge.consumed_at = utc_now()
        db.commit()
        raise HTTPException(status_code=503, detail="mail delivery unavailable") from None


def verify_code(email: str, code: str, db: Session, settings: Settings) -> LoginSession:
    address = normalize_email(email)
    now = utc_now()
    challenge = db.scalar(
        select(EmailChallenge).where(EmailChallenge.email == address)
        .order_by(EmailChallenge.created_at.desc()).with_for_update().limit(1)
    )
    if (challenge is None or challenge.consumed_at is not None
            or challenge.attempts >= MAX_ATTEMPTS or _aware(challenge.expires_at) <= now):
        raise HTTPException(status_code=400, detail="invalid or expired code")
    challenge.attempts += 1
    if not hmac.compare_digest(challenge.digest, _code_digest(settings, challenge, code)):
        db.commit()
        raise HTTPException(status_code=400, detail="invalid or expired code")
    challenge.consumed_at = now
    user = db.scalar(select(User).where(User.email == address))
    if user is None:
        user = User(email=address)
        db.add(user)
        db.flush()
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(24)
    db.add(UserSession(
        user_id=user.id, token_hash=_token_hash(token), csrf_token=csrf_token,
        expires_at=now + SESSION_LIFETIME,
    ))
    db.commit()
    return LoginSession(user=user, token=token, csrf_token=csrf_token)


def require_csrf(request: Request, session: UserSession) -> None:
    supplied = request.headers.get("x-csrf-token", "")
    if not supplied or not hmac.compare_digest(supplied, session.csrf_token):
        raise HTTPException(status_code=403, detail="CSRF token required")


def get_current_user(request: Request, db: Session) -> User:
    token = request.cookies.get("plimsoll_session")
    if not token:
        raise HTTPException(status_code=401, detail="login required")
    session = db.scalar(select(UserSession).where(UserSession.token_hash == _token_hash(token)))
    if session is None or session.revoked_at is not None or _aware(session.expires_at) <= utc_now():
        raise HTTPException(status_code=401, detail="login required")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_origin(request)
        require_json(request)
        require_csrf(request, session)
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="login required")
    request.state.user_session = session
    return user
