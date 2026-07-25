"""Authenticated editable-master downloads and inline PNG previews."""

from __future__ import annotations

import base64
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from mimik_contracts import PRESETS, CreativeManifest, LayerKind
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal
from api.db.session import get_session
from api.services.creative_generation import creative_artifact_path, get_scoped_creative
from creative.export.svg import rasterize_svg_to_png, render_creative_svg


router = APIRouter(prefix="/exports", tags=["exports"])


class ExportCreative(BaseModel):
    format_key: str
    image_ref: str
    headline: str
    sub: str | None = None
    cta: str | None = None
    palette_ink: str
    palette_ground: str
    badge_text: str | None = None
    text_region: str = "bottom_right"


def _render_svg(body: ExportCreative) -> str:
    return render_creative_svg(
        format_key=body.format_key,
        image_ref=body.image_ref,
        headline=body.headline,
        sub=body.sub,
        cta=body.cta,
        palette_ink=body.palette_ink,
        palette_ground=body.palette_ground,
        badge_text=body.badge_text,
        logo_ref=None,
        text_region=body.text_region,
    )


def _brand_slug(badge_text: str | None) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (badge_text or "brand").lower()).strip("-")
    return slug or "brand"


def _artifact_for_creative(creative_id: str, reference: object) -> Path | None:
    """Resolve only artifacts owned by this creative, never arbitrary manifest paths."""
    if not isinstance(reference, str) or not reference:
        return None
    root = creative_artifact_path(creative_id, "_").parent.resolve()
    candidate = Path(reference).resolve()
    if candidate.parent == root and candidate.is_file():
        return candidate
    return None


def _stored_artifact(
    creative_id: str,
    manifest: CreativeManifest,
    *,
    filename: str,
    manifest_key: str,
) -> Path | None:
    canonical = creative_artifact_path(creative_id, filename)
    if canonical.is_file():
        return canonical
    finish = manifest.layer(LayerKind.L5_FINISH)
    if finish is None:
        return None
    return _artifact_for_creative(
        creative_id,
        finish.recipe.params.get(manifest_key),
    )


def _preview_backed_svg(preview: Path, manifest: CreativeManifest) -> str:
    """Make legacy PNG-only creatives loadable as a single editable canvas layer."""
    preset = PRESETS.get(manifest.format_key, PRESETS["ig_post"])
    encoded = base64.b64encode(preview.read_bytes()).decode("ascii")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {preset.width} {preset.height}">'
        f'<g data-layer="layer-background" '
        f'data-bbox="0 0 {preset.width} {preset.height}">'
        f'<image href="data:image/png;base64,{encoded}" width="{preset.width}" '
        f'height="{preset.height}" preserveAspectRatio="xMidYMid slice"/>'
        "</g></svg>"
    )


@router.get("/svg")
async def download_stored_svg(
    creative_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    scoped = await get_scoped_creative(
        session,
        principal=principal,
        creative_id=creative_id,
    )
    if scoped is None:
        raise HTTPException(status_code=404, detail="Creative not found")
    creative = scoped[0]
    manifest = CreativeManifest.model_validate(creative.manifest)
    path = _stored_artifact(
        creative.id,
        manifest,
        filename="creative.svg",
        manifest_key="svg_ref",
    )
    if path is not None:
        return FileResponse(
            path,
            media_type="image/svg+xml",
            filename=f"{creative_id}.svg",
        )

    preview = _stored_artifact(
        creative.id,
        manifest,
        filename="preview.png",
        manifest_key="preview_ref",
    )
    if preview is None:
        raise HTTPException(status_code=404, detail="Creative SVG not found")
    return Response(
        content=_preview_backed_svg(preview, manifest),
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="{creative_id}.svg"'},
    )


@router.post("/svg")
async def export_svg(
    body: ExportCreative,
    _principal: Principal = Depends(get_principal),
) -> Response:
    svg = _render_svg(body)
    filename = f"{_brand_slug(body.badge_text)}-{body.format_key}.svg"
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/png-preview")
async def export_png_preview(
    body: ExportCreative,
    _principal: Principal = Depends(get_principal),
) -> Response:
    svg = _render_svg(body)
    png = await rasterize_svg_to_png(svg, body.format_key)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": "inline"},
    )
