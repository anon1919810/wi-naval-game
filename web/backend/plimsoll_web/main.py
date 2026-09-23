"""FastAPI routes for the private Plimsoll workspace."""

from typing import Literal
import uuid

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from . import auth, projects
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


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template: Literal["analytic_box", "generic_steamer", "queen_mary_1913"] | None
    name: str = Field(min_length=1, max_length=200)


class ProjectSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_revision: int = Field(ge=1)
    project: dict


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Plimsoll")
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.state.mailer = mailer_from_settings(settings)

    @app.middleware("http")
    async def require_browser_write_origin(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            content_length = request.headers.get("content-length")
            if content_length is not None and content_length.isdigit() and int(content_length) > 8 * 1024 * 1024:
                return JSONResponse(status_code=413, content={"detail": "request too large"})
            if request.headers.get("origin") not in settings.allowed_origins:
                return JSONResponse(status_code=403, content={"detail": "untrusted request origin"})
            if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
                return JSONResponse(status_code=415, content={"detail": "JSON content type required"})
            if len(await request.body()) > 8 * 1024 * 1024:
                return JSONResponse(status_code=413, content={"detail": "request too large"})
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

    @app.get("/api/projects")
    def list_projects(request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        return projects.list_projects(user.id, db)

    @app.post("/api/projects", status_code=201)
    def create_project(body: ProjectCreate, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        return projects.create_project(user.id, body.template, body.name, db)

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        return projects.get_project(user.id, project_id, db)

    @app.put("/api/projects/{project_id}")
    def save_project(project_id: uuid.UUID, body: ProjectSave, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        try:
            return projects.save_project(user.id, project_id, body.base_revision, body.project, db)
        except projects.RevisionConflict as error:
            return JSONResponse(status_code=409, content={"current_revision": error.current_revision})

    @app.delete("/api/projects/{project_id}", status_code=204)
    def delete_project(project_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        projects.delete_project(user.id, project_id, db)

    return app
