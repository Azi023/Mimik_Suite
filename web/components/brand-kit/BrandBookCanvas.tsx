/**
 * Brand Kit v2 — the brand-book canvas (spec §6/§7): ONE template, TWO surfaces.
 *
 * The canvas is its own editorial surface: CSS custom properties derived from the CLIENT's
 * tokens are written on the canvas root, so the book carries the client's brand while any
 * surrounding chrome stays untouched. The studio page renders it inside the mono-admin
 * shell (`view="studio"`); the public share route renders it full-bleed with zero admin
 * chrome (`view="client"`, §5 client rules).
 *
 * Export modes (spec §8): `exportMode` renders the registry statically — no tab nav, no
 * interactive chrome — for the Playwright PDF/PNG paths. Panels keep their
 * `data-kit-section` attributes in every mode; that attribute IS the export contract.
 */

import type { CSSProperties, JSX, ReactNode } from "react";
import type { ApiBrand } from "@/lib/api";
import { deriveKitCanvasVars } from "@/lib/brand-kit";
import { ApplicationsSection } from "./ApplicationsSection";
import { BrandKitTabs } from "./BrandKitTabs";
import { ColoursFontsSection } from "./ColoursFontsSection";
import { DirectionSection } from "./DirectionSection";
import { DiscoverySection } from "./DiscoverySection";
import { LogoSuiteSection } from "./LogoSuiteSection";
import { LaunchTemplatesSection } from "./LaunchTemplatesSection";
import { KIT_TABS, type BookExportMode, type BookView } from "./registry";
import "./brand-kit.css";

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

function Colophon(): JSX.Element {
  return (
    <footer className="bk-colophon">
      <div className="bk-fleur">❦</div>
      Prepared by Mimik Creations · Brand Kit v2 · rendered from live brand tokens
    </footer>
  );
}

/** All six chapters, keyed by section-registry key, rendered for the given surface. */
function buildPanels(
  brand: ApiBrand,
  clientName: string,
  view: BookView,
): Record<string, JSX.Element> {
  return {
    discovery: <DiscoverySection brand={brand} clientName={clientName} view={view} />,
    direction: <DirectionSection brand={brand} view={view} />,
    logo_suite: <LogoSuiteSection brand={brand} view={view} />,
    colours_fonts: <ColoursFontsSection brand={brand} view={view} />,
    applications: <ApplicationsSection brand={brand} view={view} />,
    launch_templates: <LaunchTemplatesSection brand={brand} view={view} />,
  };
}

interface BrandBookCanvasProps {
  brand: ApiBrand;
  /** The "Client" meta cell of chapter 01 (the share view passes the brand name). */
  clientName: string;
  view: BookView;
  /** Static export render for the Playwright PDF/PNG paths; null ⇒ the interactive book. */
  exportMode?: BookExportMode | null;
  /** Studio-only control bar (publish/share/export); rendered above the masthead. */
  controls?: ReactNode;
  /** Full-bleed skin for the public route (no shell margins, paper to the viewport edge). */
  fullBleed?: boolean;
}

export function BrandBookCanvas({
  brand,
  clientName,
  view,
  exportMode = null,
  controls = null,
  fullBleed = false,
}: BrandBookCanvasProps): JSX.Element {
  const canvasVars = deriveKitCanvasVars(brand) as CSSProperties;
  const panels = buildPanels(brand, clientName, view);
  const canvasClass = [
    "bk-canvas",
    fullBleed ? "bk-canvas--full" : "",
    exportMode !== null ? "bk-canvas--export" : "",
  ]
    .filter((part) => part !== "")
    .join(" ");

  if (exportMode !== null) {
    // Static registry render — no tab nav, no interactive chrome (spec §8).
    const keys =
      exportMode.kind === "pdf" ? KIT_TABS.map((tab) => tab.key) : [exportMode.section];
    return (
      <div className={canvasClass} style={canvasVars}>
        {exportMode.kind === "pdf" && <Masthead brand={brand} />}
        <div className="bk-bookwrap">
          <main className="bk-sheet">
            {keys.map((key) => (
              <section
                key={key}
                data-kit-section={key}
                className="bk-panel bk-panel--export"
              >
                {panels[key]}
              </section>
            ))}
          </main>
        </div>
        {exportMode.kind === "pdf" && <Colophon />}
      </div>
    );
  }

  return (
    <div className={canvasClass} style={canvasVars}>
      {controls}
      <Masthead brand={brand} />
      {/* The book opens on chapter 01 (the reference's reading order). */}
      <BrandKitTabs tabs={KIT_TABS} panels={panels} initialKey="discovery" />
      <Colophon />
    </div>
  );
}
