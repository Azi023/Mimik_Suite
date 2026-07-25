# Mimik Suite — Production Roadmap (operator-driven, codex-executable)

> Built 2026-07-25 from the operator's "improve the live product" session. Each item is scoped so
> a fresh codex/Claude session can pick it up. Prefer **codex** for buildable lanes (saves Claude
> usage); use Claude/browser only where noted. Deploy flow: push main → CI build-images (~4min) →
> `ssh hetzner-vps && cd /root/mimik-suite && docker compose -p mimiksuite pull && … up -d`.

Prod brand IDs — Glo2Go `d319e984-…`, Island Cart `6bcf3ff1-…`, Simply Nikah `cc05d62c-…`
(client `6eb877c3-…`). Tenant `87c42869-902d-44bb-8f92-823e99f93db6`.

## 1. Chapters 05/06 + curation — IN PROGRESS (codex this session)
Applications + Launch Templates sections + `scripts/curate_brand_kit.py` (populate kit.launch_templates/
applications from a brand's existing CreativeDocs). Run on prod per brand after deploy.

## 2. Fill the brand-kit TEXT fields for all 3 brands (codex, self-contained, no copyright)
The ghost cards visible today: Discovery `vision` / `visual_competitor_analysis` / `existing_brand_review`;
Direction `personality_alignment` / `competitor_differentiation`; Brief sections (snapshot, logo notes,
voice & tone). EXTEND `scripts/seed_brand_kit.py` (or a new `seed_brand_copy.py`) to author real strategy
copy per brand from `docs/STYLE_PROFILES.md` + each brand's tokens, and fill `kit.discovery.*`,
`kit.direction.*`, and the Brief `sections`. Idempotent, non-destructive. Dogfood: SN + Glo2Go first.

## 3. In-product editing (P7) — so the operator fills fields THROUGH the UI (not scripts)
`PUT /brands/{id}` already accepts kit? verify; else add a tenant-scoped, versioned, non-destructive
brand-kit update endpoint. Add studio edit controls to each chapter (inline text edit + save) — plain
scoped CSS (shadcn NOT installed). This is what lets the operator type into vision/USP/etc. live.

## 4. SYSTEMATIC CRUD across every entity (not just asset-delete)
Audit 2026-07-25 — DELETE is missing EVERYWHERE; UPDATE missing on many:

| Entity | C | R | U | D |
|---|---|---|---|---|
| clients / brands / briefs | ✅ | ✅ | ✅ | ❌ |
| assets / creatives / jobs / tasks / approvals / pillars / preferences | ✅ | ✅ | ❌ | ❌ |
| brand_book / deliveries / me | – | ✅ | ❌ | ❌ |
| tenants | ✅ | ❌ | ❌ | ❌ |

Deliver full CRUD as a dedicated, uniform pass (one codex lane per entity group), following ONE pattern:
- **DELETE = soft-delete** (set `deleted_at`/`active=false`, audited actor+ts) — constraint #8 non-destructive;
  hard-delete only behind a super_admin "purge" with confirmation. Add a migration for `deleted_at`
  where absent; every list/read query filters out soft-deleted rows.
- **UPDATE**: add PATCH where missing (creatives, jobs, tasks, assets metadata, launch_templates,
  applications, accounts already has it). Versioned + non-destructive for brief/creative/brand-kit.
- **Tenant isolation on EVERY new endpoint** (filter by `principal.tenant_id`; keep the IDOR negative
  test green — extend it to cover the new delete/update routes). super_admin bypass already central.
- **UI**: matching edit + remove controls in each list/detail view (BrandAssetLibrary, board cards,
  brand-kit slots, briefs, tasks) + a confirm dialog on delete + an approved/pending/deleted filter.
- Priority order: assets → clients/brands (delete) → creatives/tasks/jobs (update+delete) →
  launch_templates/applications (via brand-kit editor) → tenants (list/update/suspend, super_admin).
This also answers "how do I see/remove what's added": the /assets library + brand-kit slots gain
list+remove; a global audit/activity view (who added/removed what, when) is the read side.

## 5. External asset gathering (logos / fonts / posters / references) — Claude+browser, COPYRIGHT-AWARE
The `/assets` page (per client) is the upload surface: Logos, Fonts, Product Photos, Reference Creatives.
- **Client's OWN material** (their real logo, their own past posts from their own socials/website): fine
  to fetch + upload as that client's assets. This is the client's IP.
- **Fonts**: download the ACTUAL licensed files (OFL/Google Fonts for the 9 built-ins already bundled;
  for brand fonts, the properly-licensed file) + upload with the licence noted. Never rehost a paid
  font without a licence.
- **References (Pinterest/Dribbble/etc.)**: fine as *references* (aesthetic study, attributed) — they
  feed `Brand.references` / moodboard, not the client's "own creatives".
- **Competitor posters / others' creative work**: DO NOT rehost as the client's own assets/creatives —
  that's copyright infringement. Use only as references (link/attribution), or as private study inputs.
This lane is semi-manual (browser + judgment). Best run in a focused Claude+browser session; the
operator uploads alongside. Wire uploaded assets into logo_suite slots + moodboard_asset_ids after.

## 6. Live codex/agy terminal on the VPS (superadmin-only) + two-way sync — DESIGN FIRST (security)
Operator wants a terminal to run codex/agy against live prod. **Security reality (pentester's lens):**
an in-APP web terminal with shell access on prod is remote-code-execution by design — the single
highest-value target on the box. Recommendation, safest → riskiest:
- **Preferred: SSH + tmux on the VPS.** Operator SSHes in (`ssh hetzner-vps`), runs codex/agy inside a
  persistent `tmux` session in a git clone at `/root/mimik-suite-src` (separate from the deployed
  `/root/mimik-suite` compose dir). No new web attack surface. This already works today.
- If a browser terminal is truly wanted: a hardened `ttyd`/`gotty` behind (a) the app's super_admin
  session check, (b) an IP allowlist, (c) TLS, (d) audit logging — and NEVER the app's own web
  container. Treat as a separate, reviewed micro-service. High risk; only with eyes open.
- **Two-way sync ("CI/CD both ways")**: prod runs built images, not editable source, so true bidirectional
  sync of *running code* isn't the model. Do it in git: a VPS clone tracks `main`; a hook auto-commits +
  pushes VPS-side edits to a branch and auto-pulls `main` on deploy. Never rsync into running containers.
  Concretely: `git` is the sync bus both ways; CI is one-way (main→images→deploy) and stays that way.

### 6a. CONTEXT BUNDLE — the terminal must have FULL context, nothing missing (operator requirement)
A codex/agy/claude session on the VPS is only as good as the context it can see. The workspace at
`/root/mimik-suite-src/` must carry the complete knowledge surface:
- **All three repos side-by-side** (so `../mimik-contracts` / `../mimik-knowledge` path deps resolve
  exactly like local + Docker): clone `Mimik_Suite`, `mimik-contracts`, AND `mimik-knowledge` (prompt
  library, golden set, rubrics, evals, learning-loop) as siblings under `/root/mimik-src/`.
- **In-repo durable context (already travels via git):** `CLAUDE.md` (project brain), `HANDOFF.md`
  (rolling state — read top entry first), `SESSION_LOG.md` (decision audit), `docs/` (BRAND_KIT_V2_SPEC,
  STYLE_PROFILES, DESIGN_REFERENCES, this ROADMAP), `graphify-out/` (knowledge graph + wiki).
- **A top-level `AGENTS.md` / `CONTEXT.md` index** at `/root/mimik-src/` that points every agent to:
  read HANDOFF top entry → CLAUDE.md → this roadmap → graphify wiki, before acting. Mirror the global
  `~/ai-dotfiles/AGENTS.md` conventions.
- **claude-mem (episodic) is machine-local + rebuildable** — it does NOT auto-travel to the VPS, and
  per CLAUDE.md the DOCS are the durable source of truth (claude-mem is scratchpad). So the handoff +
  SESSION_LOG + docs ARE the R&D memory for the VPS. If deeper episodic recall is wanted there,
  rebuild claude-mem on the VPS from the git history, or export key observations into `docs/`.
- **Refresh discipline:** a `git pull` on session start (mirror the local `session-start` hook) keeps
  the VPS context current; `graphify update .` after code changes keeps the graph fresh.
- Secrets stay ONLY in `/root/mimik-suite/.env` (the compose dir) — never in the source clone.

## 7. superadmin scope — operator wants super_admin = ONLY themselves (they are the owner)
Zaid (`zaidxdesigns@gmail.com`) was provisioned super_admin earlier. To make super_admin operator-only:
demote Zaid to `owner` (full tenant powers, no cross-tenant) via `PATCH /admin/accounts/{id}` or a
one-line DB update. CONFIRM with operator before changing a colleague's access.

## Ordering suggestion
2 (text fill) + 4 (asset delete) are quick codex wins → 3 (in-product editing) unlocks self-service →
5 (asset gathering) is the content push → 1 finishes the book → 6/7 are infra/policy decisions.
