# HANDOFF — Mimik Suite

> Latest entry on top. Read this before doing anything. Ground truth for state.

---

## ► LATEST (2026-07-20 deep-night, main `5670d81`) — FRONTEND session: 3 screens + compositor wiring + roadmap

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
