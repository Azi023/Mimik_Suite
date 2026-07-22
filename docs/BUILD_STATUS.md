# Mimik Suite — Build Status & Delegation Ledger

> Living report. What's happening, what's about to be implemented, and who's doing it.
> **Brain:** Claude Code / Opus (this terminal) — plans, specs, reviews, integrates. Planning is the point.
> **Hands (executors, driven from this terminal):**
> - **Codex** `codex exec -m gpt-5.6-sol -c model_reasoning_effort=xhigh -s workspace-write` — primary coder (6/7 tasks).
> - **agy** (Antigravity CLI, Gemini 3.1 Pro High) `agy -p "<spec>" --mode accept-edits --dangerously-skip-permissions` — RESERVED for the **Command Center** (hand it a full plan → it executes).
> - **gemini** CLI — spare executor for independent parallel tasks.
> Rule: executors never commit; Claude reviews every diff before it lands.

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
| 02 | Draft `docs/STYLE_PROFILES.md` — 3 real profiles (Simply Nikah / Glo2Go / Island Cart) + schema | Codex (gpt-5.6-sol, xhigh) | ✅ done, committed `7f9557b` | ✅ Claude-verified (accurate, source-bound) |
| — | **Checkpoint commit `7f9557b`** — mock-fix + engine-v2 spec + profiles + art-director spike | Claude | ✅ committed (not pushed) | — |
| 03 | `scripts/seed_profiles.py` — add the 3 real clients from the profiles | Codex (gpt-5.6-sol, xhigh) | ✅ ran vs local DB | ✅ 3 clients live (Simply Nikah / Glo2Go / Island Cart), idempotent |
| 05 | `creative/style_profile.py` — encode 3 profiles as Pydantic `StyleProfile` (M3/M4 foundation) | Codex (gpt-5.6-sol, xhigh) | ✅ done, unstaged | ✅ Claude-verified (4 tests, faithful load, modesty guardrail machine-checkable) |
| 06 | Multi-source references: add Unsplash+Pexels fetchers (env-key gated) + fix `build_query`; TODO pinterest/dribbble/behance/envato | Codex (gpt-5.6-sol, xhigh) | ✅ committed `70c0704` | ✅ **live-judged**: Pexels ACCEPT for Glo2Go (on-brief clinic photos); stock DECLINED for Island Cart (need cutout) + Simply Nikah (violates modesty) → profile-routing validated |
| 07 | **M3 slice #1** `creative/render/glo2go_templates.py` — Glo2Go archetypes (single-hero + myth/fact) w/ text-panel + badge, profile-driven | Codex (gpt-5.6-sol, xhigh) | ✅ done | ✅ **rendered + judged ~72%** — right architecture (real photo, plum, badge, panel); flaws → panel covers face, generic CTA/font, wordmark not logo, flat panel |
| — | **`docs/DESIGN_RUBRIC.md`** — living self-improving design-critique brain (seeds C1/T1/T2/B1/P1/G1/G2 from the judge) | Claude | ✅ created | the M5 seed; art-director + templates read it |
| 08 | **Glo2Go v2** — apply rubric (CTA pill, logo image, panel blend, text size) + `creative/vision/text_region.py` (vision negative-space so panel avoids the face) | Codex (gpt-5.6-sol, xhigh) | ✅ done | ✅ **re-judged ~80%** — CTA/text/blend fixed (rubric worked); C1 sharpened (panel still overflows face) |
| — | **⏸ Visual design-tuning PAUSED** (Glo2Go v3, Simply Nikah, Island Cart visuals) — awaiting a real DESIGNER's feedback → drops into `DESIGN_RUBRIC.md`. Also asset-blocked: need Glo2Go logo file + brand font. | operator/designer | ⏸ held | resume when designer + brand assets arrive |
| 09 | **M4 slice #1** — layered **SVG export** (editable `<text>` + named layers) → Figma/Illustrator/Canva | Codex | ✅ committed `e437e39` | ✅ verified (6 layers, live `<text>`, rasterizes) |
| **A** | **M4** — editable export API: `POST /exports/svg` (downloadable **.svg**, never jpeg/png) + png-preview | Codex (gpt-5.6-sol, xhigh) | ✅ done, unstaged | ✅ Claude-verified: svg attachment + png inline-preview, authed, 2 tests, Ruff clean |
| **B** | **M4** — layered **PSD** export for Photoshop (pytoshop; per-element named layers) | Codex (gpt-5.6-sol, xhigh) | ✅ done + Claude-fixed | ✅ real .psd: 6 named layers, valid 8BPS, opens in PS. Claude fixes: forced `raw` compression (pytoshop rle broken), added numpy/six deps. ⚠ v1 text rasterized (SVG=live-text master); raw = large files (zip later) |
| **C** | **M5** — design-feedback flywheel: `creative/knowledge/` rules store + `record_feedback` + prompt block | Codex (gpt-5.6-sol, xhigh) | ✅ done, unstaged | ✅ Claude-verified: 9 rules seeded, profile-filtered load, learns new rules, prompt-block, 3 tests |
| **D** | **P-FIX** — onboarding capture (imagery medium, dos/don'ts, refs) + **draft AUTOSAVE** (reload-safe) | Codex (gpt-5.6-sol, xhigh) | ✅ done, unstaged | ✅ Claude-verified: localStorage autosave (restore/clear), medium select, tsc clean, no `any`, 5 tests |
| 04 | **M2 R&D** `creative/references/gather.py` — reference-finder (keyless Openverse source) + CLI | Codex (gpt-5.6-sol, xhigh) | ✅ built + tested | ⛔ **Claude DECLINED Openverse results** — irrelevant CC-archive junk (impala for "skin clinic"). Finding: quality = **source problem**; `build_query` also over-stacks → 0 results. Next: swap source (Unsplash/Pexels/design) + fix query. Seam is ready. |

_Codex output lands in `scratchpad/codex_run_*.log`; Claude reviews `git diff` before anything commits._

### 2026-07-22 — make it a real product (not scripts) + first designer feedback
- **API restarted** (was frozen on M0 code → /exports 404); now current. Studio confirmed working (empty by design — no UI generate yet).
- **Creative-head feedback captured** into the flywheel: L1 logo-contrast-on-dark, L2 smaller left/centered panel, L3 zoom-out subject, L4 grid alignment, L5 live-text-must-be-real (→ SVG is the live-text master; PSD live-text SKIPPED as too complex).
- **Decisions:** PSD live-text = skipped. Codex/agy usage = separate pools from Claude quota, unmeterable via CLI, headroom OK.
- **`docs/PLAN_EDITOR_AND_COMMAND_CENTER.md`** drafted — the in-product editor ("mark & tell AI", client-bounded, SVG-layer based) + Command Center (→ agy).
- **RULES** ✅ committed `33f39ba` (L1–L4 in glo2go templates + svg + art-director reads rubric).
- **GEN** ✅ committed `5bff094` + **verified LIVE**: `POST /clients/{id}/creatives:generate` works end-to-end (topic→Pexels→vision→render→persist); generated a real Glo2Go creative through the product, downloadable .svg. **Studio is now USABLE** (Generate + Download on the Board).
- **EDITOR** ▶ dispatched to **agy** (Antigravity/Gemini 3.1 Pro, first real agy run): v1 in-product editor — inline text edit + "Ask AI to change" (`POST /creatives/{id}/revise`, non-destructive versions) + layout toolbar. Claude reviews.
- **EDITOR** ✅ committed `76c8cdd` + **verified LIVE**: `/revise` → "move panel right" repositioned panel + re-drafted copy as a new non-destructive version. Minor: badge word-map inverted; instruction overrides explicit edit (queued fix). Note: agy left stray `patch*.py` (cleaned).
- **"Upload old creatives"** → moot: Board now populated by real *generated* creatives (Glo2Go + revised version live, editable); old script AI-photos were the rejected approach.
- **CLIENT/BRAND EDIT** ▶ dispatched (Codex): PATCH client + brand-brief, tenant/IDOR-safe, in-product edit surface.
- **Next:** Command Center (→ agy, needs full spec) → deploy.

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

---

## 2026-07-22 (session 2 — Opus orchestrator) — QA pass · Fable plan · editor-bug fixes · imagery/nav dispatch

**Brain:** Opus (this terminal). Confirmed the local product runs (API :8000 health 200, web :3000 200, PG :5434 / Redis :6381 up).

### Goals 1 & 2 — DONE
- **Full QA pass** (`multi-persona-qa-reviewer`): 4 P0, 4 P1, several P2/P3. P0s: (1) **mobile nav dead** — hamburger has no onClick, sidebar hidden ≤860px → no nav on phone; (2) **near-blank output for Simply Nikah + Island Cart** (= Goal 3); (3)+(4) the two editor bugs (now fixed). QA **confirmed tenant/IDOR discipline is genuinely solid** (live-probed, no cross-tenant leak; JWT alg+typ pinned). Also flagged: badge inversion ALSO in `ReviewPanel.tsx` buttons; dead `web/components/OnboardingWizard.tsx` fork; sidebar search decoy input; stale `docs/COMPLETENESS_ASSESSMENT.md`.
- **Fable-5 plan** → `docs/PLAN_COMMAND_CENTER_AND_CANVAS.md` (code-grounded; Plan A Command Center = 13 tasks/agy, Plan B Canvas Editor = 14 tasks/Codex+Fable; 9 parallel-safe waves + file-conflict map). Its **B-01 == the editor-bug fixes already completed this session**.

### Goal 4 — DONE + LIVE-VERIFIED · committed `f3a6ff7`
| Fix | Detail | Verify |
|---|---|---|
| Bug 1 badge inverted | `"lighter"→0.0` (light/reversed badge), `"darker"→1.0` (plum) in BOTH the API keyword parser AND `ReviewPanel.tsx` Light/Dark buttons | live 201, params applied; `badge_theme(0.0)="light"`, `badge_theme(1.0)="plum"` |
| Bug 2 AI clobbered edit | `body.edits` now applied AFTER the instruction redraft → explicit edit wins, layout still applies | live 201: sentinel headline survived + `panel_anchor=left` |
| Robustness | `/revise` degrades to layout-only instead of 500 when copy LLM 429s (Gemini free tier IS 429ing) | live 201 under 429 |
| Cleanup | removed dead `new_version` line; fixed latent `CopyBlock` F821 import; ruff+tsc clean, 9 tests green | — |

### Goal 3 — DONE + LIVE-VERIFIED · committed `6d65556` (Codex-built, Claude-reviewed)
- **Decisions:** Simply Nikah → paid AI-illustration (OpenRouter/OpenAI, used **sparingly**); Island Cart → Pexels now (product photos later).
- `_source_image` → ordered **source resolver** (LICENSED_STOCK→Pexels; AI_ILLUSTRATION/AI_REALISTIC→paid adapter, gated; skip GENERATED_VECTOR/PRODUCT_CUTOUT→placeholder). Art-direction prompt now carries profile medium + modesty guardrails.
- **Robustness (Claude-added):** generation no longer 500s under Gemini 429 — art-director fallback now catches OSError/HTTPError (was Value/Key/JSON/Runtime only); copy falls back to a deterministic topic CopyBlock; 502 handler now logs the real exception.
- **Verdict:** LIVE — all 3 clients 200 under current 429s (Glo2Go/Island Cart → real Pexels photo; Simply Nikah → placeholder in dev). **One real OpenRouter validation render** of Simply Nikah = faceless flat-vector, mihrab framing, on-brand pink/plum — **modesty guardrail held**. 6 new tests + 18 total green; ruff clean; zero test spend; paid gate operator-controlled.

### QA P0 mobile-nav + frontend — DONE + VERIFIED · committed `a289187` (Fable-built, Claude-reviewed)
- **P0** hamburger → off-canvas `MobileNavDrawer` (reuses desktop `<Sidebar>` wholesale; scrim/Escape/link-close, focus trap, aria-modal). **P1** sidebar search now filters clients. **P1** dead `web/components/OnboardingWizard.tsx` fork deleted.
- **Verdict:** tsc clean, no `any`, AppShell→client-component safe (all 19 call sites pass serializable props, no server-only imports). Sidebar renders twice (desktop+drawer) but has no static `id` → no duplicate-DOM issue.

### Remaining QA P0/P1 (not yet done) — for next wave
P1: ReviewPanel inline styles → design-system classes (B-10 covers this) · `.env` JWT_SECRET = published default locally (confirm PROD uses a real secret) · P2: portal `/portal/session` leaks raw PyJWT error string · ClientBrandEditor React key `${index}-${hex}` collision.

### Program note — Fable plan rollout (wave-by-wave, review-gated)
Operator greenlit building the **Command Center + Canvas** program. Text quality: operator chose **route
copy/art-direction through OpenRouter/OpenAI** (done — see below).

**Wave 1 status:**
| Task | What | Owner | Status |
|---|---|---|---|
| B-01 | editor-bug fixes (badge/edit/robustness) | Claude | ✅ `f3a6ff7` |
| — | Goal-3 imagery (extra task on hot file) | Codex | ✅ `6d65556` |
| TEXT | resilient provider chain Gemini→OpenRouter→OpenAI (`default_generate`) | Codex | ✅ `879ea7e` — LIVE-verified (real copy via OpenRouter under Gemini 429) |
| A-01+B-02 | typed ops + canvas contracts (sibling repo) | Codex | ✅ `mimik-contracts@7fb1210` — 27 tests, cross-repo import OK |
| B-05 | svg.py `layer_overrides` + data-editable/data-bbox | Codex | ⏳ in flight |

**Hot-file `api/services/creative_generation.py` sequence** (never parallel): [B-01 ✅ · imagery ✅] → B-04 → B-06 → B-07 → B-11 → B-13 → A-03.
**Next (W2):** B-03 (lineage migration) ∥ A-02 (typed /ops responses). Then W3: B-04→B-06→B-07 (strict, hot file) ∥ A-10 (admin). See the plan's wave matrix.
**Ongoing paid spend:** text chain uses OpenRouter/OpenAI (cheap per call, operator-approved). Image gate (`MIMIK_ALLOW_PAID_IMAGES`) stays OFF by default; Simply Nikah illustration validated once (faceless/on-brand).
