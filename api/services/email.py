"""Swappable, fail-soft outbound email delivery.

`EMAIL_PROVIDER=none` is the inert default: it records the attempt in logs and returns without
network access or an email account. `console` logs the full message for development. `smtp`
performs blocking stdlib SMTP in a worker thread. `graph` uses Microsoft Graph's app-only OAuth2
flow and caches its access token until expiry. Every network path converts delivery errors into a
failed result so callers can preserve their primary flow.
"""

from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Literal

from api.core.config import get_settings

logger = logging.getLogger(__name__)

EmailStatus = Literal["recorded", "sent", "failed"]
_GRAPH_SCOPE = "https://graph.microsoft.com/.default"
_GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
_GRAPH_TOKEN_EXPIRY_SKEW = 60


@dataclass(frozen=True, slots=True)
class EmailResult:
    """Outcome of one email delivery attempt."""

    provider: str
    status: EmailStatus
    error: str | None = None


@dataclass(frozen=True, slots=True)
class _GraphToken:
    access_token: str
    expires_at: float
    cache_key: tuple[str, str]


_graph_token_cache: _GraphToken | None = None


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


def _post_form(url: str, fields: dict[str, str]) -> dict[str, object]:
    """POST a form-encoded OAuth request and decode its JSON response."""
    body = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
        return json.loads(response.read())


def _post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, object],
) -> None:
    """POST a JSON request whose successful response has no useful body."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15):  # noqa: S310
        return


def _get_graph_access_token(
    *,
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> str:
    """Return a cached app-only Graph token, refreshing before its hard expiry."""
    global _graph_token_cache

    cache_key = (tenant_id, client_id)
    now = time.time()
    cached = _graph_token_cache
    if (
        cached is not None
        and cached.cache_key == cache_key
        and now < cached.expires_at - _GRAPH_TOKEN_EXPIRY_SKEW
    ):
        return cached.access_token

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    response = _post_form(
        token_url,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            "scope": _GRAPH_SCOPE,
        },
    )
    access_token = response.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise ValueError("Graph token response did not include an access_token")
    try:
        expires_in = int(response.get("expires_in", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("Graph token response included an invalid expires_in") from exc

    _graph_token_cache = _GraphToken(
        access_token=access_token,
        expires_at=now + max(expires_in, 0),
        cache_key=cache_key,
    )
    return access_token


def _send_graph(
    *,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    sender: str,
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None,
) -> None:
    """Acquire an app-only token and submit one Microsoft Graph sendMail request."""
    access_token = _get_graph_access_token(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    body = {
        "contentType": "HTML" if body_html is not None else "Text",
        "content": body_html if body_html is not None else body_text,
    }
    payload: dict[str, object] = {
        "message": {
            "subject": subject,
            "body": body,
            "toRecipients": [{"emailAddress": {"address": to}}],
        }
    }
    encoded_sender = urllib.parse.quote(sender, safe="@.")
    _post_json(
        f"{_GRAPH_API_BASE}/users/{encoded_sender}/sendMail",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        payload=payload,
    )


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
        if provider == "smtp":
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
        elif provider == "graph":
            missing = [
                name
                for name, value in (
                    ("GRAPH_TENANT_ID", settings.graph_tenant_id),
                    ("GRAPH_CLIENT_ID", settings.graph_client_id),
                    ("GRAPH_CLIENT_SECRET", settings.graph_client_secret),
                    ("GRAPH_SENDER", settings.graph_sender),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"{', '.join(missing)} required when EMAIL_PROVIDER=graph"
                )

            await asyncio.to_thread(
                _send_graph,
                tenant_id=settings.graph_tenant_id,
                client_id=settings.graph_client_id,
                client_secret=settings.graph_client_secret,
                sender=settings.graph_sender,
                to=to,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
        else:
            raise ValueError(f"unknown email provider: {provider}")
    except Exception as exc:
        logger.error(
            "email delivery failed provider=%s to=%s error_type=%s",
            provider,
            to,
            type(exc).__name__,
        )
        return EmailResult(provider=provider, status="failed", error=str(exc))

    logger.info("email delivered provider=%s to=%s subject=%s", provider, to, subject)
    return EmailResult(provider=provider, status="sent")
