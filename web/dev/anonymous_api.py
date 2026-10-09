"""Anonymous loopback preview using an existing, migrated SQLite database."""
from __future__ import annotations

import argparse
from contextlib import closing
from pathlib import Path
import secrets
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "web/backend")]
REQUIRED_TABLES = {"users", "user_sessions", "projects", "project_revisions", "calculation_runs"}


def check_database(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"Existing database not found: {path}")
    # URI read-only mode cannot create a missing database or alter its schema.
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = REQUIRED_TABLES - tables
    if missing:
        raise ValueError("Database needs existing migrations; missing tables: " + ", ".join(sorted(missing)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    database = args.database.resolve()
    try:
        check_database(database)
    except (ValueError, sqlite3.Error) as error:
        parser.exit(1, f"Local preview: {error}\n")
    if args.check_only:
        print("Existing database schema checked (read-only).")
        return

    from sqlalchemy.engine import URL
    from plimsoll_web.config import Settings
    from plimsoll_web.main import create_app
    import uvicorn

    settings = Settings(
        database_url=URL.create("sqlite+pysqlite", database=database.as_posix()).render_as_string(),
        secret_key=secrets.token_urlsafe(48),
        allowed_origins=("http://127.0.0.1:5173",),
        allow_insecure_cookies=True,
        auth_mode="anonymous",
    )
    uvicorn.run(create_app(settings), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
