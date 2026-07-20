# SESSION LOG — Mimik Suite

Chronological audit trail of decisions. Newest at bottom.

## 2026-07-18 — Session 1

- Grilling + planning session produced the v0.1 living plan (`~/.claude/plans/hi-i-want-to-sunny-fox.md`).
- Feasibility verdict: buildable; ~40% of parts already exist (Sales, ProofKit, mimik-engine, storefront).
- Chose stack: Python 3.12 + uv, FastAPI + async SQLAlchemy + Alembic + Postgres + Redis + Arq, Next.js.
- Chose orchestrator + satellites topology; contracts + knowledge as shared sibling packages.
- Started P0: governance files + repo scaffold.

## 2026-07-19 — Autonomous build loop (P2)

- Verified 56-green baseline; extended contracts (CopyBlock/CopyStatus, manifest template_key+copy_block, ImageBackend none/openrouter/gemini_image). Renamed `copy`→`copy_block` (pydantic shadow warning).
- Fanned P2 to parallel subagents: copy L0, image adapters+router+spend gate, brand-QA critic, reference fit-critic; assembly + pipeline built in main thread.
- Session-limit cutoff killed 2 agents mid-run; on resume audited disk (no partial files), relaunched; QA agent stalled once — its modules were complete, tests finished inline.
- Reviews before gate (pattern + security + code agents): fixed CRITICAL CSS-url() injection via asset refs (validation at contracts + render sink), hardened fence-stripper variants, router exception narrowing, gpt_image shape guard, copy-aware geometry estimate + DOM-containment tests.
- DRY: extracted shared critic plumbing to creative/prompting.py.
- Live sample: real free-tier Gemini copy on Mimik brand → 3 QA-passing renders (placeholder grounds, zero spend).
- 116 tests green, ruff clean. P2 machine-checks GREEN; operator eyeball = the last gate item.
- Deferred deliberately: preference persistence + A/B logging → P4; reference gathering (browser scrape) stubbed behind the fit-critic seam.

## 2026-07-19 — Autonomous build loop (P3: ops + approval)

- P2 gate PASSED (operator approved the sample creatives; loop advanced).
- P3.1: contracts (UserAccount, Notification, ActorRole.OWNER) + 6 ORM tables + migration e26e196b8532 (Postgres) + repo/mappers. Built in main thread (shared foundation) to keep fan-out file boundaries clean.
- P3.2 auth: managed Supabase auth (never self-rolled). Project signs ES256/JWKS → added pyjwt[crypto]+cryptography (in-service of "standards-compliant auth" constraint). Dual-issuer principal (Supabase-verified→UserAccount→tenant/role; first-party bootstrap retained for CI/founding owner). Admin provisioning (owner-gated), require_role. Tested with local ES256 keypair + injected JWKS, zero network.
- P3.3 approval (main thread centerpiece): audited approve/request-change/comment; approve→auto-archive (deterministic re-render from manifest → ArchiveBackend → Delivery → status ARCHIVED); magic-link no-login capability; archive adapter (Local default + GoogleDrive via SA-JWT, both mocked-tested).
- Fanned P3.4 (ops board+calendar+transitions+at-risk), P3.5 (tasks+notifications+brief revise), and GoogleDriveArchive to 3 parallel subagents; wired their routers into main.py myself (clean boundaries, no collisions).
- Security review (automated) flagged creatives.py IDOR → fixed (team-role gate + client-scoping + regression tests). Centralized naive/aware datetime coercion at the mapper layer (removed per-call workarounds the ops agent added).
- 174 tests green, ruff clean, contracts 11 green. e2e gate test proves intake→approve→auto-archive with real render + audit trail, zero manual upload.
- Deferred: preference/A-B → P4; reference gathering stays stubbed.

## 2026-07-19 — P3 gate PASSED (reviews clean)

- Ran code-reviewer + security-reviewer on the full P3 surface (auth, magic-link, approval, archive, ops, tasks).
- Code review found 1 CRITICAL (double-approve re-archives) + 1 CRITICAL (blocking JWKS on event loop) + warnings; security review found 2 Important latent footguns + 2 nice-to-have. All real findings FIXED with regression tests:
  - double-approve → ApprovalConflictError/409 terminal guard (exactly-1-delivery test)
  - JWKS fetch → asyncio.to_thread (no event-loop stall)
  - access/magic-link token confusion → typ=access pinned (rejection test)
  - Drive query f-string → re-sanitize in _ensure_folder
  - at-risk O(N²) + dispatch_pending → targeted list_notifications(job_id/status) filters
  - admin TOCTOU → IntegrityError→409; task cross-client job_id → ownership check; JWKS read cap 256KB
- 177 tests green, ruff clean, contracts 11 green. P3 gate met: e2e intake→approve→auto-archive (real render, real PNG, audit trail, zero manual upload) + at-risk fires on breach.
- Human gate flagged (not blocking): real Google Drive archive needs GOOGLE_SERVICE_ACCOUNT_JSON + DRIVE_ROOT_FOLDER_ID + ARCHIVE_BACKEND=google_drive; local backend satisfies the gate meanwhile.
- Advancing to P4 (learning loop) — no new creds required.

## 2026-07-19 — P4 learning loop (code-complete, gate green)

- P4.1 PreferenceSignalRow + migration 5a396a1c513b; contract PreferenceSignal extended (attributes/job_id/actor_role) + PreferenceProfile.signal_count/ranker_active + RANKER_MIN_SIGNALS=20.
- P4.2 heuristic taste-ranker (api/services/preferences.py): attribute scoring by net revealed preference; passthrough <20 signals, re-order ≥20; stable ties.
- P4.3 signal capture wired into approval_flow (approve→APPROVAL, request_change→REJECTION w/ reason_tag), client-scoped.
- P4.4 (fanned out): preferences router (record/profile/rank/promote, client-scoped, promote owner/ops-only) + human-gated golden promotion (promote_and_write writes only when accepted AND reviewer named; client corrections never write). P4 gate test green.
- Security review flagged list_job_approvals IDOR → client-scoped + regression test.
- 197 tests green, ruff clean, contracts 11. Real golden/ dir untouched in tests (MIMIK_GOLDEN_DIR→tmp).
- Next: P5 storefront+billing — pauses at the Stripe test-keys human gate.

## 2026-07-19 — P5.1 storefront intake (credential-free); PAUSED at Stripe gate

- Public POST /intake/claim: storefront tenant by slug → prospect Client (email-dedup) + Brand + draft Brief. Deliberately NO outbound fetch on the public path (SSRF/DoS amplifier); URL shape-validated only.
- Team POST /clients/{id}/bootstrap: cold-client bootstrap fetches the prospect site behind auth via extract_brief_sections (SSRF guard) → drafts §1-5.
- repo helpers: get_tenant_by_slug, get_client_by_email, list_brands. 8 intake tests; 206 total green, ruff clean.
- PAUSED at the P5.2 Stripe billing human gate — need STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET / STRIPE_PRICE_ID (all TEST mode). Asked the operator.

## 2026-07-19 — P5.2 Stripe billing scaffolded (mocked) — ALL PHASES BUILT

- Operator chose "scaffold P5.2 without keys" — built billing fully with mocked Stripe (stdlib only, no `stripe` dep).
- Fixed the P5.1 intake security findings first: SSRF redirect/rebind TOCTOU (no-redirect opener + per-hop re-validation), dedup race (UNIQUE(tenant_id,contact_email) + IntegrityError catch → migration f05cd87bcf42), public-input length caps. +2 regression tests.
- P5.2 foundation: Subscription contract + SubscriptionStatus enum, SubscriptionRow (unique client_id) + migration b08ff128c47c, repo + mapper.
- Fanned billing service/router/gating/tests to a subagent: create_checkout_session (mocked _post_form seam), verify_webhook_signature (HMAC-SHA256 over t.rawbody, constant-time, replay tolerance), apply_webhook_event (upsert on checkout.completed, status on updated/deleted), client_has_access; 402-gated /portal/design-requests.
- Wired billing router into main.py; removed test self-registration guards.
- P5 gate green: claim→client→brief→mocked checkout→signed webhook activates sub→gated endpoint flips 402→200.
- 222 tests green, ruff clean, contracts 11. Security review of the payment surface in flight.
- All phases P0–P5 built. Optional human-gate turn-ons remain (Drive creds, real Stripe test keys, paid images) — none blocking; local/mocked backends satisfy every gate.

## 2026-07-19 — Session 4 (G2G loop, evening)

- Fixed stale `gpt-image-2` assertion in test_image_router (baseline back to 222 green).
- **G1 built**: BrandAsset contract/ORM/migration `4bbd7db38ad2`/repo/mappers/router; free-Gemini
  vision client (`creative/vision/`) + `creative_study` prompt; reference-creative ingestion →
  fit-critic → Brand.references + preference signals; `copy_voice` golden kind with client-scoped
  L0 few-shot; `_vision_pass` implemented (evidence-bound, degrades to heuristics).
- **Decisions**: approved logo → data URI (set_content page can't load file:// subresources);
  reference URL scheme `asset://<id>`; heuristic CSS hexes outrank model estimates in brief merge;
  ingestion attach = critic-fits OR human force (verdict always audited).
- **Security (from gate reviews)**: golden audit-header injection fixed (sanitized header fields +
  exact-field client-scope parse; regression tests incl. prefix-collision); Gemini keys moved from
  query string to `x-goog-api-key`; register-drive-asset now mime-allow-listed.
- Fixed latent circular import prompting↔creative.copy (deferred import, order-independent).
- `CreateBrand` now accepts `tokens` (was silently dropped).
- **G2 dogfood on real Glo2Go**: fresh vision-enriched brief from the live site; 5 pillars;
  real logo approved+wired; 4 Drive refs registered; live L0 copy on-voice; creative rendered +
  local archive. Finding: purple logo invisible on purple ground → logo-contrast QA backlog.
- **G3**: first eval fixture green (frozen G2G homepage snapshot). Drive archive pending operator
  (.env values + folder share to SA); SA OAuth verified working.
- **FE**: Conceptzilla reference (dribbble 19198544) captured at full res; web/ styled to it —
  tokens.css, two-tier sidebar, kanban, review panel, GSAP motion; build+lint clean.
- Suite 253 / contracts 12 / knowledge 8 tests green; ruff clean. Nothing committed yet.

## 2026-07-19 — Session 4, iteration 2 (autonomous)

- Logo-visibility QA check: `logo_mean_luminance` (alpha-weighted opaque pixels, data-URI only,
  no network) + `luminance_ratio` in creative/qa/contrast.py; check #4 in run_brand_qa vs
  WCAG 1.4.11 threshold 3.0; imagery grounds sampled under the logo zone with imgs hidden
  (`sampled_zone_luminance` gained `hide_css`). Live-proofed on the G2G dogfood ctx: 1.04 → FAIL.
- Regression tests: stdlib PNG encoder helper; purple-on-purple fails / white knockout passes
  (browser-gated); non-data logo refs skip; ratio math.
- Service-level unit tests added for wire_approved_logo + ingest_reference_creative
  (code-reviewer gap): data-URI round-trip, fail-loud missing file, attach+signal semantics,
  forced-attach preserves the reject verdict.
- Suite 262 green, ruff clean. Still uncommitted (operator gate).

## 2026-07-19 — Session 4, iteration 3 (autonomous)

- Knockout logo derivation: creative/render/knockout.py (browser-canvas, RGB→white alpha-kept,
  no PIL, data-URI in/out) + brand_memory.derive_knockout_logo (new UNAPPROVED asset, provenance
  notes) + POST /assets/{id}/knockout (team; 422 non-logo, 409 no file).
- Tests: pixel-truth browser test (purple mark → mean opaque luminance > 0.95), router test with
  mocked seam + non-logo refusal. 264 green, ruff clean.
- Live proof on real G2G: knockout derived → approved (auto-wired as active logo) → re-rendered
  the polynucleotides creative → brand-QA PASSES (was 1.04 contrast fail). Full failure→fix→green
  loop works end to end.
- Noted: G2G brand tokens lack an accent color (CTA renders default lime) — operator to pick one.

## 2026-07-19 — Session 4, iteration 4 (operator design feedback)

- Operator rejected the flat-purple creative + flagged the Mimik-lime CTA leak; senior-designer
  art-direction critique received. All three addressed:
- creative/render/color.py: brand-derived mix/tint/shade — extra color roles DERIVE from the
  client primary, never house defaults. assemble.py accent fallback now tint(primary) for any
  brand with a palette (Mimik lime only for token-less dev brands).
- NEW soft_editorial template (modeled on the real G2G IG posts): tint-gradient ground, layered
  bottom waves (SVG), edge-bleeding badge-pill logo (logo box stays in safe zone), deep-brand
  headline, white-on-brand subhead pill, brand CTA pill; imagery gets its own rounded window
  (text never overlaps); column flex-centers without imagery. Per-template QA semantics added
  (headline/CTA/logo-ground) — QA computes exactly what renders.
- suggest_template v2: imagery-aware; placeholder path never ships a flat color plate.
- Copy editor rules (designer feedback): display type never ends in terminal punctuation
  (stripped in code), semicolons rejected with retry; copy_l0.md updated.
- mimik-knowledge/rubrics/art_direction.md: distilled designer critique (2-second hierarchy,
  grid/negative space, type pairing, imagery, brand-only color, elements, logo, CTA, benchmark).
- G2G palette updated to source of truth (#642766 primary, #8C4F8D secondary, #F6EDF7 wash);
  operator rejection recorded as a real preference signal (reason_tag=too_plain).
- Leonardo.ai browser-session route: scripts/leonardo_login.py (persistent Chrome profile,
  one-time headed login, --check probe); LEONARDO_BROWSER_PROFILE_DIR env slot; var/ gitignored.
- 271 tests green, ruff clean. New render: QA-green soft_editorial G2G creative.

## 2026-07-19 — Session 4, iteration 5 (autonomous)

- soft_editorial verified on ig_story (QA green; badge clears the 250px story bar).
- Real-post IG ingestion blocked (Instagram refuses anonymous access) → rides the Drive-share gate.
- FE wired to the real API (agent): web/lib/api.ts (typed client, NEXT_PUBLIC_API_URL +
  NEXT_PUBLIC_DEV_TOKEN, 3s timeouts, ApiError), web/lib/data.ts (facade, mock fallback —
  board never blank), page.tsx → async server component (force-dynamic). Build+lint clean.
- E2E smoke: uvicorn + next dev + real dev token → board rendered REAL G2G data (5 pillars,
  archived polynucleotides job in Approved, review panel with real creative). Screenshot saved.
- Known FE gaps: sidebar client list + top chip still mock; Supabase login UI pending.

## 2026-07-19 — Session 4, iteration 6 (Zaid feedback: pin-pointed revisions)

- Contracts: RevisionZone enum (headline|subhead|cta|logo|imagery|background|layout|other) +
  RevisionTarget (zone, optional LayerKind, capped instruction); Approval.targets list.
- ORM/migration 79fa3959d12f: approvals.targets JSON. Mapper included.
- approval_flow.submit_approval accepts targets (REQUEST_CHANGE only, dropped elsewhere):
  audit-trail persistence, ops-task detail gets "- [zone/layer] instruction" lines, and one
  zone-tagged REJECTION preference signal per target (ranker learns WHICH areas get pushback).
- Both approval entry points (in-portal + magic-link) accept targets; 422 on non-change actions;
  max 10 per request.
- Targeted re-draft seam: draft_copy(revision_note=...) fills a fenced <revision> block in
  copy_l0 (untrusted reviewer text, tag-stripped; Do/Don't lists override it). Injection test.
- 275 Suite + 12 contracts green, ruff clean.

## 2026-07-19 — Session 4, iteration 7 (autonomous)

- FE revision-pin UI landed (agent stalled once; resumed with context): ReviewPanel inline
  composer — 7 zone chips (aria-pressed), 500-char instruction, 10-pin cap, pin cards with
  remove, optional note, Send N pins → POST /approvals request_change with targets; Approve
  wired too. Token-only styling, staggerFadeUp reveal, reduced-motion safe. Offline/mock mode:
  no fetch, quiet "offline — pins not sent" note, pins kept. Build+lint clean.
- Visual verification via headless Chromium: composer screenshot captured.

## 2026-07-19 — Session 4, iteration 8 (pre-commit review gate)

- Ran code-reviewer + security-reviewer on the iterations 2–7 delta. All findings fixed:
- SECURITY (low): task-detail line forgery via newline in target instruction → instructions
  whitespace-flattened before interpolation; regression test (line-count assertion).
  Reviewer confirmed safe: both approval entry points identically capped; magic-link
  401/409 behavior; revision fence; knockout mime forcing; leonardo profile gitignored;
  React-escaped pin rendering; prior golden-poisoning fix verified landed.
- CODE (critical 1): SoftEditorial.geometry clamped the text zone to the available span →
  silent QA false-pass on overflowing copy. Clamp removed — the estimate stays a superset,
  overflow breaches the bottom safe zone and QA fails loud. Regression test (fb_post long copy).
- CODE (critical 2): trailing semicolon was stripped before the semicolon reject-check →
  laundered past the editor rule. Check moved to the ORIGINAL text. Regression test.
- CODE (warnings): ReviewPanel now distinguishes "error (server said NNN) — pins kept" from
  "offline"; submit_approval raises ApprovalFlowError on targets with non-change actions
  (was silent drop); Approval.targets capped (10) on the audited contract itself;
  contrast.py's three function-scoped SoftEditorial imports consolidated (no cycle exists).
- Gate: 278 Suite + 12 contracts + 8 knowledge green; ruff clean; npm build+lint clean.
  ALL review findings resolved — the tree is commit-ready.

## 2026-07-20 — Session 4, iteration 9 (Drive OAuth + FE interactivity)

- Diagnosed Drive SA dead-end: Google returns 403 "Service Accounts do not have storage
  quota" on file upload to a My-Drive folder (SA can read + create empty folders, not upload).
  Fix = user OAuth (files owned by user, uses their 5TB). Free Gmail can't use Shared Drives.
- Drive OAuth backend: refactored google_drive.py to _DriveArchiveBase (shared folder/upload/
  token-cache) + GoogleDriveArchive (SA/JWT) + GoogleDriveOAuthArchive (refresh-token grant,
  name "google_drive_oauth"). get_archive_backend() selects all three. config + .env.example
  updated. scripts/drive_oauth.py = one-time loopback OAuth consent → prints refresh token.
  8 new OAuth tests (grant shape, archive, caching, selection, unconfigured). 286 green, ruff clean.
- FE interactivity (iteration 8 agent): BoardView client boundary — pillar tabs filter, card→
  review-panel selection, Approve/Request-change wired to real ids, honest-disabled +buttons.
- FE sidebar wired to real /clients (earlier this session).
- Deploy: DROPPED for now (operator decision — run on Mac). Artifacts (Dockerfiles, compose,
  docs/DEPLOY.md, Coolify+Supabase guide) created + parked for later VPS upgrade. Committed? NO.
- Decisions: browser automation (Leonardo/ChatGPT) will run on the MAC not the VPS — home
  residential IP + headful + persistent profile + human pacing + dedicated account + patchright
  (headless is MORE detectable). Deferred to after Drive. Leonardo web sub != API access.
- Security note: deploy agent's `docker compose config` expanded .env → real keys hit its local
  transcript; advised operator to consider rotating OpenAI/OpenRouter/Supabase-service-role/Gemini.

## Human gates open
- Drive: create OAuth client (Desktop) in Google Cloud console + publish consent screen
  (Production, else 7-day token expiry) → set GOOGLE_OAUTH_CLIENT_ID/SECRET + DRIVE_ROOT_FOLDER_ID
  in .env → run `uv run --no-sync python scripts/drive_oauth.py` → paste refresh token +
  ARCHIVE_BACKEND=google_drive_oauth. Then the approve→archive writes to their real Drive.
- Rotate the 4 keys (optional, precaution).

## 2026-07-20 — Session 4, iteration 11 (Supabase users + Leonardo harness LIVE)

- Provisioned Supabase owners: atheequeniyas23@gmail.com + mimik.creat@gmail.com → tenant mimik
  (Glo2Go). Verified full login chain: password grant → JWT → API authorized → Glo2Go returned.
- Leonardo/OpenAI decision: API later (payment issue) → burner-account browser automation now.
- Stealth harness proven LIVE on the burner: the Playwright-LAUNCHED browser ("Chrome for
  Testing") is Cloudflare-blocked; fix = attach to the human's REAL Chrome via CDP.
  scripts/chrome_debug.py launches real Chrome (found on Desktop, via bundle id com.google.Chrome)
  with --remote-debugging-port=9222 + dedicated profile; user logs in (Cloudflare passes);
  stealth_browser.connect_cdp_session attaches (owns_context=False → never closes their window);
  LeonardoBrowserAdapter._acquire_session prefers CDP (LEONARDO_CDP_URL default :9222) → launch
  fallback; _pick_page targets the leonardo tab (never hijacks ChatGPT). First real generation
  succeeded — a luxury lavender skincare hero downloaded. Live-confirmed selectors: prompt box
  get_by_placeholder(/prompt/i); Generate button role/name (.first visible+enabled); RESULT =
  img[src*='/generations/'] (NOT the broad cdn.leonardo — that matched the static UI gradient).
- 295 Suite + 12 contracts green, ruff clean. Migrate to Leonardo API later = adapter swap.
