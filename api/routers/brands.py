"""Brand CRUD — tenant-scoped. A brand must belong to a client in the caller's tenant."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal, principal_audit_actor, require_role
from api.core.brand_book_token import issue_brand_book_token
from api.core.config import get_settings
from api.db import repo
from api.db.mappers import to_brand
from api.db.session import get_session
from creative.render.compositor import render_url_element_to_png, render_url_to_pdf
from mimik_contracts import ActorRole, Brand, BrandKit, BrandTokens, ColorRole, Reference

router = APIRouter(prefix="/brands", tags=["brands"])

# Team roles that may manage/export a brand book (mirrors create/update_brand). A bounded client
# principal never publishes or exports — that is a studio action (constraint #3).
_TEAM_ROLES = ("owner", "admin", "ops", "designer", "team")

# The six brand-book chapters, keyed to `<section data-kit-section="{key}">` in the web book.
# The shared contract with the frontend registry (web/components/brand-kit/registry.ts) — an
# unknown key is a 422, never a blind render.
_KIT_SECTION_KEYS = frozenset(
    {"discovery", "direction", "logo_suite", "colours_fonts", "applications", "launch_templates"}
)


class BrandBookShare(BaseModel):
    """Publish/unpublish response — the share state the studio control bar renders."""

    published: bool
    share_url: str | None = None
    token: str | None = None


class CreateBrand(BaseModel):
    client_id: str
    name: str
    slug: str
    niche: str | None = None
    services: list[str] = Field(default_factory=list)
    target_audience: str | None = None
    brand_voice: str | None = None
    tone_keywords: list[str] = Field(default_factory=list)
    dos: list[str] = Field(default_factory=list)
    donts: list[str] = Field(default_factory=list)
    handles: dict[str, str] = Field(default_factory=dict)
    imagery_style: str | None = None
    # Design tokens at creation (colors/typography/logo) — validated by the contract, so a
    # payload can't smuggle an unsafe logo ref past the asset-ref validator.
    tokens: BrandTokens = Field(default_factory=BrandTokens)
    # Vetted aesthetic references the client shares at onboarding (Pinterest / existing designs /
    # social posts / websites, with an optional note). fit_score stays None until a later ingest
    # pass scores them; these are the human-curated seeds of the mood board.
    references: list[Reference] = Field(default_factory=list)


class UpdateBrandColors(BaseModel):
    model_config = ConfigDict(extra="forbid")

    colors: list[ColorRole]


class UpdateBrandBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    niche: str | None = None
    target_audience: str | None = None
    brand_voice: str | None = None
    tone_keywords: list[str] = Field(default_factory=list)
    imagery_style: str | None = None
    dos: list[str] = Field(default_factory=list)
    donts: list[str] = Field(default_factory=list)
    tokens: UpdateBrandColors | None = None


@router.post("", response_model=Brand, status_code=201)
async def create_brand(
    body: CreateBrand,
    # TEAM action — a bounded client principal never provisions brands (constraint #3).
    principal: Principal = Depends(require_role("owner", "admin", "ops", "designer", "team")),
    session: AsyncSession = Depends(get_session),
) -> Brand:
    # The client must exist within the caller's tenant — else this is a cross-tenant attach.
    client = await repo.get_client(
        session, tenant_id=principal.tenant_id, client_id=body.client_id
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    fields = body.model_dump()
    fields["tokens"] = body.tokens.model_dump(mode="json")
    fields["references"] = [r.model_dump(mode="json") for r in body.references]
    row = await repo.create_brand(session, tenant_id=principal.tenant_id, **fields)
    await session.commit()
    return to_brand(row)


@router.patch("/{brand_id}", response_model=Brand)
async def update_brand(
    brand_id: str,
    body: UpdateBrandBrief | BrandTokens,
    principal: Principal = Depends(require_role("owner", "admin", "ops", "designer", "team")),
    session: AsyncSession = Depends(get_session),
) -> Brand:
    """Update the editable brief or replace the full brand kit, always tenant-scoped."""
    row = await repo.get_brand(session, tenant_id=principal.tenant_id, brand_id=brand_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    if isinstance(body, BrandTokens):
        fields: dict[str, object] = {"tokens": body.model_dump(mode="json")}
    else:
        # TODO(brief-versioning): v1 edits the brand brief in place; introduce immutable brief
        # versions only when that later locked concern is designed end-to-end.
        fields = body.model_dump(exclude_unset=True, exclude={"tokens"})
        if body.tokens is not None:
            current_tokens = BrandTokens.model_validate(row.tokens)
            updated_tokens = current_tokens.model_copy(update={"colors": body.tokens.colors})
            fields["tokens"] = updated_tokens.model_dump(mode="json")

    if fields:
        updated = await repo.update_brand(
            session,
            tenant_id=principal.tenant_id,
            brand_id=brand_id,
            **fields,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Brand not found")
        row = updated
    await session.commit()
    return to_brand(row)


@router.get("/{brand_id}", response_model=Brand)
async def get_brand(
    brand_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Brand:
    row = await repo.get_brand(session, tenant_id=principal.tenant_id, brand_id=brand_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    # A client principal may only read its OWN client's brand — another client's brand id is a 404
    # (bounded portal, data-layer authZ; constraint #2).
    if principal.role == ActorRole.CLIENT.value and row.client_id != principal.client_id:
        raise HTTPException(status_code=404, detail="Brand not found")
    return to_brand(row)


@router.delete("/{brand_id}", status_code=204)
async def delete_brand(
    brand_id: str,
    principal: Principal = Depends(require_role("owner", "admin")),
    session: AsyncSession = Depends(get_session),
) -> Response:
    row = await repo.soft_delete_brand(
        session,
        tenant_id=principal.tenant_id,
        brand_id=brand_id,
        actor=principal_audit_actor(principal),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    await session.commit()
    return Response(status_code=204)


async def _set_published(
    session: AsyncSession, *, tenant_id: str, brand_id: str, published: bool
) -> BrandKit:
    """Flip ONLY `kit.published`, non-destructively (all other kit fields round-trip untouched),
    always tenant-scoped. Raises 404 if the brand isn't in the caller's tenant."""
    row = await repo.get_brand(session, tenant_id=tenant_id, brand_id=brand_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    kit = BrandKit.model_validate(row.kit) if row.kit else BrandKit()
    kit = kit.model_copy(update={"published": published})
    updated = await repo.update_brand(
        session, tenant_id=tenant_id, brand_id=brand_id, kit=kit.model_dump(mode="json")
    )
    if updated is None:  # lost a race with a concurrent delete/move
        raise HTTPException(status_code=404, detail="Brand not found")
    await session.commit()
    return kit


@router.post("/{brand_id}/brand-book/publish", response_model=BrandBookShare)
async def publish_brand_book(
    brand_id: str,
    principal: Principal = Depends(require_role(*_TEAM_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> BrandBookShare:
    """Publish the brand book: flip `kit.published` True and mint a long-lived SHARE token whose
    /book/{token} link anyone can read while the book stays published."""
    await _set_published(
        session, tenant_id=principal.tenant_id, brand_id=brand_id, published=True
    )
    token = issue_brand_book_token(
        brand_id=brand_id, tenant_id=principal.tenant_id, kind="share"
    )
    base = get_settings().app_base_url.rstrip("/")
    return BrandBookShare(
        published=True, share_url=f"{base}/book/{token}", token=token
    )


@router.post("/{brand_id}/brand-book/unpublish", response_model=BrandBookShare)
async def unpublish_brand_book(
    brand_id: str,
    principal: Principal = Depends(require_role(*_TEAM_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> BrandBookShare:
    """Unpublish: flip `kit.published` False. The flag is the authority — any share token already
    handed out still verifies cryptographically but the token-read endpoint 404s once unpublished."""
    await _set_published(
        session, tenant_id=principal.tenant_id, brand_id=brand_id, published=False
    )
    return BrandBookShare(published=False, share_url=None)


async def _mint_export_url(
    session: AsyncSession,
    *,
    tenant_id: str,
    brand_id: str,
    query: str,
) -> tuple[str, str]:
    """Tenant-scoped brand lookup + short-lived EXPORT token → the internal /book URL to render.
    Returns (url, brand_slug). 404 if the brand isn't in the caller's tenant."""
    row = await repo.get_brand(session, tenant_id=tenant_id, brand_id=brand_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    token = issue_brand_book_token(brand_id=brand_id, tenant_id=tenant_id, kind="export")
    base = get_settings().web_internal_url.rstrip("/")
    url = f"{base}/book/{quote(token, safe='')}?{query}"
    return url, row.slug


@router.get("/{brand_id}/brand-book.pdf")
async def export_brand_book_pdf(
    brand_id: str,
    principal: Principal = Depends(require_role(*_TEAM_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Render the whole brand book to PDF via the internal web /book route (export kind bypasses
    the published gate). Team-gated, tenant-scoped. Returns application/pdf as an attachment."""
    url, slug = await _mint_export_url(
        session, tenant_id=principal.tenant_id, brand_id=brand_id, query="export=pdf"
    )
    # TODO(audit): record a Delivery for the exported book once an export-delivery helper exists;
    # today deliveries are creative-doc scoped, so there is no trivial brand-book target to reuse.
    pdf = await render_url_to_pdf(url)
    filename = f"{slug}-brand-book.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{brand_id}/brand-book/{section_key}.png")
async def export_brand_book_section_png(
    brand_id: str,
    section_key: str,
    principal: Principal = Depends(require_role(*_TEAM_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Screenshot one brand-book chapter to PNG (2×) via the internal web /book route. Validates
    the section key against the six known chapters (422 otherwise). Team-gated, tenant-scoped."""
    if section_key not in _KIT_SECTION_KEYS:
        raise HTTPException(status_code=422, detail="Unknown brand-book section")
    url, slug = await _mint_export_url(
        session,
        tenant_id=principal.tenant_id,
        brand_id=brand_id,
        query=f"export=png&section={quote(section_key, safe='')}",
    )
    png = await render_url_element_to_png(url, f'[data-kit-section="{section_key}"]', scale=2)
    filename = f"{slug}-{section_key}.png"
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
