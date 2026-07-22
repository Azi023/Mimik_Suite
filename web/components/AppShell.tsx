"use client";

import { useCallback, useState, type JSX, type ReactNode } from "react";
import type { SidebarData } from "@/lib/data";
import { MobileNavDrawer } from "./MobileNavDrawer";
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
 * opens the off-canvas MobileNavDrawer, which reuses the same Sidebar content.
 */
export function AppShell({ children, sidebar, title, crumb }: AppShellProps): JSX.Element {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const openMobileNav = useCallback((): void => setMobileNavOpen(true), []);
  const closeMobileNav = useCallback((): void => setMobileNavOpen(false), []);

  return (
    <div className="app-shell">
      <Sidebar groups={sidebar.groups} />
      <MobileNavDrawer groups={sidebar.groups} open={mobileNavOpen} onClose={closeMobileNav} />
      <div className="app-main">
        <TopBar
          activeClient={sidebar.activeClient}
          title={title}
          crumb={crumb}
          navOpen={mobileNavOpen}
          onOpenNav={openMobileNav}
        />
        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}
