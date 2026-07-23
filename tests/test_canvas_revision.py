"""Test CanvasRevision structure, BC shim, layer operations, and inheritance."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import superadmin_headers
from httpx import AsyncClient
from mimik_contracts import CopyBlock

from api.services import creative_generation


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_tenant(
    client: AsyncClient, *, name: str, slug: str
) -> tuple[str, str]:
    response = await client.post(
        "/tenants",
        json={"name": name, "slug": slug},
        headers=superadmin_headers(),
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return payload["tenant"]["id"], payload["access_token"]


async def _create_creative(
    client: AsyncClient,
    *,
    token: str,
    suffix: str,
) -> tuple[str, str, str]:
    client_response = await client.post(
        "/clients",
        json={"name": f"Client {suffix}"},
        headers=_auth(token),
    )
    assert client_response.status_code == 201, client_response.text
    client_id = client_response.json()["id"]

    brand_response = await client.post(
        "/brands",
        json={
            "client_id": client_id,
            "name": f"Brand {suffix}",
            "slug": f"brand-{suffix}",
            "tokens": {
                "colors": [
                    {"name": "primary", "hex": "#112233"},
                    {"name": "ground", "hex": "#FFFFFF"},
                ]
            },
        },
        headers=_auth(token),
    )
    assert brand_response.status_code == 201, brand_response.text

    job_response = await client.post(
        "/jobs",
        json={
            "brand_id": brand_response.json()["id"],
            "title": f"Job {suffix}",
            "format_key": "ig_post",
        },
        headers=_auth(token),
    )
    assert job_response.status_code == 201, job_response.text
    job_id = job_response.json()["id"]

    creative_response = await client.post(
        f"/jobs/{job_id}/creatives",
        json={
            "template_key": "centered_hero",
            "copy_block": {
                "headline": f"Original {suffix}",
                "subhead": "Original subhead",
                "cta": "Original CTA",
            },
            "image_artifact": "source.png",
        },
        headers=_auth(token),
    )
    assert creative_response.status_code == 201, creative_response.text
    return client_id, job_id, creative_response.json()["id"]


def _stub_renderer(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    async def fake_render(**kwargs: object) -> tuple[Path, Path, None]:
        calls.append(kwargs)
        artifact_dir = kwargs["artifact_dir"]
        assert isinstance(artifact_dir, Path)
        svg_path = artifact_dir / "creative.svg"
        preview_path = artifact_dir / "preview.png"
        
        layer_overrides = kwargs.get("render_params", {}).get("layer_overrides", {})
        
        svg_content = "<svg>"
        for layer_id, op in layer_overrides.items():
            svg_content += f"<g id='{layer_id}'"
            if "dx" in op:
                svg_content += f" dx='{op['dx']}'"
            if "dy" in op:
                svg_content += f" dy='{op['dy']}'"
            if "scale" in op:
                svg_content += f" scale='{op['scale']}'"
            if "visible" in op:
                svg_content += f" visible='{op['visible']}'"
            if "fill" in op:
                svg_content += f" fill='{op['fill']}'"
            svg_content += "></g>"
        svg_content += "</svg>"

        svg_path.write_text(svg_content, encoding="utf-8")
        preview_path.write_bytes(f"preview-{len(calls)}".encode())
        return svg_path, preview_path, None

    monkeypatch.setattr(creative_generation, "_render_creative_artifacts", fake_render)
    return calls


async def test_revise_with_layer_ops_applies_overrides(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    _stub_renderer(monkeypatch)
    
    tenant_id, token = await _create_tenant(client, name="Mimik", slug="mimik")
    _client_id, job_id, first_id = await _create_creative(
        client, token=token, suffix="layerops"
    )

    revised = await client.post(
        f"/creatives/{first_id}/revise",
        json={
            "layer_ops": [
                {"layer_id": "layer-panel", "dx": 120}
            ]
        },
        headers=_auth(token),
    )

    assert revised.status_code == 201, revised.text
    creative = revised.json()["creative"]
    
    # Check L1 params
    l1_params = creative["manifest"]["layers"][0]["recipe"]["params"]
    assert "layer_overrides" in l1_params
    assert l1_params["layer_overrides"]["layer-panel"]["dx"] == 120
    
    # Check rendered SVG
    svg_url = revised.json()["svg_url"]
    svg_resp = await client.get(svg_url, headers=_auth(token))
    assert svg_resp.status_code == 200
    assert "id='layer-panel'" in svg_resp.text
    assert "dx='120'" in svg_resp.text


async def test_override_inheritance(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    _stub_renderer(monkeypatch)
    
    tenant_id, token = await _create_tenant(client, name="Mimik", slug="mimik")
    _client_id, job_id, first_id = await _create_creative(
        client, token=token, suffix="inheritance"
    )

    # Revise 1 sets panel dx
    revised1 = await client.post(
        f"/creatives/{first_id}/revise",
        json={
            "layer_ops": [
                {"layer_id": "layer-panel", "dx": 120}
            ]
        },
        headers=_auth(token),
    )
    assert revised1.status_code == 201, revised1.text
    second_id = revised1.json()["creative"]["id"]

    # Revise 2 sets badge visible=False
    revised2 = await client.post(
        f"/creatives/{second_id}/revise",
        json={
            "layer_ops": [
                {"layer_id": "layer-badge", "visible": False}
            ]
        },
        headers=_auth(token),
    )
    assert revised2.status_code == 201, revised2.text
    creative3 = revised2.json()["creative"]
    
    # The new manifest should have BOTH overrides
    l1_params = creative3["manifest"]["layers"][0]["recipe"]["params"]
    overrides = l1_params.get("layer_overrides", {})
    assert "layer-panel" in overrides
    assert overrides["layer-panel"]["dx"] == 120
    assert "layer-badge" in overrides
    assert overrides["layer-badge"]["visible"] is False


async def test_fill_role_resolution(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    _stub_renderer(monkeypatch)
    
    tenant_id, token = await _create_tenant(client, name="Mimik", slug="mimik")
    _client_id, job_id, first_id = await _create_creative(
        client, token=token, suffix="fill"
    )

    # Valid role
    revised_valid = await client.post(
        f"/creatives/{first_id}/revise",
        json={
            "layer_ops": [
                {"layer_id": "layer-headline", "fill_role": "primary"}
            ]
        },
        headers=_auth(token),
    )
    assert revised_valid.status_code == 201, revised_valid.text
    creative = revised_valid.json()["creative"]
    l1_params = creative["manifest"]["layers"][0]["recipe"]["params"]
    overrides = l1_params.get("layer_overrides", {})
    assert overrides["layer-headline"]["fill"] == "#112233"

    # Unknown role
    revised_invalid = await client.post(
        f"/creatives/{first_id}/revise",
        json={
            "layer_ops": [
                {"layer_id": "layer-headline", "fill_role": "unknown-color"}
            ]
        },
        headers=_auth(token),
    )
    assert revised_invalid.status_code == 422
    assert "Unknown brand color role: unknown-color" in revised_invalid.text


async def test_bc_shim(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    _stub_renderer(monkeypatch)
    monkeypatch.setattr(
        creative_generation.copy_l0,
        "draft_copy",
        lambda *_args, **_kwargs: CopyBlock(headline="LLM Redraft"),
    )
    
    tenant_id, token = await _create_tenant(client, name="Mimik", slug="mimik")
    _client_id, job_id, first_id = await _create_creative(
        client, token=token, suffix="shim"
    )

    # Legacy payload
    revised = await client.post(
        f"/creatives/{first_id}/revise",
        json={
            "edits": {"headline": "Explicit headline", "sub": "Explicit subhead"},
            "instruction": "Make it bolder and larger",
        },
        headers=_auth(token),
    )

    assert revised.status_code == 201, revised.text
    creative = revised.json()["creative"]
    
    # Headline edit wins over the LLM redraft
    assert creative["manifest"]["copy_block"]["headline"] == "Explicit headline"
    assert creative["manifest"]["copy_block"]["subhead"] == "Explicit subhead"
    
    # The instruction deterministic keyword check still works (e.g., 'larger' -> subject_zoom=1.2)
    l1_params = creative["manifest"]["layers"][0]["recipe"]["params"]
    assert l1_params["subject_zoom"] == 1.2

