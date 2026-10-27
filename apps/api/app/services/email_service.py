"""Email service — verification-code delivery via SMTP or the mock provider.

Mirrors the LLM/Image service factory pattern: provider is read from admin
settings (``email_provider``: "mock" | "smtp"). The mock provider logs the
email instead of sending it — intended for local dev / internal deployments
without an SMTP relay; callers may surface the code to the UI in that mode.
"""

import logging
from email.message import EmailMessage
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class MockEmailSender:
    """Logs the email — no network. Dev/local mode."""

    async def send(self, to: str, subject: str, body: str) -> None:
        logger.info("[mock-email] to=%s subject=%s\n%s", to, subject, body)


class SmtpEmailSender:
    """Sends via SMTP using admin-configured credentials (aiosmtplib)."""

    def __init__(self, host: str, port: int, user: str, password: str, sender: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sender = sender

    async def send(self, to: str, subject: str, body: str) -> None:
        import aiosmtplib

        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        await aiosmtplib.send(
            message,
            hostname=self.host,
            port=self.port,
            username=self.user or None,
            password=self.password or None,
            start_tls=self.port == 587,
        )


async def get_email_sender(db: AsyncSession) -> EmailSender:
    from app.services.settings_service import SettingsService

    cfg = await SettingsService.get_raw_many(db, [
        "email_provider", "smtp_host", "smtp_port",
        "smtp_user", "smtp_password", "smtp_from",
    ])
    if cfg["email_provider"] == "smtp" and cfg["smtp_host"]:
        return SmtpEmailSender(
            host=cfg["smtp_host"],
            port=int(cfg["smtp_port"] or 587),
            user=cfg["smtp_user"],
            password=cfg["smtp_password"],
            sender=cfg["smtp_from"] or cfg["smtp_user"] or "noreply@ai-team.local",
        )
    return MockEmailSender()


def is_mock_provider(provider: str) -> bool:
    return provider != "smtp"
