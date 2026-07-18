import type { JSX } from "react";
import type { CreativeDoc } from "@/lib/mock";
import { LayerStrip } from "./LayerStrip";

interface ReviewPanelProps {
  doc: CreativeDoc;
}

/**
 * The in-review creative: gradient thumbnail, layer strip, editor note, and the
 * three review actions (Approve primary / Request change secondary / Reassign ghost).
 */
export function ReviewPanel({ doc }: ReviewPanelProps): JSX.Element {
  return (
    <div className="review-panel">
      <div className="review-panel__thumb" role="img" aria-label={`Creative preview: ${doc.thumbnailLabel}`}>
        <span className="review-panel__thumb-label">{doc.thumbnailLabel}</span>
      </div>

      <div className="review-panel__detail">
        <LayerStrip layers={doc.layers} />
        <p className="review-panel__note">{doc.note}</p>

        <div className="review-panel__actions">
          <button type="button" className="btn btn--primary">
            Approve
          </button>
          <button type="button" className="btn btn--secondary">
            Request change
          </button>
          <button type="button" className="btn btn--ghost">
            Reassign
          </button>
        </div>
      </div>
    </div>
  );
}
