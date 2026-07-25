"""Brand Kit v2 — Share: token round-trip + tamper rejection, publish flips the flag, and the
public token-read honours the published gate (share kind) while export kind bypasses it.

The token-read endpoint is the only bearer-less surface, so its authZ story is tested hard:
a forged/tampered token, a token for a missing brand, and an unpublished share all 404 with the
same calm not-found — existence is never revealed.
"""

from __future__ import annotations

import pytest
from conftest import superadmin_headers
from httpx import AsyncClient

from api.core.brand_book_token import (
    BrandBookTokenError,
    issue_brand_book_token,
    verify_brand_book_token,
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_tenant(client: AsyncClient, slug: str = "mimik") -> str:
    resp = await client.post(
        "/tenants", json={"name": slug.title(), "slug": slug}, headers=superadmin_headers()
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def _new_brand(client: AsyncClient, token: str) -> str:
    cid = (await client.post("/clients", json={"name": "ACME"}, headers=_auth(token))).json()["id"]
    return (
        await client.post(
            "/brands", json={"client_id": cid, "name": "ACME", "slug": "acme"}, headers=_auth(token)
        )
    ).json()["id"]


# --- token module (no HTTP) ---
def test_token_round_trip_carries_scope() -> None:
    token = issue_brand_book_token(brand_id="b1", tenant_id="t1", kind="share")
    claims = verify_brand_book_token(token)
    assert claims["brand_id"] == "b1"
    assert claims["tenant_id"] == "t1"
    assert claims["kind"] == "share"
    assert claims["typ"] == "brand_book"


def test_token_tamper_is_rejected() -> None:
    token = issue_brand_book_token(brand_id="b1", tenant_id="t1", kind="share")
    # Flip the final char of the signature — verification must fail.
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(BrandBookTokenError):
        verify_brand_book_token(tampered)


def test_token_forged_with_wrong_secret_is_rejected() -> None:
    import jwt

    forged = jwt.encode(
        {"typ": "brand_book", "kind": "share", "brand_id": "b1", "tenant_id": "t1", "exp": 9999999999},
        "attacker-secret-that-is-at-least-32-bytes-long",
        algorithm="HS256",
    )
    with pytest.raises(BrandBookTokenError):
        verify_brand_book_token(forged)


def test_token_unknown_kind_is_rejected() -> None:
    with pytest.raises(BrandBookTokenError):
        issue_brand_book_token(brand_id="b1", tenant_id="t1", kind="bogus")  # type: ignore[arg-type]


# --- publish / unpublish flips the flag ---
async def test_publish_flips_flag_and_returns_share_url(client: AsyncClient) -> None:
    token = await _new_tenant(client)
    bid = await _new_brand(client, token)

    # Fresh brand starts private.
    assert (await client.get(f"/brands/{bid}", headers=_auth(token))).json()["kit"]["published"] is False

    resp = await client.post(f"/brands/{bid}/brand-book/publish", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["published"] is True
    assert body["share_url"].endswith(f"/book/{body['token']}")

    # Persisted, not just echoed.
    assert (await client.get(f"/brands/{bid}", headers=_auth(token))).json()["kit"]["published"] is True

    un = await client.post(f"/brands/{bid}/brand-book/unpublish", headers=_auth(token))
    assert un.status_code == 200, un.text
    assert un.json() == {"published": False, "share_url": None, "token": None}
    assert (await client.get(f"/brands/{bid}", headers=_auth(token))).json()["kit"]["published"] is False


async def test_publish_is_team_gated(client: AsyncClient) -> None:
    from api.core.security import create_access_token

    token = await _new_tenant(client)
    bid = await _new_brand(client, token)
    client_token = create_access_token(tenant_id="mimik", role="client")

    resp = await client.post(f"/brands/{bid}/brand-book/publish", headers=_auth(client_token))
    assert resp.status_code == 403
    # No auth at all -> 401.
    assert (await client.post(f"/brands/{bid}/brand-book/publish")).status_code == 401


async def test_publish_idor(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, slug="agency-a")
    token_b = await _new_tenant(client, slug="agency-b")
    a_bid = await _new_brand(client, token_a)
    # Tenant B cannot publish tenant A's brand -> 404 (data-layer scoping).
    resp = await client.post(f"/brands/{a_bid}/brand-book/publish", headers=_auth(token_b))
    assert resp.status_code == 404


# --- public token-read honours the published gate ---
async def test_token_read_404_when_unpublished_then_200_when_published(client: AsyncClient) -> None:
    token = await _new_tenant(client)
    bid = await _new_brand(client, token)

    share_token = (
        await client.post(f"/brands/{bid}/brand-book/publish", headers=_auth(token))
    ).json()["token"]

    # Published -> public read returns the full brand, NO bearer.
    ok = await client.get(f"/brand-book/{share_token}")
    assert ok.status_code == 200, ok.text
    assert ok.json()["id"] == bid
    assert ok.json()["slug"] == "acme"

    # Unpublish -> the same still-valid token now 404s (the flag is the authority).
    await client.post(f"/brands/{bid}/brand-book/unpublish", headers=_auth(token))
    gone = await client.get(f"/brand-book/{share_token}")
    assert gone.status_code == 404


async def test_token_read_export_kind_bypasses_published(client: AsyncClient) -> None:
    token = await _new_tenant(client)
    bid = await _new_brand(client, token)
    # Grab the tenant_id off the created brand so the export token is correctly scoped.
    tenant_id = (await client.get(f"/brands/{bid}", headers=_auth(token))).json()["tenant_id"]

    export_token = issue_brand_book_token(brand_id=bid, tenant_id=tenant_id, kind="export")
    # Never published, yet the export token (internal render) still resolves the brand.
    resp = await client.get(f"/brand-book/{export_token}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == bid


async def test_token_read_forged_and_missing_are_404(client: AsyncClient) -> None:
    # A garbage token -> calm 404 (no leak, no 500).
    assert (await client.get("/brand-book/not-a-real-token")).status_code == 404

    # A validly-signed token for a brand that doesn't exist -> 404, published gate never reached.
    ghost = issue_brand_book_token(brand_id="does-not-exist", tenant_id="ghost", kind="share")
    assert (await client.get(f"/brand-book/{ghost}")).status_code == 404
