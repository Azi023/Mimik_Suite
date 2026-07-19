"""Manifest → TemplateContext assembly: the seam between the stored creative (contracts)
and the render pipeline (templates + compositor).

Pulls the client's brand tokens, the approved L0 copy, and the cached L1/L2 imagery
artifact out of a `CreativeManifest` and produces the `TemplateContext` the compositor
renders. Deterministic and pure — the conditional-scrim decision belongs to the QA step
(render → contrast check → re-render with scrim), not here.
"""

from __future__ import annotations

import re

from mimik_contracts import Brand, ColorRole, CopyStatus, CreativeManifest, LayerKind, get_format

from creative.render.color import tint
from creative.render.templates import TemplateContext, get_template

# Mimik house defaults — used ONLY when a brand carries no tokens yet (early-stage /
# placeholder dev renders). A brand with tokens always renders from its own identity.
_DEFAULT_PRIMARY = "#2E5BFF"
_DEFAULT_ACCENT = "#C6F135"
_DEFAULT_INK = "#0B0D12"
_DEFAULT_ON_PRIMARY = "#FFFFFF"

# Font names land inside a CSS font-family declaration unquoted-by-template; restrict to
# characters that cannot break out of the style context (defense in depth — brand data is
# team-entered, but the render path shouldn't trust that).
_FONT_SAFE = re.compile(r"[^A-Za-z0-9 _-]")
_FONT_STACK = "system-ui, -apple-system, sans-serif"


class AssemblyError(ValueError):
    """The manifest is not renderable yet (missing copy, template, ...). Fail loud."""


def _normalize_hex(value: str) -> str:
    """Expand #abc → #aabbcc (contracts allow 3-digit hex; TemplateContext requires 6)."""
    if len(value) == 4:
        return "#" + "".join(ch * 2 for ch in value[1:])
    return value


def _color(colors: list[ColorRole], *names: str) -> str | None:
    for name in names:
        for role in colors:
            if role.name.lower() == name:
                return _normalize_hex(role.hex)
    return None


def _font(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = _FONT_SAFE.sub("", name).strip()
    if not cleaned:
        return None
    return f"'{cleaned}', {_FONT_STACK}"


def _image_ref(manifest: CreativeManifest) -> str | None:
    """Cached imagery: prefer the L2 concept pass, fall back to the L1 base plate.
    None → the template renders a solid brand ground (the free placeholder path)."""
    for kind in (LayerKind.L2_CONCEPT, LayerKind.L1_BASE):
        layer = manifest.layer(kind)
        if layer is not None and layer.artifact_ref:
            return layer.artifact_ref
    return None


def assemble_context(
    brand: Brand,
    manifest: CreativeManifest,
    *,
    scrim: bool = False,
    require_approved_copy: bool = False,
) -> TemplateContext:
    """Build the render-ready TemplateContext for one creative.

    `require_approved_copy=True` is the delivery path: a draft L0 copy block must never
    reach a client-facing render (the human gate is the product).
    """
    if manifest.brand_id != brand.id:
        raise AssemblyError(f"manifest brand_id {manifest.brand_id!r} != brand {brand.id!r}")
    if manifest.copy_block is None:
        raise AssemblyError("manifest has no copy block — run the L0 copy step first")
    if not manifest.template_key:
        raise AssemblyError("manifest has no template_key — layout is chosen FIRST")
    get_template(manifest.template_key)  # KeyError on unknown template (fail loud)
    get_format(manifest.format_key)  # KeyError on unknown format (fail loud)
    if require_approved_copy and manifest.copy_block.status == CopyStatus.DRAFT:
        raise AssemblyError("copy is still a draft — human approval required before delivery")

    colors = brand.tokens.colors
    primary = _color(colors, "primary") or _DEFAULT_PRIMARY
    # A brand that carries ANY palette never borrows a house color (client-feedback lesson:
    # Mimik's lime leaked into a client CTA). A missing accent is DERIVED from the brand's
    # own primary — a soft tint chip that carries the brand, reads with dark labels, and
    # can never be another company's color.
    accent = _color(colors, "accent", "secondary")
    if accent is None:
        accent = tint(primary, 0.82) if colors else _DEFAULT_ACCENT
    return TemplateContext(
        format_key=manifest.format_key,
        headline=manifest.copy_block.headline,
        subhead=manifest.copy_block.subhead,
        cta=manifest.copy_block.cta,
        primary=primary,
        accent=accent,
        on_primary=_color(colors, "on_primary") or _DEFAULT_ON_PRIMARY,
        ink=_color(colors, "ink", "dark") or _DEFAULT_INK,
        heading_font=_font(brand.tokens.typography.heading_font) or TemplateContext.model_fields["heading_font"].default,
        body_font=_font(brand.tokens.typography.body_font) or TemplateContext.model_fields["body_font"].default,
        logo_ref=brand.tokens.logo.ref,
        image_ref=_image_ref(manifest),
        scrim=scrim,
    )
