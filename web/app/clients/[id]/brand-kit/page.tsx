import type { CSSProperties, JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { BrandKitTabs, type BrandKitTabDef } from "@/components/BrandKitTabs";
import {
  getApiBaseUrl,
  type ApiBrand,
  type ApiColorRole,
  type ApiPendingColor,
} from "@/lib/api";
import { deriveKitCanvasVars, fontRoleFamily, titleCase } from "@/lib/brand-kit";
import { getClientBrandEditData, getSidebarData } from "@/lib/data";
import { redirectClientToPortal } from "@/lib/guard";
import { getSessionToken } from "@/lib/session";
import "./brand-kit.css";

export const dynamic = "force-dynamic";

/** Whether the DEV-ONLY unauthenticated fallback may render (dev + a build-time dev token). */
function devFallbackAllowed(): boolean {
  const appEnv = process.env.APP_ENV;
  const isDev = appEnv === undefined || appEnv === "" || appEnv === "dev";
  const hasDevToken =
    process.env.NEXT_PUBLIC_DEV_TOKEN !== undefined && process.env.NEXT_PUBLIC_DEV_TOKEN !== "";
  return isDev && hasDevToken;
}

/* ---------------------------------------------------------------------------
   Section registry (spec §7) — one entry per chapter, in book order.
   This slice fully builds `colours_fonts`; the rest render calm placeholders.
--------------------------------------------------------------------------- */

const KIT_TABS: BrandKitTabDef[] = [
  { key: "discovery", number: "01", label: "Brand Discovery" },
  { key: "direction", number: "02", label: "Creative Direction" },
  { key: "logo_suite", number: "03", label: "Logo Suite" },
  { key: "colours_fonts", number: "04", label: "Colours & Fonts" },
  { key: "applications", number: "05", label: "Applications" },
  { key: "launch_templates", number: "06", label: "Launch Templates" },
];

/* ---------------------------------------------------------------------------
   Shared chapter furniture
--------------------------------------------------------------------------- */

function SectionHead({ kicker }: { kicker: string }): JSX.Element {
  return (
    <div className="bk-sec-head">
      <span className="bk-kicker">{kicker}</span>
      <span className="bk-rule" />
    </div>
  );
}

/** A chapter that hasn't been built/filled yet — typeset, calm, never broken (spec §5). */
function PlaceholderChapter({ number, label }: { number: string; label: string }): JSX.Element {
  return (
    <>
      <SectionHead kicker={`Chapter ${number} — ${label}`} />
      <div className="bk-ghost-chapter">
        <span className="bk-fleur">❦</span>
        <p>This chapter is being written</p>
        <em>arriving with your next review</em>
      </div>
    </>
  );
}

/* ---------------------------------------------------------------------------
   Chapter 04 — Colours & Fonts (fully realized, read-only)
--------------------------------------------------------------------------- */

function Swatch({ color }: { color: ApiColorRole }): JSX.Element {
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
          <p className="bk-swatch-why bk-swatch-why--ghost">
            Rationale to come — one line on why this colour is in the brand.
          </p>
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

function ColoursFontsSection({ brand }: { brand: ApiBrand }): JSX.Element {
  const colors = brand.tokens.colors;
  const pending = brand.kit?.pending_colors ?? [];
  const rows = fontSuiteRows(brand);
  const fontPackHref = `${getApiBaseUrl()}/brands/${encodeURIComponent(brand.id)}/font-pack`;
  const hasProvisional = colors.some((c) => c.confirmed === false) || pending.length > 0;

  return (
    <>
      <SectionHead kicker="Chapter 04 — Colours & Fonts" />
      <h2 className="bk-sec-title">Every colour has a name, and a reason.</h2>
      <p className="bk-sec-sub">
        Named, reasoned, and honest — provisional values carry a badge until they are confirmed
        at onboarding.
      </p>

      {colors.length === 0 && pending.length === 0 ? (
        <div className="bk-ghost" style={{ marginTop: 34 }}>
          <span className="bk-ghost-hint">
            No colours yet — the named palette arrives with the brief draft, each with a hex, a
            role, and one line on why it belongs.
          </span>
        </div>
      ) : (
        <>
          <div className="bk-pal-grid">
            {colors.map((color, index) => (
              <Swatch key={`${color.name}-${index}`} color={color} />
            ))}
            {pending.map((color, index) => (
              <PendingSwatch key={`pending-${color.name}-${index}`} color={color} />
            ))}
          </div>
          {hasProvisional && (
            <p className="bk-pal-footnote">
              ◆ Provisional = supplied approximate, awaiting client sign-off · Pending = named in
              the source material, hex confirmed at onboarding — never guessed
            </p>
          )}
        </>
      )}

      <hr className="bk-divider" />

      <h2 className="bk-sec-title">Font Suite</h2>
      <p className="bk-sec-sub">
        Chosen from the Mimik font library — nine curated families, plus any type the client
        uploads.
      </p>

      {rows.map((row, index) => (
        <FontRowView key={`${row.label}-${index}`} row={row} first={index === 0} />
      ))}

      <div className="bk-fontpack">
        <div className="bk-fontpack-ico">Aa</div>
        <div className="bk-fontpack-tx">
          <b>Download the {brand.name} font pack</b>
          <span>
            Every font role in this suite, zipped from the brand&apos;s live tokens — licences
            included.
          </span>
        </div>
        <a className="bk-btn" href={fontPackHref} download>
          Download font pack
        </a>
      </div>
    </>
  );
}

/* ---------------------------------------------------------------------------
   Masthead + page
--------------------------------------------------------------------------- */

function Masthead({ brand }: { brand: ApiBrand }): JSX.Element {
  const words = brand.name.trim().split(/\s+/);
  const lead = words.slice(0, -1).join(" ");
  const tail = words[words.length - 1];
  const dek = brand.brand_voice;
  return (
    <section className="bk-masthead">
      <span className="bk-eyebrow">Brand Book</span>
      <h1>
        {words.length > 1 ? (
          <>
            {lead} <em>{tail}</em>
          </>
        ) : (
          brand.name
        )}
      </h1>
      {dek !== null && dek !== "" && <p className="bk-dek">{dek}</p>}
      <p className="bk-edition">
        {new Date().getFullYear()} Edition · Prepared by Mimik Creations · Generated from live
        brand tokens
      </p>
    </section>
  );
}

/**
 * Brand Kit v2 — the per-client brand book (slice 1: Colours & Fonts, read-only).
 *
 * The canvas is its own editorial surface (spec §6): CSS custom properties derived from the
 * client's tokens are written on the canvas root, so the book carries the CLIENT's brand while
 * the surrounding app chrome stays untouched. Tenant scoping is enforced at the API; this page
 * only forwards the caller's own session.
 */
export default async function BrandKitPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<JSX.Element> {
  const { id } = await params;
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  const [sidebar, editData] = await Promise.all([
    getSidebarData(bearer, id),
    getClientBrandEditData(id, bearer),
  ]);

  if (editData === null) {
    return (
      <AppShell sidebar={sidebar} title="Brand kit">
        <div className="empty-state">
          <p className="empty-state__title">Client not found</p>
          <p className="empty-state__body">
            It may have been removed, or it belongs to another workspace.
          </p>
          <Link href="/" className="btn-ghost">
            Back to board
          </Link>
        </div>
      </AppShell>
    );
  }

  const { client, brand } = editData;

  if (brand === null) {
    return (
      <AppShell sidebar={sidebar} title="Brand kit" crumb={client.name}>
        <div className="empty-state">
          <p className="empty-state__title">No brand book yet</p>
          <p className="empty-state__body">
            The brand book generates from live brand tokens once onboarding drafts this
            client&apos;s brief.
          </p>
          <Link href={`/clients/${encodeURIComponent(client.id)}/edit`} className="btn-ghost">
            Open client editor
          </Link>
        </div>
      </AppShell>
    );
  }

  const canvasVars = deriveKitCanvasVars(brand) as CSSProperties;

  const panels: Record<string, JSX.Element> = {
    discovery: <PlaceholderChapter number="01" label="Brand Discovery" />,
    direction: <PlaceholderChapter number="02" label="Creative Direction" />,
    logo_suite: <PlaceholderChapter number="03" label="Logo Suite" />,
    colours_fonts: <ColoursFontsSection brand={brand} />,
    applications: <PlaceholderChapter number="05" label="Applications" />,
    launch_templates: <PlaceholderChapter number="06" label="Launch Templates" />,
  };

  return (
    <AppShell sidebar={sidebar} title="Brand kit" crumb={client.name}>
      <div className="bk-canvas" style={canvasVars}>
        <Masthead brand={brand} />
        <BrandKitTabs tabs={KIT_TABS} panels={panels} initialKey="colours_fonts" />
        <footer className="bk-colophon">
          <div className="bk-fleur">❦</div>
          Prepared by Mimik Creations · Brand Kit v2 · rendered from live brand tokens
        </footer>
      </div>
    </AppShell>
  );
}
