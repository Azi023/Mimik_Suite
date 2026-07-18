"""Map ORM rows to `mimik_contracts` models so the API speaks the shared vocabulary on the wire."""

from __future__ import annotations

from mimik_contracts import (
    Brand,
    BrandTokens,
    Brief,
    BriefSections,
    Client,
    ContentPillar,
    Job,
    Tenant,
)

from .models import (
    BrandRow,
    BriefRow,
    ClientRow,
    ContentPillarRow,
    JobRow,
    TenantRow,
)


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
        publish_date=row.publish_date,
        approval_lead_days=row.approval_lead_days,
        assignee=row.assignee,
        status=row.status,
    )
