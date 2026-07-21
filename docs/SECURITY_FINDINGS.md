# Security findings & decisions — Mimik Suite

> Running log of security-relevant findings, fixes, and deliberate trade-offs, kept so they can be
> re-audited later. Newest on top. Every entry: **what / where / impact / status / how to re-verify.**
> This is the product's own security memory — treat it as ground truth for "was this ever a problem?".

Threat model anchors (from `CLAUDE.md` locked constraints):
- **#2 Tenant + client authZ at the DATA layer.** Every query filtered by `tenant_id`; a `client`
  principal is additionally confined to its own `client_id`. IDOR is the #1 risk.
- **#3 Client = untrusted principal.** Client freeform text is data, never instructions; the
  client-facing surface is low-privilege (no tools, no cross-tenant/cross-client visibility).

---

## F-001 — IDOR: client principal could read/enumerate other clients' jobs  ✅ FIXED

- **Where:** `api/routers/jobs.py` — `GET /jobs/{id}` (`get_job`) and `GET /jobs` (`list_jobs`).
- **Finding:** both endpoints filtered by `tenant_id` **only**. A `client`-role principal (the bounded
  portal) was NOT confined to its own `client_id`, unlike `tasks.py` / `creatives.py` which are. So a
  logged-in client of Agency X could read ANY job in Agency X's tenant by id (`GET /jobs/{other_id}`)
  and enumerate them all (`GET /jobs`) — leaking titles, formats, publish schedules, assignees, status.
- **Impact:** cross-**client** (within-tenant) metadata disclosure. Creative *content* was NOT exposed —
  `GET /jobs/{id}/creatives` was already client-confined (404s cross-client) — but the job metadata leak
  is still an IDOR (constraint #2). Cross-**tenant** was never possible (tenant filter held).
- **Root cause:** the client-principal confinement pattern (present in tasks/creatives/approvals) was
  simply missing on the jobs read routes.
- **Fix:** `a924a00` — `get_job` returns **404 (not 403)** when `principal.role == client` and the job's
  `client_id != principal.client_id` (a client can't even confirm another client's job exists);
  `list_jobs` forces `client_id = principal.client_id` for a client principal (403 if the account has no
  `client_id`). Mirrors `tasks.py`.
- **Re-verify:**
  ```
  uv run --no-sync pytest -q tests/test_jobs.py
  ```
  Two negative tests added: `test_client_principal_cannot_read_other_clients_job` (client A → 404 on
  client B's job) and `test_client_principal_list_filtered_to_own_client` (listing filtered to own
  client even when the query asks for another). Manual: provision a `client` account bound to client A,
  mint its Supabase token, `GET /jobs/{a_B_job_id}` → expect 404.
- **Discovered:** 2026-07-21, while scoping the client portal (would have shipped a leaky portal).

---

## F-002 — Same IDOR class across clients / brands / ops / briefs / pillars  ✅ FIXED (full sweep)

- **Where:** `clients.py` (`GET /clients`, `GET /clients/{id}`), `brands.py` (`GET /brands/{id}`),
  `ops.py` (`GET /ops/board`, `GET /ops/calendar`), `briefs.py` (`GET /briefs`, `GET /briefs/{id}`),
  `pillars.py` (`GET /pillars`).
- **Finding:** the **same missing client-principal confinement** as F-001, systemic across the read
  routes that weren't tasks/creatives/approvals. A `client`-role principal could:
  - `GET /clients` → **enumerate every other client in the agency incl. contact PII** (name, email,
    phone, instagram, notes) — the most sensitive of the set;
  - `GET /clients/{id}` / `GET /brands/{id}` / `GET /briefs/{id}` → read any client / brand / brief in
    the tenant by id (brief = brand strategy, voice, guardrails);
  - `GET /ops/board` / `GET /ops/calendar` / `GET /briefs` / `GET /pillars` → enumerate **all** tenant
    jobs / briefs / content pillars (cross-client).
- **Impact:** cross-**client** (within-tenant) disclosure of client PII, brand config, and job pipeline.
  Cross-tenant was never possible (tenant filter held). Note the frontend route-guard (H-001) does NOT
  mitigate this — a client could call these API routes directly; the fix is at the data layer per #2.
- **Fix:** commits `11d9e58` (clients/brands/ops) + `<pillars/briefs>` — client principals are now
  confined on every one of these routes: list endpoints force `client_id = principal.client_id`; get-by-id
  endpoints 404 on another client's id; `ops.calendar` filters the window to own jobs.
- **Re-verify:**
  ```
  uv run --no-sync pytest -q tests/test_jobs.py -k "client_principal_isolation"
  ```
  Two tests: clients-list/get + brands-get + board confined; briefs-get/list + pillars-list confined.
  Manual: as a client-A account, `GET /clients` returns exactly one row (client A); `GET /briefs` shows
  only A's briefs.
- **Discovered:** 2026-07-21, auditing the F-001 open-items — the leak was a repeated pattern, so a full
  sweep of every `Depends(get_principal)` GET route was run. **Now covered:** jobs (F-001), clients,
  brands, ops, briefs, pillars, tasks, creatives, approvals, preferences, billing (already confined);
  assets, invitations, admin, intake are role-gated (clients 403). Every client-data read route now
  either confines a client principal or 403s it.

---

## D-001 — Magic-link portal is a shareable capability (no login)  ⚠ BY DESIGN — audit the trade-off

- **Where:** `api/core/magic_link.py`, `POST /approvals/magic`, `POST /portal/session` (read).
- **Design:** a magic link is a **signed, expiring (default 72h) HMAC capability scoped to ONE job**,
  carrying `tenant_id` + `job_id` + `client_id`. It authorizes viewing + approving/commenting that single
  job with **no login** — the WhatsApp-shareable client path (like Frame.io / Filestage share links).
- **Trade-off / residual risk (intentional):** anyone who holds the link URL can view + approve that job.
  The token is a bearer-in-URL, so it can leak via referrer headers, browser history, chat forwards, or
  shoulder-surfing. Mitigations in place: `typ=magic_link` claim (can't be swapped for an access token),
  short TTL, single-job scope, no enumeration (each grant reaches exactly its own job — derived from the
  signed claims, never from client input). The READ endpoint (`POST /portal/session`) returns ONLY the
  granted job + its creatives/brand/audit — nothing else.
- **Re-verify / harden later (operator call):** consider (a) shorter TTL for higher-value clients, (b)
  one-time-use or approval-then-revoke, (c) binding to a client-confirmed email/OTP for the first open,
  (d) not putting the token in the query string on the API hop — we use `POST` bodies for both the read
  (`/portal/session`) and write (`/approvals/magic`) so it stays out of API access logs. The link URL
  itself still carries the token (unavoidable for a no-login link).
- **Status:** endpoints implemented; the residual "shareable link" risk is accepted as the feature's
  premise. Flagged here so it's a conscious decision, not an oversight.

---

## H-001 — Role-based route-gating on the frontend  ✅ ADDED (defense-in-depth)

- **Where:** internal Next.js routes (`/`, `/briefs`, `/members`, `/calendar`, `/tasks`, …) vs `/portal`.
- **Note:** the **DATA** is protected server-side (a client principal is confined at the API for jobs,
  creatives, tasks, approvals). Route-gating is **UX / defense-in-depth**, not the security boundary —
  even without it, a client hitting `/` would get their own scoped/empty data, not a leak.
- **Added:** `GET /me` (returns `{tenant_id, role, client_id}` for the verified principal) + a
  `requireInternal()` server guard that redirects a `client`-role session to `/portal`, and the portal
  pages redirect non-client internal roles to `/`. Keeps each audience on its own surface.
- **Re-verify:** sign in as a `client`-role account and hit `/` → expect redirect to `/portal`.

---

## F-003 — SSRF via `image_artifact` in POST /creatives  ✅ FIXED

- **Where:** `api/routers/creatives.py` — `CreateCreative.image_artifact`.
- **Finding:** `image_artifact` becomes a `Layer.artifact_ref` that the headless compositor interpolates
  into a CSS `url(...)` and **fetches server-side at render time**. It was validated for injection safety
  (`validate_asset_ref`) but NOT for destination — an **external URL** was accepted, so a team member (or
  anything that can reach this team-gated route) could point it at `http://169.254.169.254/…` (cloud
  metadata), internal services, or `file://` → classic SSRF / local-file read.
- **Impact:** SSRF. Mitigated by team-role gating (not client-reachable), but still a real internal
  surface. The copy/layout editor only ever resends the *existing* ref, so no user-facing exposure — the
  risk was the raw API accepting an arbitrary ref.
- **Fix:** `4d95011` — a `field_validator` on `image_artifact`: allow only `data:` URIs (inline, no fetch)
  and internal refs (no URI scheme, no leading `//`, no `..` traversal); **reject any scheme/host** → 422.
- **Re-verify:**
  ```
  uv run --no-sync pytest -q tests/test_approvals.py -k "image_artifact"
  ```
  Rejects `http(s)://`, `//host`, `file://`, `169.254.169.254`, `../..`; allows `data:` + internal refs.
- **Discovered:** 2026-07-21, logged as an R-001 open item, then fixed the same session.

---

## F-004 — Upload MIME check trusted the client Content-Type (disguised-file upload)  ✅ FIXED

- **Where:** `api/routers/assets.py` (`POST /brands/{id}/assets`) + `api/services/brand_memory.py`.
- **Finding:** the allowlist (png/jpeg/webp for images; ttf/otf/woff2 for fonts — already strict, no SVG,
  no scripts) was enforced against `file.content_type`, a **client-supplied, spoofable header**. A PHP /
  HTML / JS / SVG(-with-script) / PDF / ELF payload with `Content-Type: image/png` was stored as
  `<uuid>.png` with the true (malicious) bytes, and the DB recorded the fake mime.
- **Impact:** disguised-file upload. Exploitability was LOW in this architecture (files are stored under
  server-UUID paths in a NON-served dir and only read as image bytes by the compositor / base64-embedded as
  `data:` URIs — a renamed PHP never executes; SVG-in-CSS is script-inert), but it's a real gap and the
  operator asked for strict rules. **Path traversal was already NOT possible** (paths = `<uuid>.<validated-
  ext>` under `root/tenant_id/brand_id`; the client filename never touches the filesystem).
- **Fix:** `a1bfc27` — `store_asset_file` now SNIFFS the magic bytes (`sniff_mime`) and returns the TRUSTED
  mime; only real png/jpeg/webp/ttf/otf/woff2 pass (else 415), cross-kind is rejected (PNG-as-font), and the
  DB stores the sniffed mime. `safe_display_filename()` sanitizes the client filename to display-only
  metadata (strips path parts / control + quote/angle chars / leading dots; caps length).
- **Re-verify:** `uv run --no-sync pytest -q tests/test_brand_memory.py -k "disguised or cross_kind or safe_display"`
  — rejects PHP/SVG/PDF/GIF disguised as png, rejects cross-kind, sanitizes traversal/injection filenames.
- **Upload is team-only** (`require_role`); clients never reach it (constraint #3).

---

## F-005 — RBAC: client principals could create tenant resources  ✅ FIXED

- **Where:** `POST /clients`, `/brands`, `/jobs`, `/pillars`, `/briefs`, `/briefs/{id}/signoff`.
- **Finding:** these creates used bare `get_principal` (any authenticated principal). A bounded **client**-
  role principal (the review-only portal) could therefore **create tenant resources** — spin up new clients,
  or create brands/jobs **for other clients in the tenant**. The write-side analog of F-001/F-002; violates
  constraint #3 (the team runs the pipeline, the client only reviews).
- **Fix:** `c65f572` — all six now `require_role("owner","admin","ops","designer","team")` → a client
  principal gets 403 before the body is trusted. Clients keep only their bounded actions (approvals,
  own-client tasks/comments, portal reads). +1 test (client principal 403 on every create).
- **Re-verify:** `uv run --no-sync pytest -q tests/test_jobs.py -k "cannot_create_tenant_resources"`.

---

## A-001 — Full security audit sweep (2026-07-21) — what was checked

Beyond the fixes above, these surfaces were audited and found **already sound** (no change needed):
- **JWT / auth** (`api/core/supabase_auth.py`): algorithms are pinned per verification path; the HS256 path
  uses a SEPARATE configured secret (not the JWKS public key) → **RS/HS confusion not exploitable**; `none`
  and unknown algs rejected; **audience (`authenticated`) + issuer + exp enforced**. Role/tenant come from
  our `UserAccount`, never provider token metadata.
- **SSRF via URL fetch** (`api/services/brief_extraction.py`, reachable from `POST /briefs`, intake): a real
  egress guard (`_assert_public_http_url`) resolves the host and refuses loopback / RFC1918 / link-local
  (incl. `169.254.169.254` cloud metadata) / non-global, with a **per-redirect-hop re-check**. Dedicated
  `tests/test_ssrf_guard.py`. Outbound httpx (Stripe/WhatsApp/notifications) uses fixed hosts.
- **Path traversal**: asset storage uses server-UUID paths + validated extension (F-004); the archive path
  uses `safe_segment`. Client filenames are display-only.
- **CORS**: no permissive CORS middleware — the browser talks to the API only via same-origin Next server
  actions (httpOnly cookie server-side), so there is no cross-origin credentialed surface to abuse.
- **Tenant isolation**: every query filtered by `tenant_id` (`tests/test_tenant_isolation.py`); cross-tenant
  was never reachable in the IDOR findings.
- **Client-as-untrusted (constraint #3)**: client freeform text fills constrained contract slots (data),
  is never merged into a system prompt, and client-facing generation runs low-privilege.

---

## R-001 — Build-session security review (board/deliveries/billing/prefs/copy-editor)  ✅ REVIEWED

Reviewed every surface added in the 2026-07-21 build session. **No new vulnerabilities introduced.**
- **`GET /deliveries`** (new) — built client-confined from the start (joins JobRow for `client_id`;
  a client principal is forced to its own). Tested. Same F-002 discipline.
- **`GET /me`** (new) — returns the caller's OWN identity only; no id parameter, no enumeration.
- **`POST /portal/session`** (new) — magic-grant-scoped to one job; token in body; no client selector
  (D-001). **`POST /approvals/magic`** re-verifies the token server-side on every write.
- **Copy editor → `POST /jobs/{id}/creatives`** — the target is **team-role-gated** (`require_role`),
  and `editCopyAction` is passed ONLY on the internal review page (never portal/magic). A client cannot
  author engine output (constraint #3). Verified end-to-end.
- **Billing / preferences** — consume endpoints already confined by `_resolve_client_for_principal`.
- **Server actions** — all read the httpOnly session cookie server-side (or, for magic, forward a token
  the backend re-verifies); none trust client-supplied identity. Checkout/quote URL comes from Stripe.
- **No** `shell=True` / `eval` / `exec` / raw SQL in any new code; all DB access is via SQLAlchemy.

**One pre-existing hardening note (NOT introduced here):** `POST /creatives`'s `image_artifact` becomes a
`Layer.artifact_ref` the compositor may fetch/embed at render time → a potential SSRF/path surface. It is
**team-gated** (trusted principal), and the copy editor only ever resends the *existing* manifest's ref
(not fresh user input), so no new exposure — but validating `artifact_ref` against an allowlist of real
brand-asset refs (not arbitrary URLs) would harden it. Added to open items.

---

## INC-001 — Secret committed to GitHub during VPS cleanup (assistant error)  ✅ REMEDIATED

- **What:** while preserving planflow's code before decommission, the assistant `git add -A && commit &&
  push`-ed on the VPS. The untracked file `planflow/data-import/merge_local_dump.py` contained a
  hardcoded prod DB DSN (`...password=Pf@2026!xK9mWq`). Pushed to `github.com/Azi023/planflow` as commit
  `a1970f6`. Root cause: the command chained the commit after a secret-grep with `&&` instead of gating
  on the grep result.
- **Remediation (done immediately):** `git reset --soft HEAD~1` + unstage the file, then
  `git push --force origin main` → remote `main` back to `7ea6f83`; the file is untracked again (local
  only, out of git). The secret commit is off the branch.
- **Residual + action:** GitHub may retain the dangling commit by SHA until GC. Since planflow's DB is
  being decommissioned the exposure is largely moot, BUT treat **`Pf@2026!xK9mWq` as compromised** —
  rotate it if reused anywhere. (planflow repo is private, limiting blast radius.)
- **Lesson:** never auto-commit machine-local files without inspecting content; a secret-grep must GATE
  the commit (abort on hit), not just print.

---

## Open items for a security pass (not yet done)
- ~~Client-principal read scoping across jobs/clients/brands/ops/briefs/pillars~~ → **AUDITED + FIXED
  (F-001, F-002). Full sweep done — every client-data GET now confines or 403s a client principal.**
- **Re-audit trigger:** any NEW `Depends(get_principal)` route that returns client-scoped data MUST add
  the confinement (or `require_role`). Consider a lint/CI check or a shared dependency to make it
  impossible to forget (e.g. a `require_client_scope(resource.client_id)` helper).
- **Rate-limiting** on `POST /approvals/magic` + `POST /portal/session` — a leaked/guessed token has no
  throttle today. *(Not implemented.)*
- **Magic-link revocation** — no way to invalidate a shared link before its TTL (D-001). *(Not implemented.)*
- ~~Write-route RBAC review~~ → **DONE, F-005** (creates gated to team; tasks/preferences confine client_id).
- ~~`image_artifact` allowlist / compositor SSRF~~ → **FIXED, F-003.** (Follow-on: apply the same
  scheme/host guard to any OTHER path that sets `artifact_ref` — e.g. reference-creative ingest — if it
  can carry an external URL into a render. *Not yet swept.*)
- **2 temp login passwords** flagged for rotation (see HANDOFF).
