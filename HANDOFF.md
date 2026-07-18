# HANDOFF — Mimik Suite

> Latest entry on top. Read this before doing anything. Ground truth for state.

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
