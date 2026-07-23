import type {
  ApiCanvasRevision,
  ApiLayerOp,
  ApiTextEdits,
  CanvasLayerId,
} from "./canvas-types";
import type { ApiColorRole } from "@/lib/api";

export type OpKind = "text" | "fill" | "visible" | "transform";

export interface LayerTransform {
  dx: number;
  dy: number;
  scaleX: number;
  scaleY: number;
  /** Degrees about the layer's base-bbox center. Legacy transforms default to 0. */
  rotation?: number;
}

export interface LayerBBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface OrientedLayerBox extends LayerBBox {
  cx: number;
  cy: number;
  rotation: number;
}

export interface AlignmentGuides {
  x: readonly number[];
  y: readonly number[];
}

export interface SnapLines {
  x: number | null;
  y: number | null;
}

export interface SnappedLayerTransform {
  transform: LayerTransform;
  lines: SnapLines;
}

export interface DocOp {
  id: string;
  layer: CanvasLayerId;
  kind: OpKind;
  text?: string;
  fillRole?: string | null;
  visible?: boolean;
  transform?: LayerTransform;
  label: string;
}

export interface EditHistory {
  ops: DocOp[];
  redo: DocOp[];
}

export interface FoldedState {
  text: Partial<Record<CanvasLayerId, string>>;
  fill: Partial<Record<CanvasLayerId, string | null>>;
  visible: Partial<Record<CanvasLayerId, boolean>>;
  transform: Partial<Record<CanvasLayerId, LayerTransform>>;
}

export interface BaseLayerCapture {
  id: CanvasLayerId;
  bbox: LayerBBox;
  baseTransform: string;
  baseStyle: string | null;
  baseTextHTML: string | null;
  baseFill: string | null;
  initialText: string | null;
}

export interface BaseTextLayout {
  x: string;
  y: number;
  lineHeight: number;
  fontSize: number;
  textAnchor: string;
}

export interface BaseLayerState extends BaseLayerCapture {
  textLayout: BaseTextLayout | null;
}

export interface EditorBaseState {
  layers: Partial<Record<CanvasLayerId, BaseLayerState>>;
  brandColors: readonly ApiColorRole[];
  lastApplied: FoldedState | null;
  overflow: Partial<Record<CanvasLayerId, boolean>>;
}

export interface ApplyStateResult {
  dirty: CanvasLayerId[];
  overflow: Partial<Record<CanvasLayerId, boolean>>;
}

export const IDENTITY_TRANSFORM: LayerTransform = {
  dx: 0,
  dy: 0,
  scaleX: 1,
  scaleY: 1,
  rotation: 0,
};

export const EDITOR_LAYER_IDS: readonly CanvasLayerId[] = [
  "layer-background",
  "layer-panel",
  "layer-headline",
  "layer-subhead",
  "layer-cta",
  "layer-badge",
];

export const RECOLOR_TARGET: Record<CanvasLayerId, "text" | "rect" | null> = {
  "layer-background": null,
  "layer-panel": "rect",
  "layer-headline": "text",
  "layer-subhead": "text",
  "layer-cta": "text",
  "layer-badge": "rect",
};

export const TEXT_TARGET: Record<CanvasLayerId, "text" | null> = {
  "layer-background": null,
  "layer-panel": null,
  "layer-headline": "text",
  "layer-subhead": "text",
  "layer-cta": "text",
  "layer-badge": null,
};

const TEXT_EDIT_KEY: Partial<Record<CanvasLayerId, keyof ApiTextEdits>> = {
  "layer-headline": "headline",
  "layer-subhead": "subhead",
  "layer-cta": "cta",
};

export function appendOp(history: EditHistory, operation: DocOp): EditHistory {
  return { ops: [...history.ops, operation], redo: [] };
}

export function undo(history: EditHistory): EditHistory {
  const operation = history.ops.at(-1);
  if (operation === undefined) return history;
  return {
    ops: history.ops.slice(0, -1),
    redo: [...history.redo, operation],
  };
}

export function redo(history: EditHistory): EditHistory {
  const operation = history.redo.at(-1);
  if (operation === undefined) return history;
  return {
    ops: [...history.ops, operation],
    redo: history.redo.slice(0, -1),
  };
}

export function canUndo(history: EditHistory): boolean {
  return history.ops.length > 0;
}

export function canRedo(history: EditHistory): boolean {
  return history.redo.length > 0;
}

export function removeOp(history: EditHistory, operationId: string): EditHistory {
  return {
    ops: history.ops.filter((operation) => operation.id !== operationId),
    redo: history.redo,
  };
}

export function fold(ops: readonly DocOp[]): FoldedState {
  const folded: FoldedState = {
    text: {},
    fill: {},
    visible: {},
    transform: {},
  };

  for (const operation of ops) {
    switch (operation.kind) {
      case "text":
        if (operation.text !== undefined) folded.text[operation.layer] = operation.text;
        break;
      case "fill":
        if (operation.fillRole !== undefined) {
          folded.fill[operation.layer] = operation.fillRole;
        }
        break;
      case "visible":
        if (operation.visible !== undefined) {
          folded.visible[operation.layer] = operation.visible;
        }
        break;
      case "transform":
        if (operation.transform !== undefined) {
          folded.transform[operation.layer] = operation.transform;
        }
        break;
    }
  }

  return folded;
}

function hasOwn(record: object, key: PropertyKey): boolean {
  return Object.prototype.hasOwnProperty.call(record, key);
}

function round(value: number, places: number): number {
  const factor = 10 ** places;
  return Math.round(value * factor) / factor;
}

/** Keep an axis scale inside the contract's (0, 3] bound (matches the editor's [0.1, 3]). */
function clampAxisScale(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 0.1;
  return Math.min(3, Math.max(0.1, value));
}

/** Keep rotation inside the contract's inclusive [-180, 180] degree bound. */
function clampRotation(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(180, Math.max(-180, value));
}

export function toCanvasRevision(folded: FoldedState): ApiCanvasRevision {
  const textEdits: ApiTextEdits = {};
  for (const layerId of EDITOR_LAYER_IDS) {
    const key = TEXT_EDIT_KEY[layerId];
    const value = folded.text[layerId];
    if (key !== undefined && value !== undefined) textEdits[key] = value;
  }

  const layerOps: ApiLayerOp[] = [];
  for (const layerId of EDITOR_LAYER_IDS) {
    const touched =
      hasOwn(folded.fill, layerId) ||
      hasOwn(folded.visible, layerId) ||
      hasOwn(folded.transform, layerId);
    if (!touched) continue;

    const transform = folded.transform[layerId] ?? IDENTITY_TRANSFORM;
    // Defensive clamp at emit time so the payload always satisfies the contract's
    // (0, 3] scale bound, regardless of any interaction edge case that could
    // accumulate an out-of-range axis scale (a resize gesture can otherwise 422 Apply).
    const sx = clampAxisScale(transform.scaleX);
    const sy = clampAxisScale(transform.scaleY);
    layerOps.push({
      layer_id: layerId,
      dx: round(transform.dx, 2),
      dy: round(transform.dy, 2),
      scale: round(sx === sy ? sx : 1, 4),
      scale_x: round(sx, 4),
      scale_y: round(sy, 4),
      rotation: round(clampRotation(transform.rotation ?? 0), 4),
      visible: folded.visible[layerId] ?? true,
      fill_role: folded.fill[layerId] ?? null,
    });
  }

  const revision: ApiCanvasRevision = { layer_ops: layerOps };
  if (Object.keys(textEdits).length > 0) revision.text_edits = textEdits;
  return revision;
}

export function orientedBoxOf(
  bbox: LayerBBox,
  transform: LayerTransform,
): OrientedLayerBox {
  const cx = bbox.x + bbox.w / 2;
  const cy = bbox.y + bbox.h / 2;
  const x = transform.dx + cx + (bbox.x - cx) * transform.scaleX;
  const y = transform.dy + cy + (bbox.y - cy) * transform.scaleY;
  const w = bbox.w * transform.scaleX;
  const h = bbox.h * transform.scaleY;
  return {
    x,
    y,
    w,
    h,
    cx: x + w / 2,
    cy: y + h / 2,
    rotation: transform.rotation ?? 0,
  };
}

export function transformedBBox(
  bbox: LayerBBox,
  transform: LayerTransform,
): LayerBBox {
  const oriented = orientedBoxOf(bbox, transform);
  if (oriented.rotation === 0) {
    return {
      x: oriented.x,
      y: oriented.y,
      w: oriented.w,
      h: oriented.h,
    };
  }
  const radians = (oriented.rotation * Math.PI) / 180;
  const cos = Math.abs(Math.cos(radians));
  const sin = Math.abs(Math.sin(radians));
  const w = oriented.w * cos + oriented.h * sin;
  const h = oriented.w * sin + oriented.h * cos;
  return {
    x: oriented.cx - w / 2,
    y: oriented.cy - h / 2,
    w,
    h,
  };
}

interface AxisSnapMatch {
  delta: number;
  guide: number;
}

function closestAxisSnap(
  anchors: readonly number[],
  guides: readonly number[],
  threshold: number,
): AxisSnapMatch | null {
  let closest: AxisSnapMatch | null = null;
  for (const guide of guides) {
    if (!Number.isFinite(guide)) continue;
    for (const anchor of anchors) {
      const delta = guide - anchor;
      if (Math.abs(delta) > threshold) continue;
      if (closest === null || Math.abs(delta) < Math.abs(closest.delta)) {
        closest = { delta, guide };
      }
    }
  }
  return closest;
}

/**
 * Snap the visual axis-aligned edges/center of a transformed layer to the
 * closest guide on each axis. Scale and rotation pass through unchanged.
 */
export function snapLayerTransform(
  bbox: LayerBBox,
  transform: LayerTransform,
  guides: AlignmentGuides,
  threshold: number,
): SnappedLayerTransform {
  const visualBox = transformedBBox(bbox, transform);
  const boundedThreshold =
    Number.isFinite(threshold) ? Math.max(0, threshold) : 0;
  const xMatch = closestAxisSnap(
    [visualBox.x, visualBox.x + visualBox.w / 2, visualBox.x + visualBox.w],
    guides.x,
    boundedThreshold,
  );
  const yMatch = closestAxisSnap(
    [visualBox.y, visualBox.y + visualBox.h / 2, visualBox.y + visualBox.h],
    guides.y,
    boundedThreshold,
  );
  return {
    transform: {
      ...transform,
      dx: transform.dx + (xMatch?.delta ?? 0),
      dy: transform.dy + (yMatch?.delta ?? 0),
    },
    lines: {
      x: xMatch?.guide ?? null,
      y: yMatch?.guide ?? null,
    },
  };
}

function isIdentity(transform: LayerTransform): boolean {
  return (
    transform.dx === 0 &&
    transform.dy === 0 &&
    transform.scaleX === 1 &&
    transform.scaleY === 1 &&
    (transform.rotation ?? 0) === 0
  );
}

export function layerTransformAttr(
  transform: LayerTransform,
  bbox: LayerBBox,
  baseTransform: string,
): string {
  if (isIdentity(transform)) return baseTransform;
  const cx = bbox.x + bbox.w / 2;
  const cy = bbox.y + bbox.h / 2;
  const rotation = transform.rotation ?? 0;
  const local =
    `translate(${transform.dx},${transform.dy}) ` +
    (rotation === 0 ? "" : `rotate(${rotation},${cx},${cy}) `) +
    `translate(${cx},${cy}) scale(${transform.scaleX},${transform.scaleY}) ` +
    `translate(${-cx},${-cy})`;
  return baseTransform === "" ? local : `${local} ${baseTransform}`;
}

function sameTransform(
  left: LayerTransform | undefined,
  right: LayerTransform | undefined,
): boolean {
  if (left === undefined || right === undefined) return left === right;
  return (
    left.dx === right.dx &&
    left.dy === right.dy &&
    left.scaleX === right.scaleX &&
    left.scaleY === right.scaleY &&
    (left.rotation ?? 0) === (right.rotation ?? 0)
  );
}

function sameRecordValue<T>(
  left: Partial<Record<CanvasLayerId, T>>,
  right: Partial<Record<CanvasLayerId, T>>,
  layerId: CanvasLayerId,
): boolean {
  const leftHas = hasOwn(left, layerId);
  const rightHas = hasOwn(right, layerId);
  if (leftHas !== rightHas) return false;
  return !leftHas || left[layerId] === right[layerId];
}

export function dirtyLayerIds(
  previous: FoldedState | null,
  next: FoldedState,
): CanvasLayerId[] {
  if (previous === null) return [...EDITOR_LAYER_IDS];
  return EDITOR_LAYER_IDS.filter((layerId) => {
    const sameTransformPresence =
      hasOwn(previous.transform, layerId) === hasOwn(next.transform, layerId);
    return (
      !sameRecordValue(previous.text, next.text, layerId) ||
      !sameRecordValue(previous.fill, next.fill, layerId) ||
      !sameRecordValue(previous.visible, next.visible, layerId) ||
      !sameTransformPresence ||
      !sameTransform(previous.transform[layerId], next.transform[layerId])
    );
  });
}

function numericAttribute(element: Element, name: string): number | null {
  const raw = element.getAttribute(name);
  if (raw === null) return null;
  const value = Number.parseFloat(raw);
  return Number.isFinite(value) ? value : null;
}

function positiveLineGap(values: readonly number[]): number | null {
  for (let index = 1; index < values.length; index += 1) {
    const previous = values[index - 1];
    const current = values[index];
    if (previous === undefined || current === undefined) continue;
    const gap = current - previous;
    if (Number.isFinite(gap) && gap > 0) return gap;
  }
  return null;
}

function textLayout(
  textElement: SVGTextElement,
  capture: BaseLayerCapture,
): BaseTextLayout {
  const view = textElement.ownerDocument.defaultView;
  const computed = view?.getComputedStyle(textElement);
  const computedFontSize = Number.parseFloat(computed?.fontSize ?? "");
  const fontSize =
    Number.isFinite(computedFontSize) && computedFontSize > 0
      ? computedFontSize
      : Math.max(capture.bbox.h, 1);
  const tspans = Array.from(textElement.querySelectorAll("tspan"));
  const firstTspan = tspans[0];
  const x =
    firstTspan?.getAttribute("x") ??
    textElement.getAttribute("x") ??
    String(capture.bbox.x);
  const tspanYs = tspans
    .map((tspan) => numericAttribute(tspan, "y"))
    .filter((value): value is number => value !== null);
  const y =
    tspanYs[0] ??
    numericAttribute(textElement, "y") ??
    capture.bbox.y + fontSize;
  const lineHeight = positiveLineGap(tspanYs) ?? fontSize * 1.2;
  const textAnchor =
    textElement.getAttribute("text-anchor") ??
    computed?.textAnchor ??
    "start";
  return { x, y, lineHeight, fontSize, textAnchor };
}

export function createEditorBaseState(
  host: HTMLElement,
  captures: readonly BaseLayerCapture[],
  brandColors: readonly ApiColorRole[],
): EditorBaseState {
  const layers: Partial<Record<CanvasLayerId, BaseLayerState>> = {};
  for (const capture of captures) {
    const node = host.querySelector<SVGGElement>(`g[data-layer="${capture.id}"]`);
    const textElement =
      node === null || TEXT_TARGET[capture.id] === null
        ? null
        : node.querySelector<SVGTextElement>("text");
    layers[capture.id] = {
      ...capture,
      textLayout:
        textElement === null || capture.baseTextHTML === null
          ? null
          : textLayout(textElement, capture),
    };
  }
  return {
    layers,
    brandColors: [...brandColors],
    lastApplied: null,
    overflow: {},
  };
}

function restoreAttribute(
  element: Element,
  name: string,
  baseValue: string | null,
): void {
  if (baseValue === null) element.removeAttribute(name);
  else element.setAttribute(name, baseValue);
}

function measureText(textElement: SVGTextElement, fallback: number): number {
  try {
    return textElement.getComputedTextLength();
  } catch {
    return fallback;
  }
}

function wrapText(
  textElement: SVGTextElement,
  value: string,
  layout: BaseTextLayout,
  maxWidth: number,
): number {
  const namespace = textElement.namespaceURI ?? "http://www.w3.org/2000/svg";
  textElement.innerHTML = "";
  const probe = textElement.ownerDocument.createElementNS(
    namespace,
    "tspan",
  ) as SVGTSpanElement;
  probe.setAttribute("x", layout.x);
  probe.setAttribute("y", String(layout.y));
  textElement.appendChild(probe);

  const lines: string[] = [];
  for (const paragraph of value.split("\n")) {
    const words = paragraph.trim() === "" ? [] : paragraph.trim().split(/\s+/);
    if (words.length === 0) {
      lines.push("");
      continue;
    }
    let line = "";
    for (const word of words) {
      const candidate = line === "" ? word : `${line} ${word}`;
      probe.textContent = candidate;
      const approximate = candidate.length * layout.fontSize * 0.55;
      if (line !== "" && measureText(probe, approximate) > maxWidth) {
        lines.push(line);
        line = word;
      } else {
        line = candidate;
      }
    }
    lines.push(line);
  }

  probe.remove();
  lines.forEach((line, index) => {
    const tspan = textElement.ownerDocument.createElementNS(
      namespace,
      "tspan",
    ) as SVGTSpanElement;
    tspan.setAttribute("x", layout.x);
    tspan.setAttribute("y", String(layout.y + index * layout.lineHeight));
    tspan.textContent = line;
    textElement.appendChild(tspan);
  });
  return layout.fontSize + Math.max(lines.length - 1, 0) * layout.lineHeight;
}

function cloneFolded(folded: FoldedState): FoldedState {
  const transform: Partial<Record<CanvasLayerId, LayerTransform>> = {};
  for (const layerId of EDITOR_LAYER_IDS) {
    const value = folded.transform[layerId];
    if (value !== undefined) transform[layerId] = { ...value };
  }
  return {
    text: { ...folded.text },
    fill: { ...folded.fill },
    visible: { ...folded.visible },
    transform,
  };
}

export function applyState(
  host: HTMLElement,
  base: EditorBaseState,
  folded: FoldedState,
): ApplyStateResult {
  const dirty = dirtyLayerIds(base.lastApplied, folded);
  for (const layerId of dirty) {
    const layerBase = base.layers[layerId];
    const node = host.querySelector<SVGGElement>(`g[data-layer="${layerId}"]`);
    if (layerBase === undefined || node === null) continue;

    const transform = folded.transform[layerId] ?? IDENTITY_TRANSFORM;
    const transformAttr = layerTransformAttr(
      transform,
      layerBase.bbox,
      layerBase.baseTransform,
    );
    restoreAttribute(node, "transform", transformAttr === "" ? null : transformAttr);

    if (folded.visible[layerId] === false) {
      node.style.display = "none";
    } else {
      restoreAttribute(node, "style", layerBase.baseStyle);
    }

    const recolorSelector = RECOLOR_TARGET[layerId];
    const recolorTarget =
      recolorSelector === null
        ? null
        : node.querySelector<SVGElement>(recolorSelector);
    if (recolorTarget !== null) {
      const role = folded.fill[layerId];
      const hex =
        role === undefined || role === null
          ? undefined
          : base.brandColors.find((color) => color.name === role)?.hex;
      if (hex === undefined) {
        restoreAttribute(recolorTarget, "fill", layerBase.baseFill);
      } else {
        recolorTarget.setAttribute("fill", hex);
      }
    }

    const textSelector = TEXT_TARGET[layerId];
    const textTarget =
      textSelector === null
        ? null
        : node.querySelector<SVGTextElement>(textSelector);
    if (
      textTarget !== null &&
      layerBase.baseTextHTML !== null &&
      layerBase.textLayout !== null
    ) {
      const value = folded.text[layerId];
      if (value === undefined) {
        textTarget.innerHTML = layerBase.baseTextHTML;
        base.overflow[layerId] = false;
      } else {
        const height = wrapText(
          textTarget,
          value,
          layerBase.textLayout,
          layerBase.bbox.w,
        );
        base.overflow[layerId] = height > layerBase.bbox.h;
      }
    }
  }

  base.lastApplied = cloneFolded(folded);
  return { dirty, overflow: { ...base.overflow } };
}
