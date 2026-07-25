# Autonomous Operation — codex/agy improving Mimik Suite from the VPS

> How the operator's live codex/agy terminal (at `/root/mimik-src/` on the VPS) runs the
> continuous-improvement loop **autonomously, with full context, skip-permissions, and a
> 120K-token session ceiling that hands off to a fresh session cleanly.**

## The operating model the operator asked for
1. **Full context, always.** Every agent session reads, in order: this repo's `AGENTS.md` (at
   `/root/mimik-src/`), `Mimik_Suite/HANDOFF.md` (top entry), `Mimik_Suite/CLAUDE.md`,
   `Mimik_Suite/docs/PRODUCTION_ROADMAP.md`, `Mimik_Suite/docs/AUTONOMOUS_OPERATION.md` (this
   file). All three repos are cloned side-by-side so path deps resolve.
2. **Skip-permissions (no yes/yes prompts).** Run agents in auto-approve mode:
   - codex: `codex exec --full-auto "<task>"` (never stops to ask; pre-answer decisions in the prompt).
   - agy: run in its auto/full-access mode (the operator's session is already logged in).
3. **120K-token session ceiling → fresh session + handoff.** When a session's context approaches
   ~120K tokens (the smart-zone edge), STOP taking new work, WRITE a handoff (append a dated entry to
   `HANDOFF.md` + commit + push), then start a FRESH session. The fresh session rehydrates from the
   docs above — nothing is lost. Never let a session drift into the 150K+ dumb zone.
4. **Git is the two-way bus (CI/CD).** Edit in the clone → commit (phase-tagged, explicit paths) →
   `git push origin main` → CI builds images (~4min) → deploy on the VPS
   (`cd /root/mimik-suite && docker compose -p mimiksuite pull && … up -d`). A `*/3 * * * *` cron
   (`/root/mimik-src/sync-pull.sh`) ff-only-pulls main into all clones (skips dirty repos). Prod runs
   immutable images — never edit inside running containers.

## Guardrails (non-negotiable, from CLAUDE.md)
- **Tenant auth at the DATA layer** on every query/route; keep the IDOR negative test green.
- **Non-destructive**: soft-delete (`deleted_at`), versioned edits; never hard-delete or drop data.
- **Secrets live ONLY in `/root/mimik-suite/.env`** — never in the source clone, logs, or commits.
- **Never `git commit` without explicit paths** while multiple agents run (staged `git mv` from
  another lane gets swept in → broken build). Commit per-lane by path.
- **Verify before deploy**: `uv run pytest -q` (non-browser) + `cd web && npm run lint && npm run
  build` must be green. `next build` fails on any lint error → gates the deploy.
- Schema-first (mimik-contracts), no `any` in TS, no `shell=True` with untrusted input.

## The improvement loop (what to work on)
Pull the next item from `docs/PRODUCTION_ROADMAP.md`, build it as ONE scoped lane, verify, deploy,
tick it off, repeat. Prefer disjoint lanes if parallelising; serialise anything touching the same files.

## Optional future: in-APP browser terminal (operator's "terminal on the website")
The safe version is THIS (SSH + tmux + skip-permission agents). An in-browser terminal on the product
is possible but is a remote-code-execution surface on prod — build it ONLY as a separate, hardened
micro-service: super_admin-gated + IP allowlist + TLS + full audit log + NOT inside the web container.
Treat as its own reviewed project; the SSH+tmux flow already delivers the capability today.
