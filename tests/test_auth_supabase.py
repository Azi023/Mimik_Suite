"""Managed-auth (Supabase) verification + UserAccount->Principal mapping + admin provisioning.

The asymmetric ES256/JWKS path is exercised with a locally-generated P-256 keypair whose JWKS
is injected via the `_fetch_jwks` seam — the exact crypto path a real Supabase token takes,
with zero network. The first-party bootstrap path stays green (the isolation suite covers it).
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


def _pem(private_key: ec.EllipticCurvePrivateKey) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture
def supabase_env(monkeypatch: pytest.MonkeyPatch):
    """Configure the Supabase path + a local EC keypair, and inject its JWKS (no network).

    Yields a `mint(sub, **over)` helper producing valid ES256 tokens for that keypair.
    """
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = _pem(private_key)
    jwk = ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk.update({"kid": _KID, "use": "sig", "alg": "ES256"})

    # Override the cached settings so the Supabase verifier is active.
    config._settings = config.Settings(
        supabase_url=_ISSUER_BASE, supabase_jwks_url=f"{_ISSUER_BASE}/jwks"
    )
    supabase_auth._reset_cache_for_tests()
    monkeypatch.setattr(supabase_auth, "_fetch_jwks", lambda url: {"keys": [jwk]})

    def mint(sub: str, *, exp_delta: int = 3600, aud: str = "authenticated", iss: str | None = None,
             kid: str = _KID, key=private_pem) -> str:
        now = datetime.now(timezone.utc)
        claims = {
            "sub": sub,
            "aud": aud,
            "iss": iss if iss is not None else f"{_ISSUER_BASE}/auth/v1",
            "iat": now,
            "exp": now + timedelta(seconds=exp_delta),
            "email": f"{sub}@example.com",
        }
        return jwt.encode(claims, key, algorithm="ES256", headers={"kid": kid})

    yield mint

    config._settings = None
    supabase_auth._reset_cache_for_tests()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _bootstrap_tenant(client: AsyncClient) -> tuple[str, str]:
    """Create a tenant; return (tenant_id, owner first-party token)."""
    resp = await client.post("/tenants", json={"name": "Mimik", "slug": "mimik"}, headers=superadmin_headers())
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["tenant"]["id"], data["access_token"]


async def _provision(client: AsyncClient, owner_token: str, **body) -> dict:
    resp = await client.post("/admin/accounts", json=body, headers=_auth(owner_token))
    return resp


# --- the Supabase verify -> account -> principal happy path ----------------------------


@pytest_asyncio.fixture
async def tenant_with_client(client: AsyncClient) -> tuple[str, str, str]:
    tenant_id, owner = await _bootstrap_tenant(client)
    made = await client.post("/clients", json={"name": "RCD Central"}, headers=_auth(owner))
    return tenant_id, owner, made.json()["id"]


async def test_supabase_token_maps_to_provisioned_tenant(
    client: AsyncClient, supabase_env, tenant_with_client
) -> None:
    _tenant_id, owner, client_id = tenant_with_client
    # Owner provisions an ops account for a Supabase identity.
    prov = await _provision(client, owner, auth_subject="supa-user-1", role="ops", email="ops@x.co")
    assert prov.status_code == 201, prov.text

    # That identity's Supabase token now resolves to the tenant and reads its data.
    token = supabase_env("supa-user-1")
    listed = await client.get("/clients", headers=_auth(token))
    assert listed.status_code == 200, listed.text
    assert [c["id"] for c in listed.json()] == [client_id]


async def test_unprovisioned_identity_is_forbidden(
    client: AsyncClient, supabase_env
) -> None:
    await _bootstrap_tenant(client)
    token = supabase_env("nobody-here")  # verifies fine, but no account exists
    resp = await client.get("/clients", headers=_auth(token))
    assert resp.status_code == 403


async def test_expired_supabase_token_rejected(client: AsyncClient, supabase_env) -> None:
    token = supabase_env("supa-user-1", exp_delta=-10)
    resp = await client.get("/clients", headers=_auth(token))
    assert resp.status_code == 401


async def test_wrong_key_signature_rejected(client: AsyncClient, supabase_env) -> None:
    # A token signed by a DIFFERENT key (kid matches, key does not) must fail verification.
    other = ec.generate_private_key(ec.SECP256R1())
    token = supabase_env("supa-user-1", key=_pem(other))
    resp = await client.get("/clients", headers=_auth(token))
    assert resp.status_code == 401


async def test_wrong_audience_rejected(client: AsyncClient, supabase_env) -> None:
    token = supabase_env("supa-user-1", aud="something-else")
    resp = await client.get("/clients", headers=_auth(token))
    assert resp.status_code == 401


async def test_first_party_bootstrap_token_still_works(client: AsyncClient, supabase_env) -> None:
    # With Supabase configured, a first-party token (no supabase iss) still authenticates.
    _tenant_id, owner = await _bootstrap_tenant(client)
    resp = await client.get("/clients", headers=_auth(owner))
    assert resp.status_code == 200


# --- admin provisioning rules ----------------------------------------------------------


async def test_non_owner_cannot_provision(
    client: AsyncClient, supabase_env, tenant_with_client
) -> None:
    _tenant_id, owner, _client_id = tenant_with_client
    await _provision(client, owner, auth_subject="ops-1", role="ops")
    ops_token = supabase_env("ops-1")
    # An ops principal is not an owner -> 403 on provisioning.
    resp = await _provision(client, ops_token, auth_subject="ops-2", role="ops")
    assert resp.status_code == 403


async def test_client_account_requires_client_id(
    client: AsyncClient, tenant_with_client
) -> None:
    _tenant_id, owner, _client_id = tenant_with_client
    resp = await _provision(client, owner, auth_subject="c-1", role="client")
    assert resp.status_code == 422


async def test_client_account_cross_tenant_client_id_rejected(client: AsyncClient) -> None:
    _a_id, owner_a = await _bootstrap_tenant(client)
    made = await client.post("/clients", json={"name": "A client"}, headers=_auth(owner_a))
    a_client = made.json()["id"]

    resp_b = await client.post("/tenants", json={"name": "B", "slug": "b"}, headers=superadmin_headers())
    owner_b = resp_b.json()["access_token"]
    # Owner B cannot bind a client account to tenant A's client.
    resp = await _provision(client, owner_b, auth_subject="c-1", role="client", client_id=a_client)
    assert resp.status_code == 404


async def test_duplicate_identity_rejected(
    client: AsyncClient, tenant_with_client
) -> None:
    _tenant_id, owner, _client_id = tenant_with_client
    first = await _provision(client, owner, auth_subject="dup", role="designer")
    assert first.status_code == 201
    second = await _provision(client, owner, auth_subject="dup", role="ops")
    assert second.status_code == 409


# --- creatives authZ (bounded portal: clients never generate; clients see only their own) ---


async def test_client_role_cannot_create_creative(
    client: AsyncClient, supabase_env, tenant_with_client
) -> None:
    _tenant_id, owner, client_id = tenant_with_client
    await _provision(client, owner, auth_subject="cli-1", role="client", client_id=client_id)
    brand_id = (
        await client.post(
            "/brands", json={"client_id": client_id, "name": "B", "slug": "b"}, headers=_auth(owner)
        )
    ).json()["id"]
    job_id = (
        await client.post(
            "/jobs",
            json={"brand_id": brand_id, "title": "t", "format_key": "ig_post"},
            headers=_auth(owner),
        )
    ).json()["id"]
    cli = supabase_env("cli-1")
    resp = await client.post(
        f"/jobs/{job_id}/creatives",
        json={"template_key": "centered_hero", "copy_block": {"headline": "x"}},
        headers=_auth(cli),
    )
    assert resp.status_code == 403  # generating creatives is a team action


async def test_client_cannot_list_other_clients_creatives(
    client: AsyncClient, supabase_env
) -> None:
    _tenant_id, owner = await _bootstrap_tenant(client)
    a = (await client.post("/clients", json={"name": "A"}, headers=_auth(owner))).json()["id"]
    b = (await client.post("/clients", json={"name": "B"}, headers=_auth(owner))).json()["id"]
    brand_b = (
        await client.post(
            "/brands", json={"client_id": b, "name": "B", "slug": "b"}, headers=_auth(owner)
        )
    ).json()["id"]
    job_b = (
        await client.post(
            "/jobs",
            json={"brand_id": brand_b, "title": "t", "format_key": "ig_post"},
            headers=_auth(owner),
        )
    ).json()["id"]
    await _provision(client, owner, auth_subject="cli-a", role="client", client_id=a)
    cli_a = supabase_env("cli-a")
    # Client A is bound to client A; client B's job creatives are not theirs -> 404.
    resp = await client.get(f"/jobs/{job_b}/creatives", headers=_auth(cli_a))
    assert resp.status_code == 404


async def test_magic_link_token_is_not_accepted_as_access_token(client: AsyncClient) -> None:
    # A magic-link capability token (same secret, typ=magic_link) must NOT authenticate as a
    # first-party access token — the typ pin is what prevents the confusion.
    from api.core.magic_link import issue_magic_link

    _tenant_id, owner = await _bootstrap_tenant(client)
    made = await client.post("/clients", json={"name": "C"}, headers=_auth(owner))
    client_id = made.json()["id"]
    brand = await client.post(
        "/brands", json={"client_id": client_id, "name": "B", "slug": "b"}, headers=_auth(owner)
    )
    job = await client.post(
        "/jobs",
        json={"brand_id": brand.json()["id"], "title": "t", "format_key": "ig_post"},
        headers=_auth(owner),
    )
    magic = issue_magic_link(tenant_id=_tenant_id, job_id=job.json()["id"], client_id=client_id)
    # Presented as a Bearer access token, it is rejected (401), not honored as a principal.
    resp = await client.get("/clients", headers=_auth(magic))
    assert resp.status_code == 401


async def test_client_cannot_read_other_clients_audit_trail(
    client: AsyncClient, supabase_env
) -> None:
    _tenant_id, owner = await _bootstrap_tenant(client)
    a = (await client.post("/clients", json={"name": "A"}, headers=_auth(owner))).json()["id"]
    b = (await client.post("/clients", json={"name": "B"}, headers=_auth(owner))).json()["id"]
    brand_b = (
        await client.post(
            "/brands", json={"client_id": b, "name": "B", "slug": "b"}, headers=_auth(owner)
        )
    ).json()["id"]
    job_b = (
        await client.post(
            "/jobs",
            json={"brand_id": brand_b, "title": "t", "format_key": "ig_post"},
            headers=_auth(owner),
        )
    ).json()["id"]
    await _provision(client, owner, auth_subject="cli-a2", role="client", client_id=a)
    cli_a = supabase_env("cli-a2")
    # Client A cannot read client B's job audit trail -> 404.
    resp = await client.get(f"/jobs/{job_b}/approvals", headers=_auth(cli_a))
    assert resp.status_code == 404
