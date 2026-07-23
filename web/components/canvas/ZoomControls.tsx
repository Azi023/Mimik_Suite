"use client";

import type { JSX } from "react";

export interface ZoomControlsProps {
  zoom: number | "fit";
  onZoomChange: (zoom: number | "fit") => void;
  creativeSize: { w: number; h: number } | null;
  creativeFormat: string | null;
  isFullscreen: boolean;
  onToggleFullscreen: () => void;
}

export function ZoomControls({
  zoom,
  onZoomChange,
  creativeSize,
  creativeFormat,
  isFullscreen,
  onToggleFullscreen,
}: ZoomControlsProps): JSX.Element {
  const zoomDisplay = zoom === "fit" ? "Fit" : `${Math.round(zoom * 100)}%`;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-4)", background: "var(--surface)", padding: "8px 16px", borderRadius: "var(--r-full)", boxShadow: "var(--shadow-card)", border: "1px solid var(--card-border)" }}>
      {creativeSize && (
        <span style={{ fontSize: "12px", color: "var(--muted)", fontWeight: 500 }}>
          {creativeSize.w} × {creativeSize.h}
          {creativeFormat ? ` · ${creativeFormat}` : ""}
        </span>
      )}
      
      <div style={{ display: "flex", alignItems: "center", gap: "2px", background: "var(--surface-2)", padding: "2px", borderRadius: "var(--r-full)" }}>
        <button
          type="button"
          className="icon-btn"
          style={{ minWidth: "28px", minHeight: "28px", width: "28px", height: "28px", borderRadius: "50%", border: "none", boxShadow: "none", background: "transparent" }}
          title="Zoom out"
          onClick={() => onZoomChange(typeof zoom === "number" ? Math.max(0.1, zoom - 0.25) : 0.75)}
        >
          -
        </button>
        <span style={{ fontSize: "12px", fontWeight: 600, width: "40px", textAlign: "center" }}>
          {zoomDisplay}
        </span>
        <button
          type="button"
          className="icon-btn"
          style={{ minWidth: "28px", minHeight: "28px", width: "28px", height: "28px", borderRadius: "50%", border: "none", boxShadow: "none", background: "transparent" }}
          title="Zoom in"
          onClick={() => onZoomChange(typeof zoom === "number" ? Math.min(5, zoom + 0.25) : 1.25)}
        >
          +
        </button>
      </div>

      <button
        type="button"
        className="btn btn--ghost btn--sm"
        style={{ padding: "4px 8px" }}
        onClick={() => onZoomChange("fit")}
      >
        Fit
      </button>

      <button
        type="button"
        className="btn btn--ghost btn--sm"
        style={{ padding: "4px 8px" }}
        onClick={() => onZoomChange(1)}
      >
        100%
      </button>

      <div style={{ width: "1px", height: "16px", background: "var(--line)" }} />

      <button
        type="button"
        className="icon-btn"
        style={{ minWidth: "32px", minHeight: "32px", width: "32px", height: "32px", border: "none", boxShadow: "none", fontSize: "16px", fontWeight: 600 }}
        title="Toggle fullscreen (F)"
        onClick={onToggleFullscreen}
      >
        {isFullscreen ? "↙" : "↗"}
      </button>
    </div>
  );
}
