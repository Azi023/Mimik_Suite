"""Notification sink: the seam where an in-app record becomes an outbound nudge.

A `Notification` is always recorded first (the audit trail — see `mimik_contracts.Notification`).
Delivery is a separate, swappable step: today the dev/test sink just marks the row `SENT`
(in-app is delivered the moment it is recorded); tomorrow a WhatsApp/email sink plugs in behind
the same `NotificationSink` interface with zero change to callers. This is the
cheap-notifications-now / upgrade-later seam from the product plan.
"""

from __future__ import annotations

import abc
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from api.db import repo
from api.db.models import NotificationRow
from mimik_contracts import NotificationChannel, NotificationStatus


class NotificationSink(abc.ABC):
    """A channel that delivers a recorded notification. Implementations mutate the row's
    delivery state (status / sent_at); the caller commits."""

    @abc.abstractmethod
    async def send(self, notification_row: NotificationRow) -> None:
        """Deliver `notification_row` and mark its delivery outcome on the row."""
        raise NotImplementedError


class RecordingSink(NotificationSink):
    """The dev/test default: no network. An in-app notification is 'delivered' the instant it
    is recorded, so this just stamps the row SENT + sent_at."""

    async def send(self, notification_row: NotificationRow) -> None:
        notification_row.status = NotificationStatus.SENT.value
        notification_row.sent_at = datetime.now(timezone.utc)


def resolve_sink(channel: str, *, http_client: object | None = None) -> NotificationSink:
    """Pick the delivery sink for a channel. WHATSAPP routes to the configured provider
    (`WHATSAPP_PROVIDER`); IN_APP/EMAIL are delivered-on-record by the dev RecordingSink.
    `http_client` (an `httpx.AsyncClient`) is threaded to network sinks so a dispatch pass
    reuses one client instead of one per message."""
    if channel == NotificationChannel.WHATSAPP.value:
        # Local import: the whatsapp module imports NotificationSink from here (avoid a cycle).
        from api.services.whatsapp import resolve_whatsapp_sink

        return resolve_whatsapp_sink(client=http_client)
    return RecordingSink()


async def dispatch_pending(
    session: AsyncSession,
    *,
    tenant_id: str,
    sink: NotificationSink | None = None,
) -> int:
    """Deliver every PENDING notification for the tenant, returning the count actually SENT.

    Tenant-scoped: only this tenant's rows are ever touched (never a cross-tenant sweep).
    Each row is routed to a sink by its `channel` unless an explicit `sink` override is given
    (tests use that). A row a sink leaves PENDING (e.g. no WhatsApp provider wired) is not
    counted and is left for a later run — delivery is non-destructive."""
    import httpx

    # Filter to PENDING in SQL — never load the tenant's whole notification history to send.
    pending = await repo.list_notifications(
        session, tenant_id=tenant_id, status=NotificationStatus.PENDING.value
    )
    sent = 0
    # One HTTP client for the whole pass (network sinks reuse it). Resolve one sink per distinct
    # channel BEFORE sending anything: a bad provider config raises here, before any row is
    # mutated — so a misconfig can't leave a half-delivered, uncommitted batch.
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        sinks: dict[str, NotificationSink] = (
            {}
            if sink is not None
            else {ch: resolve_sink(ch, http_client=http_client) for ch in {r.channel for r in pending}}
        )
        for row in pending:
            active_sink = sink if sink is not None else sinks[row.channel]
            await active_sink.send(row)
            if row.status == NotificationStatus.SENT.value:
                sent += 1
    await session.commit()
    return sent
