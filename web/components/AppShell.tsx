import type { JSX, ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

interface AppShellProps {
  children: ReactNode;
}

/**
 * The dashboard chrome: left sidebar + top bar + main content region.
 * On mobile the sidebar collapses (see globals.css) and the TopBar hamburger
 * stands in for it.
 */
export function AppShell({ children }: AppShellProps): JSX.Element {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <TopBar />
        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}
