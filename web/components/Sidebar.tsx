"use client";

import { useMemo, useState, type JSX } from "react";
import Link from "next/link";
import { navItems, workspaceName, type NavItem, type SidebarGroup } from "@/lib/view-models";
import {
  CalendarIcon,
  ChevronDownIcon,
  FileIcon,
  GridIcon,
  ImageIcon,
  LogOutIcon,
  PlusIcon,
  SearchIcon,
  SettingsIcon,
  ShapeIcon,
  UsersIcon,
} from "./icons";

/**
 * Two-tier left navigation, per the reference:
 *  1. a slim icon rail (logo bubble, section glyphs, settings pinned bottom)
 *  2. a secondary sidebar (search filters the client rows; API-backed client rows
 *     with colored geometric markers; the active client gets a soft card highlight
 *     and a count badge).
 * Hidden on mobile (the TopBar hamburger opens MobileNavDrawer, which reuses
 * this component inside an off-canvas panel).
 *
 * Client groups are threaded in from the server component's API-backed data facade.
 */
interface SidebarProps {
  groups: SidebarGroup[];
}

/** Rail items that map to a real route (the rest stay un-wired placeholder buttons). */
const NAV_ROUTES: Partial<Record<NavItem["id"], string>> = {
  board: "/",
  calendar: "/calendar",
  "brand-briefs": "/briefs",
};

export function Sidebar({ groups }: SidebarProps): JSX.Element {
  const railItems = navItems.filter((item) => item.id !== "settings");
  const settings = navItems.find((item) => item.id === "settings");
  const hasClients = groups.some((group) => group.projects.length > 0);

  // Search filters the client rows below it; empty groups drop out entirely.
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const visibleGroups = useMemo(() => {
    if (normalizedQuery === "") return groups;
    return groups
      .map((group) => ({
        ...group,
        projects: group.projects.filter((project) =>
          project.name.toLowerCase().includes(normalizedQuery),
        ),
      }))
      .filter((group) => group.projects.length > 0);
  }, [groups, normalizedQuery]);

  return (
    <div className="side">
      <aside className="rail" aria-label="Primary">
        <Link className="rail__logo" href="/" aria-label={workspaceName}>
          M
        </Link>

        <nav className="rail__nav" aria-label="Sections">
          {railItems.map((item) => {
            // Items with a real route render as Links; the rest are not wired yet (plain buttons).
            const href = NAV_ROUTES[item.id];
            return href !== undefined ? (
              <Link
                key={item.id}
                className="rail-btn"
                href={href}
                aria-label={item.label}
                title={item.label}
              >
                <NavGlyph id={item.id} />
              </Link>
            ) : (
              <button
                key={item.id}
                type="button"
                className={`rail-btn${item.active ? " rail-btn--active" : ""}`}
                aria-current={item.active ? "page" : undefined}
                aria-label={item.label}
                title={item.label}
              >
                <NavGlyph id={item.id} />
              </button>
            );
          })}
          <Link className="rail-btn" href="/tasks" aria-label="Tasks" title="Tasks">
            <TasksGlyph />
          </Link>
          <Link className="rail-btn" href="/deliveries" aria-label="Deliveries" title="Deliveries">
            <DeliveriesGlyph />
          </Link>
          <Link className="rail-btn" href="/billing" aria-label="Billing" title="Billing">
            <BillingGlyph />
          </Link>
        </nav>

        <div className="rail__footer">
          {settings && (
            <Link className="rail-btn" href="/members" aria-label="Members & roles" title="Members & roles">
              <SettingsIcon />
            </Link>
          )}
          {/* Logout is a POST so a prefetch/link can't sign the user out. */}
          <form action="/api/auth/logout" method="post">
            <button
              type="submit"
              className="rail-btn"
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOutIcon />
            </button>
          </form>
        </div>
      </aside>

      <aside className="subbar" aria-label="Clients">
        <div className="subbar__search">
          <SearchIcon />
          <input
            type="search"
            placeholder="Search clients…"
            aria-label="Filter clients"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>

        <div className="subbar__scroll">
          {hasClients && visibleGroups.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state__title">No matches</p>
              <p className="empty-state__body">No clients match “{query.trim()}”.</p>
            </div>
          ) : hasClients ? (
            visibleGroups.map((group) => (
              <section key={group.id} className="subbar-group">
                <h2 className="subbar-group__label">
                  <ChevronDownIcon size={12} />
                  {group.label}
                </h2>
                <ul className="subbar-group__list">
                  {group.projects.map((project) => (
                    <li key={`${group.id}-${project.id}`}>
                      <Link
                        href={`/clients/${encodeURIComponent(project.id)}/edit`}
                        className={`project-row${project.active ? " project-row--active" : ""}`}
                        aria-current={project.active ? "true" : undefined}
                        aria-label={`Edit ${project.name}`}
                      >
                        <span
                          className={`project-row__shape shape--${project.tone}`}
                          aria-hidden="true"
                        >
                          <ShapeIcon shape={project.shape} />
                        </span>
                        <span className="project-row__name">{project.name}</span>
                        {project.count > 0 && (
                          <span
                            className="project-row__count"
                            aria-label={`${project.count} open jobs`}
                          >
                            {project.count}
                          </span>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            ))
          ) : (
            <div className="empty-state">
              <p className="empty-state__title">No clients yet</p>
              <p className="empty-state__body">Add a client to start building their workspace.</p>
            </div>
          )}
        </div>

        <Link href="/onboarding" className="subbar__new">
          <PlusIcon size={14} />
          New client
        </Link>
      </aside>
    </div>
  );
}

/** A small checklist glyph for the Tasks rail entry (no matching icon in ./icons). */
function TasksGlyph(): JSX.Element {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M9 6h11M9 12h11M9 18h11" strokeLinecap="round" />
      <path d="M4 6l1 1 1.5-2M4 12l1 1 1.5-2M4 18l1 1 1.5-2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** A truck/box glyph for the Deliveries rail entry (no matching icon in ./icons). */
function DeliveriesGlyph(): JSX.Element {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M3 7l9-4 9 4-9 4-9-4z" strokeLinejoin="round" />
      <path d="M3 7v10l9 4 9-4V7M12 11v10" strokeLinejoin="round" />
    </svg>
  );
}

/** A card glyph for the Billing rail entry (no matching icon in ./icons). */
function BillingGlyph(): JSX.Element {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect x="2" y="5" width="20" height="14" rx="2" />
      <path d="M2 10h20" strokeLinecap="round" />
    </svg>
  );
}

/** Maps a nav item id to its rail glyph. */
function NavGlyph({ id }: { id: NavItem["id"] }): JSX.Element {
  switch (id) {
    case "clients":
      return <UsersIcon />;
    case "calendar":
      return <CalendarIcon />;
    case "creatives":
      return <ImageIcon />;
    case "brand-briefs":
      return <FileIcon />;
    case "board":
    default:
      return <GridIcon />;
  }
}
