"""ORM rows for the spine: Tenant, Client, Brand, Brief, Job, ContentPillar.

Every tenant-scoped row carries `tenant_id` and indexes it — tenant isolation is enforced
in the query layer (see api/db/repo.py), never assumed from the route.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint
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
    # Makes the claim-form email dedup atomic (NULL emails stay distinct, so non-prospect
    # clients are unaffected). Backs api.routers.intake's IntegrityError-catch under concurrency.
    __table_args__ = (
        UniqueConstraint("tenant_id", "contact_email", name="uq_clients_tenant_email"),
    )

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
    # Stamped on entering GENERATING, cleared on leaving — drives the board's honest
    # "generating since / pending delivery" state (imagery generation is human-paced).
    generation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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


class UserAccountRow(Base):
    """The authZ source of truth: a verified provider identity -> tenant + role.

    `auth_subject` is the managed provider's user id (Supabase `sub`), globally unique. The
    tenant + role live HERE (our DB), never in provider-controlled metadata."""

    __tablename__ = "user_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    auth_subject: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    client_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    # For internal roles: client_ids this user is restricted to. Empty list = ALL clients in
    # the tenant (default, current behavior); non-empty = an assigned subset.
    client_scopes: Mapped[list] = mapped_column(JSON, default=list)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class InvitationRow(Base):
    """A pending/consumed offer to join a tenant with a role + client scope. The accept-link
    is a signed capability (api.core.invite_token); this row is the tenant-scoped state +
    audit spine. Tenant isolation is enforced in the query layer (see api/db/repo.py)."""

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    # client_ids an internal user is limited to; empty list = all clients in the tenant.
    client_scopes: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="pending")
    invited_by: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CreativeDocRow(Base):
    """The stored creative: the 5-layer manifest (copy + template + layer recipes) as JSON."""

    __tablename__ = "creative_docs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    job_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ApprovalRow(Base):
    """One review action, timestamped + attributed: the audit trail. Never updated in place."""

    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    job_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    creative_doc_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    actor: Mapped[dict] = mapped_column(JSON, default=dict)  # {id, role, name}
    action: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    # Pin-pointed change asks: [{zone, layer, instruction}] — WHERE + WHAT, per target.
    targets: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DeliveryRow(Base):
    """The archival record: a creative landed at a stable path. Written by the auto-archive
    procedure, never by a human remembering to upload."""

    __tablename__ = "deliveries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    job_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    creative_doc_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    drive_path: Mapped[str] = mapped_column(String, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TaskRow(Base):
    """A tracked unit of client<->ops collaboration. The portal and the ops board are two
    views of this one table."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    client_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    job_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="open")
    title: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[dict] = mapped_column(JSON, default=dict)  # actor {id, role, name}
    assignee: Mapped[str | None] = mapped_column(String, nullable=True)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SubscriptionRow(Base):
    """Billing state per client, mirrored from Stripe via verified webhook events. Gates the
    client's access; one active subscription per client (unique client_id)."""

    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    client_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String, default="incomplete")
    stripe_customer_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String, index=True, nullable=True
    )
    price_id: Mapped[str | None] = mapped_column(String, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PreferenceSignalRow(Base):
    """One learning-loop signal: a pick/edit/rejection/approval, client-scoped. Signals
    accumulate into a per-client preference profile (aggregated on read). Client-sourced
    signals feed ONLY their own client's profile — never the shared golden set (that path is
    human-gated). Append-only."""

    __tablename__ = "preference_signals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    client_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)  # pick|edit|rejection|approval
    creative_doc_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    job_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
    weight: Mapped[float] = mapped_column(default=1.0)
    reason_tag: Mapped[str | None] = mapped_column(String, nullable=True)
    # A snapshot of the salient creative attributes this signal is about (template_key,
    # colors, etc.) so the ranker can score future variants without re-loading each creative.
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    actor_role: Mapped[str] = mapped_column(String, default="client")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BrandAssetRow(Base):
    """One stored brand file (logo | font | imagery | reference_creative). Non-destructive:
    re-uploads create new rows; `approved` is a human-set flag. Reference creatives carry a
    `study` JSON (vision-pass observations) once ingested — the brand's style memory."""

    __tablename__ = "brand_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    client_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    brand_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # AssetKind values
    filename: Mapped[str] = mapped_column(String, nullable=False)
    mime: Mapped[str] = mapped_column(String, nullable=False)
    local_path: Mapped[str | None] = mapped_column(String, nullable=True)
    drive_file_id: Mapped[str | None] = mapped_column(String, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    license: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    study: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class NotificationRow(Base):
    """An outbound nudge, recorded first (the audit trail) then delivered by a channel adapter."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id"), index=True, nullable=False
    )
    client_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    job_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    channel: Mapped[str] = mapped_column(String, default="in_app")
    status: Mapped[str] = mapped_column(String, default="pending")
    subject: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str | None] = mapped_column(String, nullable=True)
    recipient: Mapped[str | None] = mapped_column(String, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
