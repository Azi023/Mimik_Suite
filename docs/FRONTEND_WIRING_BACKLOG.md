# Frontend Wiring Backlog — "Built on backend, never wired to UI"

> READ-ONLY inventory (2026-07-24). Diff of the FastAPI route surface (`api/routers/*.py`,
> mounted in `api/main.py`) against every backend call the web app actually makes
> (`web/lib/api.ts` — the only real HTTP client — plus a sweep of `web/app/**` and
> `web/components/**`). "Orphan" = a live backend endpoint/feature with **zero** consumer in `web/`.
>
> Feeds a frontend build lane (AGY/Fable). Request/response shapes below come from
> `mimik-contracts/src/mimik_contracts/*` and the router bodies. Auth gate notation:
> `_TEAM` = team roles only; `require_role(...)` = named roles; `get_principal` = any authed
> principal (client-confined at data layer); `public` = unauthenticated.

## Method / how the diff was built

- API surface: every `@router.*` / `@artifact_router.*` decorator across the 21 mounted routers.
- Frontend consumers: `web/lib/api.ts` is the sole backend caller. Grepped all templated + quoted
  endpoint paths across `lib/ app/ components/`. Verified each borderline hit (bootstrap, /approve,
  /tenants, POST /tasks) — all were comments/labels/nav-paths, **not** API calls.
- Confirmed-consumed endpoints (NOT orphans, listed for completeness): `/me`, `/clients` (list/create/get/patch),
  `/clients/{id}/creatives:generate`, `/clients/{id}/subscription`, `/clients/{id}/preferences/profile` (GET),
  `/brands` (create/get/patch), `/brands/{id}/assets` (GET list + POST upload), `/briefs` (list/get/create/patch/signoff/revise),
  `/jobs` (list/get), `/jobs/{id}/creatives` (GET/POST), `/jobs/{id}/approvals`, `/jobs/{id}/magic-link`,
  `/pillars` (+presets), `/creatives` (list/revise/versions/revert/preview/export.psd), `/exports/svg` (GET),
  `/ops/board`, `/ops/jobs/{id}/transition`, `/approvals` (+`/approvals/magic`), `/portal/session`,
  `/tasks` (list + `/{id}/status`), `/deliveries`, `/billing/checkout`, `/admin/accounts` (+capabilities),
  `/invitations` (list/create/revoke).
- Out of scope by design (no frontend expected): `POST /billing/webhook` (Stripe callback),
  `POST /tenants` (dev-only provisioning).

## The orphan table

| Feature | Backend endpoint(s) | Current UI state | Proposed UI | Effort | Priority |
|---|---|---|---|---|---|
| **Command Center queue** (A-08) — visibility into the generation queue + a place to enqueue a batch | `GET /ops/queue` → `GenerationQueueItem[]` `{id, job_id, client_id, topic, pillar?, format_key, status, requested_by, created_at, error?}`; `GET /ops/queue/stats` → `QueueStats {pending, in_progress, done_today, failed_today}`; `POST /ops/queue` body `EnqueueGenerationRequest {client_id, topic, pillar?, format_key="ig_post"}` → `GenerationQueueItem`. Gate: `_TEAM`. | **DNB.** MASTER_PLAN §2d confirms endpoints LIVE, "no UI consumer". No `/ops/queue*` string anywhere in `web/`. | A Command Center panel/drawer: live queue list (status pills, error surface for failed items), a stats header (4 counters), and an "enqueue generation" form (client + topic + pillar + format). This is the **generate** entry of the cockpit loop. | M | **P0** |
| **Auto brand-QA results** — the QA critic / logo-contrast / knockout verdict that `run_live_qa` now persists into the L5 layer params of the creative manifest | Data rides on the existing `CreativeDoc` manifest (already fetched via `/jobs/{id}/creatives` + `/creatives`). No dedicated endpoint — it is **unrendered manifest data**. | No consumer: zero `qa|critic|contrast` references in `web/lib`, `web/components`, `web/app` (review surfaces included). | QA verdict badges + issue list inside `ReviewPanel`/`CreativeReview` — pass/warn/fail per check (contrast, knockout, brand-floor), so the operator sees the auto-critic before approving. Part of the **review** gate. | S–M | **P0** |
| **Preference signal capture** — the LEARN loop's write path | `POST /clients/{id}/preferences` body `PreferenceSignal {source, ...}` → 201. Gate: `get_principal`. | Only the **read** side (`GET /clients/{id}/preferences/profile`) is wired (`api.ts:1040`, preferences page). Picks/edits/rejects are never recorded. | Emit a signal from the review actions (approve = positive, edit = correction, reject = negative) — mostly a no-UI wiring into existing approve/edit/reject buttons + an optional "why" note. Without it the per-client profile never learns. | S–M | **P0** |
| **Usage / render-cost meter** | `GET /ops/usage?start&end` → `UsageReport {window_start, window_end, renders, by_image_source, by_profile, monthly_cap?}`. Gate: `_TEAM`. | Orphan — no `/ops/usage` consumer. | A usage widget (renders this window, breakdown by image source + style profile, progress bar vs `monthly_cap`). Lives in Command Center or billing. Guards the "sub-now → API-later" cost story. | S | **P1** |
| **Preference ranker + golden-set promotion** | `POST /clients/{id}/preferences/rank` (rank candidates by profile); `POST /clients/{id}/preferences/promote` → `PromotionResult` (gate: `require_role("owner","ops")` — human gate into the SHARED golden set). | Orphan — neither called. | Ranker: sort/badge creative candidates in review by profile fit. Promote: an owner/ops "promote to golden set" action on a strong creative. Completes the **learn** loop. | M | **P1** |
| **Brand-asset ops: knockout / ingest / register / approve** | `POST /assets/{id}/knockout` → `BrandAsset` (logo knockout variant, `_TEAM`); `POST /assets/{id}/ingest` → `IngestResult` (brand-memory ingest, `_TEAM`); `POST /brands/{id}/assets/register` → `BrandAsset` (register external asset, `_TEAM`); `POST /assets/{id}/approve` → `BrandAsset` (`require_role("owner","ops")`). | Orphan — only upload (`POST /brands/{id}/assets`) + list are wired. MASTER_PLAN M-08 flags knockout re-wire. | In `BrandKitEditor`/asset manager: per-asset actions — "derive knockout" (logos), "ingest to brand memory", "approve", and a "register external" path. Feeds generation quality. | M | **P1** |
| **Latest-creative quick-look** | `GET /clients/{id}/creatives/latest` → `GeneratedCreative`. Gate: `get_principal`. | Orphan. | A "latest creative" thumbnail/card on the client row or client detail (fast glance without opening a job). | S | **P1** |
| **Invitation accept + resend** | `POST /invitations/accept` body invite-token, gate `verified_supabase_identity` → `UserAccount`; `POST /invitations/{id}/resend` (`require_role` manage) → re-issue. | Orphan — **no accept page exists** (`find app -ipath '*accept*'` empty); resend not wired. Revoke/list/create are wired. | An invite-accept route/page (Supabase-identity gated) that redeems the token, + a "resend" button in `MembersView`. Accept is a real onboarding dead-end today. | M | **P1** |
| **Portal "request a design"** | `POST /clients/{id}/portal/design-requests` body `DesignRequest` → `Task` 201; 402 if no active subscription. Gate: portal client principal. | Orphan — portal shows jobs only (`app/portal/page.tsx`); no request form. | A bounded "request a design" form in the client portal (subscription-gated, surfaces the 402 as an upgrade prompt). Client-driven top-of-funnel. | M | **P1** |
| **Manual job create** | `POST /jobs` body → `Job` 201. Gate: `_TEAM`. | Orphan — `web/` has no `createJob`; jobs only appear via the generate flow. | "New job" action on the board/calendar (format + publish date + assignee + brief/pillar). Lets the team schedule a slot before generating. | S–M | **P1** |
| **Task create + single fetch** | `POST /tasks` → `Task` 201 (`get_principal`); `GET /tasks/{id}` → `Task`. | Orphan — only list + `/{id}/status` are wired. | "New task" action in `TasksView` + a task detail view. Rounds out the ops task board. | S | **P2** |
| **Calendar from server** | `GET /ops/calendar?start&end` → `CalendarEntry[]` (BoardCard + at_risk). Gate: `get_principal` (client-confined). | `CalendarView` renders, but **derives** entries client-side from the jobs list — the purpose-built calendar endpoint (with at-risk flags + windowing) is unused. | Migrate `CalendarView` onto `/ops/calendar` for server-computed at-risk + date-window paging. | S | **P2** |
| **SVG (POST) + PNG preview export** | `POST /exports/svg` (compose from posted manifest); `POST /exports/png-preview`. Gate: team. | Orphan — only `GET /exports/svg?creative_id=` is wired. | Editor-side "preview PNG" + "export composed SVG from current edit state" buttons in the canvas editor (before the doc is persisted). | S | **P2** |
| **Storefront intake / cold bootstrap** | `POST /intake/claim` (**public**) body `ClaimForm` → `ClaimResult` (storefront lead / 3-free-designs trial); `POST /clients/{id}/bootstrap` → `Brief` (cold-start a client to first brief, `require_role(owner,ops,designer,team)`). | Orphan — no public claim page; bootstrap unused. | Public storefront claim form (marketing → trial) + an ops "cold bootstrap this client" button. Gated on the commerce go-live decision (MASTER_PLAN Q5). | M | **P2** |

### Adjacent note (not a wiring task — contract exists, backend does NOT)
`CommandRequest`/`CommandPlan` contracts exist in `mimik-contracts/ops.py` for the ⌘K natural-language
Command Center (A-05/A-09), but **no `/ops/command` endpoint is implemented** and no ⌘K UI exists.
That is a backend+frontend gap, not a wiring gap — out of scope for this backlog, flagged so it isn't
mistaken for an orphan endpoint.

## Top 5 to wire first

1. **Command Center queue panel** — `GET /ops/queue`, `GET /ops/queue/stats`, `POST /ops/queue`. The
   named A-08 dead-end; it is the *generate* entry of the daily cockpit loop and the highest-value orphan. **[P0]**
2. **Brand-QA results in review** — render the `run_live_qa` verdict (contrast/knockout/brand-floor)
   already sitting in the L5 manifest, inside `ReviewPanel`/`CreativeReview`. Closes the *review* gate. **[P0]**
3. **Preference signal capture** — `POST /clients/{id}/preferences` fired from approve/edit/reject.
   Without it the *learn* loop is write-blind and the profile never improves. **[P0]**
4. **Usage/cost meter** — `GET /ops/usage`. Small, high-signal; guards the subscription→API cost path. **[P1]**
5. **Invitation accept page** — `POST /invitations/accept`. A genuine onboarding dead-end (no accept
   route exists today), so invited teammates/clients currently cannot complete signup. **[P1]**
