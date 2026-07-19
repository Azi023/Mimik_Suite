import type { JSX } from "react";
import { team, type Client } from "@/lib/mock";
import { ThemeToggle } from "./ThemeToggle";
import { ChevronDownIcon, PlusIcon } from "./icons";

/** How many team avatars render before collapsing into a "+n" chip. */
const MAX_AVATARS = 4;

/**
 * Top bar: page title, team avatar stack with add button, the client-switcher
 * chip, and the theme toggle. On mobile a hamburger stands in for the
 * collapsed sidebar.
 *
 * The active client chip reflects the first real client threaded in from the
 * server component (live API when configured + reachable, mock set otherwise).
 */
interface TopBarProps {
  activeClient: Client;
}

export function TopBar({ activeClient }: TopBarProps): JSX.Element {
  const visible = team.slice(0, MAX_AVATARS);
  const overflow = team.length - visible.length;

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
        <h1 className="topbar__title">Board</h1>
        <span className="topbar__crumb">This week · approvals</span>
      </div>

      <div className="topbar__spacer" />

      <div className="avatar-stack" aria-label={`Team: ${team.map((m) => m.name).join(", ")}`}>
        {visible.map((member) => (
          <span
            key={member.id}
            className={`avatar avatar--${member.tone}`}
            title={member.name}
          >
            {member.initials}
          </span>
        ))}
        {overflow > 0 && <span className="avatar avatar--more">+{overflow}</span>}
      </div>

      <button type="button" className="icon-btn" aria-label="Invite teammate">
        <PlusIcon />
      </button>

      <button type="button" className="client-chip">
        <span className="client-chip__dot" aria-hidden="true" />
        <span>
          {activeClient.name} · {activeClient.vertical}
        </span>
        <span className="client-chip__caret" aria-hidden="true">
          <ChevronDownIcon size={12} />
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
