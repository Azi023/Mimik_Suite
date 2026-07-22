"""Authenticated editable-master downloads and inline PNG previews."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from api.core.auth import Principal, get_principal
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
