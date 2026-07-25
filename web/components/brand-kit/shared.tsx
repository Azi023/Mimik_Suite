/**
 * Brand Kit v2 — chapter furniture shared by every section component.
 * All markup stays scoped under `.bk-canvas` (see brand-kit.css).
 */

"use client";

import { useEffect, useState, type JSX } from "react";
import type {
  ApiBrandDiscoveryTextField,
  ApiCreativeDirectionTextField,
} from "@/lib/api";

export type BrandKitTextTarget =
  | { section: "discovery"; field: ApiBrandDiscoveryTextField }
  | { section: "direction"; field: ApiCreativeDirectionTextField };

export type SaveBrandKitTextField = (
  target: BrandKitTextTarget,
  value: string | null,
) => Promise<void>;

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

interface EditableTextFieldProps {
  label: string;
  value: string | null | undefined;
  displayValue?: string | null;
  hint: string;
  target: BrandKitTextTarget;
  onSave: SaveBrandKitTextField;
  compact?: boolean;
}

/** Studio-only click-to-edit text field with local save/cancel/error state. */
export function EditableTextField({
  label,
  value,
  displayValue = value,
  hint,
  target,
  onSave,
  compact = false,
}: EditableTextFieldProps): JSX.Element {
  const source = value ?? null;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!editing) setDraft(value ?? "");
  }, [editing, value]);

  const nextValue = draft.trim() === "" ? null : draft.trim();
  const unchanged = nextValue === source;

  function beginEdit(): void {
    setDraft(value ?? "");
    setError(null);
    setEditing(true);
  }

  function cancelEdit(): void {
    setDraft(value ?? "");
    setError(null);
    setEditing(false);
  }

  async function saveEdit(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await onSave(target, nextValue);
      setEditing(false);
    } catch {
      setError("Could not save this field. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!editing) {
    const hasDisplay = filled(displayValue);
    return (
      <button
        type="button"
        className={`bk-inline-trigger${hasDisplay ? "" : " bk-inline-trigger--ghost"}${
          compact ? " bk-inline-trigger--compact" : ""
        }`}
        onClick={beginEdit}
        aria-label={`Edit ${label}`}
      >
        <span>{hasDisplay ? displayValue : hint}</span>
        <span className="bk-inline-edit-mark" aria-hidden="true">
          Edit
        </span>
      </button>
    );
  }

  return (
    <div className={`bk-inline-editor${compact ? " bk-inline-editor--compact" : ""}`}>
      <textarea
        autoFocus
        aria-label={label}
        rows={compact ? 2 : 4}
        value={draft}
        disabled={busy}
        onChange={(event) => setDraft(event.target.value)}
      />
      <div className="bk-inline-actions">
        <button
          type="button"
          className="bk-btn bk-btn--primary"
          disabled={busy || unchanged}
          onClick={() => void saveEdit()}
        >
          {busy ? "Saving…" : "Save"}
        </button>
        <button type="button" className="bk-btn" disabled={busy} onClick={cancelEdit}>
          Cancel
        </button>
      </div>
      {error !== null && (
        <p className="bk-inline-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
