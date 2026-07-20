"""Brand create: the onboarding path can seed the mood board with client-shared references."""

from __future__ import annotations

from conftest import superadmin_headers
from httpx import AsyncClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_tenant(client: AsyncClient) -> str:
    resp = await client.post(
        "/tenants", json={"name": "Mimik", "slug": "mimik"}, headers=superadmin_headers()
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def test_create_brand_with_references_persists(client: AsyncClient) -> None:
    token = await _new_tenant(client)
    cid = (await client.post("/clients", json={"name": "ACME"}, headers=_auth(token))).json()["id"]

    resp = await client.post(
        "/brands",
        json={
            "client_id": cid,
            "name": "ACME",
            "slug": "acme",
            "references": [
                {"url": "https://pinterest.com/acme/board", "source": "pinterest",
                 "note": "the warm-neutral direction"},
                {"url": "https://acme-old.example/post", "source": "social",
                 "note": "their best-performing post"},
            ],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    refs = resp.json()["references"]
    assert [r["url"] for r in refs] == [
        "https://pinterest.com/acme/board",
        "https://acme-old.example/post",
    ]
    assert refs[0]["source"] == "pinterest"
    assert refs[0]["note"] == "the warm-neutral direction"
    # Client-shared references arrive unscored — a later ingest pass fills fit_score.
    assert refs[0]["fit_score"] is None

    # Persisted on the brand, not just echoed.
    bid = resp.json()["id"]
    fetched = await client.get(f"/brands/{bid}", headers=_auth(token))
    assert len(fetched.json()["references"]) == 2


async def test_create_brand_defaults_to_no_references(client: AsyncClient) -> None:
    token = await _new_tenant(client)
    cid = (await client.post("/clients", json={"name": "ACME"}, headers=_auth(token))).json()["id"]
    resp = await client.post(
        "/brands", json={"client_id": cid, "name": "ACME", "slug": "acme"}, headers=_auth(token)
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["references"] == []
