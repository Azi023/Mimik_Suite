/** Chapter 06 — approved launch creatives presented as ready-to-post template cards. */

import type { JSX } from "react";
import type { ApiBrand, ApiLaunchTemplate } from "@/lib/api";
import { titleCase } from "@/lib/brand-kit";
import { BrandKitAssetImage } from "./BrandKitAssetImage";
import { BrandKitCreativeImage } from "./BrandKitCreativeImage";
import type { BookView } from "./registry";
import { filled, PlaceholderChapter, SectionHead } from "./shared";

const EMPTY_TEMPLATE_COUNT = 3;

function hasPreview(template: ApiLaunchTemplate): boolean {
  return filled(template.creative_id) || filled(template.asset_id);
}

function TemplatePreview({
  template,
  view,
}: {
  template: ApiLaunchTemplate;
  view: BookView;
}): JSX.Element {
  if (filled(template.creative_id)) {
    return (
      <BrandKitCreativeImage
        creativeId={template.creative_id}
        alt={`${template.name} launch template`}
        fallbackLabel="render unavailable"
      />
    );
  }
  if (filled(template.asset_id)) {
    return (
      <BrandKitAssetImage
        assetId={template.asset_id}
        alt={`${template.name} launch template`}
        fit="cover"
        fallbackLabel="asset unavailable"
      />
    );
  }
  return (
    <div className="bk-tpl-placeholder">
      <p>{template.name}</p>
      <em>{view === "studio" ? "generated at launch" : "in production"}</em>
    </div>
  );
}

export function LaunchTemplatesSection({
  brand,
  view,
}: {
  brand: ApiBrand;
  view: BookView;
}): JSX.Element {
  const templates = brand.kit?.launch_templates ?? [];
  if (view === "client" && !templates.some(hasPreview)) {
    return <PlaceholderChapter number="06" label="Launch Templates" />;
  }

  const items: ApiLaunchTemplate[] =
    templates.length > 0
      ? templates
      : Array.from(
          { length: EMPTY_TEMPLATE_COUNT },
          (_, index): ApiLaunchTemplate => ({
            name: `Template slot ${index + 1}`,
            format_key: "format pending",
            creative_id: null,
            asset_id: null,
          }),
        );

  return (
    <>
      <SectionHead kicker="Chapter 06 — Launch Templates" />
      <h2 className="bk-sec-title">Ready to post from day one.</h2>
      <p className="bk-sec-sub">
        Approved formats, pre-composed in the brand system and ready for the launch calendar.
      </p>

      <div className="bk-tpl-grid">
        {items.map((template, index) => (
          <article
            key={`${template.creative_id ?? template.asset_id ?? template.name}-${index}`}
            className="bk-tpl-card"
          >
            <div
              className={
                template.format_key.includes("story")
                  ? "bk-tpl-art bk-tpl-art--portrait"
                  : "bk-tpl-art"
              }
            >
              <TemplatePreview template={template} view={view} />
            </div>
            <div className="bk-tpl-meta">
              <span className="bk-tpl-name">{template.name}</span>
              <span className="bk-tpl-format">{titleCase(template.format_key)}</span>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
