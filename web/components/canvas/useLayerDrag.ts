"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import type { CanvasLayerId } from "./canvas-types";

/** Per-layer local preview transform, in SVG viewBox units. */
export interface LayerTransform {
  dx: number;
  dy: number;
  scale: number;
}

/** Contract clamp — LayerOp.scale must stay in (0, 3]. */
const MIN_SCALE = 0.05;
const MAX_SCALE = 3;

interface DragSession {
  layerId: CanvasLayerId;
  mode: "move" | "scale";
  pointerId: number;
  startX: number;
  startY: number;
  /** The layer's transform when the drag began. */
  base: LayerTransform;
  /** Untransformed bbox width (viewBox units) — the scale-mode denominator. */
  bboxWidth: number;
  /** Screen-px -> viewBox-units factor captured at drag start. */
  factor: number;
  /** False for a click; flips only after the pointer crosses the drag threshold. */
  moved: boolean;
}

const MOVE_THRESHOLD_PX = 3;

export function pointerMovedPastThreshold(
  startX: number,
  startY: number,
  currentX: number,
  currentY: number,
): boolean {
  return Math.hypot(currentX - startX, currentY - startY) >= MOVE_THRESHOLD_PX;
}

export interface UseLayerDragArgs {
  /** Current screen-px -> viewBox-units factor (viewBox width / rendered width). */
  getScreenToViewBox: () => number;
  /** Canonical folded transform when a pointer session begins. */
  getTransform: (layerId: CanvasLayerId) => LayerTransform;
  /** Fired when pointerdown begins a possible drag; no op exists yet. */
  onDragStart?: (layerId: CanvasLayerId) => void;
  /** rAF-coalesced live transform for the canonical provisional history op. */
  onDragMove?: (layerId: CanvasLayerId, transform: LayerTransform) => void;
  /** Fired once per drag, on release, with the layer's settled transform. */
  onDragEnd?: (layerId: CanvasLayerId, transform: LayerTransform) => void;
}

export interface UseLayerDragResult {
  /** Layer mid-drag, or null when idle. */
  draggingLayer: CanvasLayerId | null;
  beginMove: (layerId: CanvasLayerId, event: ReactPointerEvent<Element>) => void;
  beginScale: (
    layerId: CanvasLayerId,
    event: ReactPointerEvent<Element>,
    bboxWidth: number,
  ) => void;
}

/**
 * Owns the pointer-drag / corner-scale math for the canvas stage. Screen-pixel
 * deltas are mapped back into viewBox units via `getScreenToViewBox`, and state
 * updates are rAF-coalesced so CanvasStage can update one provisional canonical
 * history op at 60fps. Nothing here owns document state or talks to the server.
 */
export function useLayerDrag(args: UseLayerDragArgs): UseLayerDragResult {
  const [draggingLayer, setDraggingLayer] = useState<CanvasLayerId | null>(null);

  // Ref mirrors the latest callbacks so window listeners never go stale.
  const argsRef = useRef(args);
  useEffect(() => {
    argsRef.current = args;
  }, [args]);

  const sessionRef = useRef<DragSession | null>(null);
  const pendingRef = useRef<LayerTransform | null>(null);
  const frameRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const flushFrame = useCallback((): void => {
    frameRef.current = null;
    const session = sessionRef.current;
    const pending = pendingRef.current;
    if (session === null || pending === null) return;
    argsRef.current.onDragMove?.(session.layerId, pending);
  }, []);

  const handlePointerMove = useCallback(
    (event: PointerEvent): void => {
      const session = sessionRef.current;
      if (session === null || event.pointerId !== session.pointerId) return;
      if (
        !session.moved &&
        !pointerMovedPastThreshold(
          session.startX,
          session.startY,
          event.clientX,
          event.clientY,
        )
      ) {
        return;
      }
      session.moved = true;
      const ddx = (event.clientX - session.startX) * session.factor;
      const ddy = (event.clientY - session.startY) * session.factor;
      if (session.mode === "move") {
        pendingRef.current = {
          ...session.base,
          dx: session.base.dx + ddx,
          dy: session.base.dy + ddy,
        };
      } else {
        // Corner handle: dragging away from the bbox center grows the layer.
        const raw = session.base.scale + (ddx + ddy) / session.bboxWidth;
        pendingRef.current = {
          ...session.base,
          scale: Math.min(MAX_SCALE, Math.max(MIN_SCALE, raw)),
        };
      }
      if (frameRef.current === null) {
        frameRef.current = window.requestAnimationFrame(flushFrame);
      }
    },
    [flushFrame],
  );

  const handlePointerEnd = useCallback((event: PointerEvent): void => {
    const session = sessionRef.current;
    if (session === null || event.pointerId !== session.pointerId) return;
    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
    const settled = pendingRef.current ?? session.base;
    if (session.moved) {
      argsRef.current.onDragMove?.(session.layerId, settled);
    }
    sessionRef.current = null;
    pendingRef.current = null;
    abortRef.current?.abort();
    abortRef.current = null;
    setDraggingLayer(null);
    if (session.moved) {
      argsRef.current.onDragEnd?.(session.layerId, settled);
    }
  }, []);

  const begin = useCallback(
    (
      layerId: CanvasLayerId,
      mode: "move" | "scale",
      event: ReactPointerEvent<Element>,
      bboxWidth: number,
    ): void => {
      if (sessionRef.current !== null) return;
      event.preventDefault();
      event.stopPropagation();
      sessionRef.current = {
        layerId,
        mode,
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        base: argsRef.current.getTransform(layerId),
        bboxWidth: Math.max(bboxWidth, 1),
        factor: argsRef.current.getScreenToViewBox(),
        moved: false,
      };
      pendingRef.current = null;
      setDraggingLayer(layerId);
      argsRef.current.onDragStart?.(layerId);
      const controller = new AbortController();
      abortRef.current = controller;
      window.addEventListener("pointermove", handlePointerMove, {
        signal: controller.signal,
      });
      window.addEventListener("pointerup", handlePointerEnd, {
        signal: controller.signal,
      });
      window.addEventListener("pointercancel", handlePointerEnd, {
        signal: controller.signal,
      });
    },
    [handlePointerMove, handlePointerEnd],
  );

  const beginMove = useCallback(
    (layerId: CanvasLayerId, event: ReactPointerEvent<Element>): void => {
      begin(layerId, "move", event, 1);
    },
    [begin],
  );

  const beginScale = useCallback(
    (
      layerId: CanvasLayerId,
      event: ReactPointerEvent<Element>,
      bboxWidth: number,
    ): void => {
      begin(layerId, "scale", event, bboxWidth);
    },
    [begin],
  );

  // Unmount: drop listeners and the queued frame.
  useEffect(() => {
    return (): void => {
      abortRef.current?.abort();
      if (frameRef.current !== null) window.cancelAnimationFrame(frameRef.current);
    };
  }, []);

  return { draggingLayer, beginMove, beginScale };
}
