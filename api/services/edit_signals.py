"""Shared learning-signal capture for creative edits, reverts, and approvals."""

from __future__ import annotations

import logging
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from api.db import repo
from api.db.models import CreativeDocRow, JobRow
from creative.knowledge.feedback import record_feedback
from mimik_contracts import Actor, PreferenceSource

logger = logging.getLogger(__name__)

__all__ = ["_creative_attributes", "feedback_from_edit", "record_signal"]


def _creative_attributes(doc: CreativeDocRow) -> dict[str, str]:
    """Return the salient creative attributes scored by the taste ranker."""
    manifest = doc.manifest or {}
    attributes: dict[str, str] = {}
    if manifest.get("template_key"):
        attributes["template_key"] = str(manifest["template_key"])
    if manifest.get("format_key"):
        attributes["format_key"] = str(manifest["format_key"])
    return attributes


async def record_signal(
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
    """Persist one append-only signal, scoped to the creative's tenant and client."""
    await repo.create_preference_signal(
        session,
        tenant_id=tenant_id,
        client_id=job.client_id,
        source=source.value,
        creative_doc_id=doc.id,
        job_id=job.id,
        reason_tag=reason_tag,
        detail=detail,
        attributes={
            **_creative_attributes(doc),
            **(extra_attributes or {}),
        },
        actor_role=actor.role.value,
    )


def feedback_from_edit(
    *,
    verdict: Literal["accept", "decline"],
    reason: str,
    profile_id: str | None,
) -> None:
    """Feed one bounded edit outcome into the file-backed design-rules flywheel."""
    clean_reason = reason.strip()
    if not clean_reason:
        return
    try:
        record_feedback(
            verdict=verdict,
            reason=clean_reason[:200],
            profile_id=profile_id,
        )
    except Exception as exc:
        logger.warning("design-rule feedback capture failed: %s", exc)
