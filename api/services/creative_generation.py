"""First-class Studio creative generation and persisted artifact orchestration."""

from __future__ import annotations

import asyncio
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, is_client_in_scope
from api.db import repo
from api.db.mappers import to_brand, to_creative_doc
from api.db.models import CreativeDocRow, JobRow
from creative import art_direction
from creative.copy import l0 as copy_l0
from creative.export import svg as svg_export
from creative.pipeline import build_manifest
from creative.references import gather as reference_gather
from creative.render import glo2go_templates
from creative.style_profile import ImageSource, StyleProfile, get_style_profile
from creative.vision import text_region as vision_text_region
from mimik_contracts import (
    Brand,
    CreativeDoc,
    JobStatus,
    Layer,
    LayerKind,
    LayerRecipe,
    PRESETS,
)


CREATIVE_ARTIFACT_ROOT = Path("var/creatives")
_MAX_STOCK_BYTES = 20 * 1024 * 1024
_MAX_STOCK_REDIRECTS = 3
_PEXELS_IMAGE_HOST = "images.pexels.com"
_TEAM_ROLES = frozenset({"owner", "admin", "ops", "designer", "team"})
_PROFILE_IDS = frozenset({"glo2go-aesthetics", "simply-nikah", "island-cart"})
_GLO2GO_ARCHETYPE = "single_photo_education_hero"


class GenerateCreativeRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    pillar: str | None = Field(default=None, max_length=120)
    format_key: str = "ig_post"


class GeneratedCreative(BaseModel):
    creative: CreativeDoc
    preview_url: str
    svg_url: str
    psd_url: str


def generated_creative_response(creative: CreativeDoc) -> GeneratedCreative:
    return GeneratedCreative(
        creative=creative,
        preview_url=f"/creatives/{creative.id}/preview",
        svg_url=f"/exports/svg?creative_id={creative.id}",
        psd_url=f"/creatives/{creative.id}/export.psd",
    )


def infer_style_profile_id(*, brand_slug: str, industry: str | None) -> str:
    """Map known brands first, then conservative industry signals; unknowns stay generic."""
    slug = brand_slug.casefold().replace("_", "-")
    industry_text = (industry or "").casefold()
    if any(token in slug for token in ("glo2go", "glo-2-go", "g2g")):
        return "glo2go-aesthetics"
    if "simply-nikah" in slug or "simplynikah" in slug:
        return "simply-nikah"
    if "island-cart" in slug or "islandcart" in slug:
        return "island-cart"
    if any(token in industry_text for token in ("aesthetic", "skin clinic", "skincare")):
        return "glo2go-aesthetics"
    if any(token in industry_text for token in ("matrimonial", "marriage", "nikah")):
        return "simply-nikah"
    if any(token in industry_text for token in ("ecommerce", "e-commerce", "marketplace")):
        return "island-cart"
    return "generic"


def _profile(profile_id: str) -> StyleProfile | None:
    return get_style_profile(profile_id) if profile_id in _PROFILE_IDS else None


def _profile_color(profile: StyleProfile | None, role: str) -> str | None:
    if profile is None:
        return None
    for color in profile.palette:
        if color.role == role and color.hex is not None:
            return color.hex
    return None


def brand_color(brand: Brand, role: str, fallback: str) -> str:
    for color in brand.tokens.colors:
        if color.name.casefold() == role.casefold():
            return color.hex
    return fallback


def _assert_pexels_image_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != _PEXELS_IMAGE_HOST:
        raise ValueError("Pexels image URL must use https://images.pexels.com")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse urllib's pre-validation redirect follow; the caller validates every hop."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _download_pexels_photo(url: str, destination_dir: Path) -> Path:
    """Download one bounded Pexels image after validating both initial and redirect hosts."""
    opener = urllib.request.build_opener(_NoRedirect)
    current_url = url
    for _ in range(_MAX_STOCK_REDIRECTS + 1):
        _assert_pexels_image_url(current_url)
        request = urllib.request.Request(
            current_url,
            headers={"Accept": "image/*", "User-Agent": "Mimik-Suite/0.1"},
            method="GET",
        )
        try:
            with opener.open(request, timeout=30) as response:  # noqa: S310
                content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0]
                suffix = {
                    "image/jpeg": ".jpg",
                    "image/png": ".png",
                    "image/webp": ".webp",
                }.get(content_type)
                if suffix is None:
                    raise ValueError("Pexels response was not a supported image")
                declared_length = response.headers.get("Content-Length")
                if declared_length is not None and int(declared_length) > _MAX_STOCK_BYTES:
                    raise ValueError("Pexels image exceeds the 20 MiB limit")
                payload = response.read(_MAX_STOCK_BYTES + 1)
            if not payload or len(payload) > _MAX_STOCK_BYTES:
                raise ValueError("Pexels image is empty or exceeds the 20 MiB limit")
            destination = destination_dir / f"source{suffix}"
            destination.write_bytes(payload)
            return destination
        except urllib.error.HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308):
                raise
            location = exc.headers.get("Location")
            if not location:
                raise ValueError("Pexels redirect has no Location header") from exc
            current_url = urljoin(current_url, location)
    raise ValueError(f"Pexels image exceeded {_MAX_STOCK_REDIRECTS} redirects")


def _solid_placeholder(destination_dir: Path, color: str) -> Path:
    destination = destination_dir / "source.svg"
    destination.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080" '
        f'viewBox="0 0 1080 1080"><rect width="1080" height="1080" fill="{color}"/></svg>',
        encoding="utf-8",
    )
    return destination


async def _source_image(
    *,
    brand: Brand,
    industry: str | None,
    topic: str,
    profile: StyleProfile | None,
    destination_dir: Path,
) -> tuple[Path, list[str], str]:
    first_source = profile.image_sources[0] if profile and profile.image_sources else None
    if first_source == ImageSource.LICENSED_STOCK:
        niche = brand.niche or industry or brand.name
        query = reference_gather.build_query(
            niche=niche,
            medium="photography",
            keywords=[topic],
        )
        candidates = await reference_gather.gather_references(query, limit=1, source="pexels")
        if not candidates:
            raise RuntimeError("Pexels returned no imagery for this topic")
        candidate = candidates[0]
        image_path = await asyncio.to_thread(
            _download_pexels_photo,
            candidate.url,
            destination_dir,
        )
        return image_path, [candidate.url], "licensed_stock"

    # TODO: replace this brand-ground plate with AI illustration/product-cutout adapters
    # once those media are operator-approved for first-class generation.
    ground = brand_color(brand, "ground", "#F5F6F8")
    return _solid_placeholder(destination_dir, ground), [], "brand_placeholder"


async def _safe_text_region(image_path: Path, *, source_kind: str) -> str | None:
    if source_kind != "licensed_stock":
        return None
    try:
        result = await vision_text_region.find_text_region(str(image_path))
        return result.region
    except (OSError, RuntimeError, ValueError):
        return None


async def get_scoped_creative(
    session: AsyncSession,
    *,
    principal: Principal,
    creative_id: str,
) -> tuple[CreativeDocRow, JobRow] | None:
    creative = await repo.get_creative_doc(
        session,
        tenant_id=principal.tenant_id,
        creative_doc_id=creative_id,
    )
    if creative is None:
        return None
    job = await repo.get_job(session, tenant_id=principal.tenant_id, job_id=creative.job_id)
    if job is None or not is_client_in_scope(principal, job.client_id):
        return None
    return creative, job


def creative_artifact_path(creative_id: str, filename: str) -> Path:
    if Path(creative_id).name != creative_id or Path(filename).name != filename:
        raise ValueError("Creative artifact path contains an unsafe segment")
    return CREATIVE_ARTIFACT_ROOT / creative_id / filename


async def generate_client_creative(
    session: AsyncSession,
    *,
    principal: Principal,
    client_id: str,
    body: GenerateCreativeRequest,
) -> GeneratedCreative:
    if principal.role not in _TEAM_ROLES:
        raise HTTPException(status_code=403, detail="Creative generation is a team action")
    if not is_client_in_scope(principal, client_id):
        raise HTTPException(status_code=404, detail="Client not found")
    if body.format_key not in PRESETS:
        raise HTTPException(status_code=422, detail="Unknown creative format")

    client = await repo.get_client(
        session,
        tenant_id=principal.tenant_id,
        client_id=client_id,
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    brand_rows = await repo.list_brands(
        session,
        tenant_id=principal.tenant_id,
        client_id=client_id,
    )
    if not brand_rows:
        raise HTTPException(status_code=404, detail="Client brand not found")

    brand = to_brand(brand_rows[0])
    topic = " ".join(body.topic.split())
    if not topic:
        raise HTTPException(status_code=422, detail="Topic must not be blank")
    pillar = " ".join((body.pillar or "General").split()) or "General"
    profile_id = infer_style_profile_id(brand_slug=brand.slug, industry=client.industry)
    profile = _profile(profile_id)
    creative_id = str(uuid4())
    artifact_dir = creative_artifact_path(creative_id, "preview.png").parent
    artifact_dir.mkdir(parents=True, exist_ok=False)

    try:
        image_path, reference_urls, source_kind = await _source_image(
            brand=brand,
            industry=client.industry,
            topic=topic,
            profile=profile,
            destination_dir=artifact_dir,
        )
        copy_block = await asyncio.to_thread(
            copy_l0.draft_copy,
            brand,
            pillar,
            topic,
            body.format_key,
        )
        art_request = await asyncio.to_thread(
            art_direction.build_image_request,
            brand,
            pillar,
            topic,
            PRESETS[body.format_key].label,
            PRESETS[body.format_key].width,
            PRESETS[body.format_key].height,
            template_key="centered_hero",
            profile_id=profile_id,
        )
        text_region = await _safe_text_region(image_path, source_kind=source_kind)
        ink = brand_color(
            brand,
            "primary",
            _profile_color(profile, "ink") or "#1A1D26",
        )
        ground = brand_color(
            brand,
            "ground",
            _profile_color(profile, "ground") or "#FFFFFF",
        )

        profile_render_path: Path | None = None
        if profile_id == "glo2go-aesthetics":
            profile_png = await glo2go_templates.render_glo2go(
                _GLO2GO_ARCHETYPE,
                image_ref=str(image_path),
                copy={
                    "headline": copy_block.headline,
                    "subhead": copy_block.subhead or "",
                    "cta": copy_block.cta or "",
                },
                format_key=body.format_key,
                text_region=text_region,
            )
            profile_render_path = artifact_dir / "glo2go-render.png"
            profile_render_path.write_bytes(profile_png)

        svg = svg_export.render_creative_svg(
            format_key=body.format_key,
            image_ref=str(image_path),
            headline=copy_block.headline,
            sub=copy_block.subhead,
            cta=copy_block.cta,
            palette_ink=ink,
            palette_ground=ground,
            badge_text=brand.name,
            logo_ref=brand.tokens.logo.ref,
            text_region=text_region,
        )
        preview = await svg_export.rasterize_svg_to_png(svg, body.format_key)
        svg_path = artifact_dir / "creative.svg"
        preview_path = artifact_dir / "preview.png"
        svg_path.write_text(svg, encoding="utf-8")
        preview_path.write_bytes(preview)

        manifest = build_manifest(
            brand,
            copy_block,
            body.format_key,
            template_key=_GLO2GO_ARCHETYPE
            if profile_id == "glo2go-aesthetics"
            else "centered_hero",
            image_artifact=str(image_path),
        )
        image_layer = manifest.layer(LayerKind.L1_BASE)
        assert image_layer is not None
        image_layer.recipe = LayerRecipe(
            prompt=art_request.prompt,
            reference_urls=reference_urls,
            params={
                **art_request.params,
                "topic": topic,
                "pillar": pillar,
                "style_profile_id": profile_id,
                "image_source": source_kind,
                "text_region": text_region,
            },
        )
        manifest.layers.append(
            Layer(
                kind=LayerKind.L5_FINISH,
                recipe=LayerRecipe(
                    params={
                        "svg_ref": str(svg_path),
                        "preview_ref": str(preview_path),
                        **(
                            {"profile_render_ref": str(profile_render_path)}
                            if profile_render_path is not None
                            else {}
                        ),
                    }
                ),
                artifact_ref=str(preview_path),
            )
        )

        job = await repo.create_job(
            session,
            tenant_id=principal.tenant_id,
            client_id=client_id,
            brand_id=brand.id,
            title=topic,
            format_key=body.format_key,
            status=JobStatus.GENERATING.value,
            generation_started_at=datetime.now(timezone.utc),
        )
        creative_row = await repo.create_creative_doc(
            session,
            tenant_id=principal.tenant_id,
            id=creative_id,
            job_id=job.id,
            manifest=manifest.model_dump(mode="json"),
        )
        job.status = JobStatus.INTERNAL_REVIEW.value
        job.generation_started_at = None
        await session.commit()
    except HTTPException:
        shutil.rmtree(artifact_dir, ignore_errors=True)
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        await session.rollback()
        shutil.rmtree(artifact_dir, ignore_errors=True)
        raise HTTPException(status_code=502, detail="Creative generation failed") from exc
    except Exception:
        await session.rollback()
        shutil.rmtree(artifact_dir, ignore_errors=True)
        raise

    return generated_creative_response(to_creative_doc(creative_row))
