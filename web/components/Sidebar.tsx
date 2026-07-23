"use client";

import { useMemo, useState, type JSX } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
  onCollapse?: () => void;
  /** Expands labels and stacks the contextual client list inside the mobile drawer. */
  mobile?: boolean;
}

/** Rail items that map to a real route (the rest stay un-wired placeholder buttons). */
const NAV_ROUTES: Partial<Record<NavItem["id"], string>> = {
  board: "/",
  clients: "/clients",
  calendar: "/calendar",
  creatives: "/creatives",
  "brand-briefs": "/briefs",
};

export function Sidebar({ groups, onCollapse, mobile = false }: SidebarProps): JSX.Element {
  const pathname = usePathname();
  const showSubbar = pathname.startsWith("/clients");
  const railItems = navItems.filter((item) => item.id !== "settings");
  const settings = navItems.find((item) => item.id === "settings");
  const hasClients = groups.some((group) => group.projects.length > 0);

  const [railExpanded, setRailExpanded] = useState(false);
  const railIsExpanded = mobile || railExpanded;

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
    <div className={`side${mobile ? " side--mobile" : ""}`}>
      <style>{`
        .rail-dynamic {
          position: absolute;
          top: 0;
          left: 0;
          bottom: 0;
          width: 68px;
          align-items: center;
          transition: width 0.15s cubic-bezier(0.4, 0, 0.2, 1);
          z-index: 50;
          overflow: hidden;
          background: var(--surface);
        }
        .rail-dynamic.is-expanded {
          width: 200px;
          align-items: stretch;
          padding-left: 12px;
          padding-right: 12px;
          box-shadow: 4px 0 12px rgba(0, 0, 0, 0.05);
        }
        [data-theme="dark"] .rail-dynamic.is-expanded {
          box-shadow: 4px 0 12px rgba(0, 0, 0, 0.2);
        }
        .rail-dynamic .rail__logo {
          transition: transform 0.15s ease;
        }
        .rail-dynamic.is-expanded .rail__logo {
          align-self: flex-start;
          transform: translateX(2px);
        }
        .rail-dynamic .rail-btn {
          width: 42px;
          justify-content: flex-start;
          overflow: hidden;
          transition: width 0.15s ease, background 0.15s ease, color 0.15s ease;
        }
        .rail-dynamic.is-expanded .rail-btn {
          width: 100%;
          justify-content: flex-start;
        }
        .rail-btn__icon {
          width: 42px;
          height: 42px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }
        .rail-btn__label {
          opacity: 0;
          white-space: nowrap;
          font-size: 13px;
          font-weight: 500;
          transition: opacity 0.1s ease;
        }
        .rail-dynamic.is-expanded .rail-btn__label {
          opacity: 1;
          transition: opacity 0.2s ease 0.05s;
        }
        .side--mobile {
          width: 100%;
          height: 100%;
          min-width: 0;
          flex-direction: column;
          overflow-y: auto;
        }
        .side--mobile .rail-dynamic,
        .side--mobile .rail-dynamic.is-expanded {
          position: static;
          width: 100%;
          align-items: stretch;
          padding: var(--sp-3);
          overflow: visible;
          border-right: 0;
          box-shadow: none;
          transition: none;
        }
        .side--mobile .rail-dynamic .rail__logo,
        .side--mobile .rail-dynamic.is-expanded .rail__logo {
          align-self: flex-start;
          transform: none;
          margin: 0 0 var(--sp-2);
        }
        .side--mobile .rail__nav,
        .side--mobile .rail__footer {
          width: 100%;
          align-items: stretch;
        }
        .side--mobile .rail__footer {
          margin-top: var(--sp-2);
          padding-top: var(--sp-2);
          border-top: 1px solid var(--line);
        }
        .side--mobile .rail-dynamic .rail-btn,
        .side--mobile .rail-dynamic.is-expanded .rail-btn {
          width: 100%;
          min-height: 44px;
        }
        .side--mobile .rail-dynamic .rail-btn__label {
          opacity: 1;
          transition: none;
        }
        .side--mobile .subbar {
          width: 100%;
          flex: none;
          min-width: 0;
          padding: var(--sp-4);
          border-top: 1px solid var(--line);
          border-right: 0;
        }
        .side--mobile .subbar__scroll {
          overflow-y: visible;
        }
        .side--mobile .project-row__name {
          overflow: visible;
          text-overflow: clip;
          white-space: normal;
          overflow-wrap: anywhere;
        }
      `}</style>
      <div 
        className="rail-container" 
        style={{
          width: mobile ? "100%" : 68,
          flexShrink: 0,
          position: mobile ? "static" : "relative",
          zIndex: 20,
        }}
        onMouseEnter={mobile ? undefined : () => setRailExpanded(true)}
        onMouseLeave={mobile ? undefined : () => setRailExpanded(false)}
        onFocus={mobile ? undefined : () => setRailExpanded(true)}
        onBlur={mobile ? undefined : () => setRailExpanded(false)}
      >
        <aside
          className={`rail rail-dynamic${railIsExpanded ? " is-expanded" : ""}`}
          aria-label="Primary"
        >
          <Link className="rail__logo" href="/" aria-label={workspaceName}>
            M
          </Link>

          <nav className="rail__nav" aria-label="Sections">
            {railItems.map((item) => {
              const href = NAV_ROUTES[item.id];
              const content = (
                <>
                  <span className="rail-btn__icon"><NavGlyph id={item.id} /></span>
                  <span className="rail-btn__label">{item.label}</span>
                </>
              );
              return href !== undefined ? (
                <Link
                  key={item.id}
                  className={`rail-btn${(href === "/" ? pathname === "/" : pathname.startsWith(href)) ? " rail-btn--active" : ""}`}
                  href={href}
                  aria-label={item.label}
                >
                  {content}
                </Link>
              ) : (
                <button
                  key={item.id}
                  type="button"
                  className={`rail-btn${item.active ? " rail-btn--active" : ""}`}
                  aria-current={item.active ? "page" : undefined}
                  aria-label={item.label}
                >
                  {content}
                </button>
              );
            })}
            <Link className={`rail-btn${pathname.startsWith("/tasks") ? " rail-btn--active" : ""}`} href="/tasks" aria-label="Tasks">
              <span className="rail-btn__icon"><TasksGlyph /></span>
              <span className="rail-btn__label">Tasks</span>
            </Link>
            <Link className={`rail-btn${pathname.startsWith("/deliveries") ? " rail-btn--active" : ""}`} href="/deliveries" aria-label="Deliveries">
              <span className="rail-btn__icon"><DeliveriesGlyph /></span>
              <span className="rail-btn__label">Deliveries</span>
            </Link>
            <Link className={`rail-btn${pathname.startsWith("/billing") ? " rail-btn--active" : ""}`} href="/billing" aria-label="Billing">
              <span className="rail-btn__icon"><BillingGlyph /></span>
              <span className="rail-btn__label">Billing</span>
            </Link>
          </nav>

          <div className="rail__footer">
            {settings && (
              <Link className={`rail-btn${pathname.startsWith("/members") ? " rail-btn--active" : ""}`} href="/members" aria-label="Members & roles">
                <span className="rail-btn__icon"><SettingsIcon /></span>
                <span className="rail-btn__label">Members & roles</span>
              </Link>
            )}
            <form action="/api/auth/logout" method="post" style={{ width: '100%' }}>
              <button
                type="submit"
                className="rail-btn"
                aria-label="Sign out"
              >
                <span className="rail-btn__icon"><LogOutIcon /></span>
                <span className="rail-btn__label">Sign out</span>
              </button>
            </form>
            {onCollapse && (
              <button
                type="button"
                className="rail-btn"
                onClick={onCollapse}
                aria-label="Collapse sidebar"
                style={{ marginTop: 'var(--sp-2)' }}
              >
                <span className="rail-btn__icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>
                </span>
                <span className="rail-btn__label">Collapse</span>
              </button>
            )}
          </div>
        </aside>
      </div>

      {showSubbar && (
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
      )}
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
