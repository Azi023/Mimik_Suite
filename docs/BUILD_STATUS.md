# Mimik Suite — Build Status & Delegation Ledger

> Living report. What's happening, what's about to be implemented, and who's doing it.
> **Brain:** Claude Code (this terminal) — plans, specs, reviews, integrates.
> **Hands:** Codex CLI (`codex exec`, best model / high effort) — executes scoped specs in the background.
> Rule: Codex never commits; Claude reviews every diff before it lands.

_Last updated: 2026-07-21 (session: local-test → creative-engine v2)._

---

## Where we are

- **M0 — local instance: DONE.** App DB → local Postgres `:5434` (production untouched), wiped to empty,
  1 clean tenant, fresh 30-day owner dev-token wired into `web/.env.local`. API `:8000` + web `:3000` live.
  Login into an empty studio works (dev-token path; real Supabase multi-account login deferred to persona testing).
- **Creative-engine spike — DONE + learnings.** Built the missing seam (`creative/art_direction.py`,
  `creative/generate.py`) and generated the product's **first real creatives** (Simply Nikah, A/B: Nano-Banana
  vs GPT-Image-1). **Verdict: rejected the approach** — right pipeline, wrong output:
  - AI **photorealistic people** — client forbids real photos (wants flat illustration / silhouettes, modesty).
  - **Rigid "photo + bottom band"** — stale; real feed is varied, layered vector compositions.
  - **Brand palette not applied** to the text band (fell back to house blue); **QA is blind** to palette adherence.
  - Output is a **flat PNG** — editors can't open layers.
- **Architecture v2 — DECIDED (spec published).** Style-profile engine · layered editable document ·
  effects vocabulary (fades/shadows/shading/color-grade stay editable via SVG filters) · SVG-first export.
  Full spec: the "Creative Engine v2" artifact (published this session).

## Decisions locked
- **Imagery = paid API for tuning** (no browser-automation ban risk); **PAUSED** until the engine is right.
- **Hybrid visuals**: brand asset library → source from references → AI-generate → human approves.
- **SVG-first** editable export (Illustrator/Figma/Canva), **PSD** next; PNG = preview only.
- **Medium is per-brand** via a Style Profile; **modesty / no-real-people is a hard QA guardrail**.

## Open decisions (blocking design-dependent work — awaiting operator)
1. First 2–3 **client archetypes** to seed style profiles.
2. Which **effects** matter most (soft shadow/gradient/grade vs heavy composite → PSD priority).
3. Do we have Simply Nikah's **vector assets** to seed the library, or source/generate?
4. Green-light **P-FIX → M4 (SVG)** now (still no API spend)?

---

## Build order (fix-first, no API spend)
| Phase | What | Depends on | Owner |
|---|---|---|---|
| **P-FIX** | kill mock-fallback → real empty states; onboarding autosave; fix "session expired"; onboarding fields (medium, dos/don'ts, reference/asset upload) | — | Codex (spec'd) |
| **M4** | layered document model + **SVG export** (then PSD) | Q4 | Claude designs · Codex builds |
| **M3** | style profiles + composition variety + effects + modesty QA | Q1,Q2 | Claude |
| **M2** | reference research (Pinterest/web) → vet → asset/motif selection | Q3 | Codex + Claude |
| **M5** | golden set (client's own feed) + evals | — | Claude |

---

## Delegation log
| # | Task | Agent | Status | Review |
|---|---|---|---|---|
| 01 | Remove frontend mock-fallback → real empty states | Codex (high) | ✅ done, unstaged | ✅ Claude-verified (tsc clean, no `any`, auth untouched) |
| 02 | Draft `docs/STYLE_PROFILES.md` — 3 real profiles (Simply Nikah / Glo2Go / Island Cart) + schema | Codex (gpt-5.6-sol, xhigh) | ✅ done, unstaged | ✅ Claude-verified (accurate, source-bound); awaiting operator red-lines |

_Codex output lands in `scratchpad/codex_run_*.log`; Claude reviews `git diff` before anything commits._

---

## Refinement 2026-07-22 — client archetypes are genuinely diverse (Q1–Q3 answers)

The operator confirmed: there is **no single style** — the engine must span real, very different client types. Three
real reference clients define the spread:

| Client | Medium | Look | Engine needs |
|---|---|---|---|
| **Simply Nikah** | flat illustration, **faceless/silhouette** (modesty) | pink/plum, Islamic motifs, varied layered layouts | generate/source vector illustration + motifs; modesty guardrail |
| **Glo2Go Aesthetics** | **real photography** — owner won't appear → **stock + Leonardo-generated** | plum/white editorial, Myth-vs-Fact splits, brand pill badge, semi-transparent text panels | stock-photo + AI-realistic sourcing; photo text-panels; badge placement |
| **Island Cart** | **product photography** + bold meme type | orange/white diagonal blocks, huge condensed type, product cutout, price tags | product-photo **background-removal/cutout**, price badges, bold type, witty copy |

**Consequences for the architecture (updates the v2 spec):**
- **Image sources become a spectrum, not just "AI":** ① AI-generate (illustration *or* realistic via Leonardo/API)
  · ② **licensed stock** (Glo2Go — free tiers first: Unsplash/Pexels) · ③ **client product photos** → cutout/composite
  (Island Cart) · ④ **engine-generated/sourced vector assets** (operator does NOT have the vectors — designers make
  them, so the engine must create them).
- **Quality bar (Q2) = designer-grade & varied, NOT templated.** Every archetype gets multiple layouts + design-principle
  variation + real manipulation (cutouts, shadows, color-blocks, overlays, panels, badges). "Band at the bottom" is retired.
- **Style Profiles are derived at onboarding** (medium, sources, dos/don'ts, references, product/asset uploads) — so P-FIX
  must make onboarding capture these, then the operator onboards these 3 real clients, then the engine builds to their profiles.

**Q4 = not greenlit.** No M4 build yet. Next planning step: draft the 3 concrete Style Profiles as the build spec.
**Codex model:** operator wants a specific model ("5.6 Sol", extra-high effort) — awaiting the exact `-m` model string; ran task 01 on codex default @ high.
