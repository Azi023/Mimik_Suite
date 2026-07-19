"""Brand memory: stored assets -> durable, machine-usable style knowledge.

Three flows live here, all team-driven (the client never triggers ingestion):

1. `store_asset_file` — persist uploaded bytes under the assets root with a server-chosen
   name (never the client filename), returning the storage path for the DB row.
2. `wire_approved_logo` — an APPROVED logo asset becomes `Brand.tokens.logo.ref` as a data
   URI, so the compositor renders the real mark from brand memory (a set_content page has
   no origin to resolve file paths from — the data URI is self-contained).
3. `ingest_reference_creative` — a stored past creative goes through the free-Gemini
   vision study, then the reference fit-critic; a fitting (or human-forced) reference is
   attached to `Brand.references` as the style anchor AND seeded as positive
   `PreferenceSignal`s so the taste-ranker starts from real revealed preference. The
   creative's visible copy comes back in the result so a human can promote it as a
   copy-voice golden — promotion itself stays reviewer-gated, never automatic.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.db import repo
from api.db.mappers import to_brand
from api.db.models import BrandAssetRow, BrandRow
from creative.references.fit_critic import FitVerdict, assess_reference
from creative.vision.study import study_creative
from mimik_contracts import AssetStudy, PreferenceSource

# The only mimes an asset may carry into the render/vision paths.
IMAGE_MIMES: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}
FONT_MIMES: dict[str, str] = {
    "font/ttf": "ttf",
    "font/otf": "otf",
    "font/woff2": "woff2",
}
MAX_ASSET_BYTES = 10 * 1024 * 1024  # 10 MB — generous for a creative, hostile to abuse


class AssetTooLarge(ValueError):
    """Upload exceeds MAX_ASSET_BYTES."""


class UnsupportedAssetMime(ValueError):
    """Upload mime is outside the allowed set for its kind."""


def _extension_for(kind: str, mime: str) -> str:
    allowed = FONT_MIMES if kind == "font" else IMAGE_MIMES
    ext = allowed.get(mime)
    if ext is None:
        raise UnsupportedAssetMime(f"mime {mime!r} is not allowed for asset kind {kind!r}")
    return ext


def validate_asset_mime(kind: str, mime: str) -> None:
    """Allow-list check for asset rows created WITHOUT bytes (e.g. Drive registration).
    Raises UnsupportedAssetMime — the DB must never carry a mime the render/vision paths
    would refuse."""
    _extension_for(kind, mime)


def store_asset_file(
    *, tenant_id: str, brand_id: str, kind: str, mime: str, data: bytes
) -> str:
    """Write uploaded bytes to disk; return the storage path for the DB row.

    The path is built ONLY from server-generated ids + a validated extension — the
    client's filename never touches the filesystem (it is stored as display metadata on
    the row). The result is asset-ref-shaped (no spaces/quotes), so it survives the
    contract validator.
    """
    if len(data) > MAX_ASSET_BYTES:
        raise AssetTooLarge(f"asset exceeds {MAX_ASSET_BYTES} bytes")
    ext = _extension_for(kind, mime)
    root = Path(get_settings().assets_local_root)
    target_dir = root / tenant_id / brand_id
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{uuid4()}.{ext}"
    path.write_bytes(data)
    return str(path)


def read_asset_bytes(asset: BrandAssetRow) -> bytes:
    """Read a stored asset's bytes; fail loud if the file is gone (the row said it exists)."""
    if not asset.local_path:
        raise FileNotFoundError(f"asset {asset.id} has no local file")
    return Path(asset.local_path).read_bytes()


async def wire_approved_logo(
    session: AsyncSession, *, brand: BrandRow, asset: BrandAssetRow
) -> None:
    """Point `Brand.tokens.logo.ref` at the approved logo as a self-contained data URI."""
    data = read_asset_bytes(asset)
    encoded = base64.b64encode(data).decode("ascii")
    data_uri = f"data:{asset.mime};base64,{encoded}"
    tokens = dict(brand.tokens or {})
    logo = dict(tokens.get("logo") or {})
    logo["ref"] = data_uri
    tokens["logo"] = logo
    brand.tokens = tokens  # reassign so SQLAlchemy sees the JSON change
    await session.flush()


async def derive_knockout_logo(
    session: AsyncSession, *, brand: BrandRow, asset: BrandAssetRow
) -> BrandAssetRow:
    """Create the white-knockout variant of a stored logo as a NEW, UNAPPROVED asset.

    Non-destructive and human-gated like every asset: the variant lands in the library
    with provenance notes; a human approves it (which wires it as the active logo) or
    ignores it. The answer to a QA "logo invisible on its ground" failure.
    """
    from creative.render.knockout import derive_knockout_png

    source = read_asset_bytes(asset)
    knocked = await derive_knockout_png(source, asset.mime)
    path = store_asset_file(
        tenant_id=brand.tenant_id,
        brand_id=brand.id,
        kind="logo",
        mime="image/png",
        data=knocked,
    )
    return await repo.create_brand_asset(
        session,
        tenant_id=brand.tenant_id,
        client_id=brand.client_id,
        brand_id=brand.id,
        kind="logo",
        filename=f"knockout-{asset.filename}",
        mime="image/png",
        local_path=path,
        notes=f"auto-derived white knockout of asset {asset.id} — approve to use on "
        "brand-color/dark grounds",
    )


class IngestResult(BaseModel):
    """Everything the reviewing human needs from one reference-creative ingestion."""

    asset_id: str
    study: AssetStudy
    verdict: FitVerdict
    attached: bool
    signals_recorded: int


def _study_to_reference_meta(asset: BrandAssetRow, study: AssetStudy) -> dict[str, str]:
    """The vision study, rendered as the scraped-style metadata the fit-critic consumes."""
    meta = {
        "url": f"asset://{asset.id}",
        "source": "brand_asset",
        "title": asset.filename,
        "mood": study.mood or "",
        "palette_hint": ", ".join(study.palette),
        "composition": study.composition or "",
        "lighting": study.lighting or "",
        "complexity": study.complexity or "",
        "visible_copy": study.copy_text or "",
    }
    return {k: v for k, v in meta.items() if v}


def _signal_attributes(study: AssetStudy) -> dict[str, str]:
    """The salient style attributes a positive signal should carry for the taste-ranker."""
    attrs: dict[str, str] = {}
    if study.mood:
        attrs["mood"] = study.mood
    if study.palette:
        attrs["palette_primary"] = study.palette[0]
    if study.composition:
        attrs["composition"] = study.composition
    if study.complexity:
        attrs["complexity"] = study.complexity
    return attrs


async def ingest_reference_creative(
    session: AsyncSession,
    *,
    brand: BrandRow,
    asset: BrandAssetRow,
    actor_role: str,
    force_attach: bool = False,
    study_fn: Callable[[bytes, str], AssetStudy] | None = None,
    critic_generate: Callable[[str], str] | None = None,
) -> IngestResult:
    """Study one stored reference creative and fold it into brand memory.

    Attach happens when the critic says it fits OR the reviewing human forces it
    (`force_attach` — the human outranks the critic, and the verdict is preserved for the
    audit trail either way). Signals are seeded only for attached references. `study_fn`
    and `critic_generate` are injectable for tests.
    """
    image_bytes = read_asset_bytes(asset)
    if study_fn is None:
        study = study_creative(image_bytes, asset.mime)
    else:
        study = study_fn(image_bytes, asset.mime)

    brand_contract = to_brand(brand)
    verdict = assess_reference(
        brand_contract,
        _study_to_reference_meta(asset, study),
        content_context=f"past {brand.name} creative ingested as a style anchor",
        generate=critic_generate,
    )

    attached = verdict.fits or force_attach
    signals = 0
    if attached:
        reference = {
            "url": f"asset://{asset.id}",
            "source": "brand_asset",
            "fit_score": verdict.fit_score,
            "note": (verdict.reasoning or "")[:300] or None,
        }
        brand.references = [*(brand.references or []), reference]
        attrs = _signal_attributes(study)
        if attrs:
            await repo.create_preference_signal(
                session,
                tenant_id=brand.tenant_id,
                client_id=brand.client_id,
                source=PreferenceSource.PICK.value,
                detail=f"reference creative ingested: {asset.filename}",
                attributes=attrs,
                actor_role=actor_role,
            )
            signals = 1

    asset.study = study.model_dump()
    await session.flush()
    return IngestResult(
        asset_id=asset.id,
        study=study,
        verdict=verdict,
        attached=attached,
        signals_recorded=signals,
    )
