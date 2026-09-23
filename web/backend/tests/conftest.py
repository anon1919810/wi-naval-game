"""Isolated HTTP and database fixtures for the web service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from plimsoll_web.config import Settings
from plimsoll_web.main import create_app
from plimsoll_web.models import Base


@pytest.fixture
def engine(tmp_path):
    database = tmp_path / "web.db"
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine):
    app = create_app(Settings(database_url=str(engine.url), secret_key="test-secret-only"))
    with TestClient(app) as browser:
        yield browser
