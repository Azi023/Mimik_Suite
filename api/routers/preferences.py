"""Preference routes — the learning loop's request surface. Tenant-scoped; a client principal
is confined to its own client_id on read AND write, exactly like tasks.py (the bounded portal).

Four surfaces:
- POST .../preferences         record an explicit pick/edit signal (feeds this client's profile).
- GET  .../preferences/profile the client's aggregated preference profile + ranker readiness.
- POST .../preferences/rank    re-rank candidate variants by the client's revealed preference.
- POST .../preferences/promote human-gated promotion of a correction into the SHARED golden set.

Client-sourced signals feed ONLY that client's profile. Promotion to the shared golden set is
owner/ops-only (a client role can never reach the promote surface), and even an owner cannot
promote a client-sourced candidate — the policy in mimik_knowledge.promote() enforces that.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal, require_role
from api.db import repo
from api.db.mappers import to_preference_signal
from api.db.session import get_session
from api.services.preferences import Variant, build_profile, rank_variants
from mimik_contracts import ActorRole, PreferenceSignal, PreferenceSource
from mimik_knowledge import PromotionCandidate, PromotionResult, promote_and_write

router = APIRouter(tags=["preferences"])

_PREFERENCE_SOURCE_VALUES = {s.value for s in PreferenceSource}
_ROLE_VALUES = {r.value for r in ActorRole}
# The kinds a promotion may target. The poisoning guard keys on source_role == "client", so
# both fields are validated here rather than silently falling through to a promotable branch.
_PROMOTION_KINDS = {"golden_positive", "golden_negative", "rubric", "prompt", "copy_voice"}


class RecordSignal(BaseModel):
    source: str
    creative_doc_id: str | None = None
    job_id: str | None = None
    detail: str | None = None
    reason_tag: str | None = None
    weight: float = 1.0
    attributes: dict[str, str] = {}


class RankVariant(BaseModel):
    id: str
    attributes: dict[str, str] = {}


class RankRequest(BaseModel):
    variants: list[RankVariant] = []


class PromoteRequest(BaseModel):
    kind: str
    content: str
    source_role: str
    rationale: str | None = None
    reviewer: str | None = None


async def _resolve_client_id(
    session: AsyncSession, *, principal: Principal, path_client_id: str
) -> str:
    """The tasks.py idiom: a client principal is forced onto its own client_id (404 for any
    foreign id — a client cannot even confirm another client exists); a team principal must own
    the client within its tenant (data-layer authZ, never route trust)."""
    if principal.role == ActorRole.CLIENT.value:
        if not principal.client_id:
            raise HTTPException(status_code=403, detail="Client principal has no client_id")
        if path_client_id != principal.client_id:
            raise HTTPException(status_code=404, detail="Client not found")
        return principal.client_id
    client = await repo.get_client(
        session, tenant_id=principal.tenant_id, client_id=path_client_id
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return path_client_id


@router.post("/clients/{client_id}/preferences", response_model=PreferenceSignal, status_code=201)
async def record_preference(
    client_id: str,
    body: RecordSignal,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> PreferenceSignal:
    if body.source not in _PREFERENCE_SOURCE_VALUES:
        raise HTTPException(status_code=422, detail=f"Unknown preference source: {body.source}")
    resolved_client_id = await _resolve_client_id(
        session, principal=principal, path_client_id=client_id
    )
    row = await repo.create_preference_signal(
        session,
        tenant_id=principal.tenant_id,
        client_id=resolved_client_id,
        source=body.source,
        creative_doc_id=body.creative_doc_id,
        job_id=body.job_id,
        detail=body.detail,
        weight=body.weight,
        reason_tag=body.reason_tag,
        attributes=body.attributes,
        actor_role=principal.role,
    )
    await session.commit()
    return to_preference_signal(row)


@router.get("/clients/{client_id}/preferences/profile")
async def get_preference_profile(
    client_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    resolved_client_id = await _resolve_client_id(
        session, principal=principal, path_client_id=client_id
    )
    rows = await repo.list_preference_signals(
        session, tenant_id=principal.tenant_id, client_id=resolved_client_id
    )
    signals = [to_preference_signal(r) for r in rows]
    profile = build_profile(
        tenant_id=principal.tenant_id, client_id=resolved_client_id, signals=signals
    )
    return {
        "profile": profile.model_dump(mode="json"),
        "ranker_active": profile.ranker_active(),
        "signal_count": profile.signal_count,
    }


@router.post("/clients/{client_id}/preferences/rank")
async def rank_preferences(
    client_id: str,
    body: RankRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    resolved_client_id = await _resolve_client_id(
        session, principal=principal, path_client_id=client_id
    )
    rows = await repo.list_preference_signals(
        session, tenant_id=principal.tenant_id, client_id=resolved_client_id
    )
    signals = [to_preference_signal(r) for r in rows]
    variants = [Variant(id=v.id, attributes=v.attributes) for v in body.variants]
    result = rank_variants(signals, variants)
    return result.model_dump(mode="json")


@router.post("/clients/{client_id}/preferences/promote", response_model=PromotionResult)
async def promote_preference(
    client_id: str,
    body: PromoteRequest,
    # Human gate: promotion into the SHARED golden set is owner/ops-only. A client role can
    # never reach this surface (require_role -> 403 before any body is trusted).
    principal: Principal = Depends(require_role("owner", "ops")),
    session: AsyncSession = Depends(get_session),
) -> PromotionResult:
    # Validate the trust-bearing fields the same way record_preference validates source — the
    # guard hinges on source_role, so a typo must 422, never silently take the promotable branch.
    if body.source_role not in _ROLE_VALUES:
        raise HTTPException(status_code=422, detail=f"Unknown source_role: {body.source_role}")
    if body.kind not in _PROMOTION_KINDS:
        raise HTTPException(status_code=422, detail=f"Unknown promotion kind: {body.kind}")
    # Still confirm the client belongs to this tenant (no cross-tenant promotion attribution).
    client = await repo.get_client(
        session, tenant_id=principal.tenant_id, client_id=client_id
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    candidate = PromotionCandidate(
        source_role=body.source_role,
        kind=body.kind,
        content=body.content,
        rationale=body.rationale,
        client_id=client_id,
    )
    golden_dir = os.environ.get("MIMIK_GOLDEN_DIR") or None
    return promote_and_write(candidate, reviewer=body.reviewer, golden_dir=golden_dir)
