"""Job routes: create/get/list, pillar tagging, cross-tenant reference rejection, and IDOR guard."""

from __future__ import annotations

from conftest import superadmin_headers
from httpx import AsyncClient


async def _new_tenant(client: AsyncClient, name: str, slug: str) -> str:
    resp = await client.post("/tenants", json={"name": name, "slug": slug}, headers=superadmin_headers())
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_brand(client: AsyncClient, token: str) -> tuple[str, str]:
    cid = (await client.post("/clients", json={"name": "ACME"}, headers=_auth(token))).json()["id"]
    resp = await client.post(
        "/brands", json={"client_id": cid, "name": "ACME", "slug": "acme"}, headers=_auth(token)
    )
    assert resp.status_code == 201, resp.text
    return cid, resp.json()["id"]


async def test_create_job_and_get(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid, bid = await _new_brand(client, token)

    created = await client.post(
        "/jobs",
        json={"brand_id": bid, "title": "Launch post", "format_key": "ig_post"},
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    job = created.json()
    assert job["title"] == "Launch post"
    assert job["client_id"] == cid
    assert job["status"] == "draft"

    fetched = await client.get(f"/jobs/{job['id']}", headers=_auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["id"] == job["id"]


async def test_create_job_with_pillar_tag(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid, bid = await _new_brand(client, token)
    pillar_id = (
        await client.post(
            "/pillars", json={"client_id": cid, "preset_key": "promotional"}, headers=_auth(token)
        )
    ).json()["id"]

    created = await client.post(
        "/jobs",
        json={"brand_id": bid, "title": "Sale", "format_key": "ig_post", "pillar_id": pillar_id},
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    assert created.json()["pillar_id"] == pillar_id


async def test_job_rejects_cross_tenant_pillar(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, "Agency A", "a")
    token_b = await _new_tenant(client, "Agency B", "b")
    a_cid, _ = await _new_brand(client, token_a)
    a_pillar = (
        await client.post(
            "/pillars", json={"client_id": a_cid, "preset_key": "product"}, headers=_auth(token_a)
        )
    ).json()["id"]

    # Tenant B has its own brand but tries to reference tenant A's pillar -> 404.
    _, b_bid = await _new_brand(client, token_b)
    resp = await client.post(
        "/jobs",
        json={"brand_id": b_bid, "title": "X", "format_key": "ig_post", "pillar_id": a_pillar},
        headers=_auth(token_b),
    )
    assert resp.status_code == 404


async def test_list_jobs_by_client(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid, bid = await _new_brand(client, token)
    jid = (
        await client.post(
            "/jobs", json={"brand_id": bid, "title": "J", "format_key": "ig_post"}, headers=_auth(token)
        )
    ).json()["id"]

    listed = await client.get(f"/jobs?client_id={cid}", headers=_auth(token))
    assert listed.status_code == 200
    assert [j["id"] for j in listed.json()] == [jid]


async def test_idor_job_isolation_across_tenants(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, "Agency A", "a")
    token_b = await _new_tenant(client, "Agency B", "b")
    _, a_bid = await _new_brand(client, token_a)
    a_job_id = (
        await client.post(
            "/jobs", json={"brand_id": a_bid, "title": "A job", "format_key": "ig_post"}, headers=_auth(token_a)
        )
    ).json()["id"]

    # Tenant A reads its own job.
    assert (await client.get(f"/jobs/{a_job_id}", headers=_auth(token_a))).status_code == 200

    # Tenant B, valid token + correct id, must NOT read tenant A's job -> 404.
    leaked = await client.get(f"/jobs/{a_job_id}", headers=_auth(token_b))
    assert leaked.status_code == 404, "IDOR: tenant B read tenant A's job!"

    # Tenant B's listing is empty.
    assert (await client.get("/jobs", headers=_auth(token_b))).json() == []


async def test_job_rejects_cross_tenant_brand(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, "Agency A", "a")
    token_b = await _new_tenant(client, "Agency B", "b")
    _, a_bid = await _new_brand(client, token_a)

    resp = await client.post(
        "/jobs",
        json={"brand_id": a_bid, "title": "Hijack", "format_key": "ig_post"},
        headers=_auth(token_b),
    )
    assert resp.status_code == 404
