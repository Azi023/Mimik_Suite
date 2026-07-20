"""Stripe billing slice — checkout, webhook signature verification, subscription mirroring,
and access-gating. NO network: `billing._post_form` is monkeypatched; the Stripe signature is
built locally with the test webhook secret. Nothing here ever requires real Stripe keys."""

from __future__ import annotations

from conftest import superadmin_headers
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient
from jwt.algorithms import ECAlgorithm

from api.core import config, supabase_auth
from api.services import billing

_SECRET = "sk_test_x"
_PRICE = "price_x"
_WEBHOOK_SECRET = "whsec_x"
_ISSUER_BASE = "https://test-project.supabase.co"
_KID = "test-key-1"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _stripe_settings(**over) -> config.Settings:
    """Build a Settings carrying the Stripe test keys, preserving any Supabase config already
    active (so billing_env and supabase_env compose regardless of fixture order)."""
    current = config._settings
    base = dict(
        stripe_secret_key=_SECRET,
        stripe_price_id=_PRICE,
        stripe_webhook_secret=_WEBHOOK_SECRET,
    )
    if current is not None:
        base.setdefault("supabase_url", current.supabase_url)
        base.setdefault("supabase_jwks_url", current.supabase_jwks_url)
    base.update(over)
    return config.Settings(**base)


@pytest.fixture
def billing_env(monkeypatch: pytest.MonkeyPatch):
    """Configure Stripe test keys (mirrors test_auth_supabase's settings override) and stub the
    ONLY network seam so checkout returns a fixed session. Yields the captured `_post_form`
    call args so a test can assert what we sent Stripe."""
    config._settings = _stripe_settings()
    captured: dict = {}

    def _fake_post_form(url: str, headers: dict, fields: dict) -> dict:
        captured["url"] = url
        captured["headers"] = headers
        captured["fields"] = fields
        return {"id": "cs_test_1", "url": "https://checkout.stripe.test/x"}

    monkeypatch.setattr(billing, "_post_form", _fake_post_form)
    yield captured
    config._settings = None


def _pem(private_key: ec.EllipticCurvePrivateKey) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture
def supabase_env(monkeypatch: pytest.MonkeyPatch):
    """Local copy of the managed-auth fixture (provision a real client-role principal). Merges
    Stripe keys if billing_env already set them, so both fixtures can be requested together."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = _pem(private_key)
    jwk = ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk.update({"kid": _KID, "use": "sig", "alg": "ES256"})

    current = config._settings
    over = dict(supabase_url=_ISSUER_BASE, supabase_jwks_url=f"{_ISSUER_BASE}/jwks")
    if current is not None:
        over.setdefault("stripe_secret_key", current.stripe_secret_key)
        over.setdefault("stripe_price_id", current.stripe_price_id)
        over.setdefault("stripe_webhook_secret", current.stripe_webhook_secret)
    config._settings = config.Settings(**over)
    supabase_auth._reset_cache_for_tests()
    monkeypatch.setattr(supabase_auth, "_fetch_jwks", lambda url: {"keys": [jwk]})

    def mint(sub: str, *, exp_delta: int = 3600) -> str:
        now = datetime.now(timezone.utc)
        claims = {
            "sub": sub,
            "aud": "authenticated",
            "iss": f"{_ISSUER_BASE}/auth/v1",
            "iat": now,
            "exp": now + timedelta(seconds=exp_delta),
            "email": f"{sub}@example.com",
        }
        return jwt.encode(claims, private_pem, algorithm="ES256", headers={"kid": _KID})

    yield mint
    supabase_auth._reset_cache_for_tests()


async def _bootstrap_tenant(client: AsyncClient) -> tuple[str, str]:
    resp = await client.post("/tenants", json={"name": "Mimik", "slug": "mimik"}, headers=superadmin_headers())
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["tenant"]["id"], data["access_token"]


async def _make_client(client: AsyncClient, owner: str, **body) -> str:
    body.setdefault("name", "Rivera")
    resp = await client.post("/clients", json=body, headers=_auth(owner))
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _signed_webhook(body: dict, *, secret: str = _WEBHOOK_SECRET, ts: int | None = None):
    """Return (raw_bytes, Stripe-Signature header) for a Stripe event, signed like Stripe does."""
    raw = json.dumps(body).encode()
    if ts is None:
        ts = int(time.time())
    signed_payload = f"{ts}.".encode() + raw
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return raw, f"t={ts},v1={sig}"


def _completed_event(client_id: str, *, status: str = "active") -> dict:
    return {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": client_id,
                "customer": "cus_test_1",
                "subscription": "sub_test_1",
                "status": status,
            }
        },
    }


# --- checkout ------------------------------------------------------------------------------


async def test_checkout_returns_url_and_sends_expected_fields(
    client: AsyncClient, billing_env
) -> None:
    _tenant_id, owner = await _bootstrap_tenant(client)
    cid = await _make_client(client, owner, contact_email="hi@rivera.com")

    resp = await client.post(
        "/billing/checkout", json={"client_id": cid}, headers=_auth(owner)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["checkout_url"] == "https://checkout.stripe.test/x"
    assert resp.json()["session_id"] == "cs_test_1"

    fields = billing_env["fields"]
    assert fields["mode"] == "subscription"
    assert fields["client_reference_id"] == cid
    assert fields["line_items[0][price]"] == _PRICE
    assert fields["customer_email"] == "hi@rivera.com"
    # The secret must be sent to Stripe as a bearer, never surfaced in the response body.
    assert billing_env["headers"]["Authorization"] == f"Bearer {_SECRET}"


async def test_checkout_without_keys_is_503(client: AsyncClient) -> None:
    # No billing_env fixture -> settings have empty stripe keys.
    config._settings = None
    _tenant_id, owner = await _bootstrap_tenant(client)
    cid = await _make_client(client, owner)
    resp = await client.post(
        "/billing/checkout", json={"client_id": cid}, headers=_auth(owner)
    )
    assert resp.status_code == 503, resp.text


# --- webhook signature verification --------------------------------------------------------


async def test_valid_webhook_creates_active_subscription(
    client: AsyncClient, billing_env
) -> None:
    _tenant_id, owner = await _bootstrap_tenant(client)
    cid = await _make_client(client, owner)

    raw, sig = _signed_webhook(_completed_event(cid))
    resp = await client.post(
        "/billing/webhook", content=raw, headers={"Stripe-Signature": sig}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"received": True}

    sub = await client.get(f"/clients/{cid}/subscription", headers=_auth(owner))
    assert sub.status_code == 200, sub.text
    assert sub.json()["status"] == "active"


async def test_tampered_signature_is_400(client: AsyncClient, billing_env) -> None:
    _tenant_id, owner = await _bootstrap_tenant(client)
    cid = await _make_client(client, owner)
    raw, sig = _signed_webhook(_completed_event(cid))
    tampered = sig[:-1] + ("0" if sig[-1] != "0" else "1")  # flip the last hex nibble
    resp = await client.post(
        "/billing/webhook", content=raw, headers={"Stripe-Signature": tampered}
    )
    assert resp.status_code == 400, resp.text


async def test_stale_timestamp_is_400(client: AsyncClient, billing_env) -> None:
    _tenant_id, owner = await _bootstrap_tenant(client)
    cid = await _make_client(client, owner)
    # A correctly-signed payload but with a timestamp far in the past -> replay guard rejects.
    raw, sig = _signed_webhook(_completed_event(cid), ts=int(time.time()) - 10_000)
    resp = await client.post(
        "/billing/webhook", content=raw, headers={"Stripe-Signature": sig}
    )
    assert resp.status_code == 400, resp.text


async def test_webhook_without_secret_is_503(client: AsyncClient) -> None:
    config._settings = None  # empty webhook secret
    _tenant_id, owner = await _bootstrap_tenant(client)
    cid = await _make_client(client, owner)
    raw, sig = _signed_webhook(_completed_event(cid))
    resp = await client.post(
        "/billing/webhook", content=raw, headers={"Stripe-Signature": sig}
    )
    assert resp.status_code == 503, resp.text


# --- subscription lifecycle (via apply_webhook_event directly) -----------------------------


async def test_subscription_updated_sets_past_due(client: AsyncClient, billing_env) -> None:
    _tenant_id, owner = await _bootstrap_tenant(client)
    cid = await _make_client(client, owner)
    raw, sig = _signed_webhook(_completed_event(cid))
    await client.post("/billing/webhook", content=raw, headers={"Stripe-Signature": sig})

    raw2, sig2 = _signed_webhook(
        {
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_test_1", "status": "past_due"}},
        }
    )
    resp = await client.post(
        "/billing/webhook", content=raw2, headers={"Stripe-Signature": sig2}
    )
    assert resp.status_code == 200, resp.text
    sub = await client.get(f"/clients/{cid}/subscription", headers=_auth(owner))
    assert sub.json()["status"] == "past_due"


async def test_subscription_deleted_sets_canceled(client: AsyncClient, billing_env) -> None:
    _tenant_id, owner = await _bootstrap_tenant(client)
    cid = await _make_client(client, owner)
    raw, sig = _signed_webhook(_completed_event(cid))
    await client.post("/billing/webhook", content=raw, headers={"Stripe-Signature": sig})

    raw2, sig2 = _signed_webhook(
        {
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_test_1", "status": "canceled"}},
        }
    )
    resp = await client.post(
        "/billing/webhook", content=raw2, headers={"Stripe-Signature": sig2}
    )
    assert resp.status_code == 200, resp.text
    sub = await client.get(f"/clients/{cid}/subscription", headers=_auth(owner))
    assert sub.json()["status"] == "canceled"


# --- access gating -------------------------------------------------------------------------


async def test_design_request_blocked_without_subscription(
    client: AsyncClient, billing_env
) -> None:
    _tenant_id, owner = await _bootstrap_tenant(client)
    cid = await _make_client(client, owner)
    resp = await client.post(
        f"/clients/{cid}/portal/design-requests",
        json={"title": "New promo"},
        headers=_auth(owner),
    )
    assert resp.status_code == 402, resp.text


async def test_design_request_allowed_after_checkout_completed(
    client: AsyncClient, billing_env
) -> None:
    _tenant_id, owner = await _bootstrap_tenant(client)
    cid = await _make_client(client, owner)
    raw, sig = _signed_webhook(_completed_event(cid))
    await client.post("/billing/webhook", content=raw, headers={"Stripe-Signature": sig})

    resp = await client.post(
        f"/clients/{cid}/portal/design-requests",
        json={"title": "New promo", "detail": "Diwali campaign"},
        headers=_auth(owner),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["type"] == "change_request"
    assert resp.json()["title"] == "New promo"


async def test_client_principal_gating_via_bounded_portal(
    client: AsyncClient, billing_env, supabase_env
) -> None:
    """The real bounded-portal path: a client-role principal is blocked until a completed
    checkout activates its sub, then allowed."""
    _tenant_id, owner = await _bootstrap_tenant(client)
    cid = await _make_client(client, owner)
    await client.post(
        "/admin/accounts",
        json={"auth_subject": "cli-bill", "role": "client", "client_id": cid},
        headers=_auth(owner),
    )
    cli = supabase_env("cli-bill")

    blocked = await client.post(
        f"/clients/{cid}/portal/design-requests",
        json={"title": "Before pay"},
        headers=_auth(cli),
    )
    assert blocked.status_code == 402, blocked.text

    raw, sig = _signed_webhook(_completed_event(cid))
    await client.post("/billing/webhook", content=raw, headers={"Stripe-Signature": sig})

    allowed = await client.post(
        f"/clients/{cid}/portal/design-requests",
        json={"title": "After pay"},
        headers=_auth(cli),
    )
    assert allowed.status_code == 201, allowed.text


# --- client-scoping (a client principal is confined to its own client) ---------------------


async def test_client_cannot_read_other_clients_subscription(
    client: AsyncClient, billing_env, supabase_env
) -> None:
    _tenant_id, owner = await _bootstrap_tenant(client)
    a = await _make_client(client, owner, name="A")
    b = await _make_client(client, owner, name="B")
    # Activate B's sub so the row exists (a foreign lookup must 404 regardless of existence).
    raw, sig = _signed_webhook(_completed_event(b))
    await client.post("/billing/webhook", content=raw, headers={"Stripe-Signature": sig})

    await client.post(
        "/admin/accounts",
        json={"auth_subject": "cli-a", "role": "client", "client_id": a},
        headers=_auth(owner),
    )
    cli_a = supabase_env("cli-a")

    # Reading B's subscription as client A -> 404 (never confirm another client exists).
    resp = await client.get(f"/clients/{b}/subscription", headers=_auth(cli_a))
    assert resp.status_code == 404, resp.text


async def test_client_cannot_checkout_another_client(
    client: AsyncClient, billing_env, supabase_env
) -> None:
    _tenant_id, owner = await _bootstrap_tenant(client)
    a = await _make_client(client, owner, name="A")
    b = await _make_client(client, owner, name="B")
    await client.post(
        "/admin/accounts",
        json={"auth_subject": "cli-a2", "role": "client", "client_id": a},
        headers=_auth(owner),
    )
    cli_a = supabase_env("cli-a2")

    # Client A tries to start checkout for client B -> forced to own id path -> 404 on the foreign id.
    resp = await client.post(
        "/billing/checkout", json={"client_id": b}, headers=_auth(cli_a)
    )
    assert resp.status_code == 404, resp.text
