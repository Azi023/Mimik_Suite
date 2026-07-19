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
from mimik_contracts import NotificationStatus


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


async def dispatch_pending(
    session: AsyncSession,
    *,
    tenant_id: str,
    sink: NotificationSink | None = None,
) -> int:
    """Deliver every PENDING notification for the tenant through `sink`, returning the count
    sent. Tenant-scoped: only this tenant's rows are ever touched (never a cross-tenant sweep)."""
    active_sink = sink if sink is not None else RecordingSink()
    # Filter to PENDING in SQL — never load the tenant's whole notification history to send.
    pending = await repo.list_notifications(
        session, tenant_id=tenant_id, status=NotificationStatus.PENDING.value
    )
    for row in pending:
        await active_sink.send(row)
    await session.commit()
    return len(pending)
