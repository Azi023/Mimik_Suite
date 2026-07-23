"""Single-concurrency worker for durable generation tasks."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from mimik_contracts import ActorRole, JobStatus, TaskStatus
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.core.auth import Principal
from api.db import repo
from api.services.creative_generation import GenerateCreativeRequest, generate_client_creative
from api.services.generation_queue import parse_generation_detail


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ClaimedTask:
    id: str
    tenant_id: str
    client_id: str
    job_id: str | None
    title: str
    detail: str | None


async def _claim_oldest_task(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> _ClaimedTask | None:
    async with sessionmaker() as session:
        tasks = await repo.list_open_generation_tasks(session)
        if not tasks:
            return None
        task = tasks[0]
        claimed = _ClaimedTask(
            id=task.id,
            tenant_id=task.tenant_id,
            client_id=task.client_id,
            job_id=task.job_id,
            title=task.title,
            detail=task.detail,
        )
        task.status = TaskStatus.IN_PROGRESS.value
        task.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return claimed


def _request_from_task(task: _ClaimedTask) -> GenerateCreativeRequest:
    payload = parse_generation_detail(task.detail)
    topic_value = payload.get("topic")
    topic = topic_value if isinstance(topic_value, str) and topic_value.strip() else task.title
    pillar_value = payload.get("pillar")
    pillar = pillar_value if isinstance(pillar_value, str) else None
    format_value = payload.get("format_key")
    if not isinstance(format_value, str) or not format_value:
        raise ValueError("Generation task is missing format_key")
    if task.job_id is None:
        raise ValueError("Generation task is missing job_id")
    return GenerateCreativeRequest(
        topic=topic,
        pillar=pillar,
        format_key=format_value,
    )


async def _mark_task_done(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    task: _ClaimedTask,
) -> None:
    async with sessionmaker() as session:
        row = await repo.get_task(
            session,
            tenant_id=task.tenant_id,
            task_id=task.id,
        )
        if row is None:
            raise RuntimeError(f"Claimed generation task {task.id} disappeared")
        row.status = TaskStatus.DONE.value
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()


async def _mark_task_failed(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    task: _ClaimedTask,
    error: str,
) -> None:
    async with sessionmaker() as session:
        row = await repo.get_task(
            session,
            tenant_id=task.tenant_id,
            task_id=task.id,
        )
        if row is None:
            raise RuntimeError(f"Claimed generation task {task.id} disappeared")
        detail = parse_generation_detail(row.detail)
        detail["error"] = error[:500]
        row.detail = json.dumps(detail)
        row.status = TaskStatus.DONE.value
        row.updated_at = datetime.now(timezone.utc)

        if task.job_id is not None:
            job = await repo.get_job(
                session,
                tenant_id=task.tenant_id,
                job_id=task.job_id,
            )
            if job is not None:
                job.status = JobStatus.BLOCKED.value
                job.generation_started_at = None
        await session.commit()


async def process_one_generation_task(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> bool:
    task = await _claim_oldest_task(sessionmaker)
    if task is None:
        return False

    try:
        body = _request_from_task(task)
        principal = Principal(
            tenant_id=task.tenant_id,
            role=ActorRole.TEAM.value,
            user_id=f"generation-worker:{task.id}",
            client_scopes=[task.client_id],
        )
        async with sessionmaker() as session:
            await generate_client_creative(
                session,
                principal=principal,
                client_id=task.client_id,
                body=body,
                job_id=task.job_id,
            )
        await _mark_task_done(sessionmaker, task=task)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning(
            "Generation task %s failed: %s",
            task.id,
            exc,
            exc_info=True,
        )
        await _mark_task_failed(
            sessionmaker,
            task=task,
            error=str(exc),
        )
    return True


async def run_worker(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    poll_interval: float = 1.5,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        processed = False
        try:
            processed = await process_one_generation_task(sessionmaker)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Generation worker iteration failed")
        if processed:
            continue
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval)
        except TimeoutError:
            pass
