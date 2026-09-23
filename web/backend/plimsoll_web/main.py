"""FastAPI application factory."""

from fastapi import FastAPI

from .config import Settings
from .db import make_session_factory


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Plimsoll")
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"service": "plimsoll-web", "status": "ok"}

    return app
