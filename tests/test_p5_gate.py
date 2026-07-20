"""P5 ACCEPTANCE GATE.

The end-to-end claim-to-paid loop:
  1. A public claim (P5.1) creates a prospect Client and starts a draft Brief.
  2. A (mocked) Stripe Checkout Session is created for that client.
  3. Before payment, the gated bounded-portal action returns 402 (no active sub).
  4. Stripe fires `checkout.session.completed` via a signed webhook; the client's
     Subscription becomes ACTIVE.
  5. The same gated action now returns 201.

Proves: a claim creates a client + starts a brief; a Stripe test-mode checkout activates a sub
that gates access. NO network, NO real Stripe keys.
"""

from __future__ import annotations

from conftest import superadmin_headers
import hashlib
import hmac
import json
import time

import pytest
from httpx import AsyncClient

from api.core import config
from api.services import billing

_SECRET = "sk_test_x"
_PRICE = "price_x"
_WEBHOOK_SECRET = "whsec_x"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def billing_env(monkeypatch: pytest.MonkeyPatch):
    config._settings = config.Settings(
        stripe_secret_key=_SECRET,
        stripe_price_id=_PRICE,
        stripe_webhook_secret=_WEBHOOK_SECRET,
    )

    def _fake_post_form(url: str, headers: dict, fields: dict) -> dict:
        return {"id": "cs_test_p5", "url": "https://checkout.stripe.test/p5"}

    monkeypatch.setattr(billing, "_post_form", _fake_post_form)
    yield
    config._settings = None


def _signed_webhook(body: dict, *, ts: int | None = None):
    raw = json.dumps(body).encode()
    if ts is None:
        ts = int(time.time())
    signed_payload = f"{ts}.".encode() + raw
    sig = hmac.new(_WEBHOOK_SECRET.encode(), signed_payload, hashlib.sha256).hexdigest()
    return raw, f"t={ts},v1={sig}"


async def test_p5_claim_to_paid_access_gate(client: AsyncClient, billing_env) -> None:
    # A storefront tenant to claim through.
    tenant = await client.post("/tenants", json={"name": "Mimik", "slug": "mimik-store"}, headers=superadmin_headers())
    owner = tenant.json()["access_token"]

    # 1) P5.1: a public claim creates a prospect client + starts a draft brief.
    claim = await client.post(
        "/intake/claim",
        json={
            "tenant_slug": "mimik-store",
            "name": "Rivera Dental",
            "email": "hi@riveradental.com",
            "website_url": "https://riveradental.com",
        },
    )
    assert claim.status_code == 201, claim.text
    assert claim.json()["created"] is True
    assert claim.json()["brief"]["status"] == "draft"
    client_id = claim.json()["client"]["id"]

    # 2) Create a (mocked) Stripe Checkout Session for that client.
    checkout = await client.post(
        "/billing/checkout", json={"client_id": client_id}, headers=_auth(owner)
    )
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["session_id"] == "cs_test_p5"

    # 3) Before payment: the gated portal action is 402 (no active subscription).
    before = await client.post(
        f"/clients/{client_id}/portal/design-requests",
        json={"title": "First design request"},
        headers=_auth(owner),
    )
    assert before.status_code == 402, before.text

    # 4) Stripe fires checkout.session.completed via a signed webhook -> sub becomes ACTIVE.
    raw, sig = _signed_webhook(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "client_reference_id": client_id,
                    "customer": "cus_p5",
                    "subscription": "sub_p5",
                    "status": "active",
                }
            },
        }
    )
    hook = await client.post(
        "/billing/webhook", content=raw, headers={"Stripe-Signature": sig}
    )
    assert hook.status_code == 200, hook.text

    sub = await client.get(f"/clients/{client_id}/subscription", headers=_auth(owner))
    assert sub.status_code == 200, sub.text
    assert sub.json()["status"] == "active"

    # 5) After activation: the same gated action now succeeds (201).
    after = await client.post(
        f"/clients/{client_id}/portal/design-requests",
        json={"title": "First design request"},
        headers=_auth(owner),
    )
    assert after.status_code == 201, after.text
    assert after.json()["client_id"] == client_id
