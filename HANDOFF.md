# HANDOFF — Mimik Suite

> Latest entry on top. Read this before doing anything. Ground truth for state.

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
