"""Identity route — `GET /me` returns the verified principal's tenant + role + client binding.

The frontend needs the role (which lives in our `UserAccount`, NOT in the provider token) to steer
each audience to its own surface: a `client`-role session belongs in the bounded portal, an internal
role on the ops app. This is UX / defense-in-depth — the DATA is already confined server-side per role.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.core.auth import Principal, get_principal

router = APIRouter(tags=["me"])


@router.get("/me")
async def whoami(principal: Principal = Depends(get_principal)) -> dict:
    """The caller's own identity — never another principal's; no enumeration."""
    return {
        "tenant_id": principal.tenant_id,
        "role": principal.role,
        "client_id": principal.client_id,
        "user_id": principal.user_id,
    }
