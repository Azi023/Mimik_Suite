import type { JSX } from "react";
import { activeClient, workspaceName } from "@/lib/mock";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Top bar: workspace label (with lime brand mark), the client-switcher chip, and
 * the theme toggle. On mobile a hamburger stands in for the collapsed sidebar.
 */
export function TopBar(): JSX.Element {
  return (
    <header className="topbar">
      <button
        type="button"
        className="topbar__hamburger"
        aria-label="Open navigation menu"
      >
        <MenuIcon />
      </button>

      <div className="topbar__workspace">
        <span className="brand-mark" aria-hidden="true">
          M
        </span>
        <span>{workspaceName}</span>
      </div>

      <div className="topbar__spacer" />

      <button type="button" className="client-chip">
        <span className="client-chip__dot" aria-hidden="true" />
        <span>
          {activeClient.name} · {activeClient.vertical}
        </span>
        <span className="client-chip__caret" aria-hidden="true">
          ▾
        </span>
      </button>

      <ThemeToggle />
    </header>
  );
}

function MenuIcon(): JSX.Element {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
}
