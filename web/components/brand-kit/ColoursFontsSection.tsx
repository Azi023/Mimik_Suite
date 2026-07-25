/**
 * Chapter 04 — Colours & Fonts (read-only).
 *
 * Studio view: full shape — palette (or a ghost prompt), every font role row (ghost rows
 * for unchosen faces), and the font-pack download.
 * Client view (spec §5): empty rows/blocks are OMITTED (no ghost rationale lines, no ghost
 * font rows, no font-pack — it needs a studio session); a sparse chapter collapses to the
 * neutral in-progress card. Provisional/pending badges stay in BOTH views (§4 — honesty
 * beats polish).
 */

import type { CSSProperties, JSX } from "react";
import type { ApiBrand, ApiColorRole, ApiPendingColor } from "@/lib/api";
import { getApiBaseUrl } from "@/lib/api";
import { fontRoleFamily, titleCase } from "@/lib/brand-kit";
import type { BookView } from "./registry";
import { CLIENT_MIN_FILLED_FIELDS } from "./registry";
import { PlaceholderChapter, SectionHead } from "./shared";

function Swatch({ color, view }: { color: ApiColorRole; view: BookView }): JSX.Element {
  const displayName =
    color.display_name !== null && color.display_name !== undefined && color.display_name !== ""
      ? color.display_name
      : titleCase(color.name);
  const hasRationale =
    color.rationale !== null && color.rationale !== undefined && color.rationale !== "";
  return (
    <div className="bk-swatch">
      <div className="bk-chip-lg" style={{ background: color.hex }}>
        {color.confirmed === false && <span className="bk-badge">provisional</span>}
      </div>
      <div className="bk-swatch-info">
        <div className="bk-swatch-nm">{displayName}</div>
        <div className="bk-swatch-hex">
          {color.hex.toUpperCase()} <span className="bk-swatch-role">{color.name}</span>
        </div>
        {hasRationale ? (
          <p className="bk-swatch-why">{color.rationale}</p>
        ) : (
          view === "studio" && (
            <p className="bk-swatch-why bk-swatch-why--ghost">
              Rationale to come — one line on why this colour is in the brand.
            </p>
          )
        )}
      </div>
    </div>
  );
}

/** A named colour whose hex was never supplied — striped placeholder, never guessed (spec §4). */
function PendingSwatch({ color }: { color: ApiPendingColor }): JSX.Element {
  const displayName =
    color.display_name !== null && color.display_name !== undefined && color.display_name !== ""
      ? color.display_name
      : titleCase(color.name);
  return (
    <div className="bk-swatch">
      <div className="bk-chip-lg bk-chip-lg--pending">
        <span className="bk-chip-pending-label">Hex pending</span>
      </div>
      <div className="bk-swatch-info">
        <div className="bk-swatch-nm">{displayName}</div>
        <div className="bk-swatch-hex">
          — <span className="bk-swatch-role">{color.name}</span>
        </div>
        <p className="bk-swatch-why bk-swatch-why--ghost">
          hex pending — confirmed at onboarding
          {color.rationale !== null && color.rationale !== undefined && color.rationale !== ""
            ? ` · ${color.rationale}`
            : ""}
        </p>
      </div>
    </div>
  );
}

/** One rendered row of the font suite — either a real specimen or a ghost slot. */
interface FontSuiteRow {
  label: string;
  sourceNote: string;
  /** CSS family for the specimen; null ⇒ book serif (family unavailable in-browser). */
  family: string | null;
  sample: string;
  weights: string[];
  ghost: boolean;
  ghostHint: string;
}

const WEIGHT_NAMES: Record<string, string> = {
  "300": "300 Light",
  "400": "400 Regular",
  "500": "500 Medium",
  "600": "600 Semibold",
  "700": "700 Bold",
  "800": "800 Extrabold",
};

const ROLE_SAMPLES: Record<string, string> = {
  display: "A brand book worth keeping.",
  heading: "Modern brands move with purpose.",
  subheading: "Every chapter earns its place.",
  body: "Warm, confident, and easy to read — the voice of every panel and caption.",
  accent: "The single note of difference.",
  arabic: "بسم الله الرحمن الرحيم",
};

const GLYPH_LINE = "AaBbCcDdEe 0123456789 &?!";

/** Project the brand's typography into font-suite rows (font_roles first, flat view fallback). */
function fontSuiteRows(brand: ApiBrand): FontSuiteRow[] {
  const roles = brand.tokens.typography.font_roles ?? [];
  if (roles.length > 0) {
    return roles.map((role): FontSuiteRow => {
      const family = fontRoleFamily(role);
      const sample =
        role.sample_text !== null && role.sample_text !== ""
          ? role.sample_text
          : (ROLE_SAMPLES[role.role] ?? ROLE_SAMPLES.heading);
      return {
        label: titleCase(role.role),
        sourceNote:
          role.source === "builtin"
            ? `${family ?? "Built-in"} — Mimik library`
            : "Uploaded typeface — client's own",
        family,
        sample,
        weights: role.weights,
        ghost: false,
        ghostHint: "",
      };
    });
  }

  // Flat view fallback — the engine's heading_font / body_font pair.
  const typography = brand.tokens.typography;
  const rows: FontSuiteRow[] = [];
  const flat: { label: string; font: string | null; roleKey: "heading" | "body" }[] = [
    { label: "Heading", font: typography.heading_font, roleKey: "heading" },
    { label: "Body", font: typography.body_font, roleKey: "body" },
  ];
  for (const item of flat) {
    if (item.font !== null && item.font !== "") {
      rows.push({
        label: item.label,
        sourceNote: `${item.font} — brand tokens`,
        family: item.font,
        sample: ROLE_SAMPLES[item.roleKey],
        weights: ["400", "700"],
        ghost: false,
        ghostHint: "",
      });
    } else {
      rows.push({
        label: item.label,
        sourceNote: "",
        family: null,
        sample: "",
        weights: [],
        ghost: true,
        ghostHint: `No ${item.label.toLowerCase()} face chosen yet — it arrives with the brief draft, from the Mimik library or the client's own type.`,
      });
    }
  }
  return rows;
}

function FontRowView({ row, first }: { row: FontSuiteRow; first: boolean }): JSX.Element {
  const rowClass = first ? "bk-font-row bk-font-row--first" : "bk-font-row";
  if (row.ghost) {
    return (
      <div className={rowClass}>
        <div>
          <div className="bk-rolelab-k">{row.label}</div>
        </div>
        <div className="bk-ghost bk-font-ghost">
          <span className="bk-ghost-hint">{row.ghostHint}</span>
        </div>
      </div>
    );
  }
  const specimenStyle: CSSProperties =
    row.family !== null ? { fontFamily: `"${row.family}", var(--bk-serif)` } : {};
  return (
    <div className={rowClass}>
      <div>
        <div className="bk-rolelab-k">{row.label}</div>
        <div className="bk-rolelab-src">{row.sourceNote}</div>
      </div>
      <div className="bk-font-sample">
        <div className="bk-font-sample-big" style={specimenStyle}>
          {row.sample}
        </div>
        <div className="bk-font-sample-glyphs" style={specimenStyle}>
          {GLYPH_LINE}
        </div>
      </div>
      <div className="bk-font-wts">
        {row.weights.length > 0
          ? row.weights.map((w) => <div key={w}>{WEIGHT_NAMES[w] ?? w}</div>)
          : "—"}
      </div>
    </div>
  );
}

export function ColoursFontsSection({
  brand,
  view,
}: {
  brand: ApiBrand;
  view: BookView;
}): JSX.Element {
  const colors = brand.tokens.colors;
  const pending = brand.kit?.pending_colors ?? [];
  const allRows = fontSuiteRows(brand);
  const rows = view === "client" ? allRows.filter((row) => !row.ghost) : allRows;
  const fontPackHref = `${getApiBaseUrl()}/brands/${encodeURIComponent(brand.id)}/font-pack`;
  const hasProvisional = colors.some((c) => c.confirmed === false) || pending.length > 0;
  const hasPalette = colors.length > 0 || pending.length > 0;

  if (view === "client") {
    const filledCount = colors.length + pending.length + rows.length;
    if (filledCount < CLIENT_MIN_FILLED_FIELDS) {
      return <PlaceholderChapter number="04" label="Colours & Fonts" />;
    }
  }

  const showPaletteBlock = hasPalette || view === "studio";
  const showFontBlock = rows.length > 0 || view === "studio";

  return (
    <>
      <SectionHead kicker="Chapter 04 — Colours & Fonts" />

      {showPaletteBlock && (
        <>
          <h2 className="bk-sec-title">Every colour has a name, and a reason.</h2>
          <p className="bk-sec-sub">
            Named, reasoned, and honest — provisional values carry a badge until they are
            confirmed at onboarding.
          </p>

          {!hasPalette ? (
            <div className="bk-ghost" style={{ marginTop: 34 }}>
              <span className="bk-ghost-hint">
                No colours yet — the named palette arrives with the brief draft, each with a hex,
                a role, and one line on why it belongs.
              </span>
            </div>
          ) : (
            <>
              <div className="bk-pal-grid">
                {colors.map((color, index) => (
                  <Swatch key={`${color.name}-${index}`} color={color} view={view} />
                ))}
                {pending.map((color, index) => (
                  <PendingSwatch key={`pending-${color.name}-${index}`} color={color} />
                ))}
              </div>
              {hasProvisional && (
                <p className="bk-pal-footnote">
                  ◆ Provisional = supplied approximate, awaiting client sign-off · Pending = named
                  in the source material, hex confirmed at onboarding — never guessed
                </p>
              )}
            </>
          )}
        </>
      )}

      {showPaletteBlock && showFontBlock && <hr className="bk-divider" />}

      {showFontBlock && (
        <>
          <h2 className="bk-sec-title">Font Suite</h2>
          <p className="bk-sec-sub">
            Chosen from the Mimik font library — nine curated families, plus any type the client
            uploads.
          </p>

          {rows.map((row, index) => (
            <FontRowView key={`${row.label}-${index}`} row={row} first={index === 0} />
          ))}

          {view === "studio" && (
            <div className="bk-fontpack">
              <div className="bk-fontpack-ico">Aa</div>
              <div className="bk-fontpack-tx">
                <b>Download the {brand.name} font pack</b>
                <span>
                  Every font role in this suite, zipped from the brand&apos;s live tokens —
                  licences included.
                </span>
              </div>
              <a className="bk-btn" href={fontPackHref} download>
                Download font pack
              </a>
            </div>
          )}
        </>
      )}
    </>
  );
}
