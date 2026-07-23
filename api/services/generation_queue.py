"""Database-backed generation queue service."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException
from mimik_contracts import (
    Actor,
    ActorRole,
    GenerationQueueItem,
    JobStatus,
    PRESETS,
    QueueStats,
    TaskStatus,
    TaskType,
)
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, is_client_in_scope
from api.db import repo
from api.db.models import TaskRow
from api.services.creative_generation import _TEAM_ROLES, _actor_dict


def parse_generation_detail(detail: str | None) -> dict[str, object]:
    """Return an object payload; legacy plain text or malformed JSON becomes an empty payload."""
    if not detail:
        return {}
    try:
        parsed = json.loads(detail)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _task_actor(task: TaskRow) -> Actor:
    raw = task.created_by if isinstance(task.created_by, dict) else {}
    actor_payload = {
        "id": raw.get("id") or task.tenant_id,
        "role": raw.get("role") or ActorRole.SYSTEM.value,
        "name": raw.get("name"),
    }
    try:
        return Actor.model_validate(actor_payload)
    except (TypeError, ValueError):
        return Actor(
            id=task.tenant_id,
            role=ActorRole.SYSTEM,
            name=None,
        )


def _task_to_queue_item(task: TaskRow) -> GenerationQueueItem:
    payload = parse_generation_detail(task.detail)
    topic_value = payload.get("topic")
    topic = (
        " ".join(topic_value.split())
        if isinstance(topic_value, str) and topic_value.strip()
        else task.title
    )
    pillar_value = payload.get("pillar")
    pillar = (
        " ".join(pillar_value.split())
        if isinstance(pillar_value, str) and pillar_value.strip()
        else None
    )
    format_value = payload.get("format_key")
    error_value = payload.get("error")
    return GenerationQueueItem(
        id=task.id,
        job_id=task.job_id or "",
        client_id=task.client_id,
        topic=topic,
        pillar=pillar,
        format_key=format_value if isinstance(format_value, str) else "",
        status=TaskStatus(task.status),
        requested_by=_task_actor(task),
        created_at=task.created_at,
        error=error_value if isinstance(error_value, str) else None,
    )


async def enqueue_generation(
    session: AsyncSession,
    *,
    principal: Principal,
    client_id: str,
    topic: str,
    pillar: str | None,
    format_key: str,
) -> GenerationQueueItem:
    if principal.role not in _TEAM_ROLES:
        raise HTTPException(status_code=403, detail="Creative generation is a team action")
    if not is_client_in_scope(principal, client_id):
        raise HTTPException(status_code=404, detail="Client not found")
    if format_key not in PRESETS:
        raise HTTPException(status_code=422, detail="Unknown creative format")

    normalized_topic = " ".join(topic.split())
    if not normalized_topic:
        raise HTTPException(status_code=422, detail="Topic must not be blank")
    normalized_pillar = " ".join(pillar.split()) if pillar else None
    normalized_pillar = normalized_pillar or None

    client = await repo.get_client(
        session,
        tenant_id=principal.tenant_id,
        client_id=client_id,
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    brand_rows = await repo.list_brands(
        session,
        tenant_id=principal.tenant_id,
        client_id=client_id,
    )
    if not brand_rows:
        raise HTTPException(status_code=404, detail="Client brand not found")

    detail = json.dumps(
        {
            "topic": normalized_topic,
            "pillar": normalized_pillar,
            "format_key": format_key,
        }
    )
    try:
        job = await repo.create_job(
            session,
            tenant_id=principal.tenant_id,
            client_id=client_id,
            brand_id=brand_rows[0].id,
            title=normalized_topic,
            format_key=format_key,
            status=JobStatus.DRAFT.value,
        )
        task = await repo.create_task(
            session,
            tenant_id=principal.tenant_id,
            client_id=client_id,
            job_id=job.id,
            type=TaskType.GENERATION.value,
            status=TaskStatus.OPEN.value,
            title=normalized_topic,
            detail=detail,
            created_by=_actor_dict(principal),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return _task_to_queue_item(task)


async def list_queue(
    session: AsyncSession,
    *,
    tenant_id: str,
) -> list[GenerationQueueItem]:
    tasks = await repo.list_generation_tasks(session, tenant_id=tenant_id)
    return [_task_to_queue_item(task) for task in tasks]


async def queue_stats(
    session: AsyncSession,
    *,
    tenant_id: str,
) -> QueueStats:
    tasks = await repo.list_generation_tasks(session, tenant_id=tenant_id)
    utc_midnight = datetime.now(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    pending = 0
    in_progress = 0
    done_today = 0
    failed_today = 0
    for task in tasks:
        if task.status == TaskStatus.OPEN.value:
            pending += 1
            continue
        if task.status == TaskStatus.IN_PROGRESS.value:
            in_progress += 1
            continue
        created_at = task.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if task.status != TaskStatus.DONE.value or created_at < utc_midnight:
            continue
        if _task_to_queue_item(task).error is None:
            done_today += 1
        else:
            failed_today += 1
    return QueueStats(
        pending=pending,
        in_progress=in_progress,
        done_today=done_today,
        failed_today=failed_today,
    )
