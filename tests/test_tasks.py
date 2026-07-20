"""Task routes: team creation (+ companion notification), client-principal scoping (bounded
portal), tenant isolation, and the ops status advance open -> in_progress -> done.

The client-portal isolation test reuses the Supabase harness (see test_auth_supabase.py): a
provisioned `client` account resolves to a Principal bound to one client_id, so we exercise the
real bounded-portal path rather than only the team code path.
"""

from __future__ import annotations

from conftest import superadmin_headers
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient
from jwt.algorithms import ECAlgorithm

from api.core import config, supabase_auth

_ISSUER_BASE = "https://test-project.supabase.co"
_KID = "test-key-1"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_tenant(client: AsyncClient, name: str, slug: str) -> str:
    resp = await client.post("/tenants", json={"name": name, "slug": slug}, headers=superadmin_headers())
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def _new_client(client: AsyncClient, token: str, name: str = "ACME") -> str:
    resp = await client.post("/clients", json={"name": name}, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# --- team happy path + companion notification ------------------------------------------


async def test_team_creates_task_and_advances_status(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)

    created = await client.post(
        "/tasks",
        json={"client_id": cid, "type": "change_request", "title": "Bigger logo"},
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["status"] == "open"
    assert task["client_id"] == cid
    assert task["type"] == "change_request"
    # created_by carries the team principal's role (the bootstrap owner token here).
    assert task["created_by"]["role"] == "owner"

    # It reads back tenant-scoped.
    fetched = await client.get(f"/tasks/{task['id']}", headers=_auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["id"] == task["id"]

    # Advance open -> in_progress -> done.
    for nxt in ("in_progress", "done"):
        resp = await client.post(
            f"/tasks/{task['id']}/status", json={"status": nxt}, headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == nxt
        assert body["updated_at"] is not None


async def test_task_creation_records_companion_notification(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)

    created = await client.post(
        "/tasks",
        json={"client_id": cid, "type": "comment", "title": "Nice work"},
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    # The companion notification was recorded and links to the task. Verified at the DB layer via
    # dispatch_pending, which only finds a PENDING row if one was created. We reach the same
    # session-maker the request used through the conftest override on api.main.app.
    from api.core.security import decode_access_token
    from api.db import repo
    from api.db.session import get_session
    from api.main import app
    from api.services.notifications import dispatch_pending

    tenant_id = decode_access_token(token)["sub"]
    gen = app.dependency_overrides[get_session]()
    session = await gen.__anext__()
    try:
        notes = await repo.list_notifications(session, tenant_id=tenant_id)
        assert len(notes) == 1
        assert notes[0].task_id == task_id
        assert notes[0].subject == "New comment: Nice work"
        assert notes[0].status == "pending"

        sent = await dispatch_pending(session, tenant_id=tenant_id)
        assert sent == 1
        notes_after = await repo.list_notifications(session, tenant_id=tenant_id)
        assert notes_after[0].status == "sent"
        assert notes_after[0].sent_at is not None
    finally:
        await gen.aclose()


# --- validation + RBAC on the ops side -------------------------------------------------


async def test_create_task_unknown_type_is_422(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)
    resp = await client.post(
        "/tasks",
        json={"client_id": cid, "type": "not_a_type", "title": "x"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


async def test_advance_status_rejects_invalid_status(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)
    task_id = (
        await client.post(
            "/tasks",
            json={"client_id": cid, "type": "generation", "title": "gen"},
            headers=_auth(token),
        )
    ).json()["id"]
    resp = await client.post(
        f"/tasks/{task_id}/status", json={"status": "bogus"}, headers=_auth(token)
    )
    assert resp.status_code == 422


async def test_create_task_foreign_client_is_404(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, "Agency A", "a")
    token_b = await _new_tenant(client, "Agency B", "b")
    a_cid = await _new_client(client, token_a)

    # Team B cannot open a task against tenant A's client, even with the real id.
    resp = await client.post(
        "/tasks",
        json={"client_id": a_cid, "type": "comment", "title": "leak"},
        headers=_auth(token_b),
    )
    assert resp.status_code == 404


async def test_task_isolation_across_tenants(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, "Agency A", "a")
    token_b = await _new_tenant(client, "Agency B", "b")
    a_cid = await _new_client(client, token_a)
    a_task = (
        await client.post(
            "/tasks",
            json={"client_id": a_cid, "type": "comment", "title": "A only"},
            headers=_auth(token_a),
        )
    ).json()["id"]

    # Tenant B, valid token + real id, must NOT read tenant A's task -> 404 (IDOR guard).
    leaked = await client.get(f"/tasks/{a_task}", headers=_auth(token_b))
    assert leaked.status_code == 404, "IDOR: tenant B read tenant A's task!"
    # Tenant B's listing is empty.
    assert (await client.get("/tasks", headers=_auth(token_b))).json() == []


# --- bounded portal: a client principal is confined to its own client ------------------


def _pem(private_key: ec.EllipticCurvePrivateKey) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture
def supabase_env(monkeypatch: pytest.MonkeyPatch):
    """Configure the Supabase path + a local EC keypair, and inject its JWKS (no network).
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


@pytest_asyncio.fixture
async def tenant_two_clients(client: AsyncClient) -> tuple[str, str, str]:
    """Bootstrap a tenant with two clients; return (owner_token, client_a_id, client_b_id)."""
    owner = await _new_tenant(client, "Mimik", "mimik")
    a = await _new_client(client, owner, "Client A")
    b = await _new_client(client, owner, "Client B")
    return owner, a, b


async def test_client_principal_forced_to_own_client_id(
    client: AsyncClient, supabase_env, tenant_two_clients
) -> None:
    owner, a_cid, b_cid = tenant_two_clients
    # Provision a client-portal account bound to client A.
    prov = await client.post(
        "/admin/accounts",
        json={"auth_subject": "portal-a", "role": "client", "client_id": a_cid},
        headers=_auth(owner),
    )
    assert prov.status_code == 201, prov.text
    ctoken = supabase_env("portal-a")

    # The client tries to open a task on client B — but its client_id is forced to A.
    created = await client.post(
        "/tasks",
        json={"client_id": b_cid, "type": "change_request", "title": "portal task"},
        headers=_auth(ctoken),
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["client_id"] == a_cid, "client principal escaped its own client_id!"
    assert task["created_by"]["role"] == "client"


async def test_client_principal_list_filtered_to_own_client(
    client: AsyncClient, supabase_env, tenant_two_clients
) -> None:
    owner, a_cid, b_cid = tenant_two_clients
    # A task exists on each client (opened by the team).
    a_task = (
        await client.post(
            "/tasks",
            json={"client_id": a_cid, "type": "comment", "title": "for A"},
            headers=_auth(owner),
        )
    ).json()["id"]
    b_task = (
        await client.post(
            "/tasks",
            json={"client_id": b_cid, "type": "comment", "title": "for B"},
            headers=_auth(owner),
        )
    ).json()["id"]

    prov = await client.post(
        "/admin/accounts",
        json={"auth_subject": "portal-a", "role": "client", "client_id": a_cid},
        headers=_auth(owner),
    )
    assert prov.status_code == 201, prov.text
    ctoken = supabase_env("portal-a")

    # Listing (even asking for client B) only ever returns client A's tasks.
    listed = await client.get(f"/tasks?client_id={b_cid}", headers=_auth(ctoken))
    assert listed.status_code == 200
    assert [t["id"] for t in listed.json()] == [a_task]

    # Reading client B's task directly is a 404 for the client principal.
    assert (await client.get(f"/tasks/{b_task}", headers=_auth(ctoken))).status_code == 404
    assert (await client.get(f"/tasks/{a_task}", headers=_auth(ctoken))).status_code == 200


async def test_client_principal_cannot_advance_status(
    client: AsyncClient, supabase_env, tenant_two_clients
) -> None:
    owner, a_cid, _b_cid = tenant_two_clients
    a_task = (
        await client.post(
            "/tasks",
            json={"client_id": a_cid, "type": "comment", "title": "for A"},
            headers=_auth(owner),
        )
    ).json()["id"]
    prov = await client.post(
        "/admin/accounts",
        json={"auth_subject": "portal-a", "role": "client", "client_id": a_cid},
        headers=_auth(owner),
    )
    assert prov.status_code == 201, prov.text
    ctoken = supabase_env("portal-a")

    # Advancing status is an ops-side move — a client role is not allowed (require_role -> 403).
    resp = await client.post(
        f"/tasks/{a_task}/status", json={"status": "done"}, headers=_auth(ctoken)
    )
    assert resp.status_code == 403
