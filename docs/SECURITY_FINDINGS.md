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

## Open items for a security pass (not yet done)
- **GET /ops/board** — confirm a `client` principal cannot read the ops board (it's an internal view;
  check whether it filters by client scope or should 403 for clients). *(Not yet audited — flagged.)*
- **GET /clients** — confirm client-principal scoping (a client should not enumerate the tenant's other
  clients). *(Not yet audited — the portal avoids calling it, but the endpoint should be checked.)*
- **GET /brands/{id}** — a client can pass only its own brand_id in the portal flow, but confirm the
  endpoint itself confines client principals. *(Not yet audited.)*
- **Rate-limiting** on `POST /approvals/magic` + `POST /portal/session` — a leaked/guessed token has no
  throttle today. *(Not implemented.)*
- **2 temp login passwords** flagged for rotation (see HANDOFF).
