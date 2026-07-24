"""Invitations: email a colleague/client a signed accept-link, keep it copyable in the response,
and let the matching Supabase identity accept it to be provisioned a UserAccount.

Additive to the existing auth (admin.py provisions accounts directly; this is the self-serve
accept path). Email delivery is best-effort, so the link remains usable when email is off or
fails. Tenant isolation is enforced at the data layer: every read/write is filtered by the
caller's tenant_id, so one tenant can never see or mutate another's invites (IDOR defence).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, require_role  # noqa: F401  (Principal used in type hints)
from api.core.config import get_settings
from api.core.invite_token import (
    INVITE_TTL_HOURS,
    InviteTokenError,
    issue_invite_token,
    verify_invite_token,
)
from api.core.supabase_auth import SupabaseAuthError, verify_supabase_jwt
from api.db import repo
from api.db.mappers import _utc, to_invitation, to_user_account
from api.db.session import get_session
from api.services.email import send_email
from mimik_contracts import ActorRole, Invitation, InvitationStatus, UserAccount

_bearer = HTTPBearer(auto_error=True)


class VerifiedIdentity(BaseModel):
    """A provider-verified identity that need NOT yet have a UserAccount — exactly the invitee's
    state at accept time. This is additive to get_principal (which requires an account, 403s
    without one) and reuses the same Supabase verifier; it does not modify the existing guard."""

    auth_subject: str
    email: str | None = None


async def _verified_supabase_identity(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> VerifiedIdentity:
    """Accept-path auth: verify a Supabase token to (subject, email) without an account. A
    first-party bootstrap token has no provider identity to bind, so it is refused here."""
    try:
        claims = await asyncio.to_thread(verify_supabase_jwt, creds.credentials)
    except SupabaseAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    subject = claims.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    return VerifiedIdentity(auth_subject=subject, email=claims.get("email"))

router = APIRouter(prefix="/invitations", tags=["invitations"])

_MANAGE_ROLES = ("super_admin", "owner", "admin")
_ROLE_VALUES = {r.value for r in ActorRole}


class CreateInvitation(BaseModel):
    email: EmailStr
    role: str
    client_scopes: list[str] = []


class InvitationCreated(BaseModel):
    invitation: Invitation
    accept_url: str


class AcceptInvitation(BaseModel):
    token: str


def _accept_url(token: str) -> str:
    base = get_settings().app_base_url.rstrip("/")
    return f"{base}/invite/accept?token={token}"


async def _send_invitation_email(*, email: str, accept_url: str) -> None:
    await send_email(
        to=email,
        subject="You're invited to Mimik Suite",
        body_text=f"You're invited to Mimik Suite.\n\nAccept your invitation:\n{accept_url}",
    )


def _expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=INVITE_TTL_HOURS)


@router.post("", response_model=InvitationCreated, status_code=201)
async def create_invitation(
    body: CreateInvitation,
    principal: Principal = Depends(require_role(*_MANAGE_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> InvitationCreated:
    if body.role not in _ROLE_VALUES:
        raise HTTPException(status_code=422, detail=f"Unknown role: {body.role}")
    # Only a super_admin may mint another super_admin — no privilege escalation via invite.
    if body.role == ActorRole.SUPER_ADMIN.value and principal.role != ActorRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only a super_admin may invite a super_admin")

    # Dedup: one live (pending) invite per email per tenant.
    existing = await repo.get_invitation_by_email(
        session,
        tenant_id=principal.tenant_id,
        email=body.email,
        status=InvitationStatus.PENDING.value,
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="A pending invitation for this email exists")

    row = await repo.create_invitation(
        session,
        tenant_id=principal.tenant_id,
        email=str(body.email),
        role=body.role,
        client_scopes=body.client_scopes,
        status=InvitationStatus.PENDING.value,
        invited_by=principal.user_id or principal.role,
        expires_at=_expiry(),
    )
    await session.commit()

    token = issue_invite_token(
        invitation_id=row.id, tenant_id=row.tenant_id, email=row.email
    )
    accept_url = _accept_url(token)
    await _send_invitation_email(email=row.email, accept_url=accept_url)
    return InvitationCreated(invitation=to_invitation(row), accept_url=accept_url)


@router.get("", response_model=list[Invitation])
async def list_invitations(
    principal: Principal = Depends(require_role(*_MANAGE_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> list[Invitation]:
    rows = await repo.list_invitations(session, tenant_id=principal.tenant_id)
    return [to_invitation(r) for r in rows]


@router.post("/{invitation_id}/revoke", response_model=Invitation)
async def revoke_invitation(
    invitation_id: str,
    principal: Principal = Depends(require_role(*_MANAGE_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> Invitation:
    row = await repo.get_invitation(
        session, tenant_id=principal.tenant_id, invitation_id=invitation_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if row.status != InvitationStatus.PENDING.value:
        raise HTTPException(status_code=409, detail=f"Cannot revoke a {row.status} invitation")
    row.status = InvitationStatus.REVOKED.value
    await session.commit()
    return to_invitation(row)


@router.post("/{invitation_id}/resend", response_model=InvitationCreated)
async def resend_invitation(
    invitation_id: str,
    principal: Principal = Depends(require_role(*_MANAGE_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> InvitationCreated:
    row = await repo.get_invitation(
        session, tenant_id=principal.tenant_id, invitation_id=invitation_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if row.status != InvitationStatus.PENDING.value:
        raise HTTPException(status_code=409, detail=f"Cannot resend a {row.status} invitation")
    # Bump the window and mint a fresh token — the old link is superseded by the new expiry.
    row.expires_at = _expiry()
    await session.commit()

    token = issue_invite_token(
        invitation_id=row.id, tenant_id=row.tenant_id, email=row.email
    )
    accept_url = _accept_url(token)
    await _send_invitation_email(email=row.email, accept_url=accept_url)
    return InvitationCreated(invitation=to_invitation(row), accept_url=accept_url)


@router.post("/accept", response_model=UserAccount, status_code=201)
async def accept_invitation(
    body: AcceptInvitation,
    identity: VerifiedIdentity = Depends(_verified_supabase_identity),
    session: AsyncSession = Depends(get_session),
) -> UserAccount:
    """Consume a pending invite. The caller must be a Supabase-verified identity whose verified
    email matches the invitation's email; on success a UserAccount is provisioned and the invite
    is marked ACCEPTED. The token is a pointer — every guard is re-checked against the DB row."""
    try:
        claims = verify_invite_token(body.token)
    except InviteTokenError:
        # Never echo the token or the underlying jwt error.
        raise HTTPException(status_code=400, detail="Invalid or expired invite token")

    # Look up within the token's tenant; the row is the authority on status + email + role.
    row = await repo.get_invitation(
        session, tenant_id=claims["tenant_id"], invitation_id=claims["invitation_id"]
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if row.status != InvitationStatus.PENDING.value:
        raise HTTPException(status_code=409, detail=f"Invitation is {row.status}")
    # _utc re-attaches UTC to a naive value (SQLite drops tzinfo on read) so the compare is safe.
    expires_at = _utc(row.expires_at)
    if expires_at is not None and expires_at < datetime.now(timezone.utc):
        row.status = InvitationStatus.EXPIRED.value
        await session.commit()
        raise HTTPException(status_code=410, detail="Invitation has expired")

    # The accepting identity's verified email must match the invited email (case-insensitive).
    caller_email = (identity.email or "").lower()
    if not caller_email or caller_email != row.email.lower():
        raise HTTPException(status_code=403, detail="Invitation email does not match your identity")

    # One provider identity maps to exactly one account — refuse if one already exists.
    existing = await repo.get_user_account_by_subject(
        session, auth_subject=identity.auth_subject
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="This identity already has an account")

    # Copy the invite's client scope onto the provisioned account (empty = all clients).
    account = await repo.create_user_account(
        session,
        tenant_id=row.tenant_id,
        auth_subject=identity.auth_subject,
        email=row.email,
        role=row.role,
        client_scopes=row.client_scopes or [],
        name=None,
    )
    row.status = InvitationStatus.ACCEPTED.value
    row.accepted_at = datetime.now(timezone.utc)
    try:
        await session.commit()
    except IntegrityError:
        # Concurrent double-accept: the unique auth_subject constraint is the real backstop for
        # the read-then-write above (the pre-check can race). Surface it as a clean 409, not a 500.
        await session.rollback()
        raise HTTPException(status_code=409, detail="This identity already has an account")
    return to_user_account(account)
