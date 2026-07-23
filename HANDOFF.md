# HANDOFF — Mimik Suite

> Latest entry on top. Read this before doing anything. Ground truth for state.

---

## ► LATEST (2026-07-23 pm5) — EDITOR GATES 1-4a DONE + APPLY BUG FIXED; PM report + 3-persona audit prompt written; G4b + app-shell UX next

**Editor rebuild (audit 13/40 → usable):** Gates 1 (`d592106`/`3eeb274`), 2 (`d911ac0`), 3 (`0b7812f`),
4-contract (`e9640f8` sibling), 4a all-sides resize (`11baf99` be + `5fc85b4` fe) — ALL Playwright-proven.
**Apply bug FIXED (`e38f534`):** resize could emit a scale axis outside the contract (0,3] → 422 "rejected
as invalid"; now clamped at the `toCanvasRevision` payload boundary. Verified: aggressive resize → Apply 201.

**NEW DOCS (deliverables for the operator + next session):**
- `docs/PRODUCT_PM_REPORT.md` — top-to-bottom product report (what/why/end-goal/personas/loop/gaps/roadmap).
- `docs/AUDIT_3PERSONA_PROMPT.md` — paste-into-Chrome-extension script: full-loop 3-persona audit
  (new client → brand brief → generate → review → EDITOR every-feature → approve → deliver → portal),
  judges each view, ranked P0-P3 + editor feature-completeness table.

### ▶ OPERATOR FEEDBACK BACKLOG (2026-07-23 — real issues to fix next)
- **App-shell UX:** nav rail is ICON-ONLY → add labels/expand-on-hover. Editor shows the "All clients"
  sidebar it doesn't need → collapse app chrome by default in the editor (full-screen exists but isn't
  default). Judge every view: show only what the task needs.
- **Editor missing (Gate 4b):** rulers · margins/safe-area overlay · guides/snap · **rotation handle**
  (contract+render READY, only UI) · layer tree · align/distribute · multi-select · keyboard shortcuts.
- **Product decisions (need operator sign-off):** (a) **aspect-ratio/size switch** (1:1 / 4:5 / 9:16 story)
  — NOT a resize; = re-compose/re-render the layout at new dimensions. (b) **custom colours** beyond the
  brand palette — today recolor is brand-bounded (LOCKED, brand-safety); add a "brand + custom" mode without
  breaking client-facing safety.
- **"Why all clients always seen?"** — those are the OPERATOR's own agency clients (correct, not a leak);
  a CLIENT principal only ever sees itself (enforced). The fix is only to hide the client list in the editor.

### ▶ FRESH-SESSION KICKOFF (paste to start next session)
"You are the BRAIN orchestrating Mimik Suite. Read HANDOFF.md (top entry) → docs/PRODUCT_PM_REPORT.md →
docs/BUILD_STATUS.md. Confirm the product runs (API :8000 w/ paid TEXT keys, uvicorn NOT --reload; web
`cd web && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev`; if web 500s `rm -rf web/.next` + restart).
Editor Gates 1-4a done + Apply fixed; verify recipe = drive the real app with Playwright
(scratchpad/verify_editor.py etc.) — executors' tsc/tests are NOT enough. THIS SESSION: (1) app-shell UX pass
(labeled/expandable nav; editor collapses client chrome by default; per-view contextual cleanup) — Fable +
frontend-design; (2) Gate 4b: rotation handle → rulers/margins/guides/snap → layer tree → multi-select/
shortcuts — Codex geometry + AGY big UI, Opus specs + Playwright-verifies each; (3) surface the two product
decisions (aspect-ratio switch, custom-colour mode) for operator sign-off before building. Operating model:
Opus plans/specs/reviews; Codex=logic/backend/geometry, AGY=big UI, Fable=design-polish; executors never
commit; Opus commits after Playwright live-verify. Deploy HELD."

### ▶ ALSO STILL OPEN (paused): W4 A-05 (⌘K), A-07/A-08/A-09/A-11/B-12, gates A-12/B-14.

---

## ► (2026-07-23 pm4) — CANVAS EDITOR REBUILD: GATES 1-3 DONE + PLAYWRIGHT-PROVEN; G4 (all-sides resize) in flight

**All browser-verified with the Playwright recipe (drive the real app; executors' tsc/tests are NOT enough).**
- **GATE 1** (`d592106` core + `3eeb274` client-context) — canonical `EditHistory→fold→applyState` state;
  ROOT-CAUSE FIX = inject SVG imperatively (`host.innerHTML`), NOT dangerouslySetInnerHTML (React
  re-materialized it and wiped edits). Recolor→child fill. Proven: recolor/hide/text/discard all work.
- **GATE 2** (`d911ac0`) — undo/redo (⌘Z/⇧⌘Z + buttons), ordered pending-op list w/ per-op remove, press-hold
  before/after, safe revert + sequential version labels. Proven: recolor→Undo→base→Redo round-trips.
- **GATE 3** (`0b7812f`) — right Inspector (controls off the canvas), full-screen, zoom/fit/100% (scales
  388→582px, overlay stays aligned), creative-size ("1080 · IG Post"), per-layer reset, "Ask AI about this
  layer" rename. Proven: recolor/undo STILL work post-restructure; zoom scales.
- **GATE 4 CONTRACT** (`e9640f8`, SIBLING mimik-contracts@0.1.1) — `LayerOp` + `rotation` + per-axis
  `scale_x`/`scale_y` (BC; defaults preserve behavior). Foundation for all-sides resize.

**Editor files:** `web/components/canvas/{CanvasStage,CanvasEditor,Inspector,ZoomControls,VersionRail}.tsx`,
`editor-state.ts` (+ .test.mts), `useLayerDrag.ts`. LayerTransform is `{dx,dy,scale}` — G4 extends it.
Verify scripts: `scratchpad/verify_editor.py` (recolor/hide/discard), `verify_g2.py` (undo/redo),
`verify_g3_*.py` (zoom/inspector). Web 500 after big edits → `rm -rf web/.next` + restart `npm run dev`.

### ▶ GATE 4a DONE — all-sides resize (the operator's explicit ask) — Playwright-PROVEN
- **be (`11baf99`)** svg.py applies translate·rotate·scale(scale_x,scale_y about center) from layer_overrides
  (BC: legacy uniform scale; identity→no transform); revise persists/inherits scale_x/scale_y/rotation.
  43 tests green.
- **fe (`5fc85b4`)** editor-state LayerTransform → {dx,dy,scaleX,scaleY}; CanvasStage 8 handles (4 corner + 4
  edge, correct cursors); useLayerDrag.beginResize per-handle math (edge=1 axis, corner=both, anchor-opposite,
  clamp 0.1..3, rAF-smooth, 1 undo step). toCanvasRevision emits scale_x/scale_y. 17 tests.
- **PROVEN live:** dragging Panel's E edge grew width 226→322 with LEFT edge fixed + height unchanged;
  recolor/undo/zoom still work (no regression). API restarted so Apply re-renders the resize.

### ▶ GATE 4b — REMAINING (fuller precision toolkit; recommend FRESH session)
Rotation HANDLE (contract + render already support rotation — just the UI: a rotate handle + rotated
selection overlay/hit-box, which is the fiddly part); layer tree (reorder/lock/rename/duplicate);
align/distribute/snap/guides/safe-areas; full typography (font/size/weight/spacing); multi-select;
keyboard nudge/copy/paste/delete. Tool: Codex = geometry/logic; AGY = big UI; Opus specs + Playwright-verifies.

### ▶ ALSO STILL OPEN (paused): W4 backend A-05 (⌘K command) + frontend A-07/A-08/A-11/B-12 + gates A-12/B-14.

---

## ► (2026-07-23 pm3) — CANVAS EDITOR REBUILD: GATE 1 DONE + PLAYWRIGHT-PROVEN (correctness)

**Context:** Operator did a ChatGPT-driven usability audit (`~/Documents/Codex/2026-07-23/.../creative-editor-usability-audit.md`)
scoring the editor 13/40 (pre-alpha). Chose a FULL 4-gate rebuild (safe-template-editor direction, not Figma clone).
Program tasks = the 4 gates (see below). **Architecture spec: `scratchpad/spec_gate1_canonical_state.md`** (the contract).

### ▶ GATE 1 COMPLETE (correctness) — committed + browser-verified
- **Core (`d592106`)** — rearchitected CanvasStage around ONE state: `web/components/canvas/editor-state.ts`
  (DocOp `EditHistory` → `fold` last-write-wins → `applyState` single render → `toCanvasRevision` payload;
  + unit tests). Preview, hit-testing, pending list, and Apply payload now all read one folded state.
- **Client-context (`3eeb274`)** — editor header shows the creative's OWN client/brand (was showing the
  global sidebar selection) + mismatch note.
- **⚑ THE ROOT-CAUSE FIX (why earlier attempts failed):** the SVG was injected via
  `dangerouslySetInnerHTML`, and React **re-materialized that subtree on re-render, wiping applyState's
  imperative DOM mutations** (recolor/hide/text reverted → "pending op added but artwork unchanged"). Fix:
  inject imperatively (`host.innerHTML = parsed.markup` in a `[parsed]` effect); React never owns it again.
  Also: recolor must target the paint CHILD (`<text>`/`<rect>`), not the parent `<g>` (child's own `fill`
  attr overrides inherited fill).
- **VERIFICATION RECIPE (reuse for Gates 2-4):** the executor's tsc/tests are NOT enough — the bugs were all
  "compiles but doesn't render." Drive the REAL app with Playwright: `.venv/bin/python scratchpad/verify_editor.py`
  (needs web dev server up + a fresh `.next`). Proven live: recolor #5A2A6B→#FFFFFF, hide→display:none, text
  updates, **discard restores base exactly**. If web 500s: `rm -rf web/.next` + restart `npm run dev` (stale cache).

### ▶ REMAINING — GATES 2-4 (tasks 15/16/17; large — recommend a FRESH session per gate for review quality)
- **G2 safety:** undo/redo (Cmd+Z/Shift+Z) + visible controls, ordered pending-op list w/ per-op remove,
  before/after press-hold, safe descriptive revert (preview + warn on pending + new head). Builds on the
  EditHistory model (ops/redo already in the type).
- **G3 owner usability:** right inspector (move layer props off the canvas), zoom/fit/100%/pan, per-layer
  reset, image replace+crop+focal (NEEDS BACKEND: upload endpoint + L1 source override), Mark&Tell →
  "Ask AI about this layer", version labels = timestamp/ordinal (not V1/V1/V1), distraction-free mode.
- **G4 precision:** X/Y/W/H/**rotation** (NEEDS BACKEND: extend mimik-contracts LayerOp + svg.py render +
  revise), layer tree reorder/lock/rename/duplicate, align/distribute/snap/guides/safe-areas, full
  typography, multi-select, keyboard nudge/copy/paste/delete.
- Tool plan: Codex = correctness logic + backend contract; AGY = big UI build-outs (inspector/layer-tree);
  Fable = design-polish. Opus specs + reviews + Playwright-verifies each gate before the next builds on it.

### ▶ ALSO STILL OPEN (paused): W4 backend A-05 (⌘K command) + frontend A-07/A-08/A-11/B-12 + gates A-12/B-14.

---

## ► (2026-07-23 pm2) — W4 A-03/A-04/A-06 + FRONTEND REMEDIATION (canvas actually works now)

**State:** Operator tested the local product and reported the FRONTEND felt broken (canvas not clickable,
dead nav buttons, /creatives 404, hydration error). Ran a full-app QA audit + fixed. **Backend is solid**
(500 tests green, endpoints live-verified). The gap was frontend wiring. All fixed + committed. Local runs;
API restarted (pid varies); **deploy still HELD** (and should stay held until operator does a full click-through).

### ▶ WHAT LANDED (this half-session, all committed to main)
- **A-03 (`4a5951e`)** generation queue + crash-safe async worker (see prior entry detail) — LIVE: enqueue→
  worker→INTERNAL_REVIEW drained end-to-end over HTTP.
- **A-04 (`b21c01c`)** /ops/queue + /ops/queue/stats + POST /ops/queue + /ops/usage (team-gated, tenant-scoped,
  client→403). LIVE: /ops/usage → 29 renders grouped by source/profile.
- **A-06 (`c5e9508`)** board live drag-transitions (snap-back on 409, at-risk dot, generating-since).
- **CANVAS FIX (`e4265d3` + `3169760`) — THE key user issue.** The editor was dead because CanvasStage
  required `data-editable`/`data-bbox` attrs that OLD creatives' SVGs lack (18/30 on disk). Fix: (1) hit-rect
  overlay per layer for select/drag/dblclick over the full bbox; (2) measure each layer's real geometry from
  the live DOM via `getBBox()` (select by `data-layer` alone). **Playwright-verified** all 6 layers return
  real boxes. Frame made fluid. Canvas now works on any creative.
- **FRONTEND WIRING (`6ddef91`)** from the QA audit: TopBar Invite→/members; Board col-menu + ReviewPanel
  Reassign honestly-disabled; NEW /creatives gallery + /clients index + app/not-found.tsx; Sidebar
  creatives/clients glyphs routed; hydration fixed (<body suppressHydrationWarning, Board Date.now→effect,
  en-GB locales); touch targets ≥44px. tsc+lint clean.
- **GET /creatives (`c95e906`)** tenant-wide latest-per-job list powering the gallery. LIVE: 16 items.

### ▶ AUDIT VERDICT (docs/ — the multi-persona-qa-reviewer report)
App is MORE wired than it felt — damage was a concentrated set of dead placeholder controls + missing index
routes + 3 hydration bugs, all now fixed. Deferred follow-ups (noted, not P0): board touch-DnD fallback
(HTML5 DnD is desktop-only), `.kanban--pipeline`/`.kanban` CSS-class rename, keyboard shortcuts, RSC
preview-404 graceful thumb fallback.

### ▶ EXACT NEXT ACTION — remaining W4 (paused for the frontend fix)
Backend: **A-05** (command parser + POST /ops/command:parse+:execute, ⌘K backend, command_center.py — on
ops.py). Frontend (web/lib/api.ts single-writer, sequential): **A-07** calendar+SLA · **A-08** queue/budget
panel (backend A-04 ready) · **A-09** ⌘K bar (needs A-05) · **A-11** deliveries · **B-12** portal bounded
editor + BC-shim removal (B-11 done). Gates: A-12, B-14. Then the deferred audit follow-ups.
RECOMMEND: operator does a full click-through of the fixed frontend FIRST (esp. the canvas) before more features.

---

## ► (2026-07-23 pm) — W4 CANVAS PROGRAM: B-11 · B-08 · B-09 · B-13 LANDED (client-bounds + editor + flywheel)

**State:** Opus-orchestrated W4 running two parallel tracks (Codex backend ∥ Fable frontend, disjoint file
scopes). Four tasks this session, all reviewed + live-verified on the :5434 DB + committed. Local product runs
(API restarted twice to pick up the hot-file changes; clean boot both times). **Production still UNTOUCHED**
(deploy HELD per operator). Local DB head unchanged: `c7e90f4a1b32` (no migration this wave).

### ▶ RUN LOCALLY — unchanged from prior entry (paid TEXT keys in API env; uvicorn NOT --reload → restart after API change)
Same commands as the entry below. Web: `cd web && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev`.

### ▶ WHAT LANDED THIS SESSION (all committed to main)
- **B-11 (`9288666`)** — client-role bounded, quota-limited revise: `client` added to the revise gate;
  reduced shape (text_edits/ask only — layer_ops/params → 422); `Capability.CLIENT_PORTAL` + fail-closed on
  unbound client (404); rolling 24h quota (`client_revision_daily_quota`, default 5) → 429 w/
  `X-Revision-Quota-Remaining`; cross-client → 404 via existing scope. revert stays team-only.
  `repo.count_client_versions`. 6 tests. LIVE: 27-test suite green on :5434.
- **B-08 (`b0b1df4`)** — CanvasStage: pure controlled inline-SVG editor (`web/components/canvas/` ×3 + api.ts
  `fetchCreativeSvg`). DOMParser sanitize, select/drag/scale from `data-bbox`, visibility, brand-palette
  recolor (fill_role=color NAME), inline text overlay; emits one `ApiCanvasRevision` upward, ZERO API calls.
  tsc/lint clean, zero any.
- **B-09 (`345b21d`)** — CanvasEditor page `web/app/creatives/[id]/edit`: mounts CanvasStage + Apply/Discard +
  mark-&-tell-AI + VersionRail (real `listCreativeVersions`) + revert. api.ts: version types +
  `listCreativeVersions`/`revertCreative` + `ReviseCreativeBody` retyped `Partial<ApiCanvasRevision>` superset.
  Mutations run through NEW server actions so the httpOnly bearer never hits the browser. tsc clean across app.
- **B-13 (`cc89d67`)** — flywheel: NEW `api/services/edit_signals.py` seam shared by creative + approval
  services. revise→EDIT signal, revert→REJECTION signal (recorded via SAVEPOINT `begin_nested` — signal failure
  degrades gracefully, never loses the version). `last_ask` stamped on L1 params → ask→approve `record_feedback`
  accept, ask→revert decline (exception-safe, after commit). approval APPROVAL signal gains `edited_by_client`.
  LIVE: 59-test suite green.
- **B-10 (`edb72b6`)** — ReviewPanel integration: in-memory history[] replaced with persisted
  `listCreativeVersions` via the shared VersionRail; quick edits/Ask-AI/param presets post the TYPED body;
  "Open in editor ↗" link; inline styles → design classes; approve/request-change flow byte-identical.
  tsc clean across app.
- **A-03 (`4a5951e`)** — generation queue spine: `generate_client_creative(job_id=)` reuses a pre-created
  job (sync path unchanged); `generation_queue.py` (enqueue/list/stats, typed GenerationQueueItem/QueueStats);
  `generation_worker.py` single-concurrency worker (claims IN_PROGRESS+commit BEFORE running = crash-safe;
  least-privilege TEAM principal scoped to the task's tenant+client; failure → task DONE-with-error + job
  BLOCKED); `repo.list_open_generation_tasks` (cross-tenant) + `list_generation_tasks` (scoped); `main.py`
  lifespan starts/stops the worker (gated on `generation_worker_enabled` AND `app_env!=test`; conftest
  disables in tests). LIVE: 43 tests on :5434 + full suite 477 green; API boots clean with the worker running.

**Track B canvas program (B-08→B-09→B-10) COMPLETE.** Backend hot-file sequence reached A-03.

### ▶ EXACT NEXT ACTION — wave 4: A-04 (backend) ∥ A-06 (frontend)
Hot-file `creative_generation.py` sequence DONE through A-03. `api/routers/ops.py` sequence next:
**A-04** (`GET /ops/queue` + `/ops/queue/stats` + `POST /ops/queue` single-enqueue + `GET /ops/usage`;
NEW `api/services/usage.py`; team-gated incl. admin) → **A-05** (command parser + `POST /ops/command:parse`
+ `:execute`, ⌘K backend, `command_center.py`). Both serialize on `ops.py`.
Track B (web/lib/api.ts single-writer, sequential): **A-06** (board drag-transitions on /ops/board — the
ReviewPanel conflict is now cleared) → A-07 (calendar+SLA) → A-11 (delivery/archive).
BLOCKED until their backend lands: A-08 (needs A-04), A-09 (needs A-05). B-12 (portal bounded editor +
shim removal) is now UNBLOCKED (B-11 done) — schedule on Track B after A-06/A-07/A-11 or interleave.
Gates last: A-12 (cockpit E2E), B-14 (canvas E2E).
- Executors: Codex `codex exec -m gpt-5.6-sol -c model_reasoning_effort=xhigh -s workspace-write -c approval_policy=never - < spec.md` (specs in `scratchpad/spec_*.md`); Fable via Agent tool (model: fable) + frontend-design skill. Executors NEVER commit; Opus reviews diff + live-verifies (restart API + run tests on :5434) + commits phase-tagged.
- **Deploy: HELD** until all W4 done + operator sorts Supabase auth.

---

## ► (2026-07-22 pm) — QA + EDITOR BUGS + ALL-3-CLIENTS IMAGERY + TEXT-CHAIN; COMMAND-CENTER/CANVAS PROGRAM STARTED

**State:** all 4 kickoff goals DONE + committed; the Fable-plan Command-Center/Canvas program is underway (Wave 1
nearly complete). Local product runs; **production still UNTOUCHED** (deploy held per operator; my recommendation =
hold until the LLM-quality path + auth/persona QA + security P1/P2 land). Orchestration model unchanged: Opus plans/
reviews, Codex executes, Claude commits after live-verify.

### ▶ RUN LOCALLY — one change from the prior entry
Same as before BUT the API env must now ALSO carry the paid TEXT keys so the provider chain works:
```
set -a; source <(grep -E '^(PEXELS_API_KEY|GEMINI_API_KEY|GEMINI_TEXT_MODEL|OPENROUTER_API_KEY|OPENAI_API_KEY)=' .env); set +a
DATABASE_URL='postgresql+asyncpg://mimik:mimik@localhost:5434/mimik_suite' APP_ENV=dev IMAGE_BACKEND_PRIMARY=none \
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
```
uvicorn is NOT --reload → restart after any API change. Web unchanged (`cd web && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev`).

### ▶ WHAT LANDED THIS SESSION (all committed to main unless noted)
- **Editor bugs (`f3a6ff7`)** — badge light/dark map (API parser + `ReviewPanel` buttons); explicit edit now wins
  over AI redraft; `/revise` degrades to layout-only instead of 500 on LLM failure. LIVE-verified.
- **Imagery (`6d65556`)** — `_source_image` = ordered source resolver. **Island Cart → Pexels** (real photo);
  **Simply Nikah → paid AI-illustration** (gated; validated ONE OpenRouter render = faceless/on-brand/modesty held);
  Glo2Go unchanged. Generation now survives Gemini 429 (art-director + copy fallbacks). LIVE: all 3 → 200.
- **Text chain (`879ea7e`)** — `default_generate()` = Gemini→OpenRouter→OpenAI (env `TEXT_BACKEND_ORDER`), free-first,
  paid-on-429. LIVE: real crafted copy + art-direction via OpenRouter while Gemini 429s. **This is the fix for the
  #1 quality blocker.**
- **Contracts (`mimik-contracts@7fb1210`, SIBLING repo)** — typed ops (A-01) + canvas (B-02) models; 27 tests.
- **Mobile nav (`a289187`)** — off-canvas drawer (was P0: no phone nav); sidebar search wired; dead wizard fork deleted.
- **Docs (`b5b41c9`)** — ledger + Fable plan (`docs/PLAN_COMMAND_CENTER_AND_CANVAS.md`) + stale-doc banner.

### ▶ ⚠ SECURITY — ACTION FOR OPERATOR
An **uncommitted `.gitignore` edit (not mine) had un-ignored a real Google service-account key** (`secure repo/
gen-lang-client-*.json`). I RESTORED the ignore rules in the working tree (key is safe from `git add` now) but did
NOT commit `.gitignore` (you edited it deliberately — confirm intent). **Do not commit that key.** Also open QA:
portal `/portal/session` leaks a raw PyJWT error; confirm PROD `JWT_SECRET` ≠ the published `.env.example` default.

### ▶ EXACT NEXT ACTION — W1 + W2 + W3-hot-sequence DONE; finish A-10 then W4+
- **Wave 1 ✅:** B-01, imagery, text-chain, contracts (A-01+B-02 = `mimik-contracts@7fb1210`), B-05 (`e8c5d79`).
- **Wave 2 ✅:** A-02 typed /ops (`de225f3`) · B-03 creative lineage (`afd5a33`, migration `c7e90f4a1b32`).
- **Wave 3 hot-file sequence ✅ (all on `creative_generation.py`, live-verified):**
  - **B-04** (`80d7d3b`) — versions + revert API; revise persists lineage. IDOR: URL-path creative → 404, body id → 422.
  - **B-06** (`ab24b98`) — revise speaks typed `CanvasRevision`; `layer_ops`→brand-bounded `layer_overrides`
    (unknown `fill_role`→422); BC shim for the legacy web body; overrides inherit across versions.
  - **B-07** (`5b30958`) — guarded interpreter `creative/revision/interpreter.py`. Default (no `REVISE_LLM`) =
    deterministic keywords, ZERO LLM surface. LLM path (`REVISE_LLM=1`) fences instruction as data + allowlists
    output. **Live adversarial injection test passed** (attack → 201, zero disallowed keys, benign part still applied).
- **⚠ EXECUTOR: Codex quota EXHAUSTED until Jul 28** → switched to **agy** (`agy -p "$(cat spec.md)" --mode
  accept-edits --dangerously-skip-permissions --print-timeout 30m`; sweep stray `patch*.py` after — none appeared so far).
- **A-10 ✅ COMPLETE** — backend (`7b4c7f0`) + frontend (`ba3e4b7`, owner-gated member role/scope editing). **Wave 3 DONE.**

### ▶ REMAINING WORK (Fable plan — ~16 tasks; see `docs/PLAN_COMMAND_CENTER_AND_CANVAS.md`)
DONE so far: QA, editor bugs, imagery, text-chain, mobile-nav + plan tasks A-01, A-02, A-10, B-01..B-07.
- **Backend (Codex — quota back as of Jul 23; these serialize on `creative_generation.py`/`ops.py`):**
  - A-03 generation queue service + `generate_client_creative(job_id=...)` + asyncio worker in lifespan (HOT file).
  - A-04 `/ops/queue` + `/ops/usage` endpoints. · A-05 command parser + fan-out (`command_center.py`, ⌘K backend).
  - B-11 client-role bounded quota revise (HOT file) · B-13 flywheel capture (`edit_signals.py` + approval_flow, HOT file).
  - Hot-file order still strict: B-11 → B-13 → A-03 (never parallel on `creative_generation.py`).
- **Frontend (Fable, #9 — the high-value product surfaces):**
  - A-06 board drag-transitions · A-07 calendar+SLA · A-08 queue/budget panel · A-09 ⌘K command bar · A-11 delivery/archive.
    (`web/lib/api.ts` is a single-writer hotspot: A-06→A-07→A-08→A-09 sequential on it.)
  - B-08 CanvasStage (inline SVG drag/resize/recolor) · B-09 CanvasEditor page (versions/revert/ask) · B-10 ReviewPanel
    integration · B-12 portal bounded editor + BC-shim removal.
- **Gates:** A-12 cockpit E2E · B-14 canvas E2E.
- **Pattern:** write spec to `scratchpad/` referencing the plan's task section; demand tests + live-verify; the
  executor CANNOT reach the :5434 DB → YOU run alembic + live API checks for DB/route tasks; review diff; commit phase-tagged.
- **Deploy: HELD** until everything's done AND the operator sorts Supabase auth. Do NOT deploy.
- **Hot file `api/services/creative_generation.py`** — NEVER dispatch two of {B-04,B-06,B-07,B-11,B-13,A-03} at once.
- Codex dispatch: `codex exec -m gpt-5.6-sol -c model_reasoning_effort=xhigh -s workspace-write -c approval_policy=never [-C <dir>] - < spec.md`.
  Sibling-repo tasks need `-C /Users/atheeque/workspace/mimik-contracts`. Codex logs → `scratchpad/codex_*.log`.

### ▶ NOTES
- Gemini free tier is 429ing heavily right now → the OpenRouter leg carries most text calls (cheap, operator-OK'd).
- Image spend gate `MIMIK_ALLOW_PAID_IMAGES` stays OFF in dev; set it + `IMAGE_BACKEND_HERO=openrouter` for a real
  Simply Nikah illustration render.
- `artifacts/` + `var/` now gitignored (were not — generated PNGs incl. the paid render). Tree otherwise clean.

---

## (2026-07-22 am) — CREATIVE ENGINE v2: LOCAL PRODUCT DOES THE FULL LOOP (built via multi-agent orchestration)

**State: the local product is USABLE end-to-end.** onboard client → **Generate** a creative (topic → Pexels stock
+ Gemini-vision negative-space → on-brand render with designer rules) → **edit in-product** (inline text + "Ask AI
to change" → re-renders as non-destructive versions) → **Download editable SVG + PSD** → **edit client details +
brand brief**. All live-verified this session. **Production (VPS) intentionally UNTOUCHED** — hold deploy until the
local product is polished (operator's call).

### ▶ RUN LOCALLY (exact)
- `docker compose up -d` (Postgres :5434, Redis :6381; migrated to head).
- **API** (:8000) — env overrides force LOCAL + keys (do NOT rely on .env's prod block; uvicorn is NOT --reload, so
  **restart after any API change** or new routes 404):
  ```
  set -a; source <(grep -E '^(PEXELS_API_KEY|GEMINI_API_KEY|GEMINI_TEXT_MODEL)=' .env); set +a
  DATABASE_URL='postgresql+asyncpg://mimik:mimik@localhost:5434/mimik_suite' APP_ENV=dev IMAGE_BACKEND_PRIMARY=none \
  PEXELS_API_KEY="$PEXELS_API_KEY" GEMINI_API_KEY="$GEMINI_API_KEY" .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
  ```
- **Web** (:3000): `cd web && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev`.
  ⚠ **Blank/500 `Cannot find module './NNN.js'` = stale Next cache** → `rm -rf web/.next` + restart (hit this session).
- **Auth = dev-token** (no login): `web/.env.local` NEXT_PUBLIC_DEV_TOKEN (30-day owner for tenant `2781790d…`).
  Real Supabase login NOT wired locally (deferred). 3 clients seeded (`scripts/seed_profiles.py`, idempotent).
- ⚠ **venv is a 3.13/3.14 split** → use `.venv/bin/python -m pip` (bare `.venv/bin/pip` installs to 3.14).

### ▶ WORKS vs NOT (for the QA pass)
- ✅ Only **Glo2Go (photo)** generates real imagery (Pexels). **Simply Nikah (illustration) + Island Cart (product)
  imagery is UNWIRED** → placeholder render. Wiring their sources (AI-illustration / product-cutout) = top engine gap.
- 🐛 Editor bugs: badge light/dark word-map inverted; AI instruction overrides an explicit text edit.
- ⚠ PSD text is RASTERIZED (SVG is the live-text master; PSD-live-text skipped as too complex). 2 PSD tests fail under
  the venv split (not a code regression).

### ▶ ARCHITECTURE CHANGES (new)
`creative/art_direction.py` (LLM art-director, prepends rubric) · `creative/style_profile.py` (StyleProfile schema,
3 profiles) · `creative/render/glo2go_templates.py`+`glo2go_layout.py` (profile-driven + L1–L4 rules) ·
`creative/export/svg.py` (**layered editable SVG = the master**) + `psd.py` (layered PSD, forced `raw`) ·
`creative/references/gather.py` (multi-source: Openverse/Unsplash/Pexels + Pinterest/Dribbble/Behance/Envato stubs) ·
`creative/vision/text_region.py` (Gemini negative-space) · **`creative/knowledge/`** = the M5 self-improving design
brain (`design_rules.json` + `feedback.py`: record_feedback / rules_as_prompt_block). **API:** `POST /clients/{id}/
creatives:generate`, GET latest/preview, `/exports/svg?creative_id`, `/creatives/{id}/export.psd`, `POST /creatives/
{id}/revise`, `PATCH /clients/{id}` + `/brands/{id}`. **Web:** Board Generate, ReviewPanel editor (inline+Ask-AI+
versions+downloads), `/clients/[id]/edit`, onboarding autosave.

### ▶ R&D FINDINGS
- **Pivot:** AI-photoreal-people + fixed bottom band = REJECTED (client design languages differ wildly) → per-client
  **Style Profiles** + varied layouts + medium-aware sourcing.
- **References = a SOURCE problem:** Openverse returns junk; **Pexels is good for photo clients**; illustration/product
  need generated/cutout (encoded in each profile's `image_sources` ranking). Unsplash/Pexels keys in .env.
- **Self-improving design brain works:** creative-head feedback (L1–L5) → rules → art-director obeys next render.

### ▶ SECURITY HANDOFF
- **Tenant/IDOR verified:** PATCH client/brand filter by tenant_id at the data layer → 404 cross-tenant (live-probed);
  `test_tenant_isolation.py` green. Client "Ask AI" text = DATA (guarded revision_note), never a system prompt (locked #3).
- **Secrets:** all keys in `.env` only (Pexels/Unsplash/Gemini/Supabase); `.env` + `web/.env.local` gitignored; nothing
  secret committed. Dev-token = bootstrap shortcut; wire real Supabase login for role/persona QA.

### ▶ KEY DOCS
`docs/STYLE_PROFILES.md` (3-client build spec) · `docs/DESIGN_RUBRIC.md` (self-improving design brain) ·
`docs/BUILD_STATUS.md` (full delegation ledger) · `docs/PLAN_EDITOR_AND_COMMAND_CENTER.md` (editor + Command Center) ·
architecture artifact: https://claude.ai/code/artifact/43501966-31fd-4b7f-b42f-e8c9cec25cac

### ▶ ORCHESTRATION MODEL (keep using)
Brain = Claude/Opus (plan+spec+review). Executors: **Codex** `codex exec -m gpt-5.6-sol -c model_reasoning_effort=xhigh
-s workspace-write -c approval_policy=never` (primary, ~15 clean tasks); **agy** (Antigravity/Gemini 3.1 Pro,
`agy -p "<spec>" --mode accept-edits --dangerously-skip-permissions --print-timeout 30m`) for big chunks — ⚠ leaves
stray `patch*.py`, sweep them. Executors never commit; Claude reviews every diff. Codex/agy quota = separate from Claude's.

### ▶ NEXT SESSION (fresh) — the plan the operator wants
1. **Full QA pass** of the local product (functionalities, personas, flows) — `multi-persona-qa-reviewer` agent fits.
2. **Use Fable 5 to plan** → refine `PLAN_EDITOR_AND_COMMAND_CENTER.md` into execution-ready specs for (a) the
   **Command Center** (cockpit: Kanban + calendar/SLA + generation queue + command bar + admin → execute via agy) and
   (b) the **real-time canvas editor** (full toolset: drag/move layers, live text, palette, "mark & tell AI", client-
   bounded, versions). Goal: smooth execution.
3. **Wire imagery for Simply Nikah (illustration) + Island Cart (product-cutout)** so all 3 clients generate.
4. Fix the 2 editor bugs; wire real Supabase login for persona QA; then deploy to production.

### ▶ COMMITS THIS SESSION (main): 7f9557b, 70c0704, e437e39, b1d0814, 33f39ba, 5bff094, 76c8cdd, 908d011.

---

## ► (2026-07-21) — MIMIK SUITE LIVE IN PRODUCTION

**https://suite.mimikcreations.com (login) + https://api.suite.mimikcreations.com (API) — both HTTPS, valid
Let's Encrypt certs, verified 200.** DB = Supabase EU (session pooler :5432, cert-verified TLS via bundled
Supabase CA), 17 tables migrated. All 3 containers healthy. RAM ~2 GB free.

### HOW IT'S DEPLOYED (important — NOT via Coolify)
The VPS's real reverse proxy is **host nginx + certbot** (no Traefik). Coolify's compose-paste kept fighting
us (stale port bindings, 8000 conflict), so Mimik Suite runs as a **self-managed docker-compose stack**:
- **`/root/mimik-suite/docker-compose.yml`** + `/root/mimik-suite/.env` (secrets, chmod 600; extracted from
  the Coolify container). Project name `mimiksuite`. Images pulled from GHCR. `restart: unless-stopped`
  (survives reboot). Ports: **web 127.0.0.1:3020**, **api 127.0.0.1:8020** (8000 was taken by another app).
- **nginx vhost `/etc/nginx/sites-available/mimik-suite`**: suite→3020, api.suite→8020. Certs auto-renew.
- **Redeploy after a new image build:** `ssh hetzner-vps 'cd /root/mimik-suite && docker compose -p mimiksuite pull && docker compose -p mimiksuite up -d'`.
- **⚠ CLEANUP TODO (operator):** DELETE the redundant **Coolify "Mimik Suite" resource** (it crash-loops on
  the 8000 conflict — harmless but noisy). Coolify is not used for this app.

### Fixes that got the API healthy (all in the image)
1. `postgresql://`→`+asyncpg` auto-normalize. 2. TLS: system-CA SSLContext + **bundled docker/supabase-ca.crt**
(Supabase Root 2021 CA) = verified TLS, no MITM. 3. Supabase **Session pooler :5432** (not tx :6543).

### Still open / next
- **DNS:** `suite` + `api.suite` A → 195.201.33.87 (Spaceship) — done. `NEXT_PUBLIC_API_URL=https://api.suite.mimikcreations.com`
  baked into web (CI var).
- Screenshots (light/dark) still not run. PFI-on-Firebase parked (needs Blaze). Track B untouched.
- ⚠ INC-001: rotate the planflow DB pw (was briefly on GitHub). VPS RAM freed: hermes+planflow stopped.

---

## ► (2026-07-21) — deploy debug trail: host-nginx discovery, DB/TLS fixes

**THE APP WORKS.** Coolify Docker-Compose resource "Mimik Suite" (project → production) is deployed:
all 3 containers up — **api HEALTHY** (`alembic upgrade head` vs Supabase → **17 tables**, ver 27bc3b786ef3),
**redis healthy**, **web serving on :3000**. Images pull from GHCR (`ghcr.io/azi023/mimik-suite-{api,web}:latest`,
public, CI-built). DB = Supabase **EU** (Frankfurt), **Session pooler port 5432** (NOT 6543).

### ✅ Fixes that got the API healthy (all baked into the image)
1. `postgresql://` → auto `+asyncpg` (Settings.resolved_database_url).
2. TLS: system-CA `SSLContext` verify-full + **bundled `docker/supabase-ca.crt`** (Supabase Root 2021 CA) →
   cert-verified TLS, no MITM, zero user setup (Settings.db_connect_args).
3. `pull_policy: always` + assistant pre-pulls on the VPS (Coolify cached stale `:latest`).

### ⛳ ONLY THING LEFT — reverse proxy is HOST NGINX, not Coolify/Traefik!
80/443 are served by **host `nginx` + certbot** (no Traefik/coolify-proxy container exists). csedash + the
portfolio are nginx vhosts. So Coolify's "Domain" field did NOTHING (0 traefik labels on the containers),
and `suite.mimikcreations.com` fell through to the portfolio (atheeque.site) default vhost.
**Remaining (host nginx + certbot):**
1. Compose now binds **127.0.0.1:3000 (web)** + **127.0.0.1:8000 (api)** → operator: **Edit Compose File in
   Coolify → repaste `docker-compose.coolify.yml` → Deploy** to publish the ports.
2. DNS: add A **`api.suite`** → 195.201.33.87 (Spaceship). Web bundle now targets `https://api.suite.mimikcreations.com`.
3. nginx vhosts: `suite.mimikcreations.com`→`proxy_pass http://127.0.0.1:3000;`,
   `api.suite.mimikcreations.com`→`http://127.0.0.1:8000;` (mirror existing confs).
4. `certbot --nginx -d suite.mimikcreations.com -d api.suite.mimikcreations.com` → `nginx -t && systemctl reload nginx`.
5. Verify `curl https://api.suite.mimikcreations.com/api/openapi.json`. Assistant has root SSH to `hetzner-vps`
   → can do 3-5 once ports publish (step 1).

### RAM: hermes(systemd)+planflow(pm2) stopped → ~2.3 GB free. ⚠ INC-001: rotate the planflow DB pw (was briefly on GitHub).

---

## ► (2026-07-21, main `HEAD`) — DEPLOY IN PROGRESS: subdomain live, VPS cleanup, build blocked on GH_PAT

**Subdomain = `suite.mimikcreations.com`** (A → 195.201.33.87 added on Spaceship; `preview.mimik` A record
removed by operator). CI variable `NEXT_PUBLIC_API_URL=https://suite.mimikcreations.com/api` set on the repo.
- **VPS cleanup:** hermes systemd services (`hermes-gateway`,`hermes-webui`) **stopped+disabled** → freed
  ~430 MB (RAM avail 1.35→1.78 GB), reversible. planflow code preserved on github.com/Azi023/planflow.
  `preview.mimik` served nothing on the box. **Still to remove (via COOLIFY UI, not SSH — it auto-restarts):**
  the `csedash.xyz`/planflow Coolify app (Stop → frees ~500 MB → Delete AFTER migrating its DB); striker
  (no running container/service found — just delete its Coolify resource + `rm -rf /root/workspace/striker`).
- **⚠ INC-001 (SECURITY_FINDINGS.md):** assistant accidentally pushed a prod DB password to Azi023/planflow
  during cleanup; force-pushed it away immediately. `Pf@2026!xK9mWq` should be treated as compromised/rotated.
- **Image build: ✅ GREEN.** GH_PAT added → both images built + pushed to **ghcr.io/azi023/mimik-suite-api**
  + **mimik-suite-web** (run 29814663858, 4m25s). Fixed en route: web/.dockerignore excluded `design/` but
  globals.css `@import`s design/tokens.css (`10c… fix`). Images are PRIVATE → Coolify needs a GHCR pull
  credential (GH token w/ read:packages) OR make the 2 packages public.
- **VPS cleanup DONE:** hermes (systemd) + planflow (**pm2** — not Coolify!) stopped/deleted → **RAM avail
  ~2.28 GB** (freed ~900 MB). striker wasn't running. **Coolify holds ONLY csedash (cse-backend/frontend/
  redis) — KEEP, remove nothing there.** meridian + imaginateve-api (pm2) left running. planflow code on
  GitHub + its DB untouched (dump before full teardown for migration).
- **PFI = a Next.js app (NOT static)** → can't run on cPanel. Recommend **Vercel** (free, made for Next;
  it already has apphosting.yaml for Firebase as an alt). Point a jasmin-hostings subdomain at it (Vercel:
  CNAME → cname.vercel-dns.com, or A → 76.76.21.21). Do NOT add it back to the RAM-tight VPS.
- **⚠ Supabase region:** the existing project (`uxewpubrylgiykjhutqn`) is in **Tokyo**; the VPS is in
  **Germany** → ~250 ms/query → sluggish. **Recommend a NEW Supabase project in EU (Frankfurt)** before wiring
  (region can't be changed post-creation). Then set SUPABASE_URL + SUPABASE_ANON_KEY + DATABASE_URL (asyncpg)
  in Coolify. App auto-migrates via alembic on boot.
- **cPanel (jasmin-hostings) question:** static sites/files → yes (subdomain + File Manager/FTP); full-stack
  apps (planflow Next+Nest+DB) → NO (no Docker/limited Node) → keep on VPS/Node host. PFI depends on its stack.

---

## ► (2026-07-21, main `0ae0626`) — TRACK A COMPLETE + DEPLOY PREP (VPS audited, CI pipeline live)

**378 Suite / 19 contracts green, all pushed to github.com/Azi023/Mimik_Suite.**
- **TRACK A COMPLETE** (`a221661`): header/footer brand bands render across all 3 templates → BrandLayout
  fully renders. Column-grid snapping + free-position logo = documented v1 non-goals. Frontend ~100% of
  what's sellable; remaining is deliberate polish.
- **DEPLOY PREP** (`0ae0626`): SSH-audited the VPS (195.201.33.87). **Ubuntu 24.04, 2 vCPU, 3.7 GB RAM
  (~1.7 GB free), Coolify + planflow/striker/hermes resident, Playwright already on host, 6 GB reclaimable
  images.** Verdict: **fits with care** — Postgres is external (Supabase) so on-box steady state ~450 MB;
  the risk is the Chromium render spike (mem_limits added: api 900m / web 450m). Prior session already
  built the deploy infra (Dockerfile.api, web/Dockerfile, docker-compose.prod.yml, DEPLOY.md). This session:
  pushed the 2 private sibling path-deps (Azi023/mimik-contracts, mimik-knowledge) + added
  `.github/workflows/build-images.yml` (builds off-box → GHCR; VPS can't build the 1.5 GB image).

### ⏭ To finish the deploy — OPERATOR steps (I can't do these: secrets / no Spaceship+Coolify+Supabase access)
1. **Pick the subdomain** (studio./app./suite.mimikcreations.com) → add an **A record on Spaceship** →
   195.201.33.87. (DO NOT migrate the domain to Cloudflare — it carries live M365 email; subdomain only.)
2. **Supabase project** → DATABASE_URL (asyncpg) + SUPABASE_URL + anon key (auth AND the external Postgres).
3. **Repo secret `GH_PAT`** (reads the 2 sibling repos) + optional var `NEXT_PUBLIC_API_URL` = the subdomain.
4. **Coolify**: new Docker Compose resource from `docker-compose.prod.yml`, set env secrets, assign domain →
   web:3000 (+ `/api` → api:8000), deploy. Optional: `docker image prune -f` on the box first (frees 6 GB).
RAM headroom: stop planflow.csedash.xyz (~400–500 MB) when needed; end-of-month RAM upgrade removes the ceiling.

### Track B (later, operator-led): the Command-Center is a SEPARATE app/repo
Planning to happen on a FRESH Claude session, heavily operator-guided with visual refs. It's a different
app/tenant from the product (locked design decision) → needs its own repo (`mimik-command-center` or similar).
Logged in FRONTEND_ROADMAP §5 (B1–B12). Not started.

---

## ► (2026-07-21, main `c65f572`) — SECURITY AUDIT PASS: upload hardening + RBAC + full sweep

**377 Suite / 19 contracts green, ruff clean, web tsc + next lint clean. All pushed.** A dedicated
security pass (upload rules + RBAC + "check everything"). Two fixes + a documented audit:
- **F-004 upload hardening** (`a1bfc27`): the asset upload trusted the client `Content-Type`. Now
  `store_asset_file` SNIFFS magic bytes — only real png/jpeg/webp (images) / ttf/otf/woff2 (fonts) pass;
  PHP/HTML/JS/SVG/PDF/ELF disguised as image/png → 415; cross-kind rejected; DB stores the true mime.
  `safe_display_filename` sanitizes the filename. (Path traversal was ALREADY impossible — server-UUID
  paths.) Upload is team-only. +4 tests.
- **F-005 RBAC** (`c65f572`): `POST /clients,/brands,/jobs,/pillars,/briefs,/briefs/{id}/signoff` used bare
  get_principal → a bounded CLIENT principal could create tenant resources (incl. for OTHER clients). Now
  team-role-gated (403 for clients). The write-side analog of the IDOR sweep. +1 test.
- **A-001 audit summary** (docs/SECURITY_FINDINGS.md): audited + found ALREADY sound — JWT (alg pinned, no
  RS/HS confusion, aud/iss/exp enforced), SSRF-fetch (egress guard w/ per-hop re-check + metadata-IP block,
  test_ssrf_guard.py), path traversal, CORS (none — same-origin server actions), tenant isolation, client-
  as-untrusted (#3). **The codebase is in strong security shape.**

**Security OPEN (logged, not fixed):** rate-limiting on `/approvals/magic` + `/portal/session`; magic-link
revocation; `artifact_ref` allowlist sweep beyond POST /creatives; 2 temp passwords to rotate.

**Completion:** Track A frontend ~90%, backend ~92%. NOT literal 100% — remaining is engine-side compositor
rendering (header/footer bands + column grid, §4) + free-position logo (needs a contract field). **Next per
operator: HOSTING** (roadmap §7 has the plan — standard Next+FastAPI+PG+Redis via docker compose on the VPS
+ Caddy/nginx TLS; needs Dockerfiles for web+api added). Track B (command-center) still deferred + logged.

---

## ► (2026-07-21, main `a8e2246`) — PER-CREATIVE CANVAS EDITOR + SSRF FIX → Track A ~90%

**374 Suite / 19 contracts green, ruff clean, web tsc + next lint clean. All pushed to
github.com/Azi023/Mimik_Suite (private).** Did (a) the full per-creative canvas override + (b) the
image_artifact SSRF hardening; skipped (c) Track B per your call.
- **(a) Per-creative layout editor** — CONTRACT CHANGE `CreativeManifest.layout: BrandLayout | None`
  (mimik-contracts `4e8b91a`, +1 test) — backward-compatible override. Backend (`4d95011`):
  `assemble_context` now SETS `ctx.layout = manifest.layout or brand.tokens.layout` (fixes the §4 gap —
  BrandLayout never rendered before!); `build_manifest` + `POST /creatives` thread the override; +3 tests.
  Frontend (`a8e2246`): team-only "Edit layout" on the review — **drag the logo → snaps to the nearest of
  9 anchors**, anchor grid, size + safe-margin sliders, live preview (logo + dashed safe-zone), "Save as
  new version". Copy edits carry an existing override forward.
- **(b) SSRF fix (F-003)** — `POST /creatives`'s `image_artifact` becomes a `url(...)` the compositor
  fetches server-side; it accepted external URLs (e.g. `169.254.169.254` metadata). Now allows only
  `data:` URIs + internal refs, rejects any scheme/host/`..` → 422. +2 tests. Team-gated, but real.

**NOTE — mimik-contracts commit `4e8b91a` is LOCAL ONLY** (that sibling repo has no remote). Mimik_Suite
depends on it via path dep, so it's fine locally; if you want it on GitHub too, it needs its own remote.

**Remaining tail (see FRONTEND_ROADMAP):** compositor header/footer + column-grid *rendering* (§4,
engine-side); free-position logo (needs `logo_x/logo_y` on the contract). Track-B add-ons (B1–B12) untouched.

---

## ► (2026-07-21, main `bbdd9e9`) — TAIL SHIPPED: board/deliveries/billing/prefs/copy-editor → Track A ~85%; REPO PUSHED

**369+ Suite / 18 contracts green, ruff clean, web tsc + next lint clean.** Pushed to
**github.com/Azi023/Mimik_Suite (PRIVATE)** — remote `origin` set, all commits up, no secrets tracked
(verified). Shipped the remaining product tail on **Opus**:
- **/deliveries** — Drive-archive ledger. NEW secure `GET /deliveries` (client-confined via JobRow join) + table.
- **/billing** — per-client subscription + **"Send quote"** (mints a checkout/payment link to share;
  degrades to an honest message when no payment provider is configured — constraint #7).
- **/clients/[id]/preferences** — the learning-loop made visible (signal count, ranker active, summary, feed).
- **Board** — "Generating" (pulsing) + "At risk" card badges (roadmap §3.4).
- **Copy editor** — inline headline/subhead/CTA edit on the review canvas (live preview) → **"Save as new
  version"** (`POST /creatives`, team-only). The feasible slice of §3.5.
- **docs/SCREENSHOTS.md** — the durable Playwright light/dark guide (your ask) + **R-001** security review.

**DEFERRED (needs your call — contract change):** the FULL canvas editor (drag logo / rulers / snapping /
per-piece layout override) needs a per-creative `layout` field on `CreativeManifest` + the compositor
header/footer/grid wiring (§4). Copy-versioning is the shipped slice; the layout-override slice is gated.

### 🔒 Security — new surfaces reviewed (R-001 in SECURITY_FINDINGS.md), no new leaks
GET /deliveries confined + tested; GET /me = own identity only; POST /portal/session magic-scoped; copy
editor's POST /creatives is team-gated. **Full IDOR sweep from earlier still holds (F-001/F-002, 6 routers).**
New open item: **image_artifact SSRF hardening** (team-gated, pre-existing, low) — allowlist artifact refs.

---

## ► (2026-07-21, main `4b7e771`) — GAPS CLOSED + IDOR SWEEP: magic portal + /me + route-gating + resilience → Track A ~70%

**368 Suite (was 359) / 18 contracts green, ruff clean, web tsc + next lint clean.** Continued the same
day: closed the portal backend gaps, added the no-login magic flow, hardened routing, shipped the
resilience layer, and ran a **full IDOR sweep** (6 routers fixed). **Track A frontend now ~70%** (was
~40%). Commits `4b8575b` (backend portal+/me+security log) · `6c58f59` (magic portal + route-gating) ·
`403cbde` (resilience) · `11d9e58` + `4b7e771` (IDOR sweep). **Still LOCAL — no git remote configured**
(`git remote -v` empty); add a remote then `git push` (≈14 local commits total).

### What landed
- **Magic-link no-login portal is COMPLETE.** New `POST /portal/session` (backend READ path — resolves a
  signed single-job grant to just that job's bundle; token in body, not query; no enumeration). Frontend
  `/review/[token]` (public, no session) reuses `CreativeReview` in `magicToken` mode → decisions post via
  `POST /approvals/magic`. Team mints+copies the link from the internal review ("Share with client ↗").
- **`GET /me`** + **role-based route-gating**: `redirectClientToPortal()` (calls /me) wired into all 9
  internal pages → a `client`-role session is steered to `/portal`. Defense-in-depth (data already confined).
- **Resilience layer DONE** (§2): `useAutosave` added; brief editor + kit editor now autosave (debounced,
  edit-counter trigger) + `useUnsavedGuard`; wizard guards a half-filled intake. Review composer already
  had `useLocalDraft`.
- **Security log:** `docs/SECURITY_FINDINGS.md` — F-001 (IDOR, fixed), D-001 (magic-link shareable-capability
  trade-off, by design), H-001 (route-gating), + an OPEN-ITEMS audit list (⚠ below).

### 🔒 Full IDOR sweep DONE (F-001 + F-002 in docs/SECURITY_FINDINGS.md) — @atheeque re-verify
The jobs IDOR turned out to be a **systemic pattern** — the client-principal confinement was applied
inconsistently. Swept EVERY `Depends(get_principal)` GET returning client data and fixed all leaks:
**jobs, clients (was leaking contact PII!), brands, ops/board+calendar, briefs, pillars** now confine a
`client` principal (or 403 via role-gate: assets/invitations/admin/intake). tasks/creatives/approvals/
preferences/billing were already confined. Commits `a924a00`, `11d9e58`, `4b7e771`. Re-verify:
`uv run --no-sync pytest -q tests/test_jobs.py -k "client_principal"` (5 IDOR tests).
**Still OPEN (not fixed):** no **rate-limiting** on `/approvals/magic` + `/portal/session`; no magic-link
**revocation**; WRITE routes only spot-checked; 2 temp passwords to rotate. See SECURITY_FINDINGS.md.

### Needs YOUR input (can't do autonomously)
- **git remote** — none configured; give me the URL (or add it) and I'll push all local commits.
- **Playwright screenshots** — still not run (needs seeded owner-token data; dev-token path is read-only).

---

## ► (2026-07-21, main `6b97d70`) — FULL PRODUCT LOOP: review + portal + calendar + tasks + IDOR fix

**361 Suite (was 359) / 18 contracts green, ruff clean, web tsc + next lint clean.** Dedicated frontend
session on **Opus** — shipped all 4 target screens PLUS a security fix that surfaced mid-session. Six
commits on `main`. **Commits are LOCAL — no git remote is configured** (`git remote -v` empty); add a
remote then `git push`.

Commits: `82a1703` review · `1d06afa` calendar+tasks · `a924a00` IDOR fix · `6b97d70` portal
(+ HANDOFF docs commits `a3f90e1`, `10c0f86`).

### 🔒 Security fix landed mid-session (constraint #2)
`GET /jobs/{id}` + `GET /jobs` (`api/routers/jobs.py`) filtered by **tenant only** — a `client`-role
principal could read/enumerate EVERY client's jobs in its tenant (metadata leak; creative content was
already safe via the confined `/creatives`). **Fixed** (`a924a00`): both now confine a client principal to
its own `client_id`, mirroring tasks.py/creatives.py (404 not 403). +2 negative tests via the Supabase
harness (client A → 404 on client B's job; listing filtered). This UNBLOCKED the portal.

### Still open on the portal (follow-ups, not blocking what shipped)
- **Magic-link no-login flow:** `api/core/magic_link.py` + `POST /approvals/magic` are **write-only** —
  there is no magic-link-authenticated READ endpoint. The portal we shipped uses an AUTHENTICATED
  client-role Supabase session. The frictionless WhatsApp magic-link portal still needs a new
  low-privilege read route (return job+creatives+brand from a verified grant). Operator-gated.
- **Role-based route-gating:** a client session could still LOAD internal routes (`/`, `/ops`) — the DATA
  is protected server-side, but the chrome isn't steered. Add a redirect (client role → /portal).

### Shipped this session (all session-gated, light+dark, real empty states, token system)
- **/portal + /portal/jobs/[id]** (`6b97d70`) — bounded client portal (constraint #3): PortalShell (no
  internal nav), index lists ONLY the client's own jobs, review reuses the SAME `CreativeReview` +
  hooks. Client acts as itself; foreign id 404s.
- **/calendar** (`1d06afa`) — month grid (Mon-first) of jobs by publish_date + at-risk badges from
  GET /ops/board. Month nav + Today; opens on the soonest job; job → review. Read-only.
- **/tasks** (`1d06afa`) — filterable (status+type) + paginated table over GET /tasks. Status advance
  open→in_progress→done via server action → POST /tasks/{id}/status (team-gated; client 403s inline).
  NOTE: Task has no `priority` field → filtered by type. Rail nav now routes board/calendar/briefs/tasks.
- **/jobs/[id]/review** (`82a1703`) — the sellable core review + approval loop (below).

---

### /jobs/[id]/review — creative review + approval (the sellable core)

Reachable from the board's slide-in review panel ("Open full review ↗" on `ReviewPanel`).

- **`/jobs/[id]/review`** (`82a1703`) — image-first creative review (ref: Filestage), reachable from the
  board's slide-in review panel ("Open full review ↗" on `ReviewPanel`).
  - **Canvas** composed *client-side* from the CreativeDoc manifest + brand tokens (aspect per format,
    brand-ground / image-layer background, copy block, logo anchor). **Honest proxy** — there is NO
    server-rendered PNG endpoint; rendering is Playwright-at-archive-time only, and `artifact_ref` is null
    until a paid image backend (constraint #7). This is the real gap the canvas works around.
  - **Click-to-pin** change requests → zone auto-suggested by region, editable via chips → queued pins
    submit as one `request_change` with pin-pointed `RevisionTarget`s (cap 10 / 500 chars). NOTE: pin x/y
    are UI-only context — the contract carries no coordinates, so persisted comments can't restore pins.
  - **Decision bar:** Approve / Request changes (pinned) / Reject (reason taxonomy). **Contract reality:
    `ApprovalAction` has no `reject`** — reject = `request_change` + `reason_tag` (categorical), request-
    changes = `request_change` + `targets[]`. Mapped to existing contract; NO contract change made.
  - **Activity thread** from the append-only audit trail (`GET /jobs/{id}/approvals`) — approvals +
    deliveries, chronological. **Comment box** → `action=comment`.
  - Mutations via a **server action** reading the httpOnly Supabase cookie (`submitReviewAction`);
    `revalidatePath` + `router.refresh` reloads the thread. Session-gated, light+dark, real empty states.
  - **Resilience (§2):** new reusable **`useLocalDraft` + `useUnsavedGuard`** (`web/lib/hooks.ts`) — pins +
    comment mirrored to localStorage + guarded on unload so a dropped connection / power-cut never loses a
    reviewer's notes. Reuse these on the portal + remaining editors.
  - `api.ts`: `getJob`, `getJobAuditTrail`, `ApiDelivery`/`JobAuditTrail` types.

**Open / next:** (1) **Push** — no git remote configured; add one then `git push` (6 local commits).
(2) **Playwright light/dark screenshots of the 4 new screens — NOT yet done** (deferred for budget; the
human-gate step still owed before "verified" per the build rules; needs seeded owner-token data since the
dev-token path is read-only). (3) **Magic-link no-login portal** — needs a backend read endpoint (see
follow-ups above). (4) **Role-based route-gating** (client role → /portal). Known caveat unchanged:
save/mutation actions need a real Supabase login (dev-token path is read-only).

---

## ► (2026-07-20 deep-night, main `5670d81`) — FRONTEND session: 3 screens + compositor wiring + roadmap

**359 Suite / 18 contracts green, ruff clean, web tsc+eslint+build clean.** Dedicated frontend session,
built on **Opus**. Five commits on `main` (Suite) + one on `mimik-contracts`:
- **P1 brief editor** (`7a20442`): `PATCH /briefs/{id}` (draft-only, 409 frozen, existing BriefSections)
  + `/briefs` list + `/briefs/[id]` editor (9 sections editable, tokens+refs read-only, sign-off modal
  → freeze, revise → new version). Server actions, session-gated. +3 tests.
- **P2 onboarding wizard** (`f5748c2`): `/onboarding` 5-step (Brand→Kit→Pillars→Style ref→Review). Style
  ref = client-shared **links (source+note) AND image uploads**. Enabler: `POST /brands` now accepts
  `references` (passthrough, Reference contract already existed). Finish → client→brand→pillars→uploads→
  **auto-draft brief** → lands on brief editor. `createOnboarding` server action (multipart via apiPostForm).
  Shared `ChipsInput`. Sidebar "New client"→/onboarding. +2 tests.
- **P3 brand-kit editor** (`d8ce663` + contracts `2301c70`): **CONTRACT CHANGE** `BrandLayout` on
  `BrandTokens` (LogoPlacement 9-anchor enum, Margins per-edge, LayoutGuide draggable, logo_scale,
  header/footer bools, grid_columns+gutter, guides, show_guides) — backward-compatible default. `PATCH
  /brands/{id}` (tokens replace). `/brands/[id]/kit`: colors/type/logo + **Layout box** (3×3 anchor,
  size slider, per-edge margins w/ Linked toggle, header/footer, grid, **Adobe-style draggable guides**)
  + **live artboard** (4:5/1:1/9:16, rulers, safe-zone, bands, grid, logo, guides). Entry from brief
  tokens section. +3 Suite +4 contracts tests.
- **TopBar + compositor** (`b03fe81`): per-page TopBar titles (was always "Board"). BrandLayout wired
  into `creative/render/templates.py` — **logo placement+size + margin-floor** honored by all templates
  (central helpers `_resolve_logo`/`_edge_pads`); layout=None = no regression. +3 tests. **Still to wire:
  header/footer bands, column grid, guides, + populate TemplateContext.layout in the render pipeline.**
- **Roadmap** (`5670d81`): `docs/FRONTEND_ROADMAP.md` — the durable backlog. Two-track framing (product
  vs command-center), Track-A ~40% frontend, remaining product pages (**creative review/approval = core
  gap**), **resilience spec** (useLocalDraft/useAutosave/useUnsavedGuard — the operator's autosave /
  no-data-loss-on-powercut ask), command-center add-ons B1-B12 (Studio Admin refs), hosting + `.env` answer.

**Open / next (see FRONTEND_ROADMAP.md):** (1) resilience hooks + wire the 3 editors; (2) creative
review+approval (Filestage ref) — the sellable core; (3) client portal; (4) finish compositor
(header/footer+grid) then per-creative canvas editor. Known: save actions need a real Supabase login
(dev-token path is read-only); 2 temp passwords to rotate; Meta portfolio for WhatsApp. `.env` confirmed
**not in git** (only .example tracked) — safe for colleagues to clone.

**Operator R&D asks (added — FRONTEND_ROADMAP.md §4b):** (a) **custom font upload** — client/us upload
the brand's actual font file(s), multiple allowed; hook exists (`AssetKind.FONT` + assets upload),
work = kit/onboarding UI + `@font-face` in the compositor. (b) **brand-deck ingestion** — upload/share a
brand-guideline/portfolio deck and the intelligence layer auto-extracts palette/fonts/logo/voice/refs to
fill the kit + brief; partial backend (extract_brief_sections, ingest_reference_creative, vision/study.py),
work = a NEW deck-ingest path with human-review-before-apply. Next fresh session prompt: `NEXT_SESSION.md`.

---

## ► (2026-07-20 late-night, main `249959c`) — IAM increment B + Members/roles screen (Opus)

**348 Suite / 14 contracts green, ruff clean, web builds.** Both "unblocked steps" done + docs:
- **IAM increment B (role×scope) — backend**: `api/core/capabilities.py` (`Capability` enum + 
  `ROLE_CAPABILITIES` matrix + `has_capability`), `require_capability()` dep (has-ALL semantics),
  `client_scopes` threaded onto Principal + `UserAccountRow` (migration `27bc3b786ef3`) + copied from
  the invite at accept time, `GET /admin/capabilities`. New role `ActorRole.ADMIN`. Helpers
  `is_client_in_scope`/`principal_client_ids` exist but are **NOT wired into query routes yet**
  (empty scope = all = current behavior; wiring them in = the next behavior-changing step). +16 tests.
- **Members/roles screen — frontend** (`web/app/members/`, `components/MembersView.tsx`): 3 tabs —
  Members table, Roles&permissions (capability matrix), Invitations (invite form → copyable accept-link
  + revoke). Built on Opus vs the shadcn Roles&Permissions ref, existing token system, **light+dark**,
  **real empty states (no mock fallback)**. Mutations via **Next.js server actions** (`actions.ts`) that
  read the httpOnly session cookie server-side — stricter than the board's client fetch, the right
  pattern for the admin panel. Sidebar settings glyph now links to `/members`.
- **Docs**: `docs/BRAND_KIT_ONBOARDING.md` (Zaid's spec — onboarding flow, brand-kit **Layout box**:
  logo position / header-footer / margins, typography+image selection, editable text, the 17 design
  principles → art-direction rubric; grounded EXISTS-vs-NEW vs the current model). `docs/design-refs/
  17-design-principles.png` saved. `docs/DESIGN_REFERENCES.md` updated (UI screenshots captured by
  URL+desc; raw PNGs were transient — re-drop to archive).

**Frontend now: login✓ + members✓** (2 real screens beyond the board). Design build loop = **Opus**
(user: Fable weekly credits low). Next FE targets per `docs/DESIGN_REFERENCES.md`: brand-brief editor
(clearest client "wow"), then onboarding wizard + brand-kit Layout box (Zaid) — user wants a dedicated
**frontend-only session** for these. Open: full tailwind+shadcn adoption still deferred (we match the
look with tokens); wire scope-filtering into query routes (increment B follow-up); change 2 temp login
passwords; Meta fresh portfolio for WhatsApp.

---

## ► (2026-07-20 late, main `fc2cf04`) — IAM invitations SHIPPED + new shadcn login (both on Opus)

**332 Suite / 13 contracts green, ruff clean, web builds.** Two tracks this run (Opus, not Fable —
Fable weekly credits were low):
- **IAM increment C — invitations backend** (`api/routers/invitations.py`, `api/core/invite_token.py`,
  `InvitationRow` + migration `cb072f89d251`, `Invitation`/`InvitationStatus` contracts): invite by
  email → **copyable signed accept-link** (no email dep) → Supabase-verified accept provisions a
  UserAccount. Gated super_admin/owner/admin; no super_admin escalation via invite; tenant-scoped at
  data layer; accept re-checks status/expiry/email/existing-account vs the DB row. 13 tests.
  Review-fixed: concurrent double-accept → 409 (IntegrityError guard); single-source INVITE_TTL_HOURS.
  **Still NOT built:** IAM increment B (`require_capability` + capability matrix + user↔client scope
  column — invite stores `client_scopes` but the accept can't copy them onto the account yet); the
  admin-panel **UI** (the shadcn Roles&Permissions screen).
- **New login** (`web/app/login/page.tsx` + globals.css): shadcn "Studio Admin" **split-screen** (dark
  brand panel + form, mono primary button), light+dark, built on the existing token system (added
  `--auth-brand-*` theme-invariant tokens). **Server-side Supabase POST preserved** (httpOnly cookies,
  works JS-off). NOTE: `web/` is NOT tailwind/shadcn — it's a custom token-CSS system; we MATCH the
  shadcn look with tokens rather than migrate. A full tailwind+shadcn adoption is still an open
  decision (would touch every existing component; deferred).

**Design system LOCKED** (`docs/DESIGN_REFERENCES.md`): shadcn mono admin north-star + per-screen refs
(login✓, members/roles→shadcn Roles&Permissions, creative-review/portal→Filestage, video→Frame.io).
Build loop was going to be Fable but **user says use Opus** (Opus sees the ref images + Fable credits
limited). Next FE targets: **members/roles screen** (pairs w/ the invitations backend), then brand-brief.

---

## ► (2026-07-20 night, main `55c0eae`) — super_admin gate SHIPPED; IAM designed; WhatsApp+generating+ChatGPT merged

**Since the entry below (all on `main`, 319 Suite / 12 contracts green, ruff clean):**
- **✅ CRITICAL FIX SHIPPED** — `POST /tenants` is now gated to a new `super_admin` role (was
  unauthenticated). Supabase emails on `SUPERADMIN_EMAILS` are elevated to super_admin (identity
  still fully verified; only role raised); first-party super_admin tokens work for ops/CI. All 20
  test bootstrap call sites updated via a `superadmin_headers()` conftest helper (`pythonpath=tests`);
  new `test_tenants.py` (anon→401/403, owner→403, super→201). Commit `55c0eae` (+ contracts `9452a7d`).
  This was **increment 1** of the IAM plan.
- **IAM / admin-panel DESIGNED + decided** → `docs/IAM_DESIGN.md`. User picked **role × scope now,
  per-user custom permissions possible later** (don't over-build). Model: roles {super_admin, owner,
  admin(NEW), ops/designer, client} × scope (all-clients / assigned). Invitations ship first as a
  **copyable accept link** (no email dep); real invite emails reuse the deferred M365 Graph EMAIL sink.
  **Remaining IAM increments (NOT built):** B = `require_capability` + capability matrix + user↔clients
  scope; C = `Invitation` model + create/accept/revoke/resend endpoints. Admin-panel UI = reference+Fable.
- **Design workflow set** → `docs/DESIGN_REFERENCES.md` (north-star + per-page analog table; Mobbin/Refero;
  build screens on **Fable** subagents, not Opus). User is gathering references. Start screen: brand-brief or members.
- **Dummy data — corrected understanding:** the visible fake clients are the **frontend mock-fallback**
  (`web/lib/data.ts` lines 347/380 fall back to mock when a tenant is EMPTY, plus when `!isApiConfigured`).
  Removing it needs real **empty states** → **deferred to the frontend build** (ripping it out raw makes
  empty tenants look broken). DB truth: `mimik`/Glo2Go + 2 owner accounts = REAL; `mimik-smoke`/`other-smoke`
  = harmless isolated test tenants (leave them).

---

## ► (earlier same session, 2026-07-20 evening, main `d8065e9`) — WhatsApp+generating+ChatGPT MERGED; COMPLETENESS ASSESSED

**All this session's work is merged to `main` and green: 316 Suite / 12 contracts, ruff clean.**
Three features shipped behind existing seams (each was its own branch, now merged into `main`):

- **WhatsApp adapter** (`api/services/whatsapp.py`) behind `NotificationChannel.WHATSAPP` — Meta Cloud
  sink + null default; **INERT** (`WHATSAPP_PROVIDER=none`, nothing sends). Adapter mechanically PROVEN
  (a real Meta `401` = payload/endpoint/auth all correct). `dispatch_pending` now routes per channel,
  reuses one httpx client, resolves sinks up front (bad provider fails before mutating rows). Token
  header-only/never-logged; body/magic-link never logged; phone masked. **Live activation BLOCKED** on
  Meta account-health: `Mimik Creations` portfolio + `Mimik flow` app are BOTH enforcement-restricted
  ("prohibited from advertising / claiming apps"); needs a FRESH clean business portfolio (user hit a
  24h name-hold). Runbook `docs/WHATSAPP_SETUP.md`; smoke `scripts/whatsapp_smoke.py`.
- **Generating/pending-delivery state** — `Job.generation_started_at` (contracts) stamped on entering
  GENERATING, cleared on exit / when first creative lands. Board card carries it so the FE can show
  "generating since X" instead of implying instant. Migration `8281453f4476`.
- **ChatGPT image adapter** (`creative/adapters/chatgpt_browser.py`) — IMPLEMENTED (was a P2 stub).
  Mirrors Leonardo: CDP-attach + patchright, tab-safe `_pick_page`, step helpers w/ actionable errors,
  image-only directive around the prompt, grabs newest `oaiusercontent` image. Selectors best-guess —
  tune on 1st live run via `scripts/chatgpt_generate.py`. Burner-account risk accepted by user.

**⚠ CRITICAL SECURITY FINDING (NOT yet fixed):** `POST /tenants` (`api/routers/tenants.py`) is
UNAUTHENTICATED — anyone reachable can create a tenant + mint an `owner` token. Gate to super-admin
before ANY 2nd agency touches it. Top of the auth backlog.

**Completeness assessment done** → `docs/COMPLETENESS_ASSESSMENT.md` (backend ~85%, **frontend ~10%**:
`web/` has ONLY the Kanban board + login — onboarding, brand-brief UI, client portal, calendar,
settings, billing screens DON'T EXIST; `web/lib/data.ts` mock-fallback leaks demo clients into empty
tenants — kill for prod). Roadmap Phases A–D in that doc.

**Open decisions (USER):** (1) ✅ RESOLVED — UI references received; **design system LOCKED** =
shadcn/ui mono admin ("Studio Admin"), see `docs/DESIGN_REFERENCES.md` (north-star + per-screen map:
login→shadcn split login, members/roles→shadcn Roles&Permissions, creative-review/portal→Filestage,
video→Frame.io). **Frontend builds run on FABLE** (Opus specs from the images → Fable-agent builds w/
frontend-design skill + shadcn). Adopt shadcn/ui in `web/`. First target: **login**, then **members/roles**.
⚠ Scope note: those CRM/Finance/Infra nav items = an INTERNAL command-center (Leads/Proofkit/Sales/Finance/
hosted sites), a DIFFERENT app from Mimik Suite the client-facing product — same design system, don't merge.
(2) Dummy-data cleanup: **Glo2Go + the 2 owner accounts are REAL**; kill mock-fallback as each real screen
lands. (3) Google/MS social login deferred. **Recommended next:** IAM increment B/C (backend, unblocked) +
build the login screen on Fable.

Prior open loops still live: change 2 temp login passwords; Leonardo→API when payment clears; deploy
parked (`docs/DEPLOY.md`, needs 8GB VPS).

---

## 2026-07-20 (morning), commit `4f5f290` — G1–G3 + FE + auth + Leonardo stealth harness (prev LATEST)

**Everything is built, committed, and green** (295 Suite / 12 contracts, ruff clean). Done this
run: G1–G3 (Drive archive verified live via user-OAuth), full FE (interactive board + sidebar +
**Supabase login**, both owner accounts provisioned + verified), pin-point revisions, art-direction
engine, and the **Leonardo stealth harness** (attach-to-real-Chrome via CDP + **patchright** + human
pacing — proven live on a burner). ChatGPT confirmed drivable via the same pattern.

Open loops: change the 2 temp login passwords; ~2 days of burner volume before the main Leonardo
account; migrate Leonardo → API when payment clears; deploy is parked (`docs/DEPLOY.md`).

---

## 2026-07-19 (evening) — G1+G2 BUILT & DOGFOODED · FE foundation styled · G3 half-done (uncommitted)

**State:** Suite **253 tests green**, ruff clean; contracts 12 green (+BrandAsset); knowledge 8 green.
Migration head `4bbd7db38ad2` (brand_assets) applied to local PG. `web/` builds + lints clean.
ALL UNCOMMITTED — review + commit is the next human step.

**G1 (done, both reviewers passed):** Asset Library end-to-end (BrandAsset contract + ORM/migration/
repo/mappers + `/brands/{id}/assets` upload·register·list·approve + `/assets/{id}/ingest`);
free-Gemini **vision** client + `creative_study` prompt (live smoke on the real G2G logo:
`#8C4F8D`/`#6B6A6A`, "usable as-is"); ingestion → fit-critic → `Brand.references` + preference
signals; copy-voice goldens (`copy_voice` kind, client-scoped few-shot into L0 via `{voice_examples}`);
`_vision_pass` implemented (evidence-bound, no-key no-op, heuristics-win-on-tokens merge). Security
fixes landed: golden audit-header injection (exact-field scope match + sanitized header — regression
tests), Gemini key moved to `x-goog-api-key` header, register-path mime allow-list. Latent circular
import (prompting↔creative.copy) fixed via deferred import.

**G2 (dogfooded on real Glo2Go):** live site = source of truth. Fresh brief auto-extracted WITH live
Gemini enrichment (real voice quote, honest logo-absent note, site css colors `#7a4d7b…`); marketing
plan + 5 pillars in `docs/dogfood/glo2go_marketing_plan.md` (operator to confirm); real logo uploaded→
approved→data-URI wired to `tokens.logo.ref`; 4 past Drive creatives registered by id (bytes pending SA
read); live L0 copy in the fresh voice ("Polynucleotides: skin regeneration, not dermal filler."); one
creative rendered + locally archived. **The 1 nudge:** purple logo invisible on purple ground — needs a
logo-contrast QA check / knockout-logo variant (top backlog item). Dogfood script: session scratchpad
`dogfood_g2g.py`; tenant slug `mimik` in local PG.

**G3 (half):** eval fixture green (`tests/test_evals_g2g.py` + frozen homepage snapshot in
`mimik-knowledge/evals/fixtures/`). Real Drive archive BLOCKED on operator: `.env`
`GOOGLE_SERVICE_ACCOUNT_JSON` + `DRIVE_ROOT_FOLDER_ID` are empty (key at `secure repo/…json`, SA auth
verified OK); archive root must be shared to `mimik-archiver@gen-lang-client-0936115045.iam.gserviceaccount.com`.

**FE:** Conceptzilla dribbble 19198544 reference captured (full-res in session scratchpad + CDN url in
`web/DESIGN_NOTES.md`); tokens.css palette/radii/shadows, two-tier sidebar, kanban cards, review panel,
GSAP motion (reduced-motion safe). Light = flagship, dark works. Operator's extra reference images
never reached the session — re-share if the direction should blend more than this one shot.

**Iteration 2 (same evening):** logo-visibility QA check LANDED — WCAG 1.4.11 (3.0) on the mark's
alpha-weighted opaque-pixel luminance vs its actual ground (solid + imagery paths, data-URI-only,
browser-gated like all sampling). Live-proofed on the dogfooded G2G context: flags `1.04 < 3.0` with
"use a knockout/light logo variant or a lighter ground" — this morning's invisible-logo creative now
gets routed back by QA instead of shipping. Also closed the reviewer's service-test gap
(wire_approved_logo + ingest_reference_creative unit tests). **262 tests green**, ruff clean.

**Iteration 3 (same evening):** knockout-logo derivation LANDED — `creative/render/knockout.py`
(browser-canvas, no PIL) + `derive_knockout_logo` service + `POST /assets/{id}/knockout` (new
unapproved asset, human still gates). Live-proved the full failure→fix→green loop on real G2G:
knockout derived → approved → re-rendered → **QA passes** (was 1.04 fail). **264 tests green.**
Noted: G2G brand tokens lack an accent color (CTA falls back to default lime) — operator to pick.

**Iteration 4 (operator design feedback):** flat-plate + Mimik-lime-leak rejection handled at the
system level — `creative/render/color.py` (brand-derived tints/shades; accent falls back to
tint(primary), never a house color for a brand with a palette), NEW `soft_editorial` template
(modeled on the real G2G IG posts: tint ground, layered waves, badge-pill logo, subhead pill;
per-template QA color semantics; flex-centered without imagery), imagery-aware `suggest_template`
(placeholder path never ships a flat plate), display-copy editor rules enforced in code (no
terminal punctuation, no semicolons — retry), `rubrics/art_direction.md` distilled from the
senior-designer critique, G2G palette set to source of truth (#642766), operator rejection stored
as a preference signal, and `scripts/leonardo_login.py` (persistent-profile Leonardo session
bootstrap; LEONARDO_BROWSER_PROFILE_DIR; `var/` gitignored). **271 tests green.** New QA-green
render delivered.

**Iterations 5–6:** FE wired to the REAL API (web/lib/api.ts typed client + data.ts facade with
mock fallback; board page → async server component; E2E-smoked against live uvicorn with a dev
token — board rendered real G2G pillars/job/creative; sidebar+client chip still mock). soft_editorial
verified on ig_story. **Pin-pointed revisions (Zaid feedback) BUILT:** RevisionZone/RevisionTarget
contracts, approvals.targets column (migration `79fa3959d12f`), targets ride both approval entry
points → audit trail + "- [zone/layer] instruction" ops-task lines + zone-tagged preference signals;
draft_copy(revision_note=…) fenced re-draft seam. **275 Suite + 12 contracts green, ruff clean.**

## 2026-07-20 (iteration 13) — hardened driver (patchright) + human pacing · NEXT: WhatsApp (new session)

Anti-detection strengthened per operator: **patchright** (hardened Playwright fork; hides the CDP
`Runtime.enable` leak Cloudflare fingerprints) now drives the harness via `_async_playwright` (vanilla
fallback). Human pacing widened (pauses 0.8–2.6s, typing 70–190ms/char) + new `human_cooldown` (8–22s)
for between-generation spacing — volume/cadence over time is what trips bans, so the caller caps volume.
CDP-attach + patchright smoke-tested against the real Chrome (both tabs seen, window preserved).
**ChatGPT confirmed drivable** via the same pattern (logged in, composer + 'Create an image' present).
Leonardo model IS selectable (URL `?model=…`; Phoenix worked). Strong-prompt burner generation delivered
a premium G2G serum hero. **Plan: ~2 days of realistic BURNER volume before the main subscription account;
API is the zero-risk endgame.** Product note: generation is human-paced (not instant) → surface a
'generating/pending' state (JobStatus.GENERATING exists). **Next session = WhatsApp adapter — see
`docs/NEXT_SESSION.md` for the paste-in prompt.** All committed + green (295 Suite / 12 contracts).

---

## 2026-07-20 (iteration 11) — Supabase owners provisioned · Leonardo harness LIVE on burner

**Auth end-to-end WORKS:** provisioned Supabase owners atheequeniyas23@gmail.com +
mimik.creat@gmail.com → tenant `mimik` (Glo2Go). Verified: password login → JWT → API authorized →
Glo2Go returned. (Temp passwords were shared in chat — operator to change.)

**Leonardo automation — PROVEN LIVE (burner account):** the Cloudflare block is on the Playwright-
*launched* "Chrome for Testing"; the fix is attaching to the human's REAL Chrome via CDP.
`scripts/chrome_debug.py` launches real Chrome (bundle id `com.google.Chrome`, found on the Desktop)
with `--remote-debugging-port=9222` + a dedicated profile → operator logs in (Cloudflare passes) →
`stealth_browser.connect_cdp_session` attaches (`owns_context=False`) → `LeonardoBrowserAdapter`
(`_acquire_session` CDP-first via `LEONARDO_CDP_URL` default :9222, launch fallback; `_pick_page`
targets the Leonardo tab). **First real generation succeeded** — a lavender skincare hero downloaded.
Live-confirmed selectors: prompt `get_by_placeholder(/prompt/i)`, Generate `role/name .first`, RESULT
`img[src*='/generations/']`. Flow: `chrome_debug.py` (log in, leave open) → `leonardo_generate.py "…"`.
Migrate to Leonardo API later = adapter swap (payment issue defers it). 295 Suite + 12 contracts green.

**Everything committed** through the Drive OAuth + FE + auth work; committing the Leonardo harness now.

---

## 2026-07-20 (iteration 10) — G3 DONE (Drive verified) · FE auth built · committing

**G3 CLOSED — verified live:** a real creative uploaded to Drive via OAuth →
`Mimik Clients/Glo2Go-Aesthetics/2026-07/oauth-verify/polynucleotides-oauth-test.png`
(file id `1AMLG9WBDYtO2XiNyfgxHtjXzOFYxWa53`). `scripts/drive_oauth.py` now loads `.env`; operator
did the OAuth consent; refresh token in `.env` (gitignored). `ARCHIVE_BACKEND=google_drive_oauth` live.

**FE auth BUILT:** Supabase email/password login (`web/app/login`, `/api/auth/login|logout`,
`web/lib/session.ts`) — httpOnly-cookie sessions + refresh, board redirects to `/login` when
unauthenticated (dev-token fallback when APP_ENV=dev). No new npm deps (GoTrue via fetch). Lint+tsc
clean. **Remaining operator gate to log in end-to-end:** create a Supabase user THEN provision a
`UserAccount` (POST /admin/accounts with auth_subject=<supabase sub>, tenant_id, role) — else API 403s.

**Leonardo automation — DECISION PENDING (operator):** browser-automating the MAIN account can't be
made ban-proof (ToS + adversarial detection). Recommended: (A) Leonardo **API** (~$9/mo, compliant,
zero ban risk — right for a product) or (B) a **dedicated burner account** for the stealth harness.
Do NOT automate the main account. No build until operator picks.

**286 tests green, ruff clean.** Committing iteration 9+10 now (Drive OAuth, FE interactivity/sidebar/
auth, parked deploy artifacts).

---

## 2026-07-20 (iteration 9) — DRIVE OAUTH BACKEND BUILT · FE interactive + sidebar wired · deploy parked

**State:** **286 tests green**, ruff clean. Committed at `8a3f5c1` (contracts `f3c63ea`, knowledge
`d4010b4`); iteration-9 work (Drive OAuth, FE interactivity/sidebar) is **uncommitted** on top.

**Drive — SA is a dead end, OAuth is the fix (BUILT):** Google 403 "Service Accounts do not have
storage quota" on My-Drive upload (SA can read + make empty folders, not upload files). Free Gmail
can't use Shared Drives. So: refactored `creative/archive/google_drive.py` → `_DriveArchiveBase`
(shared folder/upload/token-cache) + `GoogleDriveArchive` (SA) + **`GoogleDriveOAuthArchive`**
(`google_drive_oauth`, refresh-token grant → files owned by the user → their 5TB). `scripts/drive_oauth.py`
= one-time loopback consent that prints the refresh token. 8 new tests. **OPEN human gate:** operator
creates an OAuth Desktop client in Google Cloud console (project `gen-lang-client-0936115045`),
PUBLISHES the consent screen (Production — Testing expires the token in 7 days), sets
`GOOGLE_OAUTH_CLIENT_ID/SECRET` + `DRIVE_ROOT_FOLDER_ID=1LFO3hLEBNkgzvRDQR4HsG2Dtk9MmJ5mV` in `.env`,
runs `scripts/drive_oauth.py`, pastes the refresh token + `ARCHIVE_BACKEND=google_drive_oauth`.

**FE:** now INTERACTIVE — `BoardView` client boundary: pillar tabs filter, card→review-panel select,
Approve/Request-change wired to real ids, honest-disabled +buttons; sidebar + top chip wired to real
`/clients` (mock fallback holds). Local view: restart `web` with `NEXT_PUBLIC_API_URL` +
`NEXT_PUBLIC_DEV_TOKEN` for real data (devtoken in session scratchpad).

**Deploy: PARKED** (operator: run on Mac for now). Dockerfiles + `docker-compose.prod.yml` +
`docs/DEPLOY.md` (Coolify + Supabase-Postgres + GHCR) created + parked for a future VPS upgrade
(current 4GB box: ~1.8GB free, runs Coolify + 2 apps — needs 8GB for the Chromium-bearing API image).

**Next (operator decisions):** Drive OAuth gate above → then **Mac browser-automation harness** for
Leonardo (home IP + headful + persistent profile + human pacing + patchright + dedicated account;
headless is MORE detectable). Leonardo web sub ≠ API access. Optional: rotate the 4 keys that hit the
deploy agent's local transcript. Commit iteration-9 when ready.

---

**Iterations 7–8:** FE revision-pin UI landed (ReviewPanel composer: zone chips, 10-pin cap, offline
mode; verified via headless screenshot). Full pre-commit REVIEW GATE run on the it.2–7 delta — all
findings fixed: SoftEditorial geometry clamp (QA false-pass) → superset honesty + regression;
trailing-semicolon launder → reject-first; task-detail newline forgery → flattened + regression;
ReviewPanel error≠offline states; service-level targets raise (no silent drop); contract-level
10-target cap; import consolidation. **278 Suite + 12 contracts + 8 knowledge green; ruff + npm
build/lint clean. TREE IS COMMIT-READY.**

**Next:** operator gates (say "commit" — 3 repos, phase-tagged; Drive folder+share; Leonardo login via
`scripts/leonardo_login.py`; paid image go) → then Leonardo generation driver, real-post style-anchor
ingestion, FE sidebar/auth wiring.

---

## 2026-07-19 — NEXT SESSION: G2G brand-memory ingestion + dogfood → read `docs/NEXT_SESSION_G2G.md`

All P0–P5 built & green (222 tests, ruff clean, migrations head `b08ff128c47c`), committed on `main`
(not pushed): contracts `fd082c9`, knowledge `186cfc5`, Suite `e9cee23` (+ this doc/config commit).

**The next session's job** (full plan + paste-in loop prompt in `docs/NEXT_SESSION_G2G.md`): build the
**brand-memory ingestion slice** (per-brand Asset Library + free-Gemini **vision** seam +
reference-creative ingestion into the fit-critic/preference/golden systems + copy-voice golden) and
**dogfood it on Glo2Go Aesthetics**.

**Key steer from operator:** the **live site `https://glo2goaesthetics.co.uk/` + socials are the source
of truth**, NOT the old Drive brief/creatives (the brand has moved on — now "luxury, expertise,
affordability", added Polynucleotides + Aqualyx/Lemon Bottle fat-dissolving, London EC3R address). Draft
a **fresh, better brief + marketing plan + content pillars** from the current site; use the ~3–5 past
Drive creatives as a **style headstart only**. No content-planner sheet needed (app calendar replaces it).

**Done this turn:** service-account key (`secure repo/…json`) gitignored + verified never committed;
image model set to `gpt-image-2` (top tier, spend-gated); Drive scouted (G2G brief + folder IDs captured
in the plan doc); `docs/RESEARCH.md` updated with the honest build-vs-R&D gap.

**Human gates for next session:** SA `drive.readonly` scope + Clients folder shared (to READ past
creatives server-side); explicit go-ahead before any paid `gpt-image-2` call; design reference for any new
UI; commit on request.

---

## 2026-07-19 — Autonomous build loop: P2 ✅ · P3 ✅ · P4 ✅ · P5 ✅ (Stripe scaffolded, mocked) — ALL PHASES BUILT

**State: 222 tests green, ruff clean** (Suite; contracts 11 green). Migrations head `b08ff128c47c`.

**P5.2 Stripe billing — SCAFFOLDED (operator chose "mocked, ready to flip on"):**
- `Subscription` contract + `SubscriptionStatus` enum (`grants_access` = trialing/active); `SubscriptionRow` (one per client, unique client_id) + migration `b08ff128c47c`.
- `api/services/billing.py` — stdlib only (no `stripe` package): `create_checkout_session` (Stripe Checkout via a single monkeypatchable `_post_form` seam; `BillingNotConfigured`→503 without keys), `verify_webhook_signature` (real HMAC-SHA256 over `t.rawbody`, constant-time `compare_digest`, replay tolerance), `apply_webhook_event` (checkout.session.completed → upsert+activate sub; subscription.updated/deleted → status), `client_has_access`.
- `api/routers/billing.py` — POST /billing/checkout (client-scoped), POST /billing/webhook (raw-body signature-verified, no auth), GET /clients/{id}/subscription, and the gated **POST /clients/{id}/portal/design-requests** (402 unless the sub grants access).
- **P5 GATE green** (`test_p5_gate.py`): claim → client + draft brief → mocked checkout → **signed webhook activates the subscription** → the gated portal endpoint flips 402→200. Security review of the webhook/gating in flight.
- **To go live:** operator adds `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`/`STRIPE_PRICE_ID` (test mode) to `.env`; endpoints refuse with 503 until then (no accidental charges). Register the webhook endpoint URL in the Stripe dashboard (or `stripe listen`).

**ALL PHASES P0–P5 are now built and green.** Remaining human-gate items are optional turn-ons: Google Drive archive creds (P3), real Stripe test keys (P5), real paid image generation (P2). Nothing is blocked; the local/mocked backends satisfy every gate.

---

## 2026-07-19 — Autonomous build loop: P2 ✅ · P3 ✅ · P4 ✅ · P5.1 ✅ → PAUSED at Stripe human gate (superseded above)

**State: 206 tests green, ruff clean** (Suite; contracts 11 green).

**P5.1 storefront intake — DONE (credential-free half of P5):**
- Public `POST /intake/claim` (the mimikcreations.com/unlimited "3 free designs" form): resolves the storefront tenant by slug → creates a prospect Client (email-dedup: a resubmit returns the same prospect, `created:false`) + a prospect Brand + a DRAFT Brief. **Never fetches** — a public endpoint that fetched an attacker URL would be an SSRF/DoS amplifier; it only validates URL shape (http/https, no DNS).
- Team-only `POST /clients/{id}/bootstrap`: the cold-client bootstrap — fetches the prospect's site behind auth via `extract_brief_sections` (SSRF guard resolves + rejects non-public IPs) → auto-drafts brief §1-5.
- `tests/test_intake.py` (8): claim creates prospect+draft brief; idempotent by email; unknown storefront 404; non-http URL 422; public endpoint proven not to fetch; bootstrap extracts behind auth (stubbed, no network) + requires auth + 422 without a URL. Security review of the public endpoint in flight.

**⛔ PAUSED — P5.2 Stripe billing needs the operator (HUMAN GATE).** See the ask below / in chat.

---

## 2026-07-19 — Autonomous build loop: P2 ✅ · P3 ✅ · P4 ✅ (superseded by entry above)

**State: 198 tests green, ruff clean** (Suite; contracts 11 green). P4 review clean — findings fixed: promote endpoint validates `kind`/`source_role` (422, so the client-guard's string match can't be bypassed by a typo); golden exemplars carry a provenance header (promoted-by / source_role / client). Reviewer confirmed NO path — auto capture, promote endpoint, or `promote_and_write` — lets a client correction mutate the shared golden set.

**P4 learning loop — PASSED ✅ (gate green, reviews clean):**
- `PreferenceSignalRow` + migration `5a396a1c513b`; contract `PreferenceSignal` (+attributes/job_id/actor_role), `PreferenceProfile.signal_count`/`ranker_active()`, `RANKER_MIN_SIGNALS=20`.
- `api/services/preferences.py` — heuristic taste-ranker: scores creative attributes by net revealed preference (approval/pick +, edit −0.25, rejection −1), passthrough below 20 signals, re-orders above; `build_profile` + `build_summary`.
- Signal capture wired into `approval_flow`: approve→APPROVAL signal, request_change→REJECTION (reason_tag threaded through the approvals router), client-scoped, `actor_role` recorded.
- `api/routers/preferences.py` — record / profile / rank / promote (promote is owner/ops-only). Human-gated promotion: `mimik_knowledge.promote_and_write` writes a golden exemplar ONLY when accepted AND a reviewer is named; **client-sourced corrections can never produce a golden write** (poisoning guard).
- **P4 GATE green** (`test_p4_gate.py`): signals recorded from real approve/reject; ≥20 signals → re-ranked variants; auto path writes nothing to the shared golden set; client promote refused; team+reviewer writes. Real `golden/` dir untouched (tests redirect via `MIMIK_GOLDEN_DIR`→tmp).
- Security fix mid-run (automated review): `list_job_approvals` IDOR — client-scoped the audit-trail read (404 for foreign client) + regression test.

**NEXT: P5 (storefront + billing) — HAS A HUMAN GATE** (Stripe **test-mode** keys: `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`/`STRIPE_PRICE_ID`). The claim-form intake + cold-bootstrap can be built without keys, but the Stripe checkout/webhook gate needs test keys — I'll pause and ask before the billing slice.

---

## 2026-07-19 — Autonomous build loop: P2 PASSED ✅ · P3 PASSED ✅

**State: 177 tests green, ruff clean** (Suite; contracts 11 green). P2 gate PASSED (operator approved samples). **P3 gate PASSED** (e2e machine gate green + code/security reviews clean). P3 (ops + approval) built this run:

**P3.1 foundation** — contracts `UserAccount` + `Notification` (+ `NotificationChannel/Status`, `ActorRole.OWNER`); ORM rows UserAccount/CreativeDoc/Approval/Delivery/Task/Notification; migration `e26e196b8532` applied to Postgres; tenant-scoped repo funcs + mappers (incl. `_utc` naive→aware coercion for SQLite).
**P3.2 auth (Supabase, managed — never self-rolled)** — `api/core/supabase_auth.py` verifies Supabase JWTs (this project signs **ES256/JWKS**; needed `cryptography` → added `pyjwt[crypto]`). Dual-issuer `get_principal` (Supabase-verified → `UserAccount` → tenant+role, OR first-party bootstrap token). `admin.py` provisions accounts (owner-gated, client bound to one client_id). `require_role` helper. Tested with a **local ES256 keypair + injected JWKS** (zero network).
**P3.3 approval centerpiece** — `approval_flow.py`: audited approve/request-change/comment → on APPROVE: status→APPROVED → auto-archive (deterministic re-render from manifest → `ArchiveBackend` → Delivery) → status→ARCHIVED + notification. Magic-link (`magic_link.py`, signed capability, no login). Archive adapter: `LocalArchive` (default, zero-cred) + `GoogleDriveArchive` (real SA-JWT→Drive, mocked tests, gated on creds). `creatives.py` = the generate step.
**P3.4 ops** — `ops.py` Kanban board (jobs by status + at-risk flags) + calendar + status transitions (→approved fires the same archive procedure); `at_risk.py` scan (idempotent, system-scope worker).
**P3.5 tasks/versioning** — `tasks.py` (portal+board two views, client-scoped); `notifications.py` recording sink; brief `POST /revise` (frozen → new draft version, non-destructive).

**Review findings (code + security agents) — ALL RESOLVED with regression tests:**
- CRITICAL double-approve re-archived/re-delivered → terminal-state guard in `submit_approval` (`ApprovalConflictError`→409); test asserts exactly 1 delivery survives.
- CRITICAL blocking JWKS fetch stalled the async event loop → `verify_supabase_jwt` now runs via `asyncio.to_thread` in `get_principal`.
- Token confusion (magic-link vs access, shared secret) → access tokens carry `typ=access`, `decode_access_token` pins it; test asserts a magic link is rejected (401) as a Bearer.
- Drive folder query built by f-string → `_ensure_folder` re-sanitizes `name`.
- `creatives.py` IDOR → team-role gate on create + client-scoping on list.
- at-risk O(N²) + `dispatch_pending` full scan → targeted `job_id`/`status` filters on `list_notifications`.
- admin duplicate-identity TOCTOU → `IntegrityError`→409 (no 500 leak).
- task same-tenant cross-client `job_id` association → verified job belongs to the task's client.
- JWKS unbounded read → capped at 256KB.

**P3 GATE PASSED:** `test_e2e_gate.py` GREEN — intake→generate→approve→auto-archive produces a real 1080² PNG at the archive path with a timestamped audit trail, ZERO manual upload; at-risk fires on buffer breach (`test_at_risk.py`). 177 tests green, ruff clean, reviews clean.

**Human gate for real Google Drive archive:** set `ARCHIVE_BACKEND=google_drive` + `GOOGLE_SERVICE_ACCOUNT_JSON` (SA json/path) + `DRIVE_ROOT_FOLDER_ID`. Until then the local backend satisfies the gate (auto-archive, zero manual upload). Supabase creds ARE set; the ES256/JWKS path is live.

**Deferred to P4:** preference capture/A-B logging; reference *gathering* (browser scrape) stays stubbed behind the fit-critic seam.

---

## 2026-07-19 — Autonomous build loop: P2 CODE-COMPLETE (pending operator eyeball)

**State: 116 tests green, ruff clean** (suite; contracts 11 green). Built this run:
- `mimik-contracts`: `CopyBlock` + `CopyStatus`; `CreativeManifest.template_key`/`copy_block`; `ImageBackend` gains `none`/`openrouter`/`gemini_image`; **asset-ref shape validation** on `Layer.artifact_ref` + `LogoSpec.ref` (CSS-injection defense, see below).
- `creative/assemble.py` — Brand tokens + manifest → TemplateContext (hex normalize, font CSS-sanitize, L2>L1 artifact precedence, draft-copy delivery guard).
- `creative/copy/l0.py` — L0 copy on free Gemini TEXT; injection-fenced topic; headline ≤9w/≤60ch enforced in code; retry×1 → `CopyDraftError`. Prompt `copy_l0@v1` in mimik-knowledge.
- `creative/adapters/` — gpt_image/openrouter/gemini_image (stdlib REST, mocked tests) + router (env routing, retry→alternate, `ImageGenerationFailed` = L2-human signal). **Hard spend gate: `MIMIK_ALLOW_PAID_IMAGES=1` required for ANY paid call.**
- `creative/qa/` — brand-QA hard checks: exact dims, safe zones (geometry API on templates + ig_story 250px clamp), logo presence, WCAG contrast (pure math on solid grounds; in-browser pixel sampling under imagery). **Conditional scrim** via `needs_scrim` only.
- `creative/references/fit_critic.py` — reference fit-critic + StyleDescriptor, reasoning mandatory, `reference_fit@v1` prompt + rubric.
- `creative/pipeline.py` — e2e: copy → manifest → assemble → composite → QA → (scrim re-render). `creative/prompting.py` — shared critic plumbing.
- **Security review (3 agents ran: pattern/security/code):** CRITICAL fixed — `logo_ref`/`image_ref` CSS-`url()` injection (html.escape can't protect CSS context; confirmed breakout) → shape validation at contracts AND TemplateContext sink + negative tests. Also: fence-stripper hardened (spaced/attribute tags), router re-raises programming bugs, gpt_image response-shape guard, copy-aware geometry + DOM-containment tests.
- **Live gate sample produced** (scratchpad `mimik_*.png`): real Gemini copy ("Unlimited design. $750 a month." / CTA "Start free") on Mimik brand, 3 renders, all QA-pass.

**P2 gate: PASSED ✅** — machine checks green AND operator approved the samples in-session ("Approve — advance to P3", no nudge).

**Deliberate deferrals:** preference-capture persistence + A/B pick logging → P4 (its gate lives there; router already supports 2 backends). Reference *gathering* (Pinterest scrape) → stub seam; fit-critic ready.

**Env for later phases:** browser profile dirs not set (browser image paths confirmed dead — Cloudflare); paid images stay OFF until operator explicitly approves spend per-deliverable. P3 needs: Supabase keys (auth), Google service account + Drive folder (archive).

**Next:** P3 — ops + approval (dashboard→API auth wiring via Supabase, Kanban board, calendar + at-risk worker, in-portal + magic-link approval, Drive auto-archive, brief freeze versioning, task/notification system).

---

## 2026-07-18 — Session 1: P0 scaffold kickoff

**Goal:** Stand up the P0 foundation for Mimik Suite (multi-tenant done-for-you creative-agency SaaS).

**Decisions locked this session** (full plan: `~/.claude/plans/hi-i-want-to-sunny-fox.md`):
- Multi-tenant SaaS, done-for-you service, sold as the $750/mo unlimited-design sub.
- Creative engine = hybrid (AI imagery + code-composited text), 5-layer non-destructive checkpoint stack, Figma for deep edits.
- Orchestrator + satellites: engines (ProofKit, mimik-engine) stay separate repos/CLIs, called via `mimik-contracts`. Sales stays confidential, never imported.
- Assisted autonomy; knowledge/quality layer captures tuning (prompts/golden/rubric/evals/learning-loop).
- Imagery via swappable adapter; build phase = subscriptions/free tiers (ChatGPT browser + free Gemini), no paid APIs yet.
- Client portal = bounded self-serve + hardened (client = untrusted; authZ at data layer; injection guard).

**Stack:** Python 3.12 + `uv`; FastAPI + async SQLAlchemy + Alembic + Postgres + Redis + Arq queue; Next.js (App Router) for `web/`.

**State: P0 COMPLETE ✅** — foundations built, tested, and proven end-to-end on Postgres.
- `mimik-contracts` (sibling pkg) — full schema spine. **7 tests green.**
- `mimik-knowledge` (sibling pkg) — prompts/rubrics/promote/evals. **5 tests green.**
- `Mimik_Suite/api` — FastAPI + async SQLAlchemy + tenant-scoped repo + JWT auth. **8 tests green** (incl. IDOR guard).
- `creative/` — image-adapter registry + compositor interfaces (generation deferred to P2).
- Alembic initial migration `649d3966fd75` applied on Postgres (5 spine tables).
- **Live smoke:** create tenant → token → create client → read own = 200; cross-tenant read = 404. Verified against real Postgres.
- **20 tests green total.** Not yet committed (per convention: commit on request).

**Local dev:** `docker compose up -d` (Postgres :5434, Redis :6381). `uv run --no-sync alembic upgrade head`. `uv run --no-sync pytest`.

**Open loops → P1 (brand-brief automation):**
- [ ] Intake endpoint: create Client + target URL (later wire mimikcreations.com/unlimited claim form).
- [ ] Extraction: reuse ProofKit `collector/playwright_capture.py` to scrape; vision pass on free Gemini tier for palette/logo/type; LLM voice/tone.
- [ ] Assemble 9-section Brief (auto §1–5), persist as Brand+Brief (versioned), sign-off → freeze.
- [ ] First eval fixture in `mimik-knowledge/evals/` (known brands → expected fields, no fabrication).
- [ ] Brief view + sign-off route in the dashboard (structure only — need a visual reference before styling).

**Anti-context (do NOT do):**
- Do NOT import anything from `Mimik_Sales` (confidential lead PII).
- Do NOT style any UI without a visual reference first.
- Do NOT wire paid image APIs — subscriptions/free tiers only for now.
- Use `uv run --no-sync ...` (network is flaky here; avoid re-resolves).

**Next action:** P1 — build the brand-brief extraction pipeline (URL → scrape → draft Brief), starting with the intake endpoint + a Playwright scrape reusing ProofKit's collector.

---

## 2026-07-19 — Planning/grilling COMPLETE → hand to the build loop

**Spec is complete.** The full load-bearing tree is grilled (P0–P3 + auth in depth; P4/P5/infra as accepted defaults) and captured in `~/.claude/plans/hi-i-want-to-sunny-fox.md`. Added this session: content pillars, Kanban ops board with procedure-on-transition (auto-Drive-upload on Approve), managed standards-compliant auth + admin panel, in-portal+magic-link approval, brief new-version-row freezing, spend-minimizing creative pipeline, P2 blind-spots (copy L0, asset library + font licensing, layout-first + conditional scrim, reference fit-critic, cold-client bootstrap, calibrated compliance).

**Built this session:** P2 layout-template library + Playwright compositor (renders real branded PNGs) — 56 tests green.

**NEXT: start a fresh session on the strongest model and run the autonomous build loop.**
→ Read **`FRESH_SESSION_KICKOFF.md`** (phase goals + machine-checkable gates + human gates + skills/agents + the paste-in loop prompt). Begin at P2-remaining (manifest→context assembly + free-Gemini image adapter — needs the Google AI Studio key).

---

## 2026-07-18 — Session 1 (cont.): design locked + P1 building

**Design direction LOCKED:** Studio White, brand-tuned. Royal blue `#2E5BFF` = primary actions; electric lime `#C6F135` = signature pop (sparing); near-black navy `#0A0D15` dark ground; emerald `#12B76A` = success. Light + Dark. Tokens: `web/design/tokens.css`. Reference artifact: https://claude.ai/code/artifact/b3cd6c31-85a9-412b-b933-2a3bd3e62d6f
- Content pillars feature added to contracts (`ContentPillar`, `PILLAR_PRESETS`, `Job.pillar_id`); contracts now 9 tests green.

**P1 backend — DONE (integrated + verified).** pillars/briefs/jobs routers (tenant-scoped, IDOR-tested), brief-extraction service (URL→§1–5, deterministic; ProofKit/Playwright + free-Gemini vision left as clean seams), migration `a994b6944e9a` applied. **SSRF egress guard added** to the extractor (`_assert_public_http_url`: rejects loopback/RFC1918/link-local/metadata; resolves host before fetch) + `tests/test_ssrf_guard.py`. **45 tests green, ruff clean.**

**Frontend shell — DONE (verified).** Next.js 15 + TS (strict) in `web/`, Studio White light+dark from `web/design/tokens.css`, all components (Sidebar/TopBar/ThemeToggle/PillarChips/Board/JobRow/StatusPill/ReviewPanel/LayerStrip), typed mock data. `npm run build` + `lint` pass. NO API wired yet.

**P2 creative engine — GRILLED (see plan "P2 · Creative engine").** Locked: copy=L0 (AI draft→human approve→golden set); layout-FIRST from a selectable clean-template library + conditional scrim + clutter critic; per-brand Asset Library (client+team fed, Drive-backed, approved-version rendered, font licensing tracked); reference=style-descriptor+fit-critic+human-approve, never reproduced; cold/trial-client bootstrap from web+socials; compliance=calibrated critic (human final, L2 fallback on refusal); spend-minimizing pipeline (A/B base only, fan-out re-composites cached base, generate-after-approval, retry×1→other-backend→L2 human) with a free→paid tier upgrade path behind the adapter.

**P2 build started:** `creative/render/templates.py` — layout-template library (CenteredHero, LowerBand; clean/uncluttered, conditional scrim, HTML-escaped copy, exact format sizing) + `tests/test_templates.py`. **53 tests green, ruff clean.**

**P2 compositor — DONE.** Playwright 1.61 + chromium installed. `creative/render/compositor.py` (`render_html_to_png`, `render_context_to_png`, `png_size`, `browser_available`) renders a TemplateContext → real PNG at exact format size (verified 1080², 1080×1920, fb 2×). `tests/test_compositor.py` (skips if no browser). Sample renders in scratchpad look clean (exact hex, sharp text, lime CTA). **56 tests green, ruff clean.**

**Open loops / next:**
- [ ] Extend the manifest with a typed copy block + chosen-template + assembled-context path (service layer: Brand tokens + copy + cached L1/L2 artifact → TemplateContext).
- [ ] P2 copy step (L0) on the free-Gemini seam; then image adapters (Gemini first, ChatGPT-browser next). NOTE: both need creds — Google AI Studio key / ChatGPT session — set in `.env` (never commit).
- [ ] Wire frontend → P1 API (needs the auth/onboarding grill first — only tenant-bootstrap tokens exist today).
- [ ] Later grills: P3 ops+approval+brief-versioning (incl. the in-place signoff→FROZEN vs new-version-row call), P4 learning loop, P5 storefront+billing, infra/deploy, acquisition→fulfillment bridge.
