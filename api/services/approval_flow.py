"""The approval procedure: record an audited action, then fire its side-effects.

On APPROVE, the job moves to APPROVED and the auto-archive procedure runs — render the
creative deterministically from its manifest, archive it to the organized per-client path,
record a Delivery, and move the job to ARCHIVED. This is the "→ Approved auto-uploads to
Drive" rule enforced in code: a human never has to remember to upload.

On REQUEST_CHANGE / COMMENT, a Task is opened for ops and a notification is recorded. Every
path writes an append-only Approval row (the timestamped, attributed audit trail).

Rendering is injected (`render`) so the archive procedure is testable without a browser and so
the same procedure serves both the client-approval route and the ops board's →Approved move.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from api.db import repo
from api.db.mappers import to_approval, to_delivery, to_job, to_task
from api.db.models import CreativeDocRow, JobRow
from creative.archive import ArchiveBackend, get_archive_backend, safe_segment
from creative.assemble import assemble_context
from mimik_contracts import (
    Actor,
    ApprovalAction,
    CreativeManifest,
    JobStatus,
    NotificationChannel,
    PreferenceSource,
    RevisionTarget,
    TaskType,
)

# A renderer turns a stored creative doc into PNG bytes. Default re-renders from the manifest.
Renderer = Callable[[AsyncSession, str, CreativeDocRow], Awaitable[bytes]]


class ApprovalFlowError(Exception):
    """The approval could not be applied (missing job/creative, or a bad transition)."""


class ApprovalConflictError(ApprovalFlowError):
    """The action conflicts with the job's current state (e.g. approving an archived job)."""


# A job in one of these states is done; a further approve/request-change is a NEW request,
# never a re-run of the archive procedure (which would double-archive + double-deliver).
_TERMINAL_STATES = {
    JobStatus.APPROVED.value,
    JobStatus.DELIVERED.value,
    JobStatus.ARCHIVED.value,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _creative_attributes(doc: CreativeDocRow) -> dict[str, str]:
    """The salient attributes of a creative the taste-ranker scores against."""
    manifest = doc.manifest or {}
    attrs: dict[str, str] = {}
    if manifest.get("template_key"):
        attrs["template_key"] = str(manifest["template_key"])
    if manifest.get("format_key"):
        attrs["format_key"] = str(manifest["format_key"])
    return attrs


async def _record_signal(
    session: AsyncSession,
    *,
    tenant_id: str,
    job: JobRow,
    doc: CreativeDocRow,
    source: PreferenceSource,
    actor: Actor,
    reason_tag: str | None = None,
    detail: str | None = None,
    extra_attributes: dict[str, str] | None = None,
) -> None:
    """Capture a learning-loop signal, scoped to the job's client. Client-sourced signals
    feed ONLY this client's profile — never the shared golden set (that path is human-gated)."""
    await repo.create_preference_signal(
        session,
        tenant_id=tenant_id,
        client_id=job.client_id,
        source=source.value,
        creative_doc_id=doc.id,
        job_id=job.id,
        reason_tag=reason_tag,
        detail=detail,
        attributes={**_creative_attributes(doc), **(extra_attributes or {})},
        actor_role=actor.role.value,
    )


async def default_render(session: AsyncSession, tenant_id: str, doc: CreativeDocRow) -> bytes:
    """Re-render a creative deterministically from its manifest + the client's brand tokens.

    This is the manifest's whole purpose: the same manifest always yields the same creative,
    so the archive is reproducible from stored data. Needs the Playwright compositor.
    """
    from api.db.mappers import to_brand
    from creative.render.compositor import render_context_to_png

    manifest = CreativeManifest.model_validate(doc.manifest)
    job = await repo.get_job(session, tenant_id=tenant_id, job_id=doc.job_id)
    if job is None:
        raise ApprovalFlowError("job not found for creative")
    brand_row = await repo.get_brand(session, tenant_id=tenant_id, brand_id=job.brand_id)
    if brand_row is None:
        raise ApprovalFlowError("brand not found for creative")
    if not manifest.template_key:
        raise ApprovalFlowError("manifest has no template_key — cannot render")
    ctx = assemble_context(to_brand(brand_row), manifest)
    return await render_context_to_png(ctx, manifest.template_key)


async def run_archive(
    session: AsyncSession,
    *,
    tenant_id: str,
    job: JobRow,
    doc: CreativeDocRow,
    archive: ArchiveBackend,
    render: Renderer,
) -> dict:
    """Render + archive a creative and record the Delivery. Idempotent guard: callers should
    only invoke this on the approve transition."""
    client = await repo.get_client(session, tenant_id=tenant_id, client_id=job.client_id)
    client_name = client.name if client is not None else job.client_id
    when = job.publish_date or _now()
    year_month = when.strftime("%Y-%m")
    filename = f"{safe_segment(job.title, fallback='creative')}-{job.format_key}.png"

    data = await render(session, tenant_id, doc)
    stored = await archive.archive(
        client_name=client_name,
        year_month=year_month,
        job_id=job.id,
        filename=filename,
        data=data,
    )
    delivery = await repo.create_delivery(
        session,
        tenant_id=tenant_id,
        job_id=job.id,
        creative_doc_id=doc.id,
        drive_path=stored.path,
        delivered_at=_now(),
    )
    return {"delivery": to_delivery(delivery), "archived": stored}


async def submit_approval(
    session: AsyncSession,
    *,
    tenant_id: str,
    job_id: str,
    creative_doc_id: str,
    actor: Actor,
    action: ApprovalAction,
    note: str | None = None,
    reason_tag: str | None = None,
    targets: list[RevisionTarget] | None = None,
    archive: ArchiveBackend | None = None,
    render: Renderer | None = None,
) -> dict:
    """Record an approval action and apply its side-effects. Returns the resulting rows.

    Tenant scoping is enforced on every lookup; the caller is responsible for authorizing the
    actor against the job's client before calling (see the approvals router).
    """
    render = render or default_render  # resolved at call time so it stays monkeypatchable
    job = await repo.get_job(session, tenant_id=tenant_id, job_id=job_id)
    if job is None:
        raise ApprovalFlowError("job not found")
    doc = await repo.get_creative_doc(
        session, tenant_id=tenant_id, creative_doc_id=creative_doc_id
    )
    if doc is None or doc.job_id != job_id:
        raise ApprovalFlowError("creative not found for this job")

    # A stale magic link (72h TTL) or a double-submit must NOT re-fire the archive/status
    # side-effects on an already-finished job. COMMENT is exempt (append-only, no transition).
    if (
        action in (ApprovalAction.APPROVE, ApprovalAction.REQUEST_CHANGE)
        and job.status in _TERMINAL_STATES
    ):
        raise ApprovalConflictError(f"job is already {job.status}; a change now is a new request")

    # Targets only make sense on a change request. The router 422s this before we're
    # called; a direct caller gets the same rule enforced loud — silently dropping audit
    # data would violate the non-destructive/audited invariant (locked constraint #8).
    if targets and action != ApprovalAction.REQUEST_CHANGE:
        raise ApprovalFlowError("targets are only valid on a request_change action")
    approval = await repo.create_approval(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
        creative_doc_id=creative_doc_id,
        actor=actor.model_dump(mode="json"),
        action=action.value,
        note=note,
        targets=[t.model_dump(mode="json") for t in targets] if targets else [],
    )
    result: dict = {"approval": to_approval(approval)}

    if action == ApprovalAction.APPROVE:
        job.status = JobStatus.APPROVED.value
        archive = archive or get_archive_backend()
        archived = await run_archive(
            session, tenant_id=tenant_id, job=job, doc=doc, archive=archive, render=render
        )
        result.update(archived)
        job.status = JobStatus.ARCHIVED.value  # delivered + archived is the terminal state
        await repo.create_notification(
            session,
            tenant_id=tenant_id,
            client_id=job.client_id,
            job_id=job_id,
            channel=NotificationChannel.IN_APP.value,
            subject=f"Approved & archived: {job.title}",
            body=f"Archived to {result['delivery'].drive_path}",
        )
        await _record_signal(
            session, tenant_id=tenant_id, job=job, doc=doc,
            source=PreferenceSource.APPROVAL, actor=actor, detail=note,
        )
    elif action == ApprovalAction.REQUEST_CHANGE:
        job.status = JobStatus.INTERNAL_REVIEW.value  # back to ops to action the change
        # Pin-pointed targets make the ops task actionable: each line says WHERE + WHAT,
        # so the designer edits the named layer/zone instead of guessing from prose.
        detail = note
        if targets:
            # One line per target; embedded newlines in the (client freeform) instruction
            # are flattened so a crafted instruction can't forge extra "- [zone]" lines.
            target_lines = "\n".join(
                f"- [{t.zone.value}{f'/{t.layer.value}' if t.layer else ''}] "
                + " ".join(t.instruction.split())
                for t in targets
            )
            detail = f"{note}\n{target_lines}" if note else target_lines
        task = await repo.create_task(
            session,
            tenant_id=tenant_id,
            client_id=job.client_id,
            job_id=job_id,
            type=TaskType.CHANGE_REQUEST.value,
            title=f"Change requested: {job.title}",
            detail=detail,
            created_by=actor.model_dump(mode="json"),
        )
        result["task"] = to_task(task)
        await repo.create_notification(
            session,
            tenant_id=tenant_id,
            client_id=job.client_id,
            job_id=job_id,
            task_id=result["task"].id,
            channel=NotificationChannel.IN_APP.value,
            subject=f"Change requested: {job.title}",
            body=note,
        )
        await _record_signal(
            session, tenant_id=tenant_id, job=job, doc=doc,
            source=PreferenceSource.REJECTION, actor=actor, reason_tag=reason_tag, detail=note,
        )
        # One signal per pin-pointed target: the ranker learns WHICH zones/layers this
        # client pushes back on, not just that they pushed back.
        for t in targets or []:
            attrs = {"revision_zone": t.zone.value}
            if t.layer:
                attrs["revision_layer"] = t.layer.value
            await _record_signal(
                session, tenant_id=tenant_id, job=job, doc=doc,
                source=PreferenceSource.REJECTION, actor=actor, reason_tag=reason_tag,
                detail=t.instruction, extra_attributes=attrs,
            )
    elif action == ApprovalAction.COMMENT:
        task = await repo.create_task(
            session,
            tenant_id=tenant_id,
            client_id=job.client_id,
            job_id=job_id,
            type=TaskType.COMMENT.value,
            title=f"Comment on: {job.title}",
            detail=note,
            created_by=actor.model_dump(mode="json"),
        )
        result["task"] = to_task(task)

    result["job"] = to_job(job)
    await session.commit()
    return result
