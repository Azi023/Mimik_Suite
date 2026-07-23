# Design-IQ Upgrade — the "perfectionist" creative intelligence layer

> Written 2026-07-24 in response to the operator's critique: the engine's creatives are
> formulaic ("photo + rounded panel + heading + body + CTA pill", same recipe every time).
> This doc is the plan to raise the engine's *creative design intelligence* — NOT a request
> to regenerate anything now. It sets the quality bar for M-01 (SN engine), M-03 (archetypes),
> and M-08 (QA critic), and adds a new pillar: a **design-critic** that gates on craft, not
> just mechanical correctness.

## 1. Diagnosis — why the output looks generated

1. **One compositional archetype per brand.** Glo2Go ≈ 2 templates; Simply Nikah / Island Cart = 0 (placeholder). No variety ⇒ everything rhymes.
2. **No per-piece art direction.** `creative/art_direction.py` writes an *image prompt*; composition is a fixed Python template. Nothing decides crop, scale-contrast, asymmetry, focal tension, or graphic devices per creative.
3. **QA checks correctness, not craft.** `creative/qa/checks.py::run_brand_qa` gates dims / safe-zones / contrast / logo-visibility. Nothing asks *"does this look like a senior designer made it?"* There is no taste critic in the loop.
4. **No reference-grounded taste.** The engine designs from nothing — the exact anti-pattern the `frontend-design`/`impeccable` skills exist to prevent. `creative/references/gather.py` + `fit_critic.py` exist but are STALE (not in the live path).
5. **System fonts.** The brand-font gap (Lane C / M-10) silently caps every creative — real design language is impossible on system type.

## 2. The honest ecosystem finding

The Claude ecosystem has **no installable, reputable skill or agent that generates or critiques social-media ad creative / brand art direction.** All the well-starred design tooling is product/web-UI (design systems, dashboards, landing pages, accessibility). Marketing skills that exist cover copy/CRO/strategy, not visual composition. The only "creative scoring" product (AdCreative.ai) is a closed vendor with an unverifiable self-reported accuracy claim.

**⇒ The perfectionist design-critic is a build, not an install.** But the building blocks are real and citable.

## 3. What to adopt (verified, with reputation signals)

### Install / adopt as reference
| Item | Source | Signal | Role |
|---|---|---|---|
| **impeccable** (Paul Bakaus) | github.com/pbakaus/impeccable | ~40k★, ~160k installs; author ex-Google DevRel / jQuery-UI | Most-adopted design skill. Lift its **brand-mode vocabulary** + "declare the system before the pixels" method + `/critique` (hierarchy + emotional resonance) as generator-side direction. UI-tuned — adapt the method, don't run it on JPEGs. |
| **designer-skills / visual-critique** (Owl-Listener) | github.com/Owl-Listener/designer-skills | ~1.9k★ | The most directly **encodable critic**: seven visual critiques (hierarchy, brand-consistency, composition, typography, color, affordance, density) → prioritized fix list. Fork it: drop UI-only axes (affordance), add ad axes (CTA prominence, thumb-stop, figure-ground, brand-recognition-without-logo). |
| **multi-persona-qa-reviewer** | *already in this environment* | in-repo | Adapt its **multi-persona → severity-triaged (P0–P3)** structure with creative personas: *senior art director · brand guardian · target-audience scroller · the client*. |
| **wondelai/skills** (marketing-cro) | github.com/wondelai/skills | community; book-derived (StoryBrand, Made to Stick, 1-Page Marketing) | For the **copy slot** (heading/body/CTA), which is also generic today. Frameworks are real (bestselling books); packaging is community. |

### Tools (the "manipulation" lever — call directly in the engine, not "skills")
| Tool | Why |
|---|---|
| **rembg (U²-Net)** | Subject cutout w/ hair-edge handling → cutout + drop-shadow + scene integration. **The concrete path off the "solid rounded panel" crutch.** Also unblocks Island Cart's product-cutout pipeline (M-02). OSS lib; free-tier-safe (constraint #7). |
| **Pillow / numpy treatments** | Duotone, grain, gradient-map, texture — art-directed photo treatments, programmatic. No skill to install; build in the engine. |
| **Remove.bg / Photoroom / Clipdrop** | Higher-quality cutout *as a service* — keep behind the swappable imagery adapter (paid; constraint #7). |

## 4. The scoring rubric (the actual "design IQ") — build-it-yourself, citable axes

These become the axes of the design-critic agent. All are well-recognized and defensible:

- **C.R.A.P.** — Contrast, Repetition, Alignment, Proximity (Robin Williams, *The Non-Designer's Design Book*). Grades any static composition. Directly attacks the formulaic panel: *is the CTA the highest-contrast element? is text grouped by meaning? is there real grid alignment?*
- **Gestalt figure-ground** — *does the subject separate from the ground WITHOUT a solid panel?* This axis is what rejects the "photo + white box" crutch.
- **Visual hierarchy** — the critic must name the 1st / 2nd / 3rd focal point and check it matches the marketing intent (hook → value → action).
- **AIDA** — Attention → Interest → Desire → Action as a message-structure axis layered on the visual.
- **Brand-token-diff (the one OBJECTIVE axis)** — diff the rendered creative's dominant colors / type against the stored `Brand.tokens`. Machine-checkable, no vision judgement needed.
- **Originality / anti-template** — *does this look generated? how close is it to the last N creatives for this client?* (penalize sameness).
- **Ad-specific** — thumb-stop (does it survive a 0.5s scroll?), CTA prominence, brand-recognition-without-logo.

Output format: severity-triaged (showstopper / gap / suggestion) — borrowed from the critique-skill pattern. Below-threshold ⇒ **reject + regenerate**.

## 5. Where it wires — the 3-tier intelligence layer

**Tier 1 — Art Director (pre-generation).** Elevate `art_direction.py` from prompt-writer to *composition-decider*: pick archetype, focal device, scale/contrast, negative-space plan, graphic devices — consulting the per-client style profile + references. Feed it impeccable's brand-mode method.

**Tier 2 — Reference-grounded taste.** Wire the STALE `references/gather.py` + `fit_critic.py` into the live path. Curate a per-brand moodboard of award-level references; compose against it so output inherits taste.

**Tier 3 — Design Critic (post-generation, the perfectionist gate).** NEW. A vision model scores the rendered PNG on the §4 rubric, triages severity, and rejects+regenerates generic output. Stacks *on top of* the mechanical `run_live_qa` (Lane A / M-08): mechanical = correctness, critic = craft.

**Enablers already on the roadmap that feed this:** SN vector engine (M-01, in flight) · more archetypes per brand (M-03) · brand fonts (M-10 / Lane C) · Island Cart cutout via rembg (M-02).

## 6. Recommended first three moves (when we build — not now)

1. **Stand up the design-critic (Tier 3)** by forking `designer-skills/visual-critique`'s seven axes → the §4 ad rubric, with the brand-token-diff objective axis first (cheapest, machine-checkable). This is the "perfectionist AI agent."
2. **Add rembg compositing** to the engine — cutout + shadow + treatment — to break the panel formula and unblock Island Cart.
3. **Wire references/fit-critic into the live path** (Tier 2) so generation is reference-grounded, and adopt impeccable's brand-mode method in Tier 1 art direction.

Copy quality (StoryBrand / marketing-cro) is a parallel, lighter win for the heading/body/CTA slot.
