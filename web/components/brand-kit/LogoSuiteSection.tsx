/**
 * Chapter 03 — Logo Suite (read-only).
 *
 * Studio view: every variant row always renders — uploaded marks live, open slots as
 * full-size "not uploaded" specimen placeholders (the suite always shows its full shape).
 * Client view (spec §5): filled slots render; empty slots become quiet "In production"
 * tiles with no upload affordance; when EVERY slot is empty the chapter collapses to the
 * neutral in-progress card.
 */

import type { JSX } from "react";
import type { ApiBrand, ApiLogoVariant, ApiLogoVariantSlot } from "@/lib/api";
import { titleCase } from "@/lib/brand-kit";
import { BrandKitAssetImage } from "./BrandKitAssetImage";
import type { BookView } from "./registry";
import { filled, PlaceholderChapter, SectionHead } from "./shared";

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

function resolveSocialGrounds(
  brand: ApiBrand,
  slot: ApiLogoVariantSlot | undefined,
): SocialGround[] {
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
  view,
}: {
  brand: ApiBrand;
  slot: ApiLogoVariantSlot | undefined;
  view: BookView;
}): JSX.Element {
  const grounds = resolveSocialGrounds(brand, slot);
  const assetId = slot?.asset_id ?? null;

  if (assetId === null) {
    // Tier-2 empty state: the row keeps its full shape — reserved circles, no broken mark.
    // Client view: the same quiet shape, labelled "in production", no upload prompt.
    return (
      <div className="bk-specimen bk-specimen--ghost bk-specimen--social">
        <div className="bk-soc-circles">
          {grounds.map((ground) => (
            <div
              key={ground.role}
              className="bk-soc bk-soc--empty"
              title={`Reserved — ${titleCase(ground.role)} ground`}
            >
              {view === "studio" ? "+" : ""}
            </div>
          ))}
        </div>
        <p className="bk-ghost-spec-label">
          {view === "studio" ? "Social icons · not uploaded" : "Social icons · in production"}
        </p>
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
              {view === "studio" ? "+" : ""}
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
  view,
}: {
  def: LogoVariantDef;
  slot: ApiLogoVariantSlot | undefined;
  view: BookView;
}): JSX.Element {
  const assetId = slot?.asset_id ?? null;

  if (assetId === null) {
    // Tier-2 empty state: a FULL-SIZE labelled specimen placeholder — planned, never broken.
    // Client view: the same tile reads "in production" (no upload affordance).
    return (
      <div className="bk-specimen bk-specimen--ghost">
        <div className={def.roundFrame ? "bk-ghost-frame bk-ghost-frame--round" : "bk-ghost-frame"}>
          {def.roundFrame ? "○" : "▢"}
        </div>
        <p className="bk-ghost-spec-label">
          {def.label} · {view === "studio" ? "not uploaded" : "in production"}
        </p>
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

export function LogoSuiteSection({
  brand,
  view,
}: {
  brand: ApiBrand;
  view: BookView;
}): JSX.Element {
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

  if (view === "client") {
    // Spec §5 rule 2: if ALL slots are empty the section collapses to the in-progress card.
    const anyUploaded = LOGO_VARIANTS.some(
      (def) => (slots.get(def.variant)?.asset_id ?? null) !== null,
    );
    if (!anyUploaded) {
      return <PlaceholderChapter number="03" label="Logo Suite" />;
    }
  }

  const hasClearSpace = filled(logoSpec.clear_space);
  const hasMinSize = logoSpec.min_size_px !== null;

  return (
    <>
      <SectionHead kicker="Chapter 03 — Logo Suite" />
      <h2 className="bk-sec-title">One mark, every context.</h2>
      <p className="bk-sec-sub">
        {view === "studio"
          ? "Uploaded variants render live; open slots stay reserved so the suite always shows its full shape."
          : "The full suite of marks — variants still on the drawing board are noted as in production."}
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
              <SocialCircles brand={brand} slot={slot} view={view} />
            ) : (
              <LogoSpecimen def={def} slot={slot} view={view} />
            )}
          </div>
        );
      })}
    </>
  );
}
