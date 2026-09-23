"""FastAPI routes for the private Plimsoll workspace."""

from typing import Literal

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from . import auth
from .config import Settings
from .db import get_db, make_session_factory
from .mailer import mailer_from_settings
from .models import utc_now


class CodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str


class CodeVerification(CodeRequest):
    code: str = Field(pattern=r"^\d{6}$")


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme: Literal["light", "dark"]


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Plimsoll")
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.state.mailer = mailer_from_settings(settings)

    @app.middleware("http")
    async def require_browser_write_origin(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin") not in settings.allowed_origins:
                return JSONResponse(status_code=403, content={"detail": "untrusted request origin"})
            if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
                return JSONResponse(status_code=415, content={"detail": "JSON content type required"})
        return await call_next(request)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"service": "plimsoll-web", "status": "ok"}

    @app.post("/api/auth/request-code", status_code=202)
    def request_code(body: CodeRequest, request: Request, db: Session = Depends(get_db)):
        auth.request_code(
            body.email, request.client.host if request.client else "unknown", db,
            request.app.state.mailer, settings,
        )
        return {"message": "若该邮箱可接收邮件，验证码将很快送达"}

    @app.post("/api/auth/verify-code")
    def verify_code(body: CodeVerification, response: Response, db: Session = Depends(get_db)):
        login = auth.verify_code(body.email, body.code, db, settings)
        response.set_cookie(
            "plimsoll_session", login.token, httponly=True,
            secure=not settings.allow_insecure_cookies, samesite="lax",
            max_age=int(auth.SESSION_LIFETIME.total_seconds()), path="/",
        )
        return {"id": str(login.user.id), "email": login.user.email, "theme": login.user.theme,
                "csrf_token": login.csrf_token}

    @app.get("/api/me")
    def me(request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        return {"id": str(user.id), "email": user.email, "theme": user.theme,
                "csrf_token": request.state.user_session.csrf_token}

    @app.patch("/api/me/preferences")
    def preferences(body: Preferences, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        user.theme = body.theme
        db.commit()
        return {"theme": user.theme}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response, db: Session = Depends(get_db)):
        auth.get_current_user(request, db)
        request.state.user_session.revoked_at = utc_now()
        db.commit()
        response.delete_cookie("plimsoll_session", path="/")
        return {"status": "signed_out"}

    return app
