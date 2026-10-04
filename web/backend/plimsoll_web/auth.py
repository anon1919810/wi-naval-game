"""Email challenges, owner sessions, and same-origin write checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import threading
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
ANONYMOUS_SESSION_LIFETIME = timedelta(days=365)
REQUEST_GAP = timedelta(seconds=60)
IP_HOURLY_LIMIT = 10
MAX_ATTEMPTS = 5

# Reserved, non-deliverable identity domain (RFC 2606) for browser-cookie workspaces.
ANONYMOUS_EMAIL_DOMAIN = "anonymous.invalid"
ANONYMOUS_LABEL = "本浏览器工作区"
ANONYMOUS_HOURLY_LIMIT = 30
MAX_TOKEN_LENGTH = 512

# Bounded process-local throttle for anonymous workspace creation. It is not a
# durable registry: counters reset when the API process restarts, and the
# deployment edge adds its own rate limiting. See web-production-operations.md.
_CREATE_LOCK = threading.Lock()
_ANONYMOUS_CREATIONS: dict[str, list[datetime]] = {}


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
    # Valid session tokens are URL-safe ASCII, so this stays compatible with
    # existing rows; a malformed cookie must miss the lookup, never raise.
    return hashlib.sha256(token.encode("utf-8", "replace")).hexdigest()


def _browsable_token(request: Request | None) -> str | None:
    """Read the session cookie only when it has a plausible shape."""
    token = request.cookies.get("plimsoll_session") if request is not None else None
    if not token or len(token) > MAX_TOKEN_LENGTH:
        return None
    return token


def is_anonymous_user(user: User) -> bool:
    """Recognise a browser-cookie workspace by its reserved identity."""
    return user.email.endswith("@" + ANONYMOUS_EMAIL_DOMAIN)


def issue_session(db: Session, user: User, lifetime: timedelta) -> LoginSession:
    """Mint one session row with the existing hashing and CSRF contract."""
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(24)
    db.add(UserSession(
        user_id=user.id, token_hash=_token_hash(token), csrf_token=csrf_token,
        expires_at=utc_now() + lifetime,
    ))
    db.commit()
    return LoginSession(user=user, token=token, csrf_token=csrf_token)


def _check_anonymous_creation_rate(requester_ip: str, now: datetime) -> bool:
    """Sliding one-hour window per requester address; False when throttled.

    Expired addresses are purged here, so retained memory is bounded by the
    addresses seen in the current hour rather than growing without limit.
    """
    with _CREATE_LOCK:
        for address in [key for key in _ANONYMOUS_CREATIONS
                        if not any(now - stamp < timedelta(hours=1)
                                   for stamp in _ANONYMOUS_CREATIONS[key])]:
            del _ANONYMOUS_CREATIONS[address]
        window = [stamp for stamp in _ANONYMOUS_CREATIONS.get(requester_ip, [])
                  if now - stamp < timedelta(hours=1)]
        _ANONYMOUS_CREATIONS[requester_ip] = window
        if len(window) >= ANONYMOUS_HOURLY_LIMIT:
            return False
        window.append(now)
        return True


def _browser_owner(db: Session, request: Request | None) -> User | None:
    """The anonymous owner already held by this browser cookie, if any."""
    token = _browsable_token(request)
    if token is None:
        return None
    session = db.scalar(select(UserSession).where(UserSession.token_hash == _token_hash(token)))
    if session is None or session.revoked_at is not None or _aware(session.expires_at) <= utc_now():
        return None
    user = db.get(User, session.user_id)
    return user if user is not None and is_anonymous_user(user) else None


def anonymous_workspace(requester_ip: str, db: Session, request: Request | None = None) -> LoginSession:
    """Reuse this browser's workspace, or mint exactly one new anonymous owner."""
    existing = _browser_owner(db, request)
    if existing is not None:
        return issue_session(db, existing, ANONYMOUS_SESSION_LIFETIME)
    if not _check_anonymous_creation_rate(requester_ip, utc_now()):
        raise HTTPException(status_code=429, detail="too many workspaces from this address")
    user = User(email=f"anonymous-{secrets.token_hex(16)}@{ANONYMOUS_EMAIL_DOMAIN}")
    db.add(user)
    db.flush()
    return issue_session(db, user, ANONYMOUS_SESSION_LIFETIME)


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
    return issue_session(db, user, SESSION_LIFETIME)


def require_csrf(request: Request, session: UserSession) -> None:
    supplied = request.headers.get("x-csrf-token", "")
    if not supplied or not hmac.compare_digest(supplied, session.csrf_token):
        raise HTTPException(status_code=403, detail="CSRF token required")


def get_current_user(request: Request, db: Session) -> User:
    token = _browsable_token(request)
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
    settings = request.app.state.settings
    if settings.auth_mode == "anonymous" and not is_anonymous_user(user):
        # Switching a deployment to browser workspaces must not adopt email
        # accounts as anonymous owners; those browsers bootstrap a fresh owner.
        raise HTTPException(status_code=401, detail="login required")
    request.state.user_session = session
    return user
