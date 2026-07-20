"""Magic-link portal read (`POST /portal/session`) + identity (`GET /me`, team path).

The magic-link grant is a signed, single-job capability. The read endpoint must return that ONE
job's review bundle and reject anything else (bad token -> 401; the grant reaches only its own job).
The client-principal `/me` case lives in test_jobs.py (it needs the Supabase harness there).
"""

from __future__ import annotations

from conftest import superadmin_headers
from httpx import AsyncClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_tenant(client: AsyncClient, name: str, slug: str) -> str:
    resp = await client.post("/tenants", json={"name": name, "slug": slug}, headers=superadmin_headers())
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def _new_job(client: AsyncClient, token: str) -> tuple[str, str]:
    """Create client -> brand -> job; return (client_id, job_id)."""
    cid = (await client.post("/clients", json={"name": "ACME"}, headers=_auth(token))).json()["id"]
    bid = (
        await client.post(
            "/brands", json={"client_id": cid, "name": "ACME", "slug": "acme"}, headers=_auth(token)
        )
    ).json()["id"]
    jid = (
        await client.post(
            "/jobs", json={"brand_id": bid, "title": "Launch", "format_key": "ig_post"}, headers=_auth(token)
        )
    ).json()["id"]
    return cid, jid


async def _mint_magic(client: AsyncClient, token: str, job_id: str) -> str:
    resp = await client.post(f"/jobs/{job_id}/magic-link", json={"ttl_hours": 72}, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


async def test_portal_session_returns_job_bundle(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    _cid, jid = await _new_job(client, token)
    magic = await _mint_magic(client, token, jid)

    resp = await client.post("/portal/session", json={"token": magic})
    assert resp.status_code == 200, resp.text
    bundle = resp.json()
    assert bundle["job"]["id"] == jid
    assert bundle["brand"] is not None
    # Shapes present even when empty (no creatives generated yet).
    assert bundle["creatives"] == []
    assert bundle["approvals"] == []
    assert bundle["deliveries"] == []


async def test_portal_session_rejects_garbage_token(client: AsyncClient) -> None:
    resp = await client.post("/portal/session", json={"token": "not-a-real-token"})
    assert resp.status_code == 401


async def test_portal_session_grant_reaches_only_its_own_job(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    _cid_a, job_a = await _new_job(client, token)
    _cid_b, job_b = await _new_job(client, token)

    magic_a = await _mint_magic(client, token, job_a)
    bundle = (await client.post("/portal/session", json={"token": magic_a})).json()
    # The grant for job A resolves to job A only — there is no client-supplied selector to point elsewhere.
    assert bundle["job"]["id"] == job_a
    assert bundle["job"]["id"] != job_b


async def test_me_team_token(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    resp = await client.get("/me", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    me = resp.json()
    # The first-party bootstrap token is an owner-equivalent team principal, not client-scoped.
    assert me["role"] == "owner"
    assert me["client_id"] is None
