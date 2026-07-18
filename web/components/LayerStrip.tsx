import type { JSX } from "react";
import type { Layer } from "@/lib/mock";

interface LayerStripProps {
  layers: Layer[];
}

/**
 * The 5-layer strip (L1..L5) of the creative engine. The layer under edit is
 * highlighted in royal blue.
 */
export function LayerStrip({ layers }: LayerStripProps): JSX.Element {
  return (
    <div className="layer-strip" role="group" aria-label="Creative layers">
      {layers.map((layer) => (
        <span
          key={layer.id}
          className={`layer-chip${layer.active ? " layer-chip--active" : ""}`}
          aria-current={layer.active ? "true" : undefined}
        >
          {layer.label}
        </span>
      ))}
    </div>
  );
}
