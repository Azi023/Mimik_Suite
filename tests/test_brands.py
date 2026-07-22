"""Brand create: the onboarding path can seed the mood board with client-shared references."""

from __future__ import annotations

from conftest import superadmin_headers
from httpx import AsyncClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_tenant(client: AsyncClient, slug: str = "mimik") -> str:
    resp = await client.post(
        "/tenants", json={"name": slug.title(), "slug": slug}, headers=superadmin_headers()
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


async def _new_brand(client: AsyncClient, token: str) -> str:
    cid = (await client.post("/clients", json={"name": "ACME"}, headers=_auth(token))).json()["id"]
    return (
        await client.post(
            "/brands", json={"client_id": cid, "name": "ACME", "slug": "acme"}, headers=_auth(token)
        )
    ).json()["id"]


async def test_patch_brand_tokens_persists_layout(client: AsyncClient) -> None:
    token = await _new_tenant(client)
    bid = await _new_brand(client, token)

    tokens = {
        "colors": [{"name": "Ink", "hex": "#111111", "usage": "Text"}],
        "typography": {"heading_font": "Fraunces", "body_font": "Inter", "hierarchy": []},
        "logo": {"ref": None, "clear_space": None, "min_size_px": 24, "assessment": "usable"},
        "layout": {
            "logo_placement": "bottom_right",
            "logo_scale": 0.18,
            "margins": {"top": 8, "right": 5, "bottom": 12, "left": 5},
            "header": True,
            "footer": False,
            "grid_columns": 12,
            "grid_gutter_pct": 2.0,
            "guides": [{"axis": "x", "pos": 0.25}, {"axis": "y", "pos": 0.75}],
            "show_guides": True,
        },
    }
    resp = await client.patch(f"/brands/{bid}", json=tokens, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    layout = resp.json()["tokens"]["layout"]
    assert layout["logo_placement"] == "bottom_right"
    assert layout["margins"]["bottom"] == 12
    assert layout["header"] is True
    assert len(layout["guides"]) == 2

    # Persisted, not just echoed.
    fetched = await client.get(f"/brands/{bid}", headers=_auth(token))
    assert fetched.json()["tokens"]["layout"]["logo_scale"] == 0.18
    assert fetched.json()["tokens"]["colors"][0]["hex"] == "#111111"


async def test_patch_brand_brief_returns_updated_fields(client: AsyncClient) -> None:
    token = await _new_tenant(client)
    brand_id = await _new_brand(client, token)
    original_tokens = {
        "colors": [{"name": "Ink", "hex": "#111111", "usage": "Text"}],
        "typography": {"heading_font": "Fraunces", "body_font": "Inter", "hierarchy": []},
        "logo": {"ref": None, "clear_space": None, "min_size_px": 24, "assessment": "usable"},
    }
    seeded = await client.patch(
        f"/brands/{brand_id}", json=original_tokens, headers=_auth(token)
    )
    assert seeded.status_code == 200, seeded.text

    updated = await client.patch(
        f"/brands/{brand_id}",
        json={
            "niche": "Boutique skincare clinic",
            "target_audience": "Professionals who research before booking",
            "brand_voice": "Warm, precise, quietly confident",
            "tone_keywords": ["warm", "expert", "clear"],
            "imagery_style": "Natural light on tactile paper grounds",
            "dos": ["Use specific outcomes"],
            "donts": ["Use stock gradients"],
            "tokens": {
                "colors": [{"name": "Rose", "hex": "#C9828A", "usage": "Accent"}]
            },
        },
        headers=_auth(token),
    )

    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["niche"] == "Boutique skincare clinic"
    assert body["tone_keywords"] == ["warm", "expert", "clear"]
    assert body["tokens"]["colors"][0]["hex"] == "#C9828A"
    assert body["tokens"]["typography"]["heading_font"] == "Fraunces"
    fetched = await client.get(f"/brands/{brand_id}", headers=_auth(token))
    assert fetched.json()["donts"] == ["Use stock gradients"]


async def test_patch_brand_rejects_out_of_range_layout(client: AsyncClient) -> None:
    token = await _new_tenant(client)
    bid = await _new_brand(client, token)
    # logo_scale > 0.6 is rejected by the contract at the boundary.
    resp = await client.patch(
        f"/brands/{bid}", json={"layout": {"logo_scale": 0.95}}, headers=_auth(token)
    )
    assert resp.status_code == 422


async def test_patch_brand_tokens_idor(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, slug="agency-a")
    token_b = await _new_tenant(client, slug="agency-b")
    a_bid = await _new_brand(client, token_a)
    # Tenant B cannot edit tenant A's brand tokens -> 404 (data-layer scoping).
    resp = await client.patch(
        f"/brands/{a_bid}", json={"colors": []}, headers=_auth(token_b)
    )
    assert resp.status_code == 404, "IDOR: tenant B edited tenant A's brand!"


async def test_patch_brand_brief_idor(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, slug="agency-a")
    token_b = await _new_tenant(client, slug="agency-b")
    brand_id = await _new_brand(client, token_a)

    leaked = await client.patch(
        f"/brands/{brand_id}",
        json={"brand_voice": "Tenant B's voice"},
        headers=_auth(token_b),
    )

    assert leaked.status_code == 404, "IDOR: tenant B edited tenant A's brand brief!"
    fetched = await client.get(f"/brands/{brand_id}", headers=_auth(token_a))
    assert fetched.json()["brand_voice"] is None
