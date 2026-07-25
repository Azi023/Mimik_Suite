/**
 * Brand Kit v2 — section registry (spec §7) + the two render surfaces (spec §5/§8).
 *
 * One entry per chapter, in book order. Every chapter renders as a
 * `<section data-kit-section="{key}">` block — the registry the PDF/PNG export
 * path targets. Adding a chapter = one entry here + one component in
 * `components/brand-kit/`.
 */

import type { BrandKitTabDef } from "./BrandKitTabs";

export const KIT_TABS: BrandKitTabDef[] = [
  { key: "discovery", number: "01", label: "Brand Discovery" },
  { key: "direction", number: "02", label: "Creative Direction" },
  { key: "logo_suite", number: "03", label: "Logo Suite" },
  { key: "colours_fonts", number: "04", label: "Colours & Fonts" },
  { key: "applications", number: "05", label: "Applications" },
  { key: "launch_templates", number: "06", label: "Launch Templates" },
];

/** True when `value` is a registered section key (guards `?export=png&section=…`). */
export function isKitSectionKey(value: string): boolean {
  return KIT_TABS.some((tab) => tab.key === value);
}

/**
 * The two surfaces of the one template (spec §5):
 * - `studio` — the team's view: ghost cards, full-size specimen placeholders, upload prompts.
 * - `client` — the shared read-only view: empty text rows OMITTED, empty asset slots as quiet
 *   "In production" tiles, sparse chapters collapsed to one neutral in-progress card.
 */
export type BookView = "studio" | "client";

/**
 * Export render modes the Playwright exporter drives (spec §8):
 * - `pdf` — the whole book stacked (all sections visible, no tab nav; print CSS paginates).
 * - `png` — one isolated `[data-kit-section]` block for an element screenshot.
 */
export type BookExportMode = { kind: "pdf" } | { kind: "png"; section: string };

/** A chapter is "sparse" for the client view below this many filled fields (spec §5 rule 1). */
export const CLIENT_MIN_FILLED_FIELDS = 2;
