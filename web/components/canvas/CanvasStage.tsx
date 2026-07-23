"use client";

import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type JSX,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
  type Ref,
} from "react";
import type { ApiColorRole } from "@/lib/api";
import {
  CANVAS_LAYER_IDS,
  type ApiCanvasRevision,
  type ApiTextEdits,
  type CanvasLayerId,
} from "./canvas-types";
import {
  IDENTITY_TRANSFORM,
  RECOLOR_TARGET,
  TEXT_TARGET,
  appendOp,
  applyState,
  canRedo,
  canUndo,
  createEditorBaseState,
  fold,
  isSvgLayerVisible,
  orientedBoxOf,
  redo as redoHistory,
  removeOp as removeHistoryOp,
  snapLayerTransform,
  toCanvasRevision,
  transformedBBox,
  undo as undoHistory,
  type BaseLayerCapture,
  type DocOp,
  type EditHistory,
  type EditorBaseState,
  type FoldedState,
  type LayerBBox,
  type LayerTransform,
  type SnapLines,
  type SnappedLayerTransform,
} from "./editor-state";
import { useLayerDrag, type ResizeHandle } from "./useLayerDrag";
import { Inspector, type InspectorProps } from "./Inspector";
import { ZoomControls } from "./ZoomControls";

export interface CanvasStageProps {
  /** Raw SVG master text (B-09 fetches via fetchCreativeSvg and passes in). */
  svg: string;
  /** Brand palette for the recolor swatches. */
  brandColors: ApiColorRole[];
  /** Fired with the single folded pending revision on every committed change. */
  onChange: (revision: ApiCanvasRevision) => void;
  /** Surfaces the ordered canonical history and reactive undo/redo availability. */
  onHistoryChange?: (snapshot: CanvasStageSnapshot) => void;
  /** Small imperative bridge for toolbar actions while history stays stage-owned. */
  controlsRef?: Ref<CanvasStageHandle>;
  askText?: string;
  onAskTextChange?: (text: string) => void;
  onAddAsk?: (layerId: CanvasLayerId) => void;
  busy?: boolean;
}

export interface CanvasStageSnapshot {
  history: EditHistory;
  canUndo: boolean;
  canRedo: boolean;
}

export interface CanvasStageHandle {
  undo: () => void;
  redo: () => void;
  removeOp: (operationId: string) => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
}

interface ViewBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface CanvasLayerInfo {
  id: CanvasLayerId;
  /** Server-provided fallback; live getBBox remains the geometry source of truth. */
  bbox: LayerBBox | null;
  initialText: string | null;
  baseTransform: string;
  baseStyle: string | null;
  baseDisplay: string | null;
  baseVisibility: string | null;
  baseHidden: boolean;
  baseVisible: boolean;
  baseTextHTML: string | null;
  baseFill: string | null;
}

interface ParsedSvg {
  markup: string;
  viewBox: ViewBox;
  layers: CanvasLayerInfo[];
}

interface TextEditing {
  layerId: CanvasLayerId;
  value: string;
  seed: string;
  operationId: string;
  before: EditHistory;
}

interface PanPoint {
  x: number;
  y: number;
}

interface PanBounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

const LAYER_LABEL: Record<CanvasLayerId, string> = {
  "layer-background": "Background",
  "layer-panel": "Panel",
  "layer-headline": "Headline",
  "layer-subhead": "Subhead",
  "layer-cta": "CTA",
  "layer-badge": "Badge",
};

const TEXT_EDIT_KEY: Partial<Record<CanvasLayerId, keyof ApiTextEdits>> = {
  "layer-headline": "headline",
  "layer-subhead": "subhead",
  "layer-cta": "cta",
};

const RECOLORABLE = new Set<CanvasLayerId>([
  "layer-panel",
  "layer-headline",
  "layer-subhead",
  "layer-cta",
  "layer-badge",
]);

const MAX_TEXT_CHARS = 200;
const TEXT_PREVIEW_DEBOUNCE_MS = 75;
const FALLBACK_VIEWBOX: ViewBox = { x: 0, y: 0, w: 1080, h: 1080 };
const EMPTY_HISTORY: EditHistory = { ops: [], redo: [] };
const RESIZE_HANDLE_SIZE_PX = 11;
const RESIZE_HANDLE_RADIUS_PX = 2;
const SAFE_AREA_INSET_RATIO = 0.05;
const RULER_SIZE_PX = 20;
const RULER_LABEL_SPACING_PX = 84;
const RULER_MINOR_DIVISIONS = 5;
const WHEEL_PAN_SETTLE_MS = 100;
const NUDGE_DIRECTION: Readonly<
  Partial<Record<string, readonly [x: number, y: number]>>
> = {
  ArrowLeft: [-1, 0],
  ArrowRight: [1, 0],
  ArrowUp: [0, -1],
  ArrowDown: [0, 1],
};

interface ResizeHandleDefinition {
  handle: ResizeHandle;
  xFactor: 0 | 0.5 | 1;
  yFactor: 0 | 0.5 | 1;
  cursor: "ew-resize" | "nesw-resize" | "ns-resize" | "nwse-resize";
}

const RESIZE_HANDLES: readonly ResizeHandleDefinition[] = [
  { handle: "nw", xFactor: 0, yFactor: 0, cursor: "nwse-resize" },
  { handle: "ne", xFactor: 1, yFactor: 0, cursor: "nesw-resize" },
  { handle: "se", xFactor: 1, yFactor: 1, cursor: "nwse-resize" },
  { handle: "sw", xFactor: 0, yFactor: 1, cursor: "nesw-resize" },
  { handle: "n", xFactor: 0.5, yFactor: 0, cursor: "ns-resize" },
  { handle: "e", xFactor: 1, yFactor: 0.5, cursor: "ew-resize" },
  { handle: "s", xFactor: 0.5, yFactor: 1, cursor: "ns-resize" },
  { handle: "w", xFactor: 0, yFactor: 0.5, cursor: "ew-resize" },
];

function parseBBox(raw: string | null): LayerBBox | null {
  if (raw === null) return null;
  const [x, y, w, h] = raw.trim().split(/\s+/).map(Number);
  if (
    x === undefined ||
    y === undefined ||
    w === undefined ||
    h === undefined ||
    ![x, y, w, h].every(Number.isFinite) ||
    w <= 0 ||
    h <= 0
  ) {
    return null;
  }
  return { x, y, w, h };
}

function matchingFillRole(
  baseFill: string | null,
  brandColors: readonly ApiColorRole[],
): string | undefined {
  if (baseFill === null) return undefined;
  const normalizedBaseFill = baseFill.trim().toLowerCase();
  return brandColors.find(
    (color) => color.hex.trim().toLowerCase() === normalizedBaseFill,
  )?.name;
}

/**
 * Sanitize once, capture every pristine value before injection, and avoid
 * touching the background layer's large base64 payload after this parse.
 */
function parseSvg(svgText: string): ParsedSvg | null {
  if (typeof window === "undefined" || typeof DOMParser === "undefined") return null;
  const doc = new DOMParser().parseFromString(svgText, "image/svg+xml");
  const root = doc.documentElement;
  if (root.nodeName.toLowerCase() !== "svg") return null;
  if (doc.querySelector("parsererror") !== null) return null;

  for (const element of Array.from(doc.querySelectorAll("*"))) {
    const name = element.localName.toLowerCase();
    if (name === "script" || name === "foreignobject") {
      element.remove();
      continue;
    }
    for (const attribute of Array.from(element.attributes)) {
      const attributeName = attribute.name.toLowerCase();
      if (attributeName.startsWith("on")) {
        element.removeAttribute(attribute.name);
      } else if (
        (attributeName === "href" || attributeName === "xlink:href") &&
        attribute.value.trim().toLowerCase().startsWith("javascript:")
      ) {
        element.removeAttribute(attribute.name);
      }
    }
  }

  let viewBox = FALLBACK_VIEWBOX;
  const viewBoxRaw = root.getAttribute("viewBox");
  if (viewBoxRaw !== null) {
    const [x, y, w, h] = viewBoxRaw.trim().split(/[\s,]+/).map(Number);
    if (
      x !== undefined &&
      y !== undefined &&
      w !== undefined &&
      h !== undefined &&
      [x, y, w, h].every(Number.isFinite) &&
      w > 0 &&
      h > 0
    ) {
      viewBox = { x, y, w, h };
    }
  }

  root.removeAttribute("width");
  root.removeAttribute("height");
  root.setAttribute("style", "display:block;width:100%;height:auto");

  const layers: CanvasLayerInfo[] = [];
  for (const id of CANVAS_LAYER_IDS) {
    const node = doc.querySelector<SVGGElement>(`g[data-layer="${id}"]`);
    if (node === null) continue;

    const textSelector = TEXT_TARGET[id];
    const textElement =
      textSelector === null
        ? null
        : node.querySelector<SVGTextElement>(textSelector);
    const tspans =
      textElement === null
        ? []
        : Array.from(textElement.querySelectorAll("tspan"));
    const initialText =
      textElement === null
        ? null
        : tspans.length > 0
          ? tspans.map((tspan) => tspan.textContent ?? "").join("\n")
          : (textElement.textContent ?? "");

    const recolorSelector = RECOLOR_TARGET[id];
    const recolorTarget =
      recolorSelector === null
        ? null
        : node.querySelector<SVGElement>(recolorSelector);

    layers.push({
      id,
      bbox: parseBBox(node.getAttribute("data-bbox")),
      initialText,
      baseTransform: node.getAttribute("transform") ?? "",
      baseStyle: node.getAttribute("style"),
      baseDisplay: node.getAttribute("display"),
      baseVisibility: node.getAttribute("visibility"),
      baseHidden: node.hasAttribute("hidden"),
      baseVisible: isSvgLayerVisible(node),
      baseTextHTML: textElement?.innerHTML ?? null,
      baseFill: recolorTarget?.getAttribute("fill") ?? null,
    });
  }

  return {
    markup: new XMLSerializer().serializeToString(root),
    viewBox,
    layers,
  };
}

function sameOperationIds(left: readonly DocOp[], right: readonly DocOp[]): boolean {
  return (
    left.length === right.length &&
    left.every((operation, index) => operation.id === right[index]?.id)
  );
}

function isTextEntryTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tagName = target.tagName.toLowerCase();
  return (
    tagName === "input" ||
    tagName === "textarea" ||
    tagName === "select" ||
    target.isContentEditable
  );
}

function textAlignForAnchor(
  anchor: string,
): "center" | "left" | "right" {
  if (anchor === "middle") return "center";
  if (anchor === "end") return "right";
  return "left";
}

function niceRulerStep(target: number): number {
  if (!Number.isFinite(target) || target <= 0) return 100;
  const magnitude = 10 ** Math.floor(Math.log10(target));
  const normalized = target / magnitude;
  const factor = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return factor * magnitude;
}

function rulerValues(start: number, end: number, step: number): number[] {
  if (!Number.isFinite(step) || step <= 0) return [];
  const values: number[] = [];
  const first = Math.ceil(start / step) * step;
  for (let value = first; value <= end + step * 1e-6; value += step) {
    values.push(Number(value.toFixed(6)));
    if (values.length >= 500) break;
  }
  return values;
}

function isMajorRulerValue(value: number, majorStep: number): boolean {
  const multiple = value / majorStep;
  return Math.abs(multiple - Math.round(multiple)) < 1e-6;
}

function formatRulerValue(value: number, majorStep: number): string {
  const decimals =
    majorStep >= 1 ? 0 : Math.min(3, Math.ceil(-Math.log10(majorStep)));
  const rounded = Number(value.toFixed(decimals));
  return Object.is(rounded, -0) ? "0" : String(rounded);
}

function panBounds(
  viewportWidth: number,
  viewportHeight: number,
  boardWidth: number,
  boardHeight: number,
  zoom: number,
): PanBounds {
  const horizontalReach = Math.max(
    (boardWidth * zoom - viewportWidth) / 2,
    0,
  );
  const verticalReach = Math.max(
    (boardHeight * zoom - viewportHeight) / 2,
    0,
  );
  return {
    minX: -horizontalReach,
    maxX: horizontalReach,
    minY: -verticalReach,
    maxY: verticalReach,
  };
}

function clampPan(point: PanPoint, bounds: PanBounds): PanPoint {
  return {
    x: Math.max(bounds.minX, Math.min(bounds.maxX, point.x)),
    y: Math.max(bounds.minY, Math.min(bounds.maxY, point.y)),
  };
}

/**
 * Bounded inline-SVG editor. EditHistory is the only artwork state: the DOM,
 * overlay geometry, visibility gates, pending count, and API payload all read
 * the same folded state.
 */
export function CanvasStage({
  svg,
  brandColors,
  onChange,
  onHistoryChange,
  controlsRef,
  askText,
  onAskTextChange,
  onAddAsk,
  busy,
}: CanvasStageProps): JSX.Element {
  const stageRef = useRef<HTMLDivElement>(null);
  const canvasWrapRef = useRef<HTMLDivElement>(null);
  const hostRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const baseRef = useRef<EditorBaseState | null>(null);
  const foldedRef = useRef<FoldedState>(fold([]));
  const historyRef = useRef<EditHistory>(EMPTY_HISTORY);
  const editingRef = useRef<TextEditing | null>(null);
  const textPreviewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeDragOpIdRef = useRef<string | null>(null);
  const draggingLayerRef = useRef<CanvasLayerId | null>(null);
  const showingOriginalRef = useRef(false);
  const operationCounterRef = useRef(0);
  const brandColorsRef = useRef<readonly ApiColorRole[]>(brandColors);
  const wheelPanTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const zoomRef = useRef<number | "fit">("fit");

  const [zoom, setZoom] = useState<number | "fit">("fit");
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isPanToolActive, setIsPanToolActive] = useState(false);
  const [isSpaceDown, setIsSpaceDown] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [isWheelPanning, setIsWheelPanning] = useState(false);
  const [showRulers, setShowRulers] = useState(true);
  const [showSafeArea, setShowSafeArea] = useState(true);
  const [snapLines, setSnapLines] = useState<SnapLines | null>(null);

  const [mounted, setMounted] = useState(false);
  const [stageWidth, setStageWidth] = useState(0);
  const [panGeometryVersion, setPanGeometryVersion] = useState(0);
  const [baseVersion, setBaseVersion] = useState(0);
  const [history, setHistory] = useState<EditHistory>(EMPTY_HISTORY);
  const [showingOriginal, setShowingOriginal] = useState(false);
  const [selectedId, setSelectedId] = useState<CanvasLayerId | null>(null);
  const [hoveredId, setHoveredId] = useState<CanvasLayerId | null>(null);
  const [editing, setEditing] = useState<TextEditing | null>(null);
  const [measured, setMeasured] = useState<
    Partial<Record<CanvasLayerId, LayerBBox>>
  >({});
  const [overflow, setOverflow] = useState<
    Partial<Record<CanvasLayerId, boolean>>
  >({});

  useEffect(() => {
    setMounted(true);
  }, []);

  const parsed = useMemo(
    () => (mounted ? parseSvg(svg) : null),
    [mounted, svg],
  );
  const layers = useMemo(() => parsed?.layers ?? [], [parsed]);
  const viewBox = parsed?.viewBox ?? FALLBACK_VIEWBOX;
  const folded = useMemo(() => fold(history.ops), [history.ops]);
  const isPanModeActive = isPanToolActive || isSpaceDown;

  historyRef.current = history;
  foldedRef.current = folded;
  editingRef.current = editing;
  brandColorsRef.current = brandColors;
  zoomRef.current = zoom;

  const clampPanForZoom = useCallback(
    (point: PanPoint, zoomValue: number | "fit"): PanPoint => {
      const viewport = canvasWrapRef.current;
      const board = hostRef.current;
      if (viewport === null || board === null) {
        return { x: 0, y: 0 };
      }
      return clampPan(
        point,
        panBounds(
          viewport.clientWidth,
          viewport.clientHeight,
          board.offsetWidth,
          board.offsetHeight,
          zoomValue === "fit" ? 1 : zoomValue,
        ),
      );
    },
    [],
  );

  const handleWheel = useCallback(
    (event: WheelEvent): void => {
      event.preventDefault();
      if (event.metaKey || event.ctrlKey) {
        const delta = event.deltaY > 0 ? -0.1 : 0.1;
        const current = zoomRef.current === "fit" ? 1 : zoomRef.current;
        const nextZoom = Math.max(0.1, Math.min(5, current + delta));
        zoomRef.current = nextZoom;
        setZoom(nextZoom);
        setPan((currentPan) => clampPanForZoom(currentPan, nextZoom));
        return;
      }

      const deltaScale =
        event.deltaMode === 1
          ? 16
          : event.deltaMode === 2
            ? canvasWrapRef.current?.clientHeight ?? 1
            : 1;
      setIsWheelPanning(true);
      if (wheelPanTimerRef.current !== null) {
        clearTimeout(wheelPanTimerRef.current);
      }
      wheelPanTimerRef.current = setTimeout(() => {
        wheelPanTimerRef.current = null;
        setIsWheelPanning(false);
      }, WHEEL_PAN_SETTLE_MS);
      setPan((currentPan) =>
        clampPanForZoom(
          {
            x: currentPan.x - event.deltaX * deltaScale,
            y: currentPan.y - event.deltaY * deltaScale,
          },
          zoomRef.current,
        ),
      );
    },
    [clampPanForZoom],
  );

  const setCanonicalHistory = useCallback((next: EditHistory): void => {
    historyRef.current = next;
    setHistory(next);
  }, []);

  const applyFoldedToHost = useCallback((nextFolded: FoldedState): void => {
    const host = hostRef.current;
    const base = baseRef.current;
    if (host === null || base === null) return;
    const result = applyState(host, base, nextFolded);
    setOverflow(result.overflow);
  }, []);

  const restoreOriginalPreview = useCallback((): void => {
    if (!showingOriginalRef.current) return;
    showingOriginalRef.current = false;
    setShowingOriginal(false);
    applyFoldedToHost(foldedRef.current);
  }, [applyFoldedToHost]);

  const showOriginalPreview = useCallback((): boolean => {
    if (
      showingOriginalRef.current ||
      editingRef.current !== null ||
      draggingLayerRef.current !== null
    ) {
      return false;
    }
    showingOriginalRef.current = true;
    setShowingOriginal(true);
    applyFoldedToHost(fold([]));
    return true;
  }, [applyFoldedToHost]);

  const transitionHistory = useCallback(
    (transition: (current: EditHistory) => EditHistory): void => {
      if (
        editingRef.current !== null ||
        draggingLayerRef.current !== null
      ) {
        return;
      }
      restoreOriginalPreview();
      const current = historyRef.current;
      const next = transition(current);
      if (next === current) return;
      setCanonicalHistory(next);
    },
    [restoreOriginalPreview, setCanonicalHistory],
  );

  const performUndo = useCallback((): void => {
    transitionHistory(undoHistory);
  }, [transitionHistory]);

  const performRedo = useCallback((): void => {
    transitionHistory(redoHistory);
  }, [transitionHistory]);

  const performRemoveOp = useCallback(
    (operationId: string): void => {
      transitionHistory((current) => {
        if (!current.ops.some((operation) => operation.id === operationId)) {
          return current;
        }
        return removeHistoryOp(current, operationId);
      });
    },
    [transitionHistory],
  );

  useImperativeHandle(
    controlsRef,
    (): CanvasStageHandle => ({
      undo: performUndo,
      redo: performRedo,
      removeOp: performRemoveOp,
      canUndo: (): boolean => canUndo(historyRef.current),
      canRedo: (): boolean => canRedo(historyRef.current),
    }),
    [performRedo, performRemoveOp, performUndo],
  );

  const nextOperationId = useCallback((): string => {
    operationCounterRef.current += 1;
    if (typeof globalThis.crypto?.randomUUID === "function") {
      return globalThis.crypto.randomUUID();
    }
    return `canvas-op-${operationCounterRef.current}`;
  }, []);

  const getScreenToViewBox = useCallback((): number => {
    const host = hostRef.current;
    if (host === null) return 1;
    const width = host.getBoundingClientRect().width;
    return width > 0 ? viewBox.w / width : 1;
  }, [viewBox.w]);

  const getCanonicalTransform = useCallback(
    (layerId: CanvasLayerId): LayerTransform =>
      fold(historyRef.current.ops).transform[layerId] ?? IDENTITY_TRANSFORM,
    [],
  );

  const upsertTransformOperation = useCallback(
    (layerId: CanvasLayerId, transform: LayerTransform): void => {
      const operationId =
        activeDragOpIdRef.current ?? nextOperationId();
      activeDragOpIdRef.current = operationId;
      const operation: DocOp = {
        id: operationId,
        layer: layerId,
        kind: "transform",
        transform,
        label: `Transform ${LAYER_LABEL[layerId]}`,
      };
      const previous = historyRef.current;
      const exists = previous.ops.some((item) => item.id === operationId);
      const next = !exists
        ? appendOp(previous, operation)
        : {
          ...previous,
          ops: previous.ops.map((item) =>
            item.id === operationId ? operation : item,
          ),
        };
      setCanonicalHistory(next);
    },
    [nextOperationId, setCanonicalHistory],
  );

  const layerBox = useCallback(
    (layer: CanvasLayerInfo): LayerBBox | null =>
      measured[layer.id] ?? layer.bbox,
    [measured],
  );

  const getMoveSnap = useCallback(
    (
      layerId: CanvasLayerId,
      transform: LayerTransform,
      threshold: number,
    ): SnappedLayerTransform => {
      const movingLayer =
        layers.find((layer) => layer.id === layerId) ?? null;
      const movingBox = movingLayer === null ? null : layerBox(movingLayer);
      if (movingBox === null) {
        return { transform, lines: { x: null, y: null } };
      }

      const inset =
        Math.min(viewBox.w, viewBox.h) * SAFE_AREA_INSET_RATIO;
      const xGuides = [
        viewBox.x + viewBox.w / 2,
        viewBox.x + inset,
        viewBox.x + viewBox.w - inset,
      ];
      const yGuides = [
        viewBox.y + viewBox.h / 2,
        viewBox.y + inset,
        viewBox.y + viewBox.h - inset,
      ];

      for (const layer of layers) {
        if (
          layer.id === layerId ||
          foldedRef.current.visible[layer.id] === false
        ) {
          continue;
        }
        const base = layerBox(layer);
        if (base === null) continue;
        const box = transformedBBox(
          base,
          foldedRef.current.transform[layer.id] ?? IDENTITY_TRANSFORM,
        );
        xGuides.push(box.x, box.x + box.w / 2, box.x + box.w);
        yGuides.push(box.y, box.y + box.h / 2, box.y + box.h);
      }

      return snapLayerTransform(
        movingBox,
        transform,
        { x: xGuides, y: yGuides },
        threshold,
      );
    },
    [layerBox, layers, viewBox.h, viewBox.w, viewBox.x, viewBox.y],
  );

  const { draggingLayer, beginMove, beginResize, beginRotate } = useLayerDrag({
    getScreenToViewBox,
    getTransform: getCanonicalTransform,
    getMoveSnap,
    onDragStart: (): void => {
      activeDragOpIdRef.current = nextOperationId();
    },
    onDragMove: upsertTransformOperation,
    onDragEnd: (layerId, transform): void => {
      upsertTransformOperation(layerId, transform);
      activeDragOpIdRef.current = null;
    },
    onSnapChange: setSnapLines,
  });
  draggingLayerRef.current = draggingLayer;

  // Own the SVG injection imperatively (NOT via dangerouslySetInnerHTML). React must never
  // re-materialize this subtree, or a re-render would wipe applyState's live edits (the exact
  // bug where recolor/hide reverted). Runs before base-capture (same [parsed] dep, declared first).
  useEffect(() => {
    const host = hostRef.current;
    if (host === null || parsed === null) return;
    host.innerHTML = parsed.markup;
  }, [parsed]);

  // Capture live geometry and computed text metrics while the DOM is pristine.
  useEffect(() => {
    const host = hostRef.current;
    if (host === null || parsed === null) {
      baseRef.current = null;
      setMeasured({});
      setOverflow({});
      return;
    }

    const nextMeasured: Partial<Record<CanvasLayerId, LayerBBox>> = {};
    const captures: BaseLayerCapture[] = [];
    for (const layer of parsed.layers) {
      const node = host.querySelector<SVGGraphicsElement>(
        `g[data-layer="${layer.id}"]`,
      );
      if (node === null) continue;
      let bbox = layer.bbox;
      try {
        const live = node.getBBox();
        if (live.width > 0 && live.height > 0) {
          bbox = { x: live.x, y: live.y, w: live.width, h: live.height };
        }
      } catch {
        // Pre-rendered/hidden nodes keep the parsed data-bbox fallback.
      }
      if (bbox === null) continue;
      nextMeasured[layer.id] = bbox;
      captures.push({
        id: layer.id,
        bbox,
        baseTransform: layer.baseTransform,
        baseStyle: layer.baseStyle,
        baseDisplay: layer.baseDisplay,
        baseVisibility: layer.baseVisibility,
        baseHidden: layer.baseHidden,
        baseVisible: layer.baseVisible,
        baseTextHTML: layer.baseTextHTML,
        baseFill: layer.baseFill,
        initialText: layer.initialText,
      });
    }

    baseRef.current = createEditorBaseState(
      host,
      captures,
      brandColorsRef.current,
    );
    setMeasured(nextMeasured);
    setOverflow({});
    setBaseVersion((version) => version + 1);
  }, [parsed]);

  // Palette changes re-resolve role names without recapturing edited DOM as base.
  useEffect(() => {
    const base = baseRef.current;
    if (base === null) return;
    base.brandColors = [...brandColors];
    base.lastApplied = null;
    setBaseVersion((version) => version + 1);
  }, [brandColors]);

  useEffect(() => {
    const host = hostRef.current;
    const base = baseRef.current;
    if (host === null || base === null || parsed === null) return;
    const result = applyState(
      host,
      base,
      showingOriginalRef.current ? fold([]) : folded,
    );
    setOverflow(result.overflow);
  }, [baseVersion, folded, parsed]);

  useEffect(() => {
    const host = hostRef.current;
    const viewport = canvasWrapRef.current;
    if (host === null || viewport === null) return undefined;
    const observer = new ResizeObserver((entries) => {
      const hostEntry = entries.find((entry) => entry.target === host);
      if (hostEntry !== undefined) {
        setStageWidth(hostEntry.contentRect.width);
      }
      setPanGeometryVersion((version) => version + 1);
    });
    observer.observe(host);
    observer.observe(viewport);
    setStageWidth(host.offsetWidth);
    setPanGeometryVersion((version) => version + 1);
    return (): void => observer.disconnect();
  }, [parsed]);

  useEffect(() => {
    setPan((current) => {
      const next =
        zoom === "fit"
          ? { x: 0, y: 0 }
          : clampPanForZoom(current, zoom);
      return next.x === current.x && next.y === current.y ? current : next;
    });
  }, [clampPanForZoom, panGeometryVersion, zoom]);

  useEffect(() => {
    const viewport = canvasWrapRef.current;
    if (viewport === null) return undefined;
    viewport.addEventListener("wheel", handleWheel, { passive: false });
    return (): void => viewport.removeEventListener("wheel", handleWheel);
  }, [handleWheel]);

  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const onHistoryChangeRef = useRef(onHistoryChange);
  useEffect(() => {
    onHistoryChangeRef.current = onHistoryChange;
  }, [onHistoryChange]);

  useEffect(() => {
    onHistoryChangeRef.current?.({
      history: {
        ops: [...history.ops],
        redo: [...history.redo],
      },
      canUndo: canUndo(history),
      canRedo: canRedo(history),
    });
  }, [history]);

  // Draft text and active drags already render canonically, but parent payload
  // emission waits for their transaction boundary to avoid 60fps shell churn.
  useEffect(() => {
    if (
      editing !== null ||
      draggingLayer !== null
    ) {
      return;
    }
    onChangeRef.current(toCanvasRevision(folded));
  }, [draggingLayer, editing, folded, history.ops.length]);

  useEffect(() => {
    return (): void => {
      if (textPreviewTimerRef.current !== null) {
        clearTimeout(textPreviewTimerRef.current);
      }
      if (wheelPanTimerRef.current !== null) {
        clearTimeout(wheelPanTimerRef.current);
      }
    };
  }, []);

  function addOperation(operation: DocOp): void {
    const layerBase = baseRef.current?.layers[operation.layer];
    const next = appendOp(historyRef.current, operation, {
      visible: layerBase?.baseVisible ?? true,
      fillRole: matchingFillRole(
        layerBase?.baseFill ?? null,
        baseRef.current?.brandColors ?? [],
      ),
    });
    setCanonicalHistory(next);
  }

  function removeTextDraft(
    previous: EditHistory,
    current: TextEditing,
  ): EditHistory {
    const nextOps = previous.ops.filter(
      (operation) => operation.id !== current.operationId,
    );
    if (nextOps.length === previous.ops.length) return previous;
    const restoreRedo = sameOperationIds(nextOps, current.before.ops);
    return {
      ops: nextOps,
      redo: restoreRedo ? current.before.redo : previous.redo,
    };
  }

  function historyWithTextDraft(
    previous: EditHistory,
    current: TextEditing,
  ): EditHistory {
    const operation: DocOp = {
      id: current.operationId,
      layer: current.layerId,
      kind: "text",
      text: current.value,
      label: `${LAYER_LABEL[current.layerId]} text`,
    };
    if (current.value === current.seed) {
      return removeTextDraft(previous, current);
    }
    const exists = previous.ops.some(
      (item) => item.id === current.operationId,
    );
    return !exists
      ? appendOp(previous, operation)
      : {
          ...previous,
          ops: previous.ops.map((item) =>
            item.id === current.operationId ? operation : item,
          ),
        };
  }

  function applyTextDraft(current: TextEditing): EditHistory {
    const next = historyWithTextDraft(historyRef.current, current);
    setCanonicalHistory(next);
    return next;
  }

  function scheduleTextPreview(current: TextEditing): void {
    if (textPreviewTimerRef.current !== null) {
      clearTimeout(textPreviewTimerRef.current);
    }
    textPreviewTimerRef.current = setTimeout(() => {
      textPreviewTimerRef.current = null;
      applyTextDraft(current);
    }, TEXT_PREVIEW_DEBOUNCE_MS);
  }

  function commitTextEdit(): void {
    const current = editingRef.current;
    if (current === null) return;
    if (textPreviewTimerRef.current !== null) {
      clearTimeout(textPreviewTimerRef.current);
      textPreviewTimerRef.current = null;
    }
    const committedHistory = applyTextDraft(current);
    editingRef.current = null;
    setEditing(null);
    if (committedHistory.ops.length > 0) {
      onChangeRef.current(
        toCanvasRevision(fold(committedHistory.ops)),
      );
    }
  }

  function cancelTextEdit(): void {
    const current = editingRef.current;
    if (current === null) return;
    if (textPreviewTimerRef.current !== null) {
      clearTimeout(textPreviewTimerRef.current);
      textPreviewTimerRef.current = null;
    }
    const next = removeTextDraft(historyRef.current, current);
    setCanonicalHistory(next);
    editingRef.current = null;
    setEditing(null);
  }

  function openTextEditor(layer: CanvasLayerInfo): void {
    if (TEXT_EDIT_KEY[layer.id] === undefined) return;
    if (
      editingRef.current !== null &&
      editingRef.current.layerId !== layer.id
    ) {
      commitTextEdit();
    }
    const seed =
      fold(historyRef.current.ops).text[layer.id] ??
      layer.initialText ??
      "";
    const next: TextEditing = {
      layerId: layer.id,
      value: seed,
      seed,
      operationId: nextOperationId(),
      before: historyRef.current,
    };
    editingRef.current = next;
    setSelectedId(layer.id);
    setEditing(next);
  }

  useEffect(() => {
    if (editing !== null) {
      textareaRef.current?.focus();
      textareaRef.current?.select();
    }
  }, [editing?.layerId]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleTextChange(value: string): void {
    const current = editingRef.current;
    if (current === null) return;
    const next = { ...current, value };
    editingRef.current = next;
    setEditing(next);
    scheduleTextPreview(next);
  }

  function handleEditKeyDown(
    event: ReactKeyboardEvent<HTMLTextAreaElement>,
  ): void {
    if (event.key === "Escape") {
      event.preventDefault();
      cancelTextEdit();
    } else if (
      event.key === "Enter" &&
      (event.metaKey || event.ctrlKey)
    ) {
      event.preventDefault();
      commitTextEdit();
    }
  }

  function nudgeSelectedLayer(deltaX: number, deltaY: number): void {
    if (selectedId === null || draggingLayerRef.current !== null) {
      return;
    }
    const current = getCanonicalTransform(selectedId);
    activeDragOpIdRef.current = nextOperationId();
    try {
      upsertTransformOperation(selectedId, {
        ...current,
        dx: current.dx + deltaX,
        dy: current.dy + deltaY,
      });
    } finally {
      activeDragOpIdRef.current = null;
    }
  }

  function handleEditorKeyDown(
    event: ReactKeyboardEvent<HTMLDivElement>,
  ): void {
    if (
      event.defaultPrevented ||
      isTextEntryTarget(event.target)
    ) {
      return;
    }
    const key = event.key.toLowerCase();

    if (!event.metaKey && !event.ctrlKey) {
      const nudgeStep = event.shiftKey ? 10 : 1;
      const nudgeDirection = NUDGE_DIRECTION[event.key];

      if (selectedId !== null && nudgeDirection !== undefined) {
        event.preventDefault();
        nudgeSelectedLayer(
          nudgeDirection[0] * nudgeStep,
          nudgeDirection[1] * nudgeStep,
        );
      } else if (
        selectedId !== null &&
        (event.key === "Delete" || event.key === "Backspace")
      ) {
        event.preventDefault();
        const isVisible =
          fold(historyRef.current.ops).visible[selectedId] ?? true;
        if (isVisible) toggleVisible(selectedId);
      } else if (key === "f") {
        event.preventDefault();
        setIsFullscreen(f => !f);
      } else if (key === "escape") {
        if (isFullscreen) {
          event.preventDefault();
          setIsFullscreen(false);
        }
      } else if (event.key === " ") {
        event.preventDefault();
        setIsSpaceDown(true);
      }
      return;
    }
    const wantsUndo = key === "z" && !event.shiftKey;
    const wantsRedo = (key === "z" && event.shiftKey) || key === "y";
    if (!wantsUndo && !wantsRedo) return;
    event.preventDefault();
    if (wantsRedo) performRedo();
    else performUndo();
  }

  function handleEditorKeyUp(event: ReactKeyboardEvent<HTMLDivElement>): void {
    if (isTextEntryTarget(event.target)) return;
    if (event.key === " ") {
      event.preventDefault();
      setIsSpaceDown(false);
      if (!isPanToolActive) setIsPanning(false);
    }
  }

  const panStartRef = useRef({
    pointerId: null as number | null,
    x: 0,
    y: 0,
    panX: 0,
    panY: 0,
  });

  function handlePanStart(event: React.PointerEvent<HTMLDivElement>): void {
    const primaryPan = isPanModeActive && event.button === 0;
    if ((!primaryPan && event.button !== 1) || panStartRef.current.pointerId !== null) {
      return;
    }
    event.preventDefault();
    stageRef.current?.focus({ preventScroll: true });
    const startPan = clampPanForZoom(pan, zoom);
    setPan(startPan);
    setIsPanning(true);
    panStartRef.current = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      panX: startPan.x,
      panY: startPan.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handlePanMove(event: React.PointerEvent<HTMLDivElement>): void {
    if (
      !isPanning ||
      panStartRef.current.pointerId !== event.pointerId ||
      !event.currentTarget.hasPointerCapture(event.pointerId)
    ) {
      return;
    }
    event.preventDefault();
    const dx = event.clientX - panStartRef.current.x;
    const dy = event.clientY - panStartRef.current.y;
    setPan(
      clampPanForZoom(
        {
          x: panStartRef.current.panX + dx,
          y: panStartRef.current.panY + dy,
        },
        zoom,
      ),
    );
  }

  function handlePanEnd(event: React.PointerEvent<HTMLDivElement>): void {
    if (panStartRef.current.pointerId !== event.pointerId) return;
    panStartRef.current.pointerId = null;
    setIsPanning(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function handleZoomChange(newZoom: number | "fit"): void {
    zoomRef.current = newZoom;
    setZoom(newZoom);
    setPan((current) =>
      newZoom === "fit"
        ? { x: 0, y: 0 }
        : clampPanForZoom(current, newZoom),
    );
  }

  function handlePanToolToggle(): void {
    if (!isPanToolActive && editingRef.current !== null) {
      commitTextEdit();
    }
    if (!isPanToolActive) setHoveredId(null);
    setIsPanToolActive((current) => !current);
  }

  function resetLayer(layerId: CanvasLayerId): void {
    transitionHistory((current) => {
      const nextOps = current.ops.filter((op) => op.layer !== layerId);
      return { ops: nextOps, redo: current.redo };
    });
  }


  function handleBeforePointerDown(
    event: ReactPointerEvent<HTMLButtonElement>,
  ): void {
    if (!showOriginalPreview()) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handleBeforePointerEnd(
    event: ReactPointerEvent<HTMLButtonElement>,
  ): void {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    restoreOriginalPreview();
  }

  function handleBeforeKeyDown(
    event: ReactKeyboardEvent<HTMLButtonElement>,
  ): void {
    if ((event.key === " " || event.key === "Enter") && !event.repeat) {
      event.preventDefault();
      showOriginalPreview();
    }
  }

  function handleBeforeKeyUp(
    event: ReactKeyboardEvent<HTMLButtonElement>,
  ): void {
    if (event.key !== " " && event.key !== "Enter") return;
    event.preventDefault();
    restoreOriginalPreview();
  }

  function toggleVisible(id: CanvasLayerId): void {
    const current =
      fold(historyRef.current.ops).visible[id] ??
      baseRef.current?.layers[id]?.baseVisible ??
      true;
    addOperation({
      id: nextOperationId(),
      layer: id,
      kind: "visible",
      visible: !current,
      label: `${current ? "Hide" : "Show"} ${LAYER_LABEL[id]}`,
    });
    if (current) setHoveredId(null);
  }

  function pickFillRole(id: CanvasLayerId, roleName: string): void {
    const current = folded.fill[id];
    addOperation({
      id: nextOperationId(),
      layer: id,
      kind: "fill",
      fillRole: current === roleName ? null : roleName,
      label: `${LAYER_LABEL[id]} color`,
    });
  }

  function layerFromEventTarget(
    target: EventTarget | null,
  ): CanvasLayerInfo | null {
    if (!(target instanceof Element)) return null;
    const group = target.closest("[data-layer]");
    if (group === null) return null;
    const raw = group.getAttribute("data-layer");
    return layers.find((layer) => layer.id === raw) ?? null;
  }

  function handleStageClick(
    event: ReactMouseEvent<HTMLDivElement>,
  ): void {
    if (isPanModeActive) return;
    stageRef.current?.focus({ preventScroll: true });
    const layer = layerFromEventTarget(event.target);
    setSelectedId(layer === null ? null : layer.id);
  }

  function handleStageDoubleClick(
    event: ReactMouseEvent<HTMLDivElement>,
  ): void {
    if (isPanModeActive) return;
    const layer = layerFromEventTarget(event.target);
    if (layer !== null) openTextEditor(layer);
  }

  const selectedLayer =
    selectedId === null
      ? null
      : (layers.find((layer) => layer.id === selectedId) ?? null);
  const selectedVisible =
    selectedLayer !== null && folded.visible[selectedLayer.id] !== false;
  const selectedBaseBox =
    selectedLayer === null ? null : layerBox(selectedLayer);
  const selectedTransform =
    selectedLayer === null
      ? IDENTITY_TRANSFORM
      : (folded.transform[selectedLayer.id] ?? IDENTITY_TRANSFORM);
  const selectedBox =
    selectedVisible && selectedBaseBox !== null
      ? orientedBoxOf(selectedBaseBox, selectedTransform)
      : null;

  const hoveredLayer =
    hoveredId === null
      ? null
      : (layers.find((layer) => layer.id === hoveredId) ?? null);
  const hoveredBaseBox =
    hoveredLayer === null ? null : layerBox(hoveredLayer);
  const hoveredBox =
    hoveredLayer !== null &&
    hoveredBaseBox !== null &&
    folded.visible[hoveredLayer.id] !== false
      ? transformedBBox(
          hoveredBaseBox,
          folded.transform[hoveredLayer.id] ?? IDENTITY_TRANSFORM,
        )
      : null;

  const visualZoom = zoom === "fit" ? 1 : zoom;
  const unit =
    stageWidth > 0 ? viewBox.w / (stageWidth * visualZoom) : 1;
  const pxPerUnit = stageWidth > 0 ? stageWidth / viewBox.w : 0;
  const safeAreaInset =
    Math.min(viewBox.w, viewBox.h) * SAFE_AREA_INSET_RATIO;
  const rulerMajorStep = niceRulerStep(unit * RULER_LABEL_SPACING_PX);
  const rulerMinorStep = rulerMajorStep / RULER_MINOR_DIVISIONS;
  const rulerXValues = rulerValues(
    viewBox.x,
    viewBox.x + viewBox.w,
    rulerMinorStep,
  );
  const rulerYValues = rulerValues(
    viewBox.y,
    viewBox.y + viewBox.h,
    rulerMinorStep,
  );

  const editingLayer =
    editing === null
      ? null
      : (layers.find((layer) => layer.id === editing.layerId) ?? null);
  const editingBaseBox =
    editingLayer === null ? null : layerBox(editingLayer);
  const editingTransform =
    editingLayer === null
      ? IDENTITY_TRANSFORM
      : (folded.transform[editingLayer.id] ?? IDENTITY_TRANSFORM);
  const editingBox =
    editingLayer !== null && editingBaseBox !== null
      ? transformedBBox(editingBaseBox, editingTransform)
      : null;
  const editingTextLayout =
    editing === null
      ? null
      : (baseRef.current?.layers[editing.layerId]?.textLayout ?? null);


  const overflowingLayers = layers.filter(
    (layer) => overflow[layer.id] === true,
  );

  const inspectorProps: InspectorProps = {
    layers: layers.map((layer) => ({
      id: layer.id,
      isVisible: folded.visible[layer.id] !== false,
      hasText: TEXT_EDIT_KEY[layer.id] !== undefined,
      canRecolor: RECOLORABLE.has(layer.id),
    })),
    selectedId,
    onSelect: setSelectedId,
    onToggleVisible: toggleVisible,
    onEditText: (id): void => {
      const layer = layers.find((candidate) => candidate.id === id);
      if (layer !== undefined) openTextEditor(layer);
    },
    brandColors,
    selectedFillRole:
      selectedLayer === null ? null : folded.fill[selectedLayer.id],
    onPickFillRole: pickFillRole,
    onResetLayer: resetLayer,
    canResetSelectedLayer:
      selectedLayer !== null &&
      history.ops.some((operation) => operation.layer === selectedLayer.id),
    askText: askText ?? "",
    onAskTextChange: onAskTextChange ?? ((): void => {}),
    onAddAsk: onAddAsk ?? ((): void => {}),
    busy: busy ?? false,
  };

  return (
    <div
      ref={stageRef}
      className="creview__stage"
      data-canvas-stage-layout=""
      data-canvas-fullscreen={isFullscreen ? "" : undefined}
      aria-label="Creative canvas"
      tabIndex={0}
      onKeyDown={handleEditorKeyDown}
      onKeyUp={handleEditorKeyUp}
      style={{
        display: "flex",
        gap: "var(--sp-4)",
        ...(isFullscreen ? {
          position: "fixed",
          inset: 0,
          zIndex: 50,
          background: "var(--canvas)",
          padding: "var(--sp-4)"
        } : {})
      }}
    >
      <div
        data-canvas-column=""
        style={{ 
          flex: 1, 
          minWidth: 0, 
          display: "flex", 
          flexDirection: "column", 
          gap: "var(--sp-3)", 
          position: "relative",
        }}
      >
        <div className="creview__stage-head">
          <span className="creview__meta">Canvas</span>
          <span className="creview__meta creview__meta--muted">
            {hoveredLayer !== null
              ? `${LAYER_LABEL[hoveredLayer.id]} target`
              : selectedLayer === null
                ? "No layer selected"
                : LAYER_LABEL[selectedLayer.id]}
          </span>
          <span className="creview__meta creview__meta--muted">
            {history.ops.length} pending
          </span>
          <button
            type="button"
            className="btn btn--ghost btn--sm creview__compare"
            aria-pressed={showingOriginal}
            title="Hold to show the original creative"
            disabled={editing !== null || draggingLayer !== null}
            onPointerDown={handleBeforePointerDown}
            onPointerUp={handleBeforePointerEnd}
            onPointerCancel={handleBeforePointerEnd}
            onLostPointerCapture={restoreOriginalPreview}
            onKeyDown={handleBeforeKeyDown}
            onKeyUp={handleBeforeKeyUp}
            onBlur={restoreOriginalPreview}
          >
            Before/After
          </button>
          <span className="creview__hint">
            {isPanToolActive
              ? "Pan tool active · drag the canvas to move it"
              : "Click a layer · drag to move · scroll to pan"}
          </span>
        </div>

        <div
          ref={canvasWrapRef}
          className="creview__canvas-wrap"
          data-canvas-wrap=""
          style={{
            flex: 1,
            overflow: "hidden",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
            cursor: isPanModeActive
              ? isPanning
                ? "grabbing"
                : "grab"
              : "default",
            touchAction: isPanModeActive ? "none" : "auto",
            overscrollBehavior: "contain",
          }}
          onPointerDown={handlePanStart}
          onPointerMove={handlePanMove}
          onPointerUp={handlePanEnd}
          onPointerCancel={handlePanEnd}
          onLostPointerCapture={handlePanEnd}
        >
          {showingOriginal && (
            <span className="creview__original-badge" role="status" style={{ zIndex: 10 }}>
              Showing original
            </span>
          )}

          <div
            role="group"
            aria-label="Canvas alignment aids"
            style={{
              position: "absolute",
              top: "12px",
              right: "12px",
              zIndex: 12,
              display: "flex",
              gap: "4px",
              padding: "3px",
              borderRadius: "var(--r-sm)",
              background: "var(--surface)",
              boxShadow: "var(--shadow-pop)",
            }}
            onPointerDown={(event): void => event.stopPropagation()}
            onKeyDown={(event): void => event.stopPropagation()}
          >
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              aria-pressed={showRulers}
              title="Toggle canvas rulers"
              onClick={(): void => setShowRulers((current) => !current)}
            >
              Rulers
            </button>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              aria-pressed={showSafeArea}
              title="Toggle margins and center guides"
              onClick={(): void => setShowSafeArea((current) => !current)}
            >
              Safe area
            </button>
          </div>
          
          <div
            className="creview__canvas creview__canvas--locked"
            style={{
              width: "100%",
              maxWidth: zoom === "fit" ? "620px" : `${viewBox.w}px`,
              marginInline: "auto",
              overflow: "visible",
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom === "fit" ? 1 : zoom})`,
              transformOrigin: "center",
              transition:
                isPanning || isWheelPanning
                  ? "none"
                  : "transform 0.15s ease",
              cursor: isPanModeActive
                ? isPanning
                  ? "grabbing"
                  : "grab"
                : "default",
            }}
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
                />
                
                {/* Overlay SVG */}
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
                  {showSafeArea && (
                    <g
                      data-canvas-safe-area=""
                      aria-hidden="true"
                      style={{ pointerEvents: "none" }}
                    >
                      <rect
                        x={viewBox.x + safeAreaInset}
                        y={viewBox.y + safeAreaInset}
                        width={Math.max(viewBox.w - safeAreaInset * 2, 0)}
                        height={Math.max(viewBox.h - safeAreaInset * 2, 0)}
                        fill="none"
                        stroke="var(--ink)"
                        strokeOpacity="0.28"
                        strokeWidth={unit}
                        strokeDasharray={`${6 * unit} ${5 * unit}`}
                      />
                      <line
                        x1={viewBox.x + viewBox.w / 2}
                        y1={viewBox.y + safeAreaInset}
                        x2={viewBox.x + viewBox.w / 2}
                        y2={viewBox.y + viewBox.h - safeAreaInset}
                        stroke="var(--ink)"
                        strokeOpacity="0.2"
                        strokeWidth={unit}
                        strokeDasharray={`${5 * unit} ${5 * unit}`}
                      />
                      <line
                        x1={viewBox.x + safeAreaInset}
                        y1={viewBox.y + viewBox.h / 2}
                        x2={viewBox.x + viewBox.w - safeAreaInset}
                        y2={viewBox.y + viewBox.h / 2}
                        stroke="var(--ink)"
                        strokeOpacity="0.2"
                        strokeWidth={unit}
                        strokeDasharray={`${5 * unit} ${5 * unit}`}
                      />
                    </g>
                  )}

                  {showRulers && (
                    <g
                      data-canvas-rulers=""
                      aria-hidden="true"
                      style={{
                        pointerEvents: "none",
                        fontFamily: "var(--font-mono, monospace)",
                      }}
                    >
                      <rect
                        x={viewBox.x}
                        y={viewBox.y}
                        width={viewBox.w}
                        height={RULER_SIZE_PX * unit}
                        fill="var(--surface)"
                        fillOpacity="0.92"
                      />
                      <rect
                        x={viewBox.x}
                        y={viewBox.y}
                        width={RULER_SIZE_PX * unit}
                        height={viewBox.h}
                        fill="var(--surface)"
                        fillOpacity="0.92"
                      />
                      {rulerXValues.map((value) => {
                        const major = isMajorRulerValue(
                          value,
                          rulerMajorStep,
                        );
                        const tickLength = (major ? 8 : 4) * unit;
                        return (
                          <g key={`ruler-x-${value}`}>
                            <line
                              data-ruler-axis="x"
                              x1={value}
                              y1={
                                viewBox.y +
                                RULER_SIZE_PX * unit -
                                tickLength
                              }
                              x2={value}
                              y2={viewBox.y + RULER_SIZE_PX * unit}
                              stroke="var(--ink)"
                              strokeOpacity={major ? 0.62 : 0.34}
                              strokeWidth={unit}
                            />
                            {major &&
                              value >
                                viewBox.x + (RULER_SIZE_PX + 3) * unit && (
                                <text
                                  x={value + 3 * unit}
                                  y={viewBox.y + 9 * unit}
                                  fill="var(--ink)"
                                  fillOpacity="0.72"
                                  fontSize={9 * unit}
                                  fontWeight="600"
                                >
                                  {formatRulerValue(value, rulerMajorStep)}
                                </text>
                              )}
                          </g>
                        );
                      })}
                      {rulerYValues.map((value) => {
                        const major = isMajorRulerValue(
                          value,
                          rulerMajorStep,
                        );
                        const tickLength = (major ? 8 : 4) * unit;
                        const labelX = viewBox.x + 8 * unit;
                        const labelY = value - 3 * unit;
                        return (
                          <g key={`ruler-y-${value}`}>
                            <line
                              data-ruler-axis="y"
                              x1={
                                viewBox.x +
                                RULER_SIZE_PX * unit -
                                tickLength
                              }
                              y1={value}
                              x2={viewBox.x + RULER_SIZE_PX * unit}
                              y2={value}
                              stroke="var(--ink)"
                              strokeOpacity={major ? 0.62 : 0.34}
                              strokeWidth={unit}
                            />
                            {major &&
                              value >
                                viewBox.y + (RULER_SIZE_PX + 3) * unit && (
                                <text
                                  x={labelX}
                                  y={labelY}
                                  fill="var(--ink)"
                                  fillOpacity="0.72"
                                  fontSize={9 * unit}
                                  fontWeight="600"
                                  transform={`rotate(-90 ${labelX} ${labelY})`}
                                >
                                  {formatRulerValue(value, rulerMajorStep)}
                                </text>
                              )}
                          </g>
                        );
                      })}
                      <rect
                        x={viewBox.x}
                        y={viewBox.y}
                        width={RULER_SIZE_PX * unit}
                        height={RULER_SIZE_PX * unit}
                        fill="var(--surface)"
                      />
                      <line
                        x1={viewBox.x}
                        y1={viewBox.y + RULER_SIZE_PX * unit}
                        x2={viewBox.x + viewBox.w}
                        y2={viewBox.y + RULER_SIZE_PX * unit}
                        stroke="var(--ink)"
                        strokeOpacity="0.28"
                        strokeWidth={unit}
                      />
                      <line
                        x1={viewBox.x + RULER_SIZE_PX * unit}
                        y1={viewBox.y}
                        x2={viewBox.x + RULER_SIZE_PX * unit}
                        y2={viewBox.y + viewBox.h}
                        stroke="var(--ink)"
                        strokeOpacity="0.28"
                        strokeWidth={unit}
                      />
                    </g>
                  )}

                  {layers.map((layer) => {
                    const base = layerBox(layer);
                    if (base === null) return null;
                    const box = transformedBBox(
                      base,
                      folded.transform[layer.id] ?? IDENTITY_TRANSFORM,
                    );
                    const visible = folded.visible[layer.id] !== false;
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
                          pointerEvents:
                            visible && !isPanModeActive ? "all" : "none",
                          touchAction: "none",
                          cursor: draggingLayer !== null ? "grabbing" : "grab",
                        }}
                        onPointerEnter={(): void => setHoveredId(layer.id)}
                        onPointerLeave={(): void =>
                          setHoveredId((current) =>
                            current === layer.id ? null : current,
                          )
                        }
                        onPointerDown={(event): void => {
                          if (event.button === 1) return;
                          stageRef.current?.focus({ preventScroll: true });
                          setSelectedId(layer.id);
                          beginMove(layer.id, event);
                        }}
                        onDoubleClick={(event): void => {
                          event.stopPropagation();
                          openTextEditor(layer);
                        }}
                      />
                    );
                  })}
                  {snapLines !== null && (
                    <g
                      data-canvas-snap-lines=""
                      aria-hidden="true"
                      style={{ pointerEvents: "none" }}
                    >
                      {snapLines.x !== null && (
                        <line
                          data-snap-axis="x"
                          x1={snapLines.x}
                          y1={viewBox.y}
                          x2={snapLines.x}
                          y2={viewBox.y + viewBox.h}
                          stroke="var(--accent)"
                          strokeOpacity="0.95"
                          strokeWidth={1.5 * unit}
                        />
                      )}
                      {snapLines.y !== null && (
                        <line
                          data-snap-axis="y"
                          x1={viewBox.x}
                          y1={snapLines.y}
                          x2={viewBox.x + viewBox.w}
                          y2={snapLines.y}
                          stroke="var(--accent)"
                          strokeOpacity="0.95"
                          strokeWidth={1.5 * unit}
                        />
                      )}
                    </g>
                  )}
                </svg>

                {hoveredLayer !== null &&
                  hoveredBox !== null &&
                  !isPanModeActive && (
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
                    <rect
                      x={hoveredBox.x}
                      y={hoveredBox.y}
                      width={hoveredBox.w}
                      height={hoveredBox.h}
                      fill="transparent"
                      stroke="var(--accent)"
                      strokeOpacity="0.5"
                      strokeWidth={1.25 * unit}
                    />
                    <text
                      x={hoveredBox.x + 5 * unit}
                      y={hoveredBox.y - 7 * unit}
                      fill="var(--ink)"
                      fontSize={11 * unit}
                      fontWeight="600"
                    >
                      {LAYER_LABEL[hoveredLayer.id]}
                    </text>
                  </svg>
                )}

                {selectedLayer !== null &&
                  selectedBaseBox !== null &&
                  selectedBox !== null &&
                  !isPanModeActive && (
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
                      <g
                        transform={`rotate(${selectedBox.rotation} ${selectedBox.cx} ${selectedBox.cy})`}
                      >
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
                          onPointerDown={(event): void => {
                            if (event.button === 1) return;
                            beginMove(selectedLayer.id, event);
                          }}
                          onDoubleClick={(event): void => {
                            event.stopPropagation();
                            openTextEditor(selectedLayer);
                          }}
                        />
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
                            cursor:
                              draggingLayer === selectedLayer.id
                                ? "grabbing"
                                : "grab",
                          }}
                          aria-label="Rotate layer"
                          onPointerDown={(event): void => {
                            if (event.button === 1) return;
                            beginRotate(
                              selectedLayer.id,
                              event,
                              selectedBaseBox,
                              selectedTransform,
                            );
                          }}
                        />
                        {RESIZE_HANDLES.map((resizeHandle) => (
                          <rect
                            key={resizeHandle.handle}
                            data-resize-handle={resizeHandle.handle}
                            x={
                              selectedBox.x +
                              selectedBox.w * resizeHandle.xFactor -
                              (RESIZE_HANDLE_SIZE_PX * unit) / 2
                            }
                            y={
                              selectedBox.y +
                              selectedBox.h * resizeHandle.yFactor -
                              (RESIZE_HANDLE_SIZE_PX * unit) / 2
                            }
                            width={RESIZE_HANDLE_SIZE_PX * unit}
                            height={RESIZE_HANDLE_SIZE_PX * unit}
                            rx={RESIZE_HANDLE_RADIUS_PX * unit}
                            fill="var(--surface)"
                            stroke="var(--accent)"
                            strokeWidth={1.5 * unit}
                            style={{
                              pointerEvents: "all",
                              touchAction: "none",
                              cursor: resizeHandle.cursor,
                            }}
                            // Gate 4a resize deltas remain screen-axis based. Rotation is
                            // preserved, but resize directions are only exact at 0 degrees.
                            onPointerDown={(event): void => {
                              if (event.button === 1) return;
                              beginResize(
                                selectedLayer.id,
                                resizeHandle.handle,
                                event,
                                selectedBaseBox,
                                selectedTransform,
                              );
                            }}
                          />
                        ))}
                      </g>
                    </svg>
                  )}

                {editing !== null &&
                  editingBox !== null &&
                  editingTextLayout !== null && (
                    <div
                      style={{
                        position: "absolute",
                        left: `${(editingBox.x - viewBox.x) * pxPerUnit}px`,
                        top: `${(editingBox.y - viewBox.y) * pxPerUnit}px`,
                        width: `${Math.max(editingBox.w * pxPerUnit, 1)}px`,
                        zIndex: 3,
                      }}
                    >
                      <textarea
                        ref={textareaRef}
                        className="creview__input"
                        value={editing.value}
                        maxLength={MAX_TEXT_CHARS}
                        rows={2}
                        aria-label={`Edit ${LAYER_LABEL[editing.layerId]} text`}
                        style={{
                          boxSizing: "border-box",
                          width: "100%",
                          height: `${Math.max(
                            editingBox.h * pxPerUnit,
                            editingTextLayout.lineHeight *
                              pxPerUnit *
                              editingTransform.scaleY *
                              2,
                          )}px`,
                          minHeight: 0,
                          resize: "none",
                          fontSize: `${Math.max(
                            editingTextLayout.fontSize *
                              pxPerUnit *
                              editingTransform.scaleY,
                            10,
                          )}px`,
                          lineHeight: `${Math.max(
                            editingTextLayout.lineHeight *
                              pxPerUnit *
                              editingTransform.scaleY,
                            12,
                          )}px`,
                          textAlign: textAlignForAnchor(
                            editingTextLayout.textAnchor,
                          ),
                          boxShadow: "var(--shadow-pop)",
                        }}
                        onChange={(event): void =>
                          handleTextChange(event.target.value)
                        }
                        onBlur={commitTextEdit}
                        onKeyDown={handleEditKeyDown}
                      />
                      <span
                        style={{
                          display: "block",
                          marginTop: "4px",
                          padding: "3px 6px",
                          borderRadius: "var(--r-xs)",
                          color: "var(--muted)",
                          background: "var(--surface)",
                          boxShadow: "var(--shadow-pop)",
                          fontSize: "11px",
                          lineHeight: 1.35,
                        }}
                      >
                        Enter adds a line · ⌘/Ctrl+Enter applies · Esc cancels
                      </span>
                    </div>
                  )}
              </>
            )}
          </div>
        </div>

        <div
          data-canvas-zoom=""
          style={{
            position: "absolute",
            bottom: "16px",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 10,
          }}
        >
           <ZoomControls
             zoom={zoom}
             onZoomChange={handleZoomChange}
             isPanToolActive={isPanToolActive}
             onTogglePanTool={handlePanToolToggle}
             creativeSize={{ w: viewBox.w, h: viewBox.h }}
             creativeFormat={Math.abs(viewBox.w / viewBox.h - 1) < 0.01 ? "Square / IG Post" : (Math.abs(viewBox.w / viewBox.h - 4/5) < 0.01 ? "IG Portrait" : (Math.abs(viewBox.w / viewBox.h - 9/16) < 0.01 ? "Story" : (viewBox.w > viewBox.h ? "Landscape" : "Portrait")))}
             isFullscreen={isFullscreen}
             onToggleFullscreen={() => setIsFullscreen(f => !f)}
           />
        </div>
        
        {overflowingLayers.length > 0 && (
          <div
            data-canvas-overflow=""
            style={{
              position: "absolute",
              top: "16px",
              left: "50%",
              transform: "translateX(-50%)",
              zIndex: 10,
            }}
          >
             <p className="creview__thread-empty" role="status" style={{ margin: 0, background: "var(--surface)", padding: "4px 12px", borderRadius: "var(--r-full)", boxShadow: "var(--shadow-pop)", fontSize: "12px" }}>
               {overflowingLayers.map((layer) => `${LAYER_LABEL[layer.id]} text may overflow`).join(" · ")}
             </p>
          </div>
        )}
      </div>
      
      <div data-canvas-inspector-desktop="">
        <Inspector {...inspectorProps} />
      </div>

      <details
        data-canvas-inspector-mobile=""
        onKeyDown={(event): void => {
          if (event.key === " ") event.stopPropagation();
        }}
        onKeyUp={(event): void => {
          if (event.key === " ") event.stopPropagation();
        }}
      >
        <summary className="btn btn--secondary">
          Layers &amp; properties
        </summary>
        <div data-canvas-inspector-content="">
          <Inspector {...inspectorProps} />
        </div>
      </details>

      <style jsx global>{`
        [data-canvas-stage-layout] {
          flex-direction: row;
        }

        [data-canvas-inspector-desktop] {
          display: contents;
        }

        [data-canvas-inspector-mobile] {
          display: none;
        }

        @media (max-width: 767px) {
          [data-canvas-stage-layout] {
            flex: 0 0 auto;
            flex-direction: column;
            width: 100%;
            max-width: 100%;
            min-width: 0;
            min-height: 0;
            box-sizing: border-box;
            overflow-x: clip;
          }

          [data-canvas-stage-layout][data-canvas-fullscreen] {
            height: 100dvh;
            padding-top: calc(var(--sp-4) + 60px) !important;
            overflow-y: auto;
          }

          [data-canvas-column] {
            flex: 0 0 auto !important;
            width: 100%;
            max-width: 100%;
            min-width: 0;
          }

          [data-canvas-wrap] {
            width: 100%;
            max-width: 100%;
            min-width: 0;
            min-height: max(320px, 58vh) !important;
            box-sizing: border-box;
          }

          [data-canvas-inspector-desktop] {
            display: none;
          }

          [data-canvas-inspector-mobile] {
            display: block;
            width: 100%;
            max-width: 100%;
            min-width: 0;
            box-sizing: border-box;
          }

          [data-canvas-inspector-mobile] > summary {
            width: 100%;
            max-width: 100%;
            min-height: 44px;
            box-sizing: border-box;
          }

          [data-canvas-inspector-content] {
            width: 100%;
            max-width: 100%;
            min-width: 0;
            max-height: min(42vh, 420px);
            box-sizing: border-box;
            overflow-y: auto;
            overscroll-behavior: contain;
          }

          [data-canvas-inspector-content] > .review-panel {
            width: 100%;
            max-width: 100%;
            min-width: 0;
            height: auto !important;
            margin: 0;
            box-sizing: border-box;
            overflow-y: visible;
          }

          [data-canvas-zoom] {
            right: var(--sp-3);
            bottom: var(--sp-3) !important;
            left: var(--sp-3) !important;
            width: auto;
            max-width: 100%;
            transform: none !important;
          }

          [data-canvas-zoom] > div {
            width: 100%;
            max-width: 100%;
            box-sizing: border-box;
            flex-wrap: wrap;
            justify-content: center;
            gap: var(--sp-2) !important;
            padding: var(--sp-2) !important;
          }

          [data-canvas-overflow] {
            right: var(--sp-3);
            left: var(--sp-3) !important;
            max-width: 100%;
            transform: none !important;
          }

          [data-canvas-overflow] > p {
            max-width: 100%;
            overflow-wrap: anywhere;
            white-space: normal;
          }
        }
      `}</style>
    </div>
  );
}
