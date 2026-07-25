/**
 * Brand Kit v2 — chapter furniture shared by every section component.
 * All markup stays scoped under `.bk-canvas` (see brand-kit.css).
 */

import type { JSX } from "react";

/** True when a nullable wire string actually carries text. */
export function filled(value: string | null | undefined): value is string {
  return value !== null && value !== undefined && value.trim() !== "";
}

export function SectionHead({ kicker }: { kicker: string }): JSX.Element {
  return (
    <div className="bk-sec-head">
      <span className="bk-kicker">{kicker}</span>
      <span className="bk-rule" />
    </div>
  );
}

/**
 * A chapter that hasn't been built/filled yet — typeset, calm, never broken (spec §5).
 * Doubles as the CLIENT view's collapsed state for a sparse chapter (rule 1: a tab with
 * fewer than two filled fields shows this single neutral card).
 */
export function PlaceholderChapter({
  number,
  label,
}: {
  number: string;
  label: string;
}): JSX.Element {
  return (
    <>
      <SectionHead kicker={`Chapter ${number} — ${label}`} />
      <div className="bk-ghost-chapter">
        <span className="bk-fleur">❦</span>
        <p>This chapter is being written</p>
        <em>arriving with your next review</em>
      </div>
    </>
  );
}

/** Tier-1 empty state (spec §5, STUDIO only) — a dashed ghost card with a muted, typeset prompt. */
export function GhostCard({ hint }: { hint: string }): JSX.Element {
  return (
    <div className="bk-ghost">
      <span className="bk-ghost-hint">{hint}</span>
    </div>
  );
}
