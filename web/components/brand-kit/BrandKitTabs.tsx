"use client";

import { useState, type JSX, type KeyboardEvent, type ReactNode } from "react";

/** One chapter in the brand book's folder-tab nav (section-registry order). */
export interface BrandKitTabDef {
  /** Section-registry key — becomes `data-kit-section` on the panel. */
  key: string;
  /** "01"…"06" — the mono chapter number on the tab. */
  number: string;
  label: string;
}

interface BrandKitTabsProps {
  tabs: BrandKitTabDef[];
  /** Server-rendered chapter content, keyed by section-registry key. */
  panels: Record<string, ReactNode>;
  /** Which chapter opens first. Defaults to the first tab. */
  initialKey?: string;
}

/**
 * Folder tabs + stacked-paper sheet for the brand book. Panels are server-rendered and
 * stay mounted (hidden, not unmounted) so every `[data-kit-section]` block remains in the
 * DOM — the section registry the PDF/PNG export path targets (spec §7/§8).
 */
export function BrandKitTabs({ tabs, panels, initialKey }: BrandKitTabsProps): JSX.Element {
  const fallbackKey = tabs[0]?.key ?? "";
  const [active, setActive] = useState<string>(
    initialKey !== undefined && tabs.some((t) => t.key === initialKey) ? initialKey : fallbackKey,
  );

  function onTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number): void {
    let next: BrandKitTabDef | undefined;
    if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
    if (event.key === "ArrowLeft") next = tabs[(index - 1 + tabs.length) % tabs.length];
    if (next !== undefined) {
      event.preventDefault();
      setActive(next.key);
      const el = document.getElementById(`bk-tab-${next.key}`);
      if (el !== null) el.focus();
    }
  }

  return (
    <div className="bk-bookwrap">
      <nav className="bk-tabs" role="tablist" aria-label="Brand book chapters">
        {tabs.map((tab, index) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            id={`bk-tab-${tab.key}`}
            className="bk-tab"
            aria-selected={tab.key === active}
            aria-controls={`bk-panel-${tab.key}`}
            onClick={(): void => setActive(tab.key)}
            onKeyDown={(event): void => onTabKeyDown(event, index)}
          >
            <span className="bk-tab-n">{tab.number}</span>
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="bk-sheet">
        {tabs.map((tab) => (
          <section
            key={tab.key}
            id={`bk-panel-${tab.key}`}
            data-kit-section={tab.key}
            role="tabpanel"
            aria-labelledby={`bk-tab-${tab.key}`}
            className={tab.key === active ? "bk-panel bk-panel--active" : "bk-panel"}
            hidden={tab.key !== active}
          >
            {panels[tab.key]}
          </section>
        ))}
      </main>
    </div>
  );
}
