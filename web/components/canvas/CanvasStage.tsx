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
  orientedBoxOf,
  redo as redoHistory,
  removeOp as removeHistoryOp,
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
} from "./editor-state";
import { useLayerDrag, type ResizeHandle } from "./useLayerDrag";
import { Inspector } from "./Inspector";
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

  const [zoom, setZoom] = useState<number | "fit">("fit");
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isSpaceDown, setIsSpaceDown] = useState(false);
  const [isPanning, setIsPanning] = useState(false);

  const [mounted, setMounted] = useState(false);
  const [stageWidth, setStageWidth] = useState(0);
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

  historyRef.current = history;
  foldedRef.current = folded;
  editingRef.current = editing;
  brandColorsRef.current = brandColors;

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
      foldedRef.current.transform[layerId] ?? IDENTITY_TRANSFORM,
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

  const { draggingLayer, beginMove, beginResize, beginRotate } = useLayerDrag({
    getScreenToViewBox,
    getTransform: getCanonicalTransform,
    onDragStart: (): void => {
      activeDragOpIdRef.current = nextOperationId();
    },
    onDragMove: upsertTransformOperation,
    onDragEnd: (layerId, transform): void => {
      upsertTransformOperation(layerId, transform);
      activeDragOpIdRef.current = null;
    },
  });
  draggingLayerRef.current = draggingLayer;

  const layerBox = useCallback(
    (layer: CanvasLayerInfo): LayerBBox | null =>
      measured[layer.id] ?? layer.bbox,
    [measured],
  );

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
    if (host === null) return undefined;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry !== undefined) setStageWidth(entry.contentRect.width);
    });
    observer.observe(host);
    setStageWidth(host.getBoundingClientRect().width);
    return (): void => observer.disconnect();
  }, [parsed]);

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
    };
  }, []);

  function addOperation(operation: DocOp): void {
    const next = appendOp(historyRef.current, operation);
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
      if (key === "f") {
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
      setIsPanning(false);
    }
  }

  function handleWheel(event: React.WheelEvent<HTMLDivElement>): void {
    if (event.metaKey || event.ctrlKey) {
      event.preventDefault();
      const delta = event.deltaY > 0 ? -0.1 : 0.1;
      setZoom(z => {
        const current = z === "fit" ? 1 : z;
        return Math.max(0.1, Math.min(5, current + delta));
      });
    }
  }

  const panStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

  function handlePanStart(event: React.PointerEvent<HTMLDivElement>): void {
    if ((isSpaceDown || event.button === 1) && zoom !== "fit") {
      event.preventDefault();
      setIsPanning(true);
      panStartRef.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  }

  function handlePanMove(event: React.PointerEvent<HTMLDivElement>): void {
    if (isPanning && event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.preventDefault();
      const dx = event.clientX - panStartRef.current.x;
      const dy = event.clientY - panStartRef.current.y;
      setPan({ x: panStartRef.current.panX + dx, y: panStartRef.current.panY + dy });
    }
  }

  function handlePanEnd(event: React.PointerEvent<HTMLDivElement>): void {
    if (isPanning) {
      setIsPanning(false);
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
    }
  }

  function handleZoomChange(newZoom: number | "fit"): void {
    setZoom(newZoom);
    if (newZoom === "fit") setPan({ x: 0, y: 0 });
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
    const current = folded.visible[id] ?? true;
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
    const layer = layerFromEventTarget(event.target);
    setSelectedId(layer === null ? null : layer.id);
  }

  function handleStageDoubleClick(
    event: ReactMouseEvent<HTMLDivElement>,
  ): void {
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

  return (
    <div
      className="creview__stage"
      aria-label="Creative canvas"
      tabIndex={0}
      onKeyDown={handleEditorKeyDown}
      onKeyUp={handleEditorKeyUp}
      style={{
        display: "flex",
        flexDirection: "row",
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
        style={{ 
          flex: 1, 
          minWidth: 0, 
          display: "flex", 
          flexDirection: "column", 
          gap: "var(--sp-3)", 
          position: "relative",
          cursor: isSpaceDown ? (isPanning ? "grabbing" : "grab") : "default"
        }}
        onPointerDown={handlePanStart}
        onPointerMove={handlePanMove}
        onPointerUp={handlePanEnd}
        onWheel={handleWheel}
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
            Click a layer · drag to move · double-click text to edit
          </span>
        </div>

        <div className="creview__canvas-wrap" style={{ flex: 1, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
          {showingOriginal && (
            <span className="creview__original-badge" role="status" style={{ zIndex: 10 }}>
              Showing original
            </span>
          )}
          
          <div
            className="creview__canvas creview__canvas--locked"
            style={{
              width: "100%",
              maxWidth: zoom === "fit" ? "620px" : `${viewBox.w}px`,
              marginInline: "auto",
              overflow: "visible",
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom === "fit" ? 1 : zoom})`,
              transformOrigin: "center",
              transition: isPanning ? "none" : "transform 0.15s ease",
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
                          pointerEvents: visible && !isSpaceDown ? "all" : "none",
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
                </svg>

                {hoveredLayer !== null && hoveredBox !== null && !isSpaceDown && (
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
                  selectedBox !== null && !isSpaceDown && (
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
                          onPointerDown={(event): void =>
                            beginMove(selectedLayer.id, event)
                          }
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
                          onPointerDown={(event): void =>
                            beginRotate(
                              selectedLayer.id,
                              event,
                              selectedBaseBox,
                              selectedTransform,
                            )
                          }
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
                            onPointerDown={(event): void =>
                              beginResize(
                                selectedLayer.id,
                                resizeHandle.handle,
                                event,
                                selectedBaseBox,
                                selectedTransform,
                              )
                            }
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

        <div style={{ position: "absolute", bottom: "16px", left: "50%", transform: "translateX(-50%)", zIndex: 10 }}>
           <ZoomControls
             zoom={zoom}
             onZoomChange={handleZoomChange}
             creativeSize={{ w: viewBox.w, h: viewBox.h }}
             creativeFormat={Math.abs(viewBox.w / viewBox.h - 1) < 0.01 ? "Square / IG Post" : (Math.abs(viewBox.w / viewBox.h - 4/5) < 0.01 ? "IG Portrait" : (Math.abs(viewBox.w / viewBox.h - 9/16) < 0.01 ? "Story" : (viewBox.w > viewBox.h ? "Landscape" : "Portrait")))}
             isFullscreen={isFullscreen}
             onToggleFullscreen={() => setIsFullscreen(f => !f)}
           />
        </div>
        
        {overflowingLayers.length > 0 && (
          <div style={{ position: "absolute", top: "16px", left: "50%", transform: "translateX(-50%)", zIndex: 10 }}>
             <p className="creview__thread-empty" role="status" style={{ margin: 0, background: "var(--surface)", padding: "4px 12px", borderRadius: "var(--r-full)", boxShadow: "var(--shadow-pop)", fontSize: "12px" }}>
               {overflowingLayers.map((layer) => `${LAYER_LABEL[layer.id]} text may overflow`).join(" · ")}
             </p>
          </div>
        )}
      </div>
      
      <Inspector 
         layers={layers.map(l => ({
            id: l.id,
            isVisible: folded.visible[l.id] !== false,
            hasText: TEXT_EDIT_KEY[l.id] !== undefined,
            canRecolor: RECOLORABLE.has(l.id)
         }))}
         selectedId={selectedId}
         onSelect={setSelectedId}
         onToggleVisible={toggleVisible}
         onEditText={(id) => openTextEditor(layers.find(l => l.id === id)!)}
         brandColors={brandColors}
         selectedFillRole={selectedLayer ? folded.fill[selectedLayer.id] : null}
         onPickFillRole={pickFillRole}
         onResetLayer={resetLayer}
         canResetSelectedLayer={selectedLayer ? history.ops.some(op => op.layer === selectedLayer.id) : false}
         askText={askText ?? ""}
         onAskTextChange={onAskTextChange ?? (() => {})}
         onAddAsk={onAddAsk ?? (() => {})}
         busy={busy ?? false}
      />
    </div>
  );
}
