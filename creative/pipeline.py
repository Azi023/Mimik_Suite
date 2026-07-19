"""End-to-end creative pipeline (P2): brief+pillar+topic → L0 copy → manifest → assemble
→ composite → brand-QA, with the conditional-scrim re-render loop.

The placeholder path (no cached imagery) renders a solid brand ground — the FREE dev/test
route. Real imagery arrives as a cached L1/L2 artifact ref generated elsewhere (paid,
operator-gated); this pipeline never triggers image generation itself.

QA failure does not raise: the report travels with the creative so the ops board / human
review sees exactly what failed (assisted autonomy — the human is the gate, not an exception).
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from creative.assemble import assemble_context
from creative.copy.l0 import draft_copy
from creative.qa.checks import QAReport, run_brand_qa
from creative.render.compositor import render_context_to_png
from creative.render.templates import TemplateContext
from mimik_contracts import (
    Brand,
    CopyBlock,
    CreativeManifest,
    Layer,
    LayerKind,
    LayerRecipe,
)


class CreativeResult(BaseModel):
    """One pipeline run: the rendered PNG plus everything needed to reproduce/inspect it."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    png: bytes
    manifest: CreativeManifest
    context: TemplateContext
    qa: QAReport
    scrim_applied: bool = False


def suggest_template(copy_block: CopyBlock, format_key: str) -> str:
    """v1 heuristic for the layout-FIRST pick: dense copy goes on a solid band (always
    legible); short punchy copy carries a full-bleed hero. Humans can override the pick."""
    density = len(copy_block.headline) + len(copy_block.subhead or "")
    return "lower_band" if density > 90 else "centered_hero"


def build_manifest(
    brand: Brand,
    copy_block: CopyBlock,
    format_key: str,
    *,
    template_key: str | None = None,
    image_artifact: str | None = None,
) -> CreativeManifest:
    """Assemble the deterministic manifest for one creative. `image_artifact` is a cached
    L1 ref (data URI / storage path); None keeps the free placeholder ground."""
    layers = []
    if image_artifact:
        layers.append(
            Layer(kind=LayerKind.L1_BASE, recipe=LayerRecipe(), artifact_ref=image_artifact)
        )
    return CreativeManifest(
        format_key=format_key,
        brand_id=brand.id,
        template_key=template_key or suggest_template(copy_block, format_key),
        copy_block=copy_block,
        layers=layers,
    )


async def generate_creative(
    brand: Brand,
    pillar_name: str,
    topic: str,
    format_key: str,
    *,
    template_key: str | None = None,
    copy_block: CopyBlock | None = None,
    image_artifact: str | None = None,
    require_approved_copy: bool = False,
    generate: Callable[[str], str] | None = None,
) -> CreativeResult:
    """Run the full P2 loop for one creative.

    Pass an already-approved `copy_block` to skip drafting (the normal flow once a human
    has signed the L0 copy off); omit it to draft fresh via the free Gemini text seam.
    """
    if copy_block is None:
        copy_block = draft_copy(brand, pillar_name, topic, format_key, generate=generate)
    manifest = build_manifest(
        brand, copy_block, format_key, template_key=template_key, image_artifact=image_artifact
    )

    ctx = assemble_context(brand, manifest, require_approved_copy=require_approved_copy)
    assert manifest.template_key is not None  # build_manifest always sets it
    png = await render_context_to_png(ctx, manifest.template_key)
    expect_logo = brand.tokens.logo.ref is not None
    qa = await run_brand_qa(png, ctx, manifest.template_key, expect_logo=expect_logo)

    scrim_applied = False
    if not qa.passed and qa.needs_scrim:
        # Conditional scrim (locked): only after the contrast check flags a zone.
        ctx = assemble_context(
            brand, manifest, scrim=True, require_approved_copy=require_approved_copy
        )
        png = await render_context_to_png(ctx, manifest.template_key)
        qa = await run_brand_qa(png, ctx, manifest.template_key, expect_logo=expect_logo)
        scrim_applied = True

    return CreativeResult(
        png=png, manifest=manifest, context=ctx, qa=qa, scrim_applied=scrim_applied
    )
