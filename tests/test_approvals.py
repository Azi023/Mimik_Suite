"""Approval flow: the audited Approve / Request-change action from both entry points, and the
auto-archive procedure that fires on approval (zero manual upload).

Rendering is monkeypatched to fixed bytes so the whole API flow runs browser-free; a separate
browser-gated test in test_pipeline covers real deterministic re-render. The archive writes to
a tmp local root.
"""

from __future__ import annotations

from conftest import superadmin_headers
from pathlib import Path

import pytest
from httpx import AsyncClient

from api.services import approval_flow


@pytest.fixture(autouse=True)
def _fixed_render_and_local_archive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """No browser: the archive renderer returns fixed bytes; archive writes under tmp."""

    async def _fake_render(session, tenant_id, doc):
        return b"\x89PNG\r\n\x1a\nFAKE-RENDER-BYTES"

    monkeypatch.setattr(approval_flow, "default_render", _fake_render)
    monkeypatch.setenv("ARCHIVE_BACKEND", "local")
    monkeypatch.setenv("ARCHIVE_LOCAL_ROOT", str(tmp_path / "_archive"))
    return tmp_path


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _setup_job_with_creative(client: AsyncClient) -> tuple[str, str, str, str]:
    """Bootstrap tenant → client → brand → job → creative. Returns (owner_token, client_id,
    job_id, creative_doc_id)."""
    owner = (await client.post("/tenants", json={"name": "Mimik", "slug": "mimik"}, headers=superadmin_headers())).json()[
        "access_token"
    ]
    client_id = (
        await client.post("/clients", json={"name": "RCD Central"}, headers=_auth(owner))
    ).json()["id"]
    brand_id = (
        await client.post(
            "/brands",
            json={"client_id": client_id, "name": "RCD", "slug": "rcd"},
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
    creative = await client.post(
        f"/jobs/{job_id}/creatives",
        json={
            "template_key": "centered_hero",
            "copy_block": {"headline": "Smiles, made easy", "cta": "Book now"},
        },
        headers=_auth(owner),
    )
    assert creative.status_code == 201, creative.text
    return owner, client_id, job_id, creative.json()["id"]


async def test_creating_a_creative_moves_job_to_internal_review(client: AsyncClient) -> None:
    owner, _client_id, job_id, _cid = await _setup_job_with_creative(client)
    job = (await client.get(f"/jobs/{job_id}", headers=_auth(owner))).json()
    assert job["status"] == "internal_review"


async def test_approve_archives_and_records_audit_trail(client: AsyncClient) -> None:
    owner, _client_id, job_id, cid = await _setup_job_with_creative(client)

    resp = await client.post(
        "/approvals",
        json={"job_id": job_id, "creative_doc_id": cid, "action": "approve"},
        headers=_auth(owner),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["job"]["status"] == "archived"
    assert body["delivery"]["drive_path"].startswith("Mimik Clients/RCD-Central/")

    # Audit trail: one approval + one delivery, both timestamped.
    trail = (await client.get(f"/jobs/{job_id}/approvals", headers=_auth(owner))).json()
    assert len(trail["approvals"]) == 1
    assert trail["approvals"][0]["action"] == "approve"
    assert trail["approvals"][0]["created_at"] is not None
    assert len(trail["deliveries"]) == 1


async def test_request_change_opens_task_and_returns_to_internal_review(
    client: AsyncClient,
) -> None:
    owner, _client_id, job_id, cid = await _setup_job_with_creative(client)
    resp = await client.post(
        "/approvals",
        json={
            "job_id": job_id,
            "creative_doc_id": cid,
            "action": "request_change",
            "note": "warmer tone, bigger logo",
        },
        headers=_auth(owner),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["job"]["status"] == "internal_review"
    assert body["task"]["type"] == "change_request"
    assert body["task"]["detail"] == "warmer tone, bigger logo"


async def test_magic_link_approval_without_login(client: AsyncClient) -> None:
    owner, _client_id, job_id, _cid = await _setup_job_with_creative(client)
    # A team member mints a magic link for the job.
    minted = await client.post(
        f"/jobs/{job_id}/magic-link", json={}, headers=_auth(owner)
    )
    assert minted.status_code == 200, minted.text
    token = minted.json()["token"]

    # The client approves via the link — no auth header at all.
    resp = await client.post("/approvals/magic", json={"token": token, "action": "approve"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["job"]["status"] == "archived"
    # The action is attributed to the client actor.
    assert resp.json()["approval"]["actor"]["role"] == "client"


async def test_magic_link_rejects_tampered_token(client: AsyncClient) -> None:
    resp = await client.post(
        "/approvals/magic", json={"token": "not.a.real.token", "action": "approve"}
    )
    assert resp.status_code == 401


async def test_latest_creative_used_when_id_omitted(client: AsyncClient) -> None:
    owner, _client_id, job_id, _cid = await _setup_job_with_creative(client)
    resp = await client.post(
        "/approvals", json={"job_id": job_id, "action": "approve"}, headers=_auth(owner)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["job"]["status"] == "archived"


async def test_approval_on_foreign_job_is_404(client: AsyncClient) -> None:
    _owner_a, _cid_a, job_a, creative_a = await _setup_job_with_creative(client)
    owner_b = (await client.post("/tenants", json={"name": "B", "slug": "b"}, headers=superadmin_headers())).json()[
        "access_token"
    ]
    # Tenant B cannot approve tenant A's job even with the real ids.
    resp = await client.post(
        "/approvals",
        json={"job_id": job_a, "creative_doc_id": creative_a, "action": "approve"},
        headers=_auth(owner_b),
    )
    assert resp.status_code == 404


async def test_double_approve_does_not_re_archive(client: AsyncClient) -> None:
    # A stale magic link (or a double submit) must NOT re-fire archive/delivery on a done job.
    owner, _client_id, job_id, cid = await _setup_job_with_creative(client)
    first = await client.post(
        "/approvals",
        json={"job_id": job_id, "creative_doc_id": cid, "action": "approve"},
        headers=_auth(owner),
    )
    assert first.status_code == 200
    second = await client.post(
        "/approvals",
        json={"job_id": job_id, "creative_doc_id": cid, "action": "approve"},
        headers=_auth(owner),
    )
    assert second.status_code == 409  # already archived — a change now is a new request
    # Exactly ONE delivery survived — no duplicate archive.
    trail = (await client.get(f"/jobs/{job_id}/approvals", headers=_auth(owner))).json()
    assert len(trail["deliveries"]) == 1


async def test_stale_magic_link_cannot_demote_archived_job(client: AsyncClient) -> None:
    owner, _client_id, job_id, _cid = await _setup_job_with_creative(client)
    token = (await client.post(f"/jobs/{job_id}/magic-link", json={}, headers=_auth(owner))).json()[
        "token"
    ]
    assert (await client.post("/approvals/magic", json={"token": token, "action": "approve"})).status_code == 200
    # The same still-valid link cannot request-change the already-archived job back to review.
    demote = await client.post(
        "/approvals/magic", json={"token": token, "action": "request_change", "note": "late"}
    )
    assert demote.status_code == 409
