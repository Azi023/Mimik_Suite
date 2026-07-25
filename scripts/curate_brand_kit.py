"""Append approved, rendered creatives to Brand Kit chapters 05 and 06.

Run from the repository root after migrations have been applied:

    python scripts/curate_brand_kit.py --slug simply-nikah
    python scripts/curate_brand_kit.py --all

The script follows ``seed_brand_kit.py``: it operates in the oldest studio tenant, resolves
every creative through tenant-scoped repository functions, and persists the complete validated
``BrandKit`` JSON. Existing applications and templates are retained verbatim; reruns only append
creative ids that are not already curated.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import repo
from api.db.mappers import to_brand
from api.db.models import (
    ApprovalRow,
    BrandRow,
    ContentPillarRow,
    CreativeDocRow,
    JobRow,
    TenantRow,
)
from api.db.session import get_engine, get_sessionmaker
from api.services.creative_generation import creative_artifact_path
from mimik_contracts import BrandApplication, LaunchTemplate

MAX_TEMPLATES = 6
MAX_APPLICATIONS = 2


@dataclass(frozen=True, slots=True)
class CurationSummary:
    slug: str
    eligible_creatives: int
    templates_added: int
    applications_added: int


@dataclass(frozen=True, slots=True)
class CuratedCreative:
    row: CreativeDocRow
    job: JobRow
    name: str


def _preview_exists(creative_id: str) -> bool:
    return creative_artifact_path(creative_id, "preview.png").is_file()


async def _first_tenant(session: AsyncSession) -> TenantRow | None:
    statement = select(TenantRow).order_by(TenantRow.created_at, TenantRow.id).limit(1)
    return (await session.execute(statement)).scalar_one_or_none()


async def _eligible_creatives(
    session: AsyncSession,
    *,
    tenant_id: str,
    brand: BrandRow,
    artifact_exists: Callable[[str], bool],
) -> list[CuratedCreative]:
    """Return latest approved/rendered docs for one brand, newest first."""
    latest = await repo.list_latest_creatives(
        session,
        tenant_id=tenant_id,
        client_id=brand.client_id,
    )
    if not latest:
        return []

    job_ids = {creative.job_id for creative in latest}
    jobs_statement = select(JobRow).where(
        JobRow.tenant_id == tenant_id,
        JobRow.brand_id == brand.id,
        JobRow.id.in_(job_ids),
    )
    jobs = list((await session.execute(jobs_statement)).scalars())
    jobs_by_id = {job.id: job for job in jobs}

    creative_ids = {creative.id for creative in latest}
    approvals_statement = (
        select(ApprovalRow)
        .where(
            ApprovalRow.tenant_id == tenant_id,
            ApprovalRow.creative_doc_id.in_(creative_ids),
        )
        .order_by(ApprovalRow.created_at, ApprovalRow.id)
    )
    approvals = list((await session.execute(approvals_statement)).scalars())
    latest_actions = {approval.creative_doc_id: approval.action for approval in approvals}

    pillar_ids = {job.pillar_id for job in jobs if job.pillar_id is not None}
    pillars_by_id: dict[str, ContentPillarRow] = {}
    if pillar_ids:
        pillars_statement = select(ContentPillarRow).where(
            ContentPillarRow.tenant_id == tenant_id,
            ContentPillarRow.id.in_(pillar_ids),
        )
        pillars = list((await session.execute(pillars_statement)).scalars())
        pillars_by_id = {pillar.id: pillar for pillar in pillars}

    eligible: list[CuratedCreative] = []
    for creative in latest:
        job = jobs_by_id.get(creative.job_id)
        if job is None or not artifact_exists(creative.id):
            continue
        if latest_actions.get(creative.id) != "approve":
            continue

        pillar = pillars_by_id.get(job.pillar_id) if job.pillar_id is not None else None
        pillar_name = pillar.name if pillar is not None else None
        ordinal = len(eligible) + 1
        name = pillar_name or job.title.strip() or f"Launch {ordinal:02d}"
        eligible.append(CuratedCreative(row=creative, job=job, name=name))
        if len(eligible) >= MAX_TEMPLATES:
            break
    return eligible


async def _curate_brand(
    session: AsyncSession,
    *,
    tenant_id: str,
    row: BrandRow,
    artifact_exists: Callable[[str], bool],
) -> CurationSummary:
    brand = to_brand(row)
    eligible = await _eligible_creatives(
        session,
        tenant_id=tenant_id,
        brand=row,
        artifact_exists=artifact_exists,
    )

    template_ids = {
        template.creative_id
        for template in brand.kit.launch_templates
        if template.creative_id is not None
    }
    templates_added = 0
    for item in eligible:
        if item.row.id in template_ids:
            continue
        brand.kit.launch_templates.append(
            LaunchTemplate(
                name=item.name,
                format_key=item.job.format_key,
                creative_id=item.row.id,
            )
        )
        template_ids.add(item.row.id)
        templates_added += 1

    application_ids = {
        application.creative_id
        for application in brand.kit.applications
        if application.creative_id is not None
    }
    application_slots = len(application_ids)
    applications_added = 0
    for item in eligible:
        if application_slots >= MAX_APPLICATIONS:
            break
        if item.row.id in application_ids:
            continue
        brand.kit.applications.append(
            BrandApplication(
                kind="ig_post",
                creative_id=item.row.id,
                caption=item.name,
            )
        )
        application_ids.add(item.row.id)
        application_slots += 1
        applications_added += 1

    if templates_added > 0 or applications_added > 0:
        updated = await repo.update_brand(
            session,
            tenant_id=tenant_id,
            brand_id=row.id,
            kit=brand.kit.model_dump(mode="json"),
        )
        if updated is None:
            raise RuntimeError(f"Brand disappeared during curation: {row.slug}")
        await session.commit()

    return CurationSummary(
        slug=row.slug,
        eligible_creatives=len(eligible),
        templates_added=templates_added,
        applications_added=applications_added,
    )


async def curate_brand_kits(
    session: AsyncSession,
    *,
    slug: str | None,
    curate_all: bool,
    artifact_exists: Callable[[str], bool] = _preview_exists,
) -> list[CurationSummary]:
    """Curate one slug or every brand in the oldest tenant."""
    if curate_all == (slug is not None):
        raise ValueError("Choose exactly one of slug or curate_all")

    tenant = await _first_tenant(session)
    if tenant is None:
        raise RuntimeError("No Tenant row exists; create the studio tenant first")

    brands = await repo.list_brands(session, tenant_id=tenant.id)
    selected = brands if curate_all else [row for row in brands if row.slug == slug]
    summaries: list[CurationSummary] = []
    for row in selected:
        summaries.append(
            await _curate_brand(
                session,
                tenant_id=tenant.id,
                row=row,
                artifact_exists=artifact_exists,
            )
        )
    return summaries


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Append approved rendered creatives to Brand Kit chapters 05 and 06."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--slug", help="Curate one brand slug in the studio tenant.")
    selection.add_argument(
        "--all",
        action="store_true",
        dest="curate_all",
        help="Curate every brand in the studio tenant.",
    )
    return parser


async def _run(slug: str | None, curate_all: bool) -> list[CurationSummary]:
    engine = get_engine()
    try:
        async with get_sessionmaker()() as session:
            return await curate_brand_kits(
                session,
                slug=slug,
                curate_all=curate_all,
            )
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    slug = args.slug if isinstance(args.slug, str) else None
    curate_all = bool(args.curate_all)
    summaries = asyncio.run(_run(slug, curate_all))
    if not summaries:
        print(f"SKIPPED {slug}: brand not found in oldest tenant")
        return 1
    for summary in summaries:
        print(
            f"CURATED {summary.slug}: eligible={summary.eligible_creatives}, "
            f"templates_added={summary.templates_added}, "
            f"applications_added={summary.applications_added}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
