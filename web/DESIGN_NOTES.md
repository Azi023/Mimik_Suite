# Mimik Suite Web — Design Notes

## Reference (operator-approved)

Conceptzilla — **"Team Management Dashboard"**, Dribbble shot `19198544`.

- Local copy: `/private/tmp/claude-502/-Users-atheeque-workspace-Mimik-Suite/41efe422-4b5a-45a2-bd22-12fc7fe01866/scratchpad/dribbble_ref.png`
  (scratchpad is session-scoped — re-download from the CDN if missing)
- CDN: https://cdn.dribbble.com/userupload/3349890/file/original-54964eaa6cba4961bb0493df2f5e1249.png

Design language reproduced: near-white canvas + pure-white surfaces, two-tier
sidebar (icon rail + client list), kanban with status-dot column heads,
white cards on soft diffuse shadows (no hard borders in light), saturated-pastel
tag pills with white text, circular checklist rows, overlapping avatar stacks,
right slide-in detail pane. Light is the flagship theme; dark is a ground/ink
swap only.

## Token system — `design/tokens.css`

Single source of truth. **No literal hex values outside this file** — every
color, radius, shadow and spacing step in `app/globals.css` and components is
a `var(--…)` reference. Light lives on `:root`, dark on `[data-theme="dark"]`
(applied pre-paint by `app/theme-script.ts`, toggled by `ThemeToggle`).

| Group | Tokens | Notes |
|---|---|---|
| Ground | `--canvas` `--surface` `--surface-2` `--surface-3` `--line` `--card-border` | canvas `#F5F6F8`, surfaces pure white. `--card-border` is transparent in light (cards float on shadow) and a hairline in dark (shadows vanish on dark grounds). |
| Ink | `--ink` `--ink-2` `--muted` `--faint` | headings `#1A1D26` at 600–700; secondary `#8A8F98`. |
| Accent | `--accent` `--accent-hover` `--accent-soft` `--accent-ink` | primary blue `#3B82F6`; `--accent-soft` is the active-nav tint. |
| Tags | `--tag-blue/green/orange/pink/purple/gray` | saturated pastel pill fills, white text. Shared by tags, avatars, and sidebar shape markers (`FORMAT_TONE` / `PILLAR_TONE` / `Assignee.tone` in `lib/mock.ts` map onto these). |
| Status dots | `--dot-new` (red) `--dot-progress` (orange) `--dot-done` (green) | kanban column heads + status pills. |
| Shape | `--r-lg 16` `--r-md 14` `--r-sm 10` `--r-xs 8` `--r-full` | cards `--r-md`, panel `--r-lg`, buttons/inputs `--r-sm`. |
| Elevation | `--shadow-card` `--shadow-lift` `--shadow-pop` `--shadow-panel` | card rest = `0 2px 8px rgba(20,20,43,.06)`; lift = hover; panel = the right pane. |
| Spacing | `--sp-1…--sp-8` | 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 px. |
| Type | `--font-sans` | Inter via `next/font` (`--font-inter` variable set on `<html>` in `app/layout.tsx`), system fallbacks. |

## Motion — `lib/motion.ts`

GSAP helpers, all typed, all no-ops under `prefers-reduced-motion`:

- `staggerFadeUp(targets, opts?)` — first-paint card entrance (0.4s, power2.out,
  40ms stagger). Wired in `Board.tsx` via `[data-animate="card"]`.
- `slideInPanel(target, delay?)` — right detail pane entrance (0.5s, power3.out).
  Wired in `ReviewPanel.tsx`.
- `animateCount(el, to)` — column-count tick-up. Wired via `[data-count]`.

Card hover micro-scale is CSS-only (`.job-card:hover`, gated behind
`(hover: hover) and (prefers-reduced-motion: no-preference)`). A global
reduced-motion guard in `globals.css` also flattens all CSS transitions.
House rules: no scroll-jacking, no parallax.

## Layout skeleton

`AppShell` → fixed viewport frame (`height: 100dvh`, board area scrolls
internally): `Sidebar` (`.rail` 68px + `.subbar` 240px) · `.app-main`
(`TopBar` + `.app-content`) · page composes `.board-view` = scrollable main
column (PillarChips + kanban `Board`) + `ReviewPanel` (340px, rounded-left,
`--shadow-panel`). Breakpoints: ≤1280 narrower panel, ≤1100 panel drops below
the board, ≤860 sidebar collapses to the TopBar hamburger and the kanban
stacks to one column.
