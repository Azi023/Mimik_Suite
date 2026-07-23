"use client";

import type { JSX } from "react";
import type { ApiColorRole } from "@/lib/api";
import { CanvasLayerId } from "./canvas-types";
import type { CanvasMark } from "./CanvasStage";

const LAYER_LABEL: Record<CanvasLayerId, string> = {
  "layer-background": "Background",
  "layer-panel": "Panel",
  "layer-headline": "Headline",
  "layer-subhead": "Subhead",
  "layer-cta": "CTA",
  "layer-badge": "Badge",
};

interface EyeIconProps {
  open: boolean;
  size?: number;
}

function EyeIcon({ open, size = 13 }: EyeIconProps): JSX.Element {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
      {!open && <line x1="4" y1="20" x2="20" y2="4" />}
    </svg>
  );
}

export interface InspectorProps {
  layers: { id: CanvasLayerId; isVisible: boolean; hasText: boolean; canRecolor: boolean }[];
  selectedId: CanvasLayerId | null;
  onSelect: (id: CanvasLayerId | null) => void;
  onToggleVisible: (id: CanvasLayerId) => void;
  onEditText: (id: CanvasLayerId) => void;
  brandColors: readonly ApiColorRole[];
  selectedFillRole: string | undefined | null;
  onPickFillRole: (id: CanvasLayerId, role: string) => void;
  onResetLayer: (id: CanvasLayerId) => void;
  canResetSelectedLayer: boolean;
  
  askText: string;
  onAskTextChange: (text: string) => void;
  activeMark: CanvasMark | null;
  onAddAsk: (id: CanvasLayerId, mark?: CanvasMark) => void;
  busy: boolean;
}

export function Inspector({
  layers,
  selectedId,
  onSelect,
  onToggleVisible,
  onEditText,
  brandColors,
  selectedFillRole,
  onPickFillRole,
  onResetLayer,
  canResetSelectedLayer,
  askText,
  onAskTextChange,
  activeMark,
  onAddAsk,
  busy,
}: InspectorProps): JSX.Element {
  const selectedLayer = layers.find(l => l.id === selectedId);
  const askScope =
    activeMark?.kind === "region"
      ? "region"
      : activeMark?.kind === "pin"
        ? "spot"
        : "layer";

  return (
    <aside className="review-panel" aria-label="Inspector" style={{ height: "100%" }}>
      <div className="review-panel__section">
        <span className="review-panel__label">Layers</span>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", alignItems: "center" }}>
          {layers.map((layer) => {
            const isSelected = layer.id === selectedId;
            return (
              <span key={layer.id} style={{ display: "inline-flex", alignItems: "center", gap: "2px" }}>
                <button
                  type="button"
                  className={`layer-chip${isSelected ? " layer-chip--active" : ""}`}
                  aria-pressed={isSelected}
                  onClick={() => onSelect(isSelected ? null : layer.id)}
                >
                  {LAYER_LABEL[layer.id]}
                </button>
                <button
                  type="button"
                  className="layer-chip"
                  aria-pressed={!layer.isVisible}
                  aria-label={`${layer.isVisible ? "Hide" : "Show"} ${LAYER_LABEL[layer.id]}`}
                  title={layer.isVisible ? "Hide layer" : "Show layer"}
                  style={layer.isVisible ? undefined : { opacity: 0.45 }}
                  onClick={() => onToggleVisible(layer.id)}
                >
                  <EyeIcon open={layer.isVisible} />
                </button>
              </span>
            );
          })}
        </div>
      </div>

      {!selectedLayer ? (
        <div className="review-panel__section">
           <p className="review-panel__note">Select a layer to edit its properties, reset its changes, or instruct the AI.</p>
        </div>
      ) : (
        <>
          <div className="review-panel__section">
            <span className="review-panel__label">Selection</span>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
               <strong>{LAYER_LABEL[selectedLayer.id]}</strong>
               {canResetSelectedLayer && (
                  <button type="button" className="btn btn--secondary btn--sm" disabled={busy} onClick={() => onResetLayer(selectedLayer.id)}>
                     Reset layer
                  </button>
               )}
            </div>
          </div>

          {selectedLayer.hasText && (
             <div className="review-panel__section">
               <span className="review-panel__label">Content</span>
               <button
                  type="button"
                  className="btn btn--secondary btn--sm"
                  style={{ alignSelf: "flex-start" }}
                  onClick={() => onEditText(selectedLayer.id)}
                >
                  Edit text
                </button>
             </div>
          )}

          {selectedLayer.canRecolor && brandColors.length > 0 && (
            <div className="review-panel__section">
              <span className="review-panel__label">
                Appearance · brand palette
              </span>
              <div className="brief-swatches">
                {brandColors.map((color) => {
                  const active = selectedFillRole === color.name;
                  return (
                    <button
                      key={color.name}
                      type="button"
                      className="brief-swatch"
                      aria-pressed={active}
                      title={`${color.name} · ${color.hex}`}
                      onClick={() => onPickFillRole(selectedLayer.id, color.name)}
                    >
                      <span
                        className="brief-swatch__chip"
                        style={{
                          background: color.hex,
                          ...(active
                            ? {
                                outline: "2px solid var(--accent)",
                                outlineOffset: "1px",
                              }
                            : {}),
                        }}
                      />
                      <span className="brief-swatch__name">{color.name}</span>
                      <span className="brief-swatch__hex">{color.hex}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="review-panel__section" style={{ marginTop: "auto", borderTop: "1px solid var(--line)", paddingTop: "var(--sp-4)" }}>
             <span className="review-panel__label">Ask AI about this {askScope}</span>
             <p className="review-panel__note" style={{ fontSize: "12px", marginBottom: "4px" }}>
               {activeMark === null ? (
                 <>The AI will only modify the <strong>{LAYER_LABEL[selectedLayer.id]}</strong>.</>
               ) : activeMark.kind === "region" ? (
                 <>The AI will focus on the marked region for <strong>{LAYER_LABEL[selectedLayer.id]}</strong>.</>
               ) : (
                 <>The AI will focus on the marked spot for <strong>{LAYER_LABEL[selectedLayer.id]}</strong>.</>
               )}
             </p>
             <textarea
                className="creview__input"
                value={askText}
                maxLength={500}
                placeholder="What should the AI change?"
                aria-label="AI instruction"
                rows={3}
                style={{ width: "100%", padding: "8px", resize: "none", borderRadius: "var(--r-sm)", border: "1px solid var(--line)", background: "var(--surface)", color: "var(--ink)", fontFamily: "inherit", fontSize: "13px" }}
                onChange={(e) => onAskTextChange(e.target.value)}
              />
              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "8px" }}>
                 <button
                    type="button"
                    className="btn btn--primary btn--sm"
                    disabled={busy || askText.trim() === ""}
                    onClick={(): void => {
                      if (activeMark === null) {
                        onAddAsk(selectedLayer.id);
                      } else {
                        onAddAsk(selectedLayer.id, activeMark);
                      }
                    }}
                 >
                    Queue ask
                 </button>
              </div>
          </div>
        </>
      )}
    </aside>
  );
}
