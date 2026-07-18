import type { JSX } from "react";
import type { Pillar } from "@/lib/mock";

interface PillarChipsProps {
  pillars: Pillar[];
}

/**
 * Row of content-pillar chips. The active pillar is the single lime pop; the
 * "+ Custom" entry renders as a dashed add-affordance.
 */
export function PillarChips({ pillars }: PillarChipsProps): JSX.Element {
  return (
    <div className="pillar-chips" role="group" aria-label="Content pillars">
      {pillars.map((pillar) => {
        const className = [
          "pillar-chip",
          pillar.active ? "pillar-chip--active" : "",
          pillar.custom ? "pillar-chip--custom" : "",
        ]
          .filter(Boolean)
          .join(" ");

        return (
          <button
            key={pillar.id}
            type="button"
            className={className}
            aria-pressed={pillar.custom ? undefined : pillar.active}
          >
            {pillar.label}
          </button>
        );
      })}
    </div>
  );
}
