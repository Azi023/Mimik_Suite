"""Creative routes — the "generate" step: persist a CreativeDoc (the 5-layer manifest) for a
job, and list a job's creatives. Rendering to a PNG is deterministic from the manifest and
happens at archive time (see api/services/approval_flow.py), so persisting is browser-free.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal, require_role
from api.db import repo
from api.db.mappers import to_brand, to_creative_doc
from api.db.session import get_session
from api.services.creative_generation import (
    GeneratedCreative,
    brand_color,
    creative_artifact_path,
    get_scoped_creative,
    revert_creative,
    revise_creative,
)
from creative.export import psd as psd_export
from creative.pipeline import build_manifest
from mimik_contracts import (
    Actor,
    ActorRole,
    BrandLayout,
    CopyBlock,
    CreativeDoc,
    CreativeManifest,
    CreativeVersionInfo,
    JobStatus,
    LayerKind,
    VersionHistory,
    CanvasRevision,
    RegionAsk,
    TextEdits,
    LayerOp,
)

router = APIRouter(prefix="/jobs/{job_id}/creatives", tags=["creatives"])
artifact_router = APIRouter(prefix="/creatives", tags=["creatives"])

# Any URI scheme (http:, https:, file:, gopher:, ...). An artifact ref becomes a CSS `url(...)`
# the headless compositor fetches at render time, so an EXTERNAL ref is an SSRF vector.
_URI_SCHEME = re.compile(r"^[a-z][a-z0-9+.\-]*:", re.IGNORECASE)


def _assert_safe_image_artifact(value: str | None) -> str | None:
    """image_artifact flows into a `url(...)` the renderer fetches. Allow only inline data URIs
    and internal (relative, no-scheme, no-traversal) asset refs — NEVER an external URL/host,
    which the compositor would fetch server-side (SSRF). See docs/SECURITY_FINDINGS.md R-001."""
    if value is None or value == "":
        return value
    if value.startswith("data:"):
        return value  # inline bytes — no network fetch, no SSRF
    if value.startswith("//") or _URI_SCHEME.match(value):
        raise ValueError("image_artifact must be an internal asset ref or data URI, not a URL")
    if ".." in value:
        raise ValueError("image_artifact must not contain path traversal ('..')")
    return value


class CreateCreative(BaseModel):
    template_key: str
    copy_block: CopyBlock
    image_artifact: str | None = None  # cached L1/L2 ref; None -> placeholder brand ground
    layout: BrandLayout | None = None  # per-creative layout override; None -> brand default

    _safe_artifact = field_validator("image_artifact")(
        staticmethod(_assert_safe_image_artifact)
    )


class ReviseCreativePayload(BaseModel):
    # CanvasRevision fields
    text_edits: TextEdits | None = None
    layer_ops: list[LayerOp] = []
    params: dict[str, object] | None = None
    ask: RegionAsk | None = None
    # Legacy fields
    edits: dict[str, str] | None = None
    instruction: str | None = None

    def as_revision(self) -> CanvasRevision:
        rev = CanvasRevision(
            text_edits=self.text_edits,
            layer_ops=self.layer_ops,
            params=self.params,
            ask=self.ask,
        )
        if self.edits and not rev.text_edits:
            mapped = {}
            if "headline" in self.edits:
                mapped["headline"] = self.edits["headline"]
            if "sub" in self.edits:
                mapped["subhead"] = self.edits["sub"]
            if "cta" in self.edits:
                mapped["cta"] = self.edits["cta"]
            rev.text_edits = TextEdits(**mapped)
        if self.instruction and not rev.ask:
            rev.ask = RegionAsk(zone="other", instruction=self.instruction)
        return rev


class RevertCreativeRequest(BaseModel):
    to_creative_id: str


@router.post("", response_model=CreativeDoc, status_code=201)
async def create_creative(
    job_id: str,
    body: CreateCreative,
    # Generating creatives is a team action — clients never author the engine's output.
    principal: Principal = Depends(require_role("owner", "ops", "designer", "team")),
    session: AsyncSession = Depends(get_session),
) -> CreativeDoc:
    job = await repo.get_job(session, tenant_id=principal.tenant_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    brand_row = await repo.get_brand(session, tenant_id=principal.tenant_id, brand_id=job.brand_id)
    if brand_row is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    manifest = build_manifest(
        to_brand(brand_row),
        body.copy_block,
        job.format_key,
        template_key=body.template_key,
        image_artifact=body.image_artifact,
        layout=body.layout,
    )
    row = await repo.create_creative_doc(
        session,
        tenant_id=principal.tenant_id,
        job_id=job_id,
        manifest=manifest.model_dump(mode="json"),
    )
    # First creative moves the job into internal review (ops looks before the client does).
    if job.status in (JobStatus.DRAFT.value, JobStatus.GENERATING.value):
        job.status = JobStatus.INTERNAL_REVIEW.value
        # Generation produced output: close the human-paced generation window.
        job.generation_started_at = None
    await session.commit()
    return to_creative_doc(row)


@router.get("", response_model=list[CreativeDoc])
async def list_creatives(
    job_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[CreativeDoc]:
    job = await repo.get_job(session, tenant_id=principal.tenant_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    # A client principal may only see its own client's creatives (bounded portal, data-layer authZ).
    if principal.role == ActorRole.CLIENT.value and principal.client_id != job.client_id:
        raise HTTPException(status_code=404, detail="Job not found")
    rows = await repo.list_creative_docs(session, tenant_id=principal.tenant_id, job_id=job_id)
    return [to_creative_doc(r) for r in rows]
@artifact_router.post("/{creative_id}/revise", response_model=GeneratedCreative, status_code=201)
async def revise_creative_endpoint(
    creative_id: str,
    body: ReviseCreativePayload,
    principal: Principal = Depends(
        require_role("owner", "ops", "designer", "team", "client")
    ),
    session: AsyncSession = Depends(get_session),
) -> GeneratedCreative:
    result = await revise_creative(
        session,
        principal=principal,
        creative_id=creative_id,
        revision=body.as_revision(),
    )
    return result


@artifact_router.get("/{creative_id}/versions", response_model=VersionHistory)
async def list_creative_versions_endpoint(
    creative_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> VersionHistory:
    scoped = await get_scoped_creative(
        session,
        principal=principal,
        creative_id=creative_id,
    )
    if scoped is None:
        raise HTTPException(status_code=404, detail="Creative not found")
    _creative_row, job = scoped
    rows = await repo.list_creative_versions(
        session,
        tenant_id=principal.tenant_id,
        job_id=job.id,
    )
    return VersionHistory(
        job_id=job.id,
        versions=[
            CreativeVersionInfo(
                creative_id=row.id,
                version=row.version,
                parent_id=row.parent_id,
                created_at=row.created_at,
                created_by=(
                    Actor.model_validate(row.created_by)
                    if row.created_by is not None
                    else None
                ),
                note=row.revision_note,
                preview_url=f"/creatives/{row.id}/preview",
                svg_url=f"/exports/svg?creative_id={row.id}",
            )
            for row in rows
        ],
    )


@artifact_router.post("/{creative_id}/revert", response_model=GeneratedCreative, status_code=201)
async def revert_creative_endpoint(
    creative_id: str,
    body: RevertCreativeRequest,
    principal: Principal = Depends(require_role("owner", "ops", "designer", "team")),
    session: AsyncSession = Depends(get_session),
) -> GeneratedCreative:
    return await revert_creative(
        session,
        principal=principal,
        creative_id=creative_id,
        to_creative_id=body.to_creative_id,
    )


@artifact_router.get("/{creative_id}/preview")
async def get_creative_preview(
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
    path = creative_artifact_path(scoped[0].id, "preview.png")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Creative preview not found")
    return FileResponse(
        path,
        media_type="image/png",
        headers={"Content-Disposition": "inline"},
    )


@artifact_router.get("/{creative_id}/export.psd")
async def export_creative_psd(
    creative_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Response:
    scoped = await get_scoped_creative(
        session,
        principal=principal,
        creative_id=creative_id,
    )
    if scoped is None:
        raise HTTPException(status_code=404, detail="Creative not found")
    creative_row, _job = scoped
    manifest = CreativeManifest.model_validate(creative_row.manifest)
    copy_block = manifest.copy_block
    image_layer = manifest.layer(LayerKind.L1_BASE)
    if copy_block is None or image_layer is None or image_layer.artifact_ref is None:
        raise HTTPException(status_code=422, detail="Creative cannot be exported as PSD")
    brand_row = await repo.get_brand(
        session,
        tenant_id=principal.tenant_id,
        brand_id=manifest.brand_id,
    )
    if brand_row is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    brand = to_brand(brand_row)
    text_region = image_layer.recipe.params.get("text_region") or "bottom_right"
    psd = await psd_export.render_creative_psd(
        format_key=manifest.format_key,
        image_ref=image_layer.artifact_ref,
        headline=copy_block.headline,
        sub=copy_block.subhead,
        cta=copy_block.cta,
        palette_ink=brand_color(brand, "primary", "#1A1D26"),
        palette_ground=brand_color(brand, "ground", "#FFFFFF"),
        badge_text=brand.name,
        logo_ref=brand.tokens.logo.ref,
        text_region=str(text_region),
    )
    return Response(
        content=psd,
        media_type="image/vnd.adobe.photoshop",
        headers={"Content-Disposition": f'attachment; filename="{creative_id}.psd"'},
    )
