"""Ops board + calendar + job status-transitions.

The →Approved transition is monkeypatched browser-free exactly like test_approvals: the archive
renderer returns fixed bytes and the archive writes under a tmp local root. Tenant isolation is
asserted the same way it is everywhere else — a foreign tenant's job is a 404, not a 403.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


async def _bootstrap(client: AsyncClient, *, slug: str = "mimik") -> tuple[str, str, str]:
    """Bootstrap tenant → client → brand. Returns (owner_token, client_id, brand_id)."""
    owner = (
        await client.post("/tenants", json={"name": slug, "slug": slug})
    ).json()["access_token"]
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
    return owner, client_id, brand_id


async def _make_job(
    client: AsyncClient,
    owner: str,
    brand_id: str,
    *,
    title: str = "August offer",
    publish_date: str | None = None,
    approval_lead_days: int = 3,
) -> str:
    body: dict = {"brand_id": brand_id, "title": title, "format_key": "ig_post"}
    if publish_date is not None:
        body["publish_date"] = publish_date
    body["approval_lead_days"] = approval_lead_days
    return (await client.post("/jobs", json=body, headers=_auth(owner))).json()["id"]


async def _add_creative(client: AsyncClient, owner: str, job_id: str) -> str:
    resp = await client.post(
        f"/jobs/{job_id}/creatives",
        json={
            "template_key": "centered_hero",
            "copy_block": {"headline": "Smiles, made easy", "cta": "Book now"},
        },
        headers=_auth(owner),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_board_groups_jobs_by_status_with_all_columns(client: AsyncClient) -> None:
    owner, _client_id, brand_id = await _bootstrap(client)
    draft_job = await _make_job(client, owner, brand_id, title="Draft one")
    review_job = await _make_job(client, owner, brand_id, title="In review")
    await _add_creative(client, owner, review_job)  # -> internal_review

    board = (await client.get("/ops/board", headers=_auth(owner))).json()
    columns = board["columns"]

    # Every JobStatus is present as a stable column, even when empty.
    assert list(columns.keys()) == [
        "draft",
        "generating",
        "internal_review",
        "client_review",
        "approved",
        "delivered",
        "archived",
        "blocked",
    ]
    draft_ids = [c["job"]["id"] for c in columns["draft"]]
    review_ids = [c["job"]["id"] for c in columns["internal_review"]]
    assert draft_job in draft_ids
    assert review_job in review_ids
    # Cards carry an at_risk flag.
    assert all("at_risk" in card for card in columns["draft"])


async def test_board_at_risk_flag_true_when_buffer_breached_and_false_once_approved(
    client: AsyncClient,
) -> None:
    owner, _client_id, brand_id = await _bootstrap(client)
    # publish_date already passed -> approve_by is in the past -> at risk while unapproved.
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    job_id = await _make_job(
        client, owner, brand_id, title="Breached", publish_date=past, approval_lead_days=3
    )
    await _add_creative(client, owner, job_id)  # internal_review, unapproved

    board = (await client.get("/ops/board", headers=_auth(owner))).json()
    card = next(
        c for c in board["columns"]["internal_review"] if c["job"]["id"] == job_id
    )
    assert card["at_risk"] is True

    # Approve it (fires archive) — an archived job is never at risk.
    resp = await client.post(
        "/approvals", json={"job_id": job_id, "action": "approve"}, headers=_auth(owner)
    )
    assert resp.status_code == 200, resp.text
    board2 = (await client.get("/ops/board", headers=_auth(owner))).json()
    card2 = next(
        c for c in board2["columns"]["archived"] if c["job"]["id"] == job_id
    )
    assert card2["at_risk"] is False


async def test_calendar_returns_only_in_window_jobs(client: AsyncClient) -> None:
    owner, _client_id, brand_id = await _bootstrap(client)
    now = datetime.now(timezone.utc)
    in_window = await _make_job(
        client, owner, brand_id, title="Soon", publish_date=(now + timedelta(days=5)).isoformat()
    )
    out_window = await _make_job(
        client, owner, brand_id, title="Later", publish_date=(now + timedelta(days=99)).isoformat()
    )
    no_date = await _make_job(client, owner, brand_id, title="Unscheduled")

    resp = await client.get(
        "/ops/calendar",
        params={"start": now.isoformat(), "end": (now + timedelta(days=30)).isoformat()},
        headers=_auth(owner),
    )
    assert resp.status_code == 200, resp.text
    cards = resp.json()
    ids = [c["job"]["id"] for c in cards]
    assert in_window in ids
    assert out_window not in ids
    assert no_date not in ids  # no publish_date -> never on the calendar


async def test_calendar_rejects_start_after_end(client: AsyncClient) -> None:
    owner, _client_id, _brand_id = await _bootstrap(client)
    now = datetime.now(timezone.utc)
    resp = await client.get(
        "/ops/calendar",
        params={"start": (now + timedelta(days=10)).isoformat(), "end": now.isoformat()},
        headers=_auth(owner),
    )
    assert resp.status_code == 422


async def test_transition_happy_path_internal_to_client_review(client: AsyncClient) -> None:
    owner, _client_id, brand_id = await _bootstrap(client)
    job_id = await _make_job(client, owner, brand_id)
    await _add_creative(client, owner, job_id)  # -> internal_review

    resp = await client.post(
        f"/ops/jobs/{job_id}/transition",
        json={"to_status": "client_review"},
        headers=_auth(owner),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["job"]["status"] == "client_review"


async def test_transition_to_approved_fires_archive(client: AsyncClient) -> None:
    owner, _client_id, brand_id = await _bootstrap(client)
    job_id = await _make_job(client, owner, brand_id)
    await _add_creative(client, owner, job_id)
    # internal_review -> client_review -> approved (the only legal path to approved).
    await client.post(
        f"/ops/jobs/{job_id}/transition",
        json={"to_status": "client_review"},
        headers=_auth(owner),
    )
    resp = await client.post(
        f"/ops/jobs/{job_id}/transition",
        json={"to_status": "approved"},
        headers=_auth(owner),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The shared approval procedure ran: job archived + a Delivery exists.
    assert body["job"]["status"] == "archived"
    assert body["delivery"]["drive_path"].startswith("Mimik Clients/RCD-Central/")

    trail = (await client.get(f"/jobs/{job_id}/approvals", headers=_auth(owner))).json()
    assert len(trail["deliveries"]) == 1
    assert trail["approvals"][0]["action"] == "approve"


async def test_illegal_transition_is_409(client: AsyncClient) -> None:
    owner, _client_id, brand_id = await _bootstrap(client)
    job_id = await _make_job(client, owner, brand_id)  # draft
    # draft -> client_review is not a legal step.
    resp = await client.post(
        f"/ops/jobs/{job_id}/transition",
        json={"to_status": "client_review"},
        headers=_auth(owner),
    )
    assert resp.status_code == 409


async def test_transition_forbidden_for_client_role(client: AsyncClient) -> None:
    """A client-role principal is not a team member — transitions are team-only (403)."""
    from api.core.security import create_access_token

    owner, client_id, brand_id = await _bootstrap(client)
    job_id = await _make_job(client, owner, brand_id)
    # Mint a first-party token carrying the client role for the same tenant.
    tenant_id = (await client.get(f"/jobs/{job_id}", headers=_auth(owner))).json()["tenant_id"]
    client_token = create_access_token(tenant_id=tenant_id, role="client")
    resp = await client.post(
        f"/ops/jobs/{job_id}/transition",
        json={"to_status": "generating"},
        headers=_auth(client_token),
    )
    assert resp.status_code == 403


async def test_transition_on_foreign_tenant_job_is_404(client: AsyncClient) -> None:
    owner_a, _client_id, brand_id = await _bootstrap(client, slug="a")
    job_a = await _make_job(client, owner_a, brand_id)
    owner_b = (
        await client.post("/tenants", json={"name": "B", "slug": "b"})
    ).json()["access_token"]
    # Tenant B cannot move tenant A's job even with the real id.
    resp = await client.post(
        f"/ops/jobs/{job_a}/transition",
        json={"to_status": "generating"},
        headers=_auth(owner_b),
    )
    assert resp.status_code == 404
