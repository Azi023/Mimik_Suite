"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import type { CanvasLayerId } from "./canvas-types";
import type { LayerBBox, LayerTransform } from "./editor-state";

export type ResizeHandle =
  | "n"
  | "ne"
  | "e"
  | "se"
  | "s"
  | "sw"
  | "w"
  | "nw";

/** Contract clamp — each LayerOp scale axis stays within the editor range. */
const MIN_SCALE = 0.1;
const MAX_SCALE = 3;

interface DragSession {
  layerId: CanvasLayerId;
  mode: "move" | "resize" | "rotate";
  pointerId: number;
  startX: number;
  startY: number;
  /** The layer's transform when the drag began. */
  base: LayerTransform;
  /** Untransformed geometry used as the stable resize denominator. */
  baseBox: LayerBBox | null;
  /** Active resize direction, or null for move gestures. */
  handle: ResizeHandle | null;
  /** Screen-px -> viewBox-units factor captured at drag start. */
  factor: number;
  /** Scale/translate center used by rotate gestures. */
  centerX: number | null;
  centerY: number | null;
  /** Pointer angle in radians when a rotate gesture begins. */
  startAngle: number | null;
  /** Element retaining pointer capture for the duration of the gesture. */
  captureTarget: Element;
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

function clampScale(value: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, value));
}

function normalizeRotation(value: number): number {
  const normalized = ((value + 180) % 360 + 360) % 360 - 180;
  return normalized === -180 && value > 0 ? 180 : normalized;
}

export function resizeLayerTransform(
  baseBox: LayerBBox,
  startTransform: LayerTransform,
  handle: ResizeHandle,
  deltaX: number,
  deltaY: number,
): LayerTransform {
  const width = baseBox.w > 0 ? baseBox.w : 1;
  const height = baseBox.h > 0 ? baseBox.h : 1;
  let { dx, dy, scaleX, scaleY } = startTransform;

  if (handle.includes("e")) {
    scaleX = clampScale(startTransform.scaleX + deltaX / width);
    dx =
      startTransform.dx +
      ((scaleX - startTransform.scaleX) * width) / 2;
  } else if (handle.includes("w")) {
    scaleX = clampScale(startTransform.scaleX - deltaX / width);
    dx =
      startTransform.dx -
      ((scaleX - startTransform.scaleX) * width) / 2;
  }

  if (handle.includes("s")) {
    scaleY = clampScale(startTransform.scaleY + deltaY / height);
    dy =
      startTransform.dy +
      ((scaleY - startTransform.scaleY) * height) / 2;
  } else if (handle.includes("n")) {
    scaleY = clampScale(startTransform.scaleY - deltaY / height);
    dy =
      startTransform.dy -
      ((scaleY - startTransform.scaleY) * height) / 2;
  }

  return { ...startTransform, dx, dy, scaleX, scaleY };
}

export function rotateLayerTransform(
  startTransform: LayerTransform,
  startAngle: number,
  centerX: number,
  centerY: number,
  pointerX: number,
  pointerY: number,
  snapToFifteenDegrees: boolean,
): LayerTransform {
  const newAngle = Math.atan2(pointerY - centerY, pointerX - centerX);
  const deltaDegrees = ((newAngle - startAngle) * 180) / Math.PI;
  const unsnapped = (startTransform.rotation ?? 0) + deltaDegrees;
  const rotation = snapToFifteenDegrees
    ? Math.round(unsnapped / 15) * 15
    : unsnapped;
  return {
    ...startTransform,
    rotation: normalizeRotation(rotation),
  };
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
  beginResize: (
    layerId: CanvasLayerId,
    handle: ResizeHandle,
    event: ReactPointerEvent<Element>,
    baseBox: LayerBBox,
    startTransform: LayerTransform,
  ) => void;
  beginRotate: (
    layerId: CanvasLayerId,
    event: ReactPointerEvent<Element>,
    baseBox: LayerBBox,
    startTransform: LayerTransform,
  ) => void;
}

interface ViewBoxPoint {
  x: number;
  y: number;
}

function screenPointToViewBox(
  clientX: number,
  clientY: number,
  factor: number,
  target: Element,
): ViewBoxPoint {
  const svg = target.closest("svg");
  if (!(svg instanceof SVGSVGElement)) {
    return { x: clientX * factor, y: clientY * factor };
  }
  const rect = svg.getBoundingClientRect();
  return {
    x: svg.viewBox.baseVal.x + (clientX - rect.left) * factor,
    y: svg.viewBox.baseVal.y + (clientY - rect.top) * factor,
  };
}

/**
 * Owns the pointer move, eight-handle resize, and rotation math for the canvas
 * stage. Screen-pixel deltas are mapped back into viewBox units via
 * `getScreenToViewBox`, and state updates are rAF-coalesced so CanvasStage can
 * update one provisional canonical history op at 60fps. Nothing here owns
 * document state or talks to the server.
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
      } else if (
        session.mode === "resize" &&
        session.baseBox !== null &&
        session.handle !== null
      ) {
        pendingRef.current = resizeLayerTransform(
          session.baseBox,
          session.base,
          session.handle,
          ddx,
          ddy,
        );
      } else if (
        session.mode === "rotate" &&
        session.centerX !== null &&
        session.centerY !== null &&
        session.startAngle !== null
      ) {
        const point = screenPointToViewBox(
          event.clientX,
          event.clientY,
          session.factor,
          session.captureTarget,
        );
        pendingRef.current = rotateLayerTransform(
          session.base,
          session.startAngle,
          session.centerX,
          session.centerY,
          point.x,
          point.y,
          event.shiftKey,
        );
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
    let settled = pendingRef.current ?? session.base;
    if (
      session.mode === "rotate" &&
      session.moved &&
      event.type === "pointerup" &&
      session.centerX !== null &&
      session.centerY !== null &&
      session.startAngle !== null
    ) {
      const point = screenPointToViewBox(
        event.clientX,
        event.clientY,
        session.factor,
        session.captureTarget,
      );
      settled = rotateLayerTransform(
        session.base,
        session.startAngle,
        session.centerX,
        session.centerY,
        point.x,
        point.y,
        event.shiftKey,
      );
    }
    if (session.moved) {
      argsRef.current.onDragMove?.(session.layerId, settled);
    }
    try {
      if (session.captureTarget.hasPointerCapture(session.pointerId)) {
        session.captureTarget.releasePointerCapture(session.pointerId);
      }
    } catch {
      // The element may have detached while the gesture was active.
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
      mode: "move" | "resize" | "rotate",
      event: ReactPointerEvent<Element>,
      base: LayerTransform,
      baseBox: LayerBBox | null,
      handle: ResizeHandle | null,
    ): void => {
      if (sessionRef.current !== null) return;
      event.preventDefault();
      event.stopPropagation();
      event.currentTarget.setPointerCapture(event.pointerId);
      const factor = argsRef.current.getScreenToViewBox();
      const centerX =
        mode === "rotate" && baseBox !== null
          ? baseBox.x + baseBox.w / 2 + base.dx
          : null;
      const centerY =
        mode === "rotate" && baseBox !== null
          ? baseBox.y + baseBox.h / 2 + base.dy
          : null;
      const startPoint =
        centerX === null || centerY === null
          ? null
          : screenPointToViewBox(
              event.clientX,
              event.clientY,
              factor,
              event.currentTarget,
            );
      sessionRef.current = {
        layerId,
        mode,
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        base,
        baseBox,
        handle,
        factor,
        centerX,
        centerY,
        startAngle:
          startPoint === null || centerX === null || centerY === null
            ? null
            : Math.atan2(startPoint.y - centerY, startPoint.x - centerX),
        captureTarget: event.currentTarget,
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
      begin(
        layerId,
        "move",
        event,
        argsRef.current.getTransform(layerId),
        null,
        null,
      );
    },
    [begin],
  );

  const beginResize = useCallback(
    (
      layerId: CanvasLayerId,
      handle: ResizeHandle,
      event: ReactPointerEvent<Element>,
      baseBox: LayerBBox,
      startTransform: LayerTransform,
    ): void => {
      begin(layerId, "resize", event, startTransform, baseBox, handle);
    },
    [begin],
  );

  const beginRotate = useCallback(
    (
      layerId: CanvasLayerId,
      event: ReactPointerEvent<Element>,
      baseBox: LayerBBox,
      startTransform: LayerTransform,
    ): void => {
      begin(layerId, "rotate", event, startTransform, baseBox, null);
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

  return { draggingLayer, beginMove, beginResize, beginRotate };
}
