"""Preference routes: team + client-principal scoping (bounded portal), source validation,
profile + signal_count, the taste-ranker passthrough/active boundary, and the owner/ops-only
promotion gate.

Mirrors the tasks.py client-scoping tests: a provisioned `client` account resolves to a
Principal bound to one client_id, so the real bounded-portal path is exercised, not just the
team code path. The router is included here idempotently so main.py stays untouched.
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


def _pem(private_key: ec.EllipticCurvePrivateKey) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture
def supabase_env(monkeypatch: pytest.MonkeyPatch):
    """Configure the Supabase path + a local EC keypair, inject its JWKS (no network). Yields a
    `mint(sub)` helper producing valid ES256 tokens (replicated from test_tasks.py)."""
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


async def _provision_client_account(
    client: AsyncClient, owner: str, subject: str, client_id: str
) -> None:
    prov = await client.post(
        "/admin/accounts",
        json={"auth_subject": subject, "role": "client", "client_id": client_id},
        headers=_auth(owner),
    )
    assert prov.status_code == 201, prov.text


# --- team happy path -------------------------------------------------------------------


async def test_team_records_a_signal(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)

    resp = await client.post(
        f"/clients/{cid}/preferences",
        json={"source": "pick", "attributes": {"template_key": "lower_band"}, "detail": "chose A"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source"] == "pick"
    # A team (bootstrap owner) principal stamps the signal with its own role, not "client".
    assert body["actor_role"] == "owner"
    assert body["attributes"] == {"template_key": "lower_band"}


async def test_invalid_source_is_422(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)
    resp = await client.post(
        f"/clients/{cid}/preferences",
        json={"source": "not_a_source"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


async def test_profile_summary_and_signal_count(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)
    # No signals yet -> empty profile, ranker inactive.
    empty = await client.get(f"/clients/{cid}/preferences/profile", headers=_auth(token))
    assert empty.status_code == 200
    assert empty.json()["signal_count"] == 0
    assert empty.json()["ranker_active"] is False

    for _ in range(3):
        await client.post(
            f"/clients/{cid}/preferences",
            json={"source": "pick", "attributes": {"template_key": "lower_band"}},
            headers=_auth(token),
        )
    profile = await client.get(f"/clients/{cid}/preferences/profile", headers=_auth(token))
    assert profile.status_code == 200
    data = profile.json()
    assert data["signal_count"] == 3
    assert data["ranker_active"] is False
    assert "3 pick" in data["profile"]["summary"]


# --- taste-ranker boundary -------------------------------------------------------------


async def test_rank_passthrough_below_threshold(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)
    # A handful of signals — below RANKER_MIN_SIGNALS=20 -> passthrough.
    for _ in range(3):
        await client.post(
            f"/clients/{cid}/preferences",
            json={"source": "pick", "attributes": {"template_key": "lower_band"}},
            headers=_auth(token),
        )
    resp = await client.post(
        f"/clients/{cid}/preferences/rank",
        json={
            "variants": [
                {"id": "v1", "attributes": {"template_key": "centered_hero"}},
                {"id": "v2", "attributes": {"template_key": "lower_band"}},
            ]
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["ranker_active"] is False
    # Input order preserved, all scores 0.
    assert [v["id"] for v in result["ranked"]] == ["v1", "v2"]
    assert all(v["score"] == 0.0 for v in result["ranked"])


async def test_rank_reorders_above_threshold(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)
    # 20 approvals favouring lower_band -> ranker active, lower_band should sort first.
    for _ in range(20):
        await client.post(
            f"/clients/{cid}/preferences",
            json={"source": "approval", "attributes": {"template_key": "lower_band"}},
            headers=_auth(token),
        )
    resp = await client.post(
        f"/clients/{cid}/preferences/rank",
        json={
            "variants": [
                {"id": "hero", "attributes": {"template_key": "centered_hero"}},
                {"id": "band", "attributes": {"template_key": "lower_band"}},
            ]
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["ranker_active"] is True
    assert result["ranked"][0]["id"] == "band", "learned favourite should sort first"
    assert result["ranked"][0]["score"] > result["ranked"][1]["score"]


# --- bounded portal: a client principal is confined to its own client ------------------


async def test_client_principal_forced_to_own_client_on_record(
    client: AsyncClient, supabase_env, tenant_two_clients
) -> None:
    owner, a_cid, b_cid = tenant_two_clients
    await _provision_client_account(client, owner, "portal-a", a_cid)
    ctoken = supabase_env("portal-a")

    # Recording against its OWN client works and is stamped actor_role="client".
    ok = await client.post(
        f"/clients/{a_cid}/preferences",
        json={"source": "pick", "attributes": {"template_key": "lower_band"}},
        headers=_auth(ctoken),
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["actor_role"] == "client"

    # Recording against ANOTHER client -> 404 (cannot even confirm it exists).
    leak = await client.post(
        f"/clients/{b_cid}/preferences",
        json={"source": "pick"},
        headers=_auth(ctoken),
    )
    assert leak.status_code == 404


async def test_client_principal_scoped_on_profile_and_rank(
    client: AsyncClient, supabase_env, tenant_two_clients
) -> None:
    owner, a_cid, b_cid = tenant_two_clients
    await _provision_client_account(client, owner, "portal-a", a_cid)
    ctoken = supabase_env("portal-a")

    # Its own profile is reachable.
    own = await client.get(f"/clients/{a_cid}/preferences/profile", headers=_auth(ctoken))
    assert own.status_code == 200

    # Another client's profile -> 404.
    foreign = await client.get(f"/clients/{b_cid}/preferences/profile", headers=_auth(ctoken))
    assert foreign.status_code == 404

    # Ranking against another client -> 404.
    rank_foreign = await client.post(
        f"/clients/{b_cid}/preferences/rank",
        json={"variants": [{"id": "v1", "attributes": {}}]},
        headers=_auth(ctoken),
    )
    assert rank_foreign.status_code == 404


# --- promotion gate: owner/ops only ----------------------------------------------------


async def test_promote_requires_owner_or_ops(
    client: AsyncClient, supabase_env, tenant_two_clients, monkeypatch, tmp_path
) -> None:
    owner, a_cid, _b_cid = tenant_two_clients
    monkeypatch.setenv("MIMIK_GOLDEN_DIR", str(tmp_path))

    # A designer principal cannot promote (require_role -> 403).
    await client.post(
        "/admin/accounts",
        json={"auth_subject": "designer-1", "role": "designer"},
        headers=_auth(owner),
    )
    designer = supabase_env("designer-1")
    resp = await client.post(
        f"/clients/{a_cid}/preferences/promote",
        json={"kind": "golden_positive", "content": "x", "source_role": "team"},
        headers=_auth(designer),
    )
    assert resp.status_code == 403

    # A client principal cannot reach the promote surface at all.
    await _provision_client_account(client, owner, "portal-a", a_cid)
    ctoken = supabase_env("portal-a")
    cresp = await client.post(
        f"/clients/{a_cid}/preferences/promote",
        json={"kind": "golden_positive", "content": "x", "source_role": "team"},
        headers=_auth(ctoken),
    )
    assert cresp.status_code == 403


async def test_promote_of_client_candidate_writes_nothing(
    client: AsyncClient, monkeypatch, tmp_path
) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)
    monkeypatch.setenv("MIMIK_GOLDEN_DIR", str(tmp_path))

    resp = await client.post(
        f"/clients/{cid}/preferences/promote",
        json={
            "kind": "golden_negative",
            "content": "client says logo too small",
            "source_role": "client",
            "reviewer": "atheeque",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["accepted"] is False
    assert body["requires_human_review"] is True
    assert body["written_to"] == []
    # Nothing was written into the (tmp) golden dir.
    assert list(tmp_path.rglob("*.md")) == []


async def test_promote_of_team_candidate_with_reviewer_writes_golden(
    client: AsyncClient, monkeypatch, tmp_path
) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid = await _new_client(client, token)
    monkeypatch.setenv("MIMIK_GOLDEN_DIR", str(tmp_path))

    resp = await client.post(
        f"/clients/{cid}/preferences/promote",
        json={
            "kind": "golden_positive",
            "content": "the warm-toned hero was the winner",
            "source_role": "team",
            "reviewer": "atheeque",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["accepted"] is True
    assert len(body["written_to"]) == 1
    written = list(tmp_path.rglob("*.md"))
    assert len(written) == 1
    body_text = written[0].read_text(encoding="utf-8")
    assert "the warm-toned hero was the winner" in body_text
    assert "promoted-by: atheeque" in body_text  # provenance/audit header


async def test_promote_rejects_unknown_kind_and_source_role(client: AsyncClient) -> None:
    owner = await _new_tenant(client, "Mimik", "mimik")
    client_id = await _new_client(client, owner)
    bad_kind = await client.post(
        f"/clients/{client_id}/preferences/promote",
        json={"kind": "nonsense", "content": "x", "source_role": "team"},
        headers=_auth(owner),
    )
    assert bad_kind.status_code == 422
    bad_role = await client.post(
        f"/clients/{client_id}/preferences/promote",
        json={"kind": "golden_positive", "content": "x", "source_role": "intruder"},
        headers=_auth(owner),
    )
    assert bad_role.status_code == 422
