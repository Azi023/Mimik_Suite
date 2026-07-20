"""Tenant-scoped data access.

THE tenant-isolation invariant lives here: every function that touches tenant data takes a
`tenant_id` and filters by it. Routes derive `tenant_id` from the auth token, never from the
client — so a caller cannot read another tenant's rows even with a valid id (IDOR defence).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    ApprovalRow,
    BrandAssetRow,
    BrandRow,
    BriefRow,
    ClientRow,
    ContentPillarRow,
    CreativeDocRow,
    DeliveryRow,
    InvitationRow,
    JobRow,
    NotificationRow,
    PreferenceSignalRow,
    SubscriptionRow,
    TaskRow,
    TenantRow,
    UserAccountRow,
)


# --- Tenant (not itself tenant-scoped; it IS the tenant) ---
async def create_tenant(session: AsyncSession, *, name: str, slug: str) -> TenantRow:
    row = TenantRow(name=name, slug=slug)
    session.add(row)
    await session.flush()
    return row


async def get_tenant(session: AsyncSession, tenant_id: str) -> TenantRow | None:
    return await session.get(TenantRow, tenant_id)


async def get_tenant_by_slug(session: AsyncSession, slug: str) -> TenantRow | None:
    """Resolve a storefront tenant by its public slug (the claim-form entry point)."""
    stmt = select(TenantRow).where(TenantRow.slug == slug)
    return (await session.execute(stmt)).scalar_one_or_none()


# --- Client ---
async def create_client(session: AsyncSession, *, tenant_id: str, **fields) -> ClientRow:
    row = ClientRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_client(session: AsyncSession, *, tenant_id: str, client_id: str) -> ClientRow | None:
    stmt = select(ClientRow).where(
        ClientRow.id == client_id, ClientRow.tenant_id == tenant_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_clients(session: AsyncSession, *, tenant_id: str) -> list[ClientRow]:
    stmt = select(ClientRow).where(ClientRow.tenant_id == tenant_id).order_by(ClientRow.created_at)
    return list((await session.execute(stmt)).scalars())


async def get_client_by_email(
    session: AsyncSession, *, tenant_id: str, email: str
) -> ClientRow | None:
    """Find an existing client by contact email within a tenant — the claim-form dedup key
    (a resubmitted claim returns the existing prospect instead of creating a duplicate)."""
    stmt = select(ClientRow).where(
        ClientRow.tenant_id == tenant_id, ClientRow.contact_email == email
    )
    return (await session.execute(stmt)).scalars().first()


# --- Brand ---
async def create_brand(session: AsyncSession, *, tenant_id: str, **fields) -> BrandRow:
    row = BrandRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_brand(session: AsyncSession, *, tenant_id: str, brand_id: str) -> BrandRow | None:
    stmt = select(BrandRow).where(BrandRow.id == brand_id, BrandRow.tenant_id == tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_brands(
    session: AsyncSession, *, tenant_id: str, client_id: str | None = None
) -> list[BrandRow]:
    stmt = select(BrandRow).where(BrandRow.tenant_id == tenant_id)
    if client_id is not None:
        stmt = stmt.where(BrandRow.client_id == client_id)
    stmt = stmt.order_by(BrandRow.created_at)
    return list((await session.execute(stmt)).scalars())


# --- Content pillar ---
async def create_pillar(session: AsyncSession, *, tenant_id: str, **fields) -> ContentPillarRow:
    row = ContentPillarRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_pillar(
    session: AsyncSession, *, tenant_id: str, pillar_id: str
) -> ContentPillarRow | None:
    stmt = select(ContentPillarRow).where(
        ContentPillarRow.id == pillar_id, ContentPillarRow.tenant_id == tenant_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_pillars(
    session: AsyncSession, *, tenant_id: str, client_id: str | None = None
) -> list[ContentPillarRow]:
    stmt = select(ContentPillarRow).where(ContentPillarRow.tenant_id == tenant_id)
    if client_id is not None:
        stmt = stmt.where(ContentPillarRow.client_id == client_id)
    stmt = stmt.order_by(ContentPillarRow.created_at)
    return list((await session.execute(stmt)).scalars())


# --- Brief ---
async def create_brief(session: AsyncSession, *, tenant_id: str, **fields) -> BriefRow:
    row = BriefRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_brief(session: AsyncSession, *, tenant_id: str, brief_id: str) -> BriefRow | None:
    stmt = select(BriefRow).where(BriefRow.id == brief_id, BriefRow.tenant_id == tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_briefs(
    session: AsyncSession, *, tenant_id: str, client_id: str | None = None
) -> list[BriefRow]:
    stmt = select(BriefRow).where(BriefRow.tenant_id == tenant_id)
    if client_id is not None:
        stmt = stmt.where(BriefRow.client_id == client_id)
    stmt = stmt.order_by(BriefRow.created_at)
    return list((await session.execute(stmt)).scalars())


# --- Job ---
async def create_job(session: AsyncSession, *, tenant_id: str, **fields) -> JobRow:
    row = JobRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_job(session: AsyncSession, *, tenant_id: str, job_id: str) -> JobRow | None:
    stmt = select(JobRow).where(JobRow.id == job_id, JobRow.tenant_id == tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_jobs(
    session: AsyncSession, *, tenant_id: str, client_id: str | None = None
) -> list[JobRow]:
    stmt = select(JobRow).where(JobRow.tenant_id == tenant_id)
    if client_id is not None:
        stmt = stmt.where(JobRow.client_id == client_id)
    stmt = stmt.order_by(JobRow.created_at)
    return list((await session.execute(stmt)).scalars())


async def list_jobs_in_publish_window(
    session: AsyncSession, *, tenant_id: str, start: datetime, end: datetime
) -> list[JobRow]:
    """Jobs whose publish_date falls in [start, end] — the calendar view."""
    stmt = (
        select(JobRow)
        .where(
            JobRow.tenant_id == tenant_id,
            JobRow.publish_date.is_not(None),
            JobRow.publish_date >= start,
            JobRow.publish_date <= end,
        )
        .order_by(JobRow.publish_date)
    )
    return list((await session.execute(stmt)).scalars())


async def list_scheduled_jobs_all_tenants(session: AsyncSession) -> list[JobRow]:
    """SYSTEM scope (the at-risk worker only): every job with a publish_date, across tenants.

    This is the one deliberately non-tenant-scoped query — it runs in a background worker,
    never on a request path, so there is no caller tenant to filter by. Callers must NOT
    expose its results across a tenant boundary."""
    stmt = select(JobRow).where(JobRow.publish_date.is_not(None))
    return list((await session.execute(stmt)).scalars())


# --- UserAccount (authZ source of truth) ---
async def create_user_account(session: AsyncSession, *, tenant_id: str, **fields) -> UserAccountRow:
    row = UserAccountRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_user_account_by_subject(
    session: AsyncSession, *, auth_subject: str
) -> UserAccountRow | None:
    """Look up the account for a verified provider identity. NOT tenant-scoped: the whole
    point is that the token proves identity and THIS row supplies the tenant."""
    stmt = select(UserAccountRow).where(UserAccountRow.auth_subject == auth_subject)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_user_account(
    session: AsyncSession, *, tenant_id: str, account_id: str
) -> UserAccountRow | None:
    stmt = select(UserAccountRow).where(
        UserAccountRow.id == account_id, UserAccountRow.tenant_id == tenant_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_user_accounts(session: AsyncSession, *, tenant_id: str) -> list[UserAccountRow]:
    stmt = (
        select(UserAccountRow)
        .where(UserAccountRow.tenant_id == tenant_id)
        .order_by(UserAccountRow.created_at)
    )
    return list((await session.execute(stmt)).scalars())


# --- Invitation (tenant-scoped; the invite lifecycle + audit spine) ---
async def create_invitation(session: AsyncSession, *, tenant_id: str, **fields) -> InvitationRow:
    row = InvitationRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_invitation(
    session: AsyncSession, *, tenant_id: str, invitation_id: str
) -> InvitationRow | None:
    stmt = select(InvitationRow).where(
        InvitationRow.id == invitation_id, InvitationRow.tenant_id == tenant_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_invitations(session: AsyncSession, *, tenant_id: str) -> list[InvitationRow]:
    stmt = (
        select(InvitationRow)
        .where(InvitationRow.tenant_id == tenant_id)
        .order_by(InvitationRow.created_at)
    )
    return list((await session.execute(stmt)).scalars())


async def get_invitation_by_email(
    session: AsyncSession, *, tenant_id: str, email: str, status: str | None = None
) -> InvitationRow | None:
    """Dedup lookup within a tenant (email compared case-insensitively). Optionally restrict
    to a status (e.g. PENDING) so a new invite doesn't collide with a terminal one."""
    stmt = select(InvitationRow).where(
        InvitationRow.tenant_id == tenant_id,
        func.lower(InvitationRow.email) == email.lower(),
    )
    if status is not None:
        stmt = stmt.where(InvitationRow.status == status)
    return (await session.execute(stmt)).scalars().first()


# --- CreativeDoc ---
async def create_creative_doc(session: AsyncSession, *, tenant_id: str, **fields) -> CreativeDocRow:
    row = CreativeDocRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_creative_doc(
    session: AsyncSession, *, tenant_id: str, creative_doc_id: str
) -> CreativeDocRow | None:
    stmt = select(CreativeDocRow).where(
        CreativeDocRow.id == creative_doc_id, CreativeDocRow.tenant_id == tenant_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_creative_docs(
    session: AsyncSession, *, tenant_id: str, job_id: str
) -> list[CreativeDocRow]:
    stmt = (
        select(CreativeDocRow)
        .where(CreativeDocRow.tenant_id == tenant_id, CreativeDocRow.job_id == job_id)
        .order_by(CreativeDocRow.created_at)
    )
    return list((await session.execute(stmt)).scalars())


# --- Approval (audit trail; append-only) ---
async def create_approval(session: AsyncSession, *, tenant_id: str, **fields) -> ApprovalRow:
    row = ApprovalRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def list_approvals(
    session: AsyncSession, *, tenant_id: str, job_id: str
) -> list[ApprovalRow]:
    stmt = (
        select(ApprovalRow)
        .where(ApprovalRow.tenant_id == tenant_id, ApprovalRow.job_id == job_id)
        .order_by(ApprovalRow.created_at)
    )
    return list((await session.execute(stmt)).scalars())


# --- Delivery ---
async def create_delivery(session: AsyncSession, *, tenant_id: str, **fields) -> DeliveryRow:
    row = DeliveryRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def list_deliveries(
    session: AsyncSession, *, tenant_id: str, job_id: str
) -> list[DeliveryRow]:
    stmt = (
        select(DeliveryRow)
        .where(DeliveryRow.tenant_id == tenant_id, DeliveryRow.job_id == job_id)
        .order_by(DeliveryRow.created_at)
    )
    return list((await session.execute(stmt)).scalars())


# --- Task ---
async def create_task(session: AsyncSession, *, tenant_id: str, **fields) -> TaskRow:
    row = TaskRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_task(session: AsyncSession, *, tenant_id: str, task_id: str) -> TaskRow | None:
    stmt = select(TaskRow).where(TaskRow.id == task_id, TaskRow.tenant_id == tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_tasks(
    session: AsyncSession,
    *,
    tenant_id: str,
    client_id: str | None = None,
    job_id: str | None = None,
    status: str | None = None,
) -> list[TaskRow]:
    stmt = select(TaskRow).where(TaskRow.tenant_id == tenant_id)
    if client_id is not None:
        stmt = stmt.where(TaskRow.client_id == client_id)
    if job_id is not None:
        stmt = stmt.where(TaskRow.job_id == job_id)
    if status is not None:
        stmt = stmt.where(TaskRow.status == status)
    stmt = stmt.order_by(TaskRow.created_at)
    return list((await session.execute(stmt)).scalars())


# --- Notification ---
async def create_notification(
    session: AsyncSession, *, tenant_id: str, **fields
) -> NotificationRow:
    row = NotificationRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


# --- Subscription (billing state, one per client) ---
async def create_subscription(session: AsyncSession, *, tenant_id: str, **fields) -> SubscriptionRow:
    row = SubscriptionRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_subscription_for_client(
    session: AsyncSession, *, tenant_id: str, client_id: str
) -> SubscriptionRow | None:
    stmt = select(SubscriptionRow).where(
        SubscriptionRow.tenant_id == tenant_id, SubscriptionRow.client_id == client_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_subscription_by_stripe_id(
    session: AsyncSession, *, stripe_subscription_id: str
) -> SubscriptionRow | None:
    """Webhook lookup — NOT tenant-scoped: a Stripe event identifies the sub by its Stripe id,
    and the row supplies the tenant. Callers must not expose it across tenants."""
    stmt = select(SubscriptionRow).where(
        SubscriptionRow.stripe_subscription_id == stripe_subscription_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


# --- PreferenceSignal (learning loop; append-only, client-scoped) ---
async def create_brand_asset(session: AsyncSession, *, tenant_id: str, **fields) -> BrandAssetRow:
    row = BrandAssetRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_brand_asset(
    session: AsyncSession, *, tenant_id: str, asset_id: str
) -> BrandAssetRow | None:
    stmt = select(BrandAssetRow).where(
        BrandAssetRow.id == asset_id, BrandAssetRow.tenant_id == tenant_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_brand_assets(
    session: AsyncSession, *, tenant_id: str, brand_id: str, kind: str | None = None
) -> list[BrandAssetRow]:
    stmt = select(BrandAssetRow).where(
        BrandAssetRow.tenant_id == tenant_id, BrandAssetRow.brand_id == brand_id
    )
    if kind is not None:
        stmt = stmt.where(BrandAssetRow.kind == kind)
    stmt = stmt.order_by(BrandAssetRow.created_at)
    return list((await session.execute(stmt)).scalars())


async def create_preference_signal(
    session: AsyncSession, *, tenant_id: str, **fields
) -> PreferenceSignalRow:
    row = PreferenceSignalRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def list_preference_signals(
    session: AsyncSession, *, tenant_id: str, client_id: str
) -> list[PreferenceSignalRow]:
    stmt = (
        select(PreferenceSignalRow)
        .where(
            PreferenceSignalRow.tenant_id == tenant_id,
            PreferenceSignalRow.client_id == client_id,
        )
        .order_by(PreferenceSignalRow.created_at)
    )
    return list((await session.execute(stmt)).scalars())


async def list_notifications(
    session: AsyncSession,
    *,
    tenant_id: str,
    client_id: str | None = None,
    job_id: str | None = None,
    status: str | None = None,
) -> list[NotificationRow]:
    stmt = select(NotificationRow).where(NotificationRow.tenant_id == tenant_id)
    if client_id is not None:
        stmt = stmt.where(NotificationRow.client_id == client_id)
    if job_id is not None:
        stmt = stmt.where(NotificationRow.job_id == job_id)
    if status is not None:
        stmt = stmt.where(NotificationRow.status == status)
    stmt = stmt.order_by(NotificationRow.created_at)
    return list((await session.execute(stmt)).scalars())
