"""Brand create: the onboarding path can seed the mood board with client-shared references."""

from __future__ import annotations

import json

import pytest
from conftest import superadmin_headers
from httpx import AsyncClient

from api.core.security import create_access_token
from creative import prompting


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


async def test_patch_brand_kit_updates_only_named_discovery_field(
    client: AsyncClient,
) -> None:
    token = await _new_tenant(client, slug="kit-partial")
    brand_id = await _new_brand(client, token)
    seeded = await client.patch(
        f"/brands/{brand_id}",
        json={
            "kit": {
                "discovery": {
                    "purpose": "Old purpose",
                    "mission": "Mission stays intact",
                }
            }
        },
        headers=_auth(token),
    )
    assert seeded.status_code == 200, seeded.text

    updated = await client.patch(
        f"/brands/{brand_id}",
        json={"kit": {"discovery": {"purpose": "Sharper purpose"}}},
        headers=_auth(token),
    )

    assert updated.status_code == 200, updated.text
    discovery = updated.json()["kit"]["discovery"]
    assert discovery["purpose"] == "Sharper purpose"
    assert discovery["mission"] == "Mission stays intact"


async def test_patch_brand_discovery_preserves_other_kit_sections(
    client: AsyncClient,
) -> None:
    token = await _new_tenant(client, slug="kit-sections")
    brand_id = await _new_brand(client, token)
    seeded = await client.patch(
        f"/brands/{brand_id}",
        json={
            "kit": {
                "discovery": {"vision": "Original vision"},
                "direction": {"visual_tone": "Tactile and restrained"},
                "applications": [
                    {"kind": "ig_post", "caption": "Launch application"}
                ],
                "launch_templates": [
                    {"name": "Launch post", "format_key": "ig_post"}
                ],
            }
        },
        headers=_auth(token),
    )
    assert seeded.status_code == 200, seeded.text

    updated = await client.patch(
        f"/brands/{brand_id}",
        json={"kit": {"discovery": {"vision": "Expanded vision"}}},
        headers=_auth(token),
    )

    assert updated.status_code == 200, updated.text
    kit = updated.json()["kit"]
    assert kit["direction"]["visual_tone"] == "Tactile and restrained"
    assert kit["applications"] == [
        {
            "kind": "ig_post",
            "asset_id": None,
            "creative_id": None,
            "caption": "Launch application",
        }
    ]
    assert kit["launch_templates"] == [
        {
            "name": "Launch post",
            "format_key": "ig_post",
            "creative_id": None,
            "asset_id": None,
        }
    ]


async def test_patch_brand_kit_list_field_replaces_wholesale(
    client: AsyncClient,
) -> None:
    token = await _new_tenant(client, slug="kit-lists")
    brand_id = await _new_brand(client, token)
    seeded = await client.patch(
        f"/brands/{brand_id}",
        json={
            "kit": {
                "pending_colors": [
                    {"name": "old-one", "display_name": "Old One"},
                    {"name": "old-two", "display_name": "Old Two"},
                ]
            }
        },
        headers=_auth(token),
    )
    assert seeded.status_code == 200, seeded.text

    updated = await client.patch(
        f"/brands/{brand_id}",
        json={
            "kit": {
                "pending_colors": [
                    {"name": "new-only", "display_name": "New Only"}
                ]
            }
        },
        headers=_auth(token),
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["kit"]["pending_colors"] == [
        {"name": "new-only", "display_name": "New Only", "rationale": None}
    ]


async def test_patch_brand_kit_idor_leaves_owner_kit_unchanged(
    client: AsyncClient,
) -> None:
    token_a = await _new_tenant(client, slug="kit-agency-a")
    token_b = await _new_tenant(client, slug="kit-agency-b")
    brand_id = await _new_brand(client, token_a)
    seeded = await client.patch(
        f"/brands/{brand_id}",
        json={"kit": {"discovery": {"purpose": "Tenant A purpose"}}},
        headers=_auth(token_a),
    )
    assert seeded.status_code == 200, seeded.text
    stored_before = seeded.json()["kit"]

    leaked = await client.patch(
        f"/brands/{brand_id}",
        json={"kit": {"discovery": {"purpose": "Tenant B takeover"}}},
        headers=_auth(token_b),
    )

    assert leaked.status_code == 404, "IDOR: tenant B edited tenant A's brand kit!"
    fetched = await client.get(f"/brands/{brand_id}", headers=_auth(token_a))
    assert fetched.json()["kit"] == stored_before


async def test_client_role_cannot_patch_brand_kit(client: AsyncClient) -> None:
    token = await _new_tenant(client, slug="kit-client-role")
    brand_id = await _new_brand(client, token)
    brand = await client.get(f"/brands/{brand_id}", headers=_auth(token))
    client_token = create_access_token(
        tenant_id=brand.json()["tenant_id"],
        role="client",
    )

    rejected = await client.patch(
        f"/brands/{brand_id}",
        json={"kit": {"discovery": {"purpose": "Client-authored overwrite"}}},
        headers=_auth(client_token),
    )

    assert rejected.status_code == 403
    fetched = await client.get(f"/brands/{brand_id}", headers=_auth(token))
    assert fetched.json()["kit"]["discovery"]["purpose"] is None


def _generated_kit_reply() -> dict[str, object]:
    return {
        "discovery": {
            "purpose": "Generated purpose",
            "mission": "Generated mission",
            "vision": "Generated vision",
            "personality": "Generated personality",
            "values": ["Clarity", "Care"],
            "tone_of_voice": "Generated tone",
            "key_usp": "Generated USP",
            "visual_competitor_analysis": "Generated competitor analysis",
            "existing_brand_review": "Generated existing review",
            "timeline": "Generated timeline",
        },
        "direction": {
            "palette_rationale": "Generated palette rationale",
            "visual_tone": "Generated visual tone",
            "personality_alignment": "Generated alignment",
            "competitor_differentiation": "Generated differentiation",
        },
    }


def _stub_brand_kit_text(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return json.dumps(_generated_kit_reply())

    monkeypatch.setattr(prompting, "default_generate", lambda: (generate, "injected:test"))
    return prompts


async def test_generate_brand_kit_fills_only_empty_fields_by_default(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts = _stub_brand_kit_text(monkeypatch)
    token = await _new_tenant(client, slug="kit-generate-empty")
    brand_id = await _new_brand(client, token)
    seeded = await client.patch(
        f"/brands/{brand_id}",
        json={
            "kit": {
                "discovery": {
                    "purpose": "Operator-authored purpose",
                    "mission": None,
                },
                "direction": {"visual_tone": "Operator-authored visual tone"},
            }
        },
        headers=_auth(token),
    )
    assert seeded.status_code == 200, seeded.text

    generated = await client.post(
        f"/brands/{brand_id}/kit/generate",
        json={},
        headers=_auth(token),
    )

    assert generated.status_code == 200, generated.text
    kit = generated.json()["kit"]
    assert kit["discovery"]["purpose"] == "Operator-authored purpose"
    assert kit["discovery"]["mission"] == "Generated mission"
    assert kit["discovery"]["values"] == ["Clarity", "Care"]
    assert kit["direction"]["visual_tone"] == "Operator-authored visual tone"
    assert kit["direction"]["palette_rationale"] == "Generated palette rationale"
    assert kit["prompt_ref"] == "brand_kit_narrative@v1"
    assert kit["updated_at"] is not None
    assert kit["updated_by"]["role"] == "owner"
    assert len(prompts) == 1


async def test_generate_brand_kit_overwrite_replaces_populated_fields(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_brand_kit_text(monkeypatch)
    token = await _new_tenant(client, slug="kit-generate-overwrite")
    brand_id = await _new_brand(client, token)
    seeded = await client.patch(
        f"/brands/{brand_id}",
        json={
            "kit": {
                "discovery": {"purpose": "Operator purpose"},
                "direction": {"visual_tone": "Operator visual tone"},
            }
        },
        headers=_auth(token),
    )
    assert seeded.status_code == 200, seeded.text

    generated = await client.post(
        f"/brands/{brand_id}/kit/generate",
        json={"overwrite": True},
        headers=_auth(token),
    )

    assert generated.status_code == 200, generated.text
    assert generated.json()["kit"]["discovery"]["purpose"] == "Generated purpose"
    assert generated.json()["kit"]["direction"]["visual_tone"] == "Generated visual tone"


async def test_generate_brand_kit_tenant_isolation_leaves_owner_bytes_unchanged(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts = _stub_brand_kit_text(monkeypatch)
    token_a = await _new_tenant(client, slug="kit-generate-a")
    token_b = await _new_tenant(client, slug="kit-generate-b")
    brand_id = await _new_brand(client, token_a)
    seeded = await client.patch(
        f"/brands/{brand_id}",
        json={"kit": {"discovery": {"purpose": "Tenant A purpose"}}},
        headers=_auth(token_a),
    )
    assert seeded.status_code == 200, seeded.text
    stored_before = seeded.json()["kit"]

    rejected = await client.post(
        f"/brands/{brand_id}/kit/generate",
        json={"overwrite": True},
        headers=_auth(token_b),
    )

    assert rejected.status_code == 404
    fetched = await client.get(f"/brands/{brand_id}", headers=_auth(token_a))
    assert fetched.json()["kit"] == stored_before
    assert prompts == []


async def test_client_role_cannot_generate_brand_kit(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts = _stub_brand_kit_text(monkeypatch)
    token = await _new_tenant(client, slug="kit-generate-client")
    brand_id = await _new_brand(client, token)
    brand = await client.get(f"/brands/{brand_id}", headers=_auth(token))
    client_token = create_access_token(
        tenant_id=brand.json()["tenant_id"],
        role="client",
    )

    rejected = await client.post(
        f"/brands/{brand_id}/kit/generate",
        json={},
        headers=_auth(client_token),
    )

    assert rejected.status_code == 403
    fetched = await client.get(f"/brands/{brand_id}", headers=_auth(token))
    assert fetched.json()["kit"]["discovery"]["purpose"] is None
    assert prompts == []
