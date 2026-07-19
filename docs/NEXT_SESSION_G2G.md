# Next session — Brand-memory ingestion + Glo2Go (G2G) dogfood

> Read this first, then `HANDOFF.md` (top entry). This is the plan to turn "the plumbing works"
> into "the output is on-brand," dogfooded on a real client: **Glo2Go Aesthetics**.
> The loop prompt to paste is at the bottom.

## Why this session exists

P0–P5 are built and green (222 tests). But the quality flywheel has never turned — golden set
empty, ranker has zero real signals, no per-brand Asset Library, no imagery generated, nothing
dogfooded. This session builds the **brand-memory ingestion slice** (the one missing piece) and
proves it end-to-end on **Glo2Go**, a real Mimik client with a real brief + real past creatives.

## The real client: Glo2Go Aesthetics

> **Source of truth = the LIVE website + socials, NOT the old Drive docs.** The brand has moved on
> since the Drive brief/creatives were made — treat those as a *style headstart only*, not current
> fact. The deliverable this session is a **fresh, better brief + marketing plan + content pillars**
> generated from the current site + socials, then human-refined. We do **not** need the old
> content-planner spreadsheet — the app's calendar + pillars replace it.

### Current brand (from the live site — 2026, source of truth)

**https://glo2goaesthetics.co.uk/** · IG `@glo2goaesthetics` · TikTok `@g2g.aesthetics` · FB glo2goaesthetics.

- **Positioning (current):** premium London aesthetic clinic — **"luxury, expertise, and affordability."**
  State-of-the-art tech, expert practitioners, "your satisfaction is our top priority." (Note the
  *affordability* angle is newer than the old brief's "personalized/results-driven".)
- **Location:** 36 St Mary at Hill, London EC3R 8DU.
- **Current treatments (richer than the old brief):** PRP Hair Regrowth · **Polynucleotides** ·
  Microneedling (with PRP / PDRN / Vitamin C / HA) · Dermal Fillers (jawline, cheeks, tear-trough,
  lips) · Anti-Wrinkle (forehead, crow's feet, masseter, gummy smile) · **Fat Dissolving (Aqualyx,
  Lemon Bottle)** · Skin Rejuvenation · Wellness Therapies · Glutathione.
- **Voice:** professional yet approachable; confident, reassuring; premium-but-accessible.
- **Content pillars to propose (derive fresh, human-confirm):** e.g. Treatment Education, Before/After
  Social Proof, Offers/Promotions, Wellness/Glow lifestyle, Trust/Expertise. Confirm with the operator.

The first build move for G2 is to run these through the **P1 brief extractor** (URL → §1-5, SSRF-guarded)
+ the new vision pass, then draft a **better brief + marketing plan + pillars** on top — not to copy the
old doc.

### Drive — style headstart only (may be dated)

The `Clients/` folder has ~28 clients; G2G's past creatives are a **style-continuity reference** for the
fit-critic (how designs looked before), NOT the current source of truth. Old visual: deep purple/violet
+ lavender on white, circular badge logo, before/after + educational explainers + checklists — useful to
seed the style anchor, but confirm against the current site before trusting it.

**Access:** the claude.ai Google Drive MCP reads these interactively (used to scout them). For the
PRODUCT path, the service account (key at `secure repo/…json`, gitignored) needs **`drive.readonly`
scope + the Clients folder shared to its email** to read existing creatives (its archive scope
`drive.file` only sees files IT creates — decision below).

| Item | Drive ID |
|---|---|
| Clients root | `1zQ4ckT2qighpRz4QdqWY4lIC5IqJgzkf` |
| **Glo2go** client folder | `1FMKEjFuzPXkjBcYg3wfOOXYqGGhPQLiS` |
| **Glo2Go Brief** (Google Doc) | `1U_Wcml8VxHMVdEGfTb1dqOEZktJuR6Dl-ChEVM06lQA` |
| Glo2Go Aesthetics Marketing Plan (Doc) | `17b9x_lEgENV5rQULfwqpcAE6pthh9zFUhbLoERMp29A` |
| Content planner (Spreadsheet) | `1lfcIxPt4SbYfKnvORfqw3LmvDbnx8AVBdm5h75IL5-s` |
| 2025 → 1. January → Posts | `1nGVxIq2Ome73s3KqREGRQBEwuvtf0sH6` |
| Sample creative — Glutathione v7 | `1e6mCUVA36iISb_PhsnZCbwnWsA7lYAHa` |
| Sample creative — Glow & Wellness | `1wHKfcKHPfJ9ult5-C2K_ox8SqUxgtqEd` |
| Sample creative — Hair Growth PRP | `1Hs7LflKjvsmJVI_-wMFP2rp4LqpkF37C` |
| Sample creative — Fat loss transformation | `13mdJtOfujxZT5Rro4nm6CSbeO0eBcRzS` |

## What to build

### G1 — Brand-memory ingestion (the missing slice)

1. **Asset Library** (`mimik-contracts` + ORM + repo + migration): a `BrandAsset` model —
   `kind` (logo | font | imagery | reference_creative), `drive_file_id`, `local_path`, `mime`,
   `approved`, `license`, `notes`. Team upload endpoint + a Drive-pull path. The compositor renders
   from the **approved logo** (wire `Brand.tokens.logo.ref` to the stored asset).
2. **Vision pass on the free Gemini tier** — wire the deferred `_vision_pass` seam. Free Gemini
   `gemini-flash-latest` does **image understanding for free** (only image *generation* needs
   billing). Use it to: (a) extract exact palette + logo assessment for the brief §2/§3, and
   (b) study a reference creative → a `StyleDescriptor` + an inferred copy/voice sample.
3. **Reference-creative ingestion** — take N liked creatives (Drive IDs or uploads) → vision pass →
   run through the existing **reference fit-critic** → attach to `Brand.references` (style anchor)
   **and** seed positive `PreferenceSignal`s (attributes from the creative) so the taste-ranker has
   real data. Team-review gate before any golden promotion (never auto).
4. **Copy-voice golden** — store the client's approved past copy (from creatives / the brief) as
   golden exemplars so the L0 copy prompt few-shots from them → new copy matches Glo2Go's voice.

### G2 — Glo2Go onboarding + dogfood (the proof)

5. **Draft a FRESH, better brief from the live site + socials** (not the old Drive doc): run
   `https://glo2goaesthetics.co.uk/` through the P1 extractor + vision pass → auto §1-5 → human-refine
   §6-9. Extract exact brand hex from the current logo/site (vision), current voice + do/don'ts, and
   the current treatment list. Create the **Glo2Go client + brand** from THIS.
6. **Generate a better marketing plan + content pillars** for G2G (from the current positioning —
   "luxury, expertise, affordability" — and the treatment list). Persist the pillars as
   `ContentPillar`s on the client. Operator confirms. (No content-planner spreadsheet — the app's
   calendar + pillars are the plan.)
7. Ingest **3–5 past G2G creatives** (Drive sample IDs above) as the **style anchor only** — run each
   through the vision + fit-critic → style descriptor + seed preference signals. Flag them as
   possibly-dated; the current site wins on any conflict.
8. **Generate a NEW G2G creative** for a current topic (e.g. Polynucleotides or Skin Rejuvenation):
   free-Gemini copy few-shot from the fresh G2G voice → **placeholder brand ground (free)** first to
   prove the loop, then optionally a **real `gpt-image-2` background (paid, operator-gated)** →
   brand-QA → you review/approve → archive.
9. **Compare** the generated creative against the current brand (site + a past creative for style) —
   on-voice? on-look? That human judgment is the real gate.

### G3 — Eval fixture + real Drive archive

10. First **eval fixture** in `mimik-knowledge/evals/`: the G2G site → expected brief fields (no
    fabrication) — the regression guard.
11. Wire the **real Google Drive archive** (SA now configured): confirm scope, share the archive
    folder to the SA, set `ARCHIVE_BACKEND=google_drive` + `GOOGLE_SERVICE_ACCOUNT_JSON` +
    `DRIVE_ROOT_FOLDER_ID`, run one approve→archive to Drive for real.

## Decisions to make in-session

- **Drive read scope.** Archive uses `drive.file` (write-only to files it creates). Reading existing
  client creatives needs `drive.readonly` (or `drive`) + the Clients folder shared to the SA email.
  Decide: broaden the SA scope for reads, OR keep the SA archive-only and pull reference creatives
  via the interactive MCP during dogfood. Recommendation: SA `drive.readonly` for the product path.
- **Vision cost.** Confirm free-tier Gemini vision limits are enough for per-creative study (should be).
- **Reference fit-critic currently takes TEXT `reference_meta`.** Extend it (or add a vision front-end)
  so it can score an actual image, not just scraped metadata.

## Acceptance gates

- **G1:** upload/pull a logo + N reference creatives for a brand → assets stored + a StyleDescriptor +
  ≥N preference signals recorded; compositor renders from the stored logo; pytest green; vision pass
  runs on the free tier (mocked in tests, one live smoke).
- **G2:** a NEW Glo2Go creative generated on free grounds passes brand-QA and reads as on-brand vs the
  real creatives (human judgment) with ≤1 nudge; the taste-ranker uses the seeded signals.
- **G3:** eval fixture green + one real approve→Drive archive with a timestamped audit trail.

## Human gates (pause for the operator)

- **SA read scope** — confirm broadening to `drive.readonly` + folder shared (or use MCP for dogfood).
- **Real paid image** — explicit go-ahead before any `gpt-image-2` call (`MIMIK_ALLOW_PAID_IMAGES=1`);
  prove the loop on free placeholder grounds first.
- **Design references** — for any NEW portal/asset-library UI, get a visual reference first
  (`web/design/tokens.css` is the baseline).
- **Commit/deploy** — commit on request (this session's convention: commit yes, push waits).

## Current state (recap)

- 222 tests green, ruff clean; contracts 11, knowledge 5. Migrations head `b08ff128c47c`.
- All P0–P5 built. Supabase auth live. Stripe built-but-mocked (dormant, 503 without keys).
- Image model set to `gpt-image-2` (top tier), spend-gated. SA key present + gitignored.

## THE LOOP PROMPT (paste into a fresh session)

> /loop Build the Glo2Go brand-memory ingestion + dogfood for Mimik Suite, per
> `docs/NEXT_SESSION_G2G.md` (read it first, then `HANDOFF.md` top entry, `CLAUDE.md`,
> `~/.claude/plans/hi-i-want-to-sunny-fox.md`). Verify state: `docker compose up -d` then
> `uv run --no-sync pytest` = 222 green. The Google Drive MCP can read my `Clients/Glo2go` folder
> (IDs in the plan) — use it to pull the real brief + reference creatives. Build phase by phase:
> **G1** brand-memory ingestion (Asset Library + free-Gemini vision seam + reference-creative
> ingestion into the fit-critic/preference/golden systems + copy-voice golden), **G2** onboard
> Glo2Go from its LIVE SITE https://glo2goaesthetics.co.uk/ + socials (source of truth — draft a
> BETTER brief + marketing plan + content pillars, NOT the old Drive doc; use the ~3–5 past Drive
> creatives as a style headstart only) + generate ONE new on-brand creative (free placeholder ground
> first) and compare against the current brand, **G3** first eval fixture + wire the real Google
> Drive archive. Fan independent work to subagents; run code-reviewer/
> security-reviewer before each gate; advance only when green; update HANDOFF + SESSION_LOG inline.
> Honor every constraint (uv run --no-sync; tenant authZ at the data layer; secrets only in .env —
> the SA key is at `secure repo/…json`, gitignored; managed auth never self-rolled; free Gemini for
> text+vision, NO paid image without my explicit go-ahead). Pause at the human gates (SA read scope,
> any paid image, design references, commit/deploy). Tell me exactly which .env values / Drive
> shares you need before each step.
