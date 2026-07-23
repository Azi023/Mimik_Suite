# Simply Nikah Vector Render Engine — BUILD SPEC

> Implementation-ready spec for the `simply-nikah` per-client render family.
> Design contract: `docs/STYLE_PROFILES.md` Profile 1 (the ONLY taste source).
> Data model: `creative/style_profile.py` (`PROFILES["simply-nikah"]`, `ImageSource.GENERATED_VECTOR`).
> Pattern to mirror: `creative/render/glo2go_templates.py::render_glo2go`.
> Layer contract to match: `creative/export/svg.py::render_creative_svg` (line 452) + `_layer()` (line 209).
> Wire-in target (DO NOT EDIT in this build): `api/services/creative_generation.py::_render_creative_artifacts`
> — a sibling branch `if profile_id == "simply-nikah":` will call `render_nikah(...)`, done by the orchestrator later.

## 0. Non-negotiables (from the profile's hard_guardrails)

1. Never real photographs of people. The engine composes ONLY engine SVG primitives — no raster
   `<image>` embeds except an approved logo/wordmark asset.
2. Every figure faceless/silhouette — enforced **by construction**: no primitive in the vocabulary
   has facial-feature paths, and every figure primitive stamps `data-figure="true" data-faceless="true"`.
3. Modesty (haya) mandatory — figure primitives are fully-covered silhouettes (hijab outline,
   sleeve-covered hands). No skin-tone rendering; figures render in palette colors only.
4. "simply nikāh" wordmark top-center in every archetype.
5. No forced header/footer band; each archetype composes freely (layout variety).
6. Whitespace dominates: non-ground ink coverage (ornament + symbol + type) ≤ 45% of canvas area;
   ornament alone (lattice/glow/motifs, excluding type) ≤ 25%.

Palette roles come from `get_style_profile("simply-nikah").palette` via the same
`_palette_color(profile, role, fallback)` pattern glo2go uses (all hexes are `approx=True`, so
fallback constants apply until onboarding confirms — mirror glo2go's TODO(M3) comment):

| Role | Fallback const | Value |
|---|---|---|
| primary | `_PINK_FALLBACK` | `#FD62AD` |
| accent | `_BLUSH_FALLBACK` | `#F9C6DE` |
| ink / cta_fill | `_PLUM_FALLBACK` | `#2B0A2E` |
| secondary | `_LILAC_FALLBACK` | `#9B7BA6` |
| ground | `_CLOUD_FALLBACK` | `#FAF7FB` |

Fonts: none supplied. v1 uses `_SYSTEM_FONT` (same constant style as glo2go) with a
`TODO(M3)` to swap after onboarding. The wordmark renders **typographically** ("simply nikāh",
lowercase, includes U+0101 ā) until a logo asset is supplied; `logo_ref` overrides it when present.

---

## 1. Vector primitive vocabulary — `creative/render/nikah_primitives.py`

All primitives are **pure, deterministic functions returning an SVG fragment string** (a `<g>` or
`<path>`/`<pattern>`). No I/O, no randomness unless an explicit `seed` param is given. Every
figure-depicting primitive stamps `data-figure="true" data-faceless="true"` on its root `<g>`
(the modesty check asserts on this). Coordinates are canvas px, top-left origin.

Operator decision (recorded): complex organic paths (hands-forming-heart, lantern body, hijabi
silhouette) are **seeded from FREE vector packs** — trace/simplify the path data once, embed it as
a Python path-string constant, normalize to a unit box, license-check before embedding (CC0 /
free-for-commercial only; record source URL in a comment). They render as engine SVG forever:
zero per-render cost, perfectly consistent. NO runtime fetching.

### v1 primitives (needed by the 2 v1 archetypes)

| # | Signature | Visual |
|---|---|---|
| 1 | `lattice_pattern(pattern_id: str, *, tile: int = 120, stroke: str, stroke_width: float = 3.0, motif: Literal["eight_star", "hexagon"] = "eight_star", opacity: float = 0.10) -> str` | Tileable mashrabiya/Islamic-lattice `<pattern>` def (referenced via `fill="url(#id)"`); geometric 8-point-star or hex grid at whisper opacity. |
| 2 | `crescent(cx: float, cy: float, r: float, *, fill: str, rotation: float = -20.0, thickness: float = 0.42) -> str` | Flat crescent moon: outer circle minus offset inner circle (single even-odd path), tilted. |
| 3 | `shield(cx: float, cy: float, w: float, h: float, *, fill: str, stroke: str | None = None, stroke_width: float = 0.0, fill_pattern_id: str | None = None) -> str` | Soft-cornered heater shield; optional inner fill referencing a lattice pattern at low opacity. |
| 4 | `heart(cx: float, cy: float, size: float, *, fill: str) -> str` | Flat rounded heart, no gloss/outline effects. |
| 5 | `hands_forming_heart(cx: float, cy: float, size: float, *, fill: str, sleeve_fill: str | None = None) -> str` | Two sleeve-covered silhouette hands meeting in a heart shape — faceless, fully modest; pack-seeded path constant. Stamps `data-figure`/`data-faceless`. |
| 6 | `highlighted_word_box(word: str, *, x: float, y: float, font_size: float, box_fill: str, text_fill: str, font_family: str, pad_x_em: float = 0.45, pad_y_em: float = 0.22, rx: float = 14.0) -> tuple[str, float, float]` | The decisive deep-plum box with the uppercase key word reversed out (Cloud White text). Returns `(svg, box_width, box_height)` — measured with the same conservative glyph factor the glo2go/svg code uses (0.60 × font_size per char for 700+ weight) so callers can center/flow it. |

### v1 helpers (composition-level, same file)

| Signature | Visual |
|---|---|
| `wordmark(cx: float, y: float, *, height: float, fill: str, font_family: str, logo_ref: str | None = None) -> str` | "simply nikāh" top-center; typographic until `logo_ref` (data-URI/local path, embedded via the same `_embed_local_image` pattern) is supplied. Root `<g data-role="wordmark">`. |
| `cta_pill(cx: float, y: float, *, height: float, label: str, fill: str, text_fill: str, font_family: str) -> tuple[str, float]` | Rounded pill CTA (badge/pill effect), returns `(svg, pill_width)`. |
| `glow_ellipse(cx: float, cy: float, rx: float, ry: float, *, fill: str, opacity: float = 0.5) -> str` | Restrained blush radial glow behind a hero symbol (profile's `blur` effect, done as radial-gradient ellipse — filter-free so rasterizers agree). |

### Deferred primitives (define signatures now, `raise NotImplementedError` bodies — needed by archetypes 2/3/4/6)

| # | Signature | Visual | For |
|---|---|---|---|
| 7 | `mihrab_arch_frame(x: float, y: float, w: float, h: float, *, stroke: str, stroke_width: float = 6.0, style: Literal["line", "double"] = "line") -> str` | Pointed mihrab/ogee arch outline framing content. | Mihrab/Lattice Frame |
| 8 | `faceless_avatar_card(x: float, y: float, w: float, h: float, *, variant: Literal["hijabi", "beard", "plain"], card_fill: str, figure_fill: str, rx: float = 24.0) -> str` | Rounded card holding a bust-level faceless silhouette (hijab or beard outline, zero facial features). Stamps `data-figure`/`data-faceless`. | Connected Match Cards |
| 9 | `connector_path(points: Sequence[tuple[float, float]], *, stroke: str, stroke_width: float = 4.0, dash: str | None = "2 10", dot_terminals: bool = True) -> str` | Gentle dashed connector line joining cards, dot at each end. | Connected Match Cards |
| 10 | `calligraphy_panel_frame(x: float, y: float, w: float, h: float, *, stroke: str, fill: str, rx: float = 28.0) -> str` | Ornamented panel frame that HOSTS supplied calligraphy artwork — the frame is engine vector; the ayah calligraphy itself is an approved asset, never engine-drawn. | Ayah & Translation |
| 11 | `lantern(cx: float, cy: float, h: float, *, fill: str, glow: bool = False) -> str` | Flat Ramadan/fanous lantern silhouette; pack-seeded path. | seasonal/Eid |
| 12 | `phone_mockup(cx: float, cy: float, h: float, *, frame_fill: str, screen_fill: str, screen_content_svg: str = "") -> str` | Flat rounded phone frame with an injectable screen-content slot. | Phone-and-Hijabi |

**Count: 12 motif primitives (6 v1 + 6 deferred) + 3 v1 helpers.**

---

## 2. v1 layout archetypes — composition specs

Reference format: **`carousel` preset = 1080×1350 (4:5)**, safe zone (top 80, right 60, bottom 80,
left 60). NOTE: `mimik_contracts.formats.PRESETS` has no dedicated 4:5 feed-post key — `carousel`
IS the 1080×1350 4:5 preset; SN uses it as the reference. Geometry is computed from `(W, H, safe_zone)`
via one `_composition(ctx)` dataclass per archetype (the glo2go pattern) so HTML render, SVG emitter,
and `geometry()` share one source of truth.

### Generic scaling rule (all formats)

Content column = the safe area (`layout_grid`-style insets, clamped up by `fmt.safe_zone` exactly as
`templates._edge_pads` does). Vertical placement is fractional over the **content span**
`S = [safe_top .. H - safe_bottom]`:

- wordmark baseline: `safe_top + 0.040·H` (height `0.033·H`, min 40px)
- headline block top: `safe_top + 0.115·H`
- hero symbol center-y: `safe_top + 0.60·len(S)`
- CTA pill top: `H - safe_bottom - 0.030·H - pill_h`
- hero diameter: `min(hero_frac·W, 0.85 × free vertical gap between headline-block bottom and CTA top)`

This yields for the three launch formats:

| | 4:5 `carousel` 1080×1350 | 1:1 `ig_post` 1080×1080 | 9:16 `ig_story` 1080×1920 |
|---|---|---|---|
| wordmark baseline y | 134 | 103 | 327 |
| headline top y | 235 | 184 | 471 |
| hero center y | 791 | 636 | 1102 |
| CTA top y | ~1186 | ~940 | ~1554 |

(9:16 uses the story safe zone 250/250 — everything lives in y 250..1670.)

### Archetype A — `highlighted_word_hero` (Highlighted-Word Hero)

First read (per composition_principles): **the highlighted word** → headline remainder → hero
symbol → support line → CTA. Center-aligned single column, near-symmetric, calm.

Zones at 1080×1350:

| Zone | Geometry | Content |
|---|---|---|
| ground | full bleed | Cloud White; optional vertical `gradient/fade` Cloud White → Soft Blush at ≤ 12% opacity toward the bottom |
| lattice backdrop (optional, default ON at whisper level) | full bleed OR a top band ≤ 0.22·H | `lattice_pattern` in Muted Lilac, opacity 0.06–0.10 |
| wordmark | centered, baseline y=134, h=44 | `wordmark()` |
| headline | x 120..960 (840 wide), top y=235, font 92 (`0.085·W`), line-height 1.08, ≤ 3 lines, center, Deep Plum, weight 760 | one word rendered via `highlighted_word_box` inline (uppercase, plum box, Cloud White text) — box flows within the line, line re-measured with box width |
| support | margin-top 30, font 34 (`0.0315·W`), line-height 1.45, ≤ 2 lines, Deep Plum @ 0.85 opacity, center | support line |
| hero symbol | center (540, 791), box 454 (`0.42·W`); `glow_ellipse` behind at rx=1.35×half-box, Soft Blush, opacity 0.5 | one of `hands_forming_heart` / `shield`+`crescent` composite / `heart` — selected by `hero_symbol` param |
| cta | centered pill, h=84 (`0.062·H`), font 32, top ~1186 | `cta_pill`, Deep Plum fill (`cta_fill` role), Cloud White text |

Copy keys: `headline` (required), `highlight` (required — MUST be a case-insensitive substring of
`headline`; fail loud otherwise), `sub`/`subhead` (optional), `cta` (optional).

### Archetype B — `protection_symbol_hero` (Protection/Intention Symbol Hero)

First read: **the central symbol** — it is larger and headline is restrained (symbol establishes
the first read per the profile). Center column, dominant symbol below a concise headline.

Zones at 1080×1350:

| Zone | Geometry | Content |
|---|---|---|
| ground | full bleed | Cloud White (no gradient by default — quieter than A) |
| wordmark | centered, baseline y=134, h=44 | `wordmark()` |
| headline | x 120..960, top y=235, font 76 (`0.070·W`), ≤ 2 lines, center, Deep Plum | plain (no highlight box by default; `highlight` copy key optional) |
| support | margin-top 26, font 32, ≤ 2 lines, center | support line |
| hero symbol | center (540, 815), box 562 (`0.52·W`) — deliberately larger than A; glow behind, opacity 0.45 | variants (`hero_symbol` param): `"shield_crescent"` = `shield` with `lattice_pattern` inner fill @ 0.10 + `crescent` floating at shield top-right; `"hands_heart"`; `"heart_shield"` = `heart` centered inside `shield` |
| cta | centered pill, h=84, top ~1178 | `cta_pill` |

Copy keys: `headline` (required), `sub`/`subhead` (optional), `cta` (optional), `highlight` (optional).

### Deferred archetypes ("later" list — signatures reserved, no v1 build)

`phone_hijabi_story`, `connected_match_cards`, `mihrab_lattice_frame`, `ayah_translation_panel`.

---

## 3. Render-family entry point — `creative/render/nikah_templates.py`

Mirrors `glo2go_templates.py` exactly in shape: a `NikahTemplateContext(TemplateContext)`, archetype
classes subclassing `LayoutTemplate` (registered into the shared `TEMPLATES` registry via
`TEMPLATES.update(NIKAH_TEMPLATES)` so `run_brand_qa`'s `get_template(...)` + `geometry()` work
unchanged), an HTML builder for structural tests, an async `render_nikah` returning PNG bytes via
`render_context_to_png`, and a **standalone SVG emitter** matching svg.py's named-layer contract.

Single geometry source: each archetype computes one frozen `_NikahComposition` dataclass; `render()`
(HTML), `build_nikah_svg()` (SVG), and `geometry()` (QA zones) all consume it. The HTML render
simply wraps the same inline SVG markup in a sized `<div>` — pixel parity between compositor PNG
and exported SVG is by construction.

### SVG layer contract (must match `svg.py::_layer` attributes exactly)

Root `<svg>` carries `version/width/height/viewBox/data-grid-step/data-design-rule-ids` (rule ids
via `load_rules("simply-nikah")`, same as glo2go). Each layer is a `<g>` with:
`id`, `data-layer`, `inkscape:label`, `inkscape:groupmode="layer"`, `data-editable="true"`,
`data-bbox="x y w h"` — identical attribute set to `svg.py` line 209, so the canvas editor and PSD
export consume SN SVGs with zero changes.

Layer ids (paint order, bottom→top):

```
layer-background        # ground fill + optional gradient
layer-motif             # lattice backdrop (may be empty; still emitted, like layer-subhead)
layer-glow              # blush glow ellipse
layer-hero              # the hero symbol group (figure groups inside carry data-figure/data-faceless)
layer-wordmark          # top-center wordmark
layer-headline          # headline text lines
layer-highlight-word    # the plum highlighted-word box + reversed text (empty for plain headlines)
layer-support           # support line
layer-cta               # CTA pill
```

### Skeletons (what Codex implements — signatures are the contract)

```python
"""creative/render/nikah_templates.py"""
from typing import Literal

from creative.render.templates import LayoutTemplate, TemplateContext, TemplateGeometry, TEMPLATES
from creative.style_profile import StyleProfile

_NIKAH_PROFILE_ID = "simply-nikah"

HeroSymbol = Literal["hands_heart", "shield_crescent", "heart_shield", "heart", "crescent"]


class NikahTemplateContext(TemplateContext):
    """Simply Nikah copy + composition controls shared by both v1 archetypes.

    image_ref stays None — SN composes pure engine vectors (GENERATED_VECTOR);
    a non-None image_ref MUST raise (guards the never-real-photos rule).
    """

    highlight_word: str | None = None
    hero_symbol: HeroSymbol = "hands_heart"
    lattice_backdrop: bool = True
    ground_gradient: bool = True          # archetype A default; B passes False
    secondary: str = "#9B7BA6"            # muted-lilac palette role (TemplateContext lacks it)
    design_rule_ids: tuple[str, ...] = ()


class HighlightedWordHero(LayoutTemplate):
    """Headline with one plum-boxed key word above a central vector hero."""

    key = "highlighted_word_hero"
    name = "Highlighted-Word Hero"
    description = "Trust/intention message with one decisive plum-boxed word over a vector hero."

    def render(self, ctx: TemplateContext) -> str:
        """Sized <div> wrapping the SAME inline SVG that build_nikah_svg emits."""
        raise NotImplementedError

    def geometry(self, ctx: TemplateContext) -> TemplateGeometry:
        """text_zones = [headline(+highlight) block, support, cta]; logo_zone = wordmark box;
        text_over_imagery=False (type sits on ground, never on the hero)."""
        raise NotImplementedError


class ProtectionSymbolHero(LayoutTemplate):
    """Dominant shield/crescent/hands symbol beneath a concise headline."""

    key = "protection_symbol_hero"
    name = "Protection or Intention Symbol Hero"
    description = "Central protective symbol as the first read, restrained headline above."

    def render(self, ctx: TemplateContext) -> str:
        raise NotImplementedError

    def geometry(self, ctx: TemplateContext) -> TemplateGeometry:
        raise NotImplementedError


NIKAH_TEMPLATES: dict[str, LayoutTemplate] = {
    t.key: t for t in (HighlightedWordHero(), ProtectionSymbolHero())
}
TEMPLATES.update(NIKAH_TEMPLATES)  # extend the established registry, like glo2go


def build_nikah_html(
    archetype: str,
    *,
    copy: dict[str, str],
    format_key: str,
    profile: StyleProfile,
    hero_symbol: HeroSymbol = "hands_heart",
    logo_ref: str | None = None,
    lattice_backdrop: bool = True,
) -> str:
    """Editable HTML for structural tests (mirror of build_glo2go_html).

    Copy keys — highlighted_word_hero: ``headline`` + ``highlight`` (required; highlight must be a
    case-insensitive substring of headline), optional ``sub``/``subhead``, ``cta``.
    protection_symbol_hero: ``headline`` required; ``highlight``/``sub``/``cta`` optional.
    """
    raise NotImplementedError


def build_nikah_svg(
    archetype: str,
    *,
    copy: dict[str, str],
    format_key: str,
    hero_symbol: HeroSymbol = "hands_heart",
    logo_ref: str | None = None,
    lattice_backdrop: bool = True,
    layer_overrides: "Mapping[str, object] | None" = None,
) -> str:
    """Standalone layered SVG matching svg.py's named-layer contract (layer ids above).

    layer_overrides accepts the same dx/dy/scale/rotation/visible/fill mapping svg.py honors,
    keyed by SN layer ids, so the canvas editor round-trips without a second code path.
    """
    raise NotImplementedError


async def render_nikah(
    archetype: str,
    *,
    copy: dict[str, str],
    format_key: str,
    hero_symbol: HeroSymbol = "hands_heart",
    logo_ref: str | None = None,
    lattice_backdrop: bool = True,
) -> bytes:
    """Render a Simply Nikah archetype to PNG through the existing Playwright compositor.

    Mirrors render_glo2go's call shape (minus image_ref — SN never takes a photo): loads
    get_style_profile("simply-nikah") internally, builds the context, fails loud on unknown
    archetype/format/copy, returns PNG bytes at exact format dimensions.
    """
    raise NotImplementedError


def modesty_report(svg_text: str, *, source_kind: str) -> list[str]:
    """Structural modesty/haya QA (see §4). Returns failure strings, [] = pass."""
    raise NotImplementedError
```

Internal helpers to implement (same naming discipline as glo2go): `_require_nikah_profile(profile)`
(asserts id + required effects {GRADIENT_FADE, BLUR, COLOR_BLOCK, BADGE_PILL}), `_palette_color`
reuse pattern, `_copy_value` reuse pattern, `_composition(ctx) -> _NikahComposition` per archetype,
`_density` (copy-length driven compact/dense font step-down, thresholds tuned in build).

### Wire-in contract (orchestrator does this later — ZERO edits in this build)

Sibling branch in `_render_creative_artifacts`:

```python
if profile_id == "simply-nikah":
    profile_png = await nikah_templates.render_nikah(
        _NIKAH_ARCHETYPE,
        copy={"headline": copy_block.headline, "highlight": ...,
              "subhead": copy_block.subhead or "", "cta": copy_block.cta or ""},
        format_key=format_key,
    )
```

**Wire-in note for the orchestrator (flagging now):** the shared tail of
`_render_creative_artifacts` unconditionally calls `svg_export.render_creative_svg(image_ref=...)`,
which requires a photo. SN has no photo — the SN branch must write `creative.svg` from
`build_nikah_svg(...)` and skip `render_creative_svg` (and the `_source_image` loop's
`GENERATED_VECTOR` TODO at creative_generation.py:272 becomes "SN renders its own imagery; no
source image needed"). This is a serialized wire-in decision, not part of this build.

---

## 4. Modesty QA check (`modesty` guardrail)

`modesty_report(svg_text, *, source_kind) -> list[str]` — pure, no network, no vision. Registered
into the QA gate at wire-in time (a new check invocation alongside `run_brand_qa`; checks.py is NOT
edited in this build).

What it asserts, in order:

1. **Source discipline** — `source_kind` must be `"generated_vector"`. Any of
   `licensed_stock` / `ai_realistic` / `product_cutout` / `brand_placeholder` is an immediate fail
   (`modesty: source {kind} is not approved for simply-nikah`). `"ai_illustration"` also fails in
   v1 — see (4).
2. **No raster imagery** — parse the SVG; every `<image>` element must sit inside a group with
   `data-role="wordmark"` (the only approved raster: the supplied logo). Any other `<image>`
   (jpeg/png/webp/data-URI) fails: real photos can only enter the document as raster embeds, so
   "no unapproved raster" structurally implies "no real photos of people" and "no face pixels".
3. **Faceless-by-construction audit** — every `<g data-figure="true">` must also carry
   `data-faceless="true"`. Primitives set both attributes at construction; this assertion catches a
   future primitive (or hand-edited SVG from the canvas editor) that adds a figure without going
   through the approved vocabulary. Figure groups missing the attribute pair fail.
4. **AI-illustration fallback path is the real risk** — for `GENERATED_VECTOR` output the check is
   structural and trivially satisfied (the engine can only compose approved faceless primitives;
   there is nothing to pixel-scan). The profile's second-ranked source, `AI_ILLUSTRATION`, CAN
   produce faces/immodest content and cannot be verified structurally. v1 decision: **fail closed**
   — `modesty_report` rejects `source_kind="ai_illustration"` until a vision-based face/modesty
   detector (creative/vision) exists for that path. This keeps the guardrail honest instead of
   pretending a structural check covers generated pixels.

Pass = empty list, matching the `QAReport.failures` string convention
(`"modesty: <detail>"` prefixes).

---

## 5. File plan (new files ONLY)

| File | Contents |
|---|---|
| `creative/render/nikah_primitives.py` | §1 vocabulary: 6 implemented v1 primitives + 3 helpers + 6 deferred stubs (`raise NotImplementedError`), palette fallback constants, pack-seeded path constants with license/source comments. |
| `creative/render/nikah_templates.py` | §3: context, 2 archetype classes, `NIKAH_TEMPLATES` + `TEMPLATES.update`, `build_nikah_html`, `build_nikah_svg`, `render_nikah`, `modesty_report`. |
| `tests/test_nikah_templates.py` | Day-1 stub per project convention; grow toward: archetype registry presence, copy validation (missing `highlight` fails loud), SVG layer-id set + `data-bbox` presence, modesty_report pass/fail cases, exact-dims PNG (browser-gated like test_glo2go_templates). |

**ZERO edits** to `api/services/creative_generation.py`, `creative/export/svg.py`,
`creative/qa/checks.py`, or any other existing file. The wire-in (sibling branch + QA registration
+ creative.svg source swap) is a separate serialized step owned by the orchestrator.

---

## 6. Open operator decisions / ambiguities in the profile

1. **Wordmark asset** — no logo file supplied. v1 renders "simply nikāh" typographically in
   `_SYSTEM_FONT`; visually this will NOT match the client's real wordmark. Need the actual
   wordmark SVG/PNG at onboarding (then it flows through `logo_ref`).
2. **Fonts** — profile explicitly says no families supplied. v1 = system font with TODO(M3);
   the "elegant script" Eid accent face is also unassigned (not needed for the 2 v1 archetypes).
3. **All hexes are approx** — already flagged in-profile; fallback constants carry the approx
   values until onboarding confirms.
4. **Vector-pack seeds** — which free pack for hands-forming-heart / hijabi silhouette / lantern
   path data? Needs a license-verified pick (CC0/free-commercial) before those paths are embedded;
   the primitive signatures don't change either way.
5. **4:5 format key** — SN's reference 1080×1350 uses the existing `carousel` preset (the only 4:5
   in `mimik_contracts.formats.PRESETS`). If a dedicated `ig_portrait` key is wanted, that is a
   contracts change outside this build.
6. **AI-illustration fallback** — v1 modesty gate fails closed on it (§4.4). Accept, or prioritize
   the vision modesty detector so the profile's ranked source #2 becomes usable.
