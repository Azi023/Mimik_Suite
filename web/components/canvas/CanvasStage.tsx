"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type JSX,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
} from "react";
import type { ApiColorRole } from "@/lib/api";
import {
  CANVAS_LAYER_IDS,
  type ApiCanvasRevision,
  type ApiLayerOp,
  type ApiTextEdits,
  type CanvasLayerId,
} from "./canvas-types";
import {
  IDENTITY_TRANSFORM,
  useLayerDrag,
  type LayerTransform,
} from "./useLayerDrag";

export interface CanvasStageProps {
  /** Raw SVG master text (B-09 fetches via fetchCreativeSvg and passes in). */
  svg: string;
  /** Brand palette for the recolor swatches. */
  brandColors: ApiColorRole[];
  /** Fired with the single accumulated pending revision on every change. */
  onChange: (revision: ApiCanvasRevision) => void;
}

interface ViewBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface LayerBBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface CanvasLayerInfo {
  id: CanvasLayerId;
  /** Optional server-provided bbox (data-bbox). Null on creatives rendered before that
   * hook existed — we measure the real bbox from the live DOM (getBBox) after injection. */
  bbox: LayerBBox | null;
  /** Joined tspan copy for text layers; null for non-text layers. */
  initialText: string | null;
}

interface ParsedSvg {
  markup: string;
  viewBox: ViewBox;
  layers: CanvasLayerInfo[];
}

interface LayerOverride {
  visible: boolean;
  fillRole: string | null;
}

interface TextEditing {
  layerId: CanvasLayerId;
  value: string;
}

const LAYER_LABEL: Record<CanvasLayerId, string> = {
  "layer-background": "Background",
  "layer-panel": "Panel",
  "layer-headline": "Headline",
  "layer-subhead": "Subhead",
  "layer-cta": "CTA",
  "layer-badge": "Badge",
};

/** Text slots the stage can inline-edit, keyed to the contract's TextEdits. */
const TEXT_EDIT_KEY: Partial<Record<CanvasLayerId, keyof ApiTextEdits>> = {
  "layer-headline": "headline",
  "layer-subhead": "subhead",
  "layer-cta": "cta",
};

/** Layers whose fill may be re-picked from the brand palette (text + panel). */
const RECOLORABLE = new Set<CanvasLayerId>([
  "layer-panel",
  "layer-headline",
  "layer-subhead",
  "layer-cta",
]);

/** Contract cap on TextEdits values. */
const MAX_TEXT_CHARS = 200;

const FALLBACK_VIEWBOX: ViewBox = { x: 0, y: 0, w: 1080, h: 1080 };

const DEFAULT_OVERRIDE: LayerOverride = { visible: true, fillRole: null };

/**
 * Defensively sanitize the engine's SVG (strip scripts / foreignObject / on*
 * handlers / javascript: hrefs), read the viewBox, and inspect the six named
 * `[data-layer]` groups (bbox + joined tspan copy for the text slots).
 */
function parseSvg(svgText: string): ParsedSvg | null {
  if (typeof window === "undefined" || typeof DOMParser === "undefined") return null;
  const doc = new DOMParser().parseFromString(svgText, "image/svg+xml");
  const root = doc.documentElement;
  if (root.nodeName.toLowerCase() !== "svg") return null;
  if (doc.querySelector("parsererror") !== null) return null;

  for (const el of Array.from(doc.querySelectorAll("*"))) {
    const name = el.localName.toLowerCase();
    if (name === "script" || name === "foreignobject") {
      el.remove();
      continue;
    }
    for (const attr of Array.from(el.attributes)) {
      const attrName = attr.name.toLowerCase();
      if (attrName.startsWith("on")) {
        el.removeAttribute(attr.name);
      } else if (
        (attrName === "href" || attrName === "xlink:href") &&
        attr.value.trim().toLowerCase().startsWith("javascript:")
      ) {
        el.removeAttribute(attr.name);
      }
    }
  }

  let viewBox = FALLBACK_VIEWBOX;
  const viewBoxRaw = root.getAttribute("viewBox");
  if (viewBoxRaw !== null) {
    const [x, y, w, h] = viewBoxRaw.trim().split(/[\s,]+/).map(Number);
    if (
      x !== undefined && y !== undefined && w !== undefined && h !== undefined &&
      [x, y, w, h].every(Number.isFinite) && w > 0 && h > 0
    ) {
      viewBox = { x, y, w, h };
    }
  }

  // Scale responsively to the container: the frame owns the width.
  root.removeAttribute("width");
  root.removeAttribute("height");
  root.setAttribute("style", "display:block;width:100%;height:auto");

  const layers: CanvasLayerInfo[] = [];
  for (const id of CANVAS_LAYER_IDS) {
    // Select by data-layer ONLY. data-editable/data-bbox are absent on creatives
    // rendered before those render hooks existed, so requiring them made older
    // creatives non-interactive. The real bbox is measured from the live DOM
    // (getBBox) after injection; the data-bbox attr, if present, is only a fallback.
    const node = doc.querySelector(`g[data-layer="${id}"]`);
    if (node === null) continue;
    let attrBBox: LayerBBox | null = null;
    const bboxRaw = node.getAttribute("data-bbox");
    if (bboxRaw !== null) {
      const [bx, by, bw, bh] = bboxRaw.trim().split(/\s+/).map(Number);
      if (
        bx !== undefined && by !== undefined && bw !== undefined && bh !== undefined &&
        [bx, by, bw, bh].every(Number.isFinite)
      ) {
        attrBBox = { x: bx, y: by, w: bw, h: bh };
      }
    }

    let initialText: string | null = null;
    if (TEXT_EDIT_KEY[id] !== undefined) {
      const textEl = node.querySelector("text");
      if (textEl !== null) {
        const tspans = Array.from(textEl.querySelectorAll("tspan"));
        // Long copy is wrapped into tspans — join them so the editing overlay
        // seeds with the full line.
        initialText =
          tspans.length > 0
            ? tspans.map((tspan) => tspan.textContent ?? "").join(" ")
            : (textEl.textContent ?? "");
      }
    }

    layers.push({ id, bbox: attrBBox, initialText });
  }

  return { markup: new XMLSerializer().serializeToString(root), viewBox, layers };
}

/** SVG transform string: translate then scale about the layer's bbox center. */
function layerTransformAttr(t: LayerTransform, bbox: LayerBBox): string {
  const cx = bbox.x + bbox.w / 2;
  const cy = bbox.y + bbox.h / 2;
  return `translate(${t.dx} ${t.dy}) translate(${cx} ${cy}) scale(${t.scale}) translate(${-cx} ${-cy})`;
}

/** The layer's bbox after its local transform (for the selection chrome). */
function transformedBBox(bbox: LayerBBox, t: LayerTransform): LayerBBox {
  const cx = bbox.x + bbox.w / 2;
  const cy = bbox.y + bbox.h / 2;
  return {
    x: t.dx + cx + (bbox.x - cx) * t.scale,
    y: t.dy + cy + (bbox.y - cy) * t.scale,
    w: bbox.w * t.scale,
    h: bbox.h * t.scale,
  };
}

function round(value: number, places: number): number {
  const factor = 10 ** places;
  return Math.round(value * factor) / factor;
}

interface EyeIconProps {
  open: boolean;
  size?: number;
}

function EyeIcon({ open, size = 13 }: EyeIconProps): JSX.Element {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
      {!open && <line x1="4" y1="20" x2="20" y2="4" />}
    </svg>
  );
}

/**
 * The bounded in-product canvas: the creative's layered SVG rendered inline,
 * with direct manipulation on its named layers — select, drag, corner-scale,
 * hide, brand-palette recolor, and inline text edit. Pure controlled component:
 * every interaction is a LOCAL preview that accumulates into ONE pending
 * `ApiCanvasRevision` emitted via `onChange`; it never calls the API — the
 * server re-render stays the source of truth.
 */
export function CanvasStage({ svg, brandColors, onChange }: CanvasStageProps): JSX.Element {
  const hostRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Parse on the client only (DOMParser), after mount, so SSR + hydration see
  // the same empty frame and the injected markup lands in a clean second pass.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const parsed = useMemo(() => (mounted ? parseSvg(svg) : null), [mounted, svg]);

  const layers = useMemo(() => parsed?.layers ?? [], [parsed]);
  const viewBox = parsed?.viewBox ?? FALLBACK_VIEWBOX;

  const [stageWidth, setStageWidth] = useState(0);
  const [selectedId, setSelectedId] = useState<CanvasLayerId | null>(null);
  const [overrides, setOverrides] = useState<Partial<Record<CanvasLayerId, LayerOverride>>>({});
  const [textEdits, setTextEdits] = useState<ApiTextEdits>({});
  const [editing, setEditing] = useState<TextEditing | null>(null);
  // Real bbox per layer, measured from the LIVE injected DOM (getBBox) after the markup
  // lands — independent of any server-emitted data-bbox, so ANY layered SVG is editable.
  const [measured, setMeasured] = useState<Partial<Record<CanvasLayerId, LayerBBox>>>({});

  const editingRef = useRef<TextEditing | null>(null);
  useEffect(() => {
    editingRef.current = editing;
  }, [editing]);

  const getScreenToViewBox = useCallback((): number => {
    const host = hostRef.current;
    if (host === null) return 1;
    const width = host.getBoundingClientRect().width;
    return width > 0 ? viewBox.w / width : 1;
  }, [viewBox.w]);

  const { transforms, draggingLayer, beginMove, beginScale } = useLayerDrag({
    getScreenToViewBox,
  });

  // Effective base bbox for a layer: the measured DOM geometry when available, else the
  // server data-bbox attr (may be null on both, in which case the layer has no hit target).
  const layerBox = useCallback(
    (layer: CanvasLayerInfo): LayerBBox | null => measured[layer.id] ?? layer.bbox,
    [measured],
  );

  // Measure every layer's real bbox once the SVG markup is injected. getBBox returns the
  // element's untransformed geometry in viewBox units (it ignores the group's own transform),
  // so our local transforms compose on top cleanly.
  useEffect(() => {
    const host = hostRef.current;
    if (host === null || parsed === null) {
      setMeasured({});
      return;
    }
    const next: Partial<Record<CanvasLayerId, LayerBBox>> = {};
    for (const layer of parsed.layers) {
      const node = host.querySelector<SVGGraphicsElement>(`[data-layer="${layer.id}"]`);
      if (node === null) continue;
      try {
        const box = node.getBBox();
        if (box.width > 0 && box.height > 0) {
          next[layer.id] = { x: box.x, y: box.y, w: box.width, h: box.height };
        }
      } catch {
        // getBBox throws for not-yet-rendered / display:none nodes — the data-bbox attr
        // (if any) stays the fallback via layerBox.
      }
    }
    setMeasured(next);
  }, [parsed]);

  // Track the rendered stage width (overlay stroke weights + px positioning).
  useEffect(() => {
    const host = hostRef.current;
    if (host === null) return undefined;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry !== undefined) setStageWidth(entry.contentRect.width);
    });
    observer.observe(host);
    setStageWidth(host.getBoundingClientRect().width);
    return (): void => observer.disconnect();
  }, [parsed]);

  // Preview pass — apply local transform / visibility / fill onto the real
  // injected [data-layer] nodes. The engine's own transform (if any) is kept
  // and our delta is prepended, so nothing is re-laid-out or destroyed.
  useEffect(() => {
    const host = hostRef.current;
    if (host === null || parsed === null) return;
    for (const layer of parsed.layers) {
      const node = host.querySelector<SVGGElement>(`[data-layer="${layer.id}"]`);
      if (node === null) continue;
      if (node.dataset.baseTransform === undefined) {
        node.dataset.baseTransform = node.getAttribute("transform") ?? "";
      }
      const t = transforms[layer.id] ?? IDENTITY_TRANSFORM;
      const box = measured[layer.id] ?? layer.bbox;
      const isIdentity = t.dx === 0 && t.dy === 0 && t.scale === 1;
      const local = isIdentity || box === null ? "" : layerTransformAttr(t, box);
      const combined = `${local} ${node.dataset.baseTransform}`.trim();
      if (combined === "") node.removeAttribute("transform");
      else node.setAttribute("transform", combined);

      const override = overrides[layer.id] ?? DEFAULT_OVERRIDE;
      node.style.display = override.visible ? "" : "none";
      const hex =
        override.fillRole === null
          ? undefined
          : brandColors.find((color) => color.name === override.fillRole)?.hex;
      node.style.fill = hex ?? "";
    }
  }, [parsed, transforms, overrides, brandColors, measured]);

  // Optimistic text preview — put the full edited line into the first tspan
  // (keeping its positioning attributes) and blank the wrapped remainder.
  useEffect(() => {
    const host = hostRef.current;
    if (host === null || parsed === null) return;
    for (const layer of parsed.layers) {
      const key = TEXT_EDIT_KEY[layer.id];
      if (key === undefined) continue;
      const value = textEdits[key];
      if (value === undefined) continue;
      const textEl = host.querySelector<SVGTextElement>(`[data-layer="${layer.id}"] text`);
      if (textEl === null) continue;
      const tspans = Array.from(textEl.querySelectorAll("tspan"));
      if (tspans.length === 0) {
        textEl.textContent = value;
      } else {
        tspans.forEach((tspan, index) => {
          tspan.textContent = index === 0 ? value : "";
        });
      }
    }
  }, [parsed, textEdits]);

  // Emit the ONE accumulated pending revision: a full-state op per touched
  // layer + any text edits. Skipped mid-drag (60fps preview churn) — the
  // settled state emits when the drag releases. Untouched layers never appear.
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    if (draggingLayer !== null) return;
    const touched = CANVAS_LAYER_IDS.filter(
      (id) => transforms[id] !== undefined || overrides[id] !== undefined,
    );
    const hasTextEdits = Object.keys(textEdits).length > 0;
    if (touched.length === 0 && !hasTextEdits) return;
    const layerOps: ApiLayerOp[] = touched.map((id) => {
      const t = transforms[id] ?? IDENTITY_TRANSFORM;
      const override = overrides[id] ?? DEFAULT_OVERRIDE;
      return {
        layer_id: id,
        dx: round(t.dx, 2),
        dy: round(t.dy, 2),
        scale: round(t.scale, 4),
        visible: override.visible,
        fill_role: override.fillRole,
      };
    });
    const revision: ApiCanvasRevision = { layer_ops: layerOps };
    if (hasTextEdits) revision.text_edits = textEdits;
    onChangeRef.current(revision);
  }, [draggingLayer, transforms, overrides, textEdits]);

  function layerFromEventTarget(target: EventTarget | null): CanvasLayerInfo | null {
    if (!(target instanceof Element)) return null;
    const group = target.closest("[data-layer]");
    if (group === null) return null;
    const raw = group.getAttribute("data-layer");
    return layers.find((layer) => layer.id === raw) ?? null;
  }

  function handleStageClick(event: ReactMouseEvent<HTMLDivElement>): void {
    const layer = layerFromEventTarget(event.target);
    setSelectedId(layer === null ? null : layer.id);
  }

  function handleStageDoubleClick(event: ReactMouseEvent<HTMLDivElement>): void {
    const layer = layerFromEventTarget(event.target);
    if (layer !== null) openTextEditor(layer);
  }

  function openTextEditor(layer: CanvasLayerInfo): void {
    const key = TEXT_EDIT_KEY[layer.id];
    if (key === undefined) return;
    const seed = textEdits[key] ?? layer.initialText ?? "";
    setSelectedId(layer.id);
    setEditing({ layerId: layer.id, value: seed });
  }

  useEffect(() => {
    if (editing !== null) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing?.layerId]); // eslint-disable-line react-hooks/exhaustive-deps -- refocus per layer, not per keystroke

  function commitTextEdit(): void {
    const current = editingRef.current;
    if (current === null) return;
    editingRef.current = null; // idempotent against blur firing after Enter
    setEditing(null);
    const key = TEXT_EDIT_KEY[current.layerId];
    if (key === undefined) return;
    const seed = layers.find((layer) => layer.id === current.layerId)?.initialText ?? "";
    setTextEdits((prev) => {
      // Committing the untouched seed the first time is a no-op, not an edit.
      if (prev[key] === undefined && current.value === seed) return prev;
      if (prev[key] === current.value) return prev;
      return { ...prev, [key]: current.value };
    });
  }

  function cancelTextEdit(): void {
    editingRef.current = null;
    setEditing(null);
  }

  function handleEditKeyDown(event: ReactKeyboardEvent<HTMLInputElement>): void {
    if (event.key === "Enter") {
      event.preventDefault();
      commitTextEdit();
    } else if (event.key === "Escape") {
      event.preventDefault();
      cancelTextEdit();
    }
  }

  function toggleVisible(id: CanvasLayerId): void {
    setOverrides((prev) => {
      const current = prev[id] ?? DEFAULT_OVERRIDE;
      return { ...prev, [id]: { ...current, visible: !current.visible } };
    });
  }

  function pickFillRole(id: CanvasLayerId, roleName: string): void {
    setOverrides((prev) => {
      const current = prev[id] ?? DEFAULT_OVERRIDE;
      return {
        ...prev,
        // Re-picking the active swatch clears the recolor back to the original.
        [id]: { ...current, fillRole: current.fillRole === roleName ? null : roleName },
      };
    });
  }

  const selectedLayer =
    selectedId === null ? null : (layers.find((layer) => layer.id === selectedId) ?? null);
  const selectedBaseBox = selectedLayer === null ? null : layerBox(selectedLayer);
  const selectedBox =
    selectedLayer === null || selectedBaseBox === null
      ? null
      : transformedBBox(selectedBaseBox, transforms[selectedLayer.id] ?? IDENTITY_TRANSFORM);
  const selectedOverride =
    selectedLayer === null ? DEFAULT_OVERRIDE : (overrides[selectedLayer.id] ?? DEFAULT_OVERRIDE);

  // viewBox units per rendered px (overlay chrome keeps a constant px weight).
  const unit = stageWidth > 0 ? viewBox.w / stageWidth : 1;
  const pxPerUnit = stageWidth > 0 ? stageWidth / viewBox.w : 0;

  const editingLayer =
    editing === null ? null : (layers.find((layer) => layer.id === editing.layerId) ?? null);
  const editingBaseBox = editingLayer === null ? null : layerBox(editingLayer);
  const editingBox =
    editingLayer === null || editingBaseBox === null
      ? null
      : transformedBBox(editingBaseBox, transforms[editingLayer.id] ?? IDENTITY_TRANSFORM);

  const showSwatches =
    selectedLayer !== null && RECOLORABLE.has(selectedLayer.id) && brandColors.length > 0;
  const selectedIsText = selectedLayer !== null && TEXT_EDIT_KEY[selectedLayer.id] !== undefined;

  return (
    <div className="creview__stage" aria-label="Creative canvas">
      <div className="creview__stage-head">
        <span className="creview__meta">Canvas</span>
        <span className="creview__meta creview__meta--muted">
          {selectedLayer === null ? "No layer selected" : LAYER_LABEL[selectedLayer.id]}
        </span>
        <span className="creview__hint">
          Click a layer · drag to move · double-click text to edit
        </span>
      </div>

      <div className="creview__canvas-wrap">
        <div
          className="creview__canvas creview__canvas--locked"
          style={{ width: "100%", maxWidth: "620px", marginInline: "auto", overflow: "visible" }}
        >
          {parsed === null ? (
            <div
              style={{
                aspectRatio: "1 / 1",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "var(--surface-2)",
                borderRadius: "var(--r-md)",
                color: "var(--muted)",
                fontSize: "13px",
              }}
            >
              {mounted ? "Creative master unavailable" : "Loading canvas…"}
            </div>
          ) : (
            <>
              <div
                ref={hostRef}
                onClick={handleStageClick}
                onDoubleClick={handleStageDoubleClick}
                // Sanitized above: scripts/foreignObject stripped, on* removed.
                dangerouslySetInnerHTML={{ __html: parsed.markup }}
              />

              {/*
               * Interaction overlay — one transparent hit-rect per layer over
               * its CURRENT transformed bbox. The injected SVG only hit-tests
               * painted pixels (text glyphs are nearly unclickable; the
               * full-bleed background image swallows the rest), so selection
               * and dragging happen HERE. Layers are in paint order, so the
               * topmost layer's rect wins overlapping hits. Pointerdown both
               * selects and starts a move — a press with no movement is a
               * plain click-select.
               */}
              <svg
                viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`}
                style={{
                  position: "absolute",
                  inset: 0,
                  width: "100%",
                  height: "100%",
                  pointerEvents: "none",
                  overflow: "visible",
                }}
              >
                {layers.map((layer) => {
                  const override = overrides[layer.id] ?? DEFAULT_OVERRIDE;
                  const base = layerBox(layer);
                  if (base === null) return null; // no geometry yet — nothing to hit
                  const box = transformedBBox(
                    base,
                    transforms[layer.id] ?? IDENTITY_TRANSFORM,
                  );
                  return (
                    <rect
                      key={layer.id}
                      x={box.x}
                      y={box.y}
                      width={box.w}
                      height={box.h}
                      fill="transparent"
                      role="button"
                      aria-label={`Select ${LAYER_LABEL[layer.id]}`}
                      style={{
                        // Hidden layers aren't grabbable.
                        pointerEvents: override.visible ? "all" : "none",
                        touchAction: "none",
                        cursor: draggingLayer !== null ? "grabbing" : "grab",
                      }}
                      onPointerDown={(event): void => {
                        setSelectedId(layer.id);
                        beginMove(layer.id, event);
                      }}
                      onDoubleClick={(): void => openTextEditor(layer)}
                    />
                  );
                })}
              </svg>

              {selectedLayer !== null && selectedBox !== null && (
                <svg
                  viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`}
                  aria-hidden="true"
                  style={{
                    position: "absolute",
                    inset: 0,
                    width: "100%",
                    height: "100%",
                    pointerEvents: "none",
                    overflow: "visible",
                  }}
                >
                  {/* Selection outline — also the move drag surface. */}
                  <rect
                    x={selectedBox.x}
                    y={selectedBox.y}
                    width={selectedBox.w}
                    height={selectedBox.h}
                    fill="transparent"
                    stroke="var(--accent)"
                    strokeWidth={1.5 * unit}
                    style={{
                      pointerEvents: "all",
                      touchAction: "none",
                      cursor: draggingLayer !== null ? "grabbing" : "grab",
                    }}
                    onPointerDown={(event): void => beginMove(selectedLayer.id, event)}
                  />

                  {/* Move handle — stem + grip above the top edge. */}
                  <line
                    x1={selectedBox.x + selectedBox.w / 2}
                    y1={selectedBox.y}
                    x2={selectedBox.x + selectedBox.w / 2}
                    y2={selectedBox.y - 14 * unit}
                    stroke="var(--accent)"
                    strokeWidth={1.5 * unit}
                  />
                  <circle
                    cx={selectedBox.x + selectedBox.w / 2}
                    cy={selectedBox.y - 20 * unit}
                    r={6.5 * unit}
                    fill="var(--accent)"
                    stroke="var(--surface)"
                    strokeWidth={1.5 * unit}
                    style={{
                      pointerEvents: "all",
                      touchAction: "none",
                      cursor: draggingLayer !== null ? "grabbing" : "grab",
                    }}
                    onPointerDown={(event): void => beginMove(selectedLayer.id, event)}
                  />

                  {/* Corner scale handle — bottom-right, clamped to (0, 3]. */}
                  <rect
                    x={selectedBox.x + selectedBox.w - 5.5 * unit}
                    y={selectedBox.y + selectedBox.h - 5.5 * unit}
                    width={11 * unit}
                    height={11 * unit}
                    rx={2 * unit}
                    fill="var(--surface)"
                    stroke="var(--accent)"
                    strokeWidth={1.5 * unit}
                    style={{
                      pointerEvents: "all",
                      touchAction: "none",
                      cursor: "nwse-resize",
                    }}
                    onPointerDown={(event): void =>
                      beginScale(selectedLayer.id, event, selectedBaseBox?.w ?? selectedBox.w)
                    }
                  />
                </svg>
              )}

              {editing !== null && editingBox !== null && (
                <input
                  ref={inputRef}
                  className="pin-composer__input"
                  type="text"
                  value={editing.value}
                  maxLength={MAX_TEXT_CHARS}
                  aria-label={`Edit ${LAYER_LABEL[editing.layerId]} text`}
                  style={{
                    position: "absolute",
                    left: `${(editingBox.x - viewBox.x) * pxPerUnit}px`,
                    top: `${(editingBox.y - viewBox.y) * pxPerUnit}px`,
                    width: `${Math.max(editingBox.w * pxPerUnit, 160)}px`,
                    zIndex: 3,
                    boxShadow: "var(--shadow-pop)",
                  }}
                  onChange={(event): void =>
                    setEditing({ layerId: editing.layerId, value: event.target.value })
                  }
                  onBlur={commitTextEdit}
                  onKeyDown={handleEditKeyDown}
                />
              )}
            </>
          )}
        </div>
      </div>

      {layers.length > 0 && (
        <div className="creview__section">
          <span className="review-panel__label">Layers</span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", alignItems: "center" }}>
            {layers.map((layer) => {
              const override = overrides[layer.id] ?? DEFAULT_OVERRIDE;
              const isSelected = layer.id === selectedId;
              return (
                <span
                  key={layer.id}
                  style={{ display: "inline-flex", alignItems: "center", gap: "2px" }}
                >
                  <button
                    type="button"
                    className={`layer-chip${isSelected ? " layer-chip--active" : ""}`}
                    aria-pressed={isSelected}
                    onClick={(): void => setSelectedId(isSelected ? null : layer.id)}
                  >
                    {LAYER_LABEL[layer.id]}
                  </button>
                  <button
                    type="button"
                    className="layer-chip"
                    aria-pressed={!override.visible}
                    aria-label={`${override.visible ? "Hide" : "Show"} ${LAYER_LABEL[layer.id]}`}
                    title={override.visible ? "Hide layer" : "Show layer"}
                    style={override.visible ? undefined : { opacity: 0.45 }}
                    onClick={(): void => toggleVisible(layer.id)}
                  >
                    <EyeIcon open={override.visible} />
                  </button>
                </span>
              );
            })}
            {selectedIsText && selectedLayer !== null && (
              <button
                type="button"
                className="btn btn--secondary btn--sm"
                onClick={(): void => openTextEditor(selectedLayer)}
              >
                Edit text
              </button>
            )}
          </div>
        </div>
      )}

      {showSwatches && selectedLayer !== null && (
        <div className="creview__section">
          <span className="review-panel__label">
            Fill · {LAYER_LABEL[selectedLayer.id]} — brand palette
          </span>
          <div className="brief-swatches">
            {brandColors.map((color) => {
              const active = selectedOverride.fillRole === color.name;
              return (
                <button
                  key={color.name}
                  type="button"
                  className="brief-swatch"
                  aria-pressed={active}
                  title={`${color.name} · ${color.hex}`}
                  onClick={(): void => pickFillRole(selectedLayer.id, color.name)}
                >
                  <span
                    className="brief-swatch__chip"
                    style={{
                      background: color.hex,
                      ...(active
                        ? { outline: "2px solid var(--accent)", outlineOffset: "1px" }
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
    </div>
  );
}
