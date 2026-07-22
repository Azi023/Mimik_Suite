"""Seed the three reference style profiles into an existing local studio tenant.

The operator must run this from the repository root with DATABASE_URL set explicitly:

    uv run --no-sync python scripts/seed_profiles.py

The script never creates a tenant. It selects the oldest existing tenant and creates each
Client + Brand pair in one transaction. Existing profiles are skipped by their normalized
client-name slug or exact brand slug.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import repo
from api.db.models import TenantRow
from api.db.session import get_engine, get_sessionmaker
from mimik_contracts import (
    Brand,
    BrandLayout,
    BrandTokens,
    Client,
    ColorRole,
    LogoPlacement,
    Typography,
)


@dataclass(frozen=True)
class ProfileSeed:
    client: Client
    brand: Brand


def _slugify(value: str) -> str:
    """Normalize a client name to the slug format used by the style profiles."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _require_database_url() -> None:
    """Refuse the app's development fallback; this script requires an explicit local DB URL."""
    if not (os.environ.get("DATABASE_URL") or "").strip():
        raise RuntimeError(
            "DATABASE_URL must be set explicitly before running scripts/seed_profiles.py"
        )


def _profile_seeds(tenant_id: str) -> tuple[ProfileSeed, ...]:
    """Build and validate the three source-bound profiles through mimik-contracts."""
    simply_nikah_client = Client(
        tenant_id=tenant_id,
        name="Simply Nikah",
        industry="Shariah-compliant Muslim matrimonial services",
        notes="Reference client seeded from docs/STYLE_PROFILES.md.",
    )
    simply_nikah_brand = Brand(
        tenant_id=tenant_id,
        client_id=simply_nikah_client.id,
        name="Simply Nikah",
        slug="simply-nikah",
        niche="Shariah-compliant Muslim matrimonial services",
        target_audience=(
            "Muslims seeking marriage through a respectful, modest, faith-led service."
        ),
        brand_voice=(
            "Warm, respectful, gentle, and faith-led. Use a concise values-led headline, "
            "a short support line, and a soft invitation rather than a hard sell. Faith "
            "content may lead with a Quran ayah in Arabic calligraphy, followed by its "
            "translation and a gentle CTA."
        ),
        tone_keywords=[
            "warm",
            "respectful",
            "gentle",
            "faith-led",
            "modest",
            "trustworthy",
        ],
        dos=[
            "Use faceless flat-vector scenes or silhouettes with modest visual treatment.",
            "Keep the simply nikah wordmark top-center.",
            "Use generous soft-pink or cloud-white negative space.",
            "Use Deep Plum for decisive emphasis, legible text, and restrained CTAs.",
            "Use Islamic lattice, mihrab, crescent, shield, heart, and calligraphy motifs "
            "without letting ornament compete with the message.",
        ],
        donts=[
            "Do not use real photographs of people.",
            "Do not generate, source, or retain immodest imagery.",
            "Do not force a permanent header or footer band.",
            "Do not let glow, shadows, or geometric patterns overwhelm the faith-led message "
            "or generous whitespace.",
        ],
        imagery_style=(
            "Flat vector illustration using engine-generated vector assets first and "
            "AI illustration second. Every depicted person must be faceless or a silhouette; "
            "real people photography is not approved."
        ),
        tokens=BrandTokens(
            colors=[
                ColorRole(
                    name="primary",
                    hex="#FD62AD",
                    usage="Simply Pink; approximate, confirm at onboarding.",
                ),
                ColorRole(
                    name="accent",
                    hex="#F9C6DE",
                    usage="Soft Blush; approximate, confirm at onboarding.",
                ),
                ColorRole(
                    name="ink",
                    hex="#2B0A2E",
                    usage="Deep Plum; approximate, confirm at onboarding.",
                ),
                ColorRole(
                    name="cta_fill",
                    hex="#2B0A2E",
                    usage="Deep Plum; approximate, confirm at onboarding.",
                ),
                ColorRole(
                    name="secondary",
                    hex="#9B7BA6",
                    usage="Muted Lilac; approximate, confirm at onboarding.",
                ),
                ColorRole(
                    name="ground",
                    hex="#FAF7FB",
                    usage="Cloud White; approximate, confirm at onboarding.",
                ),
            ],
            typography=Typography(
                hierarchy=[
                    "Heading: bold high-emphasis display in Deep Plum; one decisive word may "
                    "be uppercase inside a solid plum box.",
                    "Body: regular or light supporting text in Deep Plum with generous "
                    "breathing room.",
                    "Greeting accent: elegant script for occasions such as Eid only.",
                    "Font families are not supplied; confirm them at onboarding.",
                ]
            ),
            layout=BrandLayout(logo_placement=LogoPlacement.TOP_CENTER),
        ),
    )

    glo2go_client = Client(
        tenant_id=tenant_id,
        name="Glo2Go Aesthetics",
        industry="Medical aesthetics",
        notes="Reference client seeded from docs/STYLE_PROFILES.md.",
    )
    glo2go_brand = Brand(
        tenant_id=tenant_id,
        client_id=glo2go_client.id,
        name="Glo2Go Aesthetics",
        slug="glo2go-aesthetics",
        niche="Medical aesthetics education and treatments",
        target_audience=(
            "People seeking credible, premium skin and aesthetic treatment education and "
            "consultations."
        ),
        brand_voice=(
            "Educational, science-led, professional, and reassuring. Lead with a clear myth "
            "or question, give a concise factual correction or explanation, then use the CTA "
            "'DM to book your free consultation.' Avoid sensational framing and keep claims "
            "medically credible."
        ),
        tone_keywords=[
            "educational",
            "science-led",
            "professional",
            "reassuring",
            "credible",
            "restrained",
        ],
        dos=[
            "Use licensed stock photography first, then realistic generated models or clinic "
            "scenes when suitable stock is unavailable.",
            "Keep imagery tasteful, medically credible, and grounded in real-photography "
            "treatment.",
            "Keep the G2G Aesthetics rounded plum pill badge at the top-right.",
            "Preserve generous white space, restrained plum hierarchy, and clear information "
            "panels.",
            "Keep each treatment claim factual, supportable, and professionally reassuring.",
        ],
        donts=[
            "Do not show the owner.",
            "Do not use illustration as the visual treatment.",
            "Do not use wild, sensational, or unsupported treatment claims.",
            "Do not let effects make the clinic feel loud or gimmicky.",
        ],
        imagery_style=(
            "Real photography using licensed stock first and AI-realistic models or clinic "
            "scenes only when stock is insufficient. The owner must never appear, and "
            "illustration is not part of the profile."
        ),
        tokens=BrandTokens(
            colors=[
                ColorRole(
                    name="primary",
                    hex="#5A2A6B",
                    usage="Deep Plum/Purple; approximate, confirm at onboarding.",
                ),
                ColorRole(
                    name="ink",
                    hex="#5A2A6B",
                    usage="Deep Plum/Purple; approximate, confirm at onboarding.",
                ),
                ColorRole(
                    name="ground",
                    hex="#FFFFFF",
                    usage="White; approximate, confirm at onboarding.",
                ),
                # STYLE_PROFILES deliberately supplies no Soft Lilac hex. ColorRole requires a
                # validated hex, so the missing accent is left unassigned instead of guessed.
            ],
            typography=Typography(
                hierarchy=[
                    "Heading: bold clean sans serif in Deep Plum/Purple, direct and scannable.",
                    "Body: lighter-weight sans serif with a calm clinical-premium feel.",
                    "Case: natural title or sentence case; avoid condensed all-caps retail "
                    "treatment.",
                    "Font families are not supplied; confirm them at onboarding.",
                ]
            ),
            layout=BrandLayout(logo_placement=LogoPlacement.TOP_RIGHT),
        ),
    )

    island_cart_client = Client(
        tenant_id=tenant_id,
        name="Island Cart",
        industry="Sri Lankan ecommerce retail",
        notes="Reference client seeded from docs/STYLE_PROFILES.md.",
    )
    island_cart_brand = Brand(
        tenant_id=tenant_id,
        client_id=island_cart_client.id,
        name="Island Cart",
        slug="island-cart",
        niche="Sri Lankan ecommerce and product advertising",
        target_audience=(
            "Sri Lankan consumers shopping practical retail products through fast, relatable, "
            "price-led social advertising."
        ),
        brand_voice=(
            "Witty, relatable, meme-like, and commercial. Lead with a large hook or everyday "
            "observation, follow with a direct product benefit, accurate product name and "
            "price, then a simple CTA. The joke earns attention; the product information "
            "closes the sale."
        ),
        tone_keywords=[
            "witty",
            "relatable",
            "meme-like",
            "commercial",
            "high-energy",
            "direct",
        ],
        dos=[
            "Use the client's actual product photography for the focal product asset.",
            "Keep product identity, product name, benefit, and price accurate.",
            "Use Bold Orange as a dominant brand signal with hard orange-white-black contrast.",
            "Keep the IslandCart logo top-left.",
            "Use fast-scanning hierarchy: hook first, product or benefit second, price third, "
            "CTA last.",
        ],
        donts=[
            "Do not replace the client's product with a different or invented product.",
            "Do not use AI illustration or AI-realistic generation as an imagery source.",
            "Do not let the gag obscure the product, benefit, price, or CTA.",
            "Do not weaken Bold Orange as the load-bearing brand signal.",
        ],
        imagery_style=(
            "Actual client product-photo cutouts as focal assets, supported by licensed "
            "lifestyle photography and engine-generated diagonal blocks or price badges. "
            "AI illustration and AI-realistic product substitutes are not approved."
        ),
        tokens=BrandTokens(
            colors=[
                ColorRole(
                    name="primary",
                    hex="#F26522",
                    usage="Bold Orange; approximate, confirm at onboarding.",
                ),
                ColorRole(
                    name="accent",
                    hex="#F26522",
                    usage=(
                        "Bold Orange; no separate accent supplied; approximate, confirm at "
                        "onboarding."
                    ),
                ),
                ColorRole(
                    name="ink",
                    hex="#000000",
                    usage="Black; approximate, confirm at onboarding.",
                ),
                ColorRole(
                    name="ground",
                    hex="#FFFFFF",
                    usage="White; approximate, confirm at onboarding.",
                ),
            ],
            typography=Typography(
                hierarchy=[
                    "Heading: huge bold condensed sans serif in all caps for the witty hook.",
                    "Body: bold clean sans serif for benefit, product name, price, and CTA.",
                    "Product details use whichever case scans most clearly at a glance.",
                    "Font families are not supplied; confirm them at onboarding.",
                ]
            ),
            layout=BrandLayout(logo_placement=LogoPlacement.TOP_LEFT),
        ),
    )

    return (
        ProfileSeed(client=simply_nikah_client, brand=simply_nikah_brand),
        ProfileSeed(client=glo2go_client, brand=glo2go_brand),
        ProfileSeed(client=island_cart_client, brand=island_cart_brand),
    )


async def _first_tenant(session: AsyncSession) -> TenantRow | None:
    """Return the deterministic first existing tenant; never invent or hardcode one."""
    stmt = select(TenantRow).order_by(TenantRow.created_at, TenantRow.id).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _seed_profiles() -> None:
    """Create missing reference clients and their brands in the existing local tenant."""
    _require_database_url()
    engine = get_engine()
    try:
        async with get_sessionmaker()() as session:
            tenant = await _first_tenant(session)
            if tenant is None:
                raise RuntimeError("No Tenant row exists; create the local studio tenant first")

            profiles = _profile_seeds(tenant.id)
            existing_clients = await repo.list_clients(session, tenant_id=tenant.id)
            existing_brands = await repo.list_brands(session, tenant_id=tenant.id)
            client_slugs = {_slugify(client.name) for client in existing_clients}
            brand_slugs = {brand.slug for brand in existing_brands}

            for profile in profiles:
                slug = profile.brand.slug
                client_exists = slug in client_slugs
                brand_exists = slug in brand_slugs
                if client_exists or brand_exists:
                    reason = "client already exists" if client_exists else "brand already exists"
                    print(f"SKIPPED {profile.client.name} ({slug}): {reason}")
                    continue

                client_fields = profile.client.model_dump(
                    mode="json", exclude={"tenant_id", "created_at"}
                )
                brand_fields = profile.brand.model_dump(
                    mode="json", exclude={"tenant_id", "created_at"}
                )
                await repo.create_client(session, tenant_id=tenant.id, **client_fields)
                await repo.create_brand(session, tenant_id=tenant.id, **brand_fields)
                await session.commit()

                client_slugs.add(slug)
                brand_slugs.add(slug)
                print(f"CREATED {profile.client.name} ({slug}): client + brand")
    finally:
        await engine.dispose()


def main() -> int:
    """CLI entry point."""
    asyncio.run(_seed_profiles())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
