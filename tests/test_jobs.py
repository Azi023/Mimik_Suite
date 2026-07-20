"""Job routes: create/get/list, pillar tagging, cross-tenant reference rejection, and IDOR guard.

The client-principal (bounded-portal) tests reuse the Supabase harness pattern from test_tasks.py:
a provisioned `client` account resolves to a Principal bound to one client_id, so a client can only
ever read its OWN client's jobs — never another client's within the same tenant (the portal authZ).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
import pytest_asyncio
from conftest import superadmin_headers
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient
from jwt.algorithms import ECAlgorithm

from api.core import config, supabase_auth

_ISSUER_BASE = "https://test-project.supabase.co"
_KID = "test-key-1"


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


# --- bounded portal: a client principal is confined to its own client ------------------
# Self-contained Supabase harness (mirrors test_tasks.py) so a real `client`-role Principal
# exercises the portal authZ path rather than only the team code path.


def _pem(private_key: ec.EllipticCurvePrivateKey) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture
def supabase_env(monkeypatch: pytest.MonkeyPatch):
    """Configure the Supabase path + a local EC keypair, inject its JWKS (no network).
    Yields a `mint(sub)` helper producing valid ES256 tokens for that keypair."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = _pem(private_key)
    jwk = ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk.update({"kid": _KID, "use": "sig", "alg": "ES256"})

    config._settings = config.Settings(
        supabase_url=_ISSUER_BASE, supabase_jwks_url=f"{_ISSUER_BASE}/jwks"
    )
    supabase_auth._reset_cache_for_tests()
    monkeypatch.setattr(supabase_auth, "_fetch_jwks", lambda url: {"keys": [jwk]})

    def mint(sub: str) -> str:
        now = datetime.now(timezone.utc)
        claims = {
            "sub": sub,
            "aud": "authenticated",
            "iss": f"{_ISSUER_BASE}/auth/v1",
            "iat": now,
            "exp": now + timedelta(seconds=3600),
            "email": f"{sub}@example.com",
        }
        return jwt.encode(claims, private_pem, algorithm="ES256", headers={"kid": _KID})

    yield mint

    config._settings = None
    supabase_auth._reset_cache_for_tests()


async def _new_client(client: AsyncClient, token: str, name: str) -> str:
    resp = await client.post("/clients", json={"name": name}, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _new_job_for_client(client: AsyncClient, token: str, client_id: str, title: str) -> str:
    """Create a brand under `client_id`, then a job on it; return the job id."""
    bid = (
        await client.post(
            "/brands",
            json={"client_id": client_id, "name": title, "slug": title.lower().replace(" ", "-")},
            headers=_auth(token),
        )
    ).json()["id"]
    resp = await client.post(
        "/jobs", json={"brand_id": bid, "title": title, "format_key": "ig_post"}, headers=_auth(token)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest_asyncio.fixture
async def tenant_two_clients(client: AsyncClient) -> tuple[str, str, str]:
    """Bootstrap a tenant with two clients; return (owner_token, client_a_id, client_b_id)."""
    owner = await _new_tenant(client, "Mimik", "mimik")
    a = await _new_client(client, owner, "Client A")
    b = await _new_client(client, owner, "Client B")
    return owner, a, b


async def test_client_principal_cannot_read_other_clients_job(
    client: AsyncClient, supabase_env, tenant_two_clients
) -> None:
    owner, a_cid, b_cid = tenant_two_clients
    a_job = await _new_job_for_client(client, owner, a_cid, "A job")
    b_job = await _new_job_for_client(client, owner, b_cid, "B job")

    # Provision a client-portal account bound to client A.
    prov = await client.post(
        "/admin/accounts",
        json={"auth_subject": "portal-a", "role": "client", "client_id": a_cid},
        headers=_auth(owner),
    )
    assert prov.status_code == 201, prov.text
    ctoken = supabase_env("portal-a")

    # Client A can read its own job, but client B's job is a 404 (IDOR guard, not 403).
    assert (await client.get(f"/jobs/{a_job}", headers=_auth(ctoken))).status_code == 200
    leaked = await client.get(f"/jobs/{b_job}", headers=_auth(ctoken))
    assert leaked.status_code == 404, "IDOR: client A read client B's job within the tenant!"


async def test_client_principal_list_filtered_to_own_client(
    client: AsyncClient, supabase_env, tenant_two_clients
) -> None:
    owner, a_cid, b_cid = tenant_two_clients
    a_job = await _new_job_for_client(client, owner, a_cid, "A job")
    await _new_job_for_client(client, owner, b_cid, "B job")

    prov = await client.post(
        "/admin/accounts",
        json={"auth_subject": "portal-a", "role": "client", "client_id": a_cid},
        headers=_auth(owner),
    )
    assert prov.status_code == 201, prov.text
    ctoken = supabase_env("portal-a")

    # Listing (even asking for client B) only ever returns client A's jobs.
    listed = await client.get(f"/jobs?client_id={b_cid}", headers=_auth(ctoken))
    assert listed.status_code == 200
    assert [j["id"] for j in listed.json()] == [a_job]


async def test_me_reports_client_role_and_binding(
    client: AsyncClient, supabase_env, tenant_two_clients
) -> None:
    owner, a_cid, _b_cid = tenant_two_clients
    prov = await client.post(
        "/admin/accounts",
        json={"auth_subject": "portal-a", "role": "client", "client_id": a_cid},
        headers=_auth(owner),
    )
    assert prov.status_code == 201, prov.text
    ctoken = supabase_env("portal-a")

    me = await client.get("/me", headers=_auth(ctoken))
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["role"] == "client"
    assert body["client_id"] == a_cid, "GET /me leaked or dropped the client binding"


async def _new_brand_for(client: AsyncClient, token: str, client_id: str, name: str) -> str:
    resp = await client.post(
        "/brands",
        json={"client_id": client_id, "name": name, "slug": name.lower()},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_client_principal_isolation_clients_brands_board(
    client: AsyncClient, supabase_env, tenant_two_clients
) -> None:
    """A client principal must not read other clients' records, brands, or jobs (board). Same IDOR
    class as F-001 — the client-principal confinement extended to clients.py/brands.py/ops.py."""
    owner, a_cid, b_cid = tenant_two_clients
    a_brand = await _new_brand_for(client, owner, a_cid, "ABrand")
    b_brand = await _new_brand_for(client, owner, b_cid, "BBrand")
    a_job = (
        await client.post(
            "/jobs", json={"brand_id": a_brand, "title": "A", "format_key": "ig_post"}, headers=_auth(owner)
        )
    ).json()["id"]
    await client.post(
        "/jobs", json={"brand_id": b_brand, "title": "B", "format_key": "ig_post"}, headers=_auth(owner)
    )

    prov = await client.post(
        "/admin/accounts",
        json={"auth_subject": "portal-a", "role": "client", "client_id": a_cid},
        headers=_auth(owner),
    )
    assert prov.status_code == 201, prov.text
    ctoken = supabase_env("portal-a")

    # /clients — list is confined to the own client; another client's id is a 404.
    listed = await client.get("/clients", headers=_auth(ctoken))
    assert [c["id"] for c in listed.json()] == [a_cid], "client enumerated other clients!"
    assert (await client.get(f"/clients/{b_cid}", headers=_auth(ctoken))).status_code == 404
    assert (await client.get(f"/clients/{a_cid}", headers=_auth(ctoken))).status_code == 200

    # /brands/{id} — another client's brand is a 404; own brand is readable.
    assert (await client.get(f"/brands/{b_brand}", headers=_auth(ctoken))).status_code == 404
    assert (await client.get(f"/brands/{a_brand}", headers=_auth(ctoken))).status_code == 200

    # /ops/board — only the own client's jobs appear.
    board = (await client.get("/ops/board", headers=_auth(ctoken))).json()
    board_ids = [c["job"]["id"] for col in board["columns"].values() for c in col]
    assert a_job in board_ids
    assert all(jid == a_job for jid in board_ids), "client saw another client's jobs on the board!"


async def test_client_principal_isolation_briefs_pillars(
    client: AsyncClient, supabase_env, tenant_two_clients
) -> None:
    """Client principal must not read another client's briefs or pillars (F-002 sweep)."""
    owner, a_cid, b_cid = tenant_two_clients
    a_brand = await _new_brand_for(client, owner, a_cid, "ABr")
    b_brand = await _new_brand_for(client, owner, b_cid, "BBr")
    a_brief = (await client.post("/briefs", json={"brand_id": a_brand}, headers=_auth(owner))).json()["id"]
    b_brief = (await client.post("/briefs", json={"brand_id": b_brand}, headers=_auth(owner))).json()["id"]
    await client.post("/pillars", json={"client_id": a_cid, "preset_key": "promotional"}, headers=_auth(owner))
    await client.post("/pillars", json={"client_id": b_cid, "preset_key": "promotional"}, headers=_auth(owner))

    prov = await client.post(
        "/admin/accounts",
        json={"auth_subject": "portal-a", "role": "client", "client_id": a_cid},
        headers=_auth(owner),
    )
    assert prov.status_code == 201, prov.text
    ctoken = supabase_env("portal-a")

    # briefs — own readable, B's is 404, listing confined to A.
    assert (await client.get(f"/briefs/{a_brief}", headers=_auth(ctoken))).status_code == 200
    assert (await client.get(f"/briefs/{b_brief}", headers=_auth(ctoken))).status_code == 404
    briefs = (await client.get("/briefs", headers=_auth(ctoken))).json()
    assert b_brief not in [b["id"] for b in briefs]
    assert all(b["client_id"] == a_cid for b in briefs)

    # pillars — listing (even asking for client B) only returns A's pillars.
    pillars = (await client.get(f"/pillars?client_id={b_cid}", headers=_auth(ctoken))).json()
    assert all(p["client_id"] == a_cid for p in pillars), "client saw another client's pillars!"
