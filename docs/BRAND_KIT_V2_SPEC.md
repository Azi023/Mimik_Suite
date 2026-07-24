# Brand Kit v2 — the per-client Brand Book (design spec)

> Status: DESIGN. Prototype at `scratchpad/brand-kit-prototype.html` (open in a browser).
> Reference: the @identitybyshirls "Sustain Health" digital brand book — tabbed, warm-editorial,
> premium, folder tabs, cream paper cards, mono uppercase labels. We match its *level of finish*,
> not its skin: the book chrome derives from each client's own palette.
>
> Grounding: `mimik-contracts/src/mimik_contracts/brand.py` (Brand/BrandTokens/ColorRole/
> Typography/LogoSpec/BrandLayout), `assets.py` (BrandAsset/AssetStudy),
> `creative/render/builtin_fonts.py` (the 9-family built-in library),
> `docs/STYLE_PROFILES.md` (real client data), `docs/BRAND_KIT_ONBOARDING.md` (Zaid's layout box),
> `docs/DESIGN_REFERENCES.md` (locked shadcn mono-admin system).

## 1. What it is

One premium, tabbed **brand book per client** — the showcase artifact of the whole engagement.
It is generated from live data the pipeline already holds (tokens, assets, discovery answers,
creatives) and it degrades gracefully: a day-1 client with only a name and one hex still gets a
book that looks *composed*, with tasteful placeholders instead of holes.

Two audiences, one document:
- **Studio view** (internal): every section editable; empty slots show "Add…" affordances.
- **Client view** (shared via the existing magic-link mechanism): read-only, edit affordances
  hidden, unfinished sections render as neutral "in progress" cards or collapse (rules in §5).

## 2. Tab structure (mirrors the reference)

| # | Tab | Contents | Primary data source |
|---|-----|----------|---------------------|
| 01 | **Brand Discovery** | Client / industry / timeline header; two-column list: Purpose, Mission, Vision, Personality, Brand Values, Tone of Voice, Key USP, Visual Competitor Analysis, Existing Brand Review, Target Audience | `Brand` (existing fields) + NEW `BrandDiscovery` |
| 02 | **Creative Direction** | Moodboard grid; "Colour Palette:" rationale paragraph; Visual Tone; How it aligns with the Personality; Uniqueness vs Competitors | NEW `CreativeDirection` + `BrandAsset(kind=reference_creative)` + `AssetStudy` |
| 03 | **Logo Suite** | Rows: Primary, Stacked, Wordmark, Icon, Social Icons (on coloured circles); clear-space + min-size from existing `LogoSpec` | NEW `logo_suite` slots + `BrandAsset(kind=logo)` |
| 04 | **Colours & Fonts** | Named palette grid (name + hex + role + one-line rationale per swatch); Font Suite (role → specimen); Patterns strip; **Download font pack** | `ColorRole` (extended) + NEW `FontRole` + builtin_fonts + NEW `BrandPattern` |
| 05 | **Applications** | Real-world mockups: business card, IG posts, phone, tablet | NEW `BrandApplication` + delivered `CreativeDoc`s |
| 06 | **Launch Templates** | Grid of ready social-post templates | NEW `LaunchTemplate` → `formats.PRESETS` / `CreativeDoc` |

## 3. Data model — additive changes to `mimik-contracts`

Everything below is **additive**; no existing field changes shape. Old brand JSON stays valid.

### 3.1 `ColorRole` — extend in place (named colour + rationale)

```python
class ColorRole(Model):
    name: str                          # EXISTS — role: "primary" | "ink" | "ground" | ...
    hex: str                           # EXISTS
    usage: str | None = None           # EXISTS
    display_name: str | None = None    # NEW — "Clinical Plum", "Heartbeat Red"
    rationale: str | None = None       # NEW — one line: WHY this colour is in the brand
    confirmed: bool = False            # NEW — formalises "(approx — confirm at onboarding)"
                                       #        from STYLE_PROFILES; False ⇒ provisional badge
```

A swatch with `hex` unset is impossible today (hex is required) — a *pending* colour (e.g.
Glo2Go's Soft Lilac, whose source hex was never supplied) is represented as a NEW
`PendingColor(name, display_name, rationale)` entry in `BrandKit.pending_colors`, rendered as a
greyed striped placeholder swatch. This keeps `ColorRole.hex` strict.

### 3.2 Logo suite — variant slots

```python
class LogoVariant(str, Enum):          # NEW enum (enums.py)
    PRIMARY = "primary"; STACKED = "stacked"; WORDMARK = "wordmark"
    ICON = "icon"; SOCIAL_ICON = "social_icon"

class LogoVariantSlot(Model):          # NEW
    variant: LogoVariant
    asset_id: str | None = None        # BrandAsset(kind=LOGO); None ⇒ placeholder slot
    bg_roles: list[str] = []           # which palette roles to demo it on (social circles)
    notes: str | None = None

# BrandTokens gains:
#   logo_suite: list[LogoVariantSlot] = Field(default_factory=list)   # NEW
# BrandTokens.logo (LogoSpec) STAYS — it is the compositor's primary slot; the book treats it
# as the PRIMARY variant when logo_suite is empty (back-compat rendering rule, not a migration).
```

### 3.3 Font roles (typed suite over the built-in library + uploads)

```python
class FontRole(Model):                 # NEW
    role: Literal["display", "heading", "subheading", "body", "accent", "arabic"]
    source: Literal["builtin", "uploaded"]
    builtin_key: str | None = None     # key from creative/render/builtin_fonts.py ("poppins"…)
    asset_id: str | None = None        # BrandAsset(kind=FONT) when source == "uploaded"
    weights: list[str] = []            # ["400", "700"]
    sample_text: str | None = None     # overrides the builtin preview_text

# BrandTokens.typography gains:
#   font_roles: list[FontRole] = Field(default_factory=list)          # NEW
# Typography.heading_font / body_font STAY as the engine's flat view; the kit editor keeps
# them in sync (heading role ⇒ heading_font) so the compositor needs no change in slice 1.
```

**Font pack download** — NEW endpoint `GET /api/brands/{brand_id}/font-pack` → zip of the
brand's `font_roles`: built-in families ship from `assets/fonts/builtin/` (Google-hosted OFL
families — include `OFL.txt` per family), uploaded fonts from `BrandAsset.local_path` with
`BrandAsset.license` echoed into a `LICENSES.txt`. Tenant-scoped query, audited like every
delivery. No external fetches.

### 3.4 The book itself — `BrandKit` attached to `Brand`

```python
class BrandDiscovery(Model):           # NEW — tab 01 (fields the Brand model doesn't have)
    purpose: str | None = None
    mission: str | None = None
    vision: str | None = None
    personality: str | None = None
    values: list[str] = []             # rendered as chips
    tone_of_voice: str | None = None   # long-form; falls back to Brand.brand_voice + tone_keywords
    key_usp: str | None = None
    visual_competitor_analysis: str | None = None
    existing_brand_review: str | None = None
    timeline: str | None = None        # "May – July 2026" engagement window
    # industry ⇒ Brand.niche, target audience ⇒ Brand.target_audience (reused, NOT duplicated)

class CreativeDirection(Model):        # NEW — tab 02
    moodboard_asset_ids: list[str] = []          # BrandAsset refs; AssetStudy supplies captions
    palette_rationale: str | None = None         # the "Colour Palette:" paragraph
    visual_tone: str | None = None
    personality_alignment: str | None = None
    competitor_differentiation: str | None = None

class BrandPattern(Model):             # NEW — tab 04 patterns strip
    name: str
    asset_id: str | None = None        # None ⇒ engine-generated preview / placeholder
    usage: str | None = None

class BrandApplication(Model):         # NEW — tab 05
    kind: Literal["business_card", "ig_post", "ig_story", "phone_app",
                  "tablet", "signage", "packaging", "other"]
    asset_id: str | None = None        # a delivered creative render or uploaded mockup
    creative_id: str | None = None     # link back to the CreativeDoc when it came from the pipeline
    caption: str | None = None

class LaunchTemplate(Model):           # NEW — tab 06
    name: str
    format_key: str                    # ties to formats.PRESETS / Job.format_key
    creative_id: str | None = None
    asset_id: str | None = None        # preview render

class PendingColor(Model):             # NEW — see §3.1
    name: str                          # role
    display_name: str | None = None
    rationale: str | None = None

class KitTheme(Model):                 # NEW — book chrome derivation (§6)
    mode: Literal["auto", "manual"] = "auto"
    ink_hex: str | None = None         # manual override; auto = darkest brand colour
    paper_hex: str | None = None       # auto = warm off-white constant

class BrandKit(Model):                 # NEW — Brand gains  kit: BrandKit = Field(default_factory=BrandKit)
    discovery: BrandDiscovery = Field(default_factory=BrandDiscovery)
    direction: CreativeDirection = Field(default_factory=CreativeDirection)
    pending_colors: list[PendingColor] = []
    patterns: list[BrandPattern] = []
    applications: list[BrandApplication] = []
    launch_templates: list[LaunchTemplate] = []
    theme: KitTheme = Field(default_factory=KitTheme)
    published: bool = False            # gates the client-facing share view
```

All asset refs are shape-validated with the existing `validate_asset_ref` (they flow into
render contexts). `BrandKit` edits are versioned like briefs (constraint 8 — non-destructive).
Client-visible sharing runs through the existing magic-link/portal mechanism — client remains an
untrusted principal; the book is read-only data, never an instruction channel (constraint 3).

### 3.5 What already exists (do NOT rebuild)

| Book need | Existing |
|---|---|
| Client name / industry / audience / voice / dos-donts / handles | `Brand` fields |
| Colour roles + hex + usage | `ColorRole` |
| Heading/body font + hierarchy | `Typography` |
| Primary logo + clear space + min size + assessment | `LogoSpec` |
| Logo placement / margins / header-footer / grid | `BrandLayout` (Zaid's layout box — shipped) |
| Uploaded logos/fonts/imagery/reference creatives (+ vision study) | `BrandAsset` + `AssetStudy` |
| Built-in font library (9 families incl. Amiri) | `creative/render/builtin_fonts.py` |
| Vetted aesthetic references | `Brand.references: Reference[]` |
| Real client content for the sample | `docs/STYLE_PROFILES.md` |

## 4. Named palette rules

- Every swatch shows: **colour block → display name → hex → role tag → one-line rationale**.
- `confirmed == False` ⇒ a small "provisional" badge (studio AND client view — honesty beats
  polish; it also nudges the onboarding confirmation).
- Colour without a hex ⇒ `PendingColor` ⇒ striped grey placeholder swatch with the name and
  "hex pending — confirmed at onboarding".
- Display names are proposed by the brief-drafter (LLM) at onboarding and human-edited —
  names are *brand voice*, so they go through the same review gate as copy.

## 5. Placeholder / empty-state rules (the core requirement)

Three tiers, applied per-field — a section never renders blank or broken:

1. **Missing text field** (mission, USP, rationale…)
   - *Studio*: dashed "ghost card" — muted prompt ("Add your mission — one sentence on why
     {client} exists") + `+ Add` affordance.
   - *Client view*: the row is **omitted**; if a whole tab has < 2 filled fields the tab shows a
     single neutral "This chapter is being written — arriving with your next review" card.
2. **Missing asset slot** (logo variant, moodboard tile, pattern, application, template)
   - *Studio*: the slot renders at full size as a labelled specimen placeholder (dotted frame,
     variant name, "Upload" affordance) — the suite always shows its full shape, so gaps read
     as *planned*, not broken.
   - *Client view*: filled slots render; empty slots render as quiet "In production" tiles
     (no upload affordance). If ALL slots are empty the section collapses per rule 1.
3. **Provisional data** (unconfirmed hex, unassessed logo) — rendered normally + badge (§4).

Hard rule: placeholders use the muted paper palette only — never error-red, never grey boxes
with broken-image icons. A placeholder must look *typeset*.

## 6. Design language & design-system reconciliation

**Recommendation: the brand book is its own editorial surface — not a mono-admin screen.**

- `docs/DESIGN_REFERENCES.md` locks shadcn mono-admin for the **app chrome** (nav, tables,
  forms). It also already separates surfaces by audience. The brand book is not an admin
  surface — it is a **deliverable**, like a rendered creative: it must carry the *client's*
  brand, and it doubles as a client-facing/marketing showcase ("this is what you get").
  Precedent in the locked doc itself: Filestage/Frame.io review canvases are allowed their own
  visual worlds inside the shell.
- Concretely: the book lives at `web/app/(app)/clients/[id]/brand-kit` **inside** the mono-admin
  shell (sidebar/topbar stay shadcn), but the kit canvas is a self-contained themed document —
  its own token scope (CSS vars on the canvas root), not the app's. The shared client view
  renders the same canvas full-bleed with zero admin chrome.
- **Editorial chrome derives from the client** (`KitTheme`, auto mode): ink = the brand's darkest
  colour, paper = a fixed warm off-white family, labels = monospace uppercase, headings = the
  brand's own heading font when available (else the book's serif). Fallback when a brand has no
  usable dark: the Mimik house theme (deep brick `#7A2E1F` + cream) — i.e. the reference's own
  look is our default skin. One system, per-client skinning — the same trick the creative
  engine already does with style profiles.
- Editing controls (inputs, dialogs, upload) remain shadcn components; they appear only in
  studio view, styled neutrally so the document stays the hero. Fable builds the screen from
  this spec + the prototype (per the locked build mechanism).

## 7. Template architecture — HTML-first, data-driven, modular

**The HTML template IS the single source of truth for the look.** The prototype
(`scratchpad/brand-kit-prototype.html`) is template v1: one self-contained document whose
content is entirely a projection of `Brand` + `BrandKit` + `BrandAsset` data, and whose skin is
entirely CSS variables. Iterate the look → edit the template. Change the content → edit the data.
The two never cross.

- **Section registry.** Each tab/chapter is a pluggable module: a `<section data-kit-section="{key}">`
  block paired with a data selector (`discovery`, `direction`, `logo_suite`, `colours_fonts`,
  `applications`, `launch_templates`). Adding a chapter = registering one section (template block +
  selector); removing/reordering is registry order. No section may reach into another's data.
  In `web/` each section becomes one server component; the same blocks render in the export SSR.
- **Theme scope.** All look tokens live on the canvas root as CSS custom properties, written from
  `KitTheme` (§6). Re-skinning a client's book — or the Mimik house fallback — is a token swap;
  zero markup changes.
- **Self-contained by contract.** The rendered book references no external hosts (fonts and assets
  are served/inlined locally). This is what makes Playwright renders deterministic and the client
  share view safe.
- **Empty states are template-owned.** The placeholder tiers of §5 are template logic driven only
  by field presence — the data layer never stores "placeholder" values.

## 8. Exports & sharing (one template → every format)

All exports render the SAME HTML template through the **existing Playwright stack**
(`creative/render/compositor.py` already drives HTML→PNG for creatives — reuse, don't rebuild).
Every export is tenant-scoped, audited, and recorded as a `Delivery` like any other artifact.

| Surface | Mechanism |
|---|---|
| **PDF (full book)** | `GET /api/brands/{brand_id}/brand-book.pdf` — Playwright `page.pdf()` over the SSR'd template with `media: print`. The template ships print CSS: tabs/nav hidden, masthead = cover page, each `data-kit-section` breaks to a new page, shadows/motion stripped, studio-only affordances (+ Add / Upload) hidden. Prototype already renders print-clean — `⌘P` it to preview the PDF. |
| **PNG per section/page** | `GET /api/brands/{brand_id}/brand-book/{section_key}.png` — Playwright element screenshot of `[data-kit-section="{key}"]` at export width (2× scale). Same path the compositor already uses for creatives. |
| **Hosted share link** | Mirror the client-portal **magic-link** pattern: `BrandKit.published` gates it; a signed, expiring slug serves the **client view** (§5 rules — read-only, no edit affordances, neutral in-progress tiles). Client remains an untrusted principal: the shared book is rendered data only, never an editor. |
| **Launch-template images** | Each `LaunchTemplate.creative_id` points at a `CreativeDoc`; its image is produced by the **existing creative render pipeline**, not by the book. The book embeds the delivered render; "export this template" = the creative's own PNG delivery. The tab is a window onto the pipeline, not a second renderer. |

Ordering note: PDF/PNG export needs the SSR'd template (slice 6 below can land before the full
editor set — export only requires read-only sections).

## 9. Build order (smallest first slice → full)

1. **P1-KIT-TOKENS** — contracts: extend `ColorRole` (+`PendingColor`), add `FontRole`,
   `LogoVariant`/`LogoVariantSlot`, `BrandKit` scaffold on `Brand`. Additive migration only.
   Test stubs day 1. Then the **Colours & Fonts tab read-only** (data already exists for all 3
   dogfood clients) + **font-pack zip endpoint**. Smallest visible win; dogfood on Glo2Go.
2. **P2-KIT-LOGOS** — Logo Suite tab: variant slots + upload wiring (`BrandAsset kind=LOGO` +
   variant tag) + placeholder states + social-circle rendering.
3. **P3-KIT-DISCOVERY** — `BrandDiscovery` editor + tab 01; brief-drafter pre-fills from the
   existing brief pipeline; ghost-card empty states.
4. **P4-KIT-DIRECTION** — Creative Direction tab: moodboard from `reference_creative` assets
   (AssetStudy captions), rationale paragraphs.
5. **P5-KIT-SHOWCASE** — Applications + Launch Templates wired to delivered `CreativeDoc`s and
   `formats.PRESETS`; CSS-frame mockups (card/phone) around real renders.
6. **P6-KIT-EXPORT** — SSR the template + Playwright PDF (`brand-book.pdf`) and per-section PNG
   endpoints via the existing compositor stack (§8). Print CSS ships with slice 1's template.
7. **P7-KIT-SHARE** — `published` flag + magic-link client view (read-only rules of §5).
   This is the piece that "gives some look to our website".

Each slice dogfoods on a real client (constraint 10): Glo2Go for 1–2, Simply Nikah for 3–4
(Amiri/arabic font role exercises the font suite), Island Cart for 5.
