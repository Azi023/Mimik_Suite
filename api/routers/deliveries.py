"""Deliveries — the archival record view. On approval, the auto-archive procedure renders the
creative and records a Delivery at a stable per-client Drive path (never a manual upload). This
route lists them for the tenant, joined to their job for the title + client scoping.

AuthZ: tenant-scoped at the data layer; a `client` principal is confined to its own client's
deliveries (bounded portal, constraint #2 — same discipline as jobs/tasks/creatives).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal
from api.db import repo
from api.db.session import get_session
from mimik_contracts import ActorRole

router = APIRouter(tags=["deliveries"])


@router.get("/deliveries")
async def list_deliveries(
    client_id: str | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Every archived delivery in the tenant (newest first). A client principal sees only its own."""
    # Confine a client principal to its own client's deliveries, whatever the query asks for.
    if principal.role == ActorRole.CLIENT.value:
        client_id = principal.client_id
    rows = await repo.list_tenant_deliveries(
        session, tenant_id=principal.tenant_id, client_id=client_id
    )
    return [
        {
            "id": d.id,
            "job_id": d.job_id,
            "job_title": j.title,
            "client_id": j.client_id,
            "creative_doc_id": d.creative_doc_id,
            "drive_path": d.drive_path,
            "delivered_at": d.delivered_at.isoformat() if d.delivered_at is not None else None,
            "created_at": d.created_at.isoformat(),
        }
        for d, j in rows
    ]
