# Mimik Suite — Completeness Assessment & Roadmap

> ⚠️ **SUPERSEDED 2026-07-22 — historical snapshot, NOT current ground truth.** The gaps below
> (frontend "~10%", "board + login only", "critical multi-tenant auth hole", "mock-fallback leaks
> demo clients") are all RESOLVED: onboarding wizard, client/brand editor, brand-kit editor, tasks/
> members/calendar/billing views, magic-link portal, and the in-product editor now exist; the mock
> fallback was deleted; the IDOR class was fixed + is guarded by `tests/test_tenant_isolation.py`
> (re-verified live this session). **Current ground truth = `HANDOFF.md` (top entry) + `docs/BUILD_STATUS.md`.**
> Kept only for historical context.

> Generated 2026-07-20 (business-logic-strategist survey of the codebase vs the product plan).
> Backend ~85% of the plan; **frontend ~10%** (board + login only). One **critical** multi-tenant
> auth hole. This is the ground truth for "how far is the whole suite."

## 1. Product vision

Mimik Suite is a multi-tenant, **done-for-you** creative-agency SaaS that owns the whole loop —
client onboarding → auto-drafted brand brief → a hybrid 5-layer creative engine (AI imagery +
code-composited text) → auto brand-QA → an ops board/calendar → client approval via
WhatsApp/magic-link → auto-archive to Drive — and *learns* per-client preferences above a
house-quality floor. Sold as the $750/mo unlimited-design subscription; the moat is the
human-gated end-to-end loop, not "better AI images."

## 2. What's BUILT (by loop stage)

| Loop stage | Status | Evidence |
|---|---|---|
| Onboarding / intake | Done (API) | `api/routers/intake.py` (public claim + team bootstrap), `clients.py`, `brands.py` |
| Brand brief | Done (API) | `api/services/brief_extraction.py`, `briefs.py` (signoff freeze→version, revise). Dogfooded on Glo2Go |
| Asset library / brand memory | Done (API) | `assets.py`, `creative/vision/`, `brand_memory.py` |
| Creative engine (5-layer) | Partial | `creative/render/templates.py`, `compositor.py` (HTML→PNG 1080²), `copy/l0.py`, `qa/`. **Real image gen not production-ready** (burner browser harness; default backend `none`) |
| Auto QA critic | Done (hard checks) / Partial (subjective) | `creative/qa/checks.py`, `contrast.py` live; subjective Gemini-vision critics are seams |
| Ops board / calendar | Done (API) | `ops.py` (board/calendar/transition + generating window), `at_risk.py` |
| Client portal / approval | Done (API), **no client UI** | `approvals.py`, `magic_link.py`, `billing.py` gate. No client-facing frontend |
| Auto-archive to Drive | Done, verified live | `creative/archive/` (local + SA + user-OAuth) |
| Learning loop | Done (API) | `preferences.py` (signal capture, taste-ranker, golden promotion w/ poisoning guard) |
| Billing | Scaffolded (mocked) | `billing.py` (Stripe checkout+webhook, HMAC verify, 503 until keys) |
| Auth / RBAC | Done (dual-issuer) | `api/core/auth.py` (Supabase ES256/JWKS → UserAccount → tenant+role), `require_role` |
| Notifications | Partial | recording sink + WhatsApp adapter (inert, `WHATSAPP_PROVIDER=none`); email/in-app are records |

## 3. Missing or partial vs the plan

- **Real imagery generation** — only a fragile burner-account browser harness; no compliant path until the Leonardo/OpenAI **API swap** (deferred on payment). Default today = solid-color plate.
- **Client portal frontend** — backend endpoints exist, **zero UI**.
- **WhatsApp live** — adapter built but blocked on Meta account-health (see `docs/WHATSAPP_SETUP.md`).
- **Figma deep-edit (L2/L4)** — no `figma` module.
- **Reference gathering** (Pinterest/scrape → L2) — fit-critic exists, gathering stubbed.
- **A/B dual-model generation** UI + pick-capture — not wired to a human.
- **Multi-format fan-out** (one concept → all channels) — not implemented.
- **Storefront wiring** (mimikcreations.com/unlimited → intake) — not wired.
- **Weekly digest / competitor watch** — not built.

## 4. Frontend gap (the #1 concern)

`web/app` has **one product screen**. "Only seen the Kanban board" is literally all there is.

- **Exist:** `/` board (`page.tsx` + `BoardView.tsx`), `/login` (Supabase), inline `ReviewPanel.tsx` (approve / request-change with revision pins).
- **Stubbed (dead rail buttons, no route):** Clients, Calendar, Creatives, Brand Briefs, Settings (`Sidebar.tsx` / `lib/mock.ts`).
- **Don't exist at all:** onboarding wizard, brand-brief editor + sign-off (the P1 wedge has no UI), creative gallery + L1–L5 layer editing, calendar, settings/admin, billing screen, **entire client portal**.
- **Mock-fallback leaks demo clients** into empty tenants (`web/lib/data.ts`, `lib/mock.ts`) — must be killed for prod.

**Verdict:** backend ~85%, frontend ~10%. "All phases green" = API + tests, not usable surface.

## 5. SaaS / multi-tenant / RBAC readiness

**Solid:** tenant isolation at the **data layer** (`api/db/repo.py`, guarded by `tests/test_tenant_isolation.py`); RBAC roles `owner/ops/designer/team/client/system` via `require_role`; managed Supabase auth (ES256/JWKS) with `UserAccount` as authZ source of truth.

**Blocking gaps for a real 2nd agency (e.g. Jasmin Media):**
- **`POST /tenants` is UNAUTHENTICATED** (`api/routers/tenants.py`) — anyone can create a tenant + mint an `owner` token. **Critical; gate to super-admin.**
- No admin/back-office UI — provisioning is API-only (`POST /admin/accounts`).
- No self-service org signup / invite / email-verification flow.
- Mock-fallback leaks cross-agency demo data — disable in prod.
- Bootstrap-owner token has no expiry/rotation story.

## 6. P0 gaps to a client-demoable product

1. **Gate `POST /tenants`** (super-admin) + kill mock-fallback in prod. (S)
2. **Brand-brief UI** (view / sign-off / revise) — the P1 wedge, backend done, no face. (M)
3. **Client approval screen** (portal page + magic-link landing). (M)
4. **Honest generating/pending state** + one reliable image path (API swap or harness). (S FE)
5. **Admin onboarding screen** (agency + users + first client). (M)
6. **WhatsApp outbound** (even manual-share link first). (S–M)

## 7. Roadmap (ordered, sized)

**Phase A — safe & demoable to a 2nd agency (1–2 wk):** gate tenant creation + disable mock-fallback (S); brand-brief screen (M); admin onboarding screen (M); deploy off the Mac (M).

**Phase B — close the client loop (2–3 wk):** client portal v1 (approve/request-change/comment) (M); WhatsApp outbound (M); content calendar + at-risk badges (M).

**Phase C — make the creative real (2–4 wk, gated on image spend):** browser→API swap (S/gated); creatives gallery + L1–L5 UI + A/B pick-capture (L); reference gathering + Figma (M).

**Phase D — monetize & scale (1–2 wk):** flip Stripe live (S); wire storefront → intake (S); multi-format fan-out + weekly digest (M).
