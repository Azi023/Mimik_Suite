/**
 * Chapter 01 — Brand Discovery (studio text editing; client view remains read-only).
 *
 * Studio view: every registry row renders — filled prose, chips, or a tier-1 ghost card.
 * Client view (spec §5): empty rows are OMITTED; fewer than two filled fields collapses the
 * whole chapter to one neutral in-progress card.
 */

import type { JSX } from "react";
import type { ApiBrand, ApiBrandDiscoveryTextField } from "@/lib/api";
import type { BookView } from "./registry";
import { CLIENT_MIN_FILLED_FIELDS } from "./registry";
import {
  EditableTextField,
  filled,
  GhostCard,
  PlaceholderChapter,
  SectionHead,
  type SaveBrandKitTextField,
} from "./shared";

/** One entry of the two-column discovery list — real prose, chips, or a tier-1 ghost. */
interface DiscoveryEntry {
  label: string;
  content: JSX.Element | null;
  ghostHint: string;
  field?: ApiBrandDiscoveryTextField;
  value?: string | null;
  displayValue?: string | null;
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
      field: "purpose",
      value: discovery?.purpose,
    },
    {
      label: "Mission",
      content: prose(discovery?.mission),
      ghostHint: `The mission arrives with discovery — what ${brand.name} does every day to serve that purpose.`,
      field: "mission",
      value: discovery?.mission,
    },
    {
      label: "Vision",
      content: prose(discovery?.vision),
      ghostHint: "The vision arrives with discovery — where this brand is headed if everything works.",
      field: "vision",
      value: discovery?.vision,
    },
    {
      label: "Personality",
      content: prose(discovery?.personality),
      ghostHint: "The personality arrives with discovery — who this brand is when it speaks.",
      field: "personality",
      value: discovery?.personality,
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
      field: "tone_of_voice",
      value: discovery?.tone_of_voice,
      displayValue: discovery?.tone_of_voice ?? brand.brand_voice,
    },
    {
      label: "Key USP",
      content: prose(discovery?.key_usp),
      ghostHint: `The key USP arrives with discovery — the one thing only ${brand.name} can claim.`,
      field: "key_usp",
      value: discovery?.key_usp,
    },
    {
      label: "Visual Competitor Analysis",
      content: prose(discovery?.visual_competitor_analysis),
      ghostHint: "A short read on 2–3 competitor feeds — what they do visually, and what we deliberately won't.",
      field: "visual_competitor_analysis",
      value: discovery?.visual_competitor_analysis,
    },
    {
      label: "Existing Brand Review",
      content: prose(discovery?.existing_brand_review),
      ghostHint: "An honest review of the brand as it stands today — what stays, what the refresh retires.",
      field: "existing_brand_review",
      value: discovery?.existing_brand_review,
    },
    {
      label: "Target Audience",
      content: prose(brand.target_audience),
      ghostHint: "The target audience arrives with the brief draft — who this work must reach, precisely.",
    },
  ];
}

export function DiscoverySection({
  brand,
  clientName,
  view,
  onSaveTextField,
}: {
  brand: ApiBrand;
  clientName: string;
  view: BookView;
  onSaveTextField?: SaveBrandKitTextField;
}): JSX.Element {
  const timeline = brand.kit?.discovery.timeline;
  const entries = discoveryEntries(brand);
  const filledEntries = entries.filter((entry) => entry.content !== null);

  if (view === "client") {
    const filledCount =
      filledEntries.length + (filled(brand.niche) ? 1 : 0) + (filled(timeline) ? 1 : 0);
    if (filledCount < CLIENT_MIN_FILLED_FIELDS) {
      return <PlaceholderChapter number="01" label="Brand Discovery" />;
    }
  }

  const rows = view === "client" ? filledEntries : entries;

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
        {filled(brand.niche) ? (
          <div className="bk-meta-cell">
            <div className="bk-meta-k">Industry</div>
            <div className="bk-meta-v">{brand.niche}</div>
          </div>
        ) : (
          view === "studio" && (
            <div className="bk-meta-cell">
              <div className="bk-meta-k">Industry</div>
              <div className="bk-meta-v bk-meta-v--ghost">to be confirmed at onboarding</div>
            </div>
          )
        )}
        {view === "studio" && onSaveTextField !== undefined ? (
          <div className="bk-meta-cell">
            <div className="bk-meta-k">Timeline</div>
            <EditableTextField
              label="Timeline"
              value={timeline}
              hint="engagement window to come"
              target={{ section: "discovery", field: "timeline" }}
              onSave={onSaveTextField}
              compact
            />
          </div>
        ) : filled(timeline) ? (
          <div className="bk-meta-cell">
            <div className="bk-meta-k">Timeline</div>
            <div className="bk-meta-v">{timeline}</div>
          </div>
        ) : (
          view === "studio" && (
            <div className="bk-meta-cell">
              <div className="bk-meta-k">Timeline</div>
              <div className="bk-meta-v bk-meta-v--ghost">engagement window to come</div>
            </div>
          )
        )}
      </div>

      <div className="bk-disc-grid">
        {rows.map((entry) => (
          <div key={entry.label} className="bk-disc-item">
            <div className="bk-disc-k">{entry.label}</div>
            {view === "studio" &&
            onSaveTextField !== undefined &&
            entry.field !== undefined ? (
              <>
                <EditableTextField
                  label={entry.label}
                  value={entry.value}
                  displayValue={entry.displayValue}
                  hint={entry.ghostHint}
                  target={{ section: "discovery", field: entry.field }}
                  onSave={onSaveTextField}
                />
                {entry.field === "tone_of_voice" &&
                  !filled(entry.value) &&
                  brand.tone_keywords.length > 0 && (
                    <div className="bk-chips">
                      {brand.tone_keywords.map((keyword, index) => (
                        <span key={`${keyword}-${index}`} className="bk-chip">
                          {keyword}
                        </span>
                      ))}
                    </div>
                  )}
              </>
            ) : (
              entry.content ?? <GhostCard hint={entry.ghostHint} />
            )}
          </div>
        ))}
      </div>
    </>
  );
}
