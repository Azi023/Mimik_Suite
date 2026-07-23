# Mimik Suite — MASTER PLAN (full-vision reconstruction + missed-items backlog)

> Written 2026-07-23 by a business-logic analyst pass over the ENTIRE paper trail:
> `~/.claude/plans/hi-i-want-to-sunny-fox.md` (origin plan, session 1) · all 23 HANDOFF entries
> (oldest→newest) · SESSION_LOG.md · docs/PRODUCT_STATE_INVENTORY.md · docs/PRODUCT_PM_REPORT.md ·
> docs/BUILD_STATUS.md · docs/STYLE_PROFILES.md · docs/COMPLETENESS_ASSESSMENT.md ·
> docs/BRAND_KIT_ONBOARDING.md · docs/FRONTEND_ROADMAP.md · CLAUDE.md · git log · code greps.
> This is the single authoritative forward plan. It supersedes the priority lists in the
> inventory/PM report by MERGING them with the vision items those docs dropped.

---

## 1. Why Mimik exists + where it's headed (the north star)

**The wound (origin plan, "Context"):** clients churn because they built their own ChatGPT
pipelines; briefs drift after sign-off (the "greenish doctor, night before" fire drill); tuning
evaporates in chat; ops runs on Excel; approved work never reaches Drive. Atheeque runs two
agencies (Mimik Creations + Jasmine Media) bleeding on exactly these seams.

**The thesis:** own the WHOLE loop, human-gated — intake → brand brief (frozen, signed off) →
generate (hybrid: AI imagery + code-composited exact text/logo/hex) → auto brand-QA → internal
review → bounded client approval (WhatsApp/magic-link) → auto-archive to Drive → LEARN (every
pick/edit/rejection feeds a per-client preference profile above a Mimik house-quality floor).
Sell the **service** ($750/mo unlimited-design sub, already live on mimikcreations.com/unlimited),
not the tool. Pencil/Canva own self-serve tooling; the done-for-you SMB loop is the open flank.

**The end-state (PM report §3, still the target):** one operator runs 20+ clients from a cockpit —
types "generate 5 Educational posts for Glo2Go this week", the queue fans out, creatives land on
the board **in each client's own design language**, the team nudges them in a trustworthy editor,
clients approve in a bounded portal, Drive fills itself, and the per-client taste model measurably
improves hit-rate. Dogfooded first on three REAL clients whose design languages deliberately span
the space: **Simply Nikah** (faceless/silhouette flat-vector, Islamic motifs, modesty-gated),
**Glo2Go Aesthetics** (real photography, medical-premium), **Island Cart** (product-cutout +
meme type). *The per-client craft IS the product* — a shared engine that renders three wildly
different brands correctly is the moat no point-tool copies.

---

## 2. The complete intended system — every capability, tagged

Tags: **[BUILT]** works in the live path · **[PARTIAL]** some of it real · **[STALE]** code exists
but disconnected from the live path · **[DNB]** discussed-never-built · **[IMPLIED]** never
explicitly planned but the vision requires it.

### 2a. The loop
| Capability | Tag | Evidence |
|---|---|---|
| Onboarding wizard (client+kit+pillars+refs, autosave) | **[BUILT]** | `web/app/onboarding/`; `a4f43db` specific-error |
| Brand-brief auto-draft from URL (scrape+vision) | **[PARTIAL]** | `api/services/brief_extraction.py:186` — proofkit import guarded/optional; extraction unverified in current env |
| Brief versioning / signoff freeze (the anti-drift fix) | **[BUILT]** | `briefs.py:146` revise mints new immutable version |
| Generate creative (topic→image→copy→render→persist) | **[PARTIAL]** | works end-to-end but real imagery for **1/3 clients only** (Glo2Go/Pexels); SN + IC → `_solid_placeholder` (`creative_generation.py:272`) |
| 5-layer L1–L5 re-generable checkpoint stack ("check out at any layer") | **[DNB]** | actual master = fixed semantic 6-layer SVG (`creative/export/svg.py`); HANDOFF pm6 architecture-fork explicitly flags the mismatch |
| Auto brand-QA critic as a HARD gate | **[STALE]** | `run_brand_qa` (WCAG/safe-zone/logo-contrast, real) only called in `creative/pipeline.py:114`; live path `_render_creative_artifacts` bypasses it |
| Logo-contrast QA + knockout-logo derivation | **[BUILT-then-STRANDED]** | built + live-proven on G2G (SESSION_LOG it.2–3) — lives in the same bypassed pipeline |
| Ops board / drag transitions / calendar / at-risk SLA | **[BUILT]** | `ops.py:177/222`, A-06, `CalendarView.tsx` |
| Pillar-BALANCED calendar ("no five promos in a row") | **[DNB]** | pillars exist + calendar exists; no balancing/planning logic anywhere |
| Client bounded portal + magic link + quota revise | **[BUILT]** | `portal.py`, `review/[token]`, B-11 (24h quota → 429); 18/18 isolation tests |
| Approve → auto-archive to Google Drive | **[STALE-in-prod]** | code real + wired (`approval_flow.py:182` → `creative/archive/google_drive.py`); `GET /deliveries` = 0 rows → **never executed live**; was verified ONCE on 2026-07-20 (it.10: real file in Drive) then env drifted |
| Learning loop: signal capture → per-client profile | **[PARTIAL]** | signals captured on every approve/reject/edit (`edit_signals.py`, B-13); ranker exists (`preferences.py`) but **no generation code consults it**; `preferences/page.tsx:88` claims otherwise (UI lies) |
| Golden-set promotion, poisoning guard | **[BUILT, unexercised]** | P4 gate green; client corrections can never write goldens |
| Evals gating regression | **[PARTIAL]** | one G2G fixture (`tests/test_evals_g2g.py`); the "evals gate every phase" culture never scaled |

### 2b. Per-client craft (the under-planned heart)
| Capability | Tag | Evidence |
|---|---|---|
| Style Profiles (3 real clients, full creative contracts) | **[BUILT as data]** | `creative/style_profile.py` + `docs/STYLE_PROFILES.md` — meticulous 3-profile spec |
| **Simply Nikah silhouette/faceless vector engine** | **[DNB]** — the flagship miss | Profile demands engine-generated vector assets (mihrab arches, lattice, lanterns, faceless avatars, connector cards, calligraphy panels) + 6 layout archetypes; `creative_generation.py:272` skips GENERATED_VECTOR → placeholder. BUILD_STATUS open decision Q3 ("do we have SN's vector assets?") never answered |
| Island Cart product-cutout pipeline (bg-removal, price tags, diagonal blocks, 3 archetypes) | **[DNB]** | same skip at :272 for PRODUCT_CUTOUT; no cutout code anywhere |
| Glo2Go archetypes | **[PARTIAL]** | 2 of 3 built (`glo2go_templates.py`: single-hero + myth/fact, judged ~80%); Educational Carousel System **[DNB]** |
| Per-brand effect vocabulary (gradients/shadows/blur/duotone/grain via SVG filters) | **[PARTIAL]** | v2 spec decided (BUILD_STATUS); only soft shadows/panels/waves implemented in G2G templates |
| Modesty / owner-exclusion / price-accuracy as machine QA guardrails | **[PARTIAL]** | encoded in profiles + prompts (one OpenRouter render held modesty); NOT enforced by QA (critic bypassed) |
| Per-brand fonts: custom font upload + @font-face in compositor + licensing tracking | **[DNB]** | operator ask (FRONTEND_ROADMAP §4b); `AssetKind.FONT` upload exists; all 3 profiles say "typeface: confirm at onboarding" — never confirmed, compositor never loads brand fonts |
| Brand-deck ingestion (upload guideline PDF → auto-fill kit/brief) | **[DNB]** | operator ask (FRONTEND_ROADMAP §4b); partial seams (extract_brief_sections, vision/study.py) |
| Asset library (upload/approve/ingest, vision study) | **[BUILT]** | `assets.py`, `brand_memory.py`, knockout endpoint |
| Reference research → vet/score → L2 (Pinterest etc.) | **[STALE]** | `references/gather.py` (Openverse junk; Pexels ok; Pinterest/Dribbble/Behance = TODO stubs) + `fit_critic.py` — not in live generate path |
| Cold-client bootstrap (prospect URL → auto-sourced brand) | **[BUILT (API)]** | `POST /clients/{id}/bootstrap`, SSRF-guarded |

### 2c. Generation economics + variants
| Capability | Tag | Evidence |
|---|---|---|
| Swappable image adapter (sub→API = config) | **[BUILT]** | `creative/adapters/` router, spend gate `MIMIK_ALLOW_PAID_IMAGES` |
| Browser-automation backends (Leonardo/ChatGPT CDP-attach + patchright) | **[BUILT, shelved]** | proven live on burner (SESSION_LOG it.11–13); superseded by paid-API decision (BUILD_STATUS "imagery = paid API for tuning") |
| A/B dual-model generation → pick logged | **[DNB]** | LOCKED plan feature; zero variant/seed logic in `creative_generation.py` |
| Taste-ranker steers generation / auto-select | **[DNB]** | ranker built, never consulted (§2a) |
| Multi-format fan-out (one approved concept → all channels) | **[DNB]** | LOCKED plan feature; a creative has exactly ONE format from generation; editor format-switcher signed off pm6, unbuilt |
| Multi-slide carousel (a real IG carousel, not one 4:5 slide) | **[IMPLIED]** | `formats.py` "carousel" = a single 1080×1350 slide; Glo2Go profile requires a repeated-slide SYSTEM |
| Spend-minimizing queue (budget/backoff/deadline-priority) | **[PARTIAL]** | A-03 queue+worker real; per-provider budget + deadline-priority ordering not implemented |
| Multilingual / RTL Arabic (EN+Arabic at launch — LOCKED default) | **[DNB]** | zero RTL/Arabic code; Simply Nikah's Ayah-and-Translation archetype requires Arabic calligraphy panels |
| Print output (300dpi/CMYK/bleed) | **[DNB, deliberately JIT]** | plan defers — fine |
| Video module (mimik-engine satellite) | **[DNB, planned-later]** | zero imports — as planned |

### 2d. Cockpit, comms, commerce
| Capability | Tag | Evidence |
|---|---|---|
| Command Center ⌘K ("generate 5 Educational posts for Glo2Go" → fan-out) | **[DNB]** | A-05 parser: zero matches for `command_center|/ops/command`; A-08 queue panel: `/ops/queue|stats|usage` endpoints LIVE but **no UI consumer** in `web/lib/api.ts`; A-09 bar unbuilt |
| Internal Track-B command center (ALL Mimik businesses: leads/Proofkit/finance/hosting) | **[DNB]** | HANDOFF 2026-07-21 "Track B = SEPARATE app/repo… not started"; FRONTEND_ROADMAP §0/§5 B1–B12 |
| WhatsApp notifications (approval nudges, weekly digest) | **[STALE]** | Meta Cloud adapter proven mechanically (real 401), `WHATSAPP_PROVIDER=none` → inert; blocked on Meta account-health (both portfolios enforcement-restricted) |
| Auto-brief-from-WhatsApp-conversation | **[DNB]** | plan [REC] item; nothing |
| Weekly client digest / competitor watch / confidence-gated autonomy / rejection-reason analytics | **[DNB]** | plan items; nothing |
| Storefront → Suite intake bridge (unlimited claim form → prospect) | **[PARTIAL]** | `POST /intake/claim` built + gated flow green; **mimikcreations.com form not actually pointed at it** |
| Stripe billing ($750/mo + 3-free-designs trial) | **[PARTIAL]** | full mocked scaffold (P5 gate green); keys empty, never live |
| Acquisition→fulfillment auto-bridge (Sales closes → tenant auto-created) | **[DNB]** | Sales stays confidential; only the storefront claim path exists |
| Figma deep-edit L4 handoff (export→edit→re-import) | **[DNB]** | grep `figma` in creative/+api/ → zero; was a LOCKED plan pillar ("no custom canvas editor — Figma for deep edits") — note the irony: we built the canvas editor instead |
| Supabase real login as the ACTIVE path | **[STALE]** | full Supabase ES256/JWKS + IAM + invitations built; local runs on dev-token; `NEXT_PUBLIC_DEV_TOKEN` ships in client bundle (deploy HELD on hardening) |
| Multi-tenant 2nd agency (Jasmine Media) | **[DNB]** | plan promise "used by Mimik AND Jasmine"; only tenant `mimik` provisioned |
| Production deployment | **[STALE]** | suite.mimikcreations.com deployed 2026-07-21, then **all subsequent work local-only**; deploy HELD — prod is now ~2 days behind the product |
| Per-job context record (HANDOFF-per-client) | **[DNB]** | knowledge-layer item 6; nothing |

---

## 3. THE MISSED-ITEMS BACKLOG (discussed/implied, not built, mostly absent from current plans)

Ordered by how central each is to the origin vision. Size: S ≤1 session · M = 1–3 · L = program.

**M-01 · Simply Nikah silhouettes — the flagship miss (L)**
The profile is the most fully-specified creative contract in the repo (STYLE_PROFILES.md §1) and
the engine renders it as a **solid placeholder**. What's actually required (and appears in NO
current roadmap): (a) an **engine-generated vector asset library** — Islamic lattice/mashrabiya,
mihrab arches, lanterns, shields, crescents, hands-forming-heart, faceless avatar/match cards,
connector lines, calligraphy-panel frames — reusable SVG parts the compositor composes;
(b) **6 layout archetypes** (Highlighted-Word Hero, Phone-and-Hijabi, Connected Match Cards,
Mihrab Frame, Protection Symbol Hero, Ayah+Translation); (c) **AI-illustration fallback** behind
the paid gate (one validated render exists — faceless, on-brand, modesty held, `6d65556`);
(d) **modesty as an enforced QA check**, not a prompt hope. Why it matters: it's the proof the
engine spans design languages — the entire "per-client craft" moat. Deps: QA-critic rewiring
(M-08), possibly Arabic/RTL (M-11), operator answer on asset sourcing (§6 Q1).

**M-02 · Island Cart product-cutout pipeline (M)**
Sibling of M-01. Requires: client product-photo intake → background removal → cutout + drop
shadow compositing → price-tag pills, diagonal color-blocks, 3 archetypes (Diagonal Lifestyle
Split, Cutout Product Offer, Dark-Photo Type Slam). Today IC renders a Pexels lifestyle photo at
best — never the actual product, violating its own hard guardrail ("use the client's actual
product photography"). Deps: product photos from client (§6 Q2).

**M-03 · Per-client layout-archetype engine generally (M, after M-01/02)**
Only Glo2Go got real templates (2 of its 3 archetypes, judged ~80%). The v2 architecture decision
("varied layout engine that switches among …" — STYLE_PROFILES.md closing section) was never
generalized: archetypes live as prose in profiles, not as renderable templates. The engine needs
archetype→template coverage per profile + `suggest_template` extended across clients.

**M-04 · Multi-format fan-out + real carousels (M)**
LOCKED plan feature #4 ("format is a parameter") + selected feature "one approved concept → all
channels". Today: one creative = one format forever; "carousel" = a single 4:5 slide, but Glo2Go's
Educational Carousel System needs an N-slide series with repeated grid/badge/type. The signed-off
editor **format switcher** (1:1/4:5/9:16 re-compose) is the thin end of this wedge — build them as
one capability: re-compose the same manifest at target dims / across a slide sequence.

**M-05 · A/B dual-model generation + pick capture (M)**
LOCKED plan feature and the FUEL for the whole taste system ("run 2 backends/seeds → present 2 →
capture the pick"). Zero variant logic exists, which also starves M-06. The adapter router already
supports 2 backends; the missing part is variant fan-out + storage + a pick UI on review.

**M-06 · Close the learning loop (M)**
Signals in, nothing out. `rank_variants`/`build_profile` never consulted at generate/pick time;
`preferences/page.tsx:88` claims "Ranker is steering picks" — false. Either: generation consults
the profile (template/palette/params biasing + variant ordering) or the UI stops claiming it.
Without this the "it learns" sales line is fiction. Deps: M-05 gives it real choices to rank.

**M-07 · Drive auto-archive PROVEN in the running product (S — do first)**
The headline ops fix ("ops manager stopped uploading to Drive") — real code, wired, verified once
in isolation on 2026-07-20, **never once executed by the product** (`GET /deliveries` = 0 rows).
Run `scripts/drive_oauth.py`, set the 4 env vars, one real approval end-to-end, see the file in
`Mimik Clients/<Client>/<YYYY-MM>/<job>/`.

**M-08 · QA critic + logo-contrast + knockout loop re-wired into the LIVE path (S–M)**
The anti-"greenish-doctor" promise. `run_brand_qa` + the logo-contrast check + knockout derivation
were built AND live-proven (the G2G purple-on-purple failure→fix→green loop, SESSION_LOG it.2–3),
then the v2 generate path (`_render_creative_artifacts`) bypassed all of it. Re-wire + extend with
profile guardrails (modesty, owner-exclusion, price-accuracy, palette adherence).

**M-09 · Command Center (⌘K cockpit) (L)**
The operator's stated end-state interaction ("type: generate 5 Educational posts for Glo2Go").
Backend endpoints for queue/usage are LIVE and dead-ended (no UI consumer). Order: A-08 panel
(cheap, makes the worker visible) → A-05 parser+execute → A-09 ⌘K bar. Separate decision: the
Track-B ALL-businesses command center (own app/repo) — parked, keep it parked (§6 Q4).

**M-10 · Brand fonts + font licensing (M)**
Every profile says "typeface: confirm at onboarding" — never happened for ANY client. Plan LOCKED
per-brand font files + licensing tracking + open-license fallback; operator explicitly asked for
custom font upload (multiple files). Upload seam exists (`AssetKind.FONT`); missing: kit UI,
`@font-face` in the compositor/SVG, licensing field. Real design language is impossible on system
fonts — this quietly caps every client's quality.

**M-11 · Arabic / RTL (M)**
LOCKED default: "EN+Arabic at launch." Zero code. Simply Nikah's Ayah-and-Translation archetype
(Arabic calligraphy + translation) is a profile-level requirement. Needs Arabic font in the
library + per-brand language + RTL-aware templates (Playwright renders RTL natively — the plan's
own point). Fold into M-01's Ayah archetype or explicitly de-scope (§6 Q1b).

**M-12 · Reference research → vetted moodboard (M)**
Plan's brief §8 + L2 concept feeder. `gather.py` proved the SOURCE problem (Openverse junk;
Pinterest/Dribbble/Behance stubs); fit-critic works but isn't in the live path. Re-scope: team
uploads references (works today) + fit-critic scoring wired into generation prompts; defer scraping.

**M-13 · WhatsApp live + weekly digest (M, externally blocked)**
Adapter proven; blocked on a clean Meta business portfolio (both existing ones
enforcement-restricted). The magic-link-share flow covers the gap manually. Unblock = operator
creates the fresh portfolio (24h name-hold noted 07-20) → flip `WHATSAPP_PROVIDER`.

**M-14 · Storefront bridge + Stripe live (S–M, gated)**
`POST /intake/claim` + mocked billing are green; the actual mimikcreations.com/unlimited form has
never been pointed at the API, and Stripe keys were never issued. Flip when quality is sellable.

**M-15 · Figma L4 deep-edit handoff (M) — or formally retire it**
Origin-plan pillar ("no custom canvas editor — export to Figma for deep edits"). The product then
built exactly the custom canvas editor the plan forswore (and it's good). Decide: keep Figma
export as the bespoke-edit escape hatch (SVG master makes this cheap — an SVG import into Figma
is native) or strike it from the vision. Don't leave it zombie.

**M-16 · True L1–L5 checkpoint stack (L) — or formally re-scope**
"Check out at any layer / independently re-generable layers" was a LOCKED edit-model. Reality: a
fixed 6-part semantic SVG. The pm6 architecture fork (reorder/rename/duplicate don't fit) is the
same decision surfacing again. Options: (a) accept the semantic-SVG master as v1 ("checkpoints" =
versions, not layers) and rewrite the vision docs to match; (b) evolve the manifest so L1 imagery
and L2 concept are independently re-generable slots (partially true today via `_source_image` +
`layer_overrides`). Recommend (a) now + (b) selectively for imagery-regeneration.

**M-17 · Pillar-balanced planning (S–M)**
Pillars exist, calendar exists; the planning promise ("calendar balances across pillars — no five
promos in a row") has no logic. A monthly plan generator (N jobs across pillars with publish
dates) is also the natural INPUT to the Command Center fan-out.

**M-18 · Brand-deck ingestion (M, operator-asked)** — upload a brand-guideline/portfolio deck →
extract palette/fonts/logo/voice/refs into kit+brief with human review. Seams exist
(`extract_brief_sections`, `vision/study.py`).

**M-19 · Second tenant (Jasmine Media) + real Supabase login as daily path (M)**
Multi-tenant is the architecture but has never been exercised by a real 2nd agency; dev-token is
still the active auth path locally, and deploy is HELD on the `getDevToken()` hardening.

**M-20 · Smaller recorded-but-dropped items:** rejection-reason analytics dashboards ·
confidence-gated autonomy routing · competitor watch · per-job context record ("HANDOFF-per-
client") · per-provider budget + deadline-priority queue ordering · print profile · video module
(mimik-engine) · free-position logo (contract field) · column-grid snapping (documented v1
non-goal — fine).

---

## 4. Recent add-ons (this week) — and where they fit the vision

The canvas-editor program (Gates 1–4b) was **not in the origin plan** (which said "no custom
canvas editor — that's Canva's moat"). It accreted from a real trigger: the operator's ChatGPT
usability audit scored the editor 13/40, and the "editability" promise (a LOCKED reason for the
hybrid engine) demanded a trustworthy in-product surface. Verdict: **keep it — it's now a moat
component**, the "team nudges creatives" step of the loop, and it materially feeds the flywheel
(every edit = a preference signal via B-13). Shipped: canonical edit-state + undo/redo + inspector
+ zoom + 8-handle resize + rotation + rulers/guides/snap + keyboard nudge + pan + mobile structure
+ version-head stability + spatial marking (pending commit). Remaining editor backlog (multi-
select→align/distribute, layer navigator, format switcher = M-04, custom-colour "both" mode with
the client tints/shades gate) is **P2 against the product-depth gaps** — the editor is already the
strongest part of the product; the loop around it is not.

Also accreted, correctly: generation queue + crash-safe worker (A-03/04) — this is the plan's
"spend-minimizing queue" skeleton; the app-shell UX pass; the 3-persona audit habit.

---

## 5. Prioritized roadmap (P0→P3), sequenced for the multi-agent build

Operating model (proven): Opus = spec/review/Playwright-verify/commit · Codex = logic/geometry/
backend · AGY = big UI · Fable = design-craft. Hot files serialize: `creative_generation.py`
(backend) and `editor-state.ts`/`CanvasStage` (canvas). Disjoint scopes parallelize.

**P0 — the core promise, silently undelivered (all backend/ops; parallelizable as 3 lanes)**
1. **Drive end-to-end, once, for real** (M-07, S) — ops task + operator OAuth gate. *Lane A.*
2. **Re-wire QA critic + logo-contrast into live generate** (M-08, S–M) — Codex, hot-file
   `creative_generation.py`. Add profile guardrails as checks. *Lane B.*
3. **Brand-row seed drift reconciled** (S) — the dev tenant has 0 Brand rows but creatives exist;
   backfill/reseed so every screen reflects real data. *Lane A.*
4. **Simply Nikah silhouettes v1** (M-01, start of L) — first slice: vector-asset starter set
   (lattice/arch/avatar/connector/panel SVG parts) + 2 archetypes (Highlighted-Word Hero,
   Protection Symbol Hero) + AI-illustration fallback behind the gate + modesty QA check.
   Design-craft heavy: Opus specs from STYLE_PROFILES.md → Codex (SVG geometry/templates) + Fable
   (visual QA of output). *Lane C — parallel with 1–3; touches `creative/render/` not the hot file
   (new `nikah_templates.py`), then ONE serialized hot-file wire-in at the end.*

**P1 — the loop becomes true (mostly backend/logic; 2 lanes)**
5. **Island Cart cutout pipeline** (M-02, M) — bg-removal (browser-canvas like knockout.py, or
   rembg), price-tag/diagonal templates, product-photo intake. *Lane C continues.*
6. **A/B variants + pick capture** (M-05, M) — hot-file; then **close the learning loop** (M-06,
   M): generation consults profile/ranker; fix or remove the "Ranker is steering picks" label.
   *Lane B, strictly sequential on `creative_generation.py`.*
7. **Command Center**: A-08 queue panel (S, endpoints ready — AGY) → A-05 parser backend (M,
   Codex, `ops.py`) → A-09 ⌘K bar (M, AGY). *Lane D (web), parallel with B/C.*
8. **Brand fonts** (M-10, M) — kit upload UI (AGY) + @font-face in compositor/SVG (Codex).
   Prereq for every client's real look, including SN's typography.

**P2 — depth + polish (parallel lanes)**
9. Multi-format fan-out + format switcher + multi-slide carousel (M-04, M–L) — engine change
   (Codex) + editor control (canvas hot files, sequential with other canvas work).
10. Editor backlog: multi-select → align/distribute; layer navigator (+lock); custom-colour
    "both" mode **with the client tints/shades-only gate verified**; #11 resize drift; dev
    microcopy. (Canvas lane, sequential.)
11. Glo2Go carousel archetype + archetype generalization (M-03). Pillar-balanced month planner
    (M-17) — natural Command-Center companion.
12. Reference/fit-critic wired into prompts (M-12, S slice). Arabic/RTL for SN's Ayah archetype
    (M-11) if Q1b = yes.
13. Deploy re-sync: harden `getDevToken()` (NODE_ENV gate), real Supabase login as the daily
    path, redeploy prod (it's days stale), then Jasmine tenant (M-19).

**P3 — commerce + reach (each unblocks on an external gate)**
14. WhatsApp live (Meta portfolio) → weekly digest (M-13). 15. Storefront form → `/intake/claim`
+ Stripe test keys (M-14). 16. Figma export decision → thin SVG-export handoff or retire (M-15).
17. Brand-deck ingestion (M-18). 18. Video module. 19. Rejection analytics / confidence-gated
autonomy / competitor watch — only after M-06 produces real signal volume.

**Explicit vision re-scopes to write into CLAUDE.md/plan when accepted:** M-16 (semantic-SVG
master accepted as the v1 edit model; L1 imagery-slot regeneration only), M-15 (Figma = optional
escape hatch), browser-image harness = shelved (paid adapters are the path).

---

## 6. GAPS IN THE RECORD — pointed questions for the operator

The origin conversation clearly contained more than the disk captured. These answers complete the plan:

**Q1 (M-01). Simply Nikah asset sourcing — pick one:** (a) engine-generated SVG motif library
(code builds/composes the parts — biggest build, zero per-render cost, perfectly consistent);
(b) paid AI-illustration per render (validated once; per-image cost, consistency risk);
(c) commission a one-time designer starter pack of vectors and let the engine compose them
(fastest to on-brand). BUILD_STATUS asked this on 07-22 (open decision Q3) and it was never
answered — it is THE blocker on the flagship miss.
**Q1b.** Does SN's launch scope include the Ayah/Arabic-calligraphy archetype (→ Arabic font +
RTL work now), or is that phase-2 for them?

**Q2 (M-02).** Do you actually have Island Cart's product photos (and how many SKUs)? The profile
mandates real product cutouts — without the photos the whole IC pipeline has no input.

**Q3 (M-07).** Which Google account owns the production archive Drive, and can its OAuth consent
screen be published (Production) now? The refresh token + folder ID were live once on 07-20 —
what happened to that env (was it lost in the VPS redeploy, or never copied to the current
local `.env` semantics)?

**Q4 (M-09).** Two "command centers" exist in the record: the in-product ⌘K cockpit (A-05/08/09)
and the Track-B ALL-Mimik-businesses app (own repo, B1–B12, "operator-led fresh session").
Confirm: ⌘K now, Track B stays parked? And is the Track-B ambition still alive at all?

**Q5.** The $750/mo storefront + Stripe + 3-free-designs trial: is going LIVE a this-quarter goal,
or is the bar "all 3 dogfood clients rendering their real design language" first? (Everything in
P3 hangs on this.)

**Q6 (M-16).** Do you accept the semantic-SVG master as the edit model (versions = checkpoints),
retiring the literal "re-generate any of 5 layers independently" promise? This decision unblocks
the layer-navigator/reorder fork the editor keeps hitting.

**Q7.** Jasmine Media: still a real intended tenant (with its own users/clients), or has the
product quietly become Mimik-only? The multi-tenant claim has never been exercised.

**Q8 — record hygiene.** The origin session's richest material (the "grilling") lives in ONE
plan file; the per-client creative ambitions lived in chat until STYLE_PROFILES.md captured them
on 07-22 — 4 days after the plan. Anything else from the early conversations that never reached
disk (other client treatments? Jasmine-side clients? video ambitions beyond "plugs in later"?)
should be dictated into this doc's §3 now, while it's still recoverable.

---

## §7 — OPERATOR ANSWERS + SATELLITE VISION (2026-07-24, resolves §6)

### Answers to the blocking questions
1. **Simply Nikah assets** → engine-generated SVG vector library, sourced/seeded from **free vector packs/stacks online** (not paid-per-render). Build the generator + a starter modesty-safe vector set from free sources.
2. **Island Cart product photos** → **YES, they exist** (held by the ops manager; to be added post-deploy). Requirement this exposes: the **ops manager must be able to add per-client brand assets** — fonts, logos, brand assets, and client-shared assets — conveniently, so we can composite on top of them. STATUS: asset upload IS built (`POST /brands/{brand_id}/assets`, logo→`Brand.tokens.logo.ref`) — but the **compositor does not load brand FONTS** (quality cap) and there is no polished ops-side "brand asset library" UI. Gap = fonts-in-compositor + a convenient asset-management surface.
3. **Google Drive** → OAuth was set up on the **mimikcreations** Google account; env has the creds and the refresh-token file was shared. Presumed configured. So the 0-deliveries is "**never exercised in this dev instance**," not broken. ACTION: run ONE real approval end-to-end + confirm the file lands in the mimikcreations Drive folder; reconcile which env/account is live.
4. **Semantic-SVG master** → **ACCEPTED** as the edit model (retires literal per-layer regeneration; resolves the layer-tree fork). BUT two must-haves: (a) **wire the L1 imagery generation** — `creative/generate.py` is "the piece that was never wired" → this is why L1–L5 don't work today; (b) **PSD download must play along** — `GET /creatives/{id}/export.psd` IS built; verify it exports the semantic layers as real PSD layers (note: 2 pytoshop test failures — check the dependency).
5. **Stripe / storefront** → **DEFERRED** (hard to open a Stripe account from Sri Lanka). Bar first = "all 3 clients render their real design language." Revisit Stripe when an account exists.

### The satellite-integration vision (operator: "the main idea of the suite")
The suite was always meant to be an **orchestrator that calls the already-built Mimik tools** (confirmed in `docs/DECISIONS.md` #2 + `docs/FRONTEND_ROADMAP.md` Track B). This half is [DNB]. Elevate it in the roadmap:
- **Mimik_Proofkit → first-class QA + reporting satellite.** Today it's only an optional guarded import for brief extraction (`brief_extraction.py:186`). Vision: use it as the **QA engineer** (audit creatives/sites) AND as the **PDF / report / template generator** (client-ready deliverables). Proofkit itself "needs improvements" (operator). Call it via CLI/API — do not absorb.
- **Mimik_Leads / Mimik_Sales → CRM + acquisition surface via a CLEAN BOUNDARY.** `FRONTEND_ROADMAP` B12 CRM is fed from leads + Proofkit outputs. HARD CONSTRAINT (CLAUDE.md + DECISIONS #2): **Mimik_Sales is confidential (lead PII + keys) — NEVER import it into this product.** Integrate by calling its API / reading exported outputs, never by absorbing the repo/data.
- **Creative engine** → core (already in-repo).
- **Planflow (FRONTEND_ROADMAP B8)** → e-commerce / Meta-ad-planning satellite (same-stack monorepo) — call it, don't absorb.
- **Track-B internal command-center** → one cockpit surfacing ALL Mimik businesses (leads, Proofkit, finance, hosting, CRM, Planflow). Big [DNB] surface; the ⌘K Command Center is the entry to this.

### Revised P0 for the fresh session (folding the answers in)
- **Lane A (backend/logic, Codex):** run Drive end-to-end once + reconcile the mimikcreations OAuth env; re-wire `run_brand_qa` + logo-contrast into the LIVE generate path; wire `creative/generate.py` L1 imagery generation so L1–L5 actually produce.
- **Lane B (per-client craft, Codex + design):** Simply Nikah silhouettes v1 (engine vector set from free packs + modesty QA) + Island Cart product-cutout pipeline (pending photos from ops).
- **Lane C (assets/quality):** load brand FONTS into the compositor; a convenient ops-side brand-asset library UI; verify PSD export produces real layers.
- **Lane D (satellite bridge):** stub the Proofkit QA/report call boundary + the leads/CRM read boundary (confidential-safe).
- Deferred: Stripe/storefront.
