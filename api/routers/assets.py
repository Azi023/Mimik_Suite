"""Brand Asset Library — tenant-scoped, team-only.

Upload/registration, listing, approval, and reference-creative ingestion. Clients never
touch this surface: assets are brand memory the TEAM curates (locked constraint #3 — the
client portal stays a bounded review surface). Approval is the human gate: an approved
LOGO is wired into `Brand.tokens.logo.ref` so the compositor renders the real mark;
ingestion of a reference creative is likewise an explicit team action, never a side effect
of upload.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, require_role
from api.core.config import get_settings
from api.db import repo
from api.db.mappers import to_brand_asset
from api.db.session import get_session
from api.routers.jobs import _TEAM
from api.services import brand_memory
from creative.references.fit_critic import ReferenceCriticError
from creative.vision.study import CreativeStudyError
from mimik_contracts import AssetKind, BrandAsset

router = APIRouter(tags=["assets"])


async def _own_brand(session: AsyncSession, principal: Principal, brand_id: str):
    row = await repo.get_brand(session, tenant_id=principal.tenant_id, brand_id=brand_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return row


@router.post("/brands/{brand_id}/assets", response_model=BrandAsset, status_code=201)
async def upload_asset(
    brand_id: str,
    file: UploadFile = File(...),
    kind: AssetKind = Form(...),
    license: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> BrandAsset:
    brand = await _own_brand(session, principal, brand_id)
    data = await file.read(brand_memory.MAX_ASSET_BYTES + 1)
    try:
        # The trusted mime is SNIFFED from the bytes — the client Content-Type is never trusted.
        row = await brand_memory.create_stored_asset(
            session,
            brand=brand,
            kind=kind.value,
            data=data,
            filename=file.filename or "upload",
            license=license,
            notes=notes,
        )
    except brand_memory.AssetTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except brand_memory.UnsupportedAssetMime as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    await session.commit()
    return to_brand_asset(row)


class RegisterDriveAsset(BaseModel):
    """Register an asset that lives in Drive (bytes pulled later once the SA can read)."""

    kind: AssetKind
    drive_file_id: str
    filename: str
    mime: str
    license: str | None = None
    notes: str | None = None


@router.post("/brands/{brand_id}/assets/register", response_model=BrandAsset, status_code=201)
async def register_drive_asset(
    brand_id: str,
    body: RegisterDriveAsset,
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> BrandAsset:
    brand = await _own_brand(session, principal, brand_id)
    try:
        # Same mime discipline as uploads — a registered row must never carry a mime the
        # render/vision paths would refuse (or worse, one crafted to break a data URI).
        brand_memory.validate_asset_mime(body.kind.value, body.mime)
    except brand_memory.UnsupportedAssetMime as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    row = await repo.create_brand_asset(
        session,
        tenant_id=principal.tenant_id,
        client_id=brand.client_id,
        brand_id=brand_id,
        kind=body.kind.value,
        filename=body.filename,
        mime=body.mime,
        drive_file_id=body.drive_file_id,
        license=body.license,
        notes=body.notes,
    )
    await session.commit()
    return to_brand_asset(row)


@router.get("/brands/{brand_id}/assets", response_model=list[BrandAsset])
async def list_assets(
    brand_id: str,
    kind: AssetKind | None = None,
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> list[BrandAsset]:
    await _own_brand(session, principal, brand_id)
    rows = await repo.list_brand_assets(
        session,
        tenant_id=principal.tenant_id,
        brand_id=brand_id,
        kind=kind.value if kind else None,
    )
    return [to_brand_asset(r) for r in rows]


@router.get("/assets/{asset_id}/raw", response_class=FileResponse)
async def get_asset_raw(
    asset_id: str,
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    asset = await repo.get_brand_asset(
        session,
        tenant_id=principal.tenant_id,
        asset_id=asset_id,
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    brand = await repo.get_brand(
        session,
        tenant_id=principal.tenant_id,
        brand_id=asset.brand_id,
    )
    if brand is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not asset.local_path:
        raise HTTPException(status_code=404, detail="Asset file not found")

    tenant_asset_root = (
        Path(get_settings().assets_local_root) / principal.tenant_id / brand.id
    ).resolve()
    try:
        local_path = Path(asset.local_path).resolve(strict=True)
    except OSError as exc:
        raise HTTPException(status_code=404, detail="Asset file not found") from exc
    if not local_path.is_file() or not local_path.is_relative_to(tenant_asset_root):
        raise HTTPException(status_code=404, detail="Asset file not found")

    return FileResponse(path=local_path, media_type=asset.mime)


@router.post("/assets/{asset_id}/approve", response_model=BrandAsset)
async def approve_asset(
    asset_id: str,
    principal: Principal = Depends(require_role("owner", "ops")),
    session: AsyncSession = Depends(get_session),
) -> BrandAsset:
    asset = await repo.get_brand_asset(
        session, tenant_id=principal.tenant_id, asset_id=asset_id
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.approved = True
    if asset.kind == AssetKind.LOGO.value and asset.local_path:
        brand = await repo.get_brand(
            session, tenant_id=principal.tenant_id, brand_id=asset.brand_id
        )
        if brand is None:
            raise HTTPException(status_code=404, detail="Brand not found")
        try:
            await brand_memory.wire_approved_logo(session, brand=brand, asset=asset)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return to_brand_asset(asset)


@router.post("/assets/{asset_id}/knockout", response_model=BrandAsset, status_code=201)
async def derive_knockout(
    asset_id: str,
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> BrandAsset:
    """Derive the white-knockout variant of a stored logo (new unapproved asset)."""
    asset = await repo.get_brand_asset(
        session, tenant_id=principal.tenant_id, asset_id=asset_id
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.kind != AssetKind.LOGO.value:
        raise HTTPException(status_code=422, detail="Only logo assets have knockout variants")
    if not asset.local_path:
        raise HTTPException(status_code=409, detail="Asset has no local file yet")
    brand = await repo.get_brand(
        session, tenant_id=principal.tenant_id, brand_id=asset.brand_id
    )
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    try:
        variant = await brand_memory.derive_knockout_logo(session, brand=brand, asset=asset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    return to_brand_asset(variant)


class IngestRequest(BaseModel):
    force_attach: bool = False


@router.post("/assets/{asset_id}/ingest", response_model=brand_memory.IngestResult)
async def ingest_asset(
    asset_id: str,
    body: IngestRequest | None = None,
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> brand_memory.IngestResult:
    asset = await repo.get_brand_asset(
        session, tenant_id=principal.tenant_id, asset_id=asset_id
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.kind != AssetKind.REFERENCE_CREATIVE.value:
        raise HTTPException(
            status_code=422, detail="Only reference_creative assets are ingested"
        )
    brand = await repo.get_brand(
        session, tenant_id=principal.tenant_id, brand_id=asset.brand_id
    )
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    try:
        result = await brand_memory.ingest_reference_creative(
            session,
            brand=brand,
            asset=asset,
            actor_role=principal.role,
            force_attach=bool(body.force_attach) if body else False,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (CreativeStudyError, ReferenceCriticError, RuntimeError) as exc:
        # RuntimeError covers a missing GEMINI_API_KEY — a config problem, not a bug.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await session.commit()
    return result
