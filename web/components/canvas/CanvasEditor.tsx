"use client";

import { useCallback, useEffect, useRef, useState, type JSX } from "react";
import Link from "next/link";
import type { ApiColorRole, ApiVersionHistory } from "@/lib/api";
import {
  reviseCreativeCanvasAction,
  revertCreativeAction,
  type CanvasEditActionResult,
} from "@/app/actions";
import {
  CanvasStage,
  type CanvasStageHandle,
  type CanvasStageSnapshot,
} from "./CanvasStage";
import { canonicalCreativeHead, VersionRail } from "./VersionRail";
import {
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
  /** The creative's OWN client (versions → job.client_id) — NOT the sidebar's global
   *  selection. Null only when the client record couldn't be loaded (display-only, so
   *  a failed fetch never blocks editing). */
  clientId: string | null;
  clientName: string | null;
  /** The creative's own brand (job.brand_id) — always resolvable, the page gates on it. */
  brandName: string;
  /** True when the sidebar's globally-selected client differs from the creative's client;
   *  surfaces a calm "whose creative is this" chip so context is never ambiguous. */
  clientMismatch: boolean;
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



const EMPTY_STAGE_SNAPSHOT: CanvasStageSnapshot = {
  history: { ops: [], redo: [] },
  canUndo: false,
  canRedo: false,
};

interface PendingRevert {
  creativeId: string;
  ordinal: number;
}

type HeadSyncState = "loading" | "ready" | "error";

function hasCanvasRevisionChanges(revision: ApiCanvasRevision): boolean {
  return (
    revision.layer_ops.length > 0 ||
    (revision.text_edits !== undefined &&
      Object.keys(revision.text_edits).length > 0) ||
    (revision.params !== undefined && Object.keys(revision.params).length > 0)
  );
}

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
  clientId,
  clientName,
  brandName,
  clientMismatch,
}: CanvasEditorProps): JSX.Element {
  const initialHeadId =
    canonicalCreativeHead(initialVersions.versions)?.creative_id ?? creativeId;
  const stageControlsRef = useRef<CanvasStageHandle>(null);
  const [currentId, setCurrentId] = useState<string>(initialHeadId);
  const [currentSvg, setCurrentSvg] = useState<string>(svg);
  const [versions, setVersions] = useState<ApiVersionHistory>(initialVersions);
  const [pendingRevision, setPendingRevision] = useState<ApiCanvasRevision | null>(null);
  const [stageSnapshot, setStageSnapshot] =
    useState<CanvasStageSnapshot>(EMPTY_STAGE_SNAPSHOT);
  const [pendingRevert, setPendingRevert] = useState<PendingRevert | null>(null);
  /** Bumped to re-key the stage — resets its local transforms after Apply/Discard/Revert. */
  const [stageKey, setStageKey] = useState(0);
  const [revising, setRevising] = useState(false);
  const [reverting, setReverting] = useState(false);
  const [headSyncState, setHeadSyncState] = useState<HeadSyncState>(
    initialHeadId === creativeId ? "ready" : "loading",
  );
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");

  const [askText, setAskText] = useState("");

  useEffect(() => {
    if (initialHeadId === creativeId) return;

    const controller = new AbortController();
    async function loadCanonicalHead(): Promise<void> {
      try {
        const response = await fetch(
          `/api/creatives/${encodeURIComponent(initialHeadId)}/svg`,
          {
            cache: "no-store",
            signal: controller.signal,
          },
        );
        if (!response.ok) {
          throw new Error(`Current creative SVG returned ${String(response.status)}`);
        }
        const headSvg = await response.text();
        if (controller.signal.aborted) return;
        setCurrentSvg(headSvg);
        setStageKey((key) => key + 1);
        setHeadSyncState("ready");
      } catch (loadError: unknown) {
        if (controller.signal.aborted) return;
        console.warn(`[mimik-web] current creative head failed to load (${String(loadError)})`);
        setError("The current creative version could not be loaded. Reload and try again.");
        setHeadSyncState("error");
      }
    }

    void loadCanonicalHead();
    return (): void => controller.abort();
  }, [creativeId, initialHeadId]);

  // The stage emits its FULL accumulated state each time — replace ours, keep the ask.
  const handleStageChange = useCallback((revision: ApiCanvasRevision): void => {
    setPendingRevision((previous) => {
      const ask = previous?.ask;
      if (!hasCanvasRevisionChanges(revision)) {
        return ask === undefined ? null : { layer_ops: [], ask };
      }
      return ask === undefined ? revision : { ...revision, ask };
    });
  }, []);

  const handleStageHistoryChange = useCallback(
    (snapshot: CanvasStageSnapshot): void => {
      setStageSnapshot(snapshot);
      if (snapshot.history.ops.length === 0) setPendingRevert(null);
    },
    [],
  );

  const busy = revising || reverting || headSyncState !== "ready";
  const pendingAsk = pendingRevision?.ask ?? null;
  const hasPendingChanges =
    stageSnapshot.history.ops.length > 0 || pendingAsk !== null;
  const canAddAsk = askText.trim() !== "" && !busy;

  function addAsk(layerId: CanvasLayerId): void {
    if (!canAddAsk) return;
    const ask: ApiRegionAsk = {
      zone: ASK_ZONE[layerId],
      bbox: layerBBox(currentSvg, layerId),
      instruction: askText.trim(),
    };
    setPendingRevision((prev) => ({ layer_ops: [], ...(prev ?? {}), ask }));
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
    setStageSnapshot(EMPTY_STAGE_SNAPSHOT);
    setPendingRevert(null);
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
    setStageSnapshot(EMPTY_STAGE_SNAPSHOT);
    setPendingRevert(null);
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

  function requestRevert(toCreativeId: string, ordinal: number): void {
    if (busy) return;
    if (stageSnapshot.history.ops.length > 0) {
      setPendingRevert({ creativeId: toCreativeId, ordinal });
      return;
    }
    void revert(toCreativeId);
  }

  return (
    <div className="creview">
      <CanvasStage
        key={stageKey}
        svg={currentSvg}
        brandColors={brandColors}
        onChange={handleStageChange}
        onHistoryChange={handleStageHistoryChange}
        controlsRef={stageControlsRef}
        askText={askText}
        onAskTextChange={setAskText}
        onAddAsk={addAsk}
        busy={busy}
      />

      <aside className="creview__rail" aria-label="Canvas editor">
        <header className="creview__rail-head">
          <div className="creview__rail-heading">
            <h1 className="creview__title">Canvas editor</h1>
            {/* The creative's OWN client + brand — sourced from the creative's job,
                never from the sidebar's global selection. */}
            <p className="creview__context">
              {clientName !== null && clientId !== null ? (
                <>
                  <Link
                    href={`/clients/${encodeURIComponent(clientId)}/edit`}
                    className="creview__context-client"
                  >
                    {clientName}
                  </Link>
                  {brandName !== clientName && <span> · {brandName}</span>}
                </>
              ) : (
                brandName
              )}
            </p>
          </div>
          <span
            className={`creview__status${!busy && !hasPendingChanges ? " creview__status--done" : ""}`}
          >
            <span className="creview__status-dot" aria-hidden="true" />
            {busy
              ? revising
                ? "Revising…"
                : reverting
                  ? "Reverting…"
                  : headSyncState === "loading"
                    ? "Loading current…"
                    : "Current unavailable"
              : hasPendingChanges
                ? "Pending changes"
                : "Up to date"}
          </span>
        </header>

        {clientMismatch && clientName !== null && (
          <p className="creview__context-note" role="note">
            <span className="creview__context-note-dot" aria-hidden="true" />
            You&rsquo;re viewing {clientName}&rsquo;s creative
          </p>
        )}

        {banner !== "" && (
          <p className="creview__banner" role="status">
            {banner}
          </p>
        )}

        <div className="creview__section">
          <div className="creview__pending-head">
            <h2 className="creview__label">
              Pending
              <span className="creview__count">{stageSnapshot.history.ops.length}</span>
            </h2>
            <div className="creview__history-actions" aria-label="Edit history">
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                title="Undo · ⌘/Ctrl+Z"
                disabled={busy || !stageSnapshot.canUndo}
                onClick={(): void => stageControlsRef.current?.undo()}
              >
                Undo
              </button>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                title="Redo · ⌘/Ctrl+Shift+Z"
                disabled={busy || !stageSnapshot.canRedo}
                onClick={(): void => stageControlsRef.current?.redo()}
              >
                Redo
              </button>
            </div>
          </div>
          {stageSnapshot.history.ops.length === 0 ? (
            <p className="creview__thread-empty">No pending changes</p>
          ) : (
            <ol className="creview__op-list" aria-label="Pending canvas changes">
              {stageSnapshot.history.ops.map((operation) => (
                <li key={operation.id} className="creview__op">
                  <span className="creview__op-copy">
                    <span className="creview__op-label">{operation.label}</span>
                    <span className="creview__op-layer">
                      {LAYER_LABEL[operation.layer]}
                    </span>
                  </span>
                  <button
                    type="button"
                    className="creview__op-remove"
                    aria-label={`Remove ${operation.label}`}
                    title="Remove change"
                    disabled={busy}
                    onClick={(): void =>
                      stageControlsRef.current?.removeOp(operation.id)
                    }
                  >
                    ×
                  </button>
                </li>
              ))}
            </ol>
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
              disabled={!hasPendingChanges || busy}
              onClick={discard}
            >
              Discard
            </button>
            <button
              type="button"
              className="btn btn--primary btn--sm"
              disabled={!hasPendingChanges || pendingRevision === null || busy}
              onClick={(): void => void apply()}
            >
              {revising ? "Applying…" : "Apply"}
            </button>
          </div>
        </div>



        {error !== "" && (
          <p className="creview__error" role="alert">
            {error} <span className="creview__error-note">Your pending changes are kept.</span>
          </p>
        )}

        {pendingRevert !== null && (
          <div
            className="creview__revert-confirm"
            role="alertdialog"
            aria-labelledby="canvas-revert-confirm-title"
          >
            <p id="canvas-revert-confirm-title">
              You have {stageSnapshot.history.ops.length} unsaved{" "}
              {stageSnapshot.history.ops.length === 1 ? "change" : "changes"}.
              Revert discards{" "}
              {stageSnapshot.history.ops.length === 1 ? "it" : "them"} and restores
              v{pendingRevert.ordinal}. Continue?
            </p>
            <div className="creview__composer-actions">
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                disabled={busy}
                onClick={(): void => setPendingRevert(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn--danger btn--sm"
                disabled={busy}
                onClick={(): void => {
                  const target = pendingRevert.creativeId;
                  setPendingRevert(null);
                  void revert(target);
                }}
              >
                Continue
              </button>
            </div>
          </div>
        )}

        <VersionRail
          versions={versions.versions}
          currentId={currentId}
          onRevert={requestRevert}
          reverting={busy}
        />
      </aside>
    </div>
  );
}
