"use client";

import { useCallback, useState, useEffect, type JSX, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import type { SidebarData } from "@/lib/data";
import { MobileNavDrawer } from "./MobileNavDrawer";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { ChevronRightIcon } from "./icons";

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
  const pathname = usePathname();
  // Only the canvas editor + the review/approve surface collapse app chrome —
  // NOT /clients/[id]/edit (the brand form) or /brands/[id]/kit, which want the client list.
  const isEditor =
    (pathname.startsWith("/creatives/") && pathname.endsWith("/edit")) ||
    (pathname.startsWith("/jobs/") && pathname.endsWith("/review"));

  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const openMobileNav = useCallback((): void => setMobileNavOpen(true), []);
  const closeMobileNav = useCallback((): void => setMobileNavOpen(false), []);

  const [chromeCollapsed, setChromeCollapsed] = useState(isEditor);

  // Auto-collapse when entering editor routes.
  useEffect(() => {
    if (isEditor) {
      setChromeCollapsed(true);
    } else {
      setChromeCollapsed(false);
    }
  }, [isEditor]);

  const toggleChrome = useCallback(() => setChromeCollapsed(c => !c), []);

  return (
    <div className="app-shell">
      {!chromeCollapsed ? (
        <Sidebar groups={sidebar.groups} onCollapse={isEditor ? toggleChrome : undefined} />
      ) : (
        <div className="collapsed-rail" style={{ 
          width: 48, 
          background: 'var(--surface)', 
          borderRight: '1px solid var(--line)', 
          display: 'flex', 
          flexDirection: 'column', 
          alignItems: 'center', 
          paddingTop: 16,
          flexShrink: 0
        }}>
          <button 
            type="button" 
            onClick={toggleChrome} 
            aria-label="Expand sidebar" 
            className="icon-btn"
            style={{ width: 32, minWidth: 32, height: 32, minHeight: 32, borderRadius: 8 }}
          >
            <ChevronRightIcon />
          </button>
        </div>
      )}
      <MobileNavDrawer groups={sidebar.groups} open={mobileNavOpen} onClose={closeMobileNav} />
      <div className="app-main">
        <TopBar
          activeClient={sidebar.activeClient}
          clients={sidebar.groups.flatMap(g => g.projects)}
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
