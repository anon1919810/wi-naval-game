"""FastAPI routes for the private Plimsoll workspace."""

from typing import Literal
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from . import auth, damage_lab_runs, mass_proposals, projects, runs, ship_design, sship_imports, sps3b3
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
    template: Literal["analytic_box", "concept_cruiser", "generic_steamer", "queen_mary_1913", "ship_design"] | None
    name: str = Field(min_length=1, max_length=200)


class MassProposalsApply(BaseModel):
    """One explicit batch of reviewed proposals, applied against one saved run.

    ``current_options`` is the caller's own assembly of the request, not a hash of
    it and not the normalized form: the server normalizes it again and requires
    that it means the same thing as the request the named run was computed with.
    ``proposals`` is submitted exactly as the stored result presented it; the
    server recomputes every entry and refuses the batch if any of them differs.
    """

    model_config = ConfigDict(extra="forbid")
    base_revision: int = Field(ge=1)
    run_id: uuid.UUID
    condition_id: str = Field(min_length=1, max_length=120)
    current_options: dict = Field(default_factory=dict)
    proposals: list[dict]


class ProjectSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_revision: int = Field(ge=1)
    project: dict


class ProjectImportPreview(BaseModel):
    """A backup as it was downloaded: nothing about the destination yet."""

    model_config = ConfigDict(extra="forbid")
    project: dict


class ProjectImport(BaseModel):
    """A backup plus the name the reader confirmed for the new project.

    ``name`` is optional so the server never invents one: omitted, the backup's
    own name is kept. Supplied, it is the reader's decision and is bounded here.
    """

    model_config = ConfigDict(extra="forbid")
    project: dict
    name: str | None = Field(default=None, max_length=200)


class SshipPreview(BaseModel):
    """A SpringSharp 3.0 source file, still only a file the reader chose.

    The original bytes travel as base64 and nothing about the file is interpreted
    here: the name is a bare name, and the content is decoded and read by the
    shared core reader, which owns what those bytes mean.

    ``native`` selects the reader. Omitted (``False``) keeps the legacy mapping
    path exactly as it always was; ``True`` reads the original 3.0 *and* 2.0
    layouts through the pure codec and describes a first-class native design.
    """

    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str
    native: bool = False


class SshipImport(SshipPreview):
    """A source file plus the digest its current preview reported.

    ``source_sha256`` binds the save to the bytes that were previewed: the server
    reads the file again and refuses anything that no longer hashes to it. It is
    content binding, not proof that anybody looked at the preview.
    """

    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    name: str | None = Field(default=None, max_length=200)


class Sps3b3Preview(BaseModel):
    """A draft compatibility declaration and an optional pure edit command."""

    model_config = ConfigDict(extra="forbid")
    design: dict
    command: dict | None = None


class Sps3b3ImportPreview(BaseModel):
    """A SpringSharp source the reader chose, as bounded standard base64.

    The bounds match the ``.sship`` preview exactly: the same bare filename and
    the same maximum source size, so the compatibility reader is not a larger
    door into the same parsers.
    """

    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str


class Sps3b3FromMigration(BaseModel):
    """A project's archived original source, to be converted without mutation."""

    model_config = ConfigDict(extra="forbid")
    migration: dict


class ShipDesignInitialize(BaseModel):
    """A project draft to be initialized or upgraded into a native declaration."""

    model_config = ConfigDict(extra="forbid")
    project: dict


class ShipDesignPreview(BaseModel):
    """A project draft, an optional pure edit command and the last confirmed draft."""

    model_config = ConfigDict(extra="forbid")
    project: dict
    command: dict | None = None
    design: dict | None = None


class ShipDesignImportPreview(BaseModel):
    """A project draft plus a chosen source file, as bounded standard base64.

    The bounds match the ``.sship`` preview exactly: the same bare filename and
    the same maximum source size, so the native reader is not a larger door into
    the same parsers.
    """

    model_config = ConfigDict(extra="forbid")
    project: dict
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str


class ShipDesignFromMigration(BaseModel):
    """A project draft plus its archived original source, converted without mutation."""

    model_config = ConfigDict(extra="forbid")
    project: dict
    migration: dict


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    condition_id: str
    options: dict = Field(default_factory=dict)


class AnonymousRequest(BaseModel):
    """No fields: the workspace identity is minted by the server, never supplied."""

    model_config = ConfigDict(extra="forbid")


class DamageLabCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    condition_id: str
    experiment: dict


MAX_REQUEST_BYTES = 8 * 1024 * 1024


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Plimsoll")
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.state.mailer = mailer_from_settings(settings)

    def require_email_mode() -> None:
        if settings.auth_mode != "email":
            raise HTTPException(status_code=404, detail="email login is not available")

    @app.middleware("http")
    async def require_browser_write_origin(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            content_length = request.headers.get("content-length")
            if content_length is not None and content_length.isdigit() and int(content_length) > MAX_REQUEST_BYTES:
                return JSONResponse(status_code=413, content={"detail": "request too large"})
            if request.headers.get("origin") not in settings.allowed_origins:
                return JSONResponse(status_code=403, content={"detail": "untrusted request origin"})
            if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
                return JSONResponse(status_code=415, content={"detail": "JSON content type required"})
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                    return JSONResponse(status_code=413, content={"detail": "request too large"})
                body.extend(chunk)
            # Starlette's cached request body lets the route parse the same bounded bytes.
            request._body = bytes(body)
        return await call_next(request)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"service": "plimsoll-web", "status": "ok"}

    @app.get("/api/auth/config")
    def auth_config() -> dict[str, str]:
        return {"mode": settings.auth_mode}

    @app.post("/api/auth/anonymous")
    def anonymous(body: AnonymousRequest, request: Request, response: Response, db: Session = Depends(get_db)):
        if settings.auth_mode != "anonymous":
            raise HTTPException(status_code=404, detail="anonymous workspace is not available")
        login = auth.anonymous_workspace(
            request.client.host if request.client else "unknown", db, request,
        )
        response.set_cookie(
            "plimsoll_session", login.token, httponly=True,
            secure=not settings.allow_insecure_cookies, samesite="lax",
            max_age=int(auth.ANONYMOUS_SESSION_LIFETIME.total_seconds()), path="/",
        )
        return {"id": str(login.user.id), "email": login.user.email, "theme": login.user.theme,
                "csrf_token": login.csrf_token, "mode": "anonymous", "label": auth.ANONYMOUS_LABEL}

    @app.post("/api/auth/request-code", status_code=202)
    def request_code(body: CodeRequest, request: Request, db: Session = Depends(get_db)):
        require_email_mode()
        auth.request_code(
            body.email, request.client.host if request.client else "unknown", db,
            request.app.state.mailer, settings,
        )
        return {"message": "若该邮箱可接收邮件，验证码将很快送达"}

    @app.post("/api/auth/verify-code")
    def verify_code(body: CodeVerification, response: Response, db: Session = Depends(get_db)):
        require_email_mode()
        login = auth.verify_code(body.email, body.code, db, settings)
        response.set_cookie(
            "plimsoll_session", login.token, httponly=True,
            secure=not settings.allow_insecure_cookies, samesite="lax",
            max_age=int(auth.SESSION_LIFETIME.total_seconds()), path="/",
        )
        return {"id": str(login.user.id), "email": login.user.email, "theme": login.user.theme,
                "csrf_token": login.csrf_token, "mode": "email", "label": login.user.email}

    @app.get("/api/me")
    def me(request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        anonymous_owner = auth.is_anonymous_user(user)
        return {"id": str(user.id), "email": user.email, "theme": user.theme,
                "csrf_token": request.state.user_session.csrf_token,
                "mode": "anonymous" if anonymous_owner else "email",
                "label": auth.ANONYMOUS_LABEL if anonymous_owner else user.email}

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

    @app.post("/api/projects/import-preview")
    def preview_project_import(
        body: ProjectImportPreview, request: Request, db: Session = Depends(get_db),
    ):
        # A preview only reads the submitted document; it never touches a project,
        # so it is declared before the {project_id} routes it must not shadow.
        auth.get_current_user(request, db)
        return projects.preview_project_import(body.project)

    @app.post("/api/projects/import", status_code=201)
    def import_project(
        body: ProjectImport, request: Request, db: Session = Depends(get_db),
    ):
        user = auth.get_current_user(request, db)
        return projects.import_project(user.id, body.project, body.name, db)

    @app.post("/api/projects/sship-preview")
    def preview_sship_import(
        body: SshipPreview, request: Request, db: Session = Depends(get_db),
    ):
        # A source file preview only reads the bytes it was sent. It never looks
        # up a project, so it is declared with the other import routes it must
        # not be shadowed by.
        auth.get_current_user(request, db)
        return sship_imports.preview(body.filename, body.content_base64, native=body.native)

    @app.post("/api/projects/sship-import", status_code=201)
    def import_sship(
        body: SshipImport, request: Request, db: Session = Depends(get_db),
    ):
        user = auth.get_current_user(request, db)
        return sship_imports.import_source(
            user.id, body.filename, body.content_base64, body.source_sha256, body.name, db,
            native=body.native)

    @app.get("/api/sps3b3/catalog")
    def sps3b3_catalog(request: Request, db: Session = Depends(get_db)):
        # A read-only catalogue of the 222 effective compatibility fields. It
        # looks no project up and writes nothing.
        auth.get_current_user(request, db)
        return sps3b3.catalog()

    @app.get("/api/sps3b3/default")
    def sps3b3_default(request: Request, db: Session = Depends(get_db)):
        auth.get_current_user(request, db)
        return sps3b3.default_design()

    @app.post("/api/sps3b3/preview")
    def sps3b3_preview(
        body: Sps3b3Preview, request: Request, db: Session = Depends(get_db),
    ):
        # A pure preview: it computes a draft and returns it, never saving a
        # project or enqueuing a run.
        auth.get_current_user(request, db)
        return sps3b3.preview(body.design, body.command)

    @app.post("/api/sps3b3/import-preview")
    def sps3b3_import_preview(
        body: Sps3b3ImportPreview, request: Request, db: Session = Depends(get_db),
    ):
        auth.get_current_user(request, db)
        return sps3b3.import_preview(body.filename, body.content_base64)

    @app.post("/api/sps3b3/from-migration")
    def sps3b3_from_migration(
        body: Sps3b3FromMigration, request: Request, db: Session = Depends(get_db),
    ):
        auth.get_current_user(request, db)
        return sps3b3.from_migration(body.migration)

    @app.get("/api/design/catalog")
    def ship_design_catalog(request: Request, db: Session = Depends(get_db)):
        # A read-only catalogue of the native declaration's fields. It looks no
        # project up and writes nothing.
        auth.get_current_user(request, db)
        return ship_design.catalog()

    @app.post("/api/design/initialize")
    def ship_design_initialize(
        body: ShipDesignInitialize, request: Request, db: Session = Depends(get_db),
    ):
        # A pure preview of the resulting project: it is returned, never saved.
        auth.get_current_user(request, db)
        return ship_design.initialize(body.project)

    @app.post("/api/design/preview")
    def ship_design_preview(
        body: ShipDesignPreview, request: Request, db: Session = Depends(get_db),
    ):
        # A pure preview: it computes a native draft and returns it, never saving a
        # project or enqueuing a run.
        auth.get_current_user(request, db)
        return ship_design.preview(body.project, body.command, body.design)

    @app.post("/api/design/import-preview")
    def ship_design_import_preview(
        body: ShipDesignImportPreview, request: Request, db: Session = Depends(get_db),
    ):
        auth.get_current_user(request, db)
        return ship_design.import_preview(body.project, body.filename, body.content_base64)

    @app.post("/api/design/from-migration")
    def ship_design_from_migration(
        body: ShipDesignFromMigration, request: Request, db: Session = Depends(get_db),
    ):
        auth.get_current_user(request, db)
        return ship_design.from_migration(body.project, body.migration)

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

    @app.post("/api/projects/{project_id}/mass-proposals")
    def apply_mass_proposals(
        project_id: uuid.UUID, body: MassProposalsApply, request: Request,
        db: Session = Depends(get_db),
    ):
        user = auth.get_current_user(request, db)
        try:
            return mass_proposals.apply_selected(
                user.id, project_id, body.base_revision, body.run_id, body.condition_id,
                body.current_options, body.proposals, db)
        except projects.RevisionConflict as error:
            return JSONResponse(status_code=409, content={"current_revision": error.current_revision})

    @app.get("/api/projects/{project_id}/runs")
    def list_runs(project_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        return runs.list_runs(user.id, project_id, db)

    @app.post("/api/projects/{project_id}/runs", status_code=202)
    def enqueue_run(project_id: uuid.UUID, body: RunCreate, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        try:
            return runs.enqueue_run(user.id, project_id, body.revision, body.condition_id, body.options, db)
        except projects.RevisionConflict as error:
            return JSONResponse(status_code=409, content={"current_revision": error.current_revision})

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        return runs.get_run(user.id, run_id, db)

    @app.post("/api/runs/{run_id}/cancel")
    def cancel_run(run_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        return runs.cancel_run(user.id, run_id, db)

    @app.get("/api/runs/{run_id}/export")
    def export_run(run_id: uuid.UUID, format: str, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        data = runs.export_run(user.id, run_id, format, db)
        media_type = runs.export_media_type(format)
        if format in ("json", "csv"):
            # The two original exports keep their exact response, headers included.
            return PlainTextResponse(data, media_type=media_type)
        return Response(content=data, media_type=media_type, headers={
            "Content-Disposition": f'attachment; filename="{runs.export_filename(run_id, format)}"'})

    @app.get("/api/projects/{project_id}/damage-lab-setup")
    def lab_setup(project_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        return damage_lab_runs.setup(user.id, project_id, db)

    @app.get("/api/damage-lab-demo")
    def lab_demo(request: Request, db: Session = Depends(get_db)):
        auth.get_current_user(request, db)
        return damage_lab_runs.demo()

    @app.get("/api/projects/{project_id}/damage-lab-runs")
    def lab_list(project_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        return damage_lab_runs.list_runs(user.id, project_id, db)

    @app.post("/api/projects/{project_id}/damage-lab-runs", status_code=202)
    def lab_enqueue(project_id: uuid.UUID, body: DamageLabCreate, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        try:
            return damage_lab_runs.enqueue(user.id, project_id, body.revision, body.condition_id, body.experiment, db)
        except projects.RevisionConflict as error:
            return JSONResponse(status_code=409, content={"current_revision": error.current_revision})

    @app.post("/api/projects/{project_id}/damage-lab-preview")
    def lab_preview(project_id: uuid.UUID, body: DamageLabCreate, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        try:
            return damage_lab_runs.preview(user.id, project_id, body.revision, body.condition_id, body.experiment, db)
        except projects.RevisionConflict as error:
            return JSONResponse(status_code=409, content={"current_revision": error.current_revision})

    @app.get("/api/damage-lab-runs/{run_id}")
    def lab_read(run_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        return damage_lab_runs.get(user.id, run_id, db)

    @app.post("/api/damage-lab-runs/{run_id}/cancel")
    def lab_cancel(run_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        return damage_lab_runs.cancel(user.id, run_id, db)

    @app.get("/api/damage-lab-runs/{run_id}/export")
    def lab_export(run_id: uuid.UUID, format: str, request: Request, db: Session = Depends(get_db)):
        user = auth.get_current_user(request, db)
        data = damage_lab_runs.export(user.id, run_id, format, db)
        return PlainTextResponse(data, media_type="application/json" if format == "json" else "text/csv; charset=utf-8")

    return app
