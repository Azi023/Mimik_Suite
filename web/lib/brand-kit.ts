/**
 * Brand Kit v2 — canvas theme derivation (spec §6/§7).
 *
 * The brand book is its own editorial surface: its chrome derives from the CLIENT's
 * tokens, not from the app's design system. This module turns a Brand into the CSS
 * custom properties the canvas root carries:
 *
 *   ink   = the brand's darkest usable colour (auto mode), or KitTheme.ink_hex (manual)
 *   paper = a fixed warm off-white family (the reference's own skin)
 *
 * Fallback when the brand has no usable dark colour: the Mimik house theme
 * (deep brick #7A2E1F + cream) — the default skin IS the house look.
 */

import type { ApiBrand, ApiColorRole, ApiFontRole } from "@/lib/api";

/** Mimik house ink — deep brick. Used when a brand has no usable dark colour. */
export const HOUSE_INK = "#7A2E1F";

/** The fixed warm paper family (constant across clients — the "desk" never rebrands). */
const PAPER = {
  paper: "#F4ECE1",
  card: "#FCF8F1",
  card2: "#F8F1E6",
  line: "#E3D6C3",
  lineSoft: "#ECE1D0",
  muted: "#96836D",
  muted2: "#B4A48D",
  ghost: "#C9BBA5",
} as const;

/** Serif voice of the book itself (headings fall back here when the brand has no heading font). */
const BOOK_SERIF =
  '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif';

const BOOK_MONO = '"SF Mono", ui-monospace, Menlo, Consolas, "Liberation Mono", monospace';

interface Rgb {
  r: number;
  g: number;
  b: number;
}

/** Parse #RGB or #RRGGBB. Returns null for anything else — never guess a colour. */
export function parseHex(value: string | null | undefined): Rgb | null {
  if (value === null || value === undefined) return null;
  const raw = value.trim().replace(/^#/, "");
  const hex =
    raw.length === 3
      ? raw
          .split("")
          .map((c) => c + c)
          .join("")
      : raw;
  if (!/^[0-9a-fA-F]{6}$/.test(hex)) return null;
  return {
    r: parseInt(hex.slice(0, 2), 16),
    g: parseInt(hex.slice(2, 4), 16),
    b: parseInt(hex.slice(4, 6), 16),
  };
}

/** WCAG relative luminance, 0 (black) → 1 (white). */
function luminance(rgb: Rgb): number {
  const channel = (v: number): number => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(rgb.r) + 0.7152 * channel(rgb.g) + 0.0722 * channel(rgb.b);
}

/** A colour is a usable book ink only when it is genuinely dark (reads as text on cream). */
const INK_LUMINANCE_CEILING = 0.22;

/** Darkest usable brand colour, or null when the palette has no real dark. */
function darkestUsable(colors: ApiColorRole[]): string | null {
  let best: { hex: string; lum: number } | null = null;
  for (const color of colors) {
    const rgb = parseHex(color.hex);
    if (rgb === null) continue;
    const lum = luminance(rgb);
    if (lum <= INK_LUMINANCE_CEILING && (best === null || lum < best.lum)) {
      best = { hex: color.hex, lum };
    }
  }
  return best?.hex ?? null;
}

/** "r, g, b" string for rgba()-style shadows tinted with the book's ink. */
function toRgbTriplet(hex: string): string {
  const rgb = parseHex(hex) ?? { r: 46, g: 22, b: 56 };
  return `${rgb.r}, ${rgb.g}, ${rgb.b}`;
}

/** The CSS custom properties written onto the brand-book canvas root. */
export interface KitCanvasVars {
  [key: `--bk-${string}`]: string;
}

/** Wrap a raw font family name into a safe CSS stack (no external hosts — system fallbacks). */
function fontStack(family: string | null | undefined, fallback: string): string {
  if (family === null || family === undefined || family.trim() === "") return fallback;
  const clean = family.trim().replace(/["']/g, "");
  return `"${clean}", ${fallback}`;
}

/**
 * Derive the book's theme from the brand's own tokens (KitTheme auto mode), honouring a
 * manual KitTheme override when present. Pure projection: data in, CSS variables out.
 */
export function deriveKitCanvasVars(brand: ApiBrand): KitCanvasVars {
  const theme = brand.kit?.theme;
  const manualInk = theme?.mode === "manual" && parseHex(theme.ink_hex) !== null ? theme.ink_hex : null;
  const manualPaper =
    theme?.mode === "manual" && parseHex(theme.paper_hex) !== null ? theme.paper_hex : null;

  const ink = manualInk ?? darkestUsable(brand.tokens.colors) ?? HOUSE_INK;

  // Accent: the role literally named "primary" when it can carry weight on paper; else the ink.
  const primary = brand.tokens.colors.find((c) => c.name.toLowerCase() === "primary");
  const primaryRgb = parseHex(primary?.hex);
  const brandAccent =
    primary !== undefined && primaryRgb !== null && luminance(primaryRgb) <= 0.6
      ? primary.hex
      : ink;

  const headingFont = fontStack(brand.tokens.typography.heading_font, BOOK_SERIF);
  const bodyFont = fontStack(
    brand.tokens.typography.body_font,
    '"Avenir Next", "Helvetica Neue", Helvetica, Arial, sans-serif',
  );

  return {
    "--bk-ink": ink,
    "--bk-ink-rgb": toRgbTriplet(ink),
    "--bk-brand": brandAccent,
    "--bk-paper": manualPaper ?? PAPER.paper,
    "--bk-card": PAPER.card,
    "--bk-card-2": PAPER.card2,
    "--bk-line": PAPER.line,
    "--bk-line-soft": PAPER.lineSoft,
    "--bk-muted": PAPER.muted,
    "--bk-muted-2": PAPER.muted2,
    "--bk-ghost": PAPER.ghost,
    "--bk-serif": BOOK_SERIF,
    "--bk-mono": BOOK_MONO,
    "--bk-font-heading": headingFont,
    "--bk-font-body": bodyFont,
  };
}

/** "clinical_plum" / "clinical-plum" / "clinical plum" → "Clinical Plum". */
export function titleCase(value: string): string {
  return value
    .split(/[\s_-]+/)
    .filter((part) => part !== "")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/** Human family name for a font role ("playfair_display" → "Playfair Display"). */
export function fontRoleFamily(role: ApiFontRole): string | null {
  if (role.source === "builtin" && role.builtin_key !== null && role.builtin_key !== "") {
    return titleCase(role.builtin_key);
  }
  return null;
}
