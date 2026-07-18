import type { JSX } from "react";
import { navItems, workspaceName } from "@/lib/mock";

/**
 * Left navigation rail. Hidden on mobile (the TopBar renders a hamburger there).
 * The active item carries `aria-current="page"` and shows the lime marker dot.
 */
export function Sidebar(): JSX.Element {
  return (
    <aside className="sidebar" aria-label="Primary">
      <div className="sidebar__brand">
        <span className="brand-mark" aria-hidden="true">
          M
        </span>
        <span>{workspaceName}</span>
      </div>

      <nav className="sidebar__nav" aria-label="Sections">
        {navItems.map((item) => (
          <button
            key={item.id}
            type="button"
            className="nav-item"
            aria-current={item.active ? "page" : undefined}
          >
            <span className="nav-item__dot" aria-hidden="true" />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}
