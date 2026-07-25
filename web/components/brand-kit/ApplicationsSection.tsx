/** Chapter 05 — real creative renders framed as physical and digital applications. */

import type { JSX } from "react";
import type { ApiBrand, ApiBrandApplication, ApiBrandApplicationKind } from "@/lib/api";
import { titleCase } from "@/lib/brand-kit";
import { BrandKitAssetImage } from "./BrandKitAssetImage";
import { BrandKitCreativeImage } from "./BrandKitCreativeImage";
import type { BookView } from "./registry";
import { filled, PlaceholderChapter, SectionHead } from "./shared";

const EMPTY_APPLICATIONS: ApiBrandApplicationKind[] = [
  "business_card",
  "ig_post",
  "phone_app",
  "tablet",
];

function hasPreview(application: ApiBrandApplication): boolean {
  return filled(application.creative_id) || filled(application.asset_id);
}

function ApplicationPreview({
  application,
  view,
}: {
  application: ApiBrandApplication;
  view: BookView;
}): JSX.Element {
  const label = titleCase(application.kind);
  if (filled(application.creative_id)) {
    return (
      <BrandKitCreativeImage
        creativeId={application.creative_id}
        alt={application.caption ?? `${label} application`}
        fallbackLabel="render unavailable"
      />
    );
  }
  if (filled(application.asset_id)) {
    return (
      <BrandKitAssetImage
        assetId={application.asset_id}
        alt={application.caption ?? `${label} application`}
        fit="cover"
        fallbackLabel="asset unavailable"
      />
    );
  }
  return (
    <div className="bk-app-placeholder">
      <span className="bk-app-placeholder-frame" aria-hidden="true">
        ▭
      </span>
      <p>{label}</p>
      <em>{view === "studio" ? "mockup not added" : "in production"}</em>
    </div>
  );
}

export function ApplicationsSection({
  brand,
  view,
}: {
  brand: ApiBrand;
  view: BookView;
}): JSX.Element {
  const applications = brand.kit?.applications ?? [];
  if (view === "client" && !applications.some(hasPreview)) {
    return <PlaceholderChapter number="05" label="Applications" />;
  }

  const items: ApiBrandApplication[] =
    applications.length > 0
      ? applications
      : EMPTY_APPLICATIONS.map(
          (kind): ApiBrandApplication => ({
            kind,
            asset_id: null,
            creative_id: null,
            caption: null,
          }),
        );

  return (
    <>
      <SectionHead kicker="Chapter 05 — Applications" />
      <h2 className="bk-sec-title">The brand, out in the world.</h2>
      <p className="bk-sec-sub">
        Delivered work from the creative pipeline, framed in the contexts where customers meet it.
      </p>

      <div className="bk-app-grid">
        {items.map((application, index) => {
          const label = titleCase(application.kind);
          return (
            <figure
              key={`${application.creative_id ?? application.asset_id ?? application.kind}-${index}`}
              className="bk-app-item"
            >
              <div className={`bk-app-stage bk-app-stage--${application.kind}`}>
                <span className="bk-app-label">{label}</span>
                <div className={`bk-app-frame bk-app-frame--${application.kind}`}>
                  <div className="bk-app-media">
                    <ApplicationPreview application={application} view={view} />
                  </div>
                </div>
              </div>
              <figcaption>{filled(application.caption) ? application.caption : label}</figcaption>
            </figure>
          );
        })}
      </div>
    </>
  );
}
