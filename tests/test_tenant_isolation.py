"""P0 acceptance: tenant isolation. These are the guard tests for the #1 security invariant.

If any of these regress, cross-tenant data leakage is possible — treat a failure as a
release blocker.
"""

from __future__ import annotations

from conftest import superadmin_headers
from httpx import AsyncClient


async def _new_tenant(client: AsyncClient, name: str, slug: str) -> tuple[dict, str]:
    resp = await client.post("/tenants", json={"name": name, "slug": slug}, headers=superadmin_headers())
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["tenant"], data["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_client_crud_happy_path(client: AsyncClient) -> None:
    _, token = await _new_tenant(client, "Mimik", "mimik")
    created = await client.post("/clients", json={"name": "RCD Central", "industry": "healthcare"}, headers=_auth(token))
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    listed = await client.get("/clients", headers=_auth(token))
    assert listed.status_code == 200
    assert [c["id"] for c in listed.json()] == [cid]

    fetched = await client.get(f"/clients/{cid}", headers=_auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "RCD Central"


async def test_idor_client_read_blocked_across_tenants(client: AsyncClient) -> None:
    _, token_a = await _new_tenant(client, "Agency A", "a")
    _, token_b = await _new_tenant(client, "Agency B", "b")

    created = await client.post("/clients", json={"name": "A's client"}, headers=_auth(token_a))
    a_client_id = created.json()["id"]

    # Tenant A can read its own client.
    assert (await client.get(f"/clients/{a_client_id}", headers=_auth(token_a))).status_code == 200

    # Tenant B, with a VALID token and the correct id, must NOT read tenant A's client -> 404.
    leaked = await client.get(f"/clients/{a_client_id}", headers=_auth(token_b))
    assert leaked.status_code == 404, "IDOR: tenant B read tenant A's client!"

    # Tenant B's listing must not include tenant A's data.
    b_list = await client.get("/clients", headers=_auth(token_b))
    assert b_list.json() == []


async def test_brand_cannot_attach_to_another_tenants_client(client: AsyncClient) -> None:
    _, token_a = await _new_tenant(client, "Agency A", "a")
    _, token_b = await _new_tenant(client, "Agency B", "b")

    a_client_id = (await client.post("/clients", json={"name": "A's client"}, headers=_auth(token_a))).json()["id"]

    # Tenant B tries to create a brand attached to tenant A's client -> 404 (cross-tenant attach blocked).
    resp = await client.post(
        "/brands",
        json={"client_id": a_client_id, "name": "Hijack", "slug": "hijack"},
        headers=_auth(token_b),
    )
    assert resp.status_code == 404


async def test_unauthenticated_access_rejected(client: AsyncClient) -> None:
    # Missing credentials and a bad token are both rejected (401 Unauthorized).
    assert (await client.get("/clients")).status_code == 401
    assert (await client.get("/clients", headers=_auth("garbage.token.value"))).status_code == 401
