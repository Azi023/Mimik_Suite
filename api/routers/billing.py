"""Billing routes — Stripe subscription checkout, webhook ingest, and access-gating.

Two surfaces:
  * `/billing/checkout` (team or the client) starts a Stripe Checkout Session — what the
    storefront/portal calls to convert a prospect into a paying client.
  * `/billing/webhook` (Stripe → us, NO app auth) verifies the Stripe signature over the RAW
    body, then mirrors the event into our `SubscriptionRow`.

Access gating (the point of the slice): a bounded-portal action —
`POST /clients/{id}/portal/design-requests` — requires the client's subscription to grant
access, else **402 Payment Required**. This proves an active sub gates access; a missing or
canceled sub is blocked.

Tenant authZ lives at the data layer (every repo call is tenant-scoped). On top of that a
`client` principal is confined to its own client_id on read AND write — a foreign client_id is
404 (never confirm another client's existence), never 403.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal
from api.core.config import get_settings
from api.db import repo
from api.db.mappers import to_subscription, to_task
from api.db.session import get_session
from api.services import billing
from mimik_contracts import ActorRole, Subscription, Task, TaskStatus, TaskType

router = APIRouter(tags=["billing"])


class CheckoutRequest(BaseModel):
    client_id: str | None = None  # ignored for a client principal (forced to their own)


class CheckoutResult(BaseModel):
    checkout_url: str
    session_id: str


class DesignRequest(BaseModel):
    title: str
    detail: str | None = None


async def _resolve_client_for_principal(
    session: AsyncSession, principal: Principal, requested_client_id: str | None
):
    """Resolve the client this request is about, enforcing client-scoping.

    A client principal is forced onto its own client_id (the body/path is ignored). A team
    principal must name a client that belongs to its tenant. Returns the ClientRow. A foreign
    or unknown client is 404 — a client can never confirm another client's existence."""
    if principal.role == ActorRole.CLIENT.value:
        if not principal.client_id:
            raise HTTPException(status_code=403, detail="Client principal has no client_id")
        # If a path/body id was supplied and it isn't theirs, 404 (not 403) so existence leaks.
        if requested_client_id is not None and requested_client_id != principal.client_id:
            raise HTTPException(status_code=404, detail="Client not found")
        client_id = principal.client_id
    else:
        if not requested_client_id:
            raise HTTPException(status_code=422, detail="client_id is required")
        client_id = requested_client_id

    client_row = await repo.get_client(
        session, tenant_id=principal.tenant_id, client_id=client_id
    )
    if client_row is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client_row


@router.post("/billing/checkout", response_model=CheckoutResult)
async def start_checkout(
    body: CheckoutRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> CheckoutResult:
    client_row = await _resolve_client_for_principal(session, principal, body.client_id)
    try:
        result = await billing.create_checkout_session(
            client_id=client_row.id, customer_email=client_row.contact_email
        )
    except billing.BillingNotConfigured:
        # Graceful: billing isn't wired up yet (no Stripe keys). Not a 500.
        raise HTTPException(status_code=503, detail="Billing is not configured")
    return CheckoutResult(checkout_url=result["url"], session_id=result["id"])


@router.post("/billing/webhook")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Billing webhook is not configured")

    raw = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")
    try:
        billing.verify_webhook_signature(
            raw, sig_header, secret=settings.stripe_webhook_secret
        )
    except billing.WebhookError:
        # Untrusted body / bad signature / replay — never process it.
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    await billing.apply_webhook_event(session, event)
    return {"received": True}


@router.get("/clients/{client_id}/subscription", response_model=Subscription)
async def get_client_subscription(
    client_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Subscription:
    client_row = await _resolve_client_for_principal(session, principal, client_id)
    row = await repo.get_subscription_for_client(
        session, tenant_id=principal.tenant_id, client_id=client_row.id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No subscription for this client")
    return to_subscription(row)


@router.post(
    "/clients/{client_id}/portal/design-requests", response_model=Task, status_code=201
)
async def create_design_request(
    client_id: str,
    body: DesignRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Task:
    """Bounded-portal action gated on an active subscription. No/canceled sub → 402."""
    client_row = await _resolve_client_for_principal(session, principal, client_id)

    if not await billing.client_has_access(
        session, tenant_id=principal.tenant_id, client_id=client_row.id
    ):
        raise HTTPException(
            status_code=402, detail="An active subscription is required for this action"
        )

    created_by = {
        "id": principal.user_id or principal.tenant_id,
        "role": principal.role,
    }
    row = await repo.create_task(
        session,
        tenant_id=principal.tenant_id,
        client_id=client_row.id,
        job_id=None,
        type=TaskType.CHANGE_REQUEST.value,
        status=TaskStatus.OPEN.value,
        title=body.title,
        detail=body.detail,
        created_by=created_by,
    )
    await session.commit()
    return to_task(row)
