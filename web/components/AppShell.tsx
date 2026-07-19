import type { JSX, ReactNode } from "react";
import type { SidebarData } from "@/lib/data";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

interface AppShellProps {
  children: ReactNode;
  /** Sidebar client groups + active-client chip (live API or mock — see lib/data). */
  sidebar: SidebarData;
}

/**
 * The dashboard chrome: left sidebar + top bar + main content region.
 * On mobile the sidebar collapses (see globals.css) and the TopBar hamburger
 * stands in for it.
 */
export function AppShell({ children, sidebar }: AppShellProps): JSX.Element {
  return (
    <div className="app-shell">
      <Sidebar groups={sidebar.groups} />
      <div className="app-main">
        <TopBar activeClient={sidebar.activeClient} />
        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}
