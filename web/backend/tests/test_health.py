"""The service starts against a migrated database with the required ownership schema."""

from sqlalchemy import inspect


def test_health_returns_version(client):
    assert client.get("/api/health").json() == {"service": "plimsoll-web", "status": "ok"}


def test_schema_has_owner_and_revision_columns(engine):
    names = set(inspect(engine).get_table_names())
    assert {"users", "projects", "project_revisions", "calculation_runs"} <= names
    assert {"owner_id", "current_revision"} <= {
        column["name"] for column in inspect(engine).get_columns("projects")
    }
