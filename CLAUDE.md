# Mimik Suite — Project Brain

> Read this first. Then read `HANDOFF.md` (top entry) before touching anything.
> Full product plan: `~/.claude/plans/hi-i-want-to-sunny-fox.md` (living doc).

## What this is

A multi-tenant, **done-for-you** creative-agency SaaS. A client is onboarded → their
**brand brief auto-drafts** → the **hybrid 5-layer creative engine** generates creatives
(AI imagery + code-composited text) → an **auto brand-QA critic** clears obvious errors →
the team reviews on an ops board / calendar → the client approves/edits/comments in a
bounded portal (WhatsApp + magic-link) → on approval it **auto-archives to Drive**.
It *learns*: every pick/edit/rejection feeds a per-client preference profile, always above
a Mimik house-quality floor. Operating model = **assisted autonomy (guided + recorded)**.

Positioning: own the whole loop, human-gated. Sell the *service*, not the tool. (Pencil/Canva
own the self-serve tool; we don't fight them there.)

## Architecture (orchestrator + satellites, NOT a monolith)

- `Mimik_Suite/` (this repo) — the product: `api/` (FastAPI), `web/` (Next.js), `creative/` (engine).
- `mimik-contracts/` (sibling pkg) — Pydantic schemas = the shared vocabulary. Path dep.
- `mimik-knowledge/` (sibling pkg) — prompt library, golden set, rubrics, evals, learning-loop.
- Engines stay their OWN repos + CLIs and are *called*, never absorbed:
  - `Mimik_Proofkit/` — Playwright capture/qualify/pack/figma. Reuse, don't rebuild.
  - `mimik-engine/` — video pipeline. Plugs in later.
  - `Mimik_Sales/` — acquisition. **CONFIDENTIAL (lead PII + keys). NEVER import into this product.**

## Locked constraints (absolute — do not violate)

1. **Schema-first.** Every cross-boundary payload is a `mimik-contracts` Pydantic model. No ad-hoc dicts on the wire.
2. **Tenant authЗ at the DATA layer.** Every query is filtered by `tenant_id`. Never trust the route alone. IDOR is the #1 risk — there is a negative test guarding it; keep it green.
3. **Client = untrusted principal.** Client freeform text is *data, never instructions*. It only ever fills a constrained slot; it never merges into a system prompt. Client-facing generation runs in a low-privilege context (no tools, no cross-tenant visibility).
4. **Never touch secrets.** `.env*`, `*.key`, `*.pem`, `credentials*` stay out of git, stdout, and chat. Config via env only.
5. **No `shell=True` with untrusted input** (Python). No `any` in TypeScript; explicit return types on exported functions.
6. **Test stub on day 1.** Every new module gets a `tests/test_<module>.py`, even if `pass`.
7. **No paid APIs yet.** Build phase runs on subscriptions / free tiers. Imagery via a swappable adapter so "sub now → API later" is a config change. `codex`/`agy` CLIs are code-only — they cannot generate images.
8. **Non-destructive.** Briefs and creatives are versioned; edits create new versions; nothing is destroyed. Every action is audited (actor + timestamp).
9. **Frontend-design rule.** Do NOT style any UI without a concrete visual reference in hand (URL/screenshot/Figma). Scaffold structure only until then. **Design system is now LOCKED** (`docs/DESIGN_REFERENCES.md`): shadcn/ui mono admin ("Studio Admin" north-star) — adopt shadcn/ui in `web/`. **Frontend builds run on FABLE** (Opus writes the spec from references → a Fable-model agent + frontend-design skill builds it), not Opus. Preserve Supabase auth wiring + kill the mock-fallback (real empty states) as each screen lands.
10. **Dogfood before "product".** Every phase is validated on a real Mimik/Jasmine client before it's called done.

## Conventions

- **Commits:** phase-tagged Conventional Commits — `feat(P0-SCAFFOLD): ...`, `feat(P1-BRIEF): ...`, `fix: ...`.
- **Python:** `>=3.12`, `uv` for envs/deps (dev venv resolved to 3.13; both are Playwright-compatible — avoid 3.14 until Playwright supports it). `ruff` + `pytest`.
- **Local services:** `docker compose up -d` runs Postgres on host **:5434** and Redis on **:6381** (5432/6379 are taken by other local instances on this machine). Config defaults + `.env.example` match.
- **Review:** 7-axis `patterns.md` scan on every diff before commit.
- **Handoff:** update `HANDOFF.md` (top entry) at end of session; `SESSION_LOG.md` is the audit trail.

## Data model spine

`Tenant(agency) → Client → Brand(brief, tokens, logo) → Brief(version, status, frozen_at)
→ Job(format, publish_date, assignee, status, sla) → CreativeDoc(manifest) → Layer(L1..L5, recipe)
→ Approval(actor, action, ts) → Delivery(drive_path) → Task(type, status) → PreferenceProfile(client-scoped)`
