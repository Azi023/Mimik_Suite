# Next session — paste-in starter prompt

> Copy everything in the code block into a fresh Claude Code session (run on **Opus**).

```
Continue Mimik Suite — dedicated FRONTEND session. Build the CORE PRODUCT LOOP.

FIRST read, before touching anything: HANDOFF.md (top entry), CLAUDE.md, docs/DESIGN_REFERENCES.md
(LOCKED design system), docs/FRONTEND_ROADMAP.md (§2 resilience, §3 product pages, §4/§4b), and
docs/BRAND_KIT_ONBOARDING.md.

Verify baseline: `docker compose up -d` then `uv run --no-sync pytest -q` (expect 359) +
`cd ../mimik-contracts && uv run --no-sync pytest -q` (expect 18); in web/: `npx tsc --noEmit` +
`npx next lint` (expect clean). Everything is green on main; the frontend has login, board, members,
brief editor, onboarding wizard, and brand-kit editor (all light+dark, session-gated, server-action
mutations, no mock fallback, on the token system in web/design/tokens.css — NOT tailwind/shadcn).

DESIGN RULES (locked): build on Opus. Match docs/DESIGN_REFERENCES.md — shadcn "Studio Admin"
mono/monochrome north-star, light+dark, real empty states (no mock fallback), preserve Supabase
auth wiring + tenant-scoped API calls, no `any` / explicit return types on exported fns. Mutations go
through Next.js server actions that read the httpOnly session cookie server-side (pattern:
web/app/briefs/actions.ts, web/app/brands/[id]/kit/actions.ts). Keep every screen behind the Supabase
session gate like web/app/members/. Per-page TopBar title via AppShell `title`/`crumb` props.

BUILD ORDER (self-pace to your usage budget; stop cleanly at a committed checkpoint if low — do NOT
half-finish a screen):

1) CREATIVE REVIEW + APPROVAL LOOP  ← the sellable core, highest value. Reference: Filestage
   (docs/DESIGN_REFERENCES.md). Image-first canvas showing a job's latest CreativeDoc; click-to-comment
   annotations pinned to the creative; comment threads; and the decision bar: Approve / Request changes
   / Reject — Request-changes uses the pin-pointed RevisionTarget zones (headline/subhead/cta/logo/
   imagery/background/layout/other) + instruction, reject uses reason_tag. BACKEND EXISTS: GET
   /jobs/{id}/creatives, POST /approvals (ApprovalSubmission: job_id, creative_doc_id, action, note,
   reason_tag, targets[]), the ApprovalResponse returns the updated job + spawned task. Wire types are
   already in web/lib/api.ts (ApprovalSubmission/ApprovalTarget/etc). This is a new route, e.g.
   /jobs/[id]/review, reachable from a board card.

2) CLIENT PORTAL (bounded)  ← reuses the review/approval components. Low-privilege (locked constraint
   #3: client = untrusted principal, no tools, no cross-tenant visibility). Magic-link entry; the
   client sees only their creatives and can approve/request-changes/comment. Confirm the magic-link
   session mechanism before building (grep for magic-link/token in api/).

3) CONTENT CALENDAR  ← month grid + at-risk badges. Backend: jobs carry publish_date + an at-risk
   worker. Reference: shadcn Calendar. Smaller.

4) TASKS table  ← filter/status/priority table + pagination (Task backend exists). Smallest; Studio
   Admin /tasks reference. Nice-to-have if budget remains.

RESILIENCE (FRONTEND_ROADMAP §2): if you touch or add any editor with unsaved state, weave in the
shared safety hooks (useUnsavedGuard at minimum; useLocalDraft for crash/power-cut). Prefer building
these 3 hooks once and reusing. Don't let the review/portal drop a client's comment on a dropped
connection.

HUMAN GATES: pause for the operator at contract changes and before commits. Show a Playwright
screenshot (light+dark) of each screen before committing (seed demo data via a first-party owner token
like scripts/… / the prior session's seed pattern: super_admin token -> POST /tenants -> owner token;
set web/.env.local NEXT_PUBLIC_DEV_TOKEN + APP_ENV=dev; run next dev on a free port; screenshot; the
.wiz/.kit/.brief containers are their own scroll containers so flatten heights for full-page shots).
IMPORTANT: never run `next build` while `next dev` is running on the same dir — it corrupts .next
(rm -rf web/.next and restart dev if it happens). Commit per screen with phase-tagged messages; update
HANDOFF.md at the end.

Backend endpoints already available to consume: clients, brands(+PATCH), briefs(+PATCH), pillars
(+presets), jobs, /ops/board, approvals, tasks, assets(upload/ingest/approve), invitations, admin
(accounts/capabilities), tenants, billing, preferences, intake, creatives.
```
