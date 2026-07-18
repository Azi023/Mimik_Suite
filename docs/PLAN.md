# Mimik Suite — Living Plan (v0.1)

> Status legend: **[LOCKED]** decided this session · **[REC]** my recommendation, pending your confirm · **[OPEN]** not yet discussed
> This is a *living* document. We keep grilling and updating it — it is NOT a final one-shot plan.
> Last updated: 2026-07-18 (session 1).

---

## Context — why this exists

Atheeque runs creative/marketing work through two agencies (Mimik Creations; workplace Jasmine Media) and is bleeding a specific, existential problem: **clients are churning because they built their own Claude/ChatGPT pipelines and no longer need the agency.** On top of that, day-to-day ops keep failing at the seams:

- **Communication / sign-off drift** — briefs change after the output is made; last-minute rejections (the "doctor looked greenish, don't post it, the night before" incident). Root cause: *zero scheduling buffer* + no frozen, signed-off brief.
- **No durable documentation** — onboarding docs, brand briefs, brand identity live in people's heads or ephemeral chat.
- **Tuning evaporates** — quality improved through interactive chat back-and-forth (e.g. better sales emails) is not captured; an automated system would regress.
- **Ops hygiene** — tracking "is it done?" in Excel; approved deliverables not archived to Drive (ops manager started skipping it, delivering via WhatsApp only).

**Intended outcome:** a multi-tenant SaaS that (a) runs Mimik/Jasmine's own client work faster and (b) is sold as a productized *done-for-you* service. Built by a solo founder on AI-CLI subscriptions + browser automation + image models, no funding.

**Positioning (from market R&D):** The moat is **owning the whole loop, human-gated** — intake → brand brief → content → creative → internal review → client approval → delivery. Not "better AI images" (undefensible). Closest incumbent is **Pencil** (trypencil.com) — but Pencil is an *enterprise self-serve tool for paid ads*; Mimik is a *done-for-you service for SMBs*. Different buyer = the opening. Do not fight Pencil/Canva on tooling; win as the service they are not.

---

## Locked decisions (this session)

1. **[LOCKED] Product identity** — Multi-tenant SaaS from day one, configurable/settable. Used internally by Mimik/Jasmine AND sold as a product.
2. **[LOCKED] Product shape** — **Done-for-you service, productized.** Client sees a lightweight *request + review/approve* surface; Mimik's team + AI run the engine internally; each client = one tenant; sold as the existing **$750/mo unlimited-design** subscription (already live on mimikcreations.com/unlimited).
3. **[LOCKED] First wedge** — Build the **creative loop**, whose first buildable chunk is **brand-brief automation**, living inside a **minimal dashboard shell** designed to absorb the other modules (Sales, Proofkit, video) as tabs later. (These were never competing options — they're dependency-ordered layers of one thing.)
4. **[LOCKED] Creative engine = HYBRID** — AI generates *imagery only*; a code layer composites exact headline / logo / brand-hex / CTA / phone via headless-browser render (Playwright, already owned). Forced by two constraints: (a) pure-gen mangles text >~200 chars and can't place logos/hit brand hex; (b) editability requires a structured/layered artifact, which pure-gen flat PNGs can't provide. Format (IG post, story, poster, carousel, ad) is a *parameter*, not a hardcoded pipeline.
5. **[LOCKED] Edit model = 5-layer checkpoint stack** — non-destructive; every layer saved, independently re-generable, and a valid human takeover point ("check out at any layer, cut the designer's work"):
   - **L1 · Base plate** — AI base imagery/background
   - **L2 · Concept pass** — reference-driven composition (subject/scene); *no text yet*
   - **L3 · Brand scaffold** — code template: grid, safe zones, logo slot, brand colors/fonts
   - **L4 · Message layer** — real editable text (headline/sub/bullets/CTA/phone), pixel-perfect
   - **L5 · Finish** — logo, effects, color grade, export master
   - A creative = a **JSON manifest** → re-renders deterministically. Default designer handoff at **L4** (~90% of fixes); deep/bespoke edits export to **Figma** and re-import. *No custom canvas editor* (that's Canva's moat — wrong fight).
6. **[LOCKED] Approval channels = hybrid** — Internal team works in the **dashboard** (ops cockpit) + optional push with inline Approve/Change/Reassign; **client approves via WhatsApp + a no-login magic-link page** (SMB clients live in WhatsApp; zero friction on the critical "yes"). Every action timestamped → freezes the approved brief; post-sign-off changes become *logged new requests* (this is the fix for brief-drift + the greenish-doctor fire drill).
7. **[LOCKED] Ops layer must include** — content **calendar with lead-time SLA** (plan ~30 days ahead; enforce "approved ≥ N days before publish"; flag at-risk jobs early — kills "night before"); production **distribution/status board** (who's on what, what's stuck — kills the Excel sheet); **auto-archive on approval** to organized per-client **Google Drive** folders (enforced in code, not by nagging).
8. **[LOCKED] Operating model = assisted autonomy (guided + recorded)** — pipeline auto-drafts; human can nudge at the review step like the chat back-and-forth today; every correction is **promoted into the versioned prompt library / golden set / rubric**; **evals** gate against regression; autonomy dials up per task as the bar proves out.
9. **[LOCKED] Integration = orchestrator + satellites, NOT a monolith** — engines (ProofKit, mimik-engine) **keep their own repos + CLIs**; the Suite is a new thin layer that *calls* them. Physical wiring **[REC]**: meta-repo + engines as **pinned packages** (`pip install -e ../engine` in dev, `git+ssh://…@vX` in prod) + a shared **`mimik-contracts`** (Pydantic schemas) glue package + a shared **`mimik-knowledge`** layer. Confidential Sales/lead data never enters the client-facing product.

---

## Architecture (proposed)

### Repo topology
```
~/workspace/
  mimik-engine/     (own repo + CLI)  ── video pipeline
  Mimik_Proofkit/   (own repo + CLI)  ── audit/qualify/pack/render  [also vendored in Sales as engine/]
  Mimik_Sales/      (own PRIVATE repo) ── acquisition (lead-gen, outreach) — CONFIDENTIAL, stays separate
  mimik-contracts/  (new shared pkg)  ── Pydantic schemas: Tenant, Client, Brand, Brief, Job, CreativeDoc, Layer, Approval, Delivery
  mimik-knowledge/  (new shared pkg)  ── prompt library, golden set, rubrics, evals, learning-loop promoter
  Mimik_Suite/      (new, THIS repo)  ── the product
    api/    FastAPI + PostgreSQL + Redis + job queue (Celery/Arq)   [REC]
    web/    Next.js (App Router) dashboard                          [REC]
    creative/  the NEW 5-layer hybrid engine (imagery gen + Playwright compositing)
    calls -> proofkit, mimik-engine as pinned packages via mimik-contracts
```

### Stack [REC — pending confirm]
- **Backend/API + orchestration:** Python **FastAPI** — matches the entire existing AI stack (ProofKit, engine, Playwright, Pydantic); one language for the AI backend; reuses render + ledger/handoff patterns.
- **DB:** **PostgreSQL** (multi-tenant; known from cse-ai-dashboard) + **Redis** (queue/cache).
- **Long-running creative jobs:** a job queue (**Celery** — known from overwatch — or lighter Arq).
- **Frontend:** **Next.js** (known from mimik-engine + Proofkit).
- **Auth/multi-tenancy:** tenant-scoped; every row keyed by `tenant_id` (client) — RLS-style discipline.

### Data model spine
`Tenant(agency) → Client → Brand(brief, tokens, logo, assets) → Job(request, format, publish_date, assignee, status, SLA) → CreativeDoc(manifest, layers[L1..L5]) → Approval(actor, action, ts, note) → Delivery(drive_path)`

---

## The Knowledge / Quality layer (`mimik-knowledge`)

The antidote to "tuning evaporates in chat." Directly mirrors Atheeque's own `/learned` + `patterns.md` + `/missed-pattern` + claude-mem/Obsidian philosophy, applied to marketing output.

1. **Instruction library** — versioned system prompts per task (email, brand brief, image prompt), in git.
2. **Golden set** — best-ever outputs as few-shot exemplars + *negative* examples ("rejected because…").
3. **Critic + rubric** — explicit quality bar scored by a critic agent before anything reaches a human (extends ProofKit's "critic-passed").
4. **Evals** — fixed test inputs run after every change → *prove* no regression.
5. **Learning loop** — human corrections at review are promoted into 1/2/3 automatically. Improvement compounds.
6. **Per-job context record** — decisions/reasoning stored with the job (HANDOFF-per-client), so context travels.

---

## Feature set

### [LOCKED] Selected + your preference-learning core
- **Acquisition→fulfillment auto-bridge** — Sales closes a lead → auto-creates tenant + starts brand brief. One funnel.
- **Visual brand-QA critic** — auto-check logo/hex/legibility/safe-zones/spelling before human review. Kills the "greenish" error class.
- **Client brand-memory corpus** — approved creatives become the client's evolving style anchor (series consistency).
- **Multi-format fan-out** — one approved concept → all channels (re-flow L3/L4 per format), human-gated.
- **A/B dual-model generation** — run OpenAI + Gemini (or 2 seeds) → present 2 options → capture the pick.
- **Preference capture as training signal** — every pick/edit/rejection/approval logged as a preference; feeds future gen.
- **Per-client preference profile** — living record of each client's revealed desires; conditions their future creatives.
- **Iterative critique→refine convergence loop** — generate → auto-critique → refine → repeat until it clears the bar → human feedback → refine → "liked by everyone."

### [LOCKED] Content pillars (planning phase)
Before design, the client picks **content pillars** — the thematic buckets their content is planned around (Educational, Behind-the-Scenes, Promotional, Social Proof, Engagement, Product, Seasonal) — from presets OR **custom pillars of their own**. Each Job is tagged with a pillar; the content calendar balances across them (no five promos in a row). After selecting, the client proceeds to the design phase and edits per-layer / per-section (the existing 5-layer stack). Modeled: `mimik_contracts.ContentPillar` + `PILLAR_PRESETS`; `Job.pillar_id`.

### [REC] Out-of-box additions (pending your pick to elevate)
- **Taste-model auto-ranker** — once enough A/B picks accumulate, a light ranker predicts the preferred variant → auto-select or pre-sort → cuts human review time. Compounds off the preference data.
- **Two-layer taste: house floor + client pref** — Mimik's own quality standard is a hard floor never violated; client preference optimizes *above* it. ("Mimik has a set of standards.")
- **Prompt-DNA / recipe versioning** — every creative stores the exact prompt+model+refs+layer-params that made it. A winning look becomes reproducible + forkable ("more like that one"). Powers consistency + the golden set.
- **Auto-brief-from-conversation** — a messy WhatsApp request ("need something for our sale next week") → structured job + proposed brief. Attacks the mediator/communication pain at the source.
- **Confidence-gated autonomy** — the system routes high-confidence work (passes QA + high preference-model score) to quick human approval, and low-confidence work to a designer *earlier*. Ties the autonomy dial to measured confidence.
- **Rejection-reason taxonomy** — structured reasons at every rejection (too busy / wrong color / logo small / tone off) → training signal + analytics on top failure modes → systematic prompt/rubric fixes.
- **Weekly client digest** — auto "here's what we made / what's pending your approval" on WhatsApp → engagement + churn defense + unsticks approvals.
- **Competitor watch** — periodically pull competitors' socials (reuses reference-research Playwright) → keep the client differentiated/on-trend.

## [LOCKED] Client portal — bounded self-serve + security model

Default stays done-for-you (approve / request-change via WhatsApp + magic-link). PLUS a **collaborative, tracked self-serve surface** in the client's own portal — must feel **modern + effortless, not a legacy system** (frontend-design rule: get a concrete visual reference before building the UI). On their OWN creatives the client can:
- **Tier-1 edits** — copy, brand colors, pick among generated background variants, choose a layout preset. Non-destructive: every edit = a new version (revert anytime).
- **Prompt for changes** — freeform natural-language ("warmer, bigger logo") → treated as a *guarded change request* → constrained, quota-limited regeneration. NOT raw engine/system-prompt access.
- **Comment / annotate** design changes directly on the creative.
- **Request / assign an editor** or specific capabilities.
- **Task tracking + notifications** — every client action fires a notification to the ops person and becomes a **tracked task** with a status the ops person advances (open → in progress → done). The client portal and the internal ops board are **two views of the same task system**.

This is a controlled slice of self-serve on top of the done-for-you core, fully human-supervised — not unsupervised raw studio access.

**Security (client = untrusted principal — pentester discipline):**
- **Trust boundary** — client input is *data, never instructions*. Freeform text (edit copy / change requests) is delimited/quoted and passed as content, never merged into the system prompt as directives.
- **Prompt-injection defense** — a guard/moderation pass on all client freeform text; client text only ever fills a *constrained slot*; client-facing generation runs in a low-privilege model context that has no tool access and no visibility into other tenants or the pipeline internals.
- **AuthZ / tenant isolation** — a client can touch ONLY their own `Client→Brand→Job→CreativeDoc`. Authorization enforced at the *data layer*, not just the route (defeat IDOR — the exact discipline already in ProofKit/Sales).
- **Non-destructive + versioned + audited** — every client action is a new version with an actor+timestamp record.
- **Quota / rate limits** per tenant — generation costs (even free-tier has caps); prevent resource-exhaustion abuse.
- **Learning-loop isolation** — client edits feed ONLY their own preference profile. Promotion to the shared golden set / global prompts requires Mimik human review, so a malicious client can't poison the shared model.

## P2 · Creative engine — implementation grill (in progress)

Gaps surfaced that the high-level plan missed: copy origination, real assets+font licensing, composition-aware generation, multilingual/RTL, print output, industry compliance, rights/ToS, rate-limit/budget + failure handling, re-render-vs-regenerate honesty.

**Locked so far:**
- **[LOCKED] Copy = L0 step.** AI drafts headline/body/CTA from the *frozen brief + selected pillar + topic* → **human polishes & approves** → approved copy feeds the golden set. Copy automates but never ships un-reviewed (the anti-AI-slop gate).
- **[LOCKED] Text-on-imagery = layout-FIRST.** A curated library of **clean/sleek, selectable layout templates** (engine suggests the best for format + copy length; team/optionally client picks). Imagery (L1/L2) is prompted to keep the text zones *quiet*; a **scrim is applied CONDITIONALLY** — only when the QA WCAG-contrast check flags a text zone, never blanket. A **clutter critic** enforces "don't overcomplicate" (limited text, real whitespace).
- **[LOCKED] Per-brand Asset Library.** Logo (transparent, light/dark/mark variants), fonts, and imagery, stored per client, **Drive-backed** (same org as the deliverable archive), fed by **both the client AND the Mimik team** (team can upload higher-quality replacements). The compositor always renders from the **canonical "approved" version**. Font **licensing tracked per brand**; open-license (SIL OFL / Google Fonts) lookalike used when no licensed file is available — never composite an unlicensed font.

- **[LOCKED] Reference → generation.** Vetted references become a **style descriptor** (mood/palette/composition/lighting/complexity) that shapes the prompt + a reference-image input where the model supports it — refs guide STYLE, brief guides BRAND, copy+layout guide STRUCTURE; **never reproduced**. A **reference-fit critic agent** validates each reference suits the content + context AND **states its reasoning**; a **human approves** the set (assisted autonomy, dialed down as it proves out).
- **[LOCKED] Cold/trial-client bootstrap.** For a brand-new client (e.g. the 3-free-designs offer) with NO assets, **auto-source logo/imagery/style ideas from their website + socials** via the browser path, flagged auto-sourced/unverified, as the starting point until real assets are provided/approved. This is the "our own digging" flow for prospects not yet onboarded. (Established clients use the curated Asset Library instead.)

- **[LOCKED] Compliance = calibrated critic, human is final.** Per-industry ruleset + per-brand don'ts; the critic flags SPECIFIC regulated-claim patterns (guarantees, before/after, unverified superlatives) and explains each flag — it does NOT block legitimate marketing. Human overrides wrong flags with a note (tunes down over-flagging). If the AI refuses/keeps failing, the job degrades to the L2 checkpoint + human editor finishes it. AI over-caution never blocks delivery.
- **[LOCKED, defaults] Operational:** multilingual/RTL — Playwright HTML/CSS renders Arabic + RTL natively; need Arabic fonts in the library + per-brand language; EN+Arabic at launch. Print — sRGB social now, add 300dpi/CMYK/bleed profile JIT (export layer supports both). Re-render vs regenerate — AI layers cached in the manifest; re-render reuses cached, regenerate = explicit new image + stored seed. A/B + preference — a job can run 2 backends/seeds → variants stored → pick logged as a signal. Vision QA — hard checks (contrast/safe-zones/dims/logo) in code now; subjective (on-brand/clutter/AI-tells) via free-Gemini vision when the seam lands.

- **[LOCKED] Spend + reliability.** Image gen is the ONLY bottleneck (copy is cheap text, compositing is free code). Minimize it: **A/B the base concept only**; **fan-out + edits re-composite the CACHED base** (~0 extra gens); **generate downstream only after approval**; queue enforces a **per-provider budget + backoff + route-to-other-backend + deadline-priority** ordering (at-risk jobs jump ahead; the 30-day buffer absorbs delays). Failure: **retry×1 → try other backend → L2 human fallback.** **Upgrade path:** free/sub tiers now → paid ChatGPT/Gemini tiers as success grows → paid APIs, all a config swap behind the adapter (minimization stays valuable on paid — lower cost + latency).

**P2 grill COMPLETE.** Still-minor / decide-in-build: rights-ToS labeling, versioning/branching tree shape, taste-ranker trigger threshold.

### P2 build sequence (grounded in the above)
1. **Layout-template library** (network-free) — clean/sleek HTML/CSS templates parameterized by tokens + copy + format; conditional scrim; clutter-safe. *(starting now)*
2. **Compositor** — `manifest → HTML → PNG` via Playwright (headless render; install gated on network). Manifest gains a typed copy block + chosen-template ref + cached image artifact_ref.
3. **Copy step (L0)** — AI draft (free-Gemini seam) from frozen brief + pillar + topic → human approve → golden set.
4. **Image adapters** — free-Gemini first (robust), then ChatGPT-browser (fragile), behind the locked adapter; A/B base only.
5. **Reference-research + fit critic**, **brand-QA critic** (code checks now, vision later), **preference capture**.

## Auth, security & admin panel [LOCKED]

Security is never cut — international standard over friction (and passwordless *is* a standard, so we get both).
- **Managed, standards-compliant auth provider** (Supabase Auth — already running Supabase — or Clerk/Auth0). **Never self-rolled.** Configured to standard: **OAuth2/OIDC, MFA, RBAC** (owner / ops / designer / client), secure session mgmt, **audit logging**. Aligned to OWASP ASVS + ISO 27001 practice.
- **Clients get proper accounts** via the provider's **passwordless** flow (secure + frictionless), scoped to their own tenant (the bounded-portal + data-layer authZ + injection hardening already locked).
- **Admin panel (back-office)** — internal super-admin surface: issue/manage client accounts, tenants, roles, permissions, settings; fully audit-logged.
- Replaces the P0 tenant-bootstrap token (that was scaffolding). Migrate the existing tenant-scoping to derive from the provider's verified identity + role claims.

## P3 · Ops & approval — grill (in progress)

- **[LOCKED] Client approval = in-portal + magic-link, same action.** Client approves inside their authenticated portal (durable — nothing gets missed) OR via a secure, mobile-friendly magic-link page (frictionless, shareable when a link is passed manually). Both trigger the same Approve / Request-change action, audit-logged. Notifications start cheap (email / manual WhatsApp share). **Upgrade to native WhatsApp Business API buttons once the product succeeds** (additive, not a rebuild) — deferred now for cost + Meta-verification weight.
- **[LOCKED] Kanban ops board.** The ops board is a **Kanban** — columns by job status (Brief → Generating → Internal review → Client review → Approved → Delivered/Archived), cards = jobs (pillar tag, assignee, deadline, at-risk flag). Visible/trackable by anyone (ops manager, editors, team); AI moves most cards automatically. **Status transitions fire procedures** — e.g. → Approved auto-uploads to Drive (system does it, not a human remembering).
- **[LOCKED, defaults] Calendar + SLA:** per-client + global calendar; a scheduled worker flags jobs where `now ≥ approve_by` and unapproved → at-risk badge + ops notification (uses `Job.is_at_risk()`). **Drive archive:** on approval, PNG(s) + manifest → `Mimik Clients/<Client>/<YYYY-MM>/<job>/`; per-client root at onboarding. **Brief versioning:** signoff mints a **new immutable frozen version row** (edit a frozen brief → new draft → signoff) — resolves the in-place-mutation flag. **Task system:** every client action = a `Task` (open→in_progress→done) + ops notification; portal & board are two views of one table.

## P4 / P5 / Infra — accepted defaults [LOCKED, defaults]

- **P4 Learning loop:** pick/edit/rejection/approval → `PreferenceSignal` → per-client profile (rejections use a reason taxonomy). Taste-ranker starts as a simple heuristic once a client has ~20 signals, upgrades as data grows. Human-gated promotion to the shared golden set; client corrections stay client-scoped.
- **P5 Storefront + billing:** mimikcreations.com/unlimited claim form → API → auto-creates a prospect client + fires the cold-client bootstrap (acquisition→fulfillment bridge). **Stripe** for the $750/mo sub + 3-free-designs trial → paid (Checkout + webhooks gate tenant access).
- **Infra/deploy:** **Hetzner VPS + Docker** (API + worker(s) + Playwright browser pool + Redis); **Supabase** for auth (optionally managed Postgres); object storage for the asset library; secrets via env/secret-manager (never git); **GitHub Actions** CI running the suite + deploy.

## Reuse map (what already exists — do NOT rebuild)

- **Playwright render + capture infra** → reuse for L1–L5 compositing (Proofkit `collector/playwright_capture.py`, `qualify/browser.py`).
- **Brand-brief JSON structure** → seed the Brand model (`mimik-engine/config/clients/*.json`: name, niche, brand_voice, tone_keywords, dos, donts, handles).
- **Figma export** (designed in Proofkit) → the L4/L2 deep-edit handoff.
- **M365 Graph draft** (`Mimik_Sales/sales/draft.py`) → outreach/notification pattern; stdlib-only token flow.
- **Ledger dedup + schema handoffs** (`Mimik_Sales/sales/ledger.py`, `handoff_to_pack.py`) → the contract discipline for `mimik-contracts`.
- **Multi-CLI orchestration** (Claude+Codex+AGY, `WORKERS.md`) → the orchestration substrate.
- **Live storefront** — mimikcreations.com/unlimited (`$750/mo`, "3 free designs" claim form) → the front door / lead capture; wire it into the Suite intake.
- **Video pipeline** (`mimik-engine`: Claude script → ElevenLabs → FFmpeg) → plugs in as the video module later.
- **Available integrations** — Google Drive (archive), Figma (edit), Google Calendar/Gmail. WhatsApp needs WhatsApp Business API (external).

---

## The Brand Brief — deliverable spec (P1 wedge)

The frozen, signed-off artifact every creative reads. Auto-drafted from the client's URL/socials, human-confirmed, then *versioned + locked* (this lock is also the fix for brief-drift/scope-creep). Designer-grade set:

| # | Section | Auto-extractable? | Source |
|---|---------|-------------------|--------|
| 1 | **Brand snapshot** — who they are, what they sell, positioning, target audience, competitors | Partial | Firecrawl scrape + LLM summary |
| 2 | **Logo** — mark + variations, clear-space, min size, + **assessment** (usable / needs redesign) | Partial | Brandfetch + vision analysis |
| 3 | **Color palette** — primary/secondary/accent, exact hex, usage rules | Yes | Brandfetch / site CSS + vision |
| 4 | **Typography** — heading + body typefaces, weights, hierarchy | Yes | Site CSS / Brandfetch |
| 5 | **Voice & tone** — adjectives, do/don't, example phrases | Partial | Site copy + socials + LLM |
| 6 | **Imagery style** — photo vs illustration, mood, subjects, filters, what to avoid | No (human) | Human + reference board |
| 7 | **Do's & Don'ts** — hard guardrails the AI + designers must respect | No (human) | Human |
| 8 | **Reference / mood board** — *vetted* references defining the target aesthetic (feeds L2 concept pass) | Semi | Reference-research step (below) |
| 9 | **Deliverable specs** — platforms, formats, dimensions, safe zones per channel | Preset | Channel presets |

Seeds from the existing `mimik-engine/config/clients/*.json` schema (name, niche, brand_voice, tone_keywords, dos, donts, handles).

### Reference-research step (feeds section 8 + L2)
Playwright gathers candidate references (Pinterest etc.) for the brief's niche/format → a **vetting rubric** scores each for fit (on-brand palette? right complexity? legible text density? matches the content intent?) → top-N are attached to the brief as the aesthetic target. This is what makes L2's "add reference ideas via prompt" concrete and repeatable, and encodes your "don't overcomplicate / 8-words-max poster" taste as scored rules.

## Open decisions (next grilling rounds)

- **[LOCKED] Budget constraint** — NO paid-API budget now. The whole product runs on **subscriptions / free tiers** until it's trained + perfected; paid APIs come later. Reasoning/copy/orchestration stay on the existing CLI subs (free). Note: `codex`/`agy` CLIs are code-only — they cannot generate images.
- **[LOCKED] Imagery via a swappable ADAPTER** — the engine requests imagery through an interface; the backend is config-swappable so "subscription now → API later" is a one-line change, not a rewrite. No architecture bet on the sourcing method.
- **[LOCKED] Imagery backends (build phase) — BROWSER, not free API.** Images come from browser automation of the operator's **PRO ChatGPT** (empirical quality preference) and **Google AI-Studio/Gemini playground (Nano Banana)** — both use existing PRO subscriptions, no tokens. **Correction:** the free Gemini *API* tier does NOT reliably include image generation (needs billing), so the free API key is used for **copy/text only**. Running both browser backends on a job feeds the golden-set/eval comparison. Paid image APIs (Ideogram/Flux/GPT-image) slot into the same adapter once budget exists — a config swap.
- **[OPEN] Brand-brief document set** — define the standard deliverable docs (brand identity, color palette, typography, logo assessment, tone/voice, do/don't, competitor snapshot). I'll draft the designer-grade default set.
- **[OPEN] Reference-research step** — Pinterest/etc. gather + *vet/score* references before L2 (Playwright-driven; feeds concept pass). Design the vetting rubric.
- **[OPEN] Payments/billing** — Stripe for the $750/mo sub + free-3-designs trial → paid conversion. Phase 2.
- **[OPEN] Infra/hosting** — Hetzner VPS (known)? Where the queue/workers/browser run. Headless browser + API cost budget.
- **[OPEN] Brief-as-contract** — exact mechanics of versioning + sign-off freeze + scope-change logging.

---

## Phased roadmap (draft — will refine)

- **P0 — Foundations:** `mimik-contracts` + `mimik-knowledge` skeletons; Suite repo scaffold (FastAPI + Next.js + Postgres + Redis + queue); Tenant/Client/Brand/Job data model + auth.
- **P1 — Brand-brief automation:** URL → scrape (Brandfetch/Firecrawl) → colors/logo/fonts/tone → Brand Brief doc in dashboard. Dogfood on a real Mimik client.
- **P2 — Creative engine v1:** 5-layer checkpoint stack; hybrid render via Playwright; in-app L4 edits; Figma deep-edit export/import; critic + first golden set + evals.
- **P3 — Ops + approval loop:** production board + content calendar + SLA flags; hybrid approval (dashboard + WhatsApp magic-link); auto-archive to Drive; brief freeze/versioning.
- **P4 — Learning loop live:** correction-promotion into prompts/golden-set/rubric; autonomy dial-up per task.
- **P5 — Storefront + billing:** wire mimikcreations.com/unlimited intake → Suite; Stripe; trial→paid.
- **P6+ — Absorb modules:** Sales (acquisition tab), video (mimik-engine), self-serve tier (roadmap upsell for churned clients).

---

## P0 / P1 Build Kickoff (the concrete starting move)

### P0 — Foundations & scaffold
**Package/repo topology** (all sibling folders in `~/workspace`, `pip install -e` in dev):
- `mimik-contracts/` (new pkg) — Pydantic schemas, mirroring ProofKit's `proofkit/schemas/` pattern (reuse/extend `schemas/brand_context.py`). Seed `Brand` from the confirmed `mimik-engine/config/clients/*.json` fields: `name, slug, niche, services[], target_audience, brand_voice, tone_keywords[], dos[], donts[], handles{}`. Add: `Tenant, Client, Brief(version,status,frozen_at), Job(format,publish_date,assignee,status,sla), CreativeDoc(manifest), Layer(L1..L5,recipe), Approval, Delivery, Task, PreferenceProfile`.
- `mimik-knowledge/` (new pkg) — dirs `prompts/` (versioned), `golden/` (exemplars + negatives), `rubrics/`, `evals/` (harness + fixtures), `promote.py` (learning-loop promoter).
- `Mimik_Suite/` (this repo):
  - `api/` — FastAPI + SQLAlchemy/SQLModel + Alembic + Redis + queue (**Arq** recommended for solo simplicity; Celery if preferred). Tenant-scoped auth; **authZ at the data layer** (every query filtered by `tenant_id`).
  - `web/` — Next.js (App Router) shell only. **Do NOT style the UI until a concrete visual reference is in hand** (frontend-design rule).
  - `creative/` — engine pkg: stub the `ImageBackend` adapter (impls: `ChatGPTBrowser`, `GeminiFree`), the Playwright `Compositor`, and the 5-layer `manifest` model.
  - depends on: `mimik-contracts`, `mimik-knowledge`, and `Mimik_Proofkit` (reuse `collector/playwright_capture.py`, `qualify/browser.py`, `figma/`).
- **Governance:** `CLAUDE.md` with locked constraints (schema-first; no `shell=True` w/ untrusted input; never touch `.env*`; no `any` in TS + explicit return types; test stub day 1; phase-tagged commits; tenant authZ at data layer). `HANDOFF.md` + `SESSION_LOG.md`. 7-axis `patterns.md` review on every diff.
- **P0 acceptance:** `docker compose up` → API+Postgres+Redis+queue live; migrations apply; create Tenant/Client/Brand via API; auth isolates tenants (IDOR-negative test passes); contracts import across packages; CI runs tests + pattern-review.

### P1 — Brand-brief automation (first runnable slice, all free/subscription)
1. **Intake** — create `Client` + target URL (manual now; wire to `mimikcreations.com/unlimited` claim form later).
2. **Extract** — scrape via ProofKit's Playwright capture (HTML/CSS/colors/fonts/copy); logo+palette+type from site CSS + a **vision pass on the free Gemini tier** (Brandfetch free tier optional enrichment); snapshot + voice/tone via LLM over copy+socials (CLI subs/free tier).
3. **Assemble** the 9-section Brand Brief — auto-fill §1–5, human fills §6–9. Persist as `Brand` + `Brief` (versioned). Extraction prompt lives in `mimik-knowledge/prompts/`; a small eval fixture (few known brands → expected fields) guards regression.
4. **Sign-off** in dashboard → **freeze + version** (the scope-creep fix).
5. **View** the brief in the dashboard + exportable doc.
- **P1 acceptance:** a URL in → a brand-brief a **real Mimik designer signs off on**, frozen + versioned, on a real client.

### First-week moves (so it gets STARTED, not shelved)
1. `git init Mimik_Suite`; add `CLAUDE.md` + `HANDOFF.md` + patterns discipline.
2. `mimik-contracts` with `Tenant/Client/Brand/Brief` models; `pip install -e`.
3. FastAPI skeleton + Postgres + first Alembic migration + tenant auth + IDOR-negative test.
4. P1 extraction script: URL → Playwright scrape → free-Gemini vision → draft Brand Brief JSON → store.
5. Minimal dashboard route to view + sign off a brief (reference needed before any styling).

## Verification (how we'll know each phase works)

- Dogfood every phase on a **real Mimik/Jasmine client** before it's a "product."
- Evals: a fixed input set with a quality bar; a phase isn't done until evals pass and don't regress.
- P1 acceptance: a URL in → a brand-brief doc a human designer signs off on.
- P2 acceptance: a brief in → a client-grade creative (legible text, exact logo/hex) a human approves with ≤1 nudge.
- P3 acceptance: a full job runs intake→approve→auto-archive with a timestamped audit trail and zero manual Drive upload.
