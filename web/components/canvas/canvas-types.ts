/**
 * Typed mirror of the backend `CanvasRevision` contract (mimik_contracts).
 *
 * B-08 (CanvasStage) accumulates one `ApiCanvasRevision` locally; B-09 POSTs it
 * on "Apply". These shapes MUST serialize to exactly what the backend
 * `CanvasRevision` / `LayerOp` / `TextEdits` / `RegionAsk` models expect.
 */

/** The engine's six named layer groups, in paint order. */
export const CANVAS_LAYER_IDS = [
  "layer-background",
  "layer-panel",
  "layer-headline",
  "layer-subhead",
  "layer-cta",
  "layer-badge",
] as const;

export type CanvasLayerId = (typeof CANVAS_LAYER_IDS)[number];

/**
 * The FULL desired state of one layer — the backend replaces the layer's stored
 * override with this whole object, so every field is carried on every op.
 */
export interface ApiLayerOp {
  layer_id: CanvasLayerId;
  /** Horizontal offset in viewBox units. Default 0. */
  dx: number;
  /** Vertical offset in viewBox units. Default 0. */
  dy: number;
  /**
   * Backward-compatible uniform scale. Mirrors both axes when equal, otherwise 1.
   */
  scale: number;
  /** Horizontal scale about the layer's bbox center. Default 1.0; > 0 and <= 3. */
  scale_x: number;
  /** Vertical scale about the layer's bbox center. Default 1.0; > 0 and <= 3. */
  scale_y: number;
  /** Rotation in degrees. Default 0; editor UI is deferred. */
  rotation: number;
  /** Default true. */
  visible: boolean;
  /**
   * Brand color role NAME (e.g. "primary"), or null for no recolor. NEVER a
   * hex — the server resolves the role -> hex within the brand palette.
   */
  fill_role: string | null;
}

/** Copy edits keyed by text slot. Each value <= 200 chars. */
export interface ApiTextEdits {
  headline?: string;
  subhead?: string;
  cta?: string;
}

/** "Mark & tell AI" region ask (produced by B-09, not by the stage). */
export interface ApiRegionAsk {
  zone: "headline" | "subhead" | "cta" | "badge" | "background" | "panel" | "other";
  bbox: [number, number, number, number] | null;
  /** 1..500 chars. */
  instruction: string;
}

/** One accumulated pending revision. Layers never touched must NOT appear. */
export interface ApiCanvasRevision {
  text_edits?: ApiTextEdits;
  layer_ops: ApiLayerOp[];
  params?: Record<string, unknown>;
  ask?: ApiRegionAsk;
}
