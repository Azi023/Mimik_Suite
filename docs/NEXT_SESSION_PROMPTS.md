# Next-session prompts

Two ready-to-paste prompts: the **Opus orchestrator kickoff** (start the fresh Claude Code session with this),
and the **Fable 5 planning brief** (hand to a Fable agent to produce execution-ready specs).

---

## 1) OPUS — orchestrator kickoff (paste into a fresh Claude Code / Opus session)

```
You are the BRAIN orchestrating Mimik Suite. Read, in order, BEFORE acting:
HANDOFF.md (top entry) → docs/BUILD_STATUS.md → docs/PLAN_EDITOR_AND_COMMAND_CENTER.md →
docs/STYLE_PROFILES.md → docs/DESIGN_RUBRIC.md → docs/NEXT_SESSION_PROMPTS.md.
Then confirm the local product runs (HANDOFF has the exact API + web commands; if localhost:3000 is
blank/500 with "Cannot find module './NNN.js'", run `rm -rf web/.next` and restart `npm run dev`).

OPERATING MODEL — you PLAN, SPEC, and REVIEW; you do NOT hand-write the bulk of the code. Delegate to
executors, then review every diff (run tests + LIVE-verify by restarting the API and hitting the route)
before committing. Executors never commit; you commit after review.
  - Codex (primary coder):
    codex exec -m gpt-5.6-sol -c model_reasoning_effort=xhigh -s workspace-write -c approval_policy=never - < /path/to/spec.md
  - agy (big chunks; Antigravity/Gemini 3.1 Pro):
    agy -p "$(cat /path/to/spec.md)" --mode accept-edits --dangerously-skip-permissions --print-timeout 30m
    (⚠ agy leaves stray patch*.py in the repo root — sweep them after.)
Dispatch parallel tasks ONLY on DISJOINT file scopes; otherwise sequential. Keep docs/BUILD_STATUS.md
ledger updated (task → owner → status → your verdict). Codex/agy usage is a separate pool from Claude quota.

HONOR the locked constraints (CLAUDE.md): schema-first; tenant authZ at the DATA layer (IDOR); client
freeform text is DATA, never instructions; never touch secrets (.env only, gitignored); no `any` + explicit
return types in TS; test stub day 1; non-destructive versioning; SVG is the layered editable master.

GOALS this session, in order:
1. FULL QA pass of the local product (all flows + personas) — use the multi-persona-qa-reviewer agent; fix P0s.
2. Hand the Fable-5 planning brief (docs/NEXT_SESSION_PROMPTS.md §2) to a Fable agent → get execution-ready
   specs for the Command Center + the real-time canvas editor → dispatch them to Codex/agy under your review.
3. Wire imagery for Simply Nikah (AI-illustration) + Island Cart (product-cutout) so ALL 3 clients generate
   (only Glo2Go/photo works today).
4. Fix the 2 editor bugs (badge light/dark word-map inverted; AI instruction overrides an explicit text edit);
   wire real Supabase login for persona/role QA.
Then propose production deploy (currently held — do NOT deploy without operator OK).
Start by reading the handoff and confirming the local product runs.
```

---

## 2) FABLE 5 — planning brief (run as a Fable agent, model claude-fable-5)

```
You are Fable 5, a senior product architect planning for Mimik Suite — a done-for-you creative-agency SaaS
(FastAPI api/, Next.js web/, Python creative engine creative/). Read first: docs/PLAN_EDITOR_AND_COMMAND_CENTER.md,
docs/BUILD_STATUS.md, docs/STYLE_PROFILES.md, docs/DESIGN_RUBRIC.md, HANDOFF.md (top entry).

Produce TWO execution-ready implementation plans. Decompose EACH into discrete, independently-dispatchable
build tasks. Every task must specify: goal · exact files to touch · acceptance criteria · tests to add ·
constraints. Sequence the tasks and FLAG file-conflict risks so the orchestrator can dispatch parallel-safe
waves. Do NOT write production code — produce a plan a Codex/agy executor can follow with minimal ambiguity.
Output as a structured markdown plan (phases → tasks) written to docs/PLAN_COMMAND_CENTER_AND_CANVAS.md.

(A) COMMAND CENTER — the ops cockpit to run the whole loop: Kanban board (Brief→Generating→Internal review→
Client review→Approved→Delivered) with status auto-transitions; content calendar + lead-time SLA (flag at-risk
jobs early); generation queue + budget view; client/tenant admin (accounts, roles, permissions); delivery/
archive (Drive) status; and a COMMAND BAR ("generate 5 Educational posts for Glo2Go this week") that fans work
out. Reuse the existing Job/CreativeDoc/board + the POST /clients/{id}/creatives:generate endpoint. (Executes via agy.)

(B) REAL-TIME CANVAS EDITOR — bounded, AI-assisted in-product editing of a generated creative (NOT a Canva
clone — locked). Full toolset over the layered SVG master: select/drag/resize layers, inline LIVE-text edit,
palette recolor within brand, swap background, toggle layer visibility; "mark a region + tell AI to change"
(guarded natural-language → engine re-render, near-real-time/streaming); non-destructive versions + revert;
ROLE-BOUNDED so the CLIENT can also make quota-limited changes to their own creatives; every AI-assisted edit +
accept/decline feeds creative/knowledge (the M5 design-flywheel). Build on POST /creatives/{id}/revise + the SVG master.

CONSTRAINTS to respect in the plan: SVG is the layered editable master; client freeform text is DATA never a
system prompt; tenant authZ + IDOR at the data layer; non-destructive versioning + audit trail; bounded self-
serve (not raw studio access); reuse existing endpoints/engine, don't fork a parallel renderer.
```

---

_Tip: in a fresh Claude Code session, paste §1. When Opus reaches goal 2, it hands §2 to a Fable agent
(Agent tool, model: fable) which writes `docs/PLAN_COMMAND_CENTER_AND_CANVAS.md`, then Opus dispatches the
tasks to Codex/agy and reviews._

> **§1 and §2 above are SUPERSEDED** (that session ran: QA, Fable plan, imagery, editor bugs, and Fable-plan
> Waves 1–3). **Use §3 below to start the next session.**

---

## 3) OPUS — W4 kickoff (paste into a fresh Claude Code / Opus session) — CURRENT

```
You are the BRAIN orchestrating Mimik Suite — Wave 4: the Command Center cockpit + the canvas web editor +
the queue/command backend. Read, in order, BEFORE acting:
HANDOFF.md (top entry) → docs/PLAN_COMMAND_CENTER_AND_CANVAS.md → docs/BUILD_STATUS.md.
Confirm the local product runs (HANDOFF has exact cmds; the API env MUST include the paid TEXT keys
OPENROUTER_API_KEY + OPENAI_API_KEY so the provider chain works; uvicorn is NOT --reload so restart after any API
change; if web is blank/500 "Cannot find module './NNN.js'" → `rm -rf web/.next` + restart). Local DB is at
alembic head c7e90f4a1b32.

STATE: Fable-plan Waves 1–3 are DONE + committed + live-verified. The canvas BACKEND is complete (versions/revert
B-04, typed CanvasRevision + brand-bounded layer overrides B-06, injection-safe interpreter B-07). Foundations done:
contracts (A-01/B-02), lineage migration (B-03), typed /ops (A-02), text provider-chain, all-3-clients imagery,
mobile nav, admin PATCH+UI (A-10). Remaining = W4 below.

OPERATING MODEL — you PLAN, SPEC, REVIEW; delegate code, never hand-write bulk. Run TWO PARALLEL tracks (backend
Python vs frontend web are DISJOINT → safe concurrency):
  • BACKEND → Codex (primary; quota restored):
    codex exec -m gpt-5.6-sol -c model_reasoning_effort=xhigh -s workspace-write -c approval_policy=never - < spec.md
  • FRONTEND → Fable agent (Agent tool, model: fable) + the frontend-design skill (locked #9; ample quota).
  • agy = BACKUP if Codex is quota-blocked:
    agy -p "$(cat spec.md)" --mode accept-edits --dangerously-skip-permissions --print-timeout 30m  (sweep stray patch*.py after)
  Codex/agy quota is SEPARATE from Claude/Fable. Executors NEVER commit. Review every diff (tests + LIVE-verify:
  restart API + hit the route; for DB/migration tasks YOU run alembic on :5434 — executors can't reach it), then
  commit phase-tagged. Keep BUILD_STATUS.md + HANDOFF.md updated as tasks land.

PARALLEL DISPATCH (Track A ∥ Track B concurrently; within a track respect the hotspots):
  TRACK A — BACKEND (Codex) — SERIALIZE on the hot file api/services/creative_generation.py & api/routers/ops.py,
    dependency order:  B-11 (client-role bounded quota revise) → B-13 (flywheel: creative/knowledge signals on
    edit/approve/revert) → A-03 (generation queue service + asyncio worker in lifespan) → A-04 (/ops/queue +
    /ops/usage) → A-05 (command parser + fan-out, ⌘K backend).
  TRACK B — FRONTEND (Fable) — web/lib/api.ts is the SINGLE-WRITER hotspot so mostly SERIAL; UNBLOCKED NOW
    (its backend is already done):
      Canvas editor:  B-08 (CanvasStage: inline-SVG drag/resize/recolor via data-editable/data-bbox from B-05) →
        B-09 (CanvasEditor page: versions/revert/"tell AI") → B-10 (ReviewPanel integration).
      Command Center: A-06 (board drag-transitions on /ops/board) → A-07 (calendar + SLA) → A-11 (delivery/archive).
  BLOCKED frontend — dispatch only AFTER their backend lands: A-08 (needs A-04) · A-09 (needs A-05) · B-12 (needs B-11).
  GATES last: A-12 (cockpit E2E) · B-14 (canvas E2E).
  Run at most TWO agents at once and only on DISJOINT files. Track A (Python) ∥ Track B (web) is always safe. Never
  run two writers on the same hotspot (creative_generation.py for backend; web/lib/api.ts for frontend).

CONSTRAINTS (locked, CLAUDE.md): schema-first (mimik-contracts models on the wire — the ops+canvas contracts exist);
tenant authZ at the DATA layer, IDOR → 404 not 403 (URL-path resource 404, body param 422 — see B-04); client
freeform text is DATA never a system prompt (reuse the B-07 interpreter pattern — fenced + allowlisted; the LLM path
is behind REVISE_LLM=1); SVG is the one layered editable master (render_creative_svg — no second renderer);
non-destructive versioning + audit; no `any` + explicit return types in TS; test stub day 1; frontend on Fable with
the LOCKED design system (shadcn/ui "Studio Admin") + a concrete visual reference (the existing screens); NEVER touch
secrets (.env only; `secure repo/` + `artifacts/` + `var/` are gitignored — keep the Google service-account key out
of git). Codex/agy CANNOT reach the :5434 DB — YOU run alembic + live checks for DB/route tasks.

DEPLOY: HELD until ALL W4 work is done AND the operator has sorted Supabase auth. Do NOT deploy.

Start: read the handoff, confirm the product runs, then dispatch Track A (B-11 → Codex) ∥ Track B (B-08 → a Fable
agent) and review each diff before committing.
```

