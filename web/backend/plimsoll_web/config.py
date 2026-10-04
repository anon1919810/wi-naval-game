"""Service settings supplied by the local operator."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Literal


AuthMode = Literal["email", "anonymous"]

AUTH_MODES = ("email", "anonymous")
DEFAULT_AUTH_MODE: AuthMode = "email"


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    allowed_origins: tuple[str, ...] = ()
    allow_insecure_cookies: bool = False
    smtp_host: str | None = None
    smtp_port: int = 465
    smtp_sender: str | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    local_mail_test: bool = False
    auth_mode: AuthMode = DEFAULT_AUTH_MODE

    def __post_init__(self) -> None:
        if self.auth_mode not in AUTH_MODES:
            raise ValueError(
                f"auth_mode must be one of {AUTH_MODES}, got {self.auth_mode!r}"
            )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ["PLIMSOLL_DATABASE_URL"],
            secret_key=os.environ["PLIMSOLL_SECRET_KEY"],
            allowed_origins=tuple(
                item.strip() for item in os.environ["PLIMSOLL_ALLOWED_ORIGINS"].split(",")
                if item.strip()
            ),
            allow_insecure_cookies=os.environ.get("PLIMSOLL_LOCAL_HTTP") == "1",
            smtp_host=os.environ.get("PLIMSOLL_SMTP_HOST"),
            smtp_port=int(os.environ.get("PLIMSOLL_SMTP_PORT", "465")),
            smtp_sender=os.environ.get("PLIMSOLL_SMTP_SENDER"),
            smtp_username=os.environ.get("PLIMSOLL_SMTP_USERNAME"),
            smtp_password=os.environ.get("PLIMSOLL_SMTP_PASSWORD"),
            local_mail_test=os.environ.get("PLIMSOLL_LOCAL_MAIL_TEST") == "1",
            auth_mode=os.environ.get("PLIMSOLL_AUTH_MODE", DEFAULT_AUTH_MODE).strip().lower(),
        )
