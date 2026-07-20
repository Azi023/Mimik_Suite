"""Auth dependency: turn a Bearer token into a Principal whose tenant_id scopes every query.

Two token issuers are accepted, discriminated by the `iss` claim:

1. **Supabase-issued** (the managed, user-facing path): verified against Supabase's JWKS/secret,
   then mapped through our `UserAccount` table (the authZ source of truth) to a tenant + role.
   A verified provider identity that has no active account is authenticated-but-unprovisioned
   (403) — tenant + role are never taken from provider-controlled token metadata.
2. **First-party bootstrap** (dev/CI + the founding tenant token): our own HS256 token. This is
   an explicit service/bootstrap credential, not user auth — it coexists with Supabase, it does
   not replace the managed provider.
"""

from __future__ import annotations

import asyncio

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import repo
from api.db.session import get_session

from .capabilities import Capability, has_capability
from .config import get_settings
from .security import decode_access_token
from .supabase_auth import SupabaseAuthError, verify_supabase_jwt

_bearer = HTTPBearer(auto_error=True)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
)


class Principal(BaseModel):
    tenant_id: str
    role: str
    user_id: str | None = None      # our UserAccount id (Supabase path only)
    client_id: str | None = None    # set only for the bounded client-portal principal
    auth_subject: str | None = None  # Supabase `sub` (Supabase path only)
    # For internal roles: client_ids this principal is restricted to. Empty = ALL clients in
    # the tenant (the default, current behavior). Provided as a threaded field only in this
    # increment — no existing query route filters on it yet.
    client_scopes: list[str] = []


def _looks_like_supabase(token: str) -> bool:
    """Peek the UNVERIFIED issuer to choose a verifier. The token is still fully verified by
    the chosen path before it is trusted — this only routes, it does not authorize."""
    settings = get_settings()
    if not settings.supabase_issuer:
        return False
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return False
    return claims.get("iss") == settings.supabase_issuer


async def get_principal(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> Principal:
    token = creds.credentials

    if _looks_like_supabase(token):
        try:
            # Verification can fetch the JWKS over the network on a cache miss; offload it so a
            # slow/rotating-key fetch never blocks the async event loop for other requests.
            claims = await asyncio.to_thread(verify_supabase_jwt, token)
        except SupabaseAuthError:
            raise _UNAUTHORIZED
        subject = claims.get("sub")
        if not subject:
            raise _UNAUTHORIZED
        account = await repo.get_user_account_by_subject(session, auth_subject=subject)
        if account is None or not account.active:
            # Authenticated by the provider, but not provisioned in this product.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No active account for this identity"
            )
        # Platform-operator elevation: a verified identity whose email is on the configured
        # super_admin allowlist is lifted to the cross-tenant role. Identity is still fully
        # verified via Supabase and mapped through UserAccount — only the role is raised.
        role = account.role
        if account.email and account.email.lower() in get_settings().superadmin_email_set:
            role = "super_admin"
        return Principal(
            tenant_id=account.tenant_id,
            role=role,
            user_id=account.id,
            client_id=account.client_id,
            auth_subject=subject,
            client_scopes=account.client_scopes or [],
        )

    # First-party bootstrap token.
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise _UNAUTHORIZED
    tenant_id = payload.get("sub")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")
    return Principal(tenant_id=tenant_id, role=payload.get("role", "team"))


def require_role(*roles: str):
    """Dependency factory: 403 unless the principal's role is one of `roles`."""
    allowed = set(roles)

    async def _guard(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role in {sorted(allowed)}",
            )
        return principal

    return _guard


def require_capability(*caps: Capability):
    """Dependency factory (mirrors `require_role`): 403 unless the principal's ROLE grants
    ALL of `caps`. "Has all" is the chosen semantics — a guard names every capability an
    endpoint needs and the principal must hold every one. Purely additive: no existing route
    is switched to it in this increment."""
    required = tuple(caps)

    async def _guard(principal: Principal = Depends(get_principal)) -> Principal:
        if not all(has_capability(principal.role, cap) for cap in required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires capabilities {sorted(c.value for c in required)}",
            )
        return principal

    return _guard


def principal_client_ids(principal: Principal) -> list[str] | None:
    """The client_ids this principal is restricted to, or None for 'all clients in tenant'.

    - A `client`-role principal is hard-scoped to its single bound client_id.
    - An internal principal with non-empty client_scopes is limited to those.
    - An internal principal with empty client_scopes sees ALL clients (returns None)."""
    if principal.client_id is not None:
        return [principal.client_id]
    if principal.client_scopes:
        return list(principal.client_scopes)
    return None


def is_client_in_scope(principal: Principal, client_id: str) -> bool:
    """True if `client_id` is visible to `principal`: empty scope = all clients; a non-empty
    scope restricts; a client-role principal is in-scope only for its own bound client."""
    allowed = principal_client_ids(principal)
    if allowed is None:
        return True
    return client_id in allowed
