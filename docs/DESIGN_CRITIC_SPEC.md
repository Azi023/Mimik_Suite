# Design Critic — Build Spec

> Child of `docs/DESIGN_IQ_UPGRADE.md` (Tier 3). Written 2026-07-24 after operator greenlight
> "after further improvements (the critique needs to improve as well)". This is the buildable
> spec for the post-generation vision critic. It is a planning doc — no code lands from it
> until the build order in §6 starts.

## 0. The bar the critic enforces (operator's framing, verbatim intent)

- The engine's geometric-vector output is acceptable **only as an L1/L2 base-template layer**
  — scaffold, not deliverable.
- The **end-product finish** is what the reference creatives show: rich AI-illustration
  (faceless hijabi + man match cards joined by connector lines, phone-in-hand with foliage,
  soft gradients, real depth). Per `docs/STYLE_PROFILES.md` §1, that is the profile's
  *secondary* image source (`AI-illustration`) doing the craft on top of the vector scaffold.
- The critic's job is to hold output to **that** finish bar and reject anything that
  "looks like a code-assembled template."

Concrete failures it must catch (from the operator's live critique of v1):

| ID | Failure | What the critic must see |
|---|---|---|
| F1 | Lattice backdrop too heavy on light ground | Ornamental pattern competing with message; whitespace guardrail violated (SN: "geometric pattern fills must not overwhelm") |
| F2 | Broken symbol composition (shield+crescent reads as a glitch) | A composed symbol whose parts don't resolve into one recognizable icon |
| F3 | Meaningless iconography (hands-heart blob) | A shape that cannot be named by a viewer in ~1s |
| F4 | "Both look like the exact same template" | Two creatives for the same client sharing layout skeleton, hero device, and palette distribution |

Every axis anchor in §2 traces back to at least one of F1–F4 or a reference-creative virtue.

---

## 1. Role in the pipeline

### 1.1 Position

```
art_direction → render (L1..L5) → PNG
      → run_live_qa  (creative/qa/live.py — MECHANICAL: dims, safe zones,
      |                contrast, logo visibility, source guardrails. Correctness.)
      → DESIGN CRITIC (NEW: creative/qa/critic.py — CRAFT: scores the rendered
      |                PNG on the §2 rubric. Sits ABOVE run_live_qa; only runs
      |                on creatives that already passed mechanical QA.)
      → pass  → ops board review (existing flow)
      → fail  → reject + regenerate loop (§1.2)
```

Rules:
- The critic **never sees** a creative that failed `run_live_qa` — mechanical failures are
  cheaper to detect and regenerate without burning a vision call.
- The critic scores the **rendered PNG** (what a scroller sees), not the SVG/manifest. The
  manifest is supplied as *context* (archetype used, layer recipe, brand id) so verdicts can
  name what to change, but the grade is on pixels.
- Input/output are `mimik-contracts` models (constraint #1): `CriticRequest`
  (png ref + manifest + brand tokens + style-profile id + last-N creative thumbnails) and
  `CriticReport` (per-axis scores, findings, verdict, persona notes). No ad-hoc dicts.
- The critic runs in a **low-privilege context**: no tools, single-tenant inputs only
  (constraint #3). Client freeform text never enters the critic prompt as instructions.

### 1.2 The reject + regenerate loop

A failed verdict names *what kind* of failure dominated; the retry ladder branches on it.
Each attempt feeds the full `CriticReport` back into `art_direction` as structured
constraints ("lattice opacity max 12%", "replace composed shield+crescent with single-glyph
crescent") — a blind re-roll is forbidden.

| Attempt | Trigger | Action |
|---|---|---|
| 1 | Any fail | **Re-art-direct, same archetype.** Same layout family, corrected per findings (tone down lattice, swap broken symbol for an approved single motif, fix hierarchy). Cheapest fix; most F1/F2/F3 failures die here. |
| 2 | Fail again, dominant axis is HIERARCHY / COMPOSITION / ORIGINALITY | **Swap archetype.** Pick a different `layout_archetypes` entry from the style profile (e.g. Highlighted-Word Hero → Connected Match Cards). Directly attacks F4 sameness. |
| 2′ | Fail again, dominant axis is FINISH / ICONOGRAPHY | **Escalate the finish path** (§4): keep the vector scaffold as L1/L2 blueprint, generate an AI-illustration hero for the failing zone, recomposite. |
| 3 | Fail after 2/2′ | One more pass of whichever branch was NOT taken at attempt 2, if its dominant axis now applies; otherwise go straight to escape hatch. |
| — | 3 fails total | **Escape hatch.** Creative parks in a `NEEDS_ART_DIRECTION` task (existing Task type in the data spine) with the full critic history attached. Human decides. The loop never runs a 4th generation. |

Hard budget: **max 3 regenerations per creative** (initial render + 3 retries = 4 renders
ceiling). Every attempt and verdict is audited (constraint #8 — actor = `design-critic`,
timestamped, versioned; rejected renders are kept, not destroyed).

Instant-fail bypass: a **guardrail breach** (face visible, immodest content, owner shown,
wrong product/price — the style profile `hard_guardrails`) skips the ladder nuance: the
render is quarantined (never surfaces in the client portal), and regeneration restarts at
attempt 1 with the breach named. Guardrail breaches don't consume "craft" retries — but the
same breach twice in a row parks the creative immediately.

---

## 2. The scoring rubric

Forked from the installed `designer-skills` seven axes (`.claude/skills/critique-*`),
with `critique-affordance` **dropped** (UI-only) and `critique-information-density` merged
into COMPOSITION. Ad-specific axes added per the parent plan §4. Each axis is a gradeable
question with 1/3/5 anchors written for **social ad creative** (a 2 sits between 1 and 3, a
4 between 3 and 5 — anchor drift is resolved by "which anchor is it closer to").

Verdict math: weighted mean of A1–A8 on the 1–5 scale → `craft_score`.
**Provisional ship threshold: 3.8** (calibrated against the golden set, §3.2 — the number
moves, the mechanism doesn't). Independent of the mean, any **hard-fail condition** (marked
◆ below) rejects outright.

| # | Axis | Weight | Lineage |
|---|---|---|---|
| A1 | Brand-token-diff (objective) | 15% | critique-brand-consistency → made machine-checkable |
| A2 | Visual hierarchy | 15% | critique-visual-hierarchy + AIDA intent-match |
| A3 | Composition & figure-ground | 15% | critique-composition + critique-information-density + C.R.A.P. + Gestalt |
| A4 | Typography & color craft | 10% | critique-typography + critique-color |
| A5 | Iconography integrity & recognizability | 15% | NEW (F2/F3) |
| A6 | Finish: scaffold vs deliverable | 15% | NEW (the operator's L1/L2-vs-end-product bar) |
| A7 | Originality / anti-template | 10% | NEW (F4) |
| A8 | Thumb-stop & message (AIDA) | 5% | NEW (ad-specific) |

### A1 — Brand-token-diff (weight 15%, OBJECTIVE — no vision judgement)

**Question:** Do the rendered pixels' dominant colors and type roles match the stored
`Brand.tokens` within tolerance?

**Machine check (Pillow/numpy, no LLM):**
1. Quantize the PNG to its top-8 color clusters (k-means in Lab space, alpha-weighted).
2. For each cluster ≥3% coverage, compute ΔE2000 to the nearest brand token
   (`primary/ink/ground/accent/...` from `Brand.tokens`, e.g. SN `#FD62AD / #2B0A2E / #FAF7FB`).
3. `off_brand_coverage` = total coverage of clusters with ΔE > 10 to every token
   (photographic/illustration regions declared in the manifest are exempted by mask —
   an AI-illustration hero legitimately contains non-token colors; the *frame* around it
   doesn't).
4. Type check (when manifest metadata carries font family per text layer): rendered family
   ∈ brand-approved set; flag `unknown` while M-10 brand fonts are unresolved (do not fail
   on the known system-font gap — record it).

**Scoring (deterministic):**
- **5** — `off_brand_coverage` < 5%, every token role present that the archetype requires (CTA uses `cta_fill`, ink is ink).
- **3** — `off_brand_coverage` 5–15%, or one token role substituted by a near-neighbor (ΔE 10–20).
- **1** — `off_brand_coverage` > 30%, or a load-bearing brand color missing entirely (e.g. Island Cart with no Bold Orange).
- ◆ Hard fail: CTA or headline rendered in a color with ΔE > 20 from all tokens, or `off_brand_coverage` > 40%.

### A2 — Visual hierarchy (15%)

**Question:** Name the 1st / 2nd / 3rd focal point. Does that order match the marketing
intent hook → value → action, and is there exactly one entry point?

- **5** — One unmistakable entry point (highlighted word, hero symbol, gag headline) that is the hook; second read is the value/support line; CTA is findable within the first eye-path. Matches the archetype's stated intent (e.g. SN Highlighted-Word Hero: the plum-boxed word lands first).
- **3** — Entry point exists but is contested by one competing element (a decorative motif or over-weighted badge pulls the eye); reading order recoverable but not enforced by size/contrast (size steps < 1.5× between levels).
- **1** — Attention scatters: 3+ elements at equal weight, CTA visually quieter than decoration, or the first read is an ornament (F1: the lattice reads before the message).

### A3 — Composition & figure-ground (15%)

**Question:** Graded via C.R.A.P. + Gestalt figure-ground: does the subject separate from
the ground *without* leaning on a solid panel, is the canvas grouped by meaning, aligned to
a real grid, and is density controlled (ornament concentrated, not smeared)?

- **5** — Subject/ground separation achieved by value, color, or depth (glow, soft shadow, gradient) — no white-box crutch; elements group by proximity into ≤3 meaningful clusters; margins and internal alignments consistent; quiet zones alternate with compact groups (SN: "generous soft-pink negative space", ornament does not tile the whole canvas).
- **3** — Separation works but relies on a panel where the profile allows better (or one alignment axis drifts); density mostly controlled but one region is cluttered or one motif is over-scaled; whitespace present but not protective.
- **1** — Figure and ground merge (light vector on light ground with a busy pattern behind — F1); ornament distributed evenly edge-to-edge; no discernible grid; text groups split from their referents.
- ◆ Hard fail: background pattern/texture covers > 60% of the canvas at high contrast on a profile whose principles name whitespace as load-bearing (SN, Glo2Go).

### A4 — Typography & color craft (10%)

**Question:** Does the type behave like the profile's typography contract (weight, case,
emphasis device) and does the color usage have intention (roles, not decoration)?

- **5** — Heading character matches the profile (SN: bold display in Deep Plum, one decisive word reversed out in a plum box; IC: huge condensed caps); body is subordinate and legible; color roles used as roles — accent appears only at emphasis points; any gradient/glow stays inside the profile's `effect_vocabulary`.
- **3** — Right families/weights but flat execution: highlighted-word device missing where the archetype calls for it, tracking/leading uneven, accent color used in 4+ places so it stops signalling.
- **1** — Case/weight contradict the profile (sentence-case meme hook on Island Cart; harsh black text on SN), text sizes within 10% of each other across hierarchy levels, or effects outside the profile vocabulary (heavy drop shadows on SN).

### A5 — Iconography integrity & recognizability (15%)

**Question:** Can every symbol on the canvas be **named by a stranger in ~1 second**, and do
composed symbols resolve into one coherent icon?

The critic must literally attempt the naming test: for each iconographic element, state what
it is. "I can't tell" is a finding, not a shrug.

- **5** — Every motif instantly reads (crescent is a crescent, match cards are people cards, lantern is a lantern); composed symbols (shield *containing* crescent) read as one designed mark with consistent stroke/corner language; motifs are drawn from the profile's motif list.
- **3** — All symbols nameable but one is generic/clip-art-grade, or a composed symbol reads as two overlapping shapes rather than one mark (near-F2); stroke weights inconsistent across icons.
- **1** — Any symbol fails the naming test (F3: the hands-heart blob), or a composition reads as a rendering error (F2: shield+crescent glitch).
- ◆ Hard fail: a symbol that reads as a glitch/artifact (F2-class) — this is a showstopper regardless of the weighted mean, because it single-handedly makes the piece look machine-broken.

### A6 — Finish: scaffold vs deliverable (15%) — *the operator's bar*

**Question:** Does this read as a **finished creative** a client would pay for, or as the
L1/L2 vector scaffold showing through? Evidence of finish: depth (soft gradients, glow,
layered planes), richness in the hero (illustration-grade figures/scenes, not primitive-
assembled avatars), and at least one crafted moment a template couldn't produce.

- **5** — Reference-creative grade: illustration hero with real depth (phone-in-hand with foliage; hijabi+man match cards with modeled clothing folds and connector lines), soft gradient atmosphere, the vector system present only as *supporting* frame/devices.
- **3** — Competent hybrid: vector scaffold visible but dressed — gradient ground, glow behind the hero, decent avatar cards — yet the hero is still primitive-assembled; a designer would call it "clean template," not "crafted."
- **1** — Naked scaffold: flat fills, primitive shapes as the hero, uniform stroke geometry everywhere — visibly code-assembled (the v1 pair).
- ◆ Hard fail: the piece is *entirely* engine-vector on a profile whose reference finish is illustration-grade AND A6 ≤ 2 → the retry must take the 2′ escalation branch (§4), not another vector re-roll.

### A7 — Originality / anti-template (10%)

**Question:** Placed next to the last N (default 8) shipped/attempted creatives for this
client: does it read as a new piece from the same brand, or the same template refilled?

Assisted by a cheap objective signal: layout-skeleton similarity (grid of the manifest's
layer bounding boxes, cosine similarity vs the last N manifests) computed pre-vision; the
vision pass confirms or overrides.

- **5** — Different archetype OR a genuinely different execution of the same archetype (new hero device, different negative-space plan, different emphasis mechanism); shares brand DNA, not brand *layout*.
- **3** — Same archetype with real variation in one dimension (hero swapped but skeleton identical, or vice versa); a follower would notice the rhyme but not call it a repost.
- **1** — F4: swap the copy and it's the same file — same skeleton, same hero class, same palette distribution as a recent creative (manifest-skeleton similarity > 0.9 corroborates).

### A8 — Thumb-stop & message (5%)

**Question:** At feed size for 0.5 seconds: does something arrest the scroll, and does the
piece then deliver Attention → Interest → Desire → Action in that order?

Graded on a downscaled render (~350px wide) — the critic sees what the feed shows.

- **5** — A single high-contrast moment survives the 0.5s test at feed size (the plum-boxed word, the oversized gag, the striking hero); headline legible at thumbnail; AIDA chain complete with a soft-or-hard CTA per the profile's copy voice.
- **3** — Stops the scroll only for an already-interested viewer; headline legible but the hook is generic; CTA present but limp.
- **1** — Nothing arrests: even-weighted composition at thumbnail scale, headline illegible below full size, or no action step at all.

### Verdict assembly

```
craft_score = Σ (axis_score × weight)            # 1.00–5.00
verdict     = HARD_FAIL   if any ◆ condition     # regardless of mean
            = PASS        if craft_score ≥ T     # T = 3.8 provisional
            = BORDERLINE  if T − 0.4 ≤ craft_score < T   → devil's-advocate pass (§3.1)
            = FAIL        otherwise
dominant_failure_axis = lowest weighted-contribution axis among scores ≤ 2
                        (drives the §1.2 retry branch)
```

Every FAIL/HARD_FAIL must cite, per finding: **element + axis + which anchor it matched +
fix direction** (the designer-skills Observation/Problem/Fix format). A rejection without a
nameable element is invalid and is treated as PASS-with-warning (§3.1).

---

## 3. How the critique itself improves (the operator's explicit ask)

### 3.1 False-reject protection — don't kill bold-but-good

1. **Failures are named patterns, not taste.** An axis may only be scored ≤2 by matching a
   concrete anchor/failure pattern on a nameable element. "Feels off," "too unusual,"
   "unconventional layout" are not failure patterns. Boldness per se cannot lose points —
   only its side effects can (illegibility, guardrail breach, hierarchy collapse), and those
   have their own anchors.
2. **Devil's-advocate pass on BORDERLINE.** Scores within 0.4 below threshold trigger a
   second, isolated pass with the opposite mandate: "argue why this should ship; find the
   intent behind each flagged choice." If it rebuts the dominant findings, verdict flips to
   PASS-with-notes (notes still reach the ops board). This mirrors the impeccable-critique
   principle of isolated assessments that must not see each other's output before synthesis.
3. **Findings before scores.** The vision pass first writes observations (what is where,
   what reads first, what each symbol is), *then* grades. Scoring prompts never contain the
   threshold value, so the model can't steer to it.
4. **Asymmetric cost accounting.** A false reject costs a regeneration; a false pass costs
   client trust. The threshold is calibrated (§3.2) to favor recall on F1–F4-class failures
   while the devil's-advocate pass absorbs the false-reject pressure — rather than lowering
   the bar itself.

### 3.2 Golden-set calibration (lives in `mimik-knowledge`)

- **Composition (12–20 items, per brand where possible):**
  - The operator's **reference creatives** (the illustration-finish exemplars) → expected 4.5–5 on A6, PASS.
  - The **rejected v1 pair** (lattice-heavy / glitch-symbol) → expected FAIL with F1/F2/F3 findings named.
  - 3–5 **mid-grade** pieces (competent-but-template) → expected BORDERLINE/3s on A6/A7.
  - 2–3 **bold-but-good** items (unconventional layout that works) → expected PASS. These are the false-reject tripwires.
- **Calibration procedure:** run the critic on the full set; require (a) correct
  rank-ordering by craft_score, (b) verdict agreement with the operator's recorded verdict
  on every item, (c) the v1 pair's findings to name F1/F2/F3 explicitly. Tune weights and T
  until all three hold. Record the tuned values in the golden set's manifest.
- **Regression gate:** any change to the critic prompt, rubric weights, or vision model
  re-runs the golden set (an eval in `mimik-knowledge/evals`); a verdict flip on any golden
  item blocks the change. The golden set only grows — every operator override (§3.3)
  is a candidate new item.

### 3.3 Feeding the learning loop

- Every `CriticReport` is persisted against the CreativeDoc version (constraint #8).
- **Operator/client overrides are the prime signal:**
  - *Approved despite critic FAIL* → false-reject case: attach to golden set as a PASS item; the dominant axis's anchors get reviewed via the `/missed-pattern`-style loop.
  - *Rejected/edited despite critic PASS* → false-pass case: the human's stated reason becomes a new failure pattern candidate on the matching axis; item joins the golden set as FAIL.
- **Per-client PreferenceProfile writeback:** axis-level deltas between critic verdicts and
  human decisions accumulate per client (e.g. "SN operator tolerates denser ornament than
  A3 anchor 3 assumes" → a per-client anchor modifier, bounded so it can never sink below
  the Mimik house floor: no client modifier may move a hard-fail condition or drop any
  axis's effective bar below anchor 2).
- Cadence: recalibrate T per brand once ≥10 human-reviewed verdicts exist for that brand.

### 3.4 Multi-persona review → severity-triaged verdict (not one flat score)

Adapting the in-repo `multi-persona-qa-reviewer` structure (persona walk → P0–P3 triage) with
four creative personas. Each persona reviews the same PNG but owns different axes:

| Persona | Owns | Asks |
|---|---|---|
| **Senior art director** | A2 A3 A4 A6 | "Would I put my name on this? What's the one craft move it's missing?" |
| **Brand guardian** | A1 A5 + hard_guardrails | "Is every pixel on-token? Is every symbol *ours* and unbroken? Any modesty/credibility breach?" |
| **Target-audience scroller** | A8 A7 | "Scrolling at feed speed — did I stop? Have I seen this exact post from them before?" |
| **The client** | cross-cutting | "Did I pay for this, or did a tool spit it out?" (the F4/A6 gut check, in the client's voice) |

Findings are triaged, borrowing the P0–P3 ladder:

- **P0 showstopper** → HARD_FAIL regardless of score: guardrail breach, F2-class glitch symbol, unreadable headline at feed size.
- **P1 gap** → caps the owning axis at 2: heavy-lattice figure-ground failure, same-template verdict from the scroller, dead CTA.
- **P2 suggestion** → caps the owning axis at 4: limp hook, one clip-art-grade motif, uneven margins.
- **P3 polish** → no score effect; carried into the report for the ops board.

Score assembly runs *after* triage: persona findings set the caps, then axes are graded
within them. Result: a verdict that says "P0: shield+crescent reads as a glitch (A5, brand
guardian)" instead of an unexplainable 3.1. Implementation note: personas are sections of
one vision call in v1 (cost), splitting into isolated calls only if calibration shows
persona bleed — the golden set decides.

---

## 4. Escalation: L1/L2 base → L4/L5 finish

The path a creative takes when it fails on FINISH (A6) or ICONOGRAPHY (A5) but its bones
(A1/A2/A3) pass — i.e. the layout works, the craft layer doesn't.

### 4.1 The mechanism

1. **Keep the scaffold as blueprint.** The passing vector composition (L1 ground, L2
   frame/devices) is frozen as the layout contract: hero bounding box, negative-space plan,
   text zones, palette roles. It is no longer the deliverable — it is the brief.
2. **Generate the finish layer.** The failing zone (hero symbol / hero scene) is regenerated
   through the profile's secondary source — for SN, `AI-illustration` (`image_sources[1]`):
   a flat-vector-style, faceless illustration prompted from (a) the art-direction record,
   (b) the frozen hero bbox + palette hexes, (c) the critic's findings ("replace composed
   shield+crescent"; "hero must read at thumbnail").
3. **Recomposite.** The illustration lands as the L2/L3 hero; L4 text and L5
   CTA/logo/badges remain **code-composited** (text is never rasterized into the AI image —
   that keeps copy editable, QA-checkable, and immune to AI text-mangling).
4. **Full re-gate.** The escalated render goes back through `run_live_qa` **and** the
   critic. Escalation consumes one retry from the §1.2 budget; it does not get a fresh loop.

### 4.2 Constraint #7 — no paid APIs (the gate)

- All illustration generation routes through the existing swappable adapter layer
  (`creative/adapters/router.py`): `choose_backend(purpose="hero")` →
  `ensure_spend_approved(backend)`. Paid backends raise `PaidImageSpendNotApproved` unless
  explicitly approved — the critic never overrides that gate.
- Order of attempts: free-tier / subscription-browser backends first (`gemini_free`,
  browser adapters); paid API only when the spend flag is set. "Sub now → API later"
  remains a config change, exactly as the adapter contract promises.
- **No silent downgrade:** if no approved backend is available, the creative does NOT ship
  as vector-only after an A6 hard fail — it parks in `NEEDS_ART_DIRECTION` with the critic
  report stating "finish escalation blocked: no approved image backend." A human decides
  between shipping the scaffold consciously or approving spend.

### 4.3 SN modesty guardrails on the AI-illustration path

Non-negotiable, enforced at three points:
1. **Prompt-side:** every SN illustration prompt carries the profile's hard guardrails as
   constraints — faceless or silhouette figures only, modest dress/hijab, no real-photo
   style, no immodest content. Client freeform text fills only the constrained content slot
   (constraint #3), never the guardrail block.
2. **Post-generation vision check (pre-composite):** a cheap dedicated pass on the raw
   illustration — face detected? skin/modesty breach? photorealistic-human style? Any hit →
   the image is discarded and never persisted into the CreativeDoc, never shown in any
   portal. One re-prompt allowed; second breach parks the creative.
3. **Existing mechanical gate:** the composited result still passes
   `run_live_qa`'s source-guardrail checks (`_source_guardrail_failures`) — AI-illustration
   is an approved SN source, so this verifies routing, and the critic's brand-guardian
   persona re-checks modesty on the final pixels.

---

## 5. New surface summary (what gets built, where)

| Piece | Location | Notes |
|---|---|---|
| `CriticRequest` / `CriticReport` / `AxisScore` / `PersonaFinding` | `mimik-contracts` | Schema-first (constraint #1). `CriticReport` carries verdict, per-axis scores+anchors matched, findings (element+axis+anchor+fix), dominant_failure_axis, attempt number. |
| `creative/qa/critic.py` (+ `tests/test_critic.py` day 1) | this repo | Orchestrates: token-diff (pure Pillow/numpy) → vision pass via existing `creative/vision/gemini_vision.py::generate_vision` (free-tier, constraint #7) → verdict assembly. Supersedes the stale `references/fit_critic.py` verdict shape (reuse its sanitize/JSON-verdict plumbing where it fits). |
| Rubric prompts + persona blocks | `mimik-knowledge` (prompt library) | Versioned; every change re-runs the golden-set eval. |
| Golden set + calibration eval | `mimik-knowledge` (golden set / evals) | §3.2. |
| Retry-ladder wiring | `creative/pipeline.py::generate_creative` | After the existing `run_live_qa` call; ladder state on the Job/Task records. |

---

## 6. Build order

### Slice 1 — the honest first cut (recommended start)

**Brand-token-diff (A1) + one vision axis (A5 iconography) on a handful of real creatives, advisory-only.**

- Why these two: A1 is fully objective (pure Pillow/numpy vs `Brand.tokens` — zero vision
  cost, zero calibration risk) and A5 is the axis that catches the operator's two loudest
  named failures (F2 glitch symbol, F3 meaningless blob) with the simplest possible vision
  prompt ("name every symbol; flag any you can't name or that reads as broken").
- Scope: `CriticReport` contract (minimal: two axes + findings + advisory verdict),
  `creative/qa/critic.py` with the two axes, run manually over ~6 real creatives — the
  rejected v1 SN pair + the operator's reference creatives + 1–2 Glo2Go pieces.
- Exit test: the v1 pair FAILS with F2/F3 named; the reference creatives PASS both axes.
  If that doesn't hold, fix the prompt before building anything wider.
- **No pipeline gating yet** — verdicts are logged next to the CreativeDoc, compared with
  the operator's live opinion. Advisory mode is the calibration data collector.

### Slice 2 — full rubric, still advisory
All eight axes + the four-persona structure (single vision call, sectioned) + severity
triage. Stand up the golden set from Slice-1 material + operator verdicts; calibrate
weights and T per §3.2. Exit: golden set rank-order + verdict agreement holds.

### Slice 3 — the gate goes live
Wire PASS/FAIL into `generate_creative` after `run_live_qa`, with the §1.2 retry ladder
(attempts 1 and 2 only — re-art-direct and archetype swap), max-retry escape hatch, and
audit records. Devil's-advocate borderline pass ships here too (it's what makes gating safe).

### Slice 4 — finish escalation + learning loop
The 2′ branch (§4): vector→AI-illustration escalation behind the adapter/spend gate, with
the SN modesty triple-check. Operator-override capture → golden-set growth + per-client
PreferenceProfile anchor modifiers (§3.3).

Each slice is dogfooded on a real client's creatives before it's called done (constraint #10).
