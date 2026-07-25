"""Add source-bound Brand Kit v2 metadata to the three reference brands.

Run from the repository root after migrations have been applied:

    python scripts/seed_brand_kit.py

The script selects the oldest existing tenant, updates only brands with the three known
STYLE_PROFILES slugs, and merges without removing operator-authored colors, font roles, or kit
content. Re-running it deterministically refreshes the source-derived fields without duplicates.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import repo
from api.db.mappers import to_brand
from api.db.models import TenantRow
from api.db.session import get_engine, get_sessionmaker
from mimik_contracts import (
    Brand,
    BrandDiscovery,
    BrandKit,
    ColorRole,
    CreativeDirection,
    FontRole,
    PendingColor,
)


@dataclass(frozen=True, slots=True)
class ColorSeed:
    role: str
    hex: str
    display_name: str
    rationale: str
    confirmed: bool = False


@dataclass(frozen=True, slots=True)
class PendingColorSeed:
    name: str
    display_name: str
    rationale: str


@dataclass(frozen=True, slots=True)
class FontSeed:
    role: Literal["display", "heading", "subheading", "body", "accent", "arabic"]
    builtin_key: str
    family: str
    weights: tuple[str, ...]
    sample_text: str


@dataclass(frozen=True, slots=True)
class BrandKitSeed:
    colors: tuple[ColorSeed, ...]
    pending_colors: tuple[PendingColorSeed, ...]
    fonts: tuple[FontSeed, ...]
    discovery: dict[str, object]
    direction: dict[str, str]


@dataclass(frozen=True, slots=True)
class EnrichmentSummary:
    slug: str
    colors: int
    pending_colors: int
    font_roles: int
    discovery_fields: int
    direction_fields: int


_SEEDS: dict[str, BrandKitSeed] = {
    "simply-nikah": BrandKitSeed(
        colors=(
            ColorSeed(
                "primary",
                "#FD62AD",
                "Simply Pink",
                "The warm brand signal that makes matrimonial communication feel human and inviting.",
            ),
            ColorSeed(
                "accent",
                "#F9C6DE",
                "Soft Blush",
                "Creates gentle breathing room behind faith-led messages and modest illustrations.",
            ),
            ColorSeed(
                "ink",
                "#2B0A2E",
                "Deep Plum",
                "Gives headlines and supporting text decisive contrast without becoming harsh.",
            ),
            ColorSeed(
                "cta_fill",
                "#2B0A2E",
                "Deep Plum",
                "Anchors highlighted words and restrained calls to action with trustworthy emphasis.",
            ),
            ColorSeed(
                "secondary",
                "#9B7BA6",
                "Muted Lilac",
                "Adds a quiet bridge between the pink palette and protective plum emphasis.",
            ),
            ColorSeed(
                "ground",
                "#FAF7FB",
                "Cloud White",
                "Keeps the canvas airy, modest, and calm while ornamental motifs stay secondary.",
            ),
        ),
        pending_colors=(),
        fonts=(
            FontSeed(
                "heading",
                "playfair-display",
                "Playfair Display",
                ("400", "700"),
                "Right intention, beautifully expressed.",
            ),
            FontSeed(
                "body",
                "nunito",
                "Nunito",
                ("400", "700"),
                "Warm, gentle guidance with room to breathe.",
            ),
            FontSeed(
                "arabic",
                "amiri",
                "Amiri",
                ("400", "700"),
                "وَمِنْ آيَاتِهِ أَنْ خَلَقَ لَكُم",
            ),
        ),
        discovery={
            "purpose": (
                "Help Muslims approach marriage through respectful, modest, Shariah-compliant "
                "communication."
            ),
            "personality": "Warm, protective, gentle, faith-led, and quietly trustworthy.",
            "values": ["Faith-led", "Modest", "Respectful", "Trustworthy", "Gentle"],
            "tone_of_voice": (
                "Warm, respectful, gentle, and faith-led: concise values-led headlines, short "
                "supporting lines, and soft invitations rather than hard sells."
            ),
            "key_usp": (
                "A matrimonial service expressed through a consistently modest, faceless, "
                "faith-led visual language instead of conventional people photography."
            ),
        },
        direction={
            "palette_rationale": (
                "Simply Pink and Soft Blush create warmth and space; Deep Plum supplies trusted "
                "contrast, while Muted Lilac and Cloud White keep the system gentle."
            ),
            "visual_tone": (
                "Faceless flat-vector scenes, protective Islamic motifs, soft pink space, and "
                "decisive deep-plum emphasis with restrained glow and shadow."
            ),
        },
    ),
    "glo2go-aesthetics": BrandKitSeed(
        colors=(
            ColorSeed(
                "primary",
                "#5A2A6B",
                "Clinical Plum",
                "The medical authority: serious depth without corporate coldness.",
            ),
            ColorSeed(
                "ink",
                "#5A2A6B",
                "Clinical Plum",
                "Keeps educational typography credible, restrained, and unmistakably branded.",
            ),
            ColorSeed(
                "ground",
                "#FFFFFF",
                "Porcelain",
                "The clinic itself: open, clean, load-bearing whitespace for premium clarity.",
            ),
        ),
        pending_colors=(
            PendingColorSeed(
                "accent",
                "Soft Lilac",
                "Adds one gentle accent to the clinical palette; the source hex is still pending.",
            ),
        ),
        fonts=(
            FontSeed(
                "heading",
                "montserrat",
                "Montserrat",
                ("400", "700"),
                "Modern brands move with purpose.",
            ),
            FontSeed(
                "body",
                "lato",
                "Lato",
                ("400", "700"),
                "Warm, confident, and easy to read.",
            ),
        ),
        discovery={
            "purpose": (
                "Replace beauty-industry noise and myth with calm, credible skin education so "
                "clients understand a treatment before they book it."
            ),
            "personality": (
                "Precise, unhurried, quietly premium, reassuring, and never salesy or cold."
            ),
            "values": ["Credible", "Calm", "Science-led", "Premium", "Reassuring"],
            "tone_of_voice": (
                "Educational, science-led, professional, and reassuring: open with a myth or "
                "question, correct it concisely, and close with a soft consultation invitation."
            ),
            "key_usp": (
                "Education-first aesthetics: every campaign teaches a small, medically credible "
                "skin-science lesson before asking the audience to book."
            ),
        },
        direction={
            "palette_rationale": (
                "Clinical Plum carries medical authority while Porcelain whitespace keeps the "
                "clinic open and premium; pending Soft Lilac will add a single gentle note."
            ),
            "visual_tone": (
                "Credible real photography, restrained plum typography, generous white space, "
                "and polished translucent information panels."
            ),
        },
    ),
    "island-cart": BrandKitSeed(
        colors=(
            ColorSeed(
                "primary",
                "#F26522",
                "Bold Orange",
                "The load-bearing retail signal that creates energy and instant recognition.",
            ),
            ColorSeed(
                "accent",
                "#F26522",
                "Bold Orange",
                "Repeats the primary signal on price tags and calls to action for fast scanning.",
            ),
            ColorSeed(
                "ink",
                "#000000",
                "Retail Black",
                "Delivers maximum contrast for oversized hooks, benefits, prices, and details.",
            ),
            ColorSeed(
                "ground",
                "#FFFFFF",
                "Clean White",
                "Separates product cutouts and hard orange geometry without visual noise.",
            ),
        ),
        pending_colors=(),
        fonts=(
            FontSeed(
                "heading",
                "poppins",
                "Poppins",
                ("400", "700"),
                "BIG HOOK. CLEAR PRODUCT. FAST SALE.",
            ),
            FontSeed(
                "body",
                "inter",
                "Inter",
                ("400", "700"),
                "Product, benefit, price, and CTA at a glance.",
            ),
        ),
        discovery={
            "purpose": (
                "Make practical products immediately understandable and desirable through fast, "
                "relatable Sri Lankan retail communication."
            ),
            "personality": "Witty, relatable, high-energy, direct, and unapologetically commercial.",
            "values": ["Accurate", "Relatable", "Direct", "Useful", "Commercial"],
            "tone_of_voice": (
                "Witty, meme-like, and commercial: earn attention with a relatable hook, then "
                "close with the accurate product, benefit, price, and a simple CTA."
            ),
            "key_usp": (
                "Real client product photography paired with locally relatable hooks and an "
                "orange-led sales system that scans instantly."
            ),
        },
        direction={
            "palette_rationale": (
                "Bold Orange supplies the energy and recognition; Retail Black and Clean White "
                "create the hard contrast needed for product, price, and CTA hierarchy."
            ),
            "visual_tone": (
                "Actual product cutouts, hard orange-and-white geometry, huge witty type, and "
                "instantly scannable price and benefit cues."
            ),
        },
    ),
}


def _normalized(value: str) -> str:
    return value.strip().lower().replace("_", "-").replace(" ", "-")


def _merge_colors(brand: Brand, seeds: tuple[ColorSeed, ...]) -> None:
    colors = list(brand.tokens.colors)
    for seed in seeds:
        role_match = next(
            (color for color in colors if _normalized(color.name) == _normalized(seed.role)),
            None,
        )
        metadata = {
            "display_name": seed.display_name,
            "rationale": seed.rationale,
            "confirmed": seed.confirmed,
        }
        if role_match is None:
            colors.append(ColorRole(name=seed.role, hex=seed.hex, **metadata))
            continue
        colors[colors.index(role_match)] = role_match.model_copy(update=metadata)
    brand.tokens.colors = colors


def _merge_fonts(brand: Brand, seeds: tuple[FontSeed, ...]) -> None:
    roles = list(brand.tokens.typography.font_roles)
    for seed in seeds:
        replacement = FontRole(
            role=seed.role,
            source="builtin",
            builtin_key=seed.builtin_key,
            weights=list(seed.weights),
            sample_text=seed.sample_text,
        )
        index = next((i for i, role in enumerate(roles) if role.role == seed.role), None)
        if index is None:
            roles.append(replacement)
        else:
            roles[index] = replacement
        if seed.role == "heading":
            brand.tokens.typography.heading_font = seed.family
        elif seed.role == "body":
            brand.tokens.typography.body_font = seed.family
    brand.tokens.typography.font_roles = roles


def _merge_pending_colors(kit: BrandKit, seeds: tuple[PendingColorSeed, ...]) -> None:
    pending = list(kit.pending_colors)
    for seed in seeds:
        replacement = PendingColor(
            name=seed.name,
            display_name=seed.display_name,
            rationale=seed.rationale,
        )
        index = next(
            (i for i, color in enumerate(pending) if _normalized(color.name) == _normalized(seed.name)),
            None,
        )
        if index is None:
            pending.append(replacement)
        else:
            pending[index] = replacement
    kit.pending_colors = pending


def _merge_model_fields(model: BrandDiscovery | CreativeDirection, fields: dict[str, object]) -> None:
    for name, value in fields.items():
        setattr(model, name, value)


def enrich_brand(brand: Brand, seed: BrandKitSeed) -> Brand:
    """Return one enriched copy while retaining fields outside the source-derived set."""
    enriched = brand.model_copy(deep=True)
    _merge_colors(enriched, seed.colors)
    _merge_fonts(enriched, seed.fonts)
    _merge_pending_colors(enriched.kit, seed.pending_colors)
    _merge_model_fields(enriched.kit.discovery, seed.discovery)
    _merge_model_fields(enriched.kit.direction, seed.direction)
    return enriched


async def _first_tenant(session: AsyncSession) -> TenantRow | None:
    stmt = select(TenantRow).order_by(TenantRow.created_at, TenantRow.id).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


async def enrich_brand_kits(session: AsyncSession) -> list[EnrichmentSummary]:
    """Enrich matching brands in the oldest tenant and commit each update independently."""
    tenant = await _first_tenant(session)
    if tenant is None:
        raise RuntimeError("No Tenant row exists; create the studio tenant first")

    summaries: list[EnrichmentSummary] = []
    brands = await repo.list_brands(session, tenant_id=tenant.id)
    for row in brands:
        seed = _SEEDS.get(row.slug)
        if seed is None:
            continue
        enriched = enrich_brand(to_brand(row), seed)
        updated = await repo.update_brand(
            session,
            tenant_id=tenant.id,
            brand_id=row.id,
            tokens=enriched.tokens.model_dump(mode="json"),
            kit=enriched.kit.model_dump(mode="json"),
        )
        if updated is None:
            raise RuntimeError(f"Brand disappeared during enrichment: {row.slug}")
        await session.commit()
        summaries.append(
            EnrichmentSummary(
                slug=row.slug,
                colors=len(enriched.tokens.colors),
                pending_colors=len(enriched.kit.pending_colors),
                font_roles=len(enriched.tokens.typography.font_roles),
                discovery_fields=len(seed.discovery),
                direction_fields=len(seed.direction),
            )
        )
    return summaries


async def _run() -> list[EnrichmentSummary]:
    engine = get_engine()
    try:
        async with get_sessionmaker()() as session:
            return await enrich_brand_kits(session)
    finally:
        await engine.dispose()


def main() -> int:
    summaries = asyncio.run(_run())
    for summary in summaries:
        print(
            f"ENRICHED {summary.slug}: colors={summary.colors}, "
            f"pending_colors={summary.pending_colors}, font_roles={summary.font_roles}, "
            f"discovery_fields={summary.discovery_fields}, "
            f"direction_fields={summary.direction_fields}"
        )
    missing = sorted(set(_SEEDS) - {summary.slug for summary in summaries})
    for slug in missing:
        print(f"SKIPPED {slug}: brand not found in oldest tenant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
