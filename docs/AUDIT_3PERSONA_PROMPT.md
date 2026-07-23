# 3-Persona Product Audit — Chrome-extension prompt (paste this into Claude-in-Chrome)

> Runs a full end-to-end audit of Mimik Suite at http://localhost:3000 (API on :8000). Read
> `docs/PRODUCT_PM_REPORT.md` first if you want product context. Paste everything below the line.

---

You are auditing **Mimik Suite**, a done-for-you creative-agency SaaS, running locally at
**http://localhost:3000** (backend :8000). Your job: drive the ACTUAL product in the browser end-to-end and
produce a **ranked, evidence-backed issue report** — from the correct point of view at each step. Do NOT just
read code; CLICK through it and judge what you see.

## Safety / rules
- This is the operator's own local dev instance — you are authorized to interact with it.
- Use TEST data only (e.g. client "AUDIT-TEST", throwaway topics). Do not touch real client records if
  present beyond viewing.
- **Apply** (canvas Save) is now fixed and safe to test — it re-renders a version, no external spend.
- **AVOID "Queue ask" / any AI-generation button** unless explicitly needed — those may consume paid credits.
  If you test AI generation, do it ONCE and say so.
- If a page 500s, note it (a stale build); don't get stuck — move on and report it.

## The three primary personas (adopt each POV explicitly; label every finding with the persona who'd hit it)
1. **Operator / agency owner** — runs 20+ clients; cares about speed, a cockpit, trust that edits apply,
   and that nothing leaks across clients.
2. **Designer / ops teammate** — generates + edits creatives, moves board cards, actions change requests.
3. **Client (bounded)** — reviews/comments/edits in a magic-link portal; must never see another client.
Secondary lenses to apply while walking: **first-time visitor**, **skeptical investor**, **mobile-only**
(also resize the window to 375px on key pages), **accessibility** (keyboard-only + labels), **returning user**.

## Walk the FULL loop and judge each view (does this view show only what the task needs?)
For EVERY screen, ask: is the chrome contextual? are all visible controls actually wired (or dead/hover-only)?
is the nav discoverable (the rail is icon-only today — is that a problem)? does it work on mobile? any
console errors? Record concrete evidence (what you clicked, what happened, a screenshot when useful).

1. **First impression / board** (`/`) — as a first-time visitor + investor: is it obvious what this is and
   what to do first? Try the nav rail icons (do they all go somewhere?). Try dragging a board card between
   columns (does it persist? snap back on illegal moves?).
2. **Onboard a new client** (`/onboarding` or "New client") — as the operator: complete the flow for
   "AUDIT-TEST". Judge the brand-brief / brand-guideline questions: are they clear, is anything missing that
   a real brand brief needs (voice, do/don't, palette, logo, audience)? Does it save?
3. **Client + brand kit** (`/clients`, `/clients/[id]/edit`, brand kit) — verify what you entered persisted;
   check the brand palette/tokens.
4. **Generate a creative** — from the board, generate ONE creative for a client (real generation; do it
   once). Does it appear on the board and in review?
5. **Review panel + `/creatives` gallery** — open a creative's review; find the "Open in editor" path; open
   the `/creatives` gallery.
6. **CANVAS EDITOR** (`/creatives/[id]/edit`) — the centerpiece; test EVERYTHING and rate how it FEELS:
   - Select a layer (click on it); does the right layer select? Hover feedback?
   - **Move** (drag) a layer. **Resize from ALL 8 handles** (4 corners + 4 edges) — does each side resize
     smoothly and anchor the opposite side? Any jank?
   - **Recolor** from the brand palette — does the artwork change immediately? (It should.) Is the palette
     enough, or do you need custom colours?
   - **Hide/show** a layer (eye) — does it actually hide?
   - **Edit text** (double-click a text layer) — does it update live? Multi-line? Escape cancels?
   - **Undo/Redo** (buttons + ⌘Z/⇧⌘Z), the **pending-op list** (remove one op), **Before/After** press-hold.
   - **Zoom / Fit / 100%**, **full-screen**, the **creative size** display, **per-layer Reset**.
   - **Apply** — does it save and produce a new version WITHOUT the "rejected as invalid" error? Check the
     **Versions** rail (are labels meaningful, not V1/V1/V1?) and **Revert**.
   - Judge the LAYOUT: is the "All clients" sidebar necessary while editing? Are controls reachable without
     scrolling? What's MISSING that a real editor needs (rulers, margins/safe-area, guides/snap, rotation,
     aspect-ratio/size switch, layer tree, alignment)? Rate the editor's usability /10 with reasons.
7. **Approve → delivery** — approve a creative (as operator/designer); confirm it appears under
   `/deliveries` with a Drive path (or an honest "archive pending" state).
8. **Client portal** (`/portal`) — if reachable, adopt the CLIENT persona: confirm they can ONLY see their
   own creative and can make a bounded edit; confirm they never see other clients.
9. **Cross-cutting**: dead buttons anywhere? nav labels? 404s? hydration/console errors? mobile (375px)
   breakage? Confirm the earlier fixes held (Invite→/members, board drag, gallery, no bare 404).

## Output — a single ranked report
Group findings **P0 (blocks a demo) → P1 → P2 → P3 (polish)**, most severe first. For EACH finding give:
**persona** who hits it · **screen + what you did** · **what's wrong (evidence)** · **why it matters** ·
**fix direction**. Then:
- A **feature-completeness table** for the editor (implemented / partial / missing) covering: select, move,
  8-handle resize, recolor, custom colour, hide, text edit, undo/redo, op-list, before/after, zoom, full-
  screen, size display, **aspect-ratio switch**, **rulers**, **margins/safe-area**, **guides/snap**,
  **rotation**, **layer tree**, **align/distribute**, **multi-select**, apply, versions, revert.
- A **"does each view show only what it needs?"** verdict per screen (esp. the editor's client sidebar +
  the icon-only nav).
- Your top 5 highest-leverage fixes.
Be concrete and honest; the goal is a fix checklist an engineer can act on. Do NOT invent issues; only
report what you actually observed.
