"""P3 acceptance gate: a job runs intake -> generate -> approve -> auto-archive end to end,
with REAL deterministic rendering (no fake render), producing a real PNG at the archive path
and a timestamped audit trail — zero manual upload.

Browser-gated (skips without chromium, like test_compositor). This is the integration proof
that the manifest re-renders deterministically at archive time.
"""

from __future__ import annotations

from conftest import superadmin_headers
from pathlib import Path

import pytest
from httpx import AsyncClient

from creative.render.compositor import browser_available, png_size

pytestmark = pytest.mark.skipif(not browser_available(), reason="playwright not installed")


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_intake_to_autoarchive_end_to_end(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Local archive under tmp; REAL renderer (no monkeypatch of default_render).
    monkeypatch.setenv("ARCHIVE_BACKEND", "local")
    archive_root = tmp_path / "_archive"
    monkeypatch.setenv("ARCHIVE_LOCAL_ROOT", str(archive_root))

    # --- intake ---
    owner = (await client.post("/tenants", json={"name": "Mimik", "slug": "mimik"}, headers=superadmin_headers())).json()[
        "access_token"
    ]
    client_id = (
        await client.post("/clients", json={"name": "RCD Central"}, headers=_auth(owner))
    ).json()["id"]
    brand_id = (
        await client.post(
            "/brands",
            json={
                "client_id": client_id,
                "name": "RCD",
                "slug": "rcd",
                "tokens": {"colors": [{"name": "primary", "hex": "#2E5BFF"},
                                      {"name": "accent", "hex": "#C6F135"}]},
            },
            headers=_auth(owner),
        )
    ).json()["id"]
    job_id = (
        await client.post(
            "/jobs",
            json={"brand_id": brand_id, "title": "August offer", "format_key": "ig_post"},
            headers=_auth(owner),
        )
    ).json()["id"]

    # --- generate (persist the creative manifest) ---
    creative = await client.post(
        f"/jobs/{job_id}/creatives",
        json={
            "template_key": "centered_hero",
            "copy_block": {"headline": "Smiles, made easy", "cta": "Book now"},
        },
        headers=_auth(owner),
    )
    assert creative.status_code == 201, creative.text
    cid = creative.json()["id"]

    # --- approve -> auto-archive (real render) ---
    resp = await client.post(
        "/approvals",
        json={"job_id": job_id, "creative_doc_id": cid, "action": "approve"},
        headers=_auth(owner),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["job"]["status"] == "archived"
    drive_path = body["delivery"]["drive_path"]
    assert drive_path.startswith("Mimik Clients/RCD-Central/")

    # --- the archived artifact is a real PNG at the ig_post size, no manual upload ---
    written = archive_root / drive_path
    assert written.exists(), f"nothing archived at {written}"
    png = written.read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert png_size(png) == (1080, 1080)

    # --- timestamped audit trail ---
    trail = (await client.get(f"/jobs/{job_id}/approvals", headers=_auth(owner))).json()
    assert len(trail["approvals"]) == 1
    assert trail["approvals"][0]["action"] == "approve"
    assert trail["approvals"][0]["created_at"] is not None
    assert len(trail["deliveries"]) == 1
    assert trail["deliveries"][0]["delivered_at"] is not None
