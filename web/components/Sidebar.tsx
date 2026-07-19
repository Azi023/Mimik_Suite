import type { JSX } from "react";
import Link from "next/link";
import { navItems, workspaceName, type NavItem, type SidebarGroup } from "@/lib/mock";
import {
  CalendarIcon,
  ChevronDownIcon,
  FileIcon,
  GridIcon,
  ImageIcon,
  PlusIcon,
  SearchIcon,
  SettingsIcon,
  ShapeIcon,
  UsersIcon,
} from "./icons";

/**
 * Two-tier left navigation, per the reference:
 *  1. a slim icon rail (logo bubble, section glyphs, settings pinned bottom)
 *  2. a secondary sidebar (search, "Favorites" / "All clients" groups with
 *     colored geometric markers; the active client gets a soft card highlight
 *     and a count badge).
 * Hidden on mobile (the TopBar renders a hamburger there).
 *
 * The client groups are threaded in from the server component (live API when
 * configured + reachable, mock set otherwise — see `lib/data.getSidebarData`).
 */
interface SidebarProps {
  groups: SidebarGroup[];
}

export function Sidebar({ groups }: SidebarProps): JSX.Element {
  const railItems = navItems.filter((item) => item.id !== "settings");
  const settings = navItems.find((item) => item.id === "settings");

  return (
    <div className="side">
      <aside className="rail" aria-label="Primary">
        <Link className="rail__logo" href="/" aria-label={workspaceName}>
          M
        </Link>

        <nav className="rail__nav" aria-label="Sections">
          {railItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`rail-btn${item.active ? " rail-btn--active" : ""}`}
              aria-current={item.active ? "page" : undefined}
              aria-label={item.label}
              title={item.label}
            >
              <NavGlyph id={item.id} />
              {item.badge !== undefined && item.badge > 0 && (
                <span className="rail-btn__badge">{item.badge}</span>
              )}
            </button>
          ))}
        </nav>

        {settings && (
          <button
            type="button"
            className="rail-btn rail__settings"
            aria-label={settings.label}
            title={settings.label}
          >
            <SettingsIcon />
          </button>
        )}
      </aside>

      <aside className="subbar" aria-label="Clients">
        <div className="subbar__search">
          <SearchIcon />
          <input
            type="search"
            placeholder="Search…"
            aria-label="Search clients and jobs"
          />
        </div>

        <div className="subbar__scroll">
          {groups.map((group) => (
            <section key={group.id} className="subbar-group">
              <h2 className="subbar-group__label">
                <ChevronDownIcon size={12} />
                {group.label}
              </h2>
              <ul className="subbar-group__list">
                {group.projects.map((project) => (
                  <li key={`${group.id}-${project.id}`}>
                    <button
                      type="button"
                      className={`project-row${project.active ? " project-row--active" : ""}`}
                      aria-current={project.active ? "true" : undefined}
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
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        <button type="button" className="subbar__new">
          <PlusIcon size={14} />
          New client
        </button>
      </aside>
    </div>
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
