# Design system & screen references — LOCKED

> Direction decided 2026-07-20 from operator-supplied references. This is no longer "how to gather" —
> it's the chosen system. Screens are built on **Fable** (see build mechanism at the bottom).

## North-star: shadcn/ui admin ("Studio Admin")

Reference: `next-shadcn-admin-dashboard.vercel.app` (arhamkhnz) — **Next.js + shadcn/ui**. Our `web/`
is already Next.js, so shadcn/ui is a drop-in component system, not a rewrite.

**Design language:**
- **Monochrome + minimal.** Near-black ink, white/paper grounds, warm-grey neutrals. Colour is used
  ONLY as semantic signal (subtle green up / red down), never decoration.
- **Light AND dark mode** (the refs ship both; the theme toggle is a first-class control).
- **App shell:** collapsible left **sidebar** (grouped nav) + top **search/command bar** (`⌘K`) +
  content area of **cards**. Wordmark treatment like `⌘ Studio Admin`.
- **Data-dense tables** for admin surfaces (roles, users, invoices) with status pills, row actions,
  filters. Tabular numerals. Generous whitespace, calm hierarchy.
- **Component library = shadcn/ui.** Adopt it in `web/` — it gives us the tables, dialogs, dropdowns,
  tabs, forms, toasts, theming for free, all matching the reference.

**Softer alternative** (not primary): `modernize-nextjs` (Image 32) — blue, rounded, friendlier. Keep
as a fallback mood if the mono system feels too austere for the *client-facing* portal.

## Per-screen reference map

| Screen | Reference (operator-supplied) | Notes / what to copy |
|---|---|---|
| **App shell** (sidebar + topbar + theme toggle) | Studio Admin | the container for every screen |
| **Login / Register** | shadcn split login v1 — "Hello again" (Img 19), v2 (Img 20), register (Img 21) | split screen: brand panel + form + Google button. Replaces `web/app/login` |
| **Members / Roles & Permissions** | shadcn Roles & Permissions (Img 22) | **= our IAM admin panel.** Roles table (access level · users · permission sets · status), Create role, Permission-sets tab, Access-reviews tab, invite |
| **Overview dashboards** (per client / per sub-product) | shadcn CRM / Default / Analytics / Finance (Img 16,17,18,31) | KPI cards + charts + activity table |
| **Creative review + approval** | **Filestage** (Img 33–38) | image-first canvas, **annotate/click-to-comment**, comment threads, **Approve / Request changes / Reject**, email-notify. The Mimik Suite core loop + the client portal |
| **Video review** (Mimik_engine, later) | **Frame.io** (Img 39–44) | dark cinematic; asset grid w/ roles, share settings w/ permissions, time-coded comments |
| **Invoice / billing** | shadcn Invoice (Img 23) | create form + live preview + PDF; for Finance/sub-products |
| **Infrastructure / hosted sites** | shadcn Infrastructure (Img 30) | domain · platform · health · uptime · resources — to surface Mimik's hosted sites |
| **Content calendar** | shadcn Calendar (in nav) | month grid + at-risk badges (backend worker exists) |
| **Ops board** (exists) | keep; restyle to shadcn Kanban | card anatomy + the generating/pending state |

Gaps with no direct reference (the shadcn system still covers them structurally): the **onboarding /
intake wizard** and the **brand-brief editor + sign-off**. We'll compose those from shadcn form/stepper
primitives in the same language — flag if you find a reference you prefer.

## Scope note: product vs internal command-center

The nav (CRM, Finance, Analytics, Infrastructure, E-commerce…) reads as an **internal command-center for
all Mimik businesses** (Mimik_Leads, Mimik_Proofkit, Mimik_Sales, Finance, hosted sites). That is a
*different app* from **Mimik Suite the product** (multi-tenant creative pipeline sold to agencies like
Jasmin Media). They **share this one design system**, but must not merge: the client-facing product must
never expose internal-ops surfaces. Decision per surface — same tokens, separate apps/tenants where the
audience differs. (Revisit before building anything that blurs the two.)

## Build mechanism — Fable agents + skills

Per operator: design/frontend generation runs on **Fable**, not Opus.

- **Division of labour:** Opus (main thread, *can see* the reference images) writes a precise per-screen
  **spec** — layout, components, states, the exact reference to match, and the data/auth wiring to
  preserve. A **Fable-model agent** then builds from that spec + shadcn/ui + our existing tokens. This
  plays to each model's strength (Opus sees + specs; Fable builds the UI).
- **How:** `Agent(model: "fable", …)` running the **frontend-design** (or **impeccable**) skill, one
  screen per agent, reviewed interactively. Fan out to parallel subagents only when building several
  independent screens at once.
- **Invariants the Fable build MUST preserve:** Supabase auth wiring (`web/lib/session`, `/api/auth/*`);
  the real API data facade (`web/lib/data.ts`) — and **kill the mock-fallback + build real empty states**
  as each screen lands; no `any`, explicit return types on exported fns; tenant-scoped calls only.

## First build target
**Login page** — smallest, self-contained, crystal-clear reference (Img 19), and it's the current
ugly screen. Then **Members/Roles** (pairs with the IAM backend). Both on Fable.
