"""Fill empty Brand Kit and Brief copy for the three dogfood brands.

Run from the repository root after migrations have been applied:

    python scripts/seed_brand_copy.py

The script selects the oldest existing tenant, resolves brands by their STYLE_PROFILES slug,
and fills only fields that are empty or ``None``. Operator-authored Brand Kit and Brief content
is never overwritten. Re-running the script is therefore a no-op for fields already populated.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import repo
from api.db.mappers import to_brand, to_brief
from api.db.models import BriefRow, TenantRow
from api.db.session import get_engine, get_sessionmaker
from mimik_contracts import BrandTokens, BriefSections, Reference


@dataclass(frozen=True, slots=True)
class BriefCopySeed:
    snapshot: str
    logo_notes: str
    voice_tone: str
    imagery_style: str
    guardrails_dos: tuple[str, ...]
    guardrails_donts: tuple[str, ...]
    references: tuple[Reference, ...]
    deliverable_formats: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BrandCopySeed:
    discovery: dict[str, str]
    direction: dict[str, str]
    brief: BriefCopySeed


@dataclass(frozen=True, slots=True)
class CopySummary:
    slug: str
    filled: tuple[str, ...]
    skipped: tuple[str, ...]
    brief_missing: bool = False


_SEEDS: dict[str, BrandCopySeed] = {
    "simply-nikah": BrandCopySeed(
        discovery={
            "vision": (
                "To become the trusted place where Muslims can pursue marriage with clear "
                "intention, dignity, and faith at every step."
            ),
            "visual_competitor_analysis": (
                "Muslim matrimonial brands often lean on generic couple photography, app-screen "
                "collages, and loud pink romance cues. Simply Nikah will not show real people or "
                "borrow dating-app gloss; it will use modest faceless scenes, protective Islamic "
                "motifs, and calm space to make trust visible."
            ),
            "existing_brand_review": (
                "The warm pink and deep-plum palette, faith-led language, and modest visual intent "
                "are worth keeping. The refresh retires one-off ornament, generic people imagery, "
                "and inconsistent emphasis in favour of a repeatable faceless vector system with "
                "clearer hierarchy."
            ),
        },
        direction={
            "personality_alignment": (
                "Soft blush space and balanced compositions feel gentle and unhurried, while Deep "
                "Plum emphasis, mihrab forms, and protective symbols make the brand feel principled, "
                "safe, and quietly confident."
            ),
            "competitor_differentiation": (
                "Simply Nikah owns modest, faith-led matrimonial guidance expressed without people "
                "photography: a recognisable system of faceless vectors, Islamic framing, and soft "
                "invitations rather than dating-category spectacle."
            ),
        },
        brief=BriefCopySeed(
            snapshot=(
                "Simply Nikah is a Shariah-compliant matrimonial service for Muslims seeking a "
                "respectful path to marriage. Its brand promise is warm guidance, protected "
                "communication, and clear intention without the visual language of mainstream dating."
            ),
            logo_notes=(
                "Keep the simply nikah wordmark top-centre with generous clear space. Use Deep Plum "
                "or an approved high-contrast version, and never let lattice, glow, or illustration "
                "compete with it."
            ),
            voice_tone=(
                "Warm, respectful, gentle, and faith-led. Lead with a concise value or ayah-led "
                "message, add one clear support line, and close with a soft invitation rather than "
                "a hard sell."
            ),
            imagery_style=(
                "Faceless flat-vector scenes and silhouettes built from modest Islamic frames, "
                "lattice, crescents, shields, hearts, calligraphy panels, and calm pink or white space."
            ),
            guardrails_dos=(
                "Use faceless figures or silhouettes with modest clothing and poses.",
                "Keep the wordmark top-centre and preserve generous quiet space.",
                "Use Deep Plum for decisive, readable emphasis and restrained calls to action.",
            ),
            guardrails_donts=(
                "Do not use real photographs of people or immodest imagery.",
                "Do not let ornament, glow, or shadow overpower the faith-led message.",
                "Do not force the same header, footer, or hero layout onto every piece.",
            ),
            references=(
                Reference(
                    url="docs/STYLE_PROFILES.md#profile-1-simply-nikah",
                    source="Mimik Suite style profile",
                    note="Approved source for Simply Nikah's visual and verbal direction.",
                ),
            ),
            deliverable_formats=(
                "Instagram post (1080x1080)",
                "Instagram carousel (1080x1080)",
                "Story or status creative (1080x1920)",
            ),
        ),
    ),
    "glo2go-aesthetics": BrandCopySeed(
        discovery={
            "vision": (
                "To be the clinic people trust for calm, evidence-led aesthetic guidance before "
                "they make a treatment decision."
            ),
            "visual_competitor_analysis": (
                "Aesthetics competitors often rely on crowded before-and-after grids, metallic "
                "luxury cues, and dramatic transformation claims. Glo2Go will not chase cosmetic "
                "spectacle; credible photography, porcelain space, plum type, and disciplined "
                "information panels will keep education in command."
            ),
            "existing_brand_review": (
                "Clinical Plum, clean white space, and an education-first voice already give Glo2Go "
                "a credible base. The refresh keeps that authority while retiring inconsistent "
                "photo treatments, crowded copy, and decorative effects that make medical guidance "
                "feel promotional."
            ),
        },
        direction={
            "personality_alignment": (
                "Generous white space slows the read, Clinical Plum creates measured authority, and "
                "real photography with translucent panels makes complex treatment information feel "
                "clear, premium, and reassuring."
            ),
            "competitor_differentiation": (
                "Glo2Go owns the calm clinical educator corner: every visual teaches one credible "
                "skin-science point before it invites a consultation, instead of selling a dramatic "
                "transformation first."
            ),
        },
        brief=BriefCopySeed(
            snapshot=(
                "Glo2Go Aesthetics is an education-led medical aesthetics brand for people who want "
                "to understand skin and treatment choices before booking. It pairs clinical "
                "credibility with a calm, quietly premium consultation experience."
            ),
            logo_notes=(
                "Use the G2G Aesthetics mark as a compact rounded plum badge at the top-right. Keep "
                "the badge clear of faces, treatment areas, and educational labels, with enough "
                "white space to remain composed."
            ),
            voice_tone=(
                "Educational, science-led, professional, and reassuring. Open with a myth or clear "
                "question, explain the fact concisely, avoid unsupported claims, and end with a soft "
                "consultation invitation."
            ),
            imagery_style=(
                "Tasteful real skin, model, treatment, or clinic photography with restrained plum "
                "typography, generous white space, and translucent information panels where needed."
            ),
            guardrails_dos=(
                "Use credible licensed photography or realistic clinic imagery when stock is insufficient.",
                "Keep claims factual, supportable, and easy to understand.",
                "Preserve generous white space and a stable top-right plum brand badge.",
            ),
            guardrails_donts=(
                "Do not show the owner.",
                "Do not use illustration, sensational transformations, or unsupported medical claims.",
                "Do not crowd the frame or use effects that make the clinic feel loud or gimmicky.",
            ),
            references=(
                Reference(
                    url="docs/STYLE_PROFILES.md#profile-2-glo2go-aesthetics",
                    source="Mimik Suite style profile",
                    note="Approved source for Glo2Go's clinical-premium direction.",
                ),
            ),
            deliverable_formats=(
                "Instagram education post (1080x1080)",
                "Instagram carousel (1080x1080)",
                "Story or treatment explainer (1080x1920)",
            ),
        ),
    ),
    "island-cart": BrandCopySeed(
        discovery={
            "vision": (
                "To become Sri Lanka's most instantly recognisable destination for practical "
                "products explained with wit, clarity, and honest value."
            ),
            "visual_competitor_analysis": (
                "Local ecommerce advertising often defaults to crowded product grids, generic "
                "discount bursts, and interchangeable red-and-yellow sale graphics. Island Cart "
                "will not bury the product in noise or fake imagery; one real cutout, one relatable "
                "hook, and hard orange-white-black hierarchy must do the selling."
            ),
            "existing_brand_review": (
                "Bold Orange and the direct, relatable retail voice already provide strong recall. "
                "The refresh keeps that energy while retiring inconsistent product treatment, "
                "unstructured meme layouts, and any joke that delays the product, benefit, price, "
                "or call to action."
            ),
        },
        direction={
            "personality_alignment": (
                "Oversized condensed hooks deliver the wit, sharp diagonal blocks create momentum, "
                "and real product cutouts with blunt price cues keep the personality useful, direct, "
                "and unapologetically commercial."
            ),
            "competitor_differentiation": (
                "Island Cart owns witty Sri Lankan utility retail: locally relatable hooks earn the "
                "pause, then an accurate real product, clear benefit, and visible price close the sale "
                "in one fast scan."
            ),
        },
        brief=BriefCopySeed(
            snapshot=(
                "Island Cart is a Sri Lankan ecommerce brand selling practical products through "
                "fast, relatable social advertising. Its system turns an everyday observation into "
                "a clear product, benefit, price, and action without retail clutter."
            ),
            logo_notes=(
                "Keep the IslandCart logo top-left with hard contrast against orange, white, or a "
                "dark photo field. Protect it from oversized hook text and never treat it as another "
                "sale badge."
            ),
            voice_tone=(
                "Witty, relatable, meme-like, and commercial. Lead with a sharp everyday hook, then "
                "state the accurate product, useful benefit, price, and a simple call to action."
            ),
            imagery_style=(
                "The client's real product photo as a clean cutout, supported by licensed lifestyle "
                "photography, hard orange-and-white diagonals, huge type, price pills, and controlled "
                "drop shadows."
            ),
            guardrails_dos=(
                "Use the client's actual product photo and keep identity, name, benefit, and price accurate.",
                "Make Bold Orange dominant and preserve fast orange-white-black contrast.",
                "Keep the scan order clear: hook, product or benefit, price, then call to action.",
            ),
            guardrails_donts=(
                "Do not invent, substitute, or materially alter the product.",
                "Do not use AI illustration or AI-realistic product substitutes.",
                "Do not let the gag, layout, or decoration obscure the offer details.",
            ),
            references=(
                Reference(
                    url="docs/STYLE_PROFILES.md#profile-3-island-cart",
                    source="Mimik Suite style profile",
                    note="Approved source for Island Cart's high-energy retail direction.",
                ),
            ),
            deliverable_formats=(
                "Instagram product post (1080x1080)",
                "Instagram carousel (1080x1080)",
                "Story or offer creative (1080x1920)",
            ),
        ),
    ),
}


def _empty_text(value: str | None) -> bool:
    return value is None or not value.strip()


def _brief_tokens_empty(tokens: BrandTokens) -> bool:
    return tokens == BrandTokens()


def _fill_brief_sections(
    sections: BriefSections,
    brand_tokens: BrandTokens,
    seed: BriefCopySeed,
    filled: list[str],
    skipped: list[str],
) -> None:
    text_fields = ("snapshot", "logo_notes", "voice_tone", "imagery_style")
    for name in text_fields:
        path = f"brief.{name}"
        if _empty_text(getattr(sections, name)):
            setattr(sections, name, getattr(seed, name))
            filled.append(path)
        else:
            skipped.append(path)

    if _brief_tokens_empty(sections.tokens):
        sections.tokens = brand_tokens.model_copy(deep=True)
        filled.append("brief.tokens")
    else:
        skipped.append("brief.tokens")

    list_fields = ("guardrails_dos", "guardrails_donts", "references", "deliverable_formats")
    for name in list_fields:
        path = f"brief.{name}"
        if not getattr(sections, name):
            setattr(sections, name, list(getattr(seed, name)))
            filled.append(path)
        else:
            skipped.append(path)


async def _first_tenant(session: AsyncSession) -> TenantRow | None:
    stmt = select(TenantRow).order_by(TenantRow.created_at, TenantRow.id).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


def _latest_briefs_by_brand(briefs: list[BriefRow]) -> dict[str, BriefRow]:
    latest: dict[str, BriefRow] = {}
    for brief in briefs:
        latest[brief.brand_id] = brief
    return latest


async def seed_brand_copy(session: AsyncSession) -> list[CopySummary]:
    """Fill empty copy fields for matching brands in the oldest tenant."""
    tenant = await _first_tenant(session)
    if tenant is None:
        raise RuntimeError("No Tenant row exists; create the studio tenant first")

    briefs = await repo.list_briefs(session, tenant_id=tenant.id)
    latest_brief = _latest_briefs_by_brand(briefs)
    summaries: list[CopySummary] = []

    for row in await repo.list_brands(session, tenant_id=tenant.id):
        copy_seed = _SEEDS.get(row.slug)
        if copy_seed is None:
            continue

        brand = to_brand(row)
        filled: list[str] = []
        skipped: list[str] = []

        for section_name, model, values in (
            ("discovery", brand.kit.discovery, copy_seed.discovery),
            ("direction", brand.kit.direction, copy_seed.direction),
        ):
            for name, value in values.items():
                path = f"kit.{section_name}.{name}"
                if _empty_text(getattr(model, name)):
                    setattr(model, name, value)
                    filled.append(path)
                else:
                    skipped.append(path)

        brief_row = latest_brief.get(row.id)
        brief_missing = brief_row is None
        if brief_row is not None:
            sections = to_brief(brief_row).sections
            _fill_brief_sections(sections, brand.tokens, copy_seed.brief, filled, skipped)
            brief_row.sections = sections.model_dump(mode="json")

        updated = await repo.update_brand(
            session,
            tenant_id=tenant.id,
            brand_id=row.id,
            kit=brand.kit.model_dump(mode="json"),
        )
        if updated is None:
            raise RuntimeError(f"Brand disappeared during copy seeding: {row.slug}")
        await session.commit()
        summaries.append(
            CopySummary(
                slug=row.slug,
                filled=tuple(filled),
                skipped=tuple(skipped),
                brief_missing=brief_missing,
            )
        )

    return summaries


async def _run() -> list[CopySummary]:
    engine = get_engine()
    try:
        async with get_sessionmaker()() as session:
            return await seed_brand_copy(session)
    finally:
        await engine.dispose()


def main() -> int:
    summaries = asyncio.run(_run())
    for summary in summaries:
        filled = ", ".join(summary.filled) or "none"
        skipped = ", ".join(summary.skipped) or "none"
        brief_note = "; linked brief not found" if summary.brief_missing else ""
        print(
            f"SEEDED {summary.slug}: filled=[{filled}]; skipped-already-set=[{skipped}]{brief_note}"
        )
    missing = sorted(set(_SEEDS) - {summary.slug for summary in summaries})
    for slug in missing:
        print(f"SKIPPED {slug}: brand not found in oldest tenant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
