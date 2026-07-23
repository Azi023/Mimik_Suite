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
  scale: number;
}

export interface LayerBBox {
  x: number;
  y: number;
  w: number;
  h: number;
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

export const IDENTITY_TRANSFORM: LayerTransform = { dx: 0, dy: 0, scale: 1 };

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
    layerOps.push({
      layer_id: layerId,
      dx: round(transform.dx, 2),
      dy: round(transform.dy, 2),
      scale: round(transform.scale, 4),
      visible: folded.visible[layerId] ?? true,
      fill_role: folded.fill[layerId] ?? null,
    });
  }

  const revision: ApiCanvasRevision = { layer_ops: layerOps };
  if (Object.keys(textEdits).length > 0) revision.text_edits = textEdits;
  return revision;
}

export function transformedBBox(bbox: LayerBBox, transform: LayerTransform): LayerBBox {
  const cx = bbox.x + bbox.w / 2;
  const cy = bbox.y + bbox.h / 2;
  return {
    x: transform.dx + cx + (bbox.x - cx) * transform.scale,
    y: transform.dy + cy + (bbox.y - cy) * transform.scale,
    w: bbox.w * transform.scale,
    h: bbox.h * transform.scale,
  };
}

function isIdentity(transform: LayerTransform): boolean {
  return transform.dx === 0 && transform.dy === 0 && transform.scale === 1;
}

export function layerTransformAttr(
  transform: LayerTransform,
  bbox: LayerBBox,
  baseTransform: string,
): string {
  if (isIdentity(transform)) return baseTransform;
  const cx = bbox.x + bbox.w / 2;
  const cy = bbox.y + bbox.h / 2;
  const local =
    `translate(${transform.dx},${transform.dy}) ` +
    `translate(${cx},${cy}) scale(${transform.scale}) translate(${-cx},${-cy})`;
  return baseTransform === "" ? local : `${local} ${baseTransform}`;
}

function sameTransform(
  left: LayerTransform | undefined,
  right: LayerTransform | undefined,
): boolean {
  if (left === undefined || right === undefined) return left === right;
  return left.dx === right.dx && left.dy === right.dy && left.scale === right.scale;
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
