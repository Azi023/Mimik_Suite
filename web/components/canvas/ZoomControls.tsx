"use client";

import type { JSX } from "react";

export interface ZoomControlsProps {
  zoom: number | "fit";
  onZoomChange: (zoom: number | "fit") => void;
  isPanToolActive: boolean;
  onTogglePanTool: () => void;
  creativeSize: { w: number; h: number } | null;
  creativeFormat: string | null;
  isFullscreen: boolean;
  onToggleFullscreen: () => void;
}

export function ZoomControls({
  zoom,
  onZoomChange,
  isPanToolActive,
  onTogglePanTool,
  creativeSize,
  creativeFormat,
  isFullscreen,
  onToggleFullscreen,
}: ZoomControlsProps): JSX.Element {
  const zoomDisplay = zoom === "fit" ? "Fit" : `${Math.round(zoom * 100)}%`;

  return (
    <div
      style={{ display: "flex", alignItems: "center", gap: "var(--sp-4)", background: "var(--surface)", padding: "8px 16px", borderRadius: "var(--r-full)", boxShadow: "var(--shadow-card)", border: "1px solid var(--card-border)" }}
      onKeyDown={(event): void => event.stopPropagation()}
      onKeyUp={(event): void => event.stopPropagation()}
    >
      {creativeSize && (
        <span style={{ fontSize: "12px", color: "var(--muted)", fontWeight: 500 }}>
          {creativeSize.w} × {creativeSize.h}
          {creativeFormat ? ` · ${creativeFormat}` : ""}
        </span>
      )}

      <button
        type="button"
        className="icon-btn"
        aria-label="Pan tool"
        aria-pressed={isPanToolActive}
        title={
          isPanToolActive
            ? "Pan tool active: drag the canvas"
            : "Pan tool: drag the canvas (hold Space for temporary pan)"
        }
        style={{
          minWidth: "32px",
          minHeight: "32px",
          width: "32px",
          height: "32px",
          border: "1px solid",
          borderColor: isPanToolActive ? "var(--ink)" : "transparent",
          boxShadow: "none",
          color: isPanToolActive ? "var(--surface)" : "var(--ink-2)",
          background: isPanToolActive ? "var(--ink)" : "var(--surface-2)",
        }}
        onClick={onTogglePanTool}
      >
        <svg
          aria-hidden="true"
          focusable="false"
          viewBox="0 0 24 24"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M18 11V6a2 2 0 0 0-4 0v5" />
          <path d="M14 10V4a2 2 0 0 0-4 0v6" />
          <path d="M10 10.5V6a2 2 0 0 0-4 0v8" />
          <path d="m6 14-1.8-1.8A2 2 0 0 0 1.4 15L7 20.6a5 5 0 0 0 3.5 1.4H16a6 6 0 0 0 6-6v-5a2 2 0 0 0-4 0" />
        </svg>
      </button>

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
