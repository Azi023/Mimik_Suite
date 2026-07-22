"use client";

import { useCallback, useEffect, useRef, type JSX, type MouseEvent } from "react";
import type { SidebarGroup } from "@/lib/view-models";
import { Sidebar } from "./Sidebar";

/**
 * Off-canvas mobile navigation drawer (≤860px only; desktop hides it via CSS).
 * Reuses the desktop <Sidebar> wholesale so the mobile nav is pixel-identical:
 * same rail, client switcher, and logout. Slides in from the left over a scrim.
 *
 * Closes on scrim click, Escape, or any link tap inside the panel. Focus moves
 * to the panel on open and returns to the opener (the topbar hamburger) on close.
 */
interface MobileNavDrawerProps {
  groups: SidebarGroup[];
  open: boolean;
  onClose: () => void;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function MobileNavDrawer({ groups, open, onClose }: MobileNavDrawerProps): JSX.Element {
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  // On open: remember the opener and move focus into the dialog.
  // On close (effect cleanup): hand focus back to the opener.
  useEffect(() => {
    if (!open) return;
    restoreFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panelRef.current?.focus();
    return () => {
      restoreFocusRef.current?.focus();
      restoreFocusRef.current = null;
    };
  }, [open]);

  // Escape closes; Tab wraps within the panel (minimal focus trap).
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent): void => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const panel = panelRef.current;
      if (panel === null) return;
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (first === undefined || last === undefined) return;
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === panel)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  // Any link tap inside the drawer means navigation — close over it.
  // (The logout submit button posts a full navigation, so it needs no close.)
  const handlePanelClick = useCallback(
    (event: MouseEvent<HTMLDivElement>): void => {
      const target = event.target instanceof Element ? event.target : null;
      if (target !== null && target.closest("a") !== null) {
        onClose();
      }
    },
    [onClose],
  );

  return (
    <div id="mobile-nav" className={`mobile-nav${open ? " mobile-nav--open" : ""}`}>
      <div className="mobile-nav__scrim" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        className="mobile-nav__panel"
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        tabIndex={-1}
        onClick={handlePanelClick}
      >
        <Sidebar groups={groups} />
      </div>
    </div>
  );
}
