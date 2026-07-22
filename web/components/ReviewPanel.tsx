"use client";

import { useLayoutEffect, useRef, useState, type JSX } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  ApiError,
  type ApiRevisionZone,
  type ApprovalActionKind,
  type ApprovalTarget,
  isApiConfigured,
  submitApproval,
  reviseCreative,
  type ReviseCreativeBody,
} from "@/lib/api";
import type { CreativeDoc } from "@/lib/view-models";
import { toReviewDoc } from "@/lib/data";
import { slideInPanel, staggerFadeUp } from "@/lib/motion";
import { LayerStrip } from "./LayerStrip";
import { StatusPill } from "./StatusPill";

interface ReviewPanelProps {
  doc: CreativeDoc;
}

/** One queued pin-pointed change ask. `key` is UI-only (list identity/removal). */
interface Pin {
  key: number;
  zone: ApiRevisionZone;
  instruction: string;
}

/** Panel-local submit lifecycle. Terminal states flip the header chip. */
type SubmitState =
  | "idle"
  | "sending"
  | "approved"
  | "changes_requested"
  | "offline"
  | "error";

/** The zone chip row — the contract's RevisionZone values the composer exposes. */
const ZONES: ReadonlyArray<{ zone: ApiRevisionZone; label: string }> = [
  { zone: "headline", label: "Headline" },
  { zone: "subhead", label: "Subhead" },
  { zone: "cta", label: "CTA" },
  { zone: "logo", label: "Logo" },
  { zone: "imagery", label: "Imagery" },
  { zone: "background", label: "Background" },
  { zone: "layout", label: "Layout" },
];

const ZONE_LABEL: ReadonlyMap<ApiRevisionZone, string> = new Map(
  ZONES.map(({ zone, label }) => [zone, label]),
);

/** API cap on targets per request (mirrors ApprovalRequest.targets max_length). */
const MAX_PINS = 10;
/** Contract cap on RevisionTarget.instruction length. */
const MAX_INSTRUCTION_CHARS = 500;

/**
 * Right detail panel (reference: the chat/detail pane) — white, rounded-left,
 * slides in from the right on first paint. Holds the in-review creative:
 * gradient thumbnail, layer strip, editor note, and the review actions.
 *
 * "Request change" reveals a compact pin composer: pick a zone, say what should
 * change, queue up to 10 pins, send them as one `request_change` approval with
 * pin-pointed RevisionTargets. If API configuration disappears after render,
 * submits show a quiet inline offline note and keep the pins.
 */
export function ReviewPanel({ doc }: ReviewPanelProps): JSX.Element {
  const panelRef = useRef<HTMLElement>(null);
  const composerRef = useRef<HTMLDivElement>(null);

  const [composing, setComposing] = useState(false);
  const [zone, setZone] = useState<ApiRevisionZone | null>(null);
  const [instruction, setInstruction] = useState("");
  const [note, setNote] = useState("");
  const [pins, setPins] = useState<Pin[]>([]);
  const [pinKey, setPinKey] = useState(0);
  const [state, setState] = useState<SubmitState>("idle");
  const [submitError, setSubmitError] = useState<string>("");
  const [previewFailed, setPreviewFailed] = useState(false);

  const [activeDoc, setActiveDoc] = useState<CreativeDoc>(doc);
  const [history, setHistory] = useState<CreativeDoc[]>([doc]);
  
  // Editor state
  const [editHeadline, setEditHeadline] = useState("");
  const [editSub, setEditSub] = useState("");
  const [editCta, setEditCta] = useState("");
  const [aiInstruction, setAiInstruction] = useState("");
  const [revising, setRevising] = useState(false);
  
  // Keep activeDoc in sync if prop changes
  useLayoutEffect(() => {
    setActiveDoc(doc);
    setHistory([doc]);
  }, [doc]);

  async function handleRevise(body: ReviseCreativeBody) {
    if (!isApiConfigured()) {
      setState("offline");
      return;
    }
    setRevising(true);
    try {
      const result = await reviseCreative(activeDoc.creativeDocId, body);
      const newDoc = toReviewDoc(result.creative);
      setHistory(prev => [...prev, newDoc]);
      setActiveDoc(newDoc);
      // Clear inputs
      setEditHeadline("");
      setEditSub("");
      setEditCta("");
      setAiInstruction("");
    } catch (e) {
      console.error(e);
      setSubmitError("Revise failed");
      setState("error");
    } finally {
      setRevising(false);
    }
  }


  useLayoutEffect(() => {
    const tween = slideInPanel(panelRef.current);
    return (): void => {
      tween?.kill();
    };
  }, []);

  // Composer reveal — same fade/rise vocabulary as the board cards, single target.
  // No-ops under prefers-reduced-motion (the helper guards it).
  useLayoutEffect(() => {
    if (!composing || composerRef.current === null) return undefined;
    const tween = staggerFadeUp([composerRef.current], { duration: 0.25, y: 10 });
    return (): void => {
      tween?.kill();
    };
  }, [composing]);

  const busy = state === "sending";
  const settled = state === "approved" || state === "changes_requested";
  const canAddPin =
    zone !== null && instruction.trim().length > 0 && pins.length < MAX_PINS && !busy;

  function toggleComposer(): void {
    setComposing((open) => !open);
    if (state === "offline" || state === "error") setState("idle");
  }

  function addPin(): void {
    if (!canAddPin || zone === null) return;
    setPins((current) => [...current, { key: pinKey, zone, instruction: instruction.trim() }]);
    setPinKey((key) => key + 1);
    setInstruction("");
  }

  function removePin(key: number): void {
    setPins((current) => current.filter((pin) => pin.key !== key));
  }

  async function submit(action: ApprovalActionKind, targets?: ApprovalTarget[]): Promise<void> {
    if (!isApiConfigured()) {
      setState("offline");
      return;
    }
    setState("sending");
    try {
      const trimmedNote = note.trim();
      await submitApproval({
        job_id: doc.jobId,
        creative_doc_id: doc.creativeDocId,
        action,
        ...(trimmedNote !== "" ? { note: trimmedNote } : {}),
        ...(targets !== undefined ? { targets } : {}),
      });
      if (action === "approve") {
        setState("approved");
      } else {
        setState("changes_requested");
        setPins([]);
        setNote("");
      }
      setComposing(false);
    } catch (error) {
      // A real attempted-and-failed request is NOT "offline" — conflating them would
      // send an operator chasing connectivity when the server said 409/401. Pins are kept.
      console.warn(`[mimik-web] approval submit failed — keeping pins (${String(error)})`);
      setSubmitError(error instanceof ApiError ? `server said ${error.status}` : "network error");
      setState("error");
    }
  }

  function sendPins(): void {
    if (pins.length === 0 || busy) return;
    void submit(
      "request_change",
      pins.map(({ zone: pinZone, instruction: pinInstruction }) => ({
        zone: pinZone,
        instruction: pinInstruction,
      })),
    );
  }

  function approve(): void {
    if (busy) return;
    void submit("approve");
  }

  return (
    <aside className="review-panel" ref={panelRef} aria-label="In review">
      <header className="review-panel__head">
        <h2 className="review-panel__title">Creative review</h2>
        {state === "changes_requested" ? (
          <span className="status-pill status-pill--neutral">
            <span className="status-pill__dot" aria-hidden="true" />
            Changes requested
          </span>
        ) : (
          <StatusPill status={state === "approved" ? "approved" : "in_review"} />
        )}
      </header>

      <div
        className="review-panel__thumb"
      >
        {previewFailed ? (
          <span className="review-panel__thumb-label">{activeDoc.thumbnailLabel}</span>
        ) : (
          <Image
            className="review-panel__thumb-image"
            src={activeDoc.previewUrl}
            alt={`Creative preview: ${activeDoc.thumbnailLabel}`}
            width={1080}
            height={1080}
            sizes="(max-width: 1100px) 100vw, 340px"
            unoptimized
            onError={(): void => setPreviewFailed(true)}
          />
        )}
      </div>

      <div className="review-panel__downloads" aria-label="Creative downloads">
        <a className="btn btn--secondary btn--sm" href={activeDoc.svgUrl} download>
          Download SVG
        </a>
        <a className="btn btn--secondary btn--sm" href={activeDoc.psdUrl} download>
          Download PSD
        </a>
      </div>

      {doc.jobId !== undefined && (
        <Link href={`/jobs/${doc.jobId}/review`} className="review-panel__fullreview">
          Open full review ↗
        </Link>
      )}

      <div className="review-panel__section">
        <h3 className="review-panel__label">Layers</h3>
        <LayerStrip layers={activeDoc.layers} />
        <p className="review-panel__note">{activeDoc.note}</p>
      </div>

      
      <div className="review-panel__section">
        <h3 className="review-panel__label">Editor</h3>
        {revising && <p className="review-panel__note">Revising...</p>}
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
          <input className="pin-composer__input" placeholder="Headline" value={editHeadline} onChange={e => setEditHeadline(e.target.value)} />
          <input className="pin-composer__input" placeholder="Subhead" value={editSub} onChange={e => setEditSub(e.target.value)} />
          <input className="pin-composer__input" placeholder="CTA" value={editCta} onChange={e => setEditCta(e.target.value)} />
          <button className="btn btn--secondary btn--sm" disabled={revising} onClick={() => handleRevise({ edits: { headline: editHeadline || undefined, sub: editSub || undefined, cta: editCta || undefined }})}>Apply text</button>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'row', gap: '8px', marginBottom: '16px' }}>
          <input className="pin-composer__input" placeholder="Describe a change..." value={aiInstruction} onChange={e => setAiInstruction(e.target.value)} />
          <button className="btn btn--primary btn--sm" disabled={revising || !aiInstruction} onClick={() => handleRevise({ instruction: aiInstruction })}>Ask AI</button>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'row', gap: '4px', flexWrap: 'wrap', marginBottom: '16px' }}>
          <button className="btn btn--secondary btn--sm" disabled={revising} onClick={() => handleRevise({ params: { panel_anchor: 'left' }})}>Left</button>
          <button className="btn btn--secondary btn--sm" disabled={revising} onClick={() => handleRevise({ params: { panel_anchor: 'right' }})}>Right</button>
          <button className="btn btn--secondary btn--sm" disabled={revising} onClick={() => handleRevise({ params: { subject_zoom: 0.8 }})}>Smaller</button>
          <button className="btn btn--secondary btn--sm" disabled={revising} onClick={() => handleRevise({ params: { subject_zoom: 1.2 }})}>Larger</button>
          {/* badge_background_luminance = luminance of the ground BEHIND the badge: a LOW value
              makes badge_theme() pick the light/reversed mark, a HIGH value the dark plum mark.
              So a "Light" badge => dark ground (0.0), a "Dark" badge => light ground (1.0). */}
          <button className="btn btn--secondary btn--sm" disabled={revising} onClick={() => handleRevise({ params: { badge_background_luminance: 0.0 }})}>Light</button>
          <button className="btn btn--secondary btn--sm" disabled={revising} onClick={() => handleRevise({ params: { badge_background_luminance: 1.0 }})}>Dark</button>
        </div>
        
        <div style={{ display: 'flex', gap: '8px', overflowX: 'auto' }}>
          {history.map((h, i) => (
             <button key={h.creativeDocId} className={`btn btn--ghost btn--sm ${activeDoc.creativeDocId === h.creativeDocId ? 'active' : ''}`} onClick={() => setActiveDoc(h)}>
               v{i + 1}
             </button>
          ))}
        </div>
      </div>

      {composing && (
        <div className="pin-composer" ref={composerRef}>
          <h3 className="review-panel__label" id="pin-composer-label">
            Request change
          </h3>

          <div className="pin-composer__zones" role="group" aria-labelledby="pin-composer-label">
            {ZONES.map(({ zone: chipZone, label }) => (
              <button
                key={chipZone}
                type="button"
                className={`zone-chip${zone === chipZone ? " zone-chip--active" : ""}`}
                aria-pressed={zone === chipZone}
                onClick={(): void => setZone(chipZone)}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="pin-composer__row">
            <input
              className="pin-composer__input"
              type="text"
              value={instruction}
              maxLength={MAX_INSTRUCTION_CHARS}
              placeholder="What should change here?"
              aria-label="Change instruction"
              onChange={(event): void => setInstruction(event.target.value)}
              onKeyDown={(event): void => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  addPin();
                }
              }}
            />
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              disabled={!canAddPin}
              onClick={addPin}
            >
              Add pin
            </button>
          </div>

          {pins.length > 0 && (
            <ul className="pin-list" aria-label="Queued pins">
              {pins.map((pin) => (
                <li key={pin.key} className="pin-card">
                  <span className="pin-card__zone">{ZONE_LABEL.get(pin.zone) ?? pin.zone}</span>
                  <span className="pin-card__text">{pin.instruction}</span>
                  <button
                    type="button"
                    className="pin-card__remove"
                    aria-label={`Remove ${ZONE_LABEL.get(pin.zone) ?? pin.zone} pin`}
                    onClick={(): void => removePin(pin.key)}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}

          <input
            className="pin-composer__input"
            type="text"
            value={note}
            maxLength={MAX_INSTRUCTION_CHARS}
            placeholder="Note (optional)"
            aria-label="Note for the change request"
            onChange={(event): void => setNote(event.target.value)}
          />

          <button
            type="button"
            className="btn btn--primary"
            disabled={pins.length === 0 || busy || settled}
            onClick={sendPins}
          >
            {busy ? "Sending…" : `Send ${pins.length} pin${pins.length === 1 ? "" : "s"}`}
          </button>
        </div>
      )}

      {state === "offline" && (
        <p className="review-panel__offline" role="status">
          offline — pins not sent
        </p>
      )}

      {state === "error" && (
        <p className="review-panel__offline" role="status">
          submit failed ({submitError}) — pins kept
        </p>
      )}

      <div className="review-panel__actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={busy || settled}
          onClick={approve}
        >
          Approve
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          aria-expanded={composing}
          disabled={busy || settled}
          onClick={toggleComposer}
        >
          Request change
        </button>
        <button type="button" className="btn btn--ghost">
          Reassign
        </button>
      </div>
    </aside>
  );
}
