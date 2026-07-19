"""Task routes — tenant-scoped. The portal and the ops board are two views of ONE task table.

A task is created by a client (bounded portal — always scoped to their own client_id) or by the
team (any client in the tenant). Creation records a companion notification to ops (recorded now,
delivered by a channel adapter later). The team advances a task open -> in_progress -> done.

Tenant authZ lives at the data layer (every repo call is filtered by tenant_id); on top of that a
`client` principal is confined to its own client_id on read AND write — never trust the body's id.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal, require_role
from api.db import repo
from api.db.mappers import to_task
from api.db.session import get_session
from mimik_contracts import ActorRole, Task, TaskStatus, TaskType

router = APIRouter(prefix="/tasks", tags=["tasks"])

_TASK_TYPE_VALUES = {t.value for t in TaskType}
_TASK_STATUS_VALUES = {s.value for s in TaskStatus}


class CreateTask(BaseModel):
    client_id: str | None = None  # ignored for a client principal (forced to their own)
    job_id: str | None = None
    type: str
    title: str
    detail: str | None = None


class AdvanceStatus(BaseModel):
    status: str


@router.post("", response_model=Task, status_code=201)
async def create_task(
    body: CreateTask,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Task:
    if body.type not in _TASK_TYPE_VALUES:
        raise HTTPException(status_code=422, detail=f"Unknown task type: {body.type}")

    if principal.role == ActorRole.CLIENT.value:
        # Bounded portal: a client can only ever open a task on its own client, never the body's.
        if not principal.client_id:
            raise HTTPException(status_code=403, detail="Client principal has no client_id")
        client_id = principal.client_id
        created_by = {
            "id": principal.user_id or principal.tenant_id,
            "role": ActorRole.CLIENT.value,
        }
    else:
        # Team principal: the client must belong to the caller's tenant (else cross-tenant attach).
        if not body.client_id:
            raise HTTPException(status_code=422, detail="client_id is required")
        client = await repo.get_client(
            session, tenant_id=principal.tenant_id, client_id=body.client_id
        )
        if client is None:
            raise HTTPException(status_code=404, detail="Client not found")
        client_id = body.client_id
        created_by = {
            "id": principal.user_id or principal.tenant_id,
            "role": principal.role,
        }

    # If a job is referenced, it must belong to this tenant AND to the same client the task is
    # for — otherwise a principal could tag their task as being about another client's job.
    if body.job_id is not None:
        job = await repo.get_job(session, tenant_id=principal.tenant_id, job_id=body.job_id)
        if job is None or job.client_id != client_id:
            raise HTTPException(status_code=404, detail="Job not found")

    row = await repo.create_task(
        session,
        tenant_id=principal.tenant_id,
        client_id=client_id,
        job_id=body.job_id,
        type=body.type,
        status=TaskStatus.OPEN.value,
        title=body.title,
        detail=body.detail,
        created_by=created_by,
    )
    # Companion nudge to ops — recorded now (the audit trail), delivered by a channel adapter.
    await repo.create_notification(
        session,
        tenant_id=principal.tenant_id,
        client_id=client_id,
        job_id=body.job_id,
        task_id=row.id,
        subject=f"New {body.type}: {body.title}",
    )
    await session.commit()
    return to_task(row)


@router.get("", response_model=list[Task])
async def list_tasks(
    client_id: str | None = None,
    job_id: str | None = None,
    status: str | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Task]:
    # A client principal is confined to its own client's tasks, whatever the query asks for.
    if principal.role == ActorRole.CLIENT.value:
        if not principal.client_id:
            raise HTTPException(status_code=403, detail="Client principal has no client_id")
        client_id = principal.client_id
    rows = await repo.list_tasks(
        session,
        tenant_id=principal.tenant_id,
        client_id=client_id,
        job_id=job_id,
        status=status,
    )
    return [to_task(r) for r in rows]


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Task:
    row = await repo.get_task(session, tenant_id=principal.tenant_id, task_id=task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    # A client principal may only see its own client's task (bounded portal). 404, not 403, so a
    # client cannot even confirm another client's task exists.
    if principal.role == ActorRole.CLIENT.value and row.client_id != principal.client_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return to_task(row)


@router.post("/{task_id}/status", response_model=Task)
async def advance_status(
    task_id: str,
    body: AdvanceStatus,
    principal: Principal = Depends(require_role("owner", "ops", "designer", "team")),
    session: AsyncSession = Depends(get_session),
) -> Task:
    if body.status not in _TASK_STATUS_VALUES:
        raise HTTPException(status_code=422, detail=f"Unknown task status: {body.status}")
    row = await repo.get_task(session, tenant_id=principal.tenant_id, task_id=task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    row.status = body.status
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return to_task(row)
