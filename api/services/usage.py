"""Tenant-scoped creative render usage aggregation."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from mimik_contracts import LayerKind, UsageReport
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.db import repo

_UNKNOWN = "unknown"
_L1_KINDS = {LayerKind.L1_BASE.value, LayerKind.L1_BASE.name}


def _l1_params(manifest: dict) -> dict:
    """Return the raw L1 recipe params from a persisted manifest, or an empty mapping."""
    layers = manifest.get("layers")
    if not isinstance(layers, list):
        return {}
    for layer in layers:
        if not isinstance(layer, dict) or layer.get("kind") not in _L1_KINDS:
            continue
        recipe = layer.get("recipe")
        if not isinstance(recipe, dict):
            return {}
        params = recipe.get("params")
        return params if isinstance(params, dict) else {}
    return {}


def _bucket(params: dict, key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str):
        return _UNKNOWN
    normalized = value.strip()
    return normalized or _UNKNOWN


async def usage_report(
    session: AsyncSession,
    *,
    tenant_id: str,
    window_start: datetime,
    window_end: datetime,
) -> UsageReport:
    rows = await repo.list_creative_docs_in_window(
        session,
        tenant_id=tenant_id,
        start=window_start,
        end=window_end,
    )
    by_image_source: Counter[str] = Counter()
    by_profile: Counter[str] = Counter()
    for row in rows:
        manifest = row.manifest if isinstance(row.manifest, dict) else {}
        params = _l1_params(manifest)
        by_image_source[_bucket(params, "image_source")] += 1
        by_profile[_bucket(params, "style_profile_id")] += 1

    return UsageReport(
        window_start=window_start,
        window_end=window_end,
        renders=len(rows),
        by_image_source=dict(by_image_source),
        by_profile=dict(by_profile),
        monthly_cap=get_settings().generation_monthly_cap,
    )
