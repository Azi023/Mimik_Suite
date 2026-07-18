"""ORM rows for the spine: Tenant, Client, Brand, Brief, Job, ContentPillar.

Every tenant-scoped row carries `tenant_id` and indexes it — tenant isolation is enforced
in the query layer (see api/db/repo.py), never assumed from the route.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TenantRow(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ClientRow(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    website_url: Mapped[str | None] = mapped_column(String, nullable=True)
    instagram: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BrandRow(Base):
    __tablename__ = "brands"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    client_id: Mapped[str] = mapped_column(
        String, ForeignKey("clients.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    niche: Mapped[str | None] = mapped_column(String, nullable=True)
    services: Mapped[list] = mapped_column(JSON, default=list)
    target_audience: Mapped[str | None] = mapped_column(String, nullable=True)
    brand_voice: Mapped[str | None] = mapped_column(String, nullable=True)
    tone_keywords: Mapped[list] = mapped_column(JSON, default=list)
    dos: Mapped[list] = mapped_column(JSON, default=list)
    donts: Mapped[list] = mapped_column(JSON, default=list)
    handles: Mapped[dict] = mapped_column(JSON, default=dict)
    tokens: Mapped[dict] = mapped_column(JSON, default=dict)
    imagery_style: Mapped[str | None] = mapped_column(String, nullable=True)
    references: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BriefRow(Base):
    __tablename__ = "briefs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    client_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    brand_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String, default="draft")
    sections: Mapped[dict] = mapped_column(JSON, default=dict)
    signed_off_by: Mapped[str | None] = mapped_column(String, nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    client_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    brand_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    brief_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pillar_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    format_key: Mapped[str] = mapped_column(String, nullable=False)
    publish_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_lead_days: Mapped[int] = mapped_column(default=3)
    assignee: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ContentPillarRow(Base):
    __tablename__ = "content_pillars"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    client_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
