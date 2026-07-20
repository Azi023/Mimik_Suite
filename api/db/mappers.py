"""Map ORM rows to `mimik_contracts` models so the API speaks the shared vocabulary on the wire."""

from __future__ import annotations

from datetime import datetime, timezone

from mimik_contracts import (
    Actor,
    Approval,
    AssetStudy,
    Brand,
    BrandAsset,
    BrandTokens,
    Brief,
    BriefSections,
    Client,
    ContentPillar,
    CreativeDoc,
    CreativeManifest,
    Delivery,
    Job,
    Notification,
    PreferenceSignal,
    Subscription,
    Task,
    Tenant,
    UserAccount,
)

from .models import (
    ApprovalRow,
    BrandAssetRow,
    BrandRow,
    BriefRow,
    ClientRow,
    ContentPillarRow,
    CreativeDocRow,
    DeliveryRow,
    JobRow,
    NotificationRow,
    PreferenceSignalRow,
    SubscriptionRow,
    TaskRow,
    TenantRow,
    UserAccountRow,
)


def _utc(value: datetime | None) -> datetime | None:
    """Re-attach UTC to a naive datetime. The app only ever stores aware-UTC; some drivers
    (e.g. SQLite) drop tzinfo on read, so a naive value is the same instant minus its zone.
    Postgres round-trips aware datetimes, making this a no-op there."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def to_tenant(row: TenantRow) -> Tenant:
    return Tenant(id=row.id, created_at=row.created_at, name=row.name, slug=row.slug)


def to_client(row: ClientRow) -> Client:
    return Client(
        id=row.id,
        created_at=row.created_at,
        tenant_id=row.tenant_id,
        name=row.name,
        contact_email=row.contact_email,
        phone=row.phone,
        industry=row.industry,
        website_url=row.website_url,
        instagram=row.instagram,
        notes=row.notes,
    )


def to_brand(row: BrandRow) -> Brand:
    return Brand(
        id=row.id,
        created_at=row.created_at,
        tenant_id=row.tenant_id,
        client_id=row.client_id,
        name=row.name,
        slug=row.slug,
        niche=row.niche,
        services=row.services or [],
        target_audience=row.target_audience,
        brand_voice=row.brand_voice,
        tone_keywords=row.tone_keywords or [],
        dos=row.dos or [],
        donts=row.donts or [],
        handles=row.handles or {},
        tokens=BrandTokens.model_validate(row.tokens) if row.tokens else BrandTokens(),
        imagery_style=row.imagery_style,
        references=row.references or [],
    )


def to_brand_asset(row: BrandAssetRow) -> BrandAsset:
    return BrandAsset(
        id=row.id,
        created_at=_utc(row.created_at),
        tenant_id=row.tenant_id,
        client_id=row.client_id,
        brand_id=row.brand_id,
        kind=row.kind,
        filename=row.filename,
        mime=row.mime,
        local_path=row.local_path,
        drive_file_id=row.drive_file_id,
        approved=row.approved,
        license=row.license,
        notes=row.notes,
        study=AssetStudy.model_validate(row.study) if row.study else None,
    )


def to_pillar(row: ContentPillarRow) -> ContentPillar:
    return ContentPillar(
        id=row.id,
        created_at=row.created_at,
        tenant_id=row.tenant_id,
        client_id=row.client_id,
        name=row.name,
        description=row.description,
        is_custom=row.is_custom,
    )


def to_brief(row: BriefRow) -> Brief:
    return Brief(
        id=row.id,
        created_at=row.created_at,
        tenant_id=row.tenant_id,
        client_id=row.client_id,
        brand_id=row.brand_id,
        version=row.version,
        status=row.status,
        sections=BriefSections.model_validate(row.sections) if row.sections else BriefSections(),
        signed_off_by=row.signed_off_by,
        frozen_at=row.frozen_at,
    )


def to_job(row: JobRow) -> Job:
    return Job(
        id=row.id,
        created_at=row.created_at,
        tenant_id=row.tenant_id,
        client_id=row.client_id,
        brand_id=row.brand_id,
        brief_id=row.brief_id,
        pillar_id=row.pillar_id,
        title=row.title,
        format_key=row.format_key,
        publish_date=_utc(row.publish_date),
        approval_lead_days=row.approval_lead_days,
        assignee=row.assignee,
        status=row.status,
        generation_started_at=_utc(row.generation_started_at),
    )


def to_user_account(row: UserAccountRow) -> UserAccount:
    return UserAccount(
        id=row.id,
        created_at=row.created_at,
        tenant_id=row.tenant_id,
        auth_subject=row.auth_subject,
        email=row.email,
        role=row.role,
        client_id=row.client_id,
        name=row.name,
        active=row.active,
    )


def to_creative_doc(row: CreativeDocRow) -> CreativeDoc:
    return CreativeDoc(
        id=row.id,
        created_at=row.created_at,
        tenant_id=row.tenant_id,
        job_id=row.job_id,
        manifest=CreativeManifest.model_validate(row.manifest),
        version=row.version,
    )


def to_approval(row: ApprovalRow) -> Approval:
    return Approval(
        id=row.id,
        created_at=row.created_at,
        tenant_id=row.tenant_id,
        job_id=row.job_id,
        creative_doc_id=row.creative_doc_id,
        actor=Actor.model_validate(row.actor),
        action=row.action,
        note=row.note,
        targets=row.targets or [],
    )


def to_delivery(row: DeliveryRow) -> Delivery:
    return Delivery(
        id=row.id,
        created_at=row.created_at,
        tenant_id=row.tenant_id,
        job_id=row.job_id,
        creative_doc_id=row.creative_doc_id,
        drive_path=row.drive_path,
        delivered_at=row.delivered_at,
    )


def to_task(row: TaskRow) -> Task:
    return Task(
        id=row.id,
        created_at=row.created_at,
        tenant_id=row.tenant_id,
        client_id=row.client_id,
        job_id=row.job_id,
        type=row.type,
        status=row.status,
        title=row.title,
        detail=row.detail,
        created_by=Actor.model_validate(row.created_by),
        assignee=row.assignee,
        notified=row.notified,
        updated_at=row.updated_at,
    )


def to_subscription(row: SubscriptionRow) -> Subscription:
    return Subscription(
        id=row.id,
        created_at=row.created_at,
        tenant_id=row.tenant_id,
        client_id=row.client_id,
        status=row.status,
        stripe_customer_id=row.stripe_customer_id,
        stripe_subscription_id=row.stripe_subscription_id,
        price_id=row.price_id,
        current_period_end=_utc(row.current_period_end),
    )


def to_preference_signal(row: PreferenceSignalRow) -> PreferenceSignal:
    return PreferenceSignal(
        source=row.source,
        creative_doc_id=row.creative_doc_id,
        job_id=row.job_id,
        detail=row.detail,
        weight=row.weight,
        reason_tag=row.reason_tag,
        attributes=row.attributes or {},
        actor_role=row.actor_role,
    )


def to_notification(row: NotificationRow) -> Notification:
    return Notification(
        id=row.id,
        created_at=row.created_at,
        tenant_id=row.tenant_id,
        client_id=row.client_id,
        job_id=row.job_id,
        task_id=row.task_id,
        channel=row.channel,
        status=row.status,
        subject=row.subject,
        body=row.body,
        recipient=row.recipient,
        sent_at=row.sent_at,
    )
