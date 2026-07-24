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


def safe_display_filename(name: str | None) -> str:
    """Sanitize a client-supplied filename to safe DISPLAY metadata (it never becomes a path).
    Strips any directory components + control/quote chars and caps length, so it can't inject
    into a Drive title / HTML / CSS context downstream or masquerade as a path."""
    if not name:
        return "upload"
    base = name.replace("\\", "/").split("/")[-1]  # drop any path, both separators
    cleaned = "".join(c for c in base if c.isprintable() and c not in '"\'`<>').strip()
    cleaned = cleaned.lstrip(".")  # no leading dots (hidden / traversal-ish)
    return cleaned[:120] or "upload"


def sniff_mime(data: bytes) -> str | None:
    """Identify a file's type from its MAGIC BYTES, never a client-supplied header. Only the
    formats we accept are recognized; everything else (PHP, HTML, scripts, ELF, PDF, SVG, …)
    returns None → rejected. This is the real upload gate — Content-Type is spoofable."""
    if len(data) < 12:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"wOF2":
        return "font/woff2"
    if data[:4] == b"OTTO":
        return "font/otf"
    if data[:4] in (b"\x00\x01\x00\x00", b"true", b"ttcf"):
        return "font/ttf"
    return None


def validate_asset_mime(kind: str, mime: str) -> None:
    """Allow-list check for asset rows created WITHOUT bytes (e.g. Drive registration).
    Raises UnsupportedAssetMime — the DB must never carry a mime the render/vision paths
    would refuse."""
    _extension_for(kind, mime)


def store_asset_file(
    *, tenant_id: str, brand_id: str, kind: str, data: bytes
) -> tuple[str, str]:
    """Write uploaded bytes to disk; return (storage_path, TRUSTED mime).

    The trusted mime is SNIFFED from the bytes (never a client header) and must be allowed for
    this asset kind — so a PHP/HTML/script/SVG payload disguised as image/png is rejected here,
    and the DB always carries the true type. The path is built ONLY from server-generated ids +
    the validated extension — the client's filename never touches the filesystem (it is display
    metadata on the row). The result is asset-ref-shaped (no spaces/quotes) for the contract validator.
    """
    if len(data) > MAX_ASSET_BYTES:
        raise AssetTooLarge(f"asset exceeds {MAX_ASSET_BYTES} bytes")
    real_mime = sniff_mime(data)
    if real_mime is None:
        raise UnsupportedAssetMime("file content is not a recognized image/font type")
    # Cross-kind guard too: a real PNG uploaded as kind=font (or vice-versa) is rejected.
    ext = _extension_for(kind, real_mime)
    root = Path(get_settings().assets_local_root)
    target_dir = root / tenant_id / brand_id
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{uuid4()}.{ext}"
    path.write_bytes(data)
    return str(path), real_mime


async def create_stored_asset(
    session: AsyncSession,
    *,
    brand: BrandRow,
    kind: str,
    data: bytes,
    filename: str,
    approved: bool = False,
    license: str | None = None,
    notes: str | None = None,
) -> BrandAssetRow:
    """Persist trusted bytes and create the matching brand-asset row.

    Uploads and server-bundled assets share this path so storage layout, magic-byte MIME
    detection, size limits, and server-generated filenames cannot drift between flows.
    """
    path, mime = store_asset_file(
        tenant_id=brand.tenant_id,
        brand_id=brand.id,
        kind=kind,
        data=data,
    )
    return await repo.create_brand_asset(
        session,
        tenant_id=brand.tenant_id,
        client_id=brand.client_id,
        brand_id=brand.id,
        kind=kind,
        filename=safe_display_filename(filename),
        mime=mime,
        local_path=path,
        approved=approved,
        license=license,
        notes=notes,
    )


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
    path, _mime = store_asset_file(
        tenant_id=brand.tenant_id,
        brand_id=brand.id,
        kind="logo",
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
