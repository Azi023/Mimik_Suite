import type { JSX, ReactNode } from "react";
import type { SidebarData } from "@/lib/data";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

interface AppShellProps {
  children: ReactNode;
  /** API-backed sidebar client groups + active-client chip. */
  sidebar: SidebarData;
  /** Top-bar page title (defaults to the board). */
  title?: string;
  /** Optional secondary crumb next to the title. */
  crumb?: string;
}

/**
 * The dashboard chrome: left sidebar + top bar + main content region.
 * On mobile the sidebar collapses (see globals.css) and the TopBar hamburger
 * stands in for it.
 */
export function AppShell({ children, sidebar, title, crumb }: AppShellProps): JSX.Element {
  return (
    <div className="app-shell">
      <Sidebar groups={sidebar.groups} />
      <div className="app-main">
        <TopBar activeClient={sidebar.activeClient} title={title} crumb={crumb} />
        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}
