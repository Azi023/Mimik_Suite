import type { JSX } from "react";
import Link from "next/link";
import type { Client } from "@/lib/view-models";
import { ThemeToggle } from "./ThemeToggle";
import { ChevronDownIcon, PlusIcon } from "./icons";

/**
 * Top bar: page title, invite control, the client-switcher
 * chip, and the theme toggle. On mobile a hamburger stands in for the
 * collapsed sidebar.
 *
 * The active client chip reflects the first client returned by the API.
 */
interface TopBarProps {
  activeClient: Client | null;
  /** Page title in the bar. Defaults to the board. */
  title?: string;
  /** Secondary crumb next to the title (omitted when not given). */
  crumb?: string;
}

export function TopBar({ activeClient, title = "Board", crumb }: TopBarProps): JSX.Element {
  return (
    <header className="topbar">
      <button
        type="button"
        className="topbar__hamburger"
        aria-label="Open navigation menu"
      >
        <MenuIcon />
      </button>

      <div className="topbar__heading">
        <span className="topbar__glyph" aria-hidden="true" />
        <h1 className="topbar__title">{title}</h1>
        {crumb !== undefined && <span className="topbar__crumb">{crumb}</span>}
      </div>

      <div className="topbar__spacer" />

      <button type="button" className="icon-btn" aria-label="Invite teammate">
        <PlusIcon />
      </button>

      {activeClient === null ? (
        <button type="button" className="client-chip" disabled>
          <span>No clients yet</span>
        </button>
      ) : (
        <Link
          href={`/clients/${encodeURIComponent(activeClient.id)}/edit`}
          className="client-chip"
          aria-label={`Edit ${activeClient.name} client and brand brief`}
        >
          <span className="client-chip__dot" aria-hidden="true" />
          <span>
            {activeClient.name} · {activeClient.vertical}
          </span>
          <span className="client-chip__caret" aria-hidden="true">
            <ChevronDownIcon size={12} />
          </span>
        </Link>
      )}

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
