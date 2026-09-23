"""Outbound code delivery. The default never silently accepts mail."""

from __future__ import annotations

from email.message import EmailMessage
import smtplib
import ssl
from urllib.parse import urlsplit

from .config import Settings


class MailUnavailable(RuntimeError):
    """Report an unavailable delivery channel without exposing credentials."""


class UnavailableMailer:
    def send_code(self, email: str, code: str) -> None:
        raise MailUnavailable("mail delivery is not configured")


class ConsoleMailer:
    """Explicit local-only development outbox; never send a real email."""

    def send_code(self, email: str, code: str) -> None:
        print(f"PLIMSOLL LOCAL TEST CODE for {email}: {code}", flush=True)


class SMTPMailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send_code(self, email: str, code: str) -> None:
        config = self.settings
        if not config.smtp_host or not config.smtp_sender:
            raise MailUnavailable("mail delivery is not configured")
        message = EmailMessage()
        message["From"] = config.smtp_sender
        message["To"] = email
        message["Subject"] = "Plimsoll 登录验证码"
        message.set_content(f"你的 Plimsoll 验证码是 {code}。10 分钟内有效，仅可使用一次。")
        try:
            if config.smtp_port == 465:
                connection = smtplib.SMTP_SSL(
                    config.smtp_host, config.smtp_port, timeout=10,
                    context=ssl.create_default_context(),
                )
            else:
                connection = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)
            with connection as smtp:
                if config.smtp_port != 465:
                    smtp.starttls(context=ssl.create_default_context())
                if config.smtp_username and config.smtp_password:
                    smtp.login(config.smtp_username, config.smtp_password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            raise MailUnavailable("mail delivery failed") from error


def mailer_from_settings(settings: Settings) -> SMTPMailer | UnavailableMailer | ConsoleMailer:
    if settings.local_mail_test:
        loopback_origins = bool(settings.allowed_origins) and all(
            urlsplit(origin).scheme == "http"
            and urlsplit(origin).hostname in {"localhost", "127.0.0.1", "[::1]", "::1"}
            for origin in settings.allowed_origins
        )
        if not settings.allow_insecure_cookies or not loopback_origins:
            raise MailUnavailable("local mail test requires loopback HTTP origins")
        return ConsoleMailer()
    if settings.smtp_host and settings.smtp_sender:
        return SMTPMailer(settings)
    return UnavailableMailer()
