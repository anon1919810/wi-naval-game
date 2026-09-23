"""Service settings supplied by the local operator."""

from __future__ import annotations

from dataclasses import dataclass
import os


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
        )
