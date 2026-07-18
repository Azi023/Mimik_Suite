"""Tenant-scoped data access.

THE tenant-isolation invariant lives here: every function that touches tenant data takes a
`tenant_id` and filters by it. Routes derive `tenant_id` from the auth token, never from the
client — so a caller cannot read another tenant's rows even with a valid id (IDOR defence).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    BrandRow,
    BriefRow,
    ClientRow,
    ContentPillarRow,
    JobRow,
    TenantRow,
)


# --- Tenant (not itself tenant-scoped; it IS the tenant) ---
async def create_tenant(session: AsyncSession, *, name: str, slug: str) -> TenantRow:
    row = TenantRow(name=name, slug=slug)
    session.add(row)
    await session.flush()
    return row


async def get_tenant(session: AsyncSession, tenant_id: str) -> TenantRow | None:
    return await session.get(TenantRow, tenant_id)


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


# --- Brand ---
async def create_brand(session: AsyncSession, *, tenant_id: str, **fields) -> BrandRow:
    row = BrandRow(tenant_id=tenant_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_brand(session: AsyncSession, *, tenant_id: str, brand_id: str) -> BrandRow | None:
    stmt = select(BrandRow).where(BrandRow.id == brand_id, BrandRow.tenant_id == tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


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
