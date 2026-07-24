"""Swappable, fail-soft outbound email delivery.

`EMAIL_PROVIDER=none` is the inert default: it records the attempt in logs and returns without
network access or an email account. `console` logs the full message for development. `smtp`
performs blocking stdlib SMTP in a worker thread and converts every delivery error into a failed
result so callers can preserve their primary flow.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Literal

from api.core.config import get_settings

logger = logging.getLogger(__name__)

EmailStatus = Literal["recorded", "sent", "failed"]


@dataclass(frozen=True, slots=True)
class EmailResult:
    """Outcome of one email delivery attempt."""

    provider: str
    status: EmailStatus
    error: str | None = None


def _send_smtp(
    *,
    message: EmailMessage,
    host: str,
    port: int,
    username: str,
    password: str,
    use_tls: bool,
) -> None:
    """Send one message synchronously. The async public API runs this function in a thread."""
    with smtplib.SMTP(host=host, port=port, timeout=15) as client:
        client.ehlo()
        if use_tls:
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
        if username:
            client.login(username, password)
        client.send_message(message)


async def send_email(
    *,
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> EmailResult:
    """Deliver through the configured provider without raising into the caller's flow."""
    settings = get_settings()
    provider = settings.email_provider.strip().lower() or "none"

    if provider == "none":
        logger.info(
            "email provider is 'none' — delivery recorded without sending to=%s subject=%s",
            to,
            subject,
        )
        return EmailResult(provider=provider, status="recorded")

    if provider == "console":
        logger.info(
            "console email\nTo: %s\nSubject: %s\n\n%s%s",
            to,
            subject,
            body_text,
            f"\n\nHTML:\n{body_html}" if body_html is not None else "",
        )
        return EmailResult(provider=provider, status="recorded")

    try:
        if provider != "smtp":
            raise ValueError(f"unknown email provider: {provider}")
        if not settings.smtp_host:
            raise ValueError("SMTP_HOST is required when EMAIL_PROVIDER=smtp")
        if not settings.smtp_from:
            raise ValueError("SMTP_FROM is required when EMAIL_PROVIDER=smtp")

        message = EmailMessage()
        message["To"] = to
        message["From"] = settings.smtp_from
        message["Subject"] = subject
        message.set_content(body_text)
        if body_html is not None:
            message.add_alternative(body_html, subtype="html")

        await asyncio.to_thread(
            _send_smtp,
            message=message,
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
        )
    except Exception as exc:
        logger.error(
            "email delivery failed provider=%s to=%s error_type=%s",
            provider,
            to,
            type(exc).__name__,
        )
        return EmailResult(provider=provider, status="failed", error=str(exc))

    logger.info("email delivered provider=smtp to=%s subject=%s", to, subject)
    return EmailResult(provider=provider, status="sent")
