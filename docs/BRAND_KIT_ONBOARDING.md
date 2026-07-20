# Brand-kit onboarding + designer controls — product spec

> Source: Zaid Hutch (2026-07-20), designer perspective. This is the spec for the **new-client
> onboarding flow** and the **designer-grade creative controls** to build in the frontend session.
> Grounded against the existing data model — most of the brand-kit spine already exists; the
> **layout box** (logo position, header/footer, margins) and the **designer selection controls**
> are the genuinely new pieces. Status column marks EXISTS vs NEW.

## 1. Onboarding flow (new client)

```
Brand → Brand Kit → Content Pillars → Style reference
```

| Step | What it captures | Data model | Status |
|---|---|---|---|
| **Brand** | name, niche, audience, voice, dos/donts, handles | `Brand` (contracts `brand.py`) | EXISTS (API); no UI |
| **Brand Kit** | colors, typography, logo — see §3 | `BrandTokens` = `colors: ColorRole[]`, `typography: Typography`, `logo: LogoSpec` | EXISTS + **extend** (add Layout) |
| **Content Pillars** | the recurring content themes | `ContentPillar` (`POST /pillars`, `is_custom`) | EXISTS (API); no UI |
| **Style reference** | vetted mood board / example creatives | `Brand.references: Reference[]` + `BrandAsset(kind=reference_creative)` + fit-critic | EXISTS (ingest + critic); no UI |

**Onboarding UI = NEW** (a stepper wizard). Backend endpoints exist for every step; this is a
frontend build. Reference: shadcn form/stepper primitives (see `docs/DESIGN_REFERENCES.md`).

## 2. Content creation flow

```
Static  →  Content pillar  →  Content reference & description (optional)  →  editable
```

- **Static** = the format (IG post / poster / story…) — `Job.format_key` (formats.PRESETS). EXISTS.
- **Content pillar** — tag the piece to a pillar (`Job.pillar_id`). EXISTS.
- **Content reference & description (optional)** — a per-job creative brief/reference. **NEW small
  field** — add optional `Job.reference_note` / attach a reference image to the job (today references
  live at brand level, not per-job).
- **editable** — the generated creative must be **editable** (text + layout), not a flat render. This
  is the big designer ask — see §4 (the 5-layer engine already separates text as an editable layer;
  the UI to edit it is NEW).

## 3. Brand Kit — extend with a **Layout** section (NEW)

Today `BrandTokens` = colors + typography + logo. Zaid wants a **Layout box** added under the brand
kit, so every creative composes from the brand's own layout rules:

| Control | Meaning | Status |
|---|---|---|
| **Logo position** | where the logo sits — a 3×3 grid pick (top-left … bottom-right) + size | NEW — add `LogoPlacement` to `BrandTokens` / a `Layout` model |
| **Header / footer** (optional) | reserved brand bar top and/or bottom | NEW |
| **Margins / safe zone** | the outer padding creatives must respect | NEW — `LayoutTemplate` has safe-zone logic; expose it as a brand-kit setting |

**Typography selection** — "choosing the right typography **based on the brand kit**": the brand's
`Typography` tokens constrain the font choices offered; the designer/engine picks within them.
EXISTS as tokens; the **selection UI + the "pick within brand" rule** is NEW.

**Image selection** — "choosing the right image **based on the brand kit**": imagery is filtered/
graded by the brand's `imagery_style` + palette (the QA contrast + fit-critic already enforce
on-brand). The **pick-an-image UI** wired to the brand's L1/L2 assets is NEW.

### Proposed contract change (for the FE session — not built yet)
```python
class LogoPlacement(str, Enum):
    TOP_LEFT = "top_left"; TOP_CENTER = "top_center"; TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"; CENTER = "center"; MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"; BOTTOM_CENTER = "bottom_center"; BOTTOM_RIGHT = "bottom_right"

class BrandLayout(Model):
    logo_placement: LogoPlacement = LogoPlacement.TOP_LEFT
    logo_scale: float = 1.0          # relative to the logo slot
    header: bool = False
    footer: bool = False
    margin_pct: float = 5.0          # safe-zone margin as % of the shortest edge

# add to BrandTokens:  layout: BrandLayout = Field(default_factory=BrandLayout)
```
The compositor (`creative/render/`) then reads `layout` when placing the logo slot, header/footer
band, and safe zone. **Editable text** already exists as `LayerKind.L4_MESSAGE` (real editable text,
pixel-perfect) — the FE just needs an inline text-edit control bound to that layer.

## 4. Designer capabilities & the 17 principles

Zaid wants the engine + the review UI to respect designer fundamentals. Reference image saved at
`docs/design-refs/17-design-principles.png` — the **17 Key Principles of Design**:

> Alignment · Hierarchy · Contrast · Repetition · Proximity · Balance · Color · Space · Emphasis ·
> Proportion · Rhythm · Pattern · Movement · Variety · Unity · Lines · Shapes

**How they map to what we have / need:**
- **Contrast** — already enforced by the QA critic (`creative/qa/contrast.py`, WCAG + scrim). ✅
- **Alignment / Proximity / Balance / Space / Proportion** — belong in the **layout templates**
  (`creative/render/templates.py` safe-zones/grid) + the new `BrandLayout` margins. Partly EXISTS.
- **Hierarchy / Emphasis** — headline vs subhead vs CTA sizing in the template + copy layer. EXISTS.
- **Color** — brand palette tokens + on-brand grading. EXISTS.
- **Repetition / Pattern / Unity / Rhythm / Variety / Movement / Lines / Shapes** — the aesthetic
  layer; today implicit in templates, could become an explicit **art-direction rubric** the QA
  critic and the taste-ranker score against. NEW (rubric extension of `mimik-knowledge` rubrics).

**Action for the FE/creative session:** (a) add `BrandLayout` to the brand kit + wire the compositor;
(b) inline **editable text** on L4 in the review UI; (c) a **logo-placement picker** (3×3) + margin
control in the brand-kit editor; (d) extend the QA rubric toward the principle checklist above.

## 5. Scope note
These are **product/creative-engine** features (brand kit, onboarding, creative editor) — distinct
from the IAM/admin work. They belong to the **frontend + creative-engine session**. Backend spine for
brand/pillars/references/editable-text already exists; the NEW backend bits are small (`BrandLayout`,
per-job reference). Build order suggestion: onboarding wizard → brand-kit editor (with Layout box) →
creative review/editor (inline text + logo placement) → art-direction rubric.
