# Mimik Suite — Fresh-Session Build-Loop Kickoff

Paste the **LOOP PROMPT** (bottom) into a fresh Claude Code session on the strongest model
available (Opus / Fable, high effort). It runs an autonomous build loop over the phases,
self-verifying against the acceptance gates, pausing only at the listed human gates.

## Read-first (the loop MUST read these before building)
- `~/.claude/plans/hi-i-want-to-sunny-fox.md` — the full living plan; every locked decision.
- `CLAUDE.md` — inviolable constraints.
- `HANDOFF.md` — current state (top entry).

## Current state (2026-07-19)
- **Stack:** Python 3.13 + `uv`; FastAPI + async SQLAlchemy + Alembic + Postgres(:5434) + Redis(:6381); Next.js 15 (`web/`). Playwright + chromium installed.
- **Done:** P0 (foundations, tenant isolation), P1 (brand-brief backend + SSRF guard), P2-partial (layout-template library + Playwright compositor rendering real PNGs), dashboard shell (Studio White light+dark), design tokens locked (`web/design/tokens.css`).
- **Tests:** 56 green, ruff clean. Migration head `a994b6944e9a`. Postgres/Redis via `docker compose up -d`.
- **Packages:** `../mimik-contracts` (schemas), `../mimik-knowledge` (prompts/rubrics/evals), `Mimik_Suite` (`api/ web/ creative/`).

## Inviolable constraints (from CLAUDE.md)
Schema-first (`mimik-contracts`) · tenant authZ at the DATA layer (the IDOR test must stay green) · client = untrusted (injection + SSRF guards) · no secrets in git · **no paid APIs during build** (subscriptions/free tiers behind the swappable adapter) · `uv run --no-sync` (network is flaky) · never touch `Mimik_Sales` · no UI styling without a reference (`web/design/tokens.css` IS the reference) · **best-standard managed auth, never self-rolled**.

## Phases — goal + acceptance GATE (advance only when the gate is green)
- **P0 ✅** — foundations. GATE: `uv run --no-sync pytest` all green; tenant-isolation/IDOR test passes.
- **P1 ✅** — brand-brief backend. GATE: pytest green; a brief auto-drafts §1–5 from a URL fixture; SSRF guard rejects internal targets.
- **P2 (in progress)** — creative engine. Remaining: manifest→`TemplateContext` assembly (Brand tokens + copy + cached L1/L2 artifact); **copy step L0 via the free Gemini API (TEXT only)**; **image adapters** behind the swappable adapter; reference-research + fit-critic; brand-QA critic (code checks now, vision later); A/B + preference capture. **Image backends (per `.env`):** free = **AI-Studio browser (Nano Banana)** — NOTE **ChatGPT browser is Cloudflare-blocked for automation, do not rely on it**; paid/robust = **OpenAI `gpt-image-1`** (hero quality) and/or Gemini image API (billing). Route by `IMAGE_BACKEND_PRIMARY` / `IMAGE_BACKEND_HERO`; align the `ImageBackend` enum (`aistudio_browser`, `gpt_image`, `gemini_image`) as you wire each. **GATE:** an end-to-end creative — brief+pillar+topic → AI copy (human-approved) → AI imagery → composited PNG passing the brand-QA code checks (contrast, safe-zones, dims, logo) — on a real client, human approves with ≤1 nudge; pytest green.
- **P3** — ops + approval. Wire dashboard→API (auth); Kanban board + calendar + at-risk worker; in-portal + magic-link approval; Drive auto-archive on approval; brief versioning (new frozen version row); task/notification system. **GATE:** a job runs intake→generate→internal-review→client-approve→auto-archive with a timestamped audit trail and ZERO manual Drive upload; at-risk fires when the buffer is breached; pytest green.
- **P4** — learning loop. Preference capture → per-client profile → heuristic taste-ranker; human-gated promotion. **GATE:** picks/edits/rejections recorded as signals; a client with ≥20 signals gets re-ranked variants; client corrections never auto-promote to the shared golden set; pytest green.
- **P5** — storefront + billing. Claim-form intake → prospect client + cold-bootstrap; Stripe trial→paid gating access. **GATE:** a claim submission creates a client + starts a brief; a Stripe **test-mode** checkout activates a sub that gates tenant access; pytest green.

## Human gates — STOP and ask the operator
- **Credentials/secrets** (set in `.env` from `.env.example`, never commit): Google AI Studio key (free — TEXT/copy only), a logged-in ChatGPT/AI-Studio **browser profile dir** (IMAGES via PRO subs — operator logs in once, automation reuses cookies), Supabase project + keys (P3 auth), Google service account + Drive folder (P3 archive), Stripe **test** keys (P5 billing).
- **External setup:** Supabase project, Google service account, Stripe account, (later) Meta WhatsApp Business verification.
- **Design references** for any NEW UI beyond the locked tokens (`web/design/tokens.css`).
- **Destructive / production / deploy** actions, and any commit/push (ask first).

## Model & pacing (for a long, uninterrupted run)
- **Model:** Fable 5 at **xhigh** effort for the main loop — strongest reasoning that's still sustainable over a marathon; **max** burns limits fastest for little gain on routine build work (reserve max for a single genuinely-hard bounded task via an agent). Delegate heavy build chunks to **subagents** (they hold their own context), keeping the main loop lean.
- **Resumable by design:** each phase ends at a passed GATE + a quick inline `HANDOFF.md` update, so if the run is cut off (limits/context), the next session resumes cleanly from the last green gate — nothing is lost. This is why "cut off midway" is not fatal.
- **Do NOT stop the run for handoffs.** Keeping `HANDOFF.md` current is a **fast inline file edit** as you pass each gate — it is NOT a reason to pause, and it is NOT `/handoff` (that skill commits + could interrupt). The ONLY things that pause the run are the genuine **human gates** (missing credentials, external service setup, a design reference, deploy/commit). Everything else runs continuously.
- **Context hygiene:** fan heavy work to subagents (they hold their own context) so the main thread stays lean — this prevents mid-run context blowup more than the model choice does.
- **`/loop`:** start the build with `/loop` so it self-resumes across long periods (there is no `/goal` command — the phase acceptance GATES above ARE the goals the loop checks itself against).

## Skills to attach
- `grill-me` — only if a phase needs a decision not already in the plan.
- `frontend-design` — any UI work (reference = `web/design/tokens.css` + the published artifact).
- `artifact-design` — any visual deliverable/report.
- `pattern-reviewer` / `/code-review` — run on each phase's code before its gate.
- `/handoff` — at session end.

## Agents to attach (parallelize via the Agent tool)
- `general-purpose` — independent build chunks (backend vs frontend), bounded research.
- `software-architect` — phase design decisions.
- `code-reviewer` + `security-reviewer` — review each phase (mandatory for auth, client input, payments).
- `debugger` — when a gate fails.
- `Explore` — codebase mapping.

## Loop mechanics
1. Work phases in order (start P2-remaining). Within a phase, fan independent work to agents, integrate, run the gate, iterate until green.
2. After each gate passes: update `HANDOFF.md` + `SESSION_LOG.md`; commit phase-tagged **only if the operator has OK'd commits**.
3. Stop when all gates pass OR a human gate is hit. Use `/loop` for autonomous pacing if desired.
4. Trust-but-verify agent output — re-run the gate yourself; security-review anything touching auth/client-input/payments.

---

## THE LOOP PROMPT (paste into the fresh session)

Start it with `/loop` so it self-paces:

> /loop Build Mimik Suite autonomously, phase by phase, until all acceptance gates pass or you need me. First read `~/.claude/plans/hi-i-want-to-sunny-fox.md`, and in `/Users/atheeque/workspace/Mimik_Suite`: `CLAUDE.md`, `HANDOFF.md`, `FRESH_SESSION_KICKOFF.md`, `docs/DECISIONS.md`. Verify current state: `docker compose up -d` then `uv run --no-sync pytest` should show 56 green. Then for each phase from **P2-remaining** onward, build it (fan independent work out to subagents to keep this thread lean), run `code-reviewer`/`security-reviewer` before the gate, verify against that phase's **acceptance gate**, and advance only when green. After each gate: **quickly edit `HANDOFF.md` + `SESSION_LOG.md` inline and keep going — do NOT stop the run for a handoff ritual and do NOT invoke `/handoff`** (only the human gates pause you). Honor every constraint (no paid APIs; `uv run --no-sync`; tenant authZ at the data layer; secrets only in `.env`; managed auth never self-rolled). **Copy runs on the free Gemini API; IMAGES run via browser automation of my PRO ChatGPT/AI-Studio — the free API does not do free images.** **Pause and ask me only at the human gates** (credentials, external service setup, design references, deploy/commit). Begin with P2-remaining: the manifest→`TemplateContext` assembly, then the copy step (needs `GEMINI_API_KEY`), then the browser image adapter (needs the logged-in browser profile dir) — tell me exactly which `.env` values you need before each and I'll have them ready.
