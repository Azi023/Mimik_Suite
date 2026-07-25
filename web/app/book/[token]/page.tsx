import type { JSX } from "react";
import { BrandBookCanvas } from "@/components/brand-kit/BrandBookCanvas";
import { isKitSectionKey, type BookExportMode } from "@/components/brand-kit/registry";
import { getPublishedBrandBook } from "@/lib/api";
import "@/components/brand-kit/brand-kit.css";

export const dynamic = "force-dynamic";

/**
 * PUBLIC brand-book share view (spec §8) — `/book/{token}`.
 *
 * NO user auth: the token IS the capability (the magic-link pattern). The API's
 * `GET /brand-book/{token}` returns the full brand only while the kit is published;
 * anything else — expired, unpublished, unknown — renders the same calm unavailable
 * page. The book renders with the §5 CLIENT rules (empty rows omitted, "in production"
 * tiles, sparse chapters collapsed), full-bleed, with zero admin chrome.
 *
 * Export query params (driven by the Playwright exporter):
 *   ?export=pdf                 — whole book stacked, tab nav hidden (print CSS paginates)
 *   ?export=png&section={key}   — one `[data-kit-section]` block, isolated for an
 *                                 element screenshot
 */

type SearchParams = Record<string, string | string[] | undefined>;

/** First value of a possibly-repeated query param. */
function firstParam(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

/** Resolve `?export=…` into a render mode; "invalid" ⇒ the calm unavailable page. */
function resolveExportMode(query: SearchParams): BookExportMode | null | "invalid" {
  const exportParam = firstParam(query.export);
  if (exportParam === null || exportParam === "") {
    return null;
  }
  if (exportParam === "pdf") {
    return { kind: "pdf" };
  }
  if (exportParam === "png") {
    const section = firstParam(query.section);
    if (section === null || !isKitSectionKey(section)) {
      return "invalid";
    }
    return { kind: "png", section };
  }
  return null;
}

/** Calm terminal state — never a stack trace, never an app error surface. */
function BookUnavailable(): JSX.Element {
  return (
    <div className="bk-void">
      <div className="bk-void-card">
        <span className="bk-fleur">❦</span>
        <h1>This brand book isn&apos;t available</h1>
        <p>
          The link may have expired, or the book hasn&apos;t been published yet. Ask your
          studio contact for a fresh link.
        </p>
        <span className="bk-void-colophon">Mimik Creations · Brand Kit</span>
      </div>
    </div>
  );
}

export default async function PublicBrandBookPage({
  params,
  searchParams,
}: {
  params: Promise<{ token: string }>;
  searchParams: Promise<SearchParams>;
}): Promise<JSX.Element> {
  const [{ token }, query] = await Promise.all([params, searchParams]);

  const brand = await getPublishedBrandBook(token);
  if (brand === null) {
    return <BookUnavailable />;
  }

  const exportMode = resolveExportMode(query);
  if (exportMode === "invalid") {
    return <BookUnavailable />;
  }

  return (
    <BrandBookCanvas
      brand={brand}
      clientName={brand.name}
      view="client"
      exportMode={exportMode}
      fullBleed
    />
  );
}
