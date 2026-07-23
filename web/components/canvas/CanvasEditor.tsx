"use client";

import { useCallback, useState, type JSX } from "react";
import type { ApiColorRole, ApiVersionHistory } from "@/lib/api";
import {
  reviseCreativeCanvasAction,
  revertCreativeAction,
  type CanvasEditActionResult,
} from "@/app/actions";
import { CanvasStage } from "./CanvasStage";
import { VersionRail } from "./VersionRail";
import {
  CANVAS_LAYER_IDS,
  type ApiCanvasRevision,
  type ApiRegionAsk,
  type CanvasLayerId,
} from "./canvas-types";

export interface CanvasEditorProps {
  /** The creative currently heading the job (the page's [id] param). */
  creativeId: string;
  /** Its server-rendered SVG master (fetched by the page via fetchCreativeSvg). */
  svg: string;
  brandColors: ApiColorRole[];
  /** Persisted history from GET /creatives/{id}/versions (fetched by the page). */
  initialVersions: ApiVersionHistory;
}

/** RegionAsk zone per marked layer (layer-subhead → "subhead"; the map is total, no "other"). */
const ASK_ZONE: Record<CanvasLayerId, ApiRegionAsk["zone"]> = {
  "layer-background": "background",
  "layer-panel": "panel",
  "layer-headline": "headline",
  "layer-subhead": "subhead",
  "layer-cta": "cta",
  "layer-badge": "badge",
};

const LAYER_LABEL: Record<CanvasLayerId, string> = {
  "layer-background": "Background",
  "layer-panel": "Panel",
  "layer-headline": "Headline",
  "layer-subhead": "Subhead",
  "layer-cta": "CTA",
  "layer-badge": "Badge",
};

/** Contract cap on RegionAsk.instruction. */
const MAX_ASK_CHARS = 500;

/** The marked layer's untransformed `data-bbox` from the SVG master, or null. */
function layerBBox(
  svg: string,
  layerId: CanvasLayerId,
): [number, number, number, number] | null {
  if (typeof DOMParser === "undefined") return null;
  const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
  if (doc.querySelector("parsererror") !== null) return null;
  const raw = doc.querySelector(`g[data-layer="${layerId}"]`)?.getAttribute("data-bbox") ?? null;
  if (raw === null) return null;
  const parts = raw.trim().split(/\s+/).map(Number);
  if (parts.length !== 4 || !parts.every(Number.isFinite)) return null;
  return [parts[0], parts[1], parts[2], parts[3]];
}

/** Drop the ask from a pending revision; collapse to null when nothing else remains. */
function withoutAsk(revision: ApiCanvasRevision): ApiCanvasRevision | null {
  const hasTextEdits =
    revision.text_edits !== undefined && Object.keys(revision.text_edits).length > 0;
  const hasParams = revision.params !== undefined && Object.keys(revision.params).length > 0;
  if (revision.layer_ops.length === 0 && !hasTextEdits && !hasParams) return null;
  const rest: ApiCanvasRevision = { layer_ops: revision.layer_ops };
  if (revision.text_edits !== undefined) rest.text_edits = revision.text_edits;
  if (revision.params !== undefined) rest.params = revision.params;
  return rest;
}

/**
 * B-09: the full-page canvas editor shell around CanvasStage. The stage accumulates
 * ONE local pending ApiCanvasRevision; this shell adds "Mark & tell AI", Apply
 * (POST /creatives/{id}/revise → swap in the new server-rendered head), Discard,
 * and the persisted version rail with Revert. All mutations run through server
 * actions so the httpOnly Supabase bearer never reaches the browser.
 */
export function CanvasEditor({
  creativeId,
  svg,
  brandColors,
  initialVersions,
}: CanvasEditorProps): JSX.Element {
  const [currentId, setCurrentId] = useState<string>(creativeId);
  const [currentSvg, setCurrentSvg] = useState<string>(svg);
  const [versions, setVersions] = useState<ApiVersionHistory>(initialVersions);
  const [pendingRevision, setPendingRevision] = useState<ApiCanvasRevision | null>(null);
  /** Bumped to re-key the stage — resets its local transforms after Apply/Discard/Revert. */
  const [stageKey, setStageKey] = useState(0);
  const [revising, setRevising] = useState(false);
  const [reverting, setReverting] = useState(false);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");

  // "Mark & tell AI" composer.
  const [askLayer, setAskLayer] = useState<CanvasLayerId | null>(null);
  const [askText, setAskText] = useState("");

  // The stage emits its FULL accumulated state each time — replace ours, keep the ask.
  const handleStageChange = useCallback((revision: ApiCanvasRevision): void => {
    setPendingRevision((prev) =>
      prev?.ask !== undefined ? { ...revision, ask: prev.ask } : revision,
    );
  }, []);

  const busy = revising || reverting;
  const pendingLayerOps = pendingRevision === null ? 0 : pendingRevision.layer_ops.length;
  const pendingTextEdits =
    pendingRevision?.text_edits === undefined ? 0 : Object.keys(pendingRevision.text_edits).length;
  const pendingAsk = pendingRevision?.ask ?? null;
  const canAddAsk = askLayer !== null && askText.trim() !== "" && !busy;

  function addAsk(): void {
    if (askLayer === null || !canAddAsk) return;
    const ask: ApiRegionAsk = {
      zone: ASK_ZONE[askLayer],
      bbox: layerBBox(currentSvg, askLayer),
      instruction: askText.trim(),
    };
    setPendingRevision((prev) => ({ layer_ops: [], ...(prev ?? {}), ask }));
    setAskLayer(null);
    setAskText("");
  }

  function removeAsk(): void {
    setPendingRevision((prev) => (prev === null ? null : withoutAsk(prev)));
  }

  function swapInHead(result: Extract<CanvasEditActionResult, { ok: true }>): void {
    setCurrentId(result.creativeId);
    setCurrentSvg(result.svg);
    setVersions(result.versions);
    setPendingRevision(null);
    setAskLayer(null);
    setAskText("");
    // The server render now carries the applied state — reset the stage's local preview.
    setStageKey((key) => key + 1);
  }

  async function apply(): Promise<void> {
    if (pendingRevision === null || busy) return;
    setRevising(true);
    setError("");
    setBanner("");
    // Optimistic feel: the stage's local preview stays mounted and visible while the
    // server re-renders; the returned SVG is swapped in on arrival (sub-second).
    // Deferred stretch (intentionally NOT built): SSE progress for long renders.
    const result = await reviseCreativeCanvasAction(currentId, pendingRevision);
    if (result.ok) {
      swapInHead(result);
      setBanner(`Applied — v${result.version} is on the stage.`);
    } else {
      setError(result.error);
    }
    setRevising(false);
  }

  function discard(): void {
    if (busy) return;
    setPendingRevision(null);
    setAskLayer(null);
    setAskText("");
    setStageKey((key) => key + 1);
    setError("");
    setBanner("");
  }

  async function revert(toCreativeId: string): Promise<void> {
    if (busy) return;
    setReverting(true);
    setError("");
    setBanner("");
    const result = await revertCreativeAction(currentId, toCreativeId);
    if (result.ok) {
      swapInHead(result);
      setBanner(`Reverted — v${result.version} is the new head.`);
    } else {
      setError(result.error);
    }
    setReverting(false);
  }

  const pendingSummary: string[] = [];
  if (pendingLayerOps > 0) {
    pendingSummary.push(`${pendingLayerOps} layer ${pendingLayerOps === 1 ? "op" : "ops"}`);
  }
  if (pendingTextEdits > 0) {
    pendingSummary.push(`${pendingTextEdits} text ${pendingTextEdits === 1 ? "edit" : "edits"}`);
  }
  if (pendingAsk !== null) pendingSummary.push("1 AI ask");

  return (
    <div className="creview">
      <CanvasStage
        key={stageKey}
        svg={currentSvg}
        brandColors={brandColors}
        onChange={handleStageChange}
      />

      <aside className="creview__rail" aria-label="Canvas editor">
        <header className="creview__rail-head">
          <h1 className="creview__title">Canvas editor</h1>
          <span
            className={`creview__status${!busy && pendingRevision === null ? " creview__status--done" : ""}`}
          >
            <span className="creview__status-dot" aria-hidden="true" />
            {busy
              ? revising
                ? "Revising…"
                : "Reverting…"
              : pendingRevision !== null
                ? "Pending changes"
                : "Up to date"}
          </span>
        </header>

        {banner !== "" && (
          <p className="creview__banner" role="status">
            {banner}
          </p>
        )}

        <div className="creview__section">
          <h2 className="creview__label">Pending</h2>
          {pendingRevision === null ? (
            <p className="creview__thread-empty">
              Nothing pending. Drag, scale, recolor, or edit text on the canvas — then Apply.
            </p>
          ) : (
            <p className="creview__event-text">{pendingSummary.join(" · ")}</p>
          )}
          {pendingAsk !== null && (
            <ul className="pin-list" aria-label="Queued AI ask">
              <li className="pin-card">
                <span className="pin-card__zone">{pendingAsk.zone}</span>
                <span className="pin-card__text">{pendingAsk.instruction}</span>
                <button
                  type="button"
                  className="pin-card__remove"
                  aria-label="Remove AI ask"
                  disabled={busy}
                  onClick={removeAsk}
                >
                  ×
                </button>
              </li>
            </ul>
          )}
          <div className="creview__composer-actions">
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              disabled={pendingRevision === null || busy}
              onClick={discard}
            >
              Discard
            </button>
            <button
              type="button"
              className="btn btn--primary btn--sm"
              disabled={pendingRevision === null || busy}
              onClick={(): void => void apply()}
            >
              {revising ? "Applying…" : "Apply"}
            </button>
          </div>
        </div>

        <div className="creview__composer">
          <h2 className="creview__label" id="canvas-ask-label">
            Mark &amp; tell AI
          </h2>
          <div className="creview__zones" role="group" aria-labelledby="canvas-ask-label">
            {CANVAS_LAYER_IDS.map((layerId) => (
              <button
                key={layerId}
                type="button"
                className={`zone-chip${askLayer === layerId ? " zone-chip--active" : ""}`}
                aria-pressed={askLayer === layerId}
                onClick={(): void => setAskLayer(askLayer === layerId ? null : layerId)}
              >
                {LAYER_LABEL[layerId]}
              </button>
            ))}
          </div>
          <textarea
            className="creview__input"
            value={askText}
            maxLength={MAX_ASK_CHARS}
            placeholder="What should the AI change in the marked region?"
            aria-label="AI instruction"
            rows={2}
            onChange={(event): void => setAskText(event.target.value)}
          />
          <div className="creview__composer-actions">
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              disabled={!canAddAsk}
              onClick={addAsk}
            >
              Queue ask
            </button>
          </div>
        </div>

        {error !== "" && (
          <p className="creview__error" role="alert">
            {error} <span className="creview__error-note">Your pending changes are kept.</span>
          </p>
        )}

        <VersionRail
          versions={versions.versions}
          currentId={currentId}
          onRevert={(toCreativeId): void => void revert(toCreativeId)}
          reverting={reverting}
        />
      </aside>
    </div>
  );
}
