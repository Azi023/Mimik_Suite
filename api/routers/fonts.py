"""Built-in font discovery and tenant-scoped brand materialization."""

from __future__ import annotations

import io
from pathlib import Path
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal
from api.core.config import get_settings
from api.db import repo
from api.db.mappers import to_brand, to_brand_asset
from api.db.session import get_session
from api.routers.jobs import _TEAM
from api.services import brand_memory
from creative.render.builtin_fonts import FontCategory, get_builtin_font, list_builtin_fonts
from mimik_contracts import ActorRole, AssetKind, BrandAsset

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


@router.get("/brands/{brand_id}/font-pack")
async def download_font_pack(
    brand_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Response:
    row = await repo.get_brand(
        session,
        tenant_id=principal.tenant_id,
        brand_id=brand_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    if principal.role == ActorRole.CLIENT.value and row.client_id != principal.client_id:
        raise HTTPException(status_code=404, detail="Brand not found")

    brand = to_brand(row)
    roles = brand.tokens.typography.font_roles
    builtin_keys: list[str] = []
    uploaded_asset_ids: list[str] = []
    if roles:
        builtin_keys = [
            role.builtin_key
            for role in roles
            if role.source == "builtin" and role.builtin_key is not None
        ]
        uploaded_asset_ids = [
            role.asset_id
            for role in roles
            if role.source == "uploaded" and role.asset_id is not None
        ]
    else:
        by_family = {font.family.casefold(): font.key for font in list_builtin_fonts()}
        builtin_keys = [
            key
            for family in (
                brand.tokens.typography.heading_font,
                brand.tokens.typography.body_font,
            )
            if family is not None and (key := by_family.get(family.casefold())) is not None
        ]

    buffer = io.BytesIO()
    license_notes = [f"Font licenses for {brand.name}"]
    added_font_paths: set[str] = set()
    seen_builtin_keys: set[str] = set()
    seen_asset_ids: set[str] = set()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for key in builtin_keys:
            if key in seen_builtin_keys:
                continue
            seen_builtin_keys.add(key)
            font = get_builtin_font(key)
            if font is None:
                continue
            family_files = {font.regular_path, font.bold_path}
            try:
                for font_path in family_files:
                    archive_path = f"fonts/{font.key}/{font_path.name}"
                    archive.write(font_path, archive_path)
                    added_font_paths.add(archive_path)
            except OSError:
                continue

            ofl_path = font.regular_path.parent / "OFL.txt"
            if ofl_path.is_file():
                archive.write(ofl_path, f"fonts/{font.key}/OFL.txt")
                license_notes.append(
                    f"{font.family}: SIL Open Font License 1.1 (see fonts/{font.key}/OFL.txt)."
                )
            else:
                license_notes.append(
                    f"{font.family}: OFL-licensed Google Font; no per-family OFL.txt "
                    "is bundled in this repository."
                )

        tenant_asset_root = (
            Path(get_settings().assets_local_root) / principal.tenant_id / brand.id
        ).resolve()
        uploaded_assets = (
            {
                asset.id: asset
                for asset in await repo.list_brand_assets(
                    session,
                    tenant_id=principal.tenant_id,
                    brand_id=brand.id,
                    kind=AssetKind.FONT.value,
                )
            }
            if uploaded_asset_ids
            else {}
        )
        for asset_id in uploaded_asset_ids:
            if asset_id in seen_asset_ids:
                continue
            seen_asset_ids.add(asset_id)
            asset = uploaded_assets.get(asset_id)
            if asset is None or not asset.local_path:
                continue
            try:
                local_path = Path(asset.local_path).resolve(strict=True)
            except OSError:
                continue
            if not local_path.is_file() or not local_path.is_relative_to(tenant_asset_root):
                continue
            archive_path = f"fonts/uploaded/{Path(asset.filename).name}"
            try:
                archive.write(local_path, archive_path)
            except OSError:
                continue
            added_font_paths.add(archive_path)
            if asset.license:
                license_notes.append(f"{Path(asset.filename).name}: {asset.license}")

        readme_lines = [f"Font pack for {brand.name}."]
        if not added_font_paths:
            readme_lines.append("No fonts are configured yet.")
        archive.writestr("README.txt", "\n\n".join(readme_lines) + "\n")
        archive.writestr("LICENSES.txt", "\n\n".join(license_notes) + "\n")

    # TODO(audit): record this download when a generic delivery-audit helper exists.
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{brand.slug}-fonts.zip"'},
    )


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
