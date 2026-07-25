/**
 * Chapter 02 — Creative Direction (read-only).
 *
 * Studio view: the moodboard always shows its full shape (curation ghosts) and every prose
 * block renders — filled or as a tier-1 ghost card.
 * Client view (spec §5): empty prose rows are OMITTED; open moodboard slots become quiet
 * "In production" tiles with no upload affordance; a sparse chapter collapses to the
 * neutral in-progress card.
 */

import type { JSX } from "react";
import type { ApiBrand } from "@/lib/api";
import { BrandKitAssetImage } from "./BrandKitAssetImage";
import type { BookView } from "./registry";
import { CLIENT_MIN_FILLED_FIELDS } from "./registry";
import { filled, GhostCard, PlaceholderChapter, SectionHead } from "./shared";

/** The moodboard always shows its full shape — assets first, reserved tiles after (spec §5 tier 2). */
const MOODBOARD_MIN_TILES = 6;

function Moodboard({ assetIds, view }: { assetIds: string[]; view: BookView }): JSX.Element {
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
            removable={view === "studio"}
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
          {view === "studio" && <span className="bk-mood-ghost-ico">+</span>}
          <span>{view === "studio" ? "Moodboard image · in curation" : "In production"}</span>
        </div>
      ))}
    </div>
  );
}

/** One prose block of the direction spread — filled paragraph or a tier-1 ghost (studio only). */
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

interface ProseDef {
  label: string;
  text: string | null | undefined;
  ghostHint: string;
}

export function DirectionSection({
  brand,
  view,
}: {
  brand: ApiBrand;
  view: BookView;
}): JSX.Element {
  const direction = brand.kit?.direction;
  const assetIds = direction?.moodboard_asset_ids ?? [];

  const proseDefs: ProseDef[] = [
    {
      label: "Colour Palette:",
      text: direction?.palette_rationale,
      ghostHint:
        "The palette rationale arrives with creative direction — why each colour earns its place in the system.",
    },
    {
      label: "Visual Tone:",
      text: direction?.visual_tone,
      ghostHint:
        "The visual tone arrives with creative direction — photography, light, and what a busy layout would betray.",
    },
    {
      label: "How it aligns with the Personality:",
      text: direction?.personality_alignment,
      ghostHint: "How the look performs the personality — written once the direction locks.",
    },
    {
      label: "Uniqueness vs Competitors:",
      text: direction?.competitor_differentiation,
      ghostHint: "What the category default looks like, and the corner this brand owns instead.",
    },
  ];

  const filledProse = proseDefs.filter((def) => filled(def.text));

  if (view === "client") {
    const filledCount = assetIds.length + filledProse.length;
    if (filledCount < CLIENT_MIN_FILLED_FIELDS) {
      return <PlaceholderChapter number="02" label="Creative Direction" />;
    }
  }

  const proseRows = view === "client" ? filledProse : proseDefs;

  return (
    <>
      <SectionHead kicker="Chapter 02 — Creative Direction" />
      <h2 className="bk-sec-title">The mood every frame answers to.</h2>
      <p className="bk-sec-sub">
        Vetted references from the brand&apos;s asset library, and the reasoning that turns a
        palette into a point of view.
      </p>

      <Moodboard assetIds={assetIds} view={view} />

      {proseRows.length > 0 && (
        <div className="bk-prose-grid">
          {proseRows.map((def) => (
            <ProseBlock key={def.label} label={def.label} text={def.text} ghostHint={def.ghostHint} />
          ))}
        </div>
      )}
    </>
  );
}
