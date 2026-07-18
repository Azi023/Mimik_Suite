# Decision Log (ADR-style)

The load-bearing decisions and *why*. Distilled — only decisions that shape the build.
Master plan (full detail + open items): `~/.claude/plans/hi-i-want-to-sunny-fox.md`.

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Multi-tenant SaaS, **done-for-you** service (client requests+approves, Mimik runs the engine), sold as the $750/mo unlimited-design sub | Sidesteps funded self-serve tools (Pencil/Canva); the human gate IS the product |
| 2 | **Orchestrator + satellites**, not a monolith — engines (ProofKit, mimik-engine) stay their own repos/CLIs and are *called* | Reuse without rewrite; confidential Sales data never enters the client product |
| 3 | Glue = `mimik-contracts` (Pydantic schemas); knowledge = `mimik-knowledge` (prompts/golden/rubrics/evals) | Schema-first wire contract; tuning captured durably, not lost in chat |
| 4 | Creative engine = **hybrid**: AI imagery + code-composited text/logo/hex (Playwright) | Pure-gen mangles text >~200 chars, can't place logos/exact hex; also needed for editability |
| 5 | **5-layer non-destructive checkpoint stack** (L1 base → L5 finish); designer checks out at any layer; deep edits in Figma; no custom canvas editor | "Cut the designer's work"; Canva's editor is the wrong fight |
| 6 | **Layout-first** from a selectable clean-template library; **conditional** scrim (contrast-driven); clutter critic | Guarantees legible text + "don't overcomplicate"; anti-AI-slop |
| 7 | **Copy = L0**: AI draft (free Gemini) → human approve → golden set | Automates the painful part; human gate keeps it from sounding AI |
| 8 | **Images = browser automation of PRO ChatGPT/AI-Studio**; **copy = free Gemini API** | Free API image gen isn't reliably free; browser uses existing PRO subs, no tokens |
| 9 | Imagery behind a **swappable adapter**; free/sub now → paid tiers → paid APIs as a config swap | Never bet the architecture on the sourcing method; clean upgrade path |
| 10 | **Spend-minimizing pipeline**: A/B base only, fan-out re-composites the *cached* base (~0 extra gens), generate-after-approval, retry×1→other-backend→L2 human | Image gen is the only bottleneck; makes free tiers viable |
| 11 | **Per-brand Asset Library** (logos/fonts/imagery), client+team fed, Drive-backed, approved-version rendered; **font licensing tracked** (OFL fallback) | Brand-exact + always legal; team can replace weak client assets |
| 12 | **Reference = style descriptor + fit-critic + human-approve**, never reproduced | Inspiration not copying; legally safe; explains its choice |
| 13 | **Cold/trial-client bootstrap** from website+socials (browser) | New prospects (3-free-designs) have no assets yet — auto-dig |
| 14 | **Compliance = calibrated critic**, human final, L2 fallback on AI refusal | Blocks real regulated claims but NEVER blocks honest marketing |
| 15 | **Assisted autonomy**: auto-draft → human nudge → correction promoted to prompts/golden/rubric; evals gate regression | Interactive quality control, now recorded; dial autonomy up per task |
| 16 | **Content pillars** (presets + custom) tag jobs in the planning phase | Balanced calendar; client-driven themes |
| 17 | **Kanban ops board**; status transitions fire procedures (→Approved auto-uploads to Drive) | Visual tracking for ops; fixes the skipped-Drive-upload pain |
| 18 | **Content calendar + SLA**: approved ≥N days before publish; worker flags at-risk early | Kills the "night before" fire drill |
| 19 | **Brief freeze = new immutable version row**; post-signoff change = new request | Versioned + non-destructive; scope-creep fix |
| 20 | **Approval = in-portal + magic-link** (same action, audit-logged); WhatsApp Business API later | Durable (nothing missed) + frictionless; defer paid WhatsApp API |
| 21 | **Managed standards-compliant auth** (Supabase/Clerk), never self-rolled; passwordless clients; RBAC+MFA+audit; **admin panel** | International standard > friction; passwordless is a standard, so both |
| 22 | **Tenant authZ at the DATA layer**; client = untrusted (injection + **SSRF** guards) | IDOR is the #1 risk; SSRF closed on the URL fetcher |
| 23 | Stack: Python 3.12+/uv, FastAPI + async SQLAlchemy + Alembic + Postgres + Redis + queue; Next.js 15; Playwright | Matches the existing Python AI stack; one language for the AI backend |
| 24 | Design = **Studio White, brand-tuned** (royal blue #2E5BFF primary, lime #C6F135 pop), light + dark | User pick; grounded in mimikcreations.com brand |
| 25 | Infra: Hetzner VPS + Docker; Supabase auth; object storage for assets; GitHub Actions CI | Known infra; managed where security-critical |
