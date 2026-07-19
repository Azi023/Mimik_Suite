"""P4 ACCEPTANCE GATE — the learning loop's guarantees, end to end.

Three properties are asserted:
1. Real actions become signals — an approval records an `approval` signal; a request_change
   records a `rejection` signal; an explicit pick/edit is recorded via the POST endpoint.
2. Once a client crosses RANKER_MIN_SIGNALS (20), the taste-ranker re-orders variants toward
   the learned favourite.
3. Client corrections NEVER auto-promote to the SHARED golden set — the auto path writes
   nothing; an explicit client-sourced promote() writes nothing; only a TEAM-sourced candidate
   WITH a reviewer produces a golden file (the human gate).

All golden writes are redirected to a tmp dir via MIMIK_GOLDEN_DIR — the real golden/ is never
touched. The archive renderer is stubbed so approval runs browser-free.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from api.services import approval_flow
from mimik_knowledge import PromotionCandidate, promote, promote_and_write


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _stub_render_and_local_archive(monkeypatch, tmp_path):
    """Approval fires the archive procedure, which renders via Playwright. Stub the renderer so
    the gate runs without a browser; the local archive writes under tmp (never the repo)."""

    async def _fake_render(session, tenant_id, doc) -> bytes:
        return b"\x89PNG\r\n\x1a\nFAKE-RENDER-BYTES"

    monkeypatch.setattr(approval_flow, "default_render", _fake_render)
    monkeypatch.setenv("ARCHIVE_BACKEND", "local")
    monkeypatch.setenv("ARCHIVE_LOCAL_ROOT", str(tmp_path / "_archive"))


async def _new_tenant(client: AsyncClient) -> str:
    resp = await client.post("/tenants", json={"name": "Mimik", "slug": "mimik"})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def _new_client(client: AsyncClient, token: str, name: str = "ACME") -> str:
    resp = await client.post("/clients", json={"name": name}, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _new_job_with_creative(
    client: AsyncClient, token: str, cid: str, *, title: str, template_key: str
) -> str:
    """Bootstrap brand -> job -> creative for a client; return the job_id."""
    brand_id = (
        await client.post(
            "/brands",
            json={"client_id": cid, "name": f"{title} brand", "slug": f"{title}-brand"},
            headers=_auth(token),
        )
    ).json()["id"]
    job_id = (
        await client.post(
            "/jobs",
            json={"brand_id": brand_id, "title": title, "format_key": "ig_post"},
            headers=_auth(token),
        )
    ).json()["id"]
    created = await client.post(
        f"/jobs/{job_id}/creatives",
        json={"template_key": template_key, "copy_block": {"headline": "x"}},
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    return job_id


# --- 1. real actions become signals ----------------------------------------------------


async def test_approval_and_rejection_become_signals(client: AsyncClient) -> None:
    token = await _new_tenant(client)
    cid = await _new_client(client, token)

    # Approve one job -> records an `approval` signal.
    approved_job = await _new_job_with_creative(
        client, token, cid, title="approved", template_key="centered_hero"
    )
    approve = await client.post(
        "/approvals",
        json={"job_id": approved_job, "action": "approve", "note": "looks great"},
        headers=_auth(token),
    )
    assert approve.status_code == 200, approve.text

    # Request a change on another job -> records a `rejection` signal with a reason_tag.
    reject_job = await _new_job_with_creative(
        client, token, cid, title="rejected", template_key="lower_band"
    )
    change = await client.post(
        "/approvals",
        json={
            "job_id": reject_job,
            "action": "request_change",
            "note": "logo too small",
            "reason_tag": "logo_small",
        },
        headers=_auth(token),
    )
    assert change.status_code == 200, change.text

    # An explicit pick via the preferences endpoint.
    pick = await client.post(
        f"/clients/{cid}/preferences",
        json={"source": "pick", "attributes": {"template_key": "centered_hero"}},
        headers=_auth(token),
    )
    assert pick.status_code == 201, pick.text

    # The profile now carries all three signal sources.
    profile = await client.get(f"/clients/{cid}/preferences/profile", headers=_auth(token))
    assert profile.status_code == 200, profile.text
    data = profile.json()
    assert data["signal_count"] >= 3
    sources = {s["source"] for s in data["profile"]["signals"]}
    assert {"approval", "rejection", "pick"} <= sources
    # The rejection carried its reason tag.
    reasons = {s["reason_tag"] for s in data["profile"]["signals"] if s["reason_tag"]}
    assert "logo_small" in reasons


# --- 2. >=20 signals -> re-ranked ------------------------------------------------------


async def test_twenty_signals_reranks(client: AsyncClient) -> None:
    token = await _new_tenant(client)
    cid = await _new_client(client, token)
    for _ in range(20):
        r = await client.post(
            f"/clients/{cid}/preferences",
            json={"source": "approval", "attributes": {"template_key": "lower_band"}},
            headers=_auth(token),
        )
        assert r.status_code == 201, r.text

    ranked = await client.post(
        f"/clients/{cid}/preferences/rank",
        json={
            "variants": [
                {"id": "hero", "attributes": {"template_key": "centered_hero"}},
                {"id": "band", "attributes": {"template_key": "lower_band"}},
            ]
        },
        headers=_auth(token),
    )
    assert ranked.status_code == 200, ranked.text
    result = ranked.json()
    assert result["ranker_active"] is True
    assert result["ranked"][0]["id"] == "band"


# --- 3. client corrections NEVER auto-promote to the shared golden set ------------------


async def test_client_corrections_never_reach_golden_set(
    client: AsyncClient, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("MIMIK_GOLDEN_DIR", str(tmp_path))
    # The tmp golden dir starts empty.
    assert list(tmp_path.rglob("*.md")) == []

    token = await _new_tenant(client)
    cid = await _new_client(client, token)

    # Record several CLIENT signals and do client-style approvals/rejections via the endpoint.
    for source in ("pick", "edit", "rejection", "approval"):
        r = await client.post(
            f"/clients/{cid}/preferences",
            json={"source": source, "attributes": {"template_key": "lower_band"}},
            headers=_auth(token),
        )
        assert r.status_code == 201, r.text

    # A real client approval through the approval flow (records an approval signal).
    approved_job = await _new_job_with_creative(
        client, token, cid, title="clientapproved", template_key="lower_band"
    )
    approve = await client.post(
        "/approvals",
        json={"job_id": approved_job, "action": "approve", "note": "ok"},
        headers=_auth(token),
    )
    assert approve.status_code == 200, approve.text

    # None of that auto-wrote to the shared golden set.
    assert list(tmp_path.rglob("*.md")) == [], "signals must never auto-write to golden/"

    # An explicit promote() of a CLIENT-sourced candidate also writes nothing.
    client_candidate = PromotionCandidate(
        source_role="client",
        kind="golden_negative",
        content="client: make the logo bigger",
        client_id=cid,
    )
    client_result = promote_and_write(
        client_candidate, reviewer="atheeque", golden_dir=str(tmp_path)
    )
    assert client_result.accepted is False
    assert client_result.written_to == []
    assert list(tmp_path.rglob("*.md")) == []
    # promote() policy alone rejects the client source too.
    assert promote(client_candidate).accepted is False

    # A TEAM-sourced candidate WITH a reviewer DOES write exactly one golden file (human gate).
    team_candidate = PromotionCandidate(
        source_role="team",
        kind="golden_positive",
        content="the winning hero exemplar",
        client_id=cid,
    )
    team_result = promote_and_write(
        team_candidate, reviewer="atheeque", golden_dir=str(tmp_path)
    )
    assert team_result.accepted is True
    assert len(team_result.written_to) == 1
    written = list(tmp_path.rglob("*.md"))
    assert len(written) == 1
    body = written[0].read_text(encoding="utf-8")
    assert "the winning hero exemplar" in body
    # The provenance/audit header records who promoted it and from which client's context.
    assert "promoted-by: atheeque" in body
    assert "source_role: team" in body


async def test_team_candidate_without_reviewer_writes_nothing(tmp_path) -> None:
    """The reviewer is the human in the loop: an accepted candidate with NO reviewer still
    writes nothing — acceptance is necessary but not sufficient, a human must sign off."""
    candidate = PromotionCandidate(
        source_role="team",
        kind="golden_positive",
        content="accepted but unreviewed",
        client_id="c1",
    )
    result = promote_and_write(candidate, reviewer=None, golden_dir=str(tmp_path))
    assert result.accepted is True
    assert result.written_to == []
    assert list(tmp_path.rglob("*.md")) == []
