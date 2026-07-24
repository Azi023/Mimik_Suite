"""Identity route — `GET /me` returns the verified principal's tenant + role + client binding.

The frontend needs the role (which lives in our `UserAccount`, NOT in the provider token) to steer
each audience to its own surface: a `client`-role session belongs in the bounded portal, an internal
role on the ops app. This is UX / defense-in-depth — the DATA is already confined server-side per role.

It also returns the caller's own tenant `slug`/`name` (a stable, human-readable key that never leaks
another tenant's data — it is resolved from the principal's own `tenant_id`). The web shell keys its
per-tenant white-label branding off this slug (see `web/lib/branding.ts`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal
from api.db import repo
from api.db.session import get_session

router = APIRouter(tags=["me"])


@router.get("/me")
async def whoami(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """The caller's own identity — never another principal's; no enumeration."""
    # Resolve the caller's OWN tenant only (scoped by principal.tenant_id) — additive branding key.
    tenant = await repo.get_tenant(session, principal.tenant_id)
    return {
        "tenant_id": principal.tenant_id,
        "tenant_slug": tenant.slug if tenant is not None else None,
        "tenant_name": tenant.name if tenant is not None else None,
        "role": principal.role,
        "client_id": principal.client_id,
        "user_id": principal.user_id,
    }
