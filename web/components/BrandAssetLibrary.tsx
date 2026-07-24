"use client";

import { useRef, useState, useTransition, type JSX } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ApiBrandAsset, type ApiFontLibraryEntry, type AssetKind, assetRawUrl } from "@/lib/api";
import type { AssetActionResult, FontLibraryResult } from "@/app/assets/actions";

type UploadAction = (
  brandId: string,
  kind: string,
  formData: FormData,
) => Promise<AssetActionResult>;
type AssetAction = (assetId: string) => Promise<AssetActionResult>;
type FontLibraryAction = () => Promise<FontLibraryResult>;
type MaterializeFontAction = (brandId: string, fontKey: string) => Promise<AssetActionResult>;

/** Kinds whose stored bytes are images the browser can render as a thumbnail (fonts are not). */
const IMAGE_KINDS: ReadonlySet<AssetKind> = new Set<AssetKind>([
  "logo",
  "imagery",
  "reference_creative",
]);

interface ClientOption {
  id: string;
  name: string;
}

interface BrandAssetLibraryProps {
  clients: ClientOption[];
  selectedClientId: string;
  /** The selected client's resolved brand; null when the client has no brand/brief yet. */
  brandId: string | null;
  assets: ApiBrandAsset[];
  uploadAction: UploadAction;
  approveAction: AssetAction;
  knockoutAction: AssetAction;
  ingestAction: AssetAction;
  /** Lazy-load the built-in font catalog (team-gated, server-side) for the Fonts picker. */
  fontLibraryAction: FontLibraryAction;
  /** Materialize a chosen built-in font as an approved FONT asset for the brand. */
  materializeFontAction: MaterializeFontAction;
}

/** The four asset kinds, in the order they appear on the page, with their upload affordances. */
interface SectionSpec {
  kind: AssetKind;
  title: string;
  /** File-picker `accept` — the browser hint; the backend re-sniffs the real mime and is the gate. */
  accept: string;
  /** Real empty-state guidance naming the accepted formats (the backend's allow-list). */
  emptyHint: string;
}

const SECTIONS: readonly SectionSpec[] = [
  {
    kind: "logo",
    title: "Logos",
    accept: "image/png,image/jpeg,image/webp",
    emptyHint: "No logos uploaded yet — upload a PNG, JPG or WebP mark.",
  },
  {
    kind: "font",
    title: "Fonts",
    accept: ".ttf,.otf,.woff2,font/ttf,font/otf,font/woff2",
    emptyHint: "No fonts uploaded yet — upload a .ttf, .otf or .woff2.",
  },
  {
    kind: "imagery",
    title: "Product Photos & Imagery",
    accept: "image/png,image/jpeg,image/webp",
    emptyHint: "No product photos yet — upload a PNG, JPG or WebP.",
  },
  {
    kind: "reference_creative",
    title: "Reference Creatives",
    accept: "image/png,image/jpeg,image/webp",
    emptyHint: "No references yet — upload a past creative (PNG, JPG or WebP) to study.",
  },
];

/**
 * The ops-facing brand-asset library: the operator adds per-client brand material — logos, fonts,
 * product photos, and reference creatives — so the engine can composite on top of them. Assets are
 * brand-scoped; the client selector at the top switches which client's brand library is shown
 * (server-resolved via the page). Each kind has its own upload control and per-asset actions
 * (approve; knockout for logos; ingest for references). Image kinds render a real thumbnail via the
 * same-origin `/api/assets/{id}/raw` proxy (auth stays server-side); fonts and non-image assets keep
 * the kind glyph. The Fonts section also offers a built-in-font picker that materializes a catalog
 * font as an approved brand asset. Ingested references additionally show the observed palette and
 * mood (real study data, never invented).
 */
export function BrandAssetLibrary({
  clients,
  selectedClientId,
  brandId,
  assets,
  uploadAction,
  approveAction,
  knockoutAction,
  ingestAction,
  fontLibraryAction,
  materializeFontAction,
}: BrandAssetLibraryProps): JSX.Element {
  const router = useRouter();

  function selectClient(next: string): void {
    router.push(next === "" ? "/assets" : `/assets?client=${encodeURIComponent(next)}`);
  }

  const header = (
    <div className="assetlib__head">
      <div>
        <h1 className="assetlib__title">Brand assets</h1>
        <p className="assetlib__sub">
          Per-client brand material the engine composites on top of. Uploads are team-only; approve
          is the human gate.
        </p>
      </div>
      {clients.length > 0 && (
        <label className="assetlib__clientpick">
          <span className="assetlib__field-label">Client</span>
          <select
            className="tasks__select"
            aria-label="Client"
            value={selectedClientId}
            onChange={(e): void => selectClient(e.target.value)}
          >
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );

  let body: JSX.Element;
  if (clients.length === 0) {
    body = (
      <div className="empty-state">
        <p className="empty-state__title">No clients yet</p>
        <p className="empty-state__body">
          Add a client and create their brand kit first — assets are attached to a client&apos;s
          brand.
        </p>
        <Link className="btn btn--secondary" href="/onboarding">
          Add a client
        </Link>
      </div>
    );
  } else if (brandId === null) {
    body = (
      <div className="empty-state">
        <p className="empty-state__title">No brand yet</p>
        <p className="empty-state__body">
          This client doesn&apos;t have a brand kit &amp; brief yet — create one, then come back to
          add its assets.
        </p>
        <Link
          className="btn btn--secondary"
          href={`/onboarding?clientId=${encodeURIComponent(selectedClientId)}`}
        >
          Create brand kit &amp; brief
        </Link>
      </div>
    );
  } else {
    body = (
      <div className="assetlib__sections">
        {SECTIONS.map((spec) => (
          <AssetSection
            key={spec.kind}
            spec={spec}
            brandId={brandId}
            assets={assets.filter((a) => a.kind === spec.kind)}
            uploadAction={uploadAction}
            approveAction={approveAction}
            knockoutAction={knockoutAction}
            ingestAction={ingestAction}
            fontLibraryAction={fontLibraryAction}
            materializeFontAction={materializeFontAction}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="assetlib">
      <style>{STYLES}</style>
      {header}
      {body}
    </div>
  );
}

interface AssetSectionProps {
  spec: SectionSpec;
  brandId: string;
  assets: ApiBrandAsset[];
  uploadAction: UploadAction;
  approveAction: AssetAction;
  knockoutAction: AssetAction;
  ingestAction: AssetAction;
  fontLibraryAction: FontLibraryAction;
  materializeFontAction: MaterializeFontAction;
}

function AssetSection({
  spec,
  brandId,
  assets,
  uploadAction,
  approveAction,
  knockoutAction,
  ingestAction,
  fontLibraryAction,
  materializeFontAction,
}: AssetSectionProps): JSX.Element {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");

  function onFileChosen(files: FileList | null): void {
    if (files === null || files.length === 0) return;
    setError("");
    const form = new FormData();
    form.append("file", files[0]);
    startTransition(async () => {
      const result = await uploadAction(brandId, spec.kind, form);
      // Reset the picker either way so re-picking the same file re-fires change.
      if (inputRef.current !== null) inputRef.current.value = "";
      if (result.ok) {
        router.refresh();
      } else {
        setError(result.error ?? "Couldn't upload that file.");
      }
    });
  }

  return (
    <section className="assetlib__section" aria-label={spec.title}>
      <div className="assetlib__section-head">
        <h2 className="assetlib__section-title">{spec.title}</h2>
        <span className="tasks__count">
          {assets.length} asset{assets.length === 1 ? "" : "s"}
        </span>
        <div className="assetlib__upload">
          <input
            ref={inputRef}
            type="file"
            className="assetlib__file"
            accept={spec.accept}
            aria-label={`Upload ${spec.title}`}
            disabled={pending}
            onChange={(e): void => onFileChosen(e.target.files)}
          />
          <button
            type="button"
            className="btn btn--primary btn--sm"
            disabled={pending}
            onClick={(): void => inputRef.current?.click()}
          >
            {pending ? "Uploading…" : "Upload"}
          </button>
        </div>
      </div>

      {error !== "" && (
        <p className="tasks__error" role="alert">
          {error}
        </p>
      )}

      {spec.kind === "font" && (
        <BuiltinFontPicker
          brandId={brandId}
          loadAction={fontLibraryAction}
          materializeAction={materializeFontAction}
        />
      )}

      {assets.length === 0 ? (
        <div className="empty-state assetlib__empty">
          <p className="empty-state__body">{spec.emptyHint}</p>
        </div>
      ) : (
        <div className="assetlib__grid">
          {assets.map((asset) => (
            <AssetCard
              key={asset.id}
              asset={asset}
              approveAction={approveAction}
              knockoutAction={knockoutAction}
              ingestAction={ingestAction}
            />
          ))}
        </div>
      )}
    </section>
  );
}

interface AssetCardProps {
  asset: ApiBrandAsset;
  approveAction: AssetAction;
  knockoutAction: AssetAction;
  ingestAction: AssetAction;
}

function AssetCard({
  asset,
  approveAction,
  knockoutAction,
  ingestAction,
}: AssetCardProps): JSX.Element {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function run(action: AssetAction): void {
    setError("");
    setNotice("");
    startTransition(async () => {
      const result = await action(asset.id);
      if (result.ok) {
        if (result.message !== undefined && result.message !== "") setNotice(result.message);
        router.refresh();
      } else {
        setError(result.error ?? "That action failed.");
      }
    });
  }

  const isFont = asset.kind === "font";
  const study = asset.study;

  return (
    <div className="assetcard">
      <AssetThumb asset={asset} />

      <div className="assetcard__body">
        <p className="assetcard__name" title={asset.filename}>
          {asset.filename}
        </p>
        <p className="assetcard__meta">
          {isFont ? "Font · " : ""}
          {asset.mime}
        </p>

        <span
          className={`assetcard__badge assetcard__badge--${asset.approved ? "ok" : "pending"}`}
        >
          {asset.approved ? "Approved" : "Pending approval"}
        </span>

        {study !== null && (
          <div className="assetcard__study">
            {study.palette.length > 0 && (
              <div className="assetcard__palette" aria-label="Observed palette">
                {study.palette.slice(0, 6).map((hex, i) => (
                  <span
                    key={`${hex}-${i}`}
                    className="assetcard__swatch"
                    style={{ background: hex }}
                    title={hex}
                  />
                ))}
              </div>
            )}
            {study.mood !== null && study.mood !== "" && (
              <p className="assetcard__mood">{study.mood}</p>
            )}
          </div>
        )}

        <div className="assetcard__actions">
          {!asset.approved && (
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              disabled={pending}
              onClick={(): void => run(approveAction)}
            >
              Approve
            </button>
          )}
          {asset.kind === "logo" && (
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              disabled={pending}
              onClick={(): void => run(knockoutAction)}
            >
              Derive knockout
            </button>
          )}
          {asset.kind === "reference_creative" && (
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              disabled={pending}
              onClick={(): void => run(ingestAction)}
            >
              {study === null ? "Ingest" : "Re-ingest"}
            </button>
          )}
        </div>

        {error !== "" && (
          <p className="assetcard__err" role="alert">
            {error}
          </p>
        )}
        {notice !== "" && (
          <p className="assetcard__notice" role="status">
            {notice}
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * The asset tile. For image kinds (logo, imagery, reference_creative) it renders a REAL thumbnail
 * proxied through `/api/assets/{id}/raw` (auth attached server-side). The kind glyph shows while the
 * image loads and stays as the honest fallback for fonts, non-image mimes, or a failed/absent byte
 * stream (e.g. an asset whose bytes were never stored). No invented imagery — glyph or the real file.
 */
function AssetThumb({ asset }: { asset: ApiBrandAsset }): JSX.Element {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const isImage = IMAGE_KINDS.has(asset.kind) && asset.mime.startsWith("image/");

  if (!isImage || failed) {
    return (
      <div className={`assetcard__tile assetcard__tile--${asset.kind}`} aria-hidden="true">
        <KindGlyph kind={asset.kind} />
      </div>
    );
  }

  return (
    <div className={`assetcard__tile assetcard__tile--${asset.kind} assetcard__tile--img`}>
      {!loaded && <KindGlyph kind={asset.kind} />}
      <Image
        className="assetcard__thumb"
        src={assetRawUrl(asset.id)}
        alt=""
        width={48}
        height={48}
        unoptimized
        style={{ opacity: loaded ? 1 : 0 }}
        onLoad={(): void => setLoaded(true)}
        onError={(): void => setFailed(true)}
      />
    </div>
  );
}

interface BuiltinFontPickerProps {
  brandId: string;
  loadAction: FontLibraryAction;
  materializeAction: MaterializeFontAction;
}

/**
 * "Choose a built-in font" — lazily loads the team-gated catalog (GET /fonts/library, server-side)
 * on open, then on select materializes the font as an approved brand FONT asset
 * (POST /brands/{id}/fonts/{key}) and refreshes so it appears in the grid. Real empty/error/loading
 * states; the catalog is never faked.
 */
function BuiltinFontPicker({
  brandId,
  loadAction,
  materializeAction,
}: BuiltinFontPickerProps): JSX.Element {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [fonts, setFonts] = useState<ApiFontLibraryEntry[] | null>(null);
  const [pending, startTransition] = useTransition();
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [error, setError] = useState("");

  function toggle(): void {
    const next = !open;
    setOpen(next);
    if (next && fonts === null) {
      setError("");
      startTransition(async () => {
        const result = await loadAction();
        if (result.ok && result.fonts !== undefined) {
          setFonts(result.fonts);
        } else {
          setError(result.error ?? "Couldn't load the built-in fonts.");
        }
      });
    }
  }

  function choose(key: string): void {
    setError("");
    setPendingKey(key);
    startTransition(async () => {
      const result = await materializeAction(brandId, key);
      setPendingKey(null);
      if (result.ok) {
        setOpen(false);
        router.refresh();
      } else {
        setError(result.error ?? "Couldn't add that font.");
      }
    });
  }

  return (
    <div className="fontpick">
      <button
        type="button"
        className="btn btn--secondary btn--sm"
        aria-expanded={open}
        onClick={toggle}
      >
        {open ? "Hide built-in fonts" : "Choose a built-in font"}
      </button>

      {open && (
        <div className="fontpick__panel">
          {pending && fonts === null ? (
            <p className="fontpick__note">Loading built-in fonts…</p>
          ) : error !== "" && fonts === null ? (
            <p className="tasks__error" role="alert">
              {error}
            </p>
          ) : fonts !== null && fonts.length === 0 ? (
            <p className="fontpick__note">No built-in fonts are available.</p>
          ) : fonts !== null ? (
            <>
              <ul className="fontpick__list">
                {fonts.map((font) => (
                  <li key={font.key} className="fontpick__item">
                    <div className="fontpick__meta">
                      <span
                        className="fontpick__preview"
                        style={{ fontFamily: `${font.family}, sans-serif` }}
                      >
                        {font.preview_text !== "" ? font.preview_text : font.family}
                      </span>
                      <span className="fontpick__name">
                        {font.family}
                        <span className="fontpick__cat">{font.category}</span>
                      </span>
                    </div>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      disabled={pending}
                      onClick={(): void => choose(font.key)}
                    >
                      {pendingKey === font.key ? "Adding…" : "Add"}
                    </button>
                  </li>
                ))}
              </ul>
              {error !== "" && (
                <p className="tasks__error" role="alert">
                  {error}
                </p>
              )}
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}

/** A simple line glyph per asset kind — an honest placeholder, since stored bytes aren't served. */
function KindGlyph({ kind }: { kind: AssetKind }): JSX.Element {
  switch (kind) {
    case "font":
      return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4 7V5h16v2M9 19h6M12 5v14" />
        </svg>
      );
    case "reference_creative":
      return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M3 15l5-5 4 4 3-3 6 6" />
          <circle cx="8.5" cy="8.5" r="1.5" />
        </svg>
      );
    case "logo":
      return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M8 12l3 3 5-6" />
        </svg>
      );
    case "imagery":
    default:
      return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <circle cx="8" cy="10" r="1.5" />
          <path d="M21 16l-5-4-4 3-3-2-6 5" />
        </svg>
      );
  }
}

const STYLES = `
  .assetlib { display: flex; flex-direction: column; gap: var(--sp-5); }
  .assetlib__head {
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: var(--sp-4); flex-wrap: wrap;
  }
  .assetlib__title { font-size: 20px; font-weight: 700; color: var(--ink); }
  .assetlib__sub { margin-top: 4px; font-size: 13px; color: var(--muted); max-width: 60ch; }
  .assetlib__clientpick { display: flex; flex-direction: column; gap: 4px; }
  .assetlib__field-label { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
  .assetlib__sections { display: flex; flex-direction: column; gap: var(--sp-5); }
  .assetlib__section {
    border: 1px solid var(--line); border-radius: var(--r-md, 12px);
    background: var(--surface); padding: var(--sp-4);
  }
  .assetlib__section-head {
    display: flex; align-items: center; gap: var(--sp-3);
    margin-bottom: var(--sp-3); flex-wrap: wrap;
  }
  .assetlib__section-title { font-size: 15px; font-weight: 650; color: var(--ink); }
  .assetlib__upload { margin-left: auto; position: relative; }
  .assetlib__file {
    position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
    overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
  }
  .assetlib__empty { padding: var(--sp-4); text-align: left; }
  .assetlib__grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: var(--sp-3);
  }
  .assetcard {
    display: flex; gap: var(--sp-3);
    border: 1px solid var(--line); border-radius: var(--r-sm, 10px);
    background: var(--surface-2); padding: var(--sp-3);
  }
  .assetcard__tile {
    flex-shrink: 0; width: 48px; height: 48px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    background: var(--surface); color: var(--muted); border: 1px solid var(--line);
  }
  .assetcard__tile--img { position: relative; overflow: hidden; padding: 0; }
  .assetcard__thumb {
    position: absolute; inset: 0; width: 100%; height: 100%;
    object-fit: cover; transition: opacity 120ms ease;
  }
  .assetcard__tile--logo.assetcard__tile--img .assetcard__thumb { object-fit: contain; padding: 4px; }
  .fontpick { margin-bottom: var(--sp-3); display: flex; flex-direction: column; gap: var(--sp-2); }
  .fontpick__panel {
    border: 1px solid var(--line); border-radius: var(--r-sm, 10px);
    background: var(--surface-2); padding: var(--sp-3);
  }
  .fontpick__note { font-size: 12px; color: var(--muted); }
  .fontpick__list { display: flex; flex-direction: column; gap: var(--sp-2); }
  .fontpick__item {
    display: flex; align-items: center; gap: var(--sp-3);
    padding: var(--sp-2) 0; border-bottom: 1px solid var(--line);
  }
  .fontpick__item:last-child { border-bottom: 0; }
  .fontpick__meta { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
  .fontpick__preview {
    font-size: 16px; color: var(--ink);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .fontpick__name { font-size: 11px; color: var(--muted); display: flex; gap: 6px; align-items: center; }
  .fontpick__cat {
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em;
    padding: 1px 6px; border-radius: 999px; background: var(--surface); border: 1px solid var(--line);
  }
  .assetcard__body { display: flex; flex-direction: column; gap: 4px; min-width: 0; flex: 1; }
  .assetcard__name {
    font-size: 13px; font-weight: 600; color: var(--ink);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .assetcard__meta { font-size: 11px; color: var(--muted); }
  .assetcard__badge {
    align-self: flex-start; font-size: 11px; font-weight: 600;
    padding: 2px 8px; border-radius: 999px; margin-top: 2px;
  }
  .assetcard__badge--ok { background: var(--accent-soft); color: var(--accent); }
  .assetcard__badge--pending { background: var(--surface); color: var(--muted); border: 1px solid var(--line); }
  .assetcard__study { margin-top: 4px; display: flex; flex-direction: column; gap: 4px; }
  .assetcard__palette { display: flex; gap: 3px; }
  .assetcard__swatch { width: 16px; height: 16px; border-radius: 4px; border: 1px solid var(--line); }
  .assetcard__mood { font-size: 11px; color: var(--muted); font-style: italic; }
  .assetcard__actions { display: flex; gap: var(--sp-2); flex-wrap: wrap; margin-top: 6px; }
  .assetcard__err { font-size: 12px; color: var(--danger, #cf3a3f); margin-top: 4px; }
  .assetcard__notice { font-size: 12px; color: var(--accent); margin-top: 4px; }
`;
