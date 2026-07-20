"""WhatsApp delivery sinks — the outbound channel behind `NotificationChannel.WHATSAPP`.

Swappable exactly like the image backends: `resolve_whatsapp_sink()` reads `WHATSAPP_PROVIDER`
and returns a concrete `NotificationSink`. `none` (the default) is the inert path — no network,
no account, the row is left PENDING so a later configured run can still deliver it. `meta_cloud`
is the official WhatsApp Business Platform (Cloud API) sender.

Security posture (locked constraints):
- The access token and message body (which carries a magic-link capability token) are NEVER
  logged. Phone numbers are masked in logs.
- The message content is a SYSTEM-composed magic-link, filling a constrained template slot — it
  is never client freeform text merged into anything (constraint #3: client text is data).
- Delivery is tenant-scoped by the caller (`dispatch_pending`); this module never sweeps.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx

from api.core.config import get_settings
from api.db.models import NotificationRow
from api.services.notifications import NotificationSink
from mimik_contracts import NotificationStatus

logger = logging.getLogger(__name__)

_NON_DIGITS = re.compile(r"[^\d]")


def _to_msisdn(recipient: str | None) -> str:
    """Normalise a recipient to a bare international MSISDN (digits only, no '+').

    Meta's Cloud API wants the number in international format; it tolerates a leading '+',
    but stripping to digits is the least-surprising canonical form. Returns '' if there's
    nothing usable — the caller treats that as a hard delivery failure, never a silent drop.
    """
    if not recipient:
        return ""
    return _NON_DIGITS.sub("", recipient)


def _mask(msisdn: str) -> str:
    """Mask a phone number for logs — keep only the last 3 digits."""
    return f"***{msisdn[-3:]}" if len(msisdn) >= 3 else "***"


def _fail(row: NotificationRow, reason: str) -> None:
    """Mark a row FAILED with a reason (no secrets, no message body, phone masked upstream)."""
    row.status = NotificationStatus.FAILED.value
    logger.warning("whatsapp delivery failed notif=%s: %s", row.id, reason)


class NullWhatsAppSink(NotificationSink):
    """`WHATSAPP_PROVIDER=none` (default): no provider wired. Non-destructive — the row is left
    PENDING (not FAILED) so it delivers the moment a real provider is configured."""

    async def send(self, notification_row: NotificationRow) -> None:
        logger.info(
            "whatsapp provider is 'none' — notif=%s left PENDING (no delivery configured)",
            notification_row.id,
        )


class MetaCloudWhatsAppSink(NotificationSink):
    """Official WhatsApp Business Platform (Cloud API) sender.

    Sends a pre-approved Utility template whose single body variable {{1}} carries the
    system-composed review magic-link (from `row.body`). Business-initiated messages outside
    the 24h customer-care window require a template — this is that path.

    Config is injectable so tests never touch the network or the process-wide settings singleton.
    """

    def __init__(
        self,
        *,
        phone_number_id: str | None = None,
        access_token: str | None = None,
        api_base: str | None = None,
        template_name: str | None = None,
        template_lang: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
    ) -> None:
        s = get_settings()
        self._phone_number_id = (
            phone_number_id if phone_number_id is not None else s.whatsapp_phone_number_id
        )
        self._access_token = access_token if access_token is not None else s.whatsapp_access_token
        self._api_base = (api_base if api_base is not None else s.whatsapp_api_base).rstrip("/")
        self._template_name = (
            template_name if template_name is not None else s.whatsapp_template_name
        )
        self._template_lang = (
            template_lang if template_lang is not None else s.whatsapp_template_lang
        )
        self._client = client  # injected in tests; None -> a per-send AsyncClient
        self._timeout = timeout

    def _payload(self, to: str, body_param: str) -> dict:
        return {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": self._template_name,
                "language": {"code": self._template_lang},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": body_param}],
                    }
                ],
            },
        }

    async def send(self, notification_row: NotificationRow) -> None:
        to = _to_msisdn(notification_row.recipient)
        if not to:
            _fail(notification_row, "no recipient phone number")
            return
        if not (self._phone_number_id and self._access_token):
            # Wiring gap, not a runtime error: provider selected but credentials absent.
            _fail(notification_row, "meta_cloud selected but WHATSAPP_* credentials are not set")
            return

        # System-composed content only (the magic-link URL). Never client freeform text.
        body_param = notification_row.body or notification_row.subject or ""
        url = f"{self._api_base}/{self._phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        try:
            if self._client is not None:
                resp = await self._client.post(url, json=self._payload(to, body_param), headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(
                        url, json=self._payload(to, body_param), headers=headers
                    )
        except httpx.HTTPError as exc:
            # Log the class, never the exception text (a URL with the token could surface there).
            _fail(notification_row, f"transport error ({exc.__class__.__name__})")
            return

        if resp.is_success:
            notification_row.status = NotificationStatus.SENT.value
            notification_row.sent_at = datetime.now(timezone.utc)
            logger.info("whatsapp sent notif=%s to=%s", notification_row.id, _mask(to))
        else:
            # Status code only — never the response body (may echo the message/token).
            _fail(notification_row, f"meta api returned status {resp.status_code}")


def resolve_whatsapp_sink(client: httpx.AsyncClient | None = None) -> NotificationSink:
    """Return the configured WhatsApp sink. `none`/unset -> inert NullWhatsAppSink."""
    provider = (get_settings().whatsapp_provider or "none").strip().lower()
    if provider in ("", "none"):
        return NullWhatsAppSink()
    if provider == "meta_cloud":
        return MetaCloudWhatsAppSink(client=client)
    raise ValueError(
        f"WHATSAPP_PROVIDER={provider!r} is not a known provider (expected 'none' or 'meta_cloud')"
    )
