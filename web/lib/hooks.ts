"use client";

/**
 * Shared client-side resilience hooks (FRONTEND_ROADMAP §2 — "no data loss on a dropped
 * connection / power-cut"). Small, dependency-free, reusable across every editor with unsaved
 * state (brief editor, brand-kit editor, creative review composer, the client portal).
 *
 *   - useLocalDraft  — mirror unsaved state to localStorage so a crash/refresh recovers it.
 *   - useUnsavedGuard — warn before the tab unloads while there is unsaved work.
 */

import { useCallback, useEffect, useRef, useState } from "react";

/** localStorage key namespace so drafts never collide with unrelated app storage. */
const DRAFT_PREFIX = "mimik.draft.";

/**
 * A piece of unsaved editor state, mirrored to `localStorage` under a stable key. Hydrates
 * from any persisted draft on mount (client-only — SSR renders `initial`, so the first paint
 * matches the server and hydration recovers the draft). Writes are debounced to avoid thrashing
 * storage on every keystroke.
 *
 * Returns the live value, a setter (same signature as `useState`), and `clear()` to drop the
 * persisted draft once the work is committed server-side.
 */
export function useLocalDraft<T>(
  key: string,
  initial: T,
): [T, (next: T | ((prev: T) => T)) => void, () => void] {
  const storageKey = `${DRAFT_PREFIX}${key}`;
  const [value, setValue] = useState<T>(initial);
  // Hydrate after mount only — reading localStorage during render breaks SSR hydration.
  const hydrated = useRef(false);

  useEffect(() => {
    if (hydrated.current) {
      return;
    }
    hydrated.current = true;
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw !== null) {
        setValue(JSON.parse(raw) as T);
      }
    } catch {
      // Corrupt or unavailable storage (private mode, quota) — fall back to `initial` silently.
    }
  }, [storageKey]);

  // Debounced persist. A 400ms window collapses a burst of edits into one write.
  useEffect(() => {
    if (!hydrated.current) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(value));
      } catch {
        // Best-effort — never let a storage failure surface to the user mid-edit.
      }
    }, 400);
    return (): void => window.clearTimeout(timer);
  }, [storageKey, value]);

  const clear = useCallback((): void => {
    try {
      window.localStorage.removeItem(storageKey);
    } catch {
      // ignore — clearing a draft is best-effort.
    }
  }, [storageKey]);

  return [value, setValue, clear];
}

/**
 * Warn before the tab closes/navigates away while `dirty` is true. The native `beforeunload`
 * prompt is the only cross-browser guarantee against losing unsaved work to an accidental
 * close; it is intentionally coarse (no custom text is honored by modern browsers).
 */
export function useUnsavedGuard(dirty: boolean): void {
  useEffect(() => {
    if (!dirty) {
      return undefined;
    }
    const handler = (event: BeforeUnloadEvent): void => {
      event.preventDefault();
      // Legacy Chrome requires a truthy returnValue to trigger the prompt.
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return (): void => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
}
