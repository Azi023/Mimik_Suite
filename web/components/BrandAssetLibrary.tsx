"use client";

import { useRef, useState, useTransition, type JSX } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ApiBrandAsset, AssetKind } from "@/lib/api";
import type { AssetActionResult } from "@/app/assets/actions";

type UploadAction = (
  brandId: string,
  kind: string,
  formData: FormData,
) => Promise<AssetActionResult>;
type AssetAction = (assetId: string) => Promise<AssetActionResult>;

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
 * (approve; knockout for logos; ingest for references). There is no public byte URL for stored
 * assets, so cards show a kind tile + filename/mime rather than a rendered thumbnail; ingested
 * references additionally show the observed palette and mood (real study data, never invented).
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
}

function AssetSection({
  spec,
  brandId,
  assets,
  uploadAction,
  approveAction,
  knockoutAction,
  ingestAction,
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
      <div className={`assetcard__tile assetcard__tile--${asset.kind}`} aria-hidden="true">
        <KindGlyph kind={asset.kind} />
      </div>

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
