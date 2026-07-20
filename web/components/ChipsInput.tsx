"use client";

import { useState, type JSX } from "react";

interface ChipsInputProps {
  items: string[];
  onChange: (items: string[]) => void;
  placeholder: string;
  /** Chip tint — reuses the brief do/don't/neutral chip styles. */
  tone?: "do" | "dont" | "neutral";
}

/** A small add/remove chip list — shared by the brief editor's guardrails and the onboarding
 *  wizard (tone keywords, do's, don'ts). Enter or the Add button commits; duplicates are ignored. */
export function ChipsInput({ items, onChange, placeholder, tone = "neutral" }: ChipsInputProps): JSX.Element {
  const [draft, setDraft] = useState("");

  function add(): void {
    const v = draft.trim();
    if (v === "") return;
    if (!items.includes(v)) onChange([...items, v]);
    setDraft("");
  }

  function remove(item: string): void {
    onChange(items.filter((i) => i !== item));
  }

  return (
    <div className="brief-list">
      {items.length > 0 && (
        <ul className="brief-chips">
          {items.map((item) => (
            <li key={item} className={`brief-chip brief-chip--${tone}`}>
              <span>{item}</span>
              <button
                type="button"
                className="brief-chip__x"
                aria-label={`Remove ${item}`}
                onClick={() => remove(item)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="brief-list__add">
        <input
          className="input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={placeholder}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <button type="button" className="btn-ghost" onClick={add} disabled={draft.trim() === ""}>
          Add
        </button>
      </div>
    </div>
  );
}
