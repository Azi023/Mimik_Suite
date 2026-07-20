"use client";

import { useRef, useState, type CSSProperties, type JSX, type PointerEvent } from "react";
import Link from "next/link";
import { saveBrandKit, type KitSaveResult } from "@/app/brands/[id]/kit/actions";
import { useAutosave, useUnsavedGuard } from "@/lib/hooks";
import type {
  ApiBrand,
  ApiBrandLayout,
  ApiBrandTokens,
  ApiLayoutGuide,
  ApiLogoPlacement,
  ApiMargins,
} from "@/lib/api";

interface BrandKitEditorProps {
  brand: ApiBrand;
  clientName: string | null;
}

interface ColorRow {
  name: string;
  hex: string;
  usage: string;
}

const DEFAULT_LAYOUT: ApiBrandLayout = {
  logo_placement: "top_left",
  logo_scale: 0.12,
  margins: { top: 5, right: 5, bottom: 5, left: 5 },
  header: false,
  footer: false,
  grid_columns: 0,
  grid_gutter_pct: 2,
  guides: [],
  show_guides: true,
};

const PLACEMENTS: ApiLogoPlacement[] = [
  "top_left",
  "top_center",
  "top_right",
  "middle_left",
  "center",
  "middle_right",
  "bottom_left",
  "bottom_center",
  "bottom_right",
];

const FORMATS = [
  { key: "portrait", label: "4:5", w: 4, h: 5 },
  { key: "square", label: "1:1", w: 1, h: 1 },
  { key: "story", label: "9:16", w: 9, h: 16 },
] as const;

/** Height of a header/footer band, as % of canvas height (fixed for now; the toggle is what matters). */
const BAND_H = 9;

function nn(value: string): string | null {
  const t = value.trim();
  return t === "" ? null : t;
}

function splitPlacement(p: ApiLogoPlacement): { vert: "top" | "middle" | "bottom"; horiz: "left" | "center" | "right" } {
  const vert = p.startsWith("top") ? "top" : p.startsWith("bottom") ? "bottom" : "middle";
  const horiz = p.endsWith("left") ? "left" : p.endsWith("right") ? "right" : "center";
  return { vert, horiz };
}

export function BrandKitEditor({ brand, clientName }: BrandKitEditorProps): JSX.Element {
  const initialLayout = brand.tokens.layout ?? DEFAULT_LAYOUT;

  const [colors, setColors] = useState<ColorRow[]>(
    brand.tokens.colors.map((c) => ({ name: c.name, hex: c.hex, usage: c.usage ?? "" })),
  );
  const [headingFont, setHeadingFont] = useState(brand.tokens.typography.heading_font ?? "");
  const [bodyFont, setBodyFont] = useState(brand.tokens.typography.body_font ?? "");
  const [logoNotes, setLogoNotes] = useState(brand.tokens.logo.assessment ?? "");
  const [logoMinSize, setLogoMinSize] = useState(
    brand.tokens.logo.min_size_px !== null ? String(brand.tokens.logo.min_size_px) : "",
  );

  const [placement, setPlacement] = useState<ApiLogoPlacement>(initialLayout.logo_placement);
  const [scale, setScale] = useState(initialLayout.logo_scale);
  const [margins, setMargins] = useState<ApiMargins>(initialLayout.margins);
  const [linked, setLinked] = useState(true);
  const [header, setHeader] = useState(initialLayout.header);
  const [footer, setFooter] = useState(initialLayout.footer);
  const [gridColumns, setGridColumns] = useState(initialLayout.grid_columns);
  const [gutter, setGutter] = useState(initialLayout.grid_gutter_pct);
  const [guides, setGuides] = useState<ApiLayoutGuide[]>(initialLayout.guides);
  const [showGuides, setShowGuides] = useState(initialLayout.show_guides);

  const [formatKey, setFormatKey] = useState<(typeof FORMATS)[number]["key"]>("portrait");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<KitSaveResult | null>(null);
  // Bumped on every edit → the autosave debounce resets on each change (true idle-save).
  const [rev, setRev] = useState(0);

  const artRef = useRef<HTMLDivElement>(null);
  const dragIndex = useRef<number | null>(null);

  const format = FORMATS.find((f) => f.key === formatKey) ?? FORMATS[0];
  const ratioWH = format.w / format.h; // width / height; short edge is width for every preset

  // Any change marks dirty + clears the last save banner.
  function touched(): void {
    setDirty(true);
    setResult(null);
    setRev((r) => r + 1);
  }

  function setMargin(edge: keyof ApiMargins, value: number): void {
    const v = Number.isFinite(value) ? Math.max(0, Math.min(40, value)) : 0;
    setMargins((m) => (linked ? { top: v, right: v, bottom: v, left: v } : { ...m, [edge]: v }));
    touched();
  }

  function collectTokens(): ApiBrandTokens {
    return {
      colors: colors
        .filter((c) => c.hex.trim() !== "")
        .map((c) => ({ name: c.name.trim() === "" ? c.hex : c.name.trim(), hex: c.hex, usage: nn(c.usage) })),
      typography: {
        heading_font: nn(headingFont),
        body_font: nn(bodyFont),
        hierarchy: brand.tokens.typography.hierarchy,
      },
      logo: {
        ref: brand.tokens.logo.ref,
        clear_space: brand.tokens.logo.clear_space,
        min_size_px: logoMinSize.trim() === "" ? null : Math.max(0, Math.round(Number(logoMinSize))),
        assessment: nn(logoNotes),
      },
      layout: {
        logo_placement: placement,
        logo_scale: scale,
        margins,
        header,
        footer,
        grid_columns: gridColumns,
        grid_gutter_pct: gutter,
        guides,
        show_guides: showGuides,
      },
    };
  }

  async function onSave(): Promise<void> {
    setBusy(true);
    const res = await saveBrandKit(brand.id, collectTokens());
    setResult(res);
    if (res.ok) setDirty(false);
    setBusy(false);
  }

  // Resilience (FRONTEND_ROADMAP §2): warn on leave with unsaved edits + debounced background save.
  useUnsavedGuard(dirty);
  useAutosave(onSave, dirty && !busy, rev);

  // --- guide dragging ---
  function onGuideDown(e: PointerEvent<HTMLDivElement>, i: number): void {
    e.currentTarget.setPointerCapture(e.pointerId);
    dragIndex.current = i;
  }
  function onGuideMove(e: PointerEvent<HTMLDivElement>, i: number): void {
    if (dragIndex.current !== i || artRef.current === null) return;
    const rect = artRef.current.getBoundingClientRect();
    const g = guides[i];
    const raw = g.axis === "x" ? (e.clientX - rect.left) / rect.width : (e.clientY - rect.top) / rect.height;
    const pos = Math.max(0, Math.min(1, raw));
    setGuides((gs) => gs.map((x, idx) => (idx === i ? { ...x, pos } : x)));
    touched();
  }
  function onGuideUp(e: PointerEvent<HTMLDivElement>): void {
    e.currentTarget.releasePointerCapture(e.pointerId);
    dragIndex.current = null;
  }

  // --- artboard geometry (percentages) ---
  const insTop = margins.top * ratioWH; // % of height
  const insBottom = margins.bottom * ratioWH;
  const insLeft = margins.left; // % of width
  const insRight = margins.right;

  function logoStyle(): CSSProperties {
    const { vert, horiz } = splitPlacement(placement);
    const wPct = scale * 100; // % of width
    const hPct = scale * 100 * ratioWH; // same px -> % of height
    const style: CSSProperties = { width: `${wPct}%`, height: `${hPct}%` };
    const tx: string[] = [];
    if (horiz === "left") style.left = `${insLeft}%`;
    else if (horiz === "right") style.right = `${insRight}%`;
    else {
      style.left = "50%";
      tx.push("translateX(-50%)");
    }
    const topSafe = insTop + (header ? BAND_H : 0);
    const botSafe = insBottom + (footer ? BAND_H : 0);
    if (vert === "top") style.top = `${topSafe}%`;
    else if (vert === "bottom") style.bottom = `${botSafe}%`;
    else {
      style.top = "50%";
      tx.push("translateY(-50%)");
    }
    if (tx.length > 0) style.transform = tx.join(" ");
    return style;
  }

  return (
    <div className="kit">
      <header className="kit__bar">
        <div className="kit__ident">
          <Link href="/briefs" className="kit__back">
            ← Briefs
          </Link>
          <div>
            <h1 className="kit__title">{clientName ?? brand.name} — brand kit</h1>
            <p className="kit__sub">Colours, type, logo, and the default layout every creative inherits.</p>
          </div>
        </div>
        <button type="button" className="btn-primary" onClick={onSave} disabled={busy || !dirty}>
          {busy ? "Saving…" : dirty ? "Save kit" : "Saved"}
        </button>
      </header>

      {result !== null && (
        <p
          className={result.ok ? "brief-savemsg brief-savemsg--ok" : "brief-savemsg brief-savemsg--err"}
          role={result.ok ? "status" : "alert"}
        >
          {result.ok ? "Brand kit saved." : result.error}
        </p>
      )}

      <div className="kit__cols">
        <div className="kit__controls">
          <Card title="Palette">
            <div className="wiz-colors">
              {colors.map((c, i) => (
                <div className="wiz-color-row" key={i}>
                  <input
                    type="color"
                    className="wiz-color__swatch"
                    value={c.hex}
                    onChange={(e) => {
                      setColors((cs) => cs.map((x, idx) => (idx === i ? { ...x, hex: e.target.value } : x)));
                      touched();
                    }}
                    aria-label="Colour"
                  />
                  <input
                    className="input"
                    value={c.name}
                    onChange={(e) => {
                      setColors((cs) => cs.map((x, idx) => (idx === i ? { ...x, name: e.target.value } : x)));
                      touched();
                    }}
                    placeholder="Name"
                  />
                  <input
                    className="input"
                    value={c.usage}
                    onChange={(e) => {
                      setColors((cs) => cs.map((x, idx) => (idx === i ? { ...x, usage: e.target.value } : x)));
                      touched();
                    }}
                    placeholder="Usage"
                  />
                  <button
                    type="button"
                    className="btn-ghost"
                    aria-label="Remove colour"
                    onClick={() => {
                      setColors((cs) => cs.filter((_, idx) => idx !== i));
                      touched();
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => {
                setColors((cs) => [...cs, { name: "", hex: "#4b5563", usage: "" }]);
                touched();
              }}
            >
              + Add colour
            </button>
          </Card>

          <Card title="Typography">
            <div className="wiz-grid">
              <label className="wiz-field">
                <span className="wiz-field__label">Heading font</span>
                <input
                  className="input"
                  value={headingFont}
                  onChange={(e) => {
                    setHeadingFont(e.target.value);
                    touched();
                  }}
                  placeholder="Fraunces"
                />
              </label>
              <label className="wiz-field">
                <span className="wiz-field__label">Body font</span>
                <input
                  className="input"
                  value={bodyFont}
                  onChange={(e) => {
                    setBodyFont(e.target.value);
                    touched();
                  }}
                  placeholder="Inter"
                />
              </label>
            </div>
          </Card>

          <Card title="Logo">
            <label className="wiz-field">
              <span className="wiz-field__label">Logo notes</span>
              <textarea
                className="input brief-textarea"
                rows={2}
                value={logoNotes}
                onChange={(e) => {
                  setLogoNotes(e.target.value);
                  touched();
                }}
                placeholder="Usable as-is / needs a redesign — and why."
              />
            </label>
            <label className="wiz-field">
              <span className="wiz-field__label">Minimum size (px)</span>
              <input
                className="input wiz-narrow"
                type="number"
                min={0}
                value={logoMinSize}
                onChange={(e) => {
                  setLogoMinSize(e.target.value);
                  touched();
                }}
                placeholder="24"
              />
            </label>
          </Card>

          <Card title="Layout">
            <div className="kit-sub">Logo placement</div>
            <div className="kit-anchor" role="radiogroup" aria-label="Logo placement">
              {PLACEMENTS.map((p) => (
                <button
                  type="button"
                  key={p}
                  role="radio"
                  aria-checked={placement === p}
                  aria-label={p.replace(/_/g, " ")}
                  className={`kit-anchor__cell${placement === p ? " kit-anchor__cell--on" : ""}`}
                  onClick={() => {
                    setPlacement(p);
                    touched();
                  }}
                >
                  <span className="kit-anchor__dot" />
                </button>
              ))}
            </div>

            <label className="wiz-field">
              <span className="wiz-field__label">
                Logo size <span className="kit-readout">{Math.round(scale * 100)}% of width</span>
              </span>
              <input
                type="range"
                min={2}
                max={60}
                value={Math.round(scale * 100)}
                onChange={(e) => {
                  setScale(Number(e.target.value) / 100);
                  touched();
                }}
              />
            </label>

            <div className="kit-sub kit-sub--row">
              <span>Margins (% of short edge)</span>
              <button
                type="button"
                className={`kit-link${linked ? " kit-link--on" : ""}`}
                onClick={() => setLinked((l) => !l)}
                aria-pressed={linked}
              >
                {linked ? "Linked" : "Per-edge"}
              </button>
            </div>
            <div className="kit-margins">
              {(["top", "right", "bottom", "left"] as const).map((edge) => (
                <label className="kit-margins__field" key={edge}>
                  <span>{edge}</span>
                  <input
                    className="input"
                    type="number"
                    min={0}
                    max={40}
                    value={margins[edge]}
                    onChange={(e) => setMargin(edge, Number(e.target.value))}
                  />
                </label>
              ))}
            </div>

            <div className="kit-toggles">
              <Toggle label="Header band" on={header} onChange={(v) => { setHeader(v); touched(); }} />
              <Toggle label="Footer band" on={footer} onChange={(v) => { setFooter(v); touched(); }} />
            </div>

            <div className="kit-sub">Alignment grid</div>
            <div className="wiz-grid">
              <label className="wiz-field">
                <span className="wiz-field__label">Columns <span className="kit-readout">0 = off</span></span>
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={24}
                  value={gridColumns}
                  onChange={(e) => {
                    setGridColumns(Math.max(0, Math.min(24, Math.round(Number(e.target.value)))));
                    touched();
                  }}
                />
              </label>
              <label className="wiz-field">
                <span className="wiz-field__label">Gutter %</span>
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={20}
                  value={gutter}
                  onChange={(e) => {
                    setGutter(Math.max(0, Math.min(20, Number(e.target.value))));
                    touched();
                  }}
                />
              </label>
            </div>

            <div className="kit-sub kit-sub--row">
              <span>Guides</span>
              <Toggle label="Show" on={showGuides} onChange={(v) => { setShowGuides(v); touched(); }} />
            </div>
            <div className="kit-guide-actions">
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  setGuides((g) => [...g, { axis: "x", pos: 0.5 }]);
                  setShowGuides(true);
                  touched();
                }}
              >
                + Vertical guide
              </button>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  setGuides((g) => [...g, { axis: "y", pos: 0.5 }]);
                  setShowGuides(true);
                  touched();
                }}
              >
                + Horizontal guide
              </button>
            </div>
            {guides.length > 0 && (
              <ul className="kit-guide-list">
                {guides.map((g, i) => (
                  <li key={i} className="kit-guide-list__item">
                    <span className="kit-guide-list__axis">{g.axis === "x" ? "Vertical" : "Horizontal"}</span>
                    <span className="kit-readout">{Math.round(g.pos * 100)}%</span>
                    <button
                      type="button"
                      className="brief-chip__x"
                      aria-label="Remove guide"
                      onClick={() => {
                        setGuides((gs) => gs.filter((_, idx) => idx !== i));
                        touched();
                      }}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="wiz__hint">Drag guide lines on the preview to reposition them.</p>
          </Card>
        </div>

        <aside className="kit__preview">
          <div className="kit-formats">
            {FORMATS.map((f) => (
              <button
                type="button"
                key={f.key}
                className={`kit-format${formatKey === f.key ? " kit-format--on" : ""}`}
                onClick={() => setFormatKey(f.key)}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="kit-stage">
            {/* top ruler */}
            <div className="kit-ruler kit-ruler--top" aria-hidden="true">
              {[0, 25, 50, 75, 100].map((t) => (
                <span key={t} className="kit-ruler__tick" style={{ left: `${t}%` }}>
                  {t}
                </span>
              ))}
            </div>
            <div className="kit-ruler kit-ruler--left" aria-hidden="true">
              {[0, 25, 50, 75, 100].map((t) => (
                <span key={t} className="kit-ruler__tick" style={{ top: `${t}%` }}>
                  {t}
                </span>
              ))}
            </div>

            <div
              ref={artRef}
              className="kit-art"
              style={{ aspectRatio: `${format.w} / ${format.h}` }}
            >
              {header && <div className="kit-art__band kit-art__band--top" style={{ height: `${BAND_H}%` }}>Header</div>}
              {footer && <div className="kit-art__band kit-art__band--bottom" style={{ height: `${BAND_H}%` }}>Footer</div>}

              {/* safe area */}
              <div
                className="kit-art__safe"
                style={{ top: `${insTop}%`, right: `${insRight}%`, bottom: `${insBottom}%`, left: `${insLeft}%` }}
              >
                {gridColumns > 0 && (
                  <div
                    className="kit-art__grid"
                    style={{ gridTemplateColumns: `repeat(${gridColumns}, 1fr)`, gap: `${gutter}%` }}
                  >
                    {Array.from({ length: gridColumns }).map((_, i) => (
                      <span key={i} className="kit-art__col" />
                    ))}
                  </div>
                )}
              </div>

              {/* logo */}
              <div className="kit-art__logo" style={logoStyle()}>
                LOGO
              </div>

              {/* guides */}
              {showGuides &&
                guides.map((g, i) =>
                  g.axis === "x" ? (
                    <div
                      key={i}
                      className="kit-guide kit-guide--v"
                      style={{ left: `${g.pos * 100}%` }}
                      onPointerDown={(e) => onGuideDown(e, i)}
                      onPointerMove={(e) => onGuideMove(e, i)}
                      onPointerUp={(e) => onGuideUp(e)}
                    >
                      <span className="kit-guide__label">{Math.round(g.pos * 100)}%</span>
                    </div>
                  ) : (
                    <div
                      key={i}
                      className="kit-guide kit-guide--h"
                      style={{ top: `${g.pos * 100}%` }}
                      onPointerDown={(e) => onGuideDown(e, i)}
                      onPointerMove={(e) => onGuideMove(e, i)}
                      onPointerUp={(e) => onGuideUp(e)}
                    >
                      <span className="kit-guide__label">{Math.round(g.pos * 100)}%</span>
                    </div>
                  ),
                )}
            </div>
          </div>
          <p className="kit-preview__note">
            Preview only — the compositor applies these defaults when it composes each creative.
          </p>
        </aside>
      </div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }): JSX.Element {
  return (
    <section className="kit-card">
      <h2 className="kit-card__title">{title}</h2>
      <div className="kit-card__body">{children}</div>
    </section>
  );
}

function Toggle({ label, on, onChange }: { label: string; on: boolean; onChange: (v: boolean) => void }): JSX.Element {
  return (
    <button
      type="button"
      className={`kit-toggle${on ? " kit-toggle--on" : ""}`}
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
    >
      <span className="kit-toggle__track">
        <span className="kit-toggle__thumb" />
      </span>
      {label}
    </button>
  );
}
