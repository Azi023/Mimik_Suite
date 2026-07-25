import type { CSSProperties, JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { BrandKitTabs, type BrandKitTabDef } from "@/components/BrandKitTabs";
import { BrandKitAssetImage } from "@/components/BrandKitAssetImage";
import {
  getApiBaseUrl,
  type ApiBrand,
  type ApiColorRole,
  type ApiLogoVariant,
  type ApiLogoVariantSlot,
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
   Built read-only: discovery, direction, logo_suite, colours_fonts.
   Applications + launch templates still render calm placeholders.
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

/** True when a nullable wire string actually carries text. */
function filled(value: string | null | undefined): value is string {
  return value !== null && value !== undefined && value.trim() !== "";
}

/** Tier-1 empty state (spec §5) — a dashed ghost card with a muted, typeset prompt. */
function GhostCard({ hint }: { hint: string }): JSX.Element {
  return (
    <div className="bk-ghost">
      <span className="bk-ghost-hint">{hint}</span>
    </div>
  );
}

/* ---------------------------------------------------------------------------
   Chapter 01 — Brand Discovery (read-only)
--------------------------------------------------------------------------- */

/** One entry of the two-column discovery list — real prose, chips, or a tier-1 ghost. */
interface DiscoveryEntry {
  label: string;
  content: JSX.Element | null;
  ghostHint: string;
}

function discoveryEntries(brand: ApiBrand): DiscoveryEntry[] {
  const discovery = brand.kit?.discovery;

  const prose = (value: string | null | undefined): JSX.Element | null =>
    filled(value) ? <p>{value}</p> : null;

  const valueChips =
    discovery !== undefined && discovery.values.length > 0 ? (
      <div className="bk-chips">
        {discovery.values.map((value, index) => (
          <span key={`${value}-${index}`} className="bk-chip">
            {value}
          </span>
        ))}
      </div>
    ) : null;

  // Tone of voice: the long-form discovery field, falling back to the brand's own
  // voice line + tone keywords (spec §3.4 — reused, not duplicated).
  let toneContent: JSX.Element | null = null;
  const toneOfVoice = discovery?.tone_of_voice;
  if (filled(toneOfVoice)) {
    toneContent = <p>{toneOfVoice}</p>;
  } else if (filled(brand.brand_voice)) {
    toneContent = (
      <>
        <p>{brand.brand_voice}</p>
        {brand.tone_keywords.length > 0 && (
          <div className="bk-chips">
            {brand.tone_keywords.map((keyword, index) => (
              <span key={`${keyword}-${index}`} className="bk-chip">
                {keyword}
              </span>
            ))}
          </div>
        )}
      </>
    );
  }

  return [
    {
      label: "Purpose",
      content: prose(discovery?.purpose),
      ghostHint: `The purpose arrives with discovery — one sentence on why ${brand.name} exists.`,
    },
    {
      label: "Mission",
      content: prose(discovery?.mission),
      ghostHint: `The mission arrives with discovery — what ${brand.name} does every day to serve that purpose.`,
    },
    {
      label: "Vision",
      content: prose(discovery?.vision),
      ghostHint: "The vision arrives with discovery — where this brand is headed if everything works.",
    },
    {
      label: "Personality",
      content: prose(discovery?.personality),
      ghostHint: "The personality arrives with discovery — who this brand is when it speaks.",
    },
    {
      label: "Brand Values",
      content: valueChips,
      ghostHint: "Brand values arrive with discovery — three to five words the work must honour.",
    },
    {
      label: "Tone of Voice",
      content: toneContent,
      ghostHint: "The tone of voice arrives with the brief draft — how every caption and panel should sound.",
    },
    {
      label: "Key USP",
      content: prose(discovery?.key_usp),
      ghostHint: `The key USP arrives with discovery — the one thing only ${brand.name} can claim.`,
    },
    {
      label: "Visual Competitor Analysis",
      content: prose(discovery?.visual_competitor_analysis),
      ghostHint: "A short read on 2–3 competitor feeds — what they do visually, and what we deliberately won't.",
    },
    {
      label: "Existing Brand Review",
      content: prose(discovery?.existing_brand_review),
      ghostHint: "An honest review of the brand as it stands today — what stays, what the refresh retires.",
    },
    {
      label: "Target Audience",
      content: prose(brand.target_audience),
      ghostHint: "The target audience arrives with the brief draft — who this work must reach, precisely.",
    },
  ];
}

function DiscoverySection({
  brand,
  clientName,
}: {
  brand: ApiBrand;
  clientName: string;
}): JSX.Element {
  const timeline = brand.kit?.discovery.timeline;
  const entries = discoveryEntries(brand);

  return (
    <>
      <SectionHead kicker="Chapter 01 — Discovery" />
      <h2 className="bk-sec-title">Who {brand.name} is, before a single pixel.</h2>
      <p className="bk-sec-sub">
        The strategic foundation every creative decision in this book traces back to.
      </p>

      <div className="bk-meta-strip">
        <div className="bk-meta-cell">
          <div className="bk-meta-k">Client</div>
          <div className="bk-meta-v">{clientName}</div>
        </div>
        <div className="bk-meta-cell">
          <div className="bk-meta-k">Industry</div>
          {filled(brand.niche) ? (
            <div className="bk-meta-v">{brand.niche}</div>
          ) : (
            <div className="bk-meta-v bk-meta-v--ghost">to be confirmed at onboarding</div>
          )}
        </div>
        <div className="bk-meta-cell">
          <div className="bk-meta-k">Timeline</div>
          {filled(timeline) ? (
            <div className="bk-meta-v">{timeline}</div>
          ) : (
            <div className="bk-meta-v bk-meta-v--ghost">engagement window to come</div>
          )}
        </div>
      </div>

      <div className="bk-disc-grid">
        {entries.map((entry) => (
          <div key={entry.label} className="bk-disc-item">
            <div className="bk-disc-k">{entry.label}</div>
            {entry.content ?? <GhostCard hint={entry.ghostHint} />}
          </div>
        ))}
      </div>
    </>
  );
}

/* ---------------------------------------------------------------------------
   Chapter 02 — Creative Direction (read-only)
--------------------------------------------------------------------------- */

/** The moodboard always shows its full shape — assets first, reserved tiles after (spec §5 tier 2). */
const MOODBOARD_MIN_TILES = 6;

function Moodboard({ assetIds }: { assetIds: string[] }): JSX.Element {
  const ghostCount = Math.max(0, MOODBOARD_MIN_TILES - assetIds.length);
  return (
    <div className="bk-mood-grid">
      {assetIds.map((assetId, index) => (
        <figure
          key={assetId}
          className={index === 0 ? "bk-mood bk-mood--tall" : "bk-mood"}
        >
          <BrandKitAssetImage
            assetId={assetId}
            alt={`Moodboard reference ${index + 1}`}
            fit="cover"
            fallbackLabel="reference unavailable"
          />
          <figcaption className="bk-mood-cap">
            Reference {String(index + 1).padStart(2, "0")}
          </figcaption>
        </figure>
      ))}
      {Array.from({ length: ghostCount }, (_, index) => (
        <div
          key={`mood-ghost-${index}`}
          className={
            assetIds.length === 0 && index === 0 ? "bk-mood-ghost bk-mood--tall" : "bk-mood-ghost"
          }
        >
          <span className="bk-mood-ghost-ico">+</span>
          <span>Moodboard image · in curation</span>
        </div>
      ))}
    </div>
  );
}

/** One prose block of the direction spread — filled paragraph or a tier-1 ghost. */
function ProseBlock({
  label,
  text,
  ghostHint,
}: {
  label: string;
  text: string | null | undefined;
  ghostHint: string;
}): JSX.Element {
  return (
    <div className="bk-prose-block">
      <div className="bk-prose-k">{label}</div>
      {filled(text) ? <p>{text}</p> : <GhostCard hint={ghostHint} />}
    </div>
  );
}

function DirectionSection({ brand }: { brand: ApiBrand }): JSX.Element {
  const direction = brand.kit?.direction;
  const assetIds = direction?.moodboard_asset_ids ?? [];

  return (
    <>
      <SectionHead kicker="Chapter 02 — Creative Direction" />
      <h2 className="bk-sec-title">The mood every frame answers to.</h2>
      <p className="bk-sec-sub">
        Vetted references from the brand&apos;s asset library, and the reasoning that turns a
        palette into a point of view.
      </p>

      <Moodboard assetIds={assetIds} />

      <div className="bk-prose-grid">
        <ProseBlock
          label="Colour Palette:"
          text={direction?.palette_rationale}
          ghostHint="The palette rationale arrives with creative direction — why each colour earns its place in the system."
        />
        <ProseBlock
          label="Visual Tone:"
          text={direction?.visual_tone}
          ghostHint="The visual tone arrives with creative direction — photography, light, and what a busy layout would betray."
        />
        <ProseBlock
          label="How it aligns with the Personality:"
          text={direction?.personality_alignment}
          ghostHint="How the look performs the personality — written once the direction locks."
        />
        <ProseBlock
          label="Uniqueness vs Competitors:"
          text={direction?.competitor_differentiation}
          ghostHint="What the category default looks like, and the corner this brand owns instead."
        />
      </div>
    </>
  );
}

/* ---------------------------------------------------------------------------
   Chapter 03 — Logo Suite (read-only)
--------------------------------------------------------------------------- */

/** The suite's fixed shape — every variant row always renders (spec §5 tier 2). */
interface LogoVariantDef {
  variant: ApiLogoVariant;
  label: string;
  /** Template copy describing the slot's purpose; a slot's own `notes` overrides it. */
  defaultNote: string;
  roundFrame: boolean;
}

const LOGO_VARIANTS: LogoVariantDef[] = [
  {
    variant: "primary",
    label: "Primary Logo",
    defaultNote: "The brand's signature mark — the anchor of every creative.",
    roundFrame: false,
  },
  {
    variant: "stacked",
    label: "Stacked Logo",
    defaultNote: "For square placements and profile tiles.",
    roundFrame: false,
  },
  {
    variant: "wordmark",
    label: "Wordmark",
    defaultNote: "Full name, set in the brand's heading face, for headers and documents.",
    roundFrame: false,
  },
  {
    variant: "icon",
    label: "Icon",
    defaultNote: "The reduced mark for favicons and app touchpoints.",
    roundFrame: true,
  },
  {
    variant: "social_icon",
    label: "Social Icons",
    defaultNote: "The mark proven on every brand ground before it ships.",
    roundFrame: true,
  },
];

/** Grounds the social icons demo on when a slot names none (spec fallback: primary / ink). */
const DEFAULT_SOCIAL_ROLES = ["primary", "ink"];

/** One coloured circle ground for the social-icon row; hex null ⇒ reserved (role has no hex yet). */
interface SocialGround {
  role: string;
  hex: string | null;
}

function resolveSocialGrounds(brand: ApiBrand, slot: ApiLogoVariantSlot | undefined): SocialGround[] {
  const roles = slot !== undefined && slot.bg_roles.length > 0 ? slot.bg_roles : DEFAULT_SOCIAL_ROLES;
  return roles.map((role): SocialGround => {
    const match = brand.tokens.colors.find(
      (color) => color.name.toLowerCase() === role.toLowerCase(),
    );
    return { role, hex: match?.hex ?? null };
  });
}

function SocialCircles({
  brand,
  slot,
}: {
  brand: ApiBrand;
  slot: ApiLogoVariantSlot | undefined;
}): JSX.Element {
  const grounds = resolveSocialGrounds(brand, slot);
  const assetId = slot?.asset_id ?? null;

  if (assetId === null) {
    // Tier-2 empty state: the row keeps its full shape — reserved circles, no broken mark.
    return (
      <div className="bk-specimen bk-specimen--ghost bk-specimen--social">
        <div className="bk-soc-circles">
          {grounds.map((ground) => (
            <div
              key={ground.role}
              className="bk-soc bk-soc--empty"
              title={`Reserved — ${titleCase(ground.role)} ground`}
            >
              +
            </div>
          ))}
        </div>
        <p className="bk-ghost-spec-label">Social icons · not uploaded</p>
      </div>
    );
  }

  return (
    <div className="bk-specimen bk-specimen--social">
      <div className="bk-soc-circles">
        {grounds.map((ground) =>
          ground.hex !== null ? (
            <div
              key={ground.role}
              className="bk-soc"
              style={{ background: ground.hex }}
              title={`On ${titleCase(ground.role)}`}
            >
              <span className="bk-soc-art">
                <BrandKitAssetImage
                  assetId={assetId}
                  alt={`Social icon on ${titleCase(ground.role)}`}
                  fit="contain"
                  fallbackLabel="—"
                />
              </span>
            </div>
          ) : (
            <div
              key={ground.role}
              className="bk-soc bk-soc--empty"
              title={`Reserved — ${titleCase(ground.role)} ground, hex pending`}
            >
              +
            </div>
          ),
        )}
      </div>
    </div>
  );
}

function LogoSpecimen({
  def,
  slot,
}: {
  def: LogoVariantDef;
  slot: ApiLogoVariantSlot | undefined;
}): JSX.Element {
  const assetId = slot?.asset_id ?? null;

  if (assetId === null) {
    // Tier-2 empty state: a FULL-SIZE labelled specimen placeholder — planned, never broken.
    return (
      <div className="bk-specimen bk-specimen--ghost">
        <div className={def.roundFrame ? "bk-ghost-frame bk-ghost-frame--round" : "bk-ghost-frame"}>
          {def.roundFrame ? "○" : "▢"}
        </div>
        <p className="bk-ghost-spec-label">{def.label} · not uploaded</p>
      </div>
    );
  }

  return (
    <div className="bk-specimen">
      <span className="bk-corner bk-corner--1" />
      <span className="bk-corner bk-corner--2" />
      <span className="bk-corner bk-corner--3" />
      <span className="bk-corner bk-corner--4" />
      <div className="bk-specimen-art">
        <BrandKitAssetImage
          assetId={assetId}
          alt={def.label}
          fit="contain"
          fallbackLabel="logo unavailable"
        />
      </div>
    </div>
  );
}

function LogoSuiteSection({ brand }: { brand: ApiBrand }): JSX.Element {
  const suite = brand.tokens.logo_suite ?? [];
  const logoSpec = brand.tokens.logo;

  // Back-compat (spec §3.2): an empty suite treats tokens.logo as the PRIMARY variant.
  const slots = new Map<ApiLogoVariant, ApiLogoVariantSlot>();
  for (const slot of suite) {
    slots.set(slot.variant, slot);
  }
  if (suite.length === 0 && filled(logoSpec.ref)) {
    slots.set("primary", {
      variant: "primary",
      asset_id: logoSpec.ref,
      bg_roles: [],
      notes: logoSpec.assessment,
    });
  }

  const hasClearSpace = filled(logoSpec.clear_space);
  const hasMinSize = logoSpec.min_size_px !== null;

  return (
    <>
      <SectionHead kicker="Chapter 03 — Logo Suite" />
      <h2 className="bk-sec-title">One mark, every context.</h2>
      <p className="bk-sec-sub">
        Uploaded variants render live; open slots stay reserved so the suite always shows its
        full shape.
      </p>

      {LOGO_VARIANTS.map((def, index) => {
        const slot = slots.get(def.variant);
        const slotNotes = slot?.notes;
        const note = filled(slotNotes) ? slotNotes : def.defaultNote;
        return (
          <div
            key={def.variant}
            className={index === 0 ? "bk-logo-row bk-logo-row--first" : "bk-logo-row"}
          >
            <div className="bk-logo-meta">
              <div className="bk-logo-k">{def.label}</div>
              <p className="bk-logo-note">{note}</p>
              {def.variant === "primary" && (hasMinSize || hasClearSpace) && (
                <div className="bk-logo-spec">
                  {hasMinSize && (
                    <>
                      Min size · {logoSpec.min_size_px}px wide
                      <br />
                    </>
                  )}
                  {hasClearSpace && <>Clear space · {logoSpec.clear_space}</>}
                </div>
              )}
            </div>
            {def.variant === "social_icon" ? (
              <SocialCircles brand={brand} slot={slot} />
            ) : (
              <LogoSpecimen def={def} slot={slot} />
            )}
          </div>
        );
      })}
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
 * Brand Kit v2 — the per-client brand book (chapters 01–04 read-only; 05–06 placeholders).
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
    discovery: <DiscoverySection brand={brand} clientName={client.name} />,
    direction: <DirectionSection brand={brand} />,
    logo_suite: <LogoSuiteSection brand={brand} />,
    colours_fonts: <ColoursFontsSection brand={brand} />,
    applications: <PlaceholderChapter number="05" label="Applications" />,
    launch_templates: <PlaceholderChapter number="06" label="Launch Templates" />,
  };

  return (
    <AppShell sidebar={sidebar} title="Brand kit" crumb={client.name}>
      <div className="bk-canvas" style={canvasVars}>
        <Masthead brand={brand} />
        {/* The book now opens on chapter 01 (the reference's reading order) — slices 1–4 built. */}
        <BrandKitTabs tabs={KIT_TABS} panels={panels} initialKey="discovery" />
        <footer className="bk-colophon">
          <div className="bk-fleur">❦</div>
          Prepared by Mimik Creations · Brand Kit v2 · rendered from live brand tokens
        </footer>
      </div>
    </AppShell>
  );
}
