"""Command Center NL parser + /ops/command endpoints (A-05 / M-09).

Covers the happy-path parse ("generate 5 Educational posts for Glo2Go this week"), the
unknown-client validation error, the operator team-gate, tenant scoping (a command can never
target another tenant's client — IDOR-negative), and the enqueue side-effect on execute.
"""

from __future__ import annotations

from datetime import date, timedelta

from conftest import superadmin_headers
from httpx import AsyncClient

from api.core.security import create_access_token
from mimik_contracts import CommandExecutionResult, CommandPlan, PRESETS


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _bootstrap(
    client: AsyncClient, *, slug: str, client_name: str = "Glo2Go"
) -> tuple[str, str, str]:
    """tenant → client → brand. Returns (owner_token, client_id, tenant_id). A brand is required
    — the queue path refuses to enqueue for a client that has no brand."""
    tenant_payload = (
        await client.post(
            "/tenants", json={"name": slug, "slug": slug}, headers=superadmin_headers()
        )
    ).json()
    owner = tenant_payload["access_token"]
    tenant_id = tenant_payload["tenant"]["id"]
    client_id = (
        await client.post("/clients", json={"name": client_name}, headers=_auth(owner))
    ).json()["id"]
    resp = await client.post(
        "/brands",
        json={"client_id": client_id, "name": client_name, "slug": f"{slug}-brand"},
        headers=_auth(owner),
    )
    assert resp.status_code == 201, resp.text
    return owner, client_id, tenant_id


async def test_preview_parses_full_command(client: AsyncClient) -> None:
    owner, client_id, _tenant = await _bootstrap(client, slug="g2g")
    resp = await client.post(
        "/ops/command",
        json={"text": "generate 5 Educational posts for Glo2Go this week"},
        headers=_auth(owner),
    )
    assert resp.status_code == 200, resp.text
    plan = CommandPlan.model_validate(resp.json())
    assert plan.intent == "generate_batch"
    assert plan.count == 5
    assert plan.pillar == "Educational"
    assert plan.client_id == client_id
    assert plan.client_name == "Glo2Go"
    assert plan.format_key == "ig_post"
    assert plan.format_key in PRESETS
    assert len(plan.topics) == 5
    # "this week" → Monday..Sunday of the current week.
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    assert plan.window_start == monday
    assert plan.window_end == monday + timedelta(days=6)


async def test_client_digit_in_name_not_read_as_count(client: AsyncClient) -> None:
    """The "2" inside "Glo2Go" must never be mistaken for the count."""
    owner, _client, _tenant = await _bootstrap(client, slug="g2g2")
    resp = await client.post(
        "/ops/command",
        json={"text": "generate 3 stories for Glo2Go"},
        headers=_auth(owner),
    )
    assert resp.status_code == 200, resp.text
    plan = CommandPlan.model_validate(resp.json())
    assert plan.count == 3
    assert plan.format_key == "ig_story"


async def test_unknown_client_is_422(client: AsyncClient) -> None:
    owner, _client, _tenant = await _bootstrap(client, slug="unk")
    resp = await client.post(
        "/ops/command",
        json={"text": "generate 4 posts for Nonexistent Brand this week"},
        headers=_auth(owner),
    )
    assert resp.status_code == 422, resp.text
    assert "Unknown client" in resp.json()["detail"]


async def test_missing_count_is_422(client: AsyncClient) -> None:
    owner, _client, _tenant = await _bootstrap(client, slug="nocount")
    resp = await client.post(
        "/ops/command",
        json={"text": "generate posts for Glo2Go"},
        headers=_auth(owner),
    )
    assert resp.status_code == 422, resp.text
    assert "how many" in resp.json()["detail"].lower()


async def test_count_over_20_is_422(client: AsyncClient) -> None:
    owner, _client, _tenant = await _bootstrap(client, slug="over20")
    resp = await client.post(
        "/ops/command",
        json={"text": "generate 50 posts for Glo2Go"},
        headers=_auth(owner),
    )
    assert resp.status_code == 422, resp.text


async def test_command_requires_team_role(client: AsyncClient) -> None:
    """A client-role principal (bounded portal) cannot drive the cockpit — 403, not a plan."""
    _owner, _client_id, tenant_id = await _bootstrap(client, slug="gate")
    client_token = create_access_token(tenant_id=tenant_id, role="client")
    resp = await client.post(
        "/ops/command",
        json={"text": "generate 2 posts for Glo2Go"},
        headers=_auth(client_token),
    )
    assert resp.status_code == 403, resp.text


async def test_cannot_target_another_tenants_client(client: AsyncClient) -> None:
    """IDOR-negative: tenant B names tenant A's client — it must not resolve (422), never
    silently enqueue against the foreign client."""
    _owner_a, _client_a, _tenant_a = await _bootstrap(client, slug="ten-a", client_name="Glo2Go")
    owner_b, _client_b, _tenant_b = await _bootstrap(client, slug="ten-b", client_name="OtherCo")
    resp = await client.post(
        "/ops/command",
        json={"text": "generate 2 posts for Glo2Go this week"},
        headers=_auth(owner_b),
    )
    assert resp.status_code == 422, resp.text
    assert "Unknown client" in resp.json()["detail"]


async def test_execute_enqueues_n_jobs(client: AsyncClient) -> None:
    owner, client_id, _tenant = await _bootstrap(client, slug="exec")
    resp = await client.post(
        "/ops/command/execute",
        json={"text": "generate 3 Educational posts for Glo2Go this week"},
        headers=_auth(owner),
    )
    assert resp.status_code == 201, resp.text
    result = CommandExecutionResult.model_validate(resp.json())
    assert len(result.queued) == 3
    for item in result.queued:
        assert item.client_id == client_id
        assert item.format_key == "ig_post"
        assert item.pillar == "Educational"
        assert item.requested_by.id  # audited actor stamped

    # Side-effect: the three jobs are visible on the tenant's queue.
    queue = (await client.get("/ops/queue", headers=_auth(owner))).json()
    assert len(queue) == 3
    topics = {row["topic"] for row in queue}
    assert topics == {"Educational post #1", "Educational post #2", "Educational post #3"}
