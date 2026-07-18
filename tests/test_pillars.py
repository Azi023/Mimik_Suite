"""Content-pillar routes: presets, adopt/custom create, list, and the tenant-isolation IDOR guard."""

from __future__ import annotations

from httpx import AsyncClient


async def _new_tenant(client: AsyncClient, name: str, slug: str) -> str:
    resp = await client.post("/tenants", json={"name": name, "slug": slug})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_client(client: AsyncClient, token: str, name: str = "ACME") -> str:
    resp = await client.post("/clients", json={"name": name}, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_list_presets(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    resp = await client.get("/pillars/presets", headers=_auth(token))
    assert resp.status_code == 200
    keys = {p["key"] for p in resp.json()}
    assert {"educational", "promotional", "seasonal"} <= keys


async def test_adopt_preset_pillar(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)
    resp = await client.post(
        "/pillars",
        json={"client_id": cid, "preset_key": "promotional"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Promotional"
    assert body["is_custom"] is False
    assert body["client_id"] == cid


async def test_create_custom_pillar_and_list(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)
    resp = await client.post(
        "/pillars",
        json={"client_id": cid, "name": "Founder Story", "description": "Personal arc"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["is_custom"] is True

    listed = await client.get(f"/pillars?client_id={cid}", headers=_auth(token))
    assert listed.status_code == 200
    assert [p["name"] for p in listed.json()] == ["Founder Story"]


async def test_pillar_rejects_both_or_neither_source(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)
    # Both -> 422
    both = await client.post(
        "/pillars",
        json={"client_id": cid, "preset_key": "product", "name": "X"},
        headers=_auth(token),
    )
    assert both.status_code == 422
    # Neither -> 422
    neither = await client.post("/pillars", json={"client_id": cid}, headers=_auth(token))
    assert neither.status_code == 422


async def test_pillar_unknown_preset_key(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)
    resp = await client.post(
        "/pillars",
        json={"client_id": cid, "preset_key": "does_not_exist"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


async def test_idor_pillar_isolation_across_tenants(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, "Agency A", "a")
    token_b = await _new_tenant(client, "Agency B", "b")
    a_cid = await _new_client(client, token_a, "A client")

    # Tenant B cannot attach a pillar to tenant A's client -> 404.
    hijack = await client.post(
        "/pillars",
        json={"client_id": a_cid, "preset_key": "product"},
        headers=_auth(token_b),
    )
    assert hijack.status_code == 404, "IDOR: tenant B attached a pillar to tenant A's client!"

    # Tenant A creates a pillar; tenant B must not see it in a list.
    await client.post(
        "/pillars", json={"client_id": a_cid, "preset_key": "product"}, headers=_auth(token_a)
    )
    b_list = await client.get("/pillars", headers=_auth(token_b))
    assert b_list.json() == []
