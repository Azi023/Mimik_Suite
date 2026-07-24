"use client";

import { useCallback, useEffect, useRef, type JSX, type MouseEvent } from "react";
import type { SidebarGroup } from "@/lib/view-models";
import type { TenantBranding } from "@/lib/branding";
import { Sidebar } from "./Sidebar";

/**
 * Off-canvas mobile navigation drawer (≤860px only; desktop hides it via CSS).
 * Reuses the desktop <Sidebar> routes in an expanded mobile layout. The client
 * list remains contextual to /clients, matching the desktop navigation.
 *
 * Closes on scrim click, Escape, or any link tap inside the panel. Focus moves
 * to the close control on open and returns to the opener on close.
 */
interface MobileNavDrawerProps {
  groups: SidebarGroup[];
  /** Current tenant's white-label branding, threaded to the reused <Sidebar>. */
  branding: TenantBranding;
  open: boolean;
  onClose: () => void;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function MobileNavDrawer({ groups, branding, open, onClose }: MobileNavDrawerProps): JSX.Element {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  // On open: remember the opener, prevent background scrolling, and focus Close.
  // On close (effect cleanup): restore both document state and opener focus.
  useEffect(() => {
    if (!open) return;
    restoreFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();
    return () => {
      document.body.style.overflow = previousBodyOverflow;
      if (restoreFocusRef.current?.isConnected === true) {
        restoreFocusRef.current.focus();
      }
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
      <style>{`
        @media (max-width: 860px) {
          .mobile-nav__panel {
            width: min(80vw, 300px);
            flex-direction: column;
            overflow: hidden;
          }
          .mobile-nav__head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: var(--sp-3);
            min-height: 60px;
            padding: var(--sp-2) var(--sp-3) var(--sp-2) var(--sp-4);
            border-bottom: 1px solid var(--line);
            background: var(--surface);
            flex-shrink: 0;
          }
          .mobile-nav__title {
            font-size: 15px;
            font-weight: 700;
            color: var(--ink);
          }
          .mobile-nav__close {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: var(--sp-2);
            min-height: 44px;
            padding: 0 var(--sp-3);
            border: 1px solid var(--line);
            border-radius: var(--r-sm);
            background: var(--surface);
            color: var(--ink-2);
            font-size: 13px;
            font-weight: 600;
          }
          .mobile-nav__close:hover {
            background: var(--surface-2);
            color: var(--ink);
          }
          .mobile-nav__close:focus-visible {
            outline: 2px solid var(--accent);
            outline-offset: 2px;
          }
          .mobile-nav__panel > .side--mobile {
            height: auto;
            flex: 1;
            min-height: 0;
          }
        }
      `}</style>
      <div className="mobile-nav__scrim" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        className="mobile-nav__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mobile-nav-title"
        tabIndex={-1}
        onClick={handlePanelClick}
      >
        <div className="mobile-nav__head">
          <h2 id="mobile-nav-title" className="mobile-nav__title">
            Navigation
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            className="mobile-nav__close"
            onClick={onClose}
            aria-label="Close navigation menu"
          >
            <CloseIcon />
            Close
          </button>
        </div>
        <Sidebar groups={groups} branding={branding} mobile />
      </div>
    </div>
  );
}

function CloseIcon(): JSX.Element {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}
