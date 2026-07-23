# Mimik Suite — Product Manager's Report (top-to-bottom)

> Written 2026-07-23 as a state-of-the-product brief for the operator + any next session. Pairs with
> `HANDOFF.md` (engineering state) and `docs/AUDIT_3PERSONA_PROMPT.md` (the Chrome-extension audit script).

## 1. What the product is (one paragraph)
Mimik Suite is a **done-for-you creative-agency SaaS**. A client is onboarded → their **brand brief
auto-drafts** → a **hybrid 5-layer creative engine** generates social creatives (AI imagery + code-composited
text on a layered SVG master) → an **auto brand-QA critic** clears obvious errors → the team reviews on an
ops board/calendar → the client approves/edits/comments in a **bounded portal** → on approval it
**auto-archives to Drive**. It **learns**: every pick/edit/rejection feeds a per-client preference profile
above a Mimik house-quality floor. Operating model = **assisted autonomy** (guided + recorded). We sell the
**service**, not the tool — we own the whole loop, human-gated. (Pencil/Canva own self-serve tools; we don't
fight them there.)

## 2. Why we're building it
- Agencies bleak margin on the **repetitive middle** of creative ops: drafting briefs, spinning variations,
  chasing approvals, filing deliverables. Mimik automates that middle while keeping a human gate.
- The moat is the **loop + the learning**, not any single generator: owning brief→generate→QA→review→
  approve→deliver→learn, per-client, is what a point tool can't copy.
- Dogfood-first: every phase is validated on a real Mimik/Jasmine client (Glo2Go, Simply Nikah, Island
  Cart) before it's called done.

## 3. The end-product (what "done" looks like)
An operator runs 20+ clients from one cockpit: types "generate 5 Educational posts for Glo2Go this week",
the queue fans out, creatives land on the board, the team nudges them in a **trustworthy editor**, the client
approves in a bounded portal, Drive fills itself, and the per-client taste model measurably improves
hit-rate over time — all auditable, tenant-isolated, and brand-safe.

## 4. Who the users are (personas the audit must adopt)
1. **Operator / Agency owner (primary)** — runs the whole loop; needs speed, a cockpit, trust that edits
   apply and nothing leaks across clients.
2. **Designer / Ops teammate** — generates + edits creatives, moves cards, actions change-requests.
3. **Client (bounded)** — reviews, comments, makes quota-limited edits in a magic-link portal; must NEVER
   see another client's data.
(Secondary QA lenses for the audit: first-time visitor, skeptical investor, mobile-only, accessibility.)

## 5. The core loop (and where each step stands)
| Step | State | Notes |
|---|---|---|
| Onboard client + auto-draft brand brief | Built (needs persona QA) | `/onboarding`, brand kit editor |
| Generate creative (5-layer engine, all 3 clients) | Built + live | Glo2Go/Island Cart/Simply Nikah all 200; queue+worker (A-03/04) |
| Auto brand-QA critic | Partial | design-rules/flywheel exists; not a hard gate yet |
| Ops board + calendar + SLA | Built | drag-transitions (A-06), calendar (A-07 pending), queue/usage endpoints |
| **In-product canvas editor** | **Rebuilt this session — Gates 1–4a done** | see §6 |
| Client bounded portal (approve/edit/comment) | Built (B-11/B-12) | quota-limited client revise; persona QA pending |
| Approve → auto-archive to Drive | Built | `approval_flow` → Delivery |
| Learn (per-client preference profile) | Built (signals) | flywheel captures edits/approvals/reverts (B-13) |
| Command Center ⌘K ("generate 5 …") | Backend pending (A-05) | queue/usage endpoints live; parser + bar remaining |

## 6. The canvas editor — audit said 13/40; rebuilt this session
Full 4-gate rebuild (safe-template-editor direction, NOT a Figma clone). **All browser-verified via
Playwright.**
- **Gate 1** — one canonical state; recolor/hide/text/drag/discard all preview correctly (root-cause fix:
  imperative SVG injection so React can't wipe live edits).
- **Gate 2** — undo/redo, pending-op list + per-op remove, before/after, safe revert + real version labels.
- **Gate 3** — right inspector (controls off the canvas), full-screen, zoom/fit/100%, creative-size display,
  per-layer reset, "Ask AI about this layer".
- **Gate 4a** — resize from ALL 8 handles (non-uniform, anchor-opposite, smooth) + backend render.
- **Just fixed** — Apply no longer 422s on resize (scale clamped at the payload boundary).

## 7. What is NOT yet implemented (the honest gap list — operator asked)
**Editor (Gate 4b + editor polish):**
- Rulers · margins / safe-area overlay · snapping guides — NONE yet.
- **Rotation handle** (contract + render already support rotation; only the UI/rotated-overlay remains).
- Layer tree (reorder/lock/rename/duplicate), align/distribute, multi-select, keyboard nudge/copy/paste.
- **Creative SIZE / aspect-ratio selection** (1:1, 4:5, 9:16 story, etc.) — NOT a resize; changing format
  means re-composing/re-generating at the new dimensions. This is a **product decision** (offer a format
  switcher that re-renders the layout at the new aspect) — currently a creative has ONE format from
  generation.
- **Custom colours beyond the brand palette** — deliberately constrained today (recolor is bounded to the
  brand tokens for brand-safety, a LOCKED constraint). The ask ("more custom colours") is a **product
  decision**: add a "brand + custom" mode (e.g. tints/shades of brand colours, or an unlock for team-only)
  without breaking client-facing brand-safety.

**App shell / UX (operator's live feedback — real issues):**
- **Nav rail is icon-only** → add labels/expand-on-hover or a labeled nav; "just icons" is a discoverability
  miss.
- **The client sidebar ("All clients") shows while editing** → the editor should collapse app chrome by
  default (full-screen exists but isn't the default); the editing view doesn't need the client list.
- **Contextual chrome** generally — judge every view: hide what the current task doesn't need.

**Command Center:** A-05 (⌘K parser + bar), A-08 (queue panel UI), A-09 (command bar UI).
**Deferred W4:** A-07 calendar SLA, A-11 deliveries surface, B-12 portal editor polish, gates A-12/B-14.

## 8. Cross-client visibility — the operator's "why are all clients always seen?"
Two different things, don't conflate:
1. **Sidebar client LIST** (Simply Nikah / Glo2Go / Island Cart) — these are the OPERATOR's OWN clients
   within ONE tenant (agency). A team member legitimately sees all their agency's clients. That is correct
   and NOT a leak. The UX issue is only that it's shown in the *editor* where it's not needed (§7).
2. **Cross-CLIENT data in a creative** — the earlier "Simply Nikah header on a Glo2Go creative" was a
   display bug (fixed in Gate 1: the editor now shows the creative's OWN client). Server-side, a **client**
   principal can only ever see its own data (tenant + client scope enforced at the data layer; IDOR test is
   green). So: operators see all their clients (by design); clients see only themselves (enforced).

## 9. Recommended next moves (priority order)
1. **Run the 3-persona product audit** (`docs/AUDIT_3PERSONA_PROMPT.md`) end-to-end to get a ranked issue
   list from the correct POVs — before building more.
2. **App-shell UX pass**: labeled/expandable nav; editor collapses client chrome by default; per-view
   "what does this task need?" cleanup.
3. **Gate 4b**: rotation handle → rulers/margins/guides/snap → layer tree → multi-select/shortcuts.
4. **Product decisions** (need operator sign-off): (a) aspect-ratio/format switcher (re-render at new size);
   (b) "custom colours" mode without breaking client-facing brand-safety.
5. **Command Center** A-05/A-08/A-09 (the ⌘K cockpit).
6. Persona/Supabase auth so client-role QA is real; THEN consider deploy (currently HELD).

## 10. Constraints that never bend (from CLAUDE.md)
Schema-first · tenant authЗ at the data layer (IDOR → 404) · client freeform text is DATA never a system
prompt · never touch secrets · non-destructive versioning + audit · SVG is the one layered master · no `any`
/ explicit return types · frontend on the locked Studio-Admin design system.
