"""Stripe billing service — subscription checkout + webhook lifecycle, MOCKED in dev/test.

Stripe is the source of truth for the subscription lifecycle; we mirror it into a
`SubscriptionRow` (updated by verified webhook events) so access can be gated without a
Stripe round-trip on every request.

No `stripe` SDK dependency: the ONE network path is the module-level `_post_form` seam
(stdlib urllib, form-urlencoded POST), wrapped in `asyncio.to_thread`. Tests monkeypatch it,
so nothing here ever hits the network in dev/test. Without test keys the checkout endpoint
refuses to call Stripe at all (`BillingNotConfigured`) — no accidental live/charge calls. The
secret key and webhook secret are only ever sent to Stripe / used to sign; they are never
logged.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from api.core.config import get_settings
from api.db import repo
from mimik_contracts import Subscription, SubscriptionStatus

_CHECKOUT_SESSIONS_URL = "https://api.stripe.com/v1/checkout/sessions"


class BillingNotConfigured(RuntimeError):
    """Raised when a checkout is attempted but Stripe keys are absent — the graceful human-gate
    (no live Stripe call without configuration), never a crash."""


class WebhookError(RuntimeError):
    """Raised when a Stripe webhook fails signature/replay verification (never trust the body)."""


# Map the Stripe subscription lifecycle onto our access-gating enum. `unpaid` still owes money
# (past_due-adjacent → PAST_DUE); `incomplete_expired` never activated (dead → CANCELED).
STRIPE_STATUS_MAP: dict[str, SubscriptionStatus] = {
    "trialing": SubscriptionStatus.TRIALING,
    "active": SubscriptionStatus.ACTIVE,
    "past_due": SubscriptionStatus.PAST_DUE,
    "unpaid": SubscriptionStatus.PAST_DUE,
    "canceled": SubscriptionStatus.CANCELED,
    "incomplete": SubscriptionStatus.INCOMPLETE,
    "incomplete_expired": SubscriptionStatus.CANCELED,
}


def _post_form(url: str, headers: dict[str, str], fields: dict[str, str]) -> dict:
    """POST an application/x-www-form-urlencoded body and return the JSON response.

    THE only network path in this module (Stripe's REST API is form-encoded). Tests
    monkeypatch this seam, so nothing here ever hits the network in dev/test."""
    body = urllib.parse.urlencode(fields).encode()
    merged = {"Content-Type": "application/x-www-form-urlencoded", **headers}
    req = urllib.request.Request(url, data=body, headers=merged, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed stripe host)
        return json.loads(resp.read())


async def create_checkout_session(
    *, client_id: str, customer_email: str | None = None
) -> dict:
    """Create a Stripe Checkout Session for a subscription and return {"id", "url"}.

    `client_reference_id` carries our client_id through Stripe so the completion webhook maps
    back to the right client. Refuses (BillingNotConfigured) if keys are missing — no live
    call without configuration. The secret key is never logged."""
    settings = get_settings()
    if not settings.stripe_secret_key or not settings.stripe_price_id:
        raise BillingNotConfigured("Stripe is not configured (missing secret key or price id)")

    headers = {"Authorization": f"Bearer {settings.stripe_secret_key}"}
    fields: dict[str, str] = {
        "mode": "subscription",
        "line_items[0][price]": settings.stripe_price_id,
        "line_items[0][quantity]": "1",
        "success_url": settings.billing_success_url,
        "cancel_url": settings.billing_cancel_url,
        "client_reference_id": client_id,
    }
    if customer_email:
        fields["customer_email"] = customer_email

    data = await asyncio.to_thread(_post_form, _CHECKOUT_SESSIONS_URL, headers, fields)
    return {"id": data["id"], "url": data["url"]}


def verify_webhook_signature(
    payload: bytes,
    sig_header: str,
    *,
    secret: str,
    tolerance_s: int = 300,
    now: int | None = None,
) -> None:
    """Verify a Stripe `Stripe-Signature` header against the raw request body.

    Header format: `t=<unix_ts>,v1=<hex_sig>[,v1=<hex_sig>...]`. The signed payload is
    `f"{t}.".encode() + body`, HMAC-SHA256 with the endpoint secret. Constant-time compares
    against every v1 (Stripe may include more than one during secret rotation); rejects if none
    match. Also rejects a timestamp older than `tolerance_s` (replay guard). `now` is injectable
    for tests. No secret material appears in any error message."""
    if now is None:
        now = int(time.time())

    timestamp: str | None = None
    signatures: list[str] = []
    for item in sig_header.split(","):
        key, _, value = item.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)

    if timestamp is None or not signatures:
        raise WebhookError("Malformed Stripe-Signature header")

    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise WebhookError("Malformed Stripe-Signature timestamp") from exc

    if abs(now - ts) > tolerance_s:
        # Symmetric bound: reject both stale (replay) and far-future timestamps.
        raise WebhookError("Stripe-Signature timestamp outside tolerance (possible replay)")

    signed_payload = f"{ts}.".encode() + payload
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise WebhookError("Stripe-Signature does not match payload")


def _period_end(value: object) -> datetime | None:
    """Convert a Stripe unix `current_period_end` to an aware-UTC datetime (None if absent)."""
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc)  # type: ignore[arg-type]


async def _upsert_from_checkout(session, obj: dict) -> Subscription | None:
    """Handle `checkout.session.completed`: resolve tenant from our client_id (carried in
    `client_reference_id`) and upsert the client's subscription row to active/trialing."""
    from api.db.models import ClientRow

    client_id = obj.get("client_reference_id")
    if not client_id:
        return None

    # Stripe is the trusted source and the id came from OUR checkout, so a by-PK lookup (no
    # tenant filter — we don't yet know the tenant) is correct here; the client row supplies it.
    client_row = await session.get(ClientRow, client_id)
    if client_row is None:
        return None
    tenant_id = client_row.tenant_id

    settings = get_settings()
    stripe_status = obj.get("status")
    status = (
        SubscriptionStatus.TRIALING
        if stripe_status == "trialing"
        else SubscriptionStatus.ACTIVE
    )

    row = await repo.get_subscription_for_client(
        session, tenant_id=tenant_id, client_id=client_id
    )
    if row is None:
        row = await repo.create_subscription(
            session,
            tenant_id=tenant_id,
            client_id=client_id,
            status=status.value,
            stripe_customer_id=obj.get("customer"),
            stripe_subscription_id=obj.get("subscription"),
            price_id=settings.stripe_price_id or None,
        )
    else:
        row.status = status.value
        row.stripe_customer_id = obj.get("customer")
        row.stripe_subscription_id = obj.get("subscription")
        row.price_id = settings.stripe_price_id or None

    await session.commit()
    from api.db.mappers import to_subscription

    return to_subscription(row)


async def _update_from_subscription(session, event_type: str, obj: dict) -> Subscription | None:
    """Handle `customer.subscription.updated`/`.deleted`: find the row by Stripe subscription id
    and mirror the new status + current period end."""
    stripe_sub_id = obj.get("id")
    if not stripe_sub_id:
        return None
    row = await repo.get_subscription_by_stripe_id(
        session, stripe_subscription_id=stripe_sub_id
    )
    if row is None:
        return None

    if event_type == "customer.subscription.deleted":
        status = SubscriptionStatus.CANCELED
    else:
        status = STRIPE_STATUS_MAP.get(obj.get("status", ""), SubscriptionStatus.INCOMPLETE)

    row.status = status.value
    period_end = _period_end(obj.get("current_period_end"))
    if period_end is not None:
        row.current_period_end = period_end

    await session.commit()
    from api.db.mappers import to_subscription

    return to_subscription(row)


async def apply_webhook_event(session, event: dict) -> Subscription | None:
    """Apply a verified Stripe event to our subscription mirror. Returns the updated
    Subscription, or None for events we don't act on."""
    event_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}

    if event_type == "checkout.session.completed":
        return await _upsert_from_checkout(session, obj)
    if event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        return await _update_from_subscription(session, event_type, obj)
    return None


async def client_has_access(session, *, tenant_id: str, client_id: str) -> bool:
    """True iff the client's mirrored subscription is in an access-granting state
    (trialing/active). No sub, or a past_due/canceled/incomplete sub, means no access."""
    row = await repo.get_subscription_for_client(
        session, tenant_id=tenant_id, client_id=client_id
    )
    if row is None:
        return False
    return SubscriptionStatus(row.status).grants_access
