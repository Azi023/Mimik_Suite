"""Built-in font discovery and tenant-scoped brand materialization."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal
from api.db import repo
from api.db.mappers import to_brand_asset
from api.db.session import get_session
from api.routers.jobs import _TEAM
from api.services import brand_memory
from creative.render.builtin_fonts import FontCategory, get_builtin_font, list_builtin_fonts
from mimik_contracts import AssetKind, BrandAsset

router = APIRouter(tags=["fonts"])


class BuiltinFontResponse(BaseModel):
    key: str
    family: str
    category: FontCategory
    preview_text: str


@router.get("/fonts/library", response_model=list[BuiltinFontResponse])
async def get_font_library(
    _principal: Principal = Depends(_TEAM),
) -> list[BuiltinFontResponse]:
    return [
        BuiltinFontResponse(
            key=font.key,
            family=font.family,
            category=font.category,
            preview_text=font.preview_text,
        )
        for font in list_builtin_fonts()
    ]


@router.post(
    "/brands/{brand_id}/fonts/{font_key}",
    response_model=BrandAsset,
    status_code=201,
)
async def materialize_builtin_font(
    brand_id: str,
    font_key: str,
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> BrandAsset:
    brand = await repo.get_brand(
        session,
        tenant_id=principal.tenant_id,
        brand_id=brand_id,
    )
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    font = get_builtin_font(font_key)
    if font is None:
        raise HTTPException(status_code=404, detail="Built-in font not found")

    try:
        data = font.regular_path.read_bytes()
        row = await brand_memory.create_stored_asset(
            session,
            brand=brand,
            kind=AssetKind.FONT.value,
            data=data,
            filename=font.regular_path.name,
            approved=True,
            license="OFL-1.1",
            notes=f"Materialized from the built-in {font.family} font library.",
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Built-in font file is unavailable") from exc
    except brand_memory.AssetTooLarge as exc:
        raise HTTPException(status_code=500, detail="Built-in font exceeds storage limit") from exc
    except brand_memory.UnsupportedAssetMime as exc:
        raise HTTPException(status_code=500, detail="Built-in font file is invalid") from exc

    await session.commit()
    return to_brand_asset(row)
