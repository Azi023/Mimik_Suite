# Plan — In-Product Editor ("the canvas") + Command Center

> Draft for build (to be executed by Codex/agy under Claude's spec + review). Two features that make the
> product feel complete: (1) editing a generated creative *inside the product*, and (2) the ops cockpit.

## Part 1 — In-product editor (bounded, AI-assisted; NOT a Canva clone)

**Why it's feasible now:** our creative is already a **layered SVG with live `<text>` + named layers**
(background / panel / headline / subhead / cta / badge). That is directly editable in the browser — no
custom raster engine needed. Locked plan (PLAN.md) = Tier-1 edits + prompt-for-changes + annotate, NOT a
full canvas editor (Canva's moat). This plan honours that.

**Who edits:** team (owner/ops/editor) AND the client — same editor, **role-bounded** (client = their own
creatives only, quota-limited, guarded; the tenant-authZ + injection rules already locked apply).

**What the editor does (real-time):**
- **Direct manipulation** on the SVG layers: move/resize the panel, reposition the logo/badge, edit headline/
  sub/CTA text inline, swap the background photo, recolor within brand palette, toggle layer visibility.
- **"Mark & tell AI"** (the Claude-design-style flow): select/point at a region or layer → type an instruction
  ("make the logo lighter", "move text off her face", "smaller panel, left") → the request is a **guarded
  change-request** → the engine re-renders (art-director + templates read `creative/knowledge` rules) → the
  new version streams back. Client freeform text is DATA, never merged into a system prompt (locked constraint #3).
- **Non-destructive versioning:** every edit = a new CreativeDoc version (revert anytime); actor + ts audited.
- **Export** the edited result: SVG (master) + PNG (preview) + PSD (layered raster).

**Build phases:**
1. **Render + inspect** — show the SVG in the review panel; click a layer → highlight + its props.
2. **Direct edits** — inline text edit + drag/move + palette recolor → persist as a new version (server re-renders
   or client-side SVG DOM edit committed back).
3. **Mark & tell AI** — selection + instruction → guarded change-request endpoint → engine re-render → diff/version.
4. **Client-bounded mode** — role gating, quota, guardrail enforcement, comment/annotate + task creation for ops.

**Feeds the flywheel:** every AI-assisted edit + every accept/decline records into `creative/knowledge` (M5),
so the design brain keeps improving from real edits.

## Part 2 — Command Center (ops cockpit)

**What:** the internal surface to run the whole loop — the Kanban board (Brief→Generating→Internal review→
Client review→Approved→Delivered) already scaffolded, plus: content **calendar + SLA** (flag at-risk jobs),
**generation queue + budget** view, **client/tenant admin** (accounts, roles), **delivery/archive** status,
and a **command bar** ("generate 5 posts for Glo2Go this week on the Educational pillar") that fans work out.

**Execution model (as agreed):** Claude/Opus writes the full spec → handed to **`agy`** (Antigravity, Gemini 3.1
Pro High) which executes the build → Claude reviews. This is the one big chunk reserved for agy.

**Gate:** after the in-product editor + a working generate flow land (so the cockpit has real jobs/creatives to
orchestrate). Sequence: generate flow → editor → Command Center → deploy.

## Not doing (locked)
- No full freeform canvas/vector editor (Canva's moat). Deep edits export to SVG/Figma.
- PSD live-text (rasterized in v1; SVG is the live-text master).
