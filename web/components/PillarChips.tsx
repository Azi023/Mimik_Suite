"use client";

import { useState, type JSX } from "react";
import type { Pillar } from "@/lib/view-models";

interface PillarChipsProps {
  pillars: Pillar[];
  /** Id of the pillar whose jobs are currently shown (`ALL_PILLARS` = show everything). */
  activePillarId: string;
  /** Fired when a real (non-custom) pillar chip is selected. */
  onSelect: (pillarId: string) => void;
}

/** Sentinel filter value: the "All" default that shows every job. */
export const ALL_PILLARS = "__all__";

/**
 * Row of content-pillar chips — the board's client-side filter control. Selecting
 * a pillar narrows the visible cards to that pillar; the "All" chip clears it.
 * The active pillar is the single lime pop; the "+ Custom" entry is a dashed
 * add-affordance that (for now) reveals an honest "coming soon" hint rather than
 * a dead click — creating custom pillars is a later API phase.
 */
export function PillarChips({ pillars, activePillarId, onSelect }: PillarChipsProps): JSX.Element {
  const [showCustomHint, setShowCustomHint] = useState(false);

  return (
    <div className="pillar-chips" role="group" aria-label="Content pillars">
      <button
        type="button"
        className={`pillar-chip${activePillarId === ALL_PILLARS ? " pillar-chip--active" : ""}`}
        aria-pressed={activePillarId === ALL_PILLARS}
        onClick={(): void => {
          setShowCustomHint(false);
          onSelect(ALL_PILLARS);
        }}
      >
        All
      </button>

      {pillars.map((pillar) => {
        if (pillar.custom === true) {
          return (
            <button
              key={pillar.id}
              type="button"
              className="pillar-chip pillar-chip--custom"
              aria-disabled="true"
              aria-describedby={showCustomHint ? "pillar-custom-hint" : undefined}
              onClick={(): void => setShowCustomHint((open) => !open)}
            >
              {pillar.label}
            </button>
          );
        }

        const active = activePillarId === pillar.id;
        const className = ["pillar-chip", active ? "pillar-chip--active" : ""]
          .filter(Boolean)
          .join(" ");

        return (
          <button
            key={pillar.id}
            type="button"
            className={className}
            aria-pressed={active}
            onClick={(): void => {
              setShowCustomHint(false);
              onSelect(pillar.id);
            }}
          >
            {pillar.label}
          </button>
        );
      })}

      {showCustomHint && (
        <span id="pillar-custom-hint" className="pillar-chips__hint" role="status">
          Custom pillars coming soon
        </span>
      )}
    </div>
  );
}
