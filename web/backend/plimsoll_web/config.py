"""Service settings supplied by the local operator."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ["PLIMSOLL_DATABASE_URL"],
            secret_key=os.environ["PLIMSOLL_SECRET_KEY"],
        )
