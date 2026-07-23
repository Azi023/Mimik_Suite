# Mimik Suite — Product-State Inventory (truthful, evidence-based)

> Written 2026-07-23. A complete accounting of what was PLANNED → what is BUILT & WORKING →
> what is BUILT-BUT-STALE/unconnected → what is PARTIAL → what was DISCUSSED-BUT-NEVER-BUILT.
> Every non-trivial claim cites `file:line` or an endpoint. Where the live DB or prod config
> could not be inspected from code, the claim is marked **unverified**.
>
> Sources: `~/.claude/plans/hi-i-want-to-sunny-fox.md` · `CLAUDE.md` · `docs/PRODUCT_PM_REPORT.md`
> · `docs/BUILD_STATUS.md` · `HANDOFF.md` (all entries) + code in `api/`, `creative/`, `web/`.

---

## 1. The intended product & the full loop — step-by-step verdict

The loop (from the plan + CLAUDE.md): **onboard client → auto-draft brand brief → 5-layer
creative engine generates → auto brand-QA critic → ops board/calendar/SLA → client bounded
portal (approve/edit/comment) → approve → auto-archive to Google Drive → learn (per-client
preference profile).**

| # | Loop step | Verdict | One-line reality |
|---|-----------|---------|------------------|
| 1 | Onboard client | **WORKING** | `web/app/onboarding/` wizard + `POST /clients`; autosave; specific-error handling shipped. |
| 2 | Auto-draft brand brief | **PARTIAL** | `api/services/brief_extraction.py` exists but the real scrape path needs `proofkit`+Playwright *installed* (guarded optional import, line 186/202); brief model/versioning is real (`briefs.py`, `/{brief_id}/revise` mints a new version). Auto-extraction from a URL is **not verified to run** in the current env. |
| 3 | 5-layer creative engine generates | **PARTIAL/WORKING (one client)** | `POST /clients/{id}/creatives:generate` → `generate_client_creative` (`creative_generation.py:828`) works end-to-end. But only **Glo2Go** has a real render path (`glo2go_templates.render_glo2go`); Simply Nikah + Island Cart imagery resolve to placeholders unless paid gate on. The "5 layer" master is the SVG (`creative/export/svg.py`), not a true L1–L5 checkpoint stack. |
| 4 | Auto brand-QA critic | **BUILT-BUT-STALE** | `run_brand_qa` (WCAG/contrast/safe-zone/logo + conditional scrim) exists in `creative/pipeline.py:114`, but the **live generate path bypasses it** — `creative_generation._render_creative_artifacts` (line 316) never calls it. **Not a gate.** |
| 5 | Ops board + calendar + SLA | **WORKING** | `GET /ops/board` + `POST /ops/jobs/{id}/transition` (`ops.py:177/222`); drag-transitions (A-06); `CalendarView.tsx` (164 lines) + `/ops/calendar`; at-risk via `Job.is_at_risk()`. |
| 6 | Client bounded portal (approve/edit/comment) | **WORKING** | `portal.py`, magic-link `review/[token]`, client-role quota-limited revise (B-11, `9288666`). |
| 7 | Approve → auto-archive to Google Drive | **BUILT, REAL CODE — but NOT active (defaults to local disk)** | See §2 Drive row + the definitive answer below. |
| 8 | Learn (per-client preference profile) | **PARTIAL — captured + displayed, not closing the loop** | Signals captured & a heuristic ranker exists, but generation never consults it. See §2. |

**Command Center ⌘K cockpit** (the operator's headline ask) is **outside the loop and NOT built** — see §2.

---

## 2. Feature-by-feature status table

| Feature | Planned intent | Status | Evidence | Gap / what's missing |
|---|---|---|---|---|
| Onboarding | Create client + capture medium/dos/don'ts/refs | **WORKING** | `web/app/onboarding/`, `OnboardingFields.tsx`, `POST /clients` | Review step omits audience/voice/logo (HANDOFF #14). |
| Brand-brief auto-draft | URL → scrape → colours/logo/fonts/tone | **PARTIAL** | `api/services/brief_extraction.py:186` (proofkit optional, guarded) | Real extraction needs proofkit+Playwright installed; unverified it runs. |
| Brief versioning / signoff / freeze | Immutable frozen version on signoff | **WORKING** | `briefs.py:146` `POST /{brief_id}/revise` (201, new version) | — |
| 5-layer engine (L1..L5 recipe) | Non-destructive checkpoint stack | **PARTIAL** | `creative/export/svg.py` (layered SVG master); `build_manifest` in `creative/pipeline.py` | It's a semantic 6-layer SVG (background/panel/headline/subhead/cta/badge), **not** a re-generable L1–L5 checkpoint stack; "check out at any layer" not real. |
| SVG master / editable export | SVG-first, then PSD | **WORKING** | `POST /exports/svg`, `creatives/{id}/export.psd` (`creatives.py:284`) | PSD text is rasterized (live-text only in SVG). |
| Imagery adapter (swappable) | Sub now → API later, config swap | **WORKING (adapter) / PARTIAL (coverage)** | `creative/adapters/` (openrouter, gemini_image, gpt_image, pexels path) | Only Glo2Go (Pexels photo) renders real imagery; Simply Nikah/Island Cart → placeholder unless `MIMIK_ALLOW_PAID_IMAGES` on. |
| Auto brand-QA critic (gate) | Hard gate before human review | **BUILT-BUT-STALE** | `creative/qa/checks.py:run_brand_qa`, called ONLY in `creative/pipeline.py:114`; **not** in `creative_generation.py` live path | Wire `run_brand_qa` into the generate endpoint, or it's decorative. |
| A/B dual-model generation | 2 backends/seeds → pick logged | **NOT-STARTED** | no variant/seed/AB logic in `creative_generation.py` | No A/B; single render only. |
| Ops board + drag transitions (A-06) | Kanban, status moves fire procedures | **WORKING** | `ops.py:177/222`, `_ALLOWED_TRANSITIONS`, →Approved converges on `submit_approval` | — |
| Calendar + SLA (A-07) | 30-day view, at-risk flags | **WORKING** | `web/app/calendar/page.tsx`, `CalendarView.tsx`, `/ops/calendar` (`ops.py:198`) | Derives entries from board jobs client-side; adequate. |
| **Command Center ⌘K (A-05)** | Parse "generate 5 Educational posts for Glo2Go" → fan out | **NOT-STARTED** | grep `command:parse\|command_center\|/ops/command` in `api/` → **zero matches**; no `command_center.py` | Entire backend parser + endpoint missing. |
| **Queue panel UI (A-08)** | Show generation queue/budget | **NOT-STARTED (UI)** | backend `GET /ops/queue`,`/ops/queue/stats`,`/ops/usage` live (`ops.py:113-174`); `web/lib/api.ts` has **no** `listQueue/queueStats/usageReport` fn | A-04 endpoints exist but **no UI consumes them**. |
| **Command bar UI (A-09)** | ⌘K palette in the shell | **NOT-STARTED** | no `cmdk`/CommandBar component in `web/components/` | Depends on A-05 (also missing). |
| Generation queue + worker (A-03/A-04) | Async fan-out worker | **WORKING (backend)** | `generation_queue.py`, `generation_worker.py`, lifespan-started; `/ops/queue*` + `/ops/usage` | No UI (see A-08). |
| Canvas editor (Gates 1–4b) | Safe template editor | **WORKING (desktop)** | `web/components/canvas/{CanvasStage,CanvasEditor,Inspector,ZoomControls,VersionRail}.tsx`, `editor-state.ts`; rotation `2446ea3`, rulers/guides `710d520`, keyboard `1feb30a`, version-head `f1fba17` | Mobile @375px canvas = 0×0 (open P0). |
| Editor: multi-select / align-distribute / layer navigator / format switcher / custom colours / spatial marking | Fuller toolkit | **NOT-STARTED** | none in `web/components/canvas/`; HANDOFF pm7 "STILL OPEN" + product-decision list | Multi-select needs selection-set refactor; format switcher + custom-colour "both" mode signed off but unbuilt. |
| Client bounded portal (B-11/B-12) | Magic-link, quota revise | **WORKING** | `portal.py`, `review/[token]`, client quota (`9288666`), 24h quota → 429 | B-12 portal editor polish deferred. |
| Magic-link | No-login approve/change | **WORKING** | `review/[token]/`, 72h TTL guard in `approval_flow.py` | — |
| **Approve → Google Drive auto-archive** | Enforced in code on approval | **REAL CODE, wired, but DEFAULTS TO LOCAL DISK** | see definitive answer ↓ | Prod almost certainly archiving to local FS, not Drive — **unverified prod env**. |
| Deliveries surface (A-11) | Archive ledger view | **WORKING** | `web/app/deliveries/page.tsx` (100 lines) → `listDeliveries` → `GET /deliveries` (`deliveries.py:22`) | Shows `drive_path` (which is a local path unless Drive configured). |
| Learning loop / PreferenceProfile (B-13) | Signals feed future gen | **PARTIAL — captured + queryable, NOT used in generation** | capture: `edit_signals.py`, `approval_flow.py` APPROVAL/REJECTION signals, `PreferenceSignalRow` (`models.py:285`); ranker: `preferences.py:139 /rank`, `build_profile`, `ranker_active()` | `creative_generation.py` never calls `rank_variants`/`build_profile` → the ranker **does not steer generation**; the web "Ranker is steering picks" label (`preferences/page.tsx:88`) is aspirational. Promotion endpoint `/preferences/promote` exists. |
| Tenant/auth (Supabase + magic + dev-token) | Managed auth, RBAC | **WORKING (Supabase code) / dev-token is the ACTIVE path** | `api/core/auth.py:30` `verify_supabase_jwt` + JWKS; dev-token bootstrap coexists | Real Supabase multi-account login **deferred / unverified locally** (HANDOFF: dev-token only). |
| IDOR / tenant isolation | AuthZ at data layer | **WORKING** | `test_tenant_isolation.py` green; live-probed in HANDOFF; client-confine in `ops.py:187`, `deliveries.py:30`, `jobs.py` | Constraint #2 holds. |
| WhatsApp notifications | Approval nudges | **NOT-STARTED (inert)** | `config.py` `whatsapp_provider="none"` → recorded PENDING, never sent | Meta Cloud path coded but off. |
| Billing / Stripe (P5) | $750/mo + trial | **PARTIAL** | `billing.py`, `config.py` stripe_* (empty) | Refuses to call Stripe without keys; storefront intake bridge not wired. |
| Satellite: Proofkit capture/qualify | Reuse for extraction | **PARTIAL (optional)** | `brief_extraction.py:186/202` guarded `import proofkit` | Only used if importable; not a hard dependency, unverified installed. |
| Satellite: Figma export (L4 handoff) | Deep-edit round-trip | **NOT-STARTED** | grep `figma` in `creative/`,`api/` → zero | Plan's L4 Figma handoff never built. |
| Satellite: mimik-engine video | Video module later | **NOT-STARTED** | no import anywhere | As planned (deferred). |

---

### Definitive answer — is the Google Drive integration real and wired?

**Yes, the code is real and production-shaped — but it is almost certainly NOT active; the
system archives to the LOCAL FILESYSTEM by default.**

- Two real backends exist: `GoogleDriveArchive` (service-account JWT-bearer) and
  `GoogleDriveOAuthArchive` (user refresh-token grant) — `creative/archive/google_drive.py`.
  Real folder-ensure + multipart upload to `Mimik Clients/<Client>/<YYYY-MM>/<job>/<file>`
  over stdlib urllib (lines 152–185). Not a stub.
- It IS wired into approval: `approval_flow.submit_approval` → on APPROVE calls
  `run_archive(...)` with `archive = archive or get_archive_backend()`
  (`approval_flow.py:182`), which renders the manifest → uploads → records a `Delivery` →
  sets job ARCHIVED. The ops board →Approved transition converges on the same path
  (`ops.py:242-267`). So approval genuinely fires an archive side-effect.
- **BUT the default backend is local, not Drive:** `get_archive_backend()` reads
  `ARCHIVE_BACKEND` env, **default `"local"`** → `LocalArchive` writes to disk
  (`creative/archive/__init__.py:30`). Drive only engages if `ARCHIVE_BACKEND=google_drive_oauth`
  (or `google_drive`) AND `GOOGLE_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN` + `DRIVE_ROOT_FOLDER_ID`
  are set (`config.py:112-119`, all default `""`; `from_env` raises `ArchiveError` if absent).
- The OAuth refresh token must be minted once via `scripts/drive_oauth.py`. **No HANDOFF/SESSION
  entry records that being run or those env vars being set in prod → unverified, and the strong
  presumption is Drive is OFF.** The `Delivery.drive_path` shown in the deliveries UI is therefore
  a **local filesystem path**, not a Drive URL, in the current deployment.

**Operator takeaway:** the "auto-archive to Drive on approval" promise is *code-complete* but
*operationally inactive*. To turn it on: run `scripts/drive_oauth.py`, set the four env vars,
set `ARCHIVE_BACKEND=google_drive_oauth`, restart. Verify a real approval lands a file in Drive.

---

## 3. Built-but-not-updated / disconnected — the operator's specific worry

Concrete "exists but stale/unwired/seeded-not-real" items, each verified:

1. **QA critic is orphaned.** `run_brand_qa` (real WCAG/contrast/safe-zone/logo gate,
   `creative/qa/checks.py`) is only invoked in `creative/pipeline.py:114`, which the **live
   generation endpoint does not use** (`creative_generation._render_creative_artifacts:316`
   renders directly). The "auto brand-QA before human review" promise is not enforced in the
   path users actually hit.

2. **The taste-ranker is captured-and-displayed but never consumed.** Signals are written on
   every approve/reject/edit (`edit_signals.py`, `approval_flow.py`), a ranker exists
   (`preferences.py:139`, `build_profile`, `ranker_active()`), and the UI shows "Ranker is
   steering picks" (`web/app/clients/[id]/preferences/page.tsx:88`) — but **no generation code
   calls the ranker**. The loop is open; the label overstates reality.

3. **Drive path shown but archive is local.** `web/app/deliveries/page.tsx` renders
   `drive_path`, which under the default `ARCHIVE_BACKEND=local` is a local FS path, not Drive
   (§2). Cosmetically implies Drive; functionally isn't.

4. **A-04 queue/usage endpoints have no UI consumer.** `GET /ops/queue`, `/ops/queue/stats`,
   `/ops/usage` are live (`ops.py:113-174`) but `web/lib/api.ts` has no function calling them —
   backend built, frontend (A-08) absent. Dead-ended backend surface.

5. **Brand rows vs. creatives mismatch (HANDOFF pm7).** The dev tenant reportedly has **0 Brand
   rows** yet clients have creatives on the board, so the "Create brand kit" CTA fires for every
   client. Note the discrepancy: `scripts/seed_profiles.py:63` DOES create Brand rows (Simply
   Nikah/Glo2Go/Island Cart) — so the board creatives were populated by a *different* path
   (generated/seeded) than the profile seed, or against a different tenant. **Live DB unverified
   here; flag as seed/tenant drift.**

6. **Two onboarding wizards existed** — dead `web/components/OnboardingWizard.tsx` fork was
   deleted (`a289187`); the live one is `web/app/onboarding/OnboardingWizard.tsx`. Watch for
   re-drift.

7. **Simply Nikah / Island Cart generate to placeholders** — `creative_generation._source_image`
   skips GENERATED_VECTOR/PRODUCT_CUTOUT to a solid placeholder (`_solid_placeholder:183`);
   only Glo2Go's photo path is real. Two of three "live" clients don't produce real imagery
   without the paid gate.

8. **`creative/pipeline.py` and `creative/generate.py`** appear to be an earlier/parallel
   pipeline (imported for `build_manifest` only). The QA + scrim logic living there is the
   stranded remnant of the pre-v2 flow.

9. **WhatsApp channel** records notifications as PENDING and never sends (`config.py`
   `whatsapp_provider="none"`) — the plan's "weekly digest / approval nudge on WhatsApp" is inert.

---

## 4. Discussed-but-never-built

- **Command Center ⌘K** (parse-and-fan-out) — A-05/A-08/A-09. No backend, no UI (§2).
- **A/B dual-model generation** + **taste-ranker steering / auto-select** — captured but not
  closed (§3.2). No A/B.
- **Figma deep-edit export/import (L4 handoff)** — zero code.
- **Reference-research → vet/score before L2** — `creative/references/gather.py` +
  `fit_critic.py` exist as R&D, but not wired into the live generate flow; sources = Openverse/
  Unsplash/Pexels stubs, Pinterest/Dribbble/Behance are TODO stubs.
- **True L1–L5 re-generable checkpoint stack / "check out at any layer"** — the model is a
  fixed semantic SVG, not independent regenerable layers (HANDOFF pm6 architecture-fork note).
- **Format/aspect switcher (1:1/4:5/9:16 re-render)** and **custom-colour "both" mode** —
  operator-signed-off, not built.
- **Multi-select, align/distribute, layer navigator** in the editor.
- **Rejection-reason taxonomy analytics, confidence-gated autonomy, competitor watch, weekly
  digest, auto-brief-from-WhatsApp** — plan "out-of-box" ideas, no implementation.
- **Storefront → Suite intake bridge (mimikcreations.com/unlimited → auto-tenant)** and **Stripe
  checkout/webhooks** — `billing.py` scaffold only, keys empty.
- **Real Supabase multi-account login in practice** — code present, dev-token is the active path.
- **Mobile canvas editor** — broken at 375px (§ below), the one open P0.

---

## 5. Prioritized gap list (P0 → P3) for the next session

**P0 — the core promise is silently not delivered:**
1. **Turn on / verify Drive archive** (S). *Why:* "auto-archive to Drive on approval" is the
   headline ops fix; it currently writes to local disk. Run `scripts/drive_oauth.py`, set env,
   `ARCHIVE_BACKEND=google_drive_oauth`, prove one approval lands in Drive.
2. **Wire the QA critic into the live generate path** (S–M). *Why:* the "no greenish-doctor
   errors" promise depends on `run_brand_qa` actually gating; today it's bypassed.
3. **Fix the mobile canvas editor @375px** (M). *Why:* only remaining audit P0; canvas collapses
   to 0×0. Needs a mobile reference first (frontend-design precondition).

**P1 — significant missing pieces:**
4. **Close the learning loop** (M). *Why:* signals + ranker exist but generation ignores them;
   either consult `rank_variants` at generate/pick time or stop claiming "ranker steering picks."
5. **Command Center A-05 backend + A-09 bar** (L). *Why:* the operator's cockpit vision ("generate
   5 posts for Glo2Go"); nothing exists yet.
6. **A-08 queue/usage panel UI** (S). *Why:* A-04 endpoints are built and unused — cheap win,
   makes the async worker visible.
7. **Backfill Brand rows / fix seed drift** (S). *Why:* every client shows "missing brand"; erodes
   trust that data is real.

**P2 — enhancements / debt:**
8. Real imagery for Simply Nikah + Island Cart (M) — 2 of 3 clients placeholder.
9. Format/aspect switcher + custom-colour "both" mode (L) — signed off.
10. Multi-select / align-distribute / layer navigator (M).
11. Retire/merge stranded `creative/pipeline.py`+`generate.py` (S) — dead-path debt.

**P3 — later:**
12. WhatsApp Cloud send, Stripe/storefront bridge, Figma handoff, reference-research wiring,
    real Supabase login for persona QA, deploy hardening (`getDevToken` gate on NODE_ENV).

---

## Appendix — verification method
Read the plan, CLAUDE.md, PM report, BUILD_STATUS, all HANDOFF entries; then grepped/read
`api/routers/*`, `api/services/{approval_flow,creative_generation,generation_queue,usage}.py`,
`api/db/models.py`, `api/core/{auth,config}.py`, `creative/archive/*`, `creative/qa/*`,
`creative/pipeline.py`, `web/app/*`, `web/components/*`, `web/lib/api.ts`. Items I could not
confirm from code (live DB row counts, prod env vars) are marked **unverified**.
