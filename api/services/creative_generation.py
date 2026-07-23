"""First-class Studio creative generation and persisted artifact orchestration."""

from __future__ import annotations

import asyncio
import logging
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, is_client_in_scope
from api.core.capabilities import Capability, has_capability
from api.core.config import get_settings
from api.db import repo
from api.db.mappers import to_brand, to_creative_doc
from api.db.models import CreativeDocRow, JobRow
from api.services.edit_signals import feedback_from_edit, record_signal
from creative import art_direction
from creative.adapters import (
    ImageGenerationFailed,
    ImageRequest,
    PaidImageSpendNotApproved,
    generate_with_fallback,
)
from creative.copy import l0 as copy_l0
from creative.export import svg as svg_export
from creative.pipeline import build_manifest
from creative.qa.checks import QAReport
from creative.qa.live import LIVE_QA_BLOCKING, LiveQABlocked, run_live_qa
from creative.references import gather as reference_gather
from creative.render import glo2go_templates, nikah_templates
from creative.style_profile import ImageSource, StyleProfile, get_style_profile
from creative.vision import text_region as vision_text_region
from creative.revision.interpreter import interpret_ask
from mimik_contracts import (
    Actor,
    ActorRole,
    Brand,
    CanvasRevision,
    CopyBlock,
    CreativeDoc,
    CreativeManifest,
    JobStatus,
    Layer,
    LayerKind,
    LayerRecipe,
    PRESETS,
    PreferenceSource,
)


logger = logging.getLogger(__name__)

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
    pillar: str,
    topic: str,
    format_key: str,
    profile: StyleProfile | None,
    destination_dir: Path,
    image_request: ImageRequest | None = None,
) -> tuple[Path, list[str], str]:
    sources = profile.image_sources if profile is not None else []
    for source in sources:
        if source == ImageSource.LICENSED_STOCK:
            niche = brand.niche or industry or brand.name
            query = reference_gather.build_query(
                niche=niche,
                medium="photography",
                keywords=[topic],
            )
            candidates = await reference_gather.gather_references(
                query,
                limit=1,
                source="pexels",
            )
            if not candidates:
                logger.warning(
                    "image source licensed_stock returned no candidates for profile=%s",
                    profile.id,
                )
                continue
            candidate = candidates[0]
            image_path = await asyncio.to_thread(
                _download_pexels_photo,
                candidate.url,
                destination_dir,
            )
            return image_path, [candidate.url], "licensed_stock"

        if source in {ImageSource.AI_ILLUSTRATION, ImageSource.AI_REALISTIC}:
            try:
                request = image_request
                if request is None:
                    request = await asyncio.to_thread(
                        art_direction.build_image_request,
                        brand,
                        pillar,
                        topic,
                        PRESETS[format_key].label,
                        PRESETS[format_key].width,
                        PRESETS[format_key].height,
                        template_key="centered_hero",
                        profile_id=profile.id,
                    )
                result = await generate_with_fallback(request, purpose="hero")
                if result is None:
                    logger.warning(
                        "image source %s unavailable for profile=%s: no backend configured",
                        source.value,
                        profile.id,
                    )
                    continue
                destination = destination_dir / "source.png"
                await asyncio.to_thread(shutil.copyfile, result.artifact_ref, destination)
            except (
                PaidImageSpendNotApproved,
                ImageGenerationFailed,
                OSError,
                RuntimeError,
            ) as exc:
                logger.warning(
                    "image source %s unavailable for profile=%s: %s",
                    source.value,
                    profile.id,
                    exc,
                )
                continue
            return destination, [], source.value

        if source in {ImageSource.GENERATED_VECTOR, ImageSource.PRODUCT_CUTOUT}:
            # TODO(engine): generated-vector library / product-cutout upload pipeline
            continue

    ground = brand_color(brand, "ground", "#F5F6F8")
    return _solid_placeholder(destination_dir, ground), [], "brand_placeholder"


async def _safe_text_region(image_path: Path, *, source_kind: str) -> str | None:
    if source_kind not in {"licensed_stock", "ai_realistic"}:
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



_NIKAH_PROTECTION_KEYWORDS = (
    "protect",
    "safe",
    "trust",
    "secur",
    "privacy",
    "guardian",
    "modest",
    "haya",
)


def _suggest_nikah(copy_block: CopyBlock) -> tuple[str, str | None, str]:
    """Pick a Simply Nikah archetype (+ highlight word + hero symbol) from the copy.

    v1 selection: trust/protection themes → protection_symbol_hero (no highlight needed);
    otherwise the signature highlighted_word_hero, reversing out the headline's trailing
    phrase (kept verbatim so it stays a substring the template can locate)."""
    headline = (copy_block.headline or "").strip()
    lower = headline.lower()
    if any(keyword in lower for keyword in _NIKAH_PROTECTION_KEYWORDS):
        return "protection_symbol_hero", None, "shield_crescent"
    words = headline.split()
    if len(words) >= 2:
        return "highlighted_word_hero", " ".join(words[-2:]), "hands_heart"
    return "protection_symbol_hero", None, "shield_crescent"


async def _render_nikah_artifacts(
    *, copy_block: CopyBlock, format_key: str, brand: Brand
) -> tuple[str, bytes]:
    """Render a Simply Nikah creative through the vector engine (M-01). Returns (svg, png)
    so live QA can read the semantic-layer geometry. SN never takes a photo."""
    archetype, highlight, hero_symbol = _suggest_nikah(copy_block)
    copy: dict[str, str] = {"headline": copy_block.headline}
    if copy_block.subhead:
        copy["sub"] = copy_block.subhead
    if copy_block.cta:
        copy["cta"] = copy_block.cta
    if highlight is not None:
        copy["highlight"] = highlight
    svg = nikah_templates.build_nikah_svg(
        archetype,
        copy=copy,
        format_key=format_key,
        hero_symbol=hero_symbol,
        logo_ref=brand.tokens.logo.ref,
    )
    preview = await svg_export.rasterize_svg_to_png(svg, format_key)
    return svg, preview


async def _render_creative_artifacts(
    *,
    brand: Brand,
    profile_id: str,
    copy_block: CopyBlock,
    format_key: str,
    image_path: Path,
    artifact_dir: Path,
    render_params: dict,
    source_kind: str,
) -> tuple[Path, Path, Path | None, QAReport]:
    profile = _profile(profile_id)
    text_region = render_params.get("text_region")
    ink = brand_color(brand, "primary", _profile_color(profile, "ink") or "#1A1D26")
    ground = brand_color(brand, "ground", _profile_color(profile, "ground") or "#FFFFFF")

    profile_render_path: Path | None = None
    # Simply Nikah renders through the vector engine (M-01) — faceless flat-vector, no photo.
    # Vector composition IS the master here, so this REPLACES the photo-based render_creative_svg.
    # Defensive: any nikah render failure falls back to the generic path so live generation never
    # breaks. On success QA sees the true source kind (generated_vector), not the placeholder tag.
    nikah_render: tuple[str, bytes] | None = None
    effective_source_kind = source_kind
    if profile_id == "simply-nikah":
        try:
            nikah_render = await _render_nikah_artifacts(
                copy_block=copy_block, format_key=format_key, brand=brand
            )
            effective_source_kind = "generated_vector"
        except Exception as exc:  # noqa: BLE001 — never let a render fault break generation
            logger.warning(
                "nikah render failed for format=%s (%s); using generic fallback",
                format_key,
                exc,
            )

    if profile_id == "glo2go-aesthetics":
        profile_png = await glo2go_templates.render_glo2go(
            _GLO2GO_ARCHETYPE,
            image_ref=str(image_path),
            copy={
                "headline": copy_block.headline,
                "subhead": copy_block.subhead or "",
                "cta": copy_block.cta or "",
            },
            format_key=format_key,
            text_region=text_region,
            panel_anchor=render_params.get("panel_anchor"),
            text_alignment=render_params.get("text_alignment", "left"),
            subject_zoom=render_params.get("subject_zoom", 1.0),
            badge_background_luminance=render_params.get("badge_background_luminance"),
        )
        profile_render_path = artifact_dir / "glo2go-render.png"
        profile_render_path.write_bytes(profile_png)

    if nikah_render is not None:
        svg, preview = nikah_render
    else:
        svg = svg_export.render_creative_svg(
            format_key=format_key,
            image_ref=str(image_path),
            headline=copy_block.headline,
            sub=copy_block.subhead,
            cta=copy_block.cta,
            palette_ink=ink,
            palette_ground=ground,
            badge_text=brand.name,
            logo_ref=brand.tokens.logo.ref,
            text_region=text_region,
            panel_anchor=render_params.get("panel_anchor"),
            text_alignment=render_params.get("text_alignment", "left"),
            subject_zoom=render_params.get("subject_zoom", 1.0),
            badge_background_luminance=render_params.get("badge_background_luminance"),
        )
        preview = await svg_export.rasterize_svg_to_png(svg, format_key)
    svg_path = artifact_dir / "creative.svg"
    preview_path = artifact_dir / "preview.png"
    svg_path.write_text(svg, encoding="utf-8")
    preview_path.write_bytes(preview)

    # Brand-QA gate on the ACTUAL rendered output (M-08 / Lane A): the live path bypasses
    # creative.pipeline, so this is where the greenish-doctor / purple-on-purple checks run.
    # Recorded gate by default (assisted autonomy): failures are logged + persisted, not raised
    # — flip live_qa.LIVE_QA_BLOCKING to escalate to a hard gate.
    qa_report = await run_live_qa(
        preview,
        svg,
        brand=brand,
        profile=profile,
        format_key=format_key,
        source_kind=effective_source_kind,
        expect_logo=brand.tokens.logo.ref is not None,
    )
    if not qa_report.passed:
        logger.warning(
            "live brand-QA failed for profile=%s format=%s source=%s: %s",
            profile_id,
            format_key,
            effective_source_kind,
            "; ".join(qa_report.failures),
        )
        if LIVE_QA_BLOCKING:
            raise LiveQABlocked(qa_report)
    return svg_path, preview_path, profile_render_path, qa_report


# Legacy ReviseCreativeRequest was removed; the router maps it to CanvasRevision


def _actor_dict(principal: Principal) -> dict[str, str]:
    return {
        "id": principal.user_id or principal.tenant_id,
        "role": principal.role,
    }


def _actor(principal: Principal) -> Actor:
    return Actor(
        id=principal.user_id or principal.tenant_id,
        role=ActorRole(principal.role),
    )


async def _record_signal_best_effort(
    session: AsyncSession,
    *,
    tenant_id: str,
    job: JobRow,
    doc: CreativeDocRow,
    source: PreferenceSource,
    actor: Actor,
    detail: str | None = None,
    extra_attributes: dict[str, str] | None = None,
) -> None:
    """Capture a signal in the creative transaction without risking the new version."""
    try:
        async with session.begin_nested():
            await record_signal(
                session,
                tenant_id=tenant_id,
                job=job,
                doc=doc,
                source=source,
                actor=actor,
                detail=detail,
                extra_attributes=extra_attributes,
            )
    except Exception as exc:
        logger.warning(
            "%s signal capture failed for creative %s: %s",
            source.value,
            doc.id,
            exc,
        )


def _revision_note(revision: CanvasRevision) -> str | None:
    if revision.ask and revision.ask.instruction:
        return revision.ask.instruction
    if revision.text_edits:
        return "; ".join(f"{field}: {value}" for field, value in revision.text_edits.model_dump(exclude_none=True).items())
    if revision.layer_ops:
        return f"Layer ops: {len(revision.layer_ops)}"
    return None


def _qa_params(qa_report: QAReport | None) -> dict[str, object]:
    """The QA verdict folded into L5 params so every version records its brand-QA result
    (non-destructive audit — there is no dedicated manifest QA field yet)."""
    if qa_report is None:
        return {}
    return {
        "qa_passed": qa_report.passed,
        "qa_failures": list(qa_report.failures),
        "qa_needs_scrim": qa_report.needs_scrim,
    }


def _set_rendered_artifacts(
    manifest: CreativeManifest,
    *,
    svg_path: Path,
    preview_path: Path,
    profile_render_path: Path | None,
    qa_report: QAReport | None = None,
) -> None:
    artifact_params = {
        "svg_ref": str(svg_path),
        "preview_ref": str(preview_path),
        **(
            {"profile_render_ref": str(profile_render_path)}
            if profile_render_path is not None
            else {}
        ),
        **_qa_params(qa_report),
    }
    l5_layer = manifest.layer(LayerKind.L5_FINISH)
    if l5_layer is None:
        manifest.layers.append(
            Layer(
                kind=LayerKind.L5_FINISH,
                recipe=LayerRecipe(params=artifact_params),
                artifact_ref=str(preview_path),
            )
        )
        return

    retained_params = {
        key: value
        for key, value in l5_layer.recipe.params.items()
        if key
        not in {
            "svg_ref",
            "preview_ref",
            "profile_render_ref",
            "qa_passed",
            "qa_failures",
            "qa_needs_scrim",
        }
    }
    l5_layer.recipe = LayerRecipe(params={**retained_params, **artifact_params})
    l5_layer.artifact_ref = str(preview_path)


async def revise_creative(
    session: AsyncSession,
    *,
    principal: Principal,
    creative_id: str,
    revision: CanvasRevision,
) -> GeneratedCreative:
    scoped = await get_scoped_creative(session, principal=principal, creative_id=creative_id)
    if scoped is None:
        raise HTTPException(status_code=404, detail="Creative not found")
    creative_row, job = scoped

    if principal.role == ActorRole.CLIENT.value:
        # A client principal must be bound to exactly one client. Fail closed if legacy account
        # data reaches this path without that binding; empty internal scopes otherwise mean "all".
        if principal.client_id is None:
            raise HTTPException(status_code=404, detail="Creative not found")
        # Bounded self-serve (locked positioning + #3): a client may only text-edit / ask — never
        # manipulate layers or pass raw render params.
        if not has_capability(principal.role, Capability.CLIENT_PORTAL):
            raise HTTPException(status_code=403, detail="Client portal not permitted")
        if revision.layer_ops or revision.params:
            raise HTTPException(
                status_code=422,
                detail="Clients may only edit text or ask for changes, not manipulate layers",
            )
        # Rolling 24h quota on client-authored versions for this job.
        settings = get_settings()
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        used = await repo.count_client_versions(
            session,
            tenant_id=principal.tenant_id,
            job_id=job.id,
            since=since,
        )
        if used >= settings.client_revision_daily_quota:
            raise HTTPException(
                status_code=429,
                detail="Daily revision limit reached",
                headers={"X-Revision-Quota-Remaining": "0"},
            )

    brand_row = await repo.get_brand(
        session, tenant_id=principal.tenant_id, brand_id=job.brand_id
    )
    brand = to_brand(brand_row)

    manifest = CreativeManifest.model_validate(creative_row.manifest)
    copy_block = manifest.copy_block
    if copy_block is None:
        raise HTTPException(status_code=422, detail="No copy block in manifest")

    image_layer = manifest.layer(LayerKind.L1_BASE)
    if not image_layer or not image_layer.recipe or not image_layer.artifact_ref:
        raise HTTPException(status_code=422, detail="Creative missing L1_BASE image layer")

    params = revision.params or {}
    l1_params = image_layer.recipe.params

    wants_new_image = False
    if revision.ask and revision.ask.instruction:
        interpreted = interpret_ask(
            revision.ask,
            profile_id=str(l1_params.get("style_profile_id", "generic")),
            current_params=l1_params,
        )
        params.update(interpreted.params)
        wants_new_image = interpreted.wants_new_image

        try:
            copy_block = await asyncio.to_thread(
                copy_l0.draft_copy,
                brand,
                str(l1_params.get("pillar", "General")),
                str(l1_params.get("topic", "General")),
                manifest.format_key,
                revision_note=revision.ask.instruction,
            )
        except (copy_l0.CopyDraftError, OSError) as exc:
            logger.warning(
                "revise: copy redraft failed (%s); applying layout-only change", exc
            )
            
        for field_name, new_text in interpreted.text_edits.items():
            if field_name == "headline":
                copy_block.headline = new_text
            elif field_name == "subhead":
                copy_block.subhead = new_text
            elif field_name == "cta":
                copy_block.cta = new_text
        if interpreted.text_edits:
            copy_block.status = "edited"

    if revision.text_edits:
        edits_dump = revision.text_edits.model_dump(exclude_none=True)
        if "headline" in edits_dump:
            copy_block.headline = edits_dump["headline"]
        if "subhead" in edits_dump:
            copy_block.subhead = edits_dump["subhead"]
        if "cta" in edits_dump:
            copy_block.cta = edits_dump["cta"]
        if edits_dump:
            copy_block.status = "edited"

    l1_params.update(params)
    if revision.ask and revision.ask.instruction:
        l1_params["last_ask"] = revision.ask.instruction[:200]
    else:
        l1_params.pop("last_ask", None)

    # Resolve layer operations
    layer_overrides = l1_params.get("layer_overrides", {})
    if not isinstance(layer_overrides, dict):
        layer_overrides = {}
    layer_overrides = dict(layer_overrides)  # Clone so we don't mutate in place unexpectedly

    for op in revision.layer_ops:
        override: dict[str, object] = {
            "dx": op.dx,
            "dy": op.dy,
            "scale": op.scale,
            "scale_x": op.scale_x,
            "scale_y": op.scale_y,
            "rotation": op.rotation,
            "visible": op.visible,
        }
        if op.fill_role is not None:
            # Recolor is bounded to the brand palette: resolve the role NAME to a hex from the
            # brand tokens; an unknown role is rejected (never a free-form colour).
            hex_color = next(
                (
                    c.hex
                    for c in brand.tokens.colors
                    if c.name.casefold() == op.fill_role.casefold()
                ),
                None,
            )
            if hex_color is None:
                raise HTTPException(
                    status_code=422, detail=f"Unknown brand color role: {op.fill_role}"
                )
            override["fill"] = hex_color
        # An op carries the full desired state of its layer, so it replaces that layer's stored
        # override; layers absent from this revision keep theirs (inheritance across versions).
        layer_overrides[op.layer_id] = override

    if layer_overrides:
        l1_params["layer_overrides"] = layer_overrides

    new_creative_id = str(uuid4())
    artifact_dir = creative_artifact_path(new_creative_id, "preview.png").parent
    artifact_dir.mkdir(parents=True, exist_ok=False)

    try:
        image_path_for_render = Path(image_layer.artifact_ref)
        if wants_new_image:
            try:
                client_row = await repo.get_client(session, tenant_id=principal.tenant_id, client_id=job.client_id)
                industry = client_row.industry if client_row else None
                profile = _profile(str(l1_params.get("style_profile_id", "generic")))
                
                new_image_path, new_ref_urls, new_source_kind = await _source_image(
                    brand=brand,
                    industry=industry,
                    pillar=str(l1_params.get("pillar", "General")),
                    topic=str(l1_params.get("topic", "General")),
                    format_key=manifest.format_key,
                    profile=profile,
                    destination_dir=artifact_dir,
                )
                image_path_for_render = new_image_path
                l1_params["image_source"] = new_source_kind
                image_layer.artifact_ref = str(new_image_path)
                image_layer.recipe.reference_urls = new_ref_urls
            except Exception as exc:
                logger.warning("revise: failed to source new image (%s); keeping existing image", exc)

        svg_path, preview_path, profile_render_path, qa_report = await _render_creative_artifacts(
            brand=brand,
            profile_id=str(l1_params.get("style_profile_id", "generic")),
            copy_block=copy_block,
            format_key=manifest.format_key,
            image_path=image_path_for_render,
            artifact_dir=artifact_dir,
            render_params=l1_params,
            source_kind=str(l1_params.get("image_source") or "brand_placeholder"),
        )

        manifest.copy_block = copy_block
        _set_rendered_artifacts(
            manifest,
            svg_path=svg_path,
            preview_path=preview_path,
            profile_render_path=profile_render_path,
            qa_report=qa_report,
        )

        new_row = await repo.create_creative_doc(
            session,
            tenant_id=principal.tenant_id,
            id=new_creative_id,
            job_id=job.id,
            manifest=manifest.model_dump(mode="json"),
            parent_id=creative_id,
            created_by=_actor_dict(principal),
            revision_note=_revision_note(revision),
        )
        edit_attributes = {
            "profile_id": str(l1_params.get("style_profile_id") or "generic"),
            "edited_by_client": (
                "true" if principal.role == ActorRole.CLIENT.value else "false"
            ),
        }
        if revision.ask is not None:
            edit_attributes["revision_zone"] = revision.ask.zone.value
        await _record_signal_best_effort(
            session,
            tenant_id=principal.tenant_id,
            job=job,
            doc=new_row,
            source=PreferenceSource.EDIT,
            actor=_actor(principal),
            detail=_revision_note(revision),
            extra_attributes=edit_attributes,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        shutil.rmtree(artifact_dir, ignore_errors=True)
        raise

    return generated_creative_response(to_creative_doc(new_row))


async def revert_creative(
    session: AsyncSession,
    *,
    principal: Principal,
    creative_id: str,
    to_creative_id: str,
) -> GeneratedCreative:
    current_scoped = await get_scoped_creative(
        session,
        principal=principal,
        creative_id=creative_id,
    )
    # The URL-path resource follows the IDOR convention (locked #2): out-of-scope/missing → 404
    # (never leak existence), matching /versions, /revise, /preview.
    if current_scoped is None:
        raise HTTPException(status_code=404, detail="Creative not found")
    # `to_creative_id` is a request-body param → 422 when it can't be resolved in scope.
    target_scoped = await get_scoped_creative(
        session,
        principal=principal,
        creative_id=to_creative_id,
    )
    if target_scoped is None:
        raise HTTPException(
            status_code=422,
            detail="to_creative_id must exist within the caller's tenant and scope",
        )

    current_row, current_job = current_scoped
    target_row, target_job = target_scoped
    if current_job.id != target_job.id:
        raise HTTPException(
            status_code=422,
            detail="Creative versions must belong to the same job",
        )

    current_manifest = CreativeManifest.model_validate(current_row.manifest)
    current_image_layer = current_manifest.layer(LayerKind.L1_BASE)
    current_params = (
        current_image_layer.recipe.params
        if current_image_layer is not None
        else {}
    )
    current_last_ask = current_params.get("last_ask")
    current_profile_value = current_params.get("style_profile_id")

    brand_row = await repo.get_brand(
        session,
        tenant_id=principal.tenant_id,
        brand_id=current_job.brand_id,
    )
    if brand_row is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    brand = to_brand(brand_row)

    manifest = CreativeManifest.model_validate(target_row.manifest)
    copy_block = manifest.copy_block
    if copy_block is None:
        raise HTTPException(status_code=422, detail="No copy block in target manifest")
    image_layer = manifest.layer(LayerKind.L1_BASE)
    if not image_layer or not image_layer.recipe or not image_layer.artifact_ref:
        raise HTTPException(status_code=422, detail="Target creative missing L1_BASE image layer")

    render_params = image_layer.recipe.params
    new_creative_id = str(uuid4())
    artifact_dir = creative_artifact_path(new_creative_id, "preview.png").parent
    artifact_dir.mkdir(parents=True, exist_ok=False)

    try:
        svg_path, preview_path, profile_render_path, qa_report = await _render_creative_artifacts(
            brand=brand,
            profile_id=str(render_params.get("style_profile_id", "generic")),
            copy_block=copy_block,
            format_key=manifest.format_key,
            image_path=Path(image_layer.artifact_ref),
            artifact_dir=artifact_dir,
            render_params=render_params,
            source_kind=str(render_params.get("image_source") or "brand_placeholder"),
        )
        _set_rendered_artifacts(
            manifest,
            svg_path=svg_path,
            preview_path=preview_path,
            profile_render_path=profile_render_path,
            qa_report=qa_report,
        )
        new_row = await repo.create_creative_doc(
            session,
            tenant_id=principal.tenant_id,
            id=new_creative_id,
            job_id=current_job.id,
            manifest=manifest.model_dump(mode="json"),
            parent_id=current_row.id,
            created_by=_actor_dict(principal),
            revision_note=f"revert to v{target_row.version}",
        )
        await _record_signal_best_effort(
            session,
            tenant_id=principal.tenant_id,
            job=current_job,
            doc=new_row,
            source=PreferenceSource.REJECTION,
            actor=_actor(principal),
            detail=f"revert to v{target_row.version}",
            extra_attributes={
                "reverted_from_version": str(current_row.version),
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()
        shutil.rmtree(artifact_dir, ignore_errors=True)
        raise

    if isinstance(current_last_ask, str) and current_last_ask.strip():
        feedback_from_edit(
            verdict="decline",
            reason=current_last_ask,
            profile_id=(
                str(current_profile_value)
                if current_profile_value
                else None
            ),
        )
    return generated_creative_response(to_creative_doc(new_row))


async def generate_client_creative(
    session: AsyncSession,
    *,
    principal: Principal,
    client_id: str,
    body: GenerateCreativeRequest,
    job_id: str | None = None,
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

    job: JobRow | None = None
    brand_row = brand_rows[0]
    if job_id is not None:
        job = await repo.get_job(
            session,
            tenant_id=principal.tenant_id,
            job_id=job_id,
        )
        if (
            job is None
            or job.client_id != client_id
            or not is_client_in_scope(principal, job.client_id)
        ):
            raise HTTPException(status_code=404, detail="Job not found")
        matching_brand = next((row for row in brand_rows if row.id == job.brand_id), None)
        if matching_brand is None:
            raise HTTPException(status_code=404, detail="Job brand not found")
        brand_row = matching_brand

    brand = to_brand(brand_row)
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
        if job is not None:
            job.status = JobStatus.GENERATING.value
            job.generation_started_at = datetime.now(timezone.utc)
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
        image_path, reference_urls, source_kind = await _source_image(
            brand=brand,
            industry=client.industry,
            pillar=pillar,
            topic=topic,
            format_key=body.format_key,
            profile=profile,
            destination_dir=artifact_dir,
            image_request=art_request,
        )
        try:
            copy_block = await asyncio.to_thread(
                copy_l0.draft_copy,
                brand,
                pillar,
                topic,
                body.format_key,
            )
        except (copy_l0.CopyDraftError, OSError) as exc:
            # The copy LLM (free Gemini tier) can 429/fail; don't fail the whole generation.
            # Fall back to a deterministic draft from the topic so the creative still ships
            # with real imagery + editable copy (a human refines it — assisted autonomy).
            logger.warning("generate: copy draft failed (%s); using topic fallback", exc)
            copy_block = CopyBlock(headline=topic, source_model="fallback")
        text_region = await _safe_text_region(image_path, source_kind=source_kind)
        l1_params = {
            **art_request.params,
            "topic": topic,
            "pillar": pillar,
            "style_profile_id": profile_id,
            "image_source": source_kind,
            "text_region": text_region,
        }

        svg_path, preview_path, profile_render_path, qa_report = await _render_creative_artifacts(
            brand=brand,
            profile_id=profile_id,
            copy_block=copy_block,
            format_key=body.format_key,
            image_path=image_path,
            artifact_dir=artifact_dir,
            render_params=l1_params,
            source_kind=source_kind,
        )

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
            params=l1_params,
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
                        **_qa_params(qa_report),
                    }
                ),
                artifact_ref=str(preview_path),
            )
        )

        if job is None:
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
        if job_id is not None:
            await session.rollback()
        shutil.rmtree(artifact_dir, ignore_errors=True)
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        logger.exception("generate_client_creative failed")
        await session.rollback()
        shutil.rmtree(artifact_dir, ignore_errors=True)
        raise HTTPException(status_code=502, detail="Creative generation failed") from exc
    except Exception:
        await session.rollback()
        shutil.rmtree(artifact_dir, ignore_errors=True)
        raise

    return generated_creative_response(to_creative_doc(creative_row))
