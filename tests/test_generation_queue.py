"""Durable generation queue, job attachment, and single-task worker lifecycle."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from conftest import superadmin_headers
from fastapi import HTTPException
from httpx import AsyncClient
from mimik_contracts import (
    CopyBlock,
    GenerationQueueItem,
    JobStatus,
    QueueStats,
    TaskStatus,
    TaskType,
    UsageReport,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables on Base.metadata)
from api.core.auth import Principal
from api.db import repo
from api.db.base import Base
from api.services import creative_generation
from api.services.creative_generation import GenerateCreativeRequest
from api.services.generation_queue import enqueue_generation, list_queue, queue_stats
from api.services.generation_worker import process_one_generation_task
from creative.adapters import ImageRequest
from creative.qa.checks import QAReport


@pytest_asyncio.fixture
async def sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def _seed_client(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    suffix: str,
) -> tuple[Principal, str, str]:
    async with sessionmaker() as session:
        tenant = await repo.create_tenant(
            session,
            name=f"Tenant {suffix}",
            slug=f"tenant-{suffix}",
        )
        client = await repo.create_client(
            session,
            tenant_id=tenant.id,
            name=f"Client {suffix}",
            industry="Consulting",
        )
        brand = await repo.create_brand(
            session,
            tenant_id=tenant.id,
            client_id=client.id,
            name=f"Brand {suffix}",
            slug=f"brand-{suffix}",
            tokens={
                "colors": [
                    {"name": "primary", "hex": "#112233"},
                    {"name": "ground", "hex": "#FFFFFF"},
                ]
            },
        )
        await session.commit()
    return (
        Principal(
            tenant_id=tenant.id,
            role="owner",
            user_id=f"owner-{suffix}",
        ),
        client.id,
        brand.id,
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _bootstrap_route_tenant(
    client: AsyncClient,
    *,
    suffix: str,
) -> tuple[str, str, str, str]:
    tenant_response = await client.post(
        "/tenants",
        json={"name": f"Route tenant {suffix}", "slug": f"route-tenant-{suffix}"},
        headers=superadmin_headers(),
    )
    assert tenant_response.status_code == 201, tenant_response.text
    payload = tenant_response.json()
    tenant_id = payload["tenant"]["id"]
    owner_token = payload["access_token"]
    client_response = await client.post(
        "/clients",
        json={"name": f"Route client {suffix}", "industry": "Consulting"},
        headers=_auth(owner_token),
    )
    assert client_response.status_code == 201, client_response.text
    client_id = client_response.json()["id"]
    brand_response = await client.post(
        "/brands",
        json={
            "client_id": client_id,
            "name": f"Route brand {suffix}",
            "slug": f"route-brand-{suffix}",
            "tokens": {
                "colors": [
                    {"name": "primary", "hex": "#112233"},
                    {"name": "ground", "hex": "#FFFFFF"},
                ]
            },
        },
        headers=_auth(owner_token),
    )
    assert brand_response.status_code == 201, brand_response.text
    return tenant_id, owner_token, client_id, brand_response.json()["id"]


def _stub_generation_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_source: bool = False,
) -> None:
    def fake_art_direction(
        *_args: object,
        **_kwargs: object,
    ) -> ImageRequest:
        return ImageRequest(
            prompt="Stub image",
            width=1080,
            height=1080,
            params={"template_key": "centered_hero"},
        )

    async def fake_source_image(
        **kwargs: object,
    ) -> tuple[Path, list[str], str]:
        if fail_source:
            raise RuntimeError("stub generation failure")
        destination_dir = kwargs["destination_dir"]
        assert isinstance(destination_dir, Path)
        image_path = destination_dir / "source.png"
        image_path.write_bytes(b"source")
        return image_path, [], "stub"

    def fake_copy(*_args: object, **_kwargs: object) -> CopyBlock:
        return CopyBlock(
            headline="Queued headline",
            subhead="Queued subhead",
            cta="Review",
            source_model="test",
        )

    async def fake_render(
        **kwargs: object,
    ) -> tuple[Path, Path, None, QAReport]:
        artifact_dir = kwargs["artifact_dir"]
        assert isinstance(artifact_dir, Path)
        svg_path = artifact_dir / "creative.svg"
        preview_path = artifact_dir / "preview.png"
        svg_path.write_text("<svg data-queue-test='true'/>", encoding="utf-8")
        preview_path.write_bytes(b"preview")
        return svg_path, preview_path, None, QAReport(passed=True, failures=[])

    monkeypatch.setattr(
        creative_generation.art_direction,
        "build_image_request",
        fake_art_direction,
    )
    monkeypatch.setattr(creative_generation, "_source_image", fake_source_image)
    monkeypatch.setattr(creative_generation.copy_l0, "draft_copy", fake_copy)
    monkeypatch.setattr(creative_generation, "_render_creative_artifacts", fake_render)


async def test_enqueue_creates_draft_job_and_open_generation_task(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    principal, client_id, brand_id = await _seed_client(sessionmaker, suffix="enqueue")

    async with sessionmaker() as session:
        item = await enqueue_generation(
            session,
            principal=principal,
            client_id=client_id,
            topic="  Launch   strategy  ",
            pillar="Education",
            format_key="ig_post",
        )

    assert isinstance(item, GenerationQueueItem)
    assert GenerationQueueItem.model_validate(item.model_dump()) == item
    assert item.client_id == client_id
    assert item.topic == "Launch strategy"
    assert item.pillar == "Education"
    assert item.format_key == "ig_post"
    assert item.status is TaskStatus.OPEN
    assert item.requested_by.id == principal.user_id

    async with sessionmaker() as session:
        job = await repo.get_job(
            session,
            tenant_id=principal.tenant_id,
            job_id=item.job_id,
        )
        task = await repo.get_task(
            session,
            tenant_id=principal.tenant_id,
            task_id=item.id,
        )

    assert job is not None
    assert job.status == JobStatus.DRAFT.value
    assert job.client_id == client_id
    assert job.brand_id == brand_id
    assert job.title == "Launch strategy"
    assert task is not None
    assert task.type == TaskType.GENERATION.value
    assert task.status == TaskStatus.OPEN.value
    assert task.job_id == job.id
    assert json.loads(task.detail or "{}") == {
        "topic": "Launch strategy",
        "pillar": "Education",
        "format_key": "ig_post",
    }


async def test_worker_drains_task_into_same_job_and_creative(
    sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_generation_pipeline(monkeypatch)
    principal, client_id, _brand_id = await _seed_client(sessionmaker, suffix="happy")
    async with sessionmaker() as session:
        queued = await enqueue_generation(
            session,
            principal=principal,
            client_id=client_id,
            topic="Worker happy path",
            pillar=None,
            format_key="ig_post",
        )

    assert await process_one_generation_task(sessionmaker) is True
    assert await process_one_generation_task(sessionmaker) is False

    async with sessionmaker() as session:
        task = await repo.get_task(
            session,
            tenant_id=principal.tenant_id,
            task_id=queued.id,
        )
        job = await repo.get_job(
            session,
            tenant_id=principal.tenant_id,
            job_id=queued.job_id,
        )
        creatives = await repo.list_creative_versions(
            session,
            tenant_id=principal.tenant_id,
            job_id=queued.job_id,
        )

    assert task is not None
    assert task.status == TaskStatus.DONE.value
    assert job is not None
    assert job.status == JobStatus.INTERNAL_REVIEW.value
    assert job.generation_started_at is None
    assert len(creatives) == 1
    assert creatives[0].job_id == queued.job_id


async def test_worker_failure_marks_task_done_with_error_and_job_blocked(
    sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_generation_pipeline(monkeypatch, fail_source=True)
    principal, client_id, _brand_id = await _seed_client(sessionmaker, suffix="failure")
    async with sessionmaker() as session:
        queued = await enqueue_generation(
            session,
            principal=principal,
            client_id=client_id,
            topic="Worker failure path",
            pillar="Promotion",
            format_key="ig_post",
        )

    assert await process_one_generation_task(sessionmaker) is True

    async with sessionmaker() as session:
        task = await repo.get_task(
            session,
            tenant_id=principal.tenant_id,
            task_id=queued.id,
        )
        job = await repo.get_job(
            session,
            tenant_id=principal.tenant_id,
            job_id=queued.job_id,
        )
        stats = await queue_stats(session, tenant_id=principal.tenant_id)

    assert task is not None
    assert task.status == TaskStatus.DONE.value
    error = json.loads(task.detail or "{}").get("error")
    assert isinstance(error, str)
    assert error
    assert len(error) <= 500
    assert job is not None
    assert job.status == JobStatus.BLOCKED.value
    assert job.generation_started_at is None
    assert stats == QueueStats(
        pending=0,
        in_progress=0,
        done_today=0,
        failed_today=1,
    )


async def test_generate_with_job_id_reuses_job_and_none_creates_one(
    sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_generation_pipeline(monkeypatch)
    principal, client_id, brand_id = await _seed_client(sessionmaker, suffix="attach")
    async with sessionmaker() as session:
        existing = await repo.create_job(
            session,
            tenant_id=principal.tenant_id,
            client_id=client_id,
            brand_id=brand_id,
            title="Attached job",
            format_key="ig_post",
            status=JobStatus.DRAFT.value,
        )
        await session.commit()
        attached = await creative_generation.generate_client_creative(
            session,
            principal=principal,
            client_id=client_id,
            body=GenerateCreativeRequest(
                topic="Attached generation",
                pillar="Education",
                format_key="ig_post",
            ),
            job_id=existing.id,
        )
        jobs_after_attach = await repo.list_jobs(
            session,
            tenant_id=principal.tenant_id,
            client_id=client_id,
        )
        standalone = await creative_generation.generate_client_creative(
            session,
            principal=principal,
            client_id=client_id,
            body=GenerateCreativeRequest(
                topic="Standalone generation",
                format_key="ig_post",
            ),
        )
        jobs_after_standalone = await repo.list_jobs(
            session,
            tenant_id=principal.tenant_id,
            client_id=client_id,
        )

    assert attached.creative.job_id == existing.id
    assert [job.id for job in jobs_after_attach] == [existing.id]
    assert standalone.creative.job_id != existing.id
    assert len(jobs_after_standalone) == 2


async def test_queue_access_is_tenant_scoped_and_cross_tenant_enqueue_is_404(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    principal_a, client_a, _brand_a = await _seed_client(sessionmaker, suffix="scope-a")
    principal_b, client_b, _brand_b = await _seed_client(sessionmaker, suffix="scope-b")

    async with sessionmaker() as session:
        item_a = await enqueue_generation(
            session,
            principal=principal_a,
            client_id=client_a,
            topic="Tenant A",
            pillar=None,
            format_key="ig_post",
        )
        item_b = await enqueue_generation(
            session,
            principal=principal_b,
            client_id=client_b,
            topic="Tenant B",
            pillar=None,
            format_key="ig_story",
        )

        with pytest.raises(HTTPException) as exc_info:
            await enqueue_generation(
                session,
                principal=principal_a,
                client_id=client_b,
                topic="Cross tenant",
                pillar=None,
                format_key="ig_post",
            )

        queue_a = await list_queue(session, tenant_id=principal_a.tenant_id)
        queue_b = await list_queue(session, tenant_id=principal_b.tenant_id)
        stats_a = await queue_stats(session, tenant_id=principal_a.tenant_id)
        stats_b = await queue_stats(session, tenant_id=principal_b.tenant_id)

    assert exc_info.value.status_code == 404
    assert [item.id for item in queue_a] == [item_a.id]
    assert [item.id for item in queue_b] == [item_b.id]
    assert stats_a == QueueStats(pending=1, in_progress=0, done_today=0, failed_today=0)
    assert stats_b == QueueStats(pending=1, in_progress=0, done_today=0, failed_today=0)


async def test_synchronous_generate_endpoint_remains_unchanged(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_generation_pipeline(monkeypatch)
    owner = (
        await client.post(
            "/tenants",
            json={"name": "Sync tenant", "slug": "sync-tenant"},
            headers=superadmin_headers(),
        )
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {owner}"}
    client_id = (
        await client.post(
            "/clients",
            json={"name": "Sync client", "industry": "Consulting"},
            headers=headers,
        )
    ).json()["id"]
    brand_response = await client.post(
        "/brands",
        json={
            "client_id": client_id,
            "name": "Sync brand",
            "slug": "sync-brand",
            "tokens": {
                "colors": [
                    {"name": "primary", "hex": "#112233"},
                    {"name": "ground", "hex": "#FFFFFF"},
                ]
            },
        },
        headers=headers,
    )
    assert brand_response.status_code == 201, brand_response.text

    response = await client.post(
        f"/clients/{client_id}/creatives:generate",
        json={
            "topic": "Synchronous request",
            "pillar": "Education",
            "format_key": "ig_post",
        },
        headers=headers,
    )
    jobs = await client.get(f"/jobs?client_id={client_id}", headers=headers)

    assert response.status_code == 200, response.text
    assert jobs.status_code == 200, jobs.text
    assert len(jobs.json()) == 1
    assert jobs.json()[0]["id"] == response.json()["creative"]["job_id"]
    assert jobs.json()[0]["status"] == JobStatus.INTERNAL_REVIEW.value


async def test_ops_queue_routes_enqueue_list_and_report_stats(client: AsyncClient) -> None:
    _tenant_id, owner_token, client_id, _brand_id = await _bootstrap_route_tenant(
        client,
        suffix="queue",
    )

    enqueue_response = await client.post(
        "/ops/queue",
        json={
            "client_id": client_id,
            "topic": "Route queue request",
            "pillar": "Education",
            "format_key": "ig_post",
        },
        headers=_auth(owner_token),
    )
    assert enqueue_response.status_code == 201, enqueue_response.text
    queued = GenerationQueueItem.model_validate(enqueue_response.json())

    list_response = await client.get("/ops/queue", headers=_auth(owner_token))
    stats_response = await client.get("/ops/queue/stats", headers=_auth(owner_token))

    assert list_response.status_code == 200, list_response.text
    listed = [GenerationQueueItem.model_validate(item) for item in list_response.json()]
    assert [item.id for item in listed] == [queued.id]
    assert listed[0].job_id == queued.job_id
    assert listed[0].client_id == client_id
    assert listed[0].topic == "Route queue request"

    assert stats_response.status_code == 200, stats_response.text
    assert QueueStats.model_validate(stats_response.json()) == QueueStats(
        pending=1,
        in_progress=0,
        done_today=0,
        failed_today=0,
    )


async def test_ops_queue_accepts_admin_as_team_role(client: AsyncClient) -> None:
    from api.core.security import create_access_token

    tenant_id, _owner_token, client_id, _brand_id = await _bootstrap_route_tenant(
        client,
        suffix="admin",
    )
    admin_token = create_access_token(tenant_id=tenant_id, role="admin")

    response = await client.post(
        "/ops/queue",
        json={"client_id": client_id, "topic": "Admin request"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 201, response.text
    assert GenerationQueueItem.model_validate(response.json()).client_id == client_id


async def test_ops_queue_and_usage_routes_forbid_client_role(client: AsyncClient) -> None:
    from api.core.security import create_access_token

    tenant_id, _owner_token, client_id, _brand_id = await _bootstrap_route_tenant(
        client,
        suffix="client-role",
    )
    client_token = create_access_token(tenant_id=tenant_id, role="client")
    headers = _auth(client_token)

    responses = [
        await client.post(
            "/ops/queue",
            json={"client_id": client_id, "topic": "Forbidden request"},
            headers=headers,
        ),
        await client.get("/ops/queue", headers=headers),
        await client.get("/ops/queue/stats", headers=headers),
        await client.get("/ops/usage", headers=headers),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403, 403]


async def test_ops_queue_cross_tenant_enqueue_is_404(client: AsyncClient) -> None:
    _tenant_a, owner_a, _client_a, _brand_a = await _bootstrap_route_tenant(
        client,
        suffix="scope-a",
    )
    _tenant_b, _owner_b, client_b, _brand_b = await _bootstrap_route_tenant(
        client,
        suffix="scope-b",
    )

    response = await client.post(
        "/ops/queue",
        json={"client_id": client_b, "topic": "Cross-tenant request"},
        headers=_auth(owner_a),
    )

    assert response.status_code == 404


async def test_ops_usage_defaults_to_current_utc_month_and_rejects_reverse_window(
    client: AsyncClient,
) -> None:
    _tenant_id, owner_token, _client_id, brand_id = await _bootstrap_route_tenant(
        client,
        suffix="usage",
    )
    job_response = await client.post(
        "/jobs",
        json={
            "brand_id": brand_id,
            "title": "Usage route creative",
            "format_key": "ig_post",
        },
        headers=_auth(owner_token),
    )
    assert job_response.status_code == 201, job_response.text
    creative_response = await client.post(
        f"/jobs/{job_response.json()['id']}/creatives",
        json={
            "template_key": "centered_hero",
            "copy_block": {"headline": "Usage test", "cta": "Review"},
        },
        headers=_auth(owner_token),
    )
    assert creative_response.status_code == 201, creative_response.text

    before = datetime.now(timezone.utc)
    usage_response = await client.get("/ops/usage", headers=_auth(owner_token))
    after = datetime.now(timezone.utc)

    assert usage_response.status_code == 200, usage_response.text
    report = UsageReport.model_validate(usage_response.json())
    assert report.window_start == before.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    assert before <= report.window_end <= after
    assert report.renders == 1
    assert report.by_image_source == {"unknown": 1}
    assert report.by_profile == {"unknown": 1}

    reverse_response = await client.get(
        "/ops/usage",
        params={
            "start": (after + timedelta(days=1)).isoformat(),
            "end": after.isoformat(),
        },
        headers=_auth(owner_token),
    )
    assert reverse_response.status_code == 422
