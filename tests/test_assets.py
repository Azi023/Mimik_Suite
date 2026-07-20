"""Asset Library routes — the G1 acceptance gate.

Covers: team upload with mime/size discipline, listing, the owner/ops approval gate (an
approved logo is wired into Brand.tokens.logo.ref as a data URI), reference-creative
ingestion (mocked vision + critic) attaching references and seeding preference signals,
tenant isolation (the #1 invariant), and the client-role lockout (assets are team memory,
never portal surface).
"""

from __future__ import annotations

from conftest import superadmin_headers
import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from api.core import config
from api.core.security import create_access_token
from api.services import brand_memory
from mimik_contracts import AssetStudy

_PNG = b"\x89PNG\r\n\x1a\n fake-bytes"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_tenant(client: AsyncClient, name: str, slug: str) -> tuple[str, str]:
    resp = await client.post("/tenants", json={"name": name, "slug": slug}, headers=superadmin_headers())
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["tenant"]["id"], data["access_token"]


async def _new_brand(client: AsyncClient, token: str, slug: str = "g2g") -> str:
    created = await client.post(
        "/clients", json={"name": "Glo2Go"}, headers=_auth(token)
    )
    assert created.status_code == 201, created.text
    client_id = created.json()["id"]
    brand = await client.post(
        "/brands",
        json={
            "client_id": client_id,
            "name": "Glo2Go Aesthetics",
            "slug": slug,
            "niche": "aesthetic clinic",
            "brand_voice": "professional yet approachable",
        },
        headers=_auth(token),
    )
    assert brand.status_code == 201, brand.text
    return brand.json()["id"]


@pytest.fixture
def assets_root(tmp_path: Path):
    config._settings = config.Settings(assets_local_root=str(tmp_path / "assets"))
    yield tmp_path / "assets"
    config._settings = None


def _upload(kind: str = "logo", filename: str = "logo.png") -> dict:
    return {"file": (filename, _PNG, "image/png")}


async def test_upload_list_and_kind_filter(client: AsyncClient, assets_root: Path) -> None:
    _, token = await _new_tenant(client, "Mimik", "mimik")
    brand_id = await _new_brand(client, token)

    up = await client.post(
        f"/brands/{brand_id}/assets",
        files=_upload("logo"),
        data={"kind": "logo"},
        headers=_auth(token),
    )
    assert up.status_code == 201, up.text
    asset = up.json()
    assert asset["kind"] == "logo" and asset["approved"] is False
    assert asset["local_path"] and Path(asset["local_path"]).exists()

    up2 = await client.post(
        f"/brands/{brand_id}/assets",
        files=_upload("reference_creative", "glut-v7.png"),
        data={"kind": "reference_creative"},
        headers=_auth(token),
    )
    assert up2.status_code == 201, up2.text

    listed = await client.get(f"/brands/{brand_id}/assets", headers=_auth(token))
    assert listed.status_code == 200 and len(listed.json()) == 2
    logos = await client.get(
        f"/brands/{brand_id}/assets", params={"kind": "logo"}, headers=_auth(token)
    )
    assert [a["kind"] for a in logos.json()] == ["logo"]


async def test_upload_rejects_bad_mime(client: AsyncClient, assets_root: Path) -> None:
    _, token = await _new_tenant(client, "Mimik", "mimik")
    brand_id = await _new_brand(client, token)
    resp = await client.post(
        f"/brands/{brand_id}/assets",
        files={"file": ("mark.svg", b"<svg/>", "image/svg+xml")},
        data={"kind": "logo"},
        headers=_auth(token),
    )
    assert resp.status_code == 415


async def test_approved_logo_wires_brand_tokens(
    client: AsyncClient, assets_root: Path
) -> None:
    _, token = await _new_tenant(client, "Mimik", "mimik")
    brand_id = await _new_brand(client, token)
    up = await client.post(
        f"/brands/{brand_id}/assets",
        files=_upload("logo"),
        data={"kind": "logo"},
        headers=_auth(token),
    )
    asset_id = up.json()["id"]

    approved = await client.post(f"/assets/{asset_id}/approve", headers=_auth(token))
    assert approved.status_code == 200, approved.text
    assert approved.json()["approved"] is True

    brand = await client.get(f"/brands/{brand_id}", headers=_auth(token))
    ref = brand.json()["tokens"]["logo"]["ref"]
    # The compositor renders from this: a self-contained data URI of the stored bytes.
    assert ref is not None and ref.startswith("data:image/png;base64,")


async def test_register_drive_asset(client: AsyncClient, assets_root: Path) -> None:
    _, token = await _new_tenant(client, "Mimik", "mimik")
    brand_id = await _new_brand(client, token)
    resp = await client.post(
        f"/brands/{brand_id}/assets/register",
        json={
            "kind": "reference_creative",
            "drive_file_id": "1e6mCUVA36iISb_PhsnZCbwnWsA7lYAHa",
            "filename": "G2G - glutathione v7.png",
            "mime": "image/png",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["drive_file_id"] == "1e6mCUVA36iISb_PhsnZCbwnWsA7lYAHa"
    assert resp.json()["local_path"] is None  # bytes come later, via the SA read path


def _mock_study(*_args: object, **_kwargs: object) -> AssetStudy:
    return AssetStudy(
        mood="clean clinical",
        palette=["#8E4B8F", "#FFFFFF"],
        composition="centered subject, text band below",
        complexity="minimal",
        copy_text="Glow from within. Book a consult.",
    )


def _fits_reply(prompt: str) -> str:
    return json.dumps(
        {
            "fit_score": 0.85,
            "fits": True,
            "reasoning": "matches the purple-on-white house style",
            "style": {
                "mood": "clean",
                "palette": ["#8E4B8F"],
                "composition": "centered",
                "lighting": "soft",
                "complexity": "minimal",
            },
        }
    )


def _no_fit_reply(prompt: str) -> str:
    return json.dumps(
        {"fit_score": 0.2, "fits": False, "reasoning": "off-brand neon rave aesthetic"}
    )


async def _uploaded_reference(client: AsyncClient, token: str, brand_id: str) -> str:
    up = await client.post(
        f"/brands/{brand_id}/assets",
        files=_upload("reference_creative", "glut-v7.png"),
        data={"kind": "reference_creative"},
        headers=_auth(token),
    )
    assert up.status_code == 201, up.text
    return up.json()["id"]


async def test_ingest_attaches_reference_and_seeds_signal(
    client: AsyncClient, assets_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, token = await _new_tenant(client, "Mimik", "mimik")
    brand_id = await _new_brand(client, token)
    asset_id = await _uploaded_reference(client, token, brand_id)

    monkeypatch.setattr(brand_memory, "study_creative", _mock_study)
    orig_assess = brand_memory.assess_reference
    monkeypatch.setattr(
        brand_memory,
        "assess_reference",
        lambda brand, meta, content_context, generate=None: orig_assess(
            brand, meta, content_context, generate=_fits_reply
        ),
    )

    resp = await client.post(f"/assets/{asset_id}/ingest", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["attached"] is True
    assert result["signals_recorded"] == 1
    assert result["study"]["palette"][0] == "#8E4B8F"
    assert result["verdict"]["fits"] is True

    # The reference is now on the brand (the style anchor), pointing at the asset.
    brand = await client.get(f"/brands/{brand_id}", headers=_auth(token))
    refs = brand.json()["references"]
    assert len(refs) == 1 and refs[0]["url"] == f"asset://{asset_id}"

    # And the study is persisted on the asset row for future reuse.
    listed = await client.get(f"/brands/{brand_id}/assets", headers=_auth(token))
    stored = [a for a in listed.json() if a["id"] == asset_id][0]
    assert stored["study"]["mood"] == "clean clinical"


async def test_ingest_no_fit_records_nothing_unless_forced(
    client: AsyncClient, assets_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, token = await _new_tenant(client, "Mimik", "mimik")
    brand_id = await _new_brand(client, token)
    asset_id = await _uploaded_reference(client, token, brand_id)

    monkeypatch.setattr(brand_memory, "study_creative", _mock_study)
    orig_assess = brand_memory.assess_reference
    monkeypatch.setattr(
        brand_memory,
        "assess_reference",
        lambda brand, meta, content_context, generate=None: orig_assess(
            brand, meta, content_context, generate=_no_fit_reply
        ),
    )

    resp = await client.post(f"/assets/{asset_id}/ingest", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["attached"] is False
    assert resp.json()["signals_recorded"] == 0
    brand = await client.get(f"/brands/{brand_id}", headers=_auth(token))
    assert brand.json()["references"] == []

    # The human outranks the critic — force_attach attaches WITH the reject verdict kept.
    forced = await client.post(
        f"/assets/{asset_id}/ingest", json={"force_attach": True}, headers=_auth(token)
    )
    assert forced.status_code == 200 and forced.json()["attached"] is True
    brand = await client.get(f"/brands/{brand_id}", headers=_auth(token))
    assert len(brand.json()["references"]) == 1


async def test_ingest_rejects_non_reference_kinds(
    client: AsyncClient, assets_root: Path
) -> None:
    _, token = await _new_tenant(client, "Mimik", "mimik")
    brand_id = await _new_brand(client, token)
    up = await client.post(
        f"/brands/{brand_id}/assets",
        files=_upload("logo"),
        data={"kind": "logo"},
        headers=_auth(token),
    )
    resp = await client.post(f"/assets/{up.json()['id']}/ingest", headers=_auth(token))
    assert resp.status_code == 422


async def test_asset_tenant_isolation(client: AsyncClient, assets_root: Path) -> None:
    _, token_a = await _new_tenant(client, "Agency A", "a")
    _, token_b = await _new_tenant(client, "Agency B", "b")
    brand_a = await _new_brand(client, token_a)
    up = await client.post(
        f"/brands/{brand_a}/assets",
        files=_upload("logo"),
        data={"kind": "logo"},
        headers=_auth(token_a),
    )
    asset_id = up.json()["id"]

    # Tenant B, valid token + correct ids, must see nothing (404, hiding existence).
    assert (
        await client.get(f"/brands/{brand_a}/assets", headers=_auth(token_b))
    ).status_code == 404, "IDOR: tenant B listed tenant A's assets!"
    assert (
        await client.post(f"/assets/{asset_id}/approve", headers=_auth(token_b))
    ).status_code == 404, "IDOR: tenant B approved tenant A's asset!"
    assert (
        await client.post(f"/assets/{asset_id}/ingest", headers=_auth(token_b))
    ).status_code == 404, "IDOR: tenant B ingested tenant A's asset!"


async def test_client_role_is_locked_out(client: AsyncClient, assets_root: Path) -> None:
    tenant_id, token = await _new_tenant(client, "Mimik", "mimik")
    brand_id = await _new_brand(client, token)
    # Assets are team-curated brand memory; the bounded client portal has no business here.
    client_token = create_access_token(tenant_id=tenant_id, role="client")
    resp = await client.get(f"/brands/{brand_id}/assets", headers=_auth(client_token))
    assert resp.status_code == 403


async def test_knockout_endpoint_creates_unapproved_variant(
    client: AsyncClient, assets_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, token = await _new_tenant(client, "Mimik", "mimik")
    brand_id = await _new_brand(client, token)
    up = await client.post(
        f"/brands/{brand_id}/assets",
        files=_upload("logo"),
        data={"kind": "logo"},
        headers=_auth(token),
    )
    asset_id = up.json()["id"]

    # The browser pixel-work is covered in test_brand_memory; here the seam is mocked.
    import creative.render.knockout as knockout_mod

    async def fake_knockout(image_bytes: bytes, mime: str) -> bytes:
        return _PNG

    monkeypatch.setattr(knockout_mod, "derive_knockout_png", fake_knockout)
    resp = await client.post(f"/assets/{asset_id}/knockout", headers=_auth(token))
    assert resp.status_code == 201, resp.text
    variant = resp.json()
    assert variant["approved"] is False
    assert variant["filename"].startswith("knockout-")
    assert variant["id"] != asset_id

    # Non-logo assets are refused.
    up2 = await client.post(
        f"/brands/{brand_id}/assets",
        files=_upload("reference_creative", "ref.png"),
        data={"kind": "reference_creative"},
        headers=_auth(token),
    )
    refused = await client.post(f"/assets/{up2.json()['id']}/knockout", headers=_auth(token))
    assert refused.status_code == 422
