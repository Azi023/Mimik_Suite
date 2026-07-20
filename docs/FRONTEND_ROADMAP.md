# Frontend roadmap & backlog — Mimik Suite

> Living doc. Captures: where the frontend stands, the cross-cutting resilience/UX work
> (autosave, back/forth, crash-recovery), the remaining **product** pages, the **command-center**
> add-on backlog (Studio Admin references), the wiring inventory, and hosting/`.env` answers.
> Created 2026-07-20 after shipping the brief editor, onboarding wizard, and brand-kit editor.

---

## 0. Two tracks (don't merge them)

Per `docs/DESIGN_REFERENCES.md` §"product vs internal command-center", there are **two apps** that
**share one design system** (the token CSS in `web/design/tokens.css`), but must not blur:

- **Track A — Mimik Suite (the product):** the multi-tenant creative pipeline sold to agencies.
  The client-facing loop. Everything below under "Product pages". **This is the priority.**
- **Track B — Internal command-center:** surfaces all Mimik businesses (leads, Proofkit, finance,
  hosted sites, Planflow…). The Studio-Admin-inspired add-ons the operator flagged. Same tokens,
  **separate app/tenant boundary** — the client product must never expose internal-ops surfaces.

---

## 1. Status snapshot (Track A)

**Done (this + prior sessions), all light+dark, session-gated, server-action mutations, no mock fallback:**

| Screen | Route | Backend |
|---|---|---|
| Login (split shadcn) | `/login` | Supabase ✓ |
| Ops board (Kanban) | `/` | `/ops/board` ✓ |
| Members & roles (IAM admin) | `/members` | accounts/capabilities/invitations ✓ |
| Brand-brief editor + sign-off | `/briefs`, `/briefs/[id]` | briefs +PATCH ✓ |
| Onboarding wizard | `/onboarding` | clients/brands/pillars/assets ✓ |
| Brand-kit editor + Layout box | `/brands/[id]/kit` | brands +PATCH, BrandLayout ✓ |

**Rough completion — Track A frontend: ~40%.** Backend ~85% (see `docs/COMPLETENESS_ASSESSMENT.md`).
The biggest missing product surface is the **creative review + approval loop** (the core "wow") and
the **client portal** — those are what make the product sellable.

---

## 2. Cross-cutting resilience & UX-safety (do this as a shared layer)

The operator asked for: **back/forth on all pages, autosave, and no data loss on sudden leave /
power-cut** — plus "many features good sites have". Build these ONCE as reusable hooks, then apply to
every editor. Priority: **HIGH** (cheap insurance; the editors already exist).

- **`useLocalDraft(key, state)`** — mirror editor state to `localStorage` (keyed by resource id) on
  every change; on mount, if a local draft is newer than the server copy, show a non-destructive
  "Restore unsaved changes?" banner. **Covers power-cut / tab-close / crash.** Clear on successful save.
- **`useAutosave(save, dirty)`** — debounced (~1.5s idle) call to the existing server action; status
  pill "Saving… / Saved / Unsaved". Apply to the **brief editor** and **kit editor** (both PATCH a
  draft — safe to autosave). NOT the onboarding wizard (it only creates at the end → use `useLocalDraft`).
- **`useUnsavedGuard(dirty)`** — `beforeunload` + Next route-change interception → "Leave without
  saving?" when dirty. Apply to all editors + the wizard.
- **Back/forth:** the wizard already has Back/Continue with preserved step state; add the unsaved
  guard. Editors rely on browser back — add the guard. Consider a breadcrumb in the TopBar.
- **Client portal parity:** the same protections apply when the *client* edits/approves in the portal
  (they must be able to step back, and a dropped connection must not lose a comment).
- **Nice-to-haves seen on good sites:** optimistic UI + toast on save, keyboard `⌘S` to save,
  `⌘K` command palette (Studio Admin has one), skeleton loaders, empty/error/loading states on every
  fetch (partly done), focus management + a11y on modals, offline banner.

**Effort:** ~1 focused session to build the 3 hooks + wire the 3 existing editors.

---

## 3. Remaining PRODUCT pages (Track A) — priority order

1. **Creative review + approval** — THE core loop. Reference: **Filestage** (`docs/DESIGN_REFERENCES.md`).
   Image-first canvas, click-to-comment annotations, comment threads, **Approve / Request changes /
   Reject** with the pin-pointed `RevisionTarget` zones. **Backend exists** (`/approvals`, `/jobs/{id}/creatives`,
   `RevisionTarget`, `CreativeDoc`). Frontend NET-NEW. **Highest value.**
2. **Client portal (bounded)** — WhatsApp + magic-link entry; the client sees only their creatives,
   approves/edits/comments. Low-privilege (locked constraint #3). Backend: approvals + magic-link token.
   Frontend NET-NEW.
3. **Content calendar** — month grid + at-risk badges + publish dates. Reference: shadcn Calendar.
   Backend: jobs have `publish_date` + at-risk worker. Frontend NET-NEW.
4. **Board restyle** — the existing Kanban → shadcn card anatomy + the generating/pending state
   (`generation_started_at` already on the card).
5. **Creative editor (canvas)** — inline **editable text** on L4 + **per-creative layout override**
   (drag logo, rulers, snapping to the BrandLayout guides). This is where the kit's guides become
   interactive per-piece. Big; depends on the compositor work below.
6. **Deliveries / Drive archive** view — on approval, auto-archive to Drive (`Delivery.drive_path`).
7. **Tasks / ops** surfaces, **PreferenceProfile / learning-loop** visibility, **billing** (subscription).

---

## 4. Compositor wiring — remaining (creative-engine, not frontend)

`BrandLayout` is now partly wired (`creative/render/templates.py`): **logo placement + size** and
**margins-as-safe-zone-floor** are honored by every template. **Still to wire:**

- **Header/footer bands** — reserve the top/bottom brand band (templates must inset content when on).
- **Column grid** — snap text/element zones to `grid_columns` + `grid_gutter_pct`.
- **Guides** — expose `guides` to the per-creative canvas editor for snapping (not a compositor concern
  until the editor exists).
- **Populate `TemplateContext.layout`** from `brand.tokens.layout` in the render pipeline (one-liner
  where the context is built) + let a creative override it per-piece.

---

## 4b. Brand-kit & intake R&D (Track A — operator asks)

- **Custom font upload** — the client (or us) uploads the brand's actual font file(s); support
  **multiple**. **Backend hook exists:** `AssetKind.FONT` is already in the enum and
  `POST /brands/{id}/assets` accepts uploads. Work: (a) kit editor + onboarding UI to upload font
  assets and bind them to `Typography.heading_font`/`body_font`; (b) the compositor emits `@font-face`
  from the uploaded font asset (today `heading_font`/`body_font` are just names → generic fallback).
  Validate mime (woff2/woff/ttf/otf) + licence field (already on `BrandAsset`).
- **Brand-guideline / portfolio-deck ingestion** — for brands that already have branding done: upload
  or share a **brand deck / portfolio (PDF/images/URL)** and the **intelligence layer extracts
  everything** — palette, fonts, logo, voice/tone, dos/donts, references — to auto-populate the brand
  kit + brief. **Partial backend:** `extract_brief_sections(url)` (URL→brief §1-5), `ingest_reference_
  creative` (image→references via the fit-critic), and `creative/vision/study.py` already exist. Work:
  a NEW deck-ingest path (accept PDF/multi-image/deck) that runs vision+LLM extraction → fills
  `BrandTokens` + `BriefSections`, presented for human review before it's applied (client text is data,
  never instructions — locked constraint #3). High-wow onboarding accelerator.

## 5. Command-center add-on backlog (Track B) — Studio Admin references

Operator flagged these from `next-shadcn-admin-dashboard.vercel.app`. **Not urgent**; marked with the
reference route. Most are **NET-NEW backend + frontend** and belong to the internal command-center app.

| # | Add-on | Reference (`…vercel.app/dashboard/…`) | Notes / source | Backend |
|---|---|---|---|---|
| B1 | **Dashboard / Default** | `/default` | KPI cards + charts + activity table; per-client & per-sub-product overviews | new (aggregate) |
| B2 | **Chat** (own WebSocket) | `/chat` | Multi-channel inbox (email/chat/IG/FB/phone). Operator: build own Socket.IO; all channels **except WhatsApp** (Meta-restricted). Reuses `NotificationChannel` seam | new realtime svc |
| B3 | **Calendar** | `/calendar` | Month grid + events. Overlaps Track-A content calendar — share the component | jobs/events |
| B4 | **Kanban** (restyle) | `/kanban` | Card anatomy w/ progress %, owner, due date, attachments/comments counts → restyle the board | `/ops/board` ✓ |
| B5 | **Tasks** (table) | `/tasks` | Filter/status/priority table + pagination. Backend `Task` exists | tasks ✓ |
| B6 | **Invoices** (own PDF) | `/invoice` | Create form + live preview + **own PDF template** to replace Zoho Books. Backend `billing`/`Subscription` partial; invoice model NEW | partial + new |
| B7 | **Users** | `/users` | Role/team/status filters, export, add-user. **Largely = our `/members`** — extend it (workspace column, export, richer filters) | accounts ✓ |
| B8 | **E-commerce / Store → Planflow** | `/ecommerce` | Wrap **Planflow** into the suite. It's a **same-stack monorepo** (`~/workspace/planflow`, Next.js `apps/web` + FastAPI `apps/api`) — Meta-connected ad planning with an intelligence layer (`planflow/docs/INTELLIGENCE_LAYER.md`, `KPI_CALCULATION_LOGIC.md`). Integrate as a satellite (call it, don't absorb) or lift its web into a suite surface. NEW integration | Planflow API |
| B9 | **Productivity** | `/productivity` | Personal dash (tasks/focus/projects/notes). Operator undecided on fit — parked | new |
| B10 | **Analytics / traffic** | `/analytics` | Monitor `Mimikcreations.com` traffic (visitors/sessions/pageviews/sources). Wire to GA or own analytics | new integration |
| B11 | **Infrastructure** | `/` (Infra) | Hosted-sites health/uptime/domains for Mimik's sites | new |
| B12 | **CRM** | `/crm` | Pipeline overview + opportunities table. Feed from the **leads tools + Proofkit** (audit) outputs | Mimik_Leads/Proofkit |

> **Scope guard:** B1–B12 are the *command-center*. Before building any, confirm it lives in the
> command-center app/tenant, not the client product (locked design decision). Sequence suggestion once
> Track A's core loop ships: B4 (board restyle, cheap) → B7 (extend members) → B5 (tasks) → B1
> (dashboard) → B6 (invoices) → B2 (chat) → B12 (CRM) → B8 (Planflow) → B10/B11 → B3/B9.

---

## 6. Wiring inventory

**Backend endpoints that already exist (frontend just needs to consume):** clients, brands (+PATCH),
briefs (+PATCH), pillars(+presets), jobs, `/ops/board`, approvals, tasks, assets(upload/ingest/approve),
invitations, admin(accounts/capabilities), tenants, billing, preferences, intake, creatives.

**Net-new wiring needed:** realtime layer (Socket.IO) for chat/live board; invoice model + PDF render;
analytics/GA integration; Planflow integration; Drive delivery view; magic-link client-portal session.

---

## 7. Hosting on the VPS + `.env` safety

**Can we host it?** Yes — standard stack (Next.js `web/` + FastAPI `api/` + Postgres + Redis), the same
shape as `cse-ai-dashboard` on Hetzner. Ship via `docker compose` on the VPS (the repo already has a
compose for Postgres :5434 / Redis :6381; add web + api services, put Nginx/Caddy in front for TLS).
Build `web` with `next build && next start` (or a Node image); run `api` with uvicorn/gunicorn workers.

**`.env` — you're safe:**
- **Nothing secret is in git.** Only `.env.example` files are tracked; `.env`, `.env*.local` are
  gitignored (root + `web/`). Verified. So a colleague cloning the repo gets **no secrets**.
- **A `.env` file is never served to the browser.** Next only inlines `NEXT_PUBLIC_*` vars into the
  client bundle. Keep secrets **un-prefixed** (e.g. `SUPABASE_ANON_KEY`, DB URLs) → they stay
  server-side. The one client-inlined value is `NEXT_PUBLIC_DEV_TOKEN` — **DEV ONLY; leave it empty in
  prod** (set `APP_ENV=prod` to disable the dev-token fallback and force Supabase login).
- **On the VPS:** prefer real environment variables (compose `environment:` / a root-owned `.env`
  loaded by compose) over a `.env` inside the web root. Never place `.env` in a static/served dir.
  Lock file perms (`chmod 600`), keep it out of any Nginx `root`.
- **For colleagues:** share `.env.example`, not `.env`. If secrets were ever pasted into a branch,
  rotate them. (2 temp login passwords are already flagged for rotation.)

---

## 8. Suggested next sessions

1. **Resilience layer** (§2) — 3 hooks + wire the 3 editors. High value, bounded.
2. **Creative review + approval** (§3.1) — the core product loop. Highest value.
3. **Client portal** (§3.2).
4. Compositor: header/footer + grid (§4), then the per-creative canvas editor (§3.5).
5. Command-center: start with cheap wins B4/B7/B5 (§5).
