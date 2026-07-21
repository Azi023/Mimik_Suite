"use client";

import { useMemo, useRef, useState, type JSX } from "react";
import { useRouter } from "next/navigation";
import {
  type ApiApproval,
  type ApiBrand,
  type ApiCreativeDoc,
  type ApiDelivery,
  type ApiJob,
  type ApiJobStatus,
  type ApiRevisionZone,
  type ApprovalActionKind,
  type ApprovalTarget,
  type CreateCreativeBody,
} from "@/lib/api";
import { useLocalDraft, useUnsavedGuard } from "@/lib/hooks";
import { submitReviewAction } from "@/app/jobs/[id]/review/actions";
import { submitMagicApprovalAction } from "@/app/review/[token]/actions";

/* ---------------------------------------------------------------------------
   Contract-bound constants.
--------------------------------------------------------------------------- */

/** The RevisionZone values the composer exposes (mimik_contracts.enums.RevisionZone). */
const ZONES: ReadonlyArray<{ zone: ApiRevisionZone; label: string }> = [
  { zone: "headline", label: "Headline" },
  { zone: "subhead", label: "Subhead" },
  { zone: "cta", label: "CTA" },
  { zone: "logo", label: "Logo" },
  { zone: "imagery", label: "Imagery" },
  { zone: "background", label: "Background" },
  { zone: "layout", label: "Layout" },
  { zone: "other", label: "Other" },
];

const ZONE_LABEL: ReadonlyMap<ApiRevisionZone, string> = new Map(
  ZONES.map(({ zone, label }) => [zone, label]),
);

/**
 * The reject-reason taxonomy — a hard "no" carrying a categorical reason that feeds the
 * per-client preference profile (the learning loop). NOTE: the backend has no distinct
 * `reject` action; a reject is a `request_change` carrying a `reason_tag` (and no pins), so
 * "Request changes" (pin-pointed) and "Reject" (categorical) are two faces of one action.
 */
const REJECT_REASONS: ReadonlyArray<{ tag: string; label: string }> = [
  { tag: "off_brief", label: "Off the brief" },
  { tag: "tone_off", label: "Tone is off" },
  { tag: "wrong_color", label: "Wrong colours" },
  { tag: "logo_small", label: "Logo / branding" },
  { tag: "imagery_weak", label: "Imagery is weak" },
  { tag: "other", label: "Other" },
];

/** API caps (mirror ApprovalRequest): at most 10 targets; instruction/note capped at 500 chars. */
const MAX_PINS = 10;
const MAX_TEXT = 500;

/** Aspect ratios keyed by format (mimik_contracts.formats.PRESETS width/height). */
const FORMAT_ASPECT: ReadonlyMap<string, number> = new Map([
  ["ig_post", 1080 / 1080],
  ["ig_story", 1080 / 1920],
  ["fb_post", 1200 / 630],
  ["poster_a", 1414 / 2000],
  ["carousel", 1080 / 1350],
]);

/** Job states in which the creative is decided — no further decision is offered. */
const TERMINAL_STATES: ReadonlySet<ApiJobStatus> = new Set<ApiJobStatus>([
  "approved",
  "delivered",
  "archived",
]);

/* ---------------------------------------------------------------------------
   Local types + helpers.
--------------------------------------------------------------------------- */

/** One queued, pin-pointed change ask. `x`/`y` are canvas-normalized (0..1) UI context; only
 *  `zone` + `instruction` persist to the contract (RevisionTarget carries no coordinates). */
interface Pin {
  key: number;
  x: number;
  y: number;
  zone: ApiRevisionZone;
  instruction: string;
}

/** A pin being placed but not yet committed (canvas click → composer). */
interface PendingPin {
  x: number;
  y: number;
  zone: ApiRevisionZone;
}

type SubmitState = "idle" | "sending" | "done" | "error";

/** Guess the most likely zone from where on the canvas the reviewer clicked. */
function suggestZone(y: number): ApiRevisionZone {
  if (y < 0.22) return "headline";
  if (y < 0.4) return "subhead";
  if (y > 0.8) return "cta";
  return "imagery";
}

/** Relative luminance (WCAG-ish) of a #rrggbb colour → pick readable ink over a ground. */
function isLightHex(hex: string): boolean {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (m === null) return false;
  const n = parseInt(m[1], 16);
  const r = (n >> 16) & 0xff;
  const g = (n >> 8) & 0xff;
  const b = n & 0xff;
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.6;
}

/** 9-anchor logo placement → flexbox alignment. */
function logoAnchorStyle(placement: string): { justifyContent: string; alignItems: string } {
  const [v, h] = ((): [string, string] => {
    const parts = placement.split("_");
    if (parts.length === 1) return ["center", "center"]; // "center"
    return [parts[0], parts[1]];
  })();
  const map: Record<string, string> = {
    top: "flex-start",
    middle: "center",
    center: "center",
    bottom: "flex-end",
    left: "flex-start",
    right: "flex-end",
  };
  return { alignItems: map[v] ?? "flex-start", justifyContent: map[h] ?? "flex-start" };
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

/* ---------------------------------------------------------------------------
   Component.
--------------------------------------------------------------------------- */

interface CreativeReviewProps {
  job: ApiJob;
  brand: ApiBrand;
  clientName: string | null;
  /** A job's creative versions, oldest first (GET /jobs/{id}/creatives). */
  creatives: ApiCreativeDoc[];
  /** The append-only audit trail (comments + decisions), oldest first. */
  approvals: ApiApproval[];
  deliveries: ApiDelivery[];
  /** When set, this is the no-login magic-link flow: decisions post via the magic grant (token in
   *  the body) instead of the session cookie. The client acts bounded to this one job. */
  magicToken?: string;
  /** Team-only: mint a shareable no-login client review link. When provided, a "Share with client"
   *  control appears (internal review). Bound to the job id server-side by the caller. */
  mintLink?: () => Promise<{ ok: boolean; token?: string; error?: string }>;
  /** Team-only: save edited copy as a NEW creative version. When provided, an "Edit copy" mode
   *  appears (internal review). Bound to the job id server-side by the caller. */
  editCopyAction?: (body: CreateCreativeBody) => Promise<{ ok: boolean; error?: string }>;
}

/**
 * The sellable core: an image-first creative review (reference: Filestage). The left canvas shows
 * a job's latest CreativeDoc composed from its manifest + brand tokens (there is no server-rendered
 * PNG until a paid image backend lands — constraint #7 — so this is an honest client-side proxy).
 * Click the canvas to drop a change pin; the right rail carries the version selector, the activity
 * thread, a comment box, and the decision bar: Approve / Request changes (pinned) / Reject (reason).
 *
 * Unsaved pins + comment text are mirrored to localStorage (useLocalDraft) and guarded on unload
 * (useUnsavedGuard) so a dropped connection or power-cut never loses a reviewer's notes.
 */
export function CreativeReview({
  job,
  brand,
  clientName,
  creatives,
  approvals,
  deliveries,
  magicToken,
  mintLink,
  editCopyAction,
}: CreativeReviewProps): JSX.Element {
  const router = useRouter();
  const canvasRef = useRef<HTMLDivElement>(null);
  const [shareState, setShareState] = useState<"idle" | "working" | "copied" | "error">("idle");
  const [editing, setEditing] = useState(false);
  const [editHeadline, setEditHeadline] = useState("");
  const [editSubhead, setEditSubhead] = useState("");
  const [editCta, setEditCta] = useState("");
  const [savingCopy, setSavingCopy] = useState(false);

  const latestIdx = creatives.length - 1;
  const [versionIdx, setVersionIdx] = useState(latestIdx);
  const doc = creatives[versionIdx];

  // Drafts are keyed by job so each job's unsaved work is independent and recoverable.
  const [pins, setPins, clearPins] = useLocalDraft<Pin[]>(`review.${job.id}.pins`, []);
  const [comment, setComment, clearComment] = useLocalDraft<string>(`review.${job.id}.comment`, "");
  const [pinKey, setPinKey] = useState(0);

  const [pending, setPending] = useState<PendingPin | null>(null);
  const [pendingText, setPendingText] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState<string>(REJECT_REASONS[0].tag);

  const [state, setState] = useState<SubmitState>("idle");
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");

  const isTerminal = TERMINAL_STATES.has(job.status);
  const busy = state === "sending";
  const dirty = pins.length > 0 || comment.trim() !== "" || pendingText.trim() !== "";
  useUnsavedGuard(dirty && !isTerminal);

  const aspect = FORMAT_ASPECT.get(job.format_key) ?? 1;
  const copy = doc?.manifest.copy_block ?? null;

  // Canvas ground: an image layer's artifact_ref if it's a real URL, else the primary brand colour.
  const groundColor = brand.tokens.colors[0]?.hex ?? "#e9eaee";
  const imageLayer = doc?.manifest.layers.find(
    (l) => l.artifact_ref !== null && /^https?:\/\//i.test(l.artifact_ref),
  );
  const onLight = imageLayer === undefined && isLightHex(groundColor);
  const textInk = onLight ? "#14161c" : "#ffffff";
  const layout = brand.tokens.layout;
  const headingFont = brand.tokens.typography.heading_font ?? undefined;

  const activity = useMemo(
    () =>
      [
        ...approvals.map((a) => ({ kind: "approval" as const, at: a.created_at, approval: a })),
        ...deliveries.map((d) => ({ kind: "delivery" as const, at: d.created_at, delivery: d })),
      ].sort((x, y) => x.at.localeCompare(y.at)),
    [approvals, deliveries],
  );

  /* ---- canvas pin placement ---- */

  function onCanvasClick(event: React.MouseEvent<HTMLDivElement>): void {
    if (isTerminal || busy || canvasRef.current === null) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    setPending({ x, y, zone: suggestZone(y) });
    setPendingText("");
  }

  function commitPin(): void {
    if (pending === null || pendingText.trim() === "" || pins.length >= MAX_PINS) return;
    setPins((cur) => [
      ...cur,
      { key: pinKey, x: pending.x, y: pending.y, zone: pending.zone, instruction: pendingText.trim() },
    ]);
    setPinKey((k) => k + 1);
    setPending(null);
    setPendingText("");
  }

  function removePin(key: number): void {
    setPins((cur) => cur.filter((p) => p.key !== key));
  }

  /* ---- submit ---- */

  async function submit(
    action: ApprovalActionKind,
    extra: { targets?: ApprovalTarget[]; reason_tag?: string; note?: string },
  ): Promise<boolean> {
    if (doc === undefined) return false;
    setState("sending");
    setError("");
    const common = {
      action,
      creative_doc_id: doc.id,
      ...(extra.note !== undefined && extra.note !== "" ? { note: extra.note } : {}),
      ...(extra.reason_tag !== undefined ? { reason_tag: extra.reason_tag } : {}),
      ...(extra.targets !== undefined ? { targets: extra.targets } : {}),
    };
    // No-login magic flow posts via the grant (token in body); the in-app flow via the session cookie.
    const result =
      magicToken !== undefined
        ? await submitMagicApprovalAction({ token: magicToken, ...common })
        : await submitReviewAction({ job_id: job.id, ...common });
    if (result.ok) {
      setState("done");
      return true;
    }
    setState("error");
    setError(result.error ?? "Something went wrong.");
    return false;
  }

  async function approve(): Promise<void> {
    if (busy || isTerminal) return;
    const note = comment.trim();
    if (await submit("approve", { note })) {
      clearComment();
      setBanner("Approved — archiving to Drive.");
      router.refresh();
    }
  }

  async function requestChanges(): Promise<void> {
    if (busy || isTerminal || pins.length === 0) return;
    const targets: ApprovalTarget[] = pins.map((p) => ({ zone: p.zone, instruction: p.instruction }));
    const note = comment.trim();
    if (await submit("request_change", { targets, note })) {
      clearPins();
      clearComment();
      setPins([]);
      setComment("");
      setBanner(`Sent ${targets.length} change${targets.length === 1 ? "" : "s"} to the team.`);
      router.refresh();
    }
  }

  async function reject(): Promise<void> {
    if (busy || isTerminal) return;
    const note = comment.trim();
    if (await submit("request_change", { reason_tag: reason, note })) {
      clearComment();
      setComment("");
      setRejecting(false);
      setBanner("Rejected — the team has the reason.");
      router.refresh();
    }
  }

  async function sendComment(): Promise<void> {
    if (busy) return;
    const note = comment.trim();
    if (note === "") return;
    if (await submit("comment", { note })) {
      clearComment();
      setComment("");
      setBanner("Comment posted.");
      router.refresh();
    }
  }

  async function shareLink(): Promise<void> {
    if (mintLink === undefined || shareState === "working") return;
    setShareState("working");
    const result = await mintLink();
    if (result.ok && result.token !== undefined) {
      const url = `${window.location.origin}/review/${result.token}`;
      try {
        await navigator.clipboard.writeText(url);
        setShareState("copied");
      } catch {
        // Clipboard blocked (permissions / insecure context) — still surface the link to copy manually.
        setBanner(url);
        setShareState("copied");
      }
    } else {
      setShareState("error");
      setError(result.error ?? "Could not create a share link.");
    }
  }

  function startEdit(): void {
    setEditHeadline(copy?.headline ?? "");
    setEditSubhead(copy?.subhead ?? "");
    setEditCta(copy?.cta ?? "");
    setEditing(true);
    setBanner("");
    setError("");
  }

  async function saveCopy(): Promise<void> {
    if (editCopyAction === undefined || doc === undefined || savingCopy) return;
    const templateKey = doc.manifest.template_key;
    if (templateKey === null) {
      setError("This creative has no template — its copy can't be versioned here.");
      return;
    }
    if (editHeadline.trim() === "") {
      setError("The headline can't be empty.");
      return;
    }
    setSavingCopy(true);
    setError("");
    const result = await editCopyAction({
      template_key: templateKey,
      copy_block: {
        headline: editHeadline.trim(),
        subhead: editSubhead.trim() === "" ? null : editSubhead.trim(),
        cta: editCta.trim() === "" ? null : editCta.trim(),
        language: copy?.language ?? "en",
        status: "edited",
      },
      image_artifact: imageLayer?.artifact_ref ?? null,
    });
    setSavingCopy(false);
    if (result.ok) {
      setEditing(false);
      setBanner("Saved as a new version.");
      router.refresh();
    } else {
      setError(result.error ?? "Could not save the new version.");
    }
  }

  /* ---- empty state: no creative yet ---- */

  if (doc === undefined) {
    return (
      <div className="creview creview--empty">
        <div className="empty-state">
          <p className="empty-state__title">No creative to review yet</p>
          <p className="empty-state__body">
            This job hasn&apos;t generated a creative. Once the engine produces one, it lands here for review.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="creview">
      {/* ---- LEFT: image-first canvas ---- */}
      <div className="creview__stage">
        <div className="creview__stage-head">
          <span className="creview__meta">{job.format_key}</span>
          {clientName !== null && <span className="creview__meta creview__meta--muted">{clientName}</span>}
          <span className="creview__hint">{isTerminal ? "Read-only" : "Click the creative to pin a change"}</span>
        </div>

        <div className="creview__canvas-wrap">
          <div
            ref={canvasRef}
            className={`creview__canvas creview__canvas--${aspect < 1 ? "portrait" : "landscape"}${
              isTerminal ? " creview__canvas--locked" : ""
            }`}
            style={{
              aspectRatio: String(aspect),
              background: imageLayer !== undefined ? undefined : groundColor,
              backgroundImage: imageLayer !== undefined ? `url(${imageLayer.artifact_ref})` : undefined,
              backgroundSize: "cover",
              backgroundPosition: "center",
            }}
            onClick={onCanvasClick}
            role="img"
            aria-label={`Creative preview, version ${doc.version}`}
          >
            {imageLayer !== undefined && <div className="creview__scrim" aria-hidden="true" />}

            {/* logo chip at the brand's anchor */}
            {layout !== undefined && (
              <div className="creview__logo-layer" style={logoAnchorStyle(layout.logo_placement)}>
                <span className="creview__logo" style={{ color: textInk, borderColor: textInk }}>
                  {brand.name}
                </span>
              </div>
            )}

            {/* copy block — live-previews the edit values while editing */}
            <div className="creview__copy">
              {copy === null && !editing ? (
                <span className="creview__copy-empty" style={{ color: textInk }}>
                  No copy on this version yet
                </span>
              ) : (
                <>
                  <span className="creview__headline" style={{ color: textInk, fontFamily: headingFont }}>
                    {editing ? editHeadline || "Headline" : copy?.headline}
                  </span>
                  {(editing ? editSubhead : copy?.subhead ?? "") !== "" && (
                    <span className="creview__subhead" style={{ color: textInk }}>
                      {editing ? editSubhead : copy?.subhead}
                    </span>
                  )}
                  {(editing ? editCta : copy?.cta ?? "") !== "" && (
                    <span className="creview__cta">{editing ? editCta : copy?.cta}</span>
                  )}
                </>
              )}
            </div>

            {/* committed change pins */}
            {pins.map((p, i) => (
              <span
                key={p.key}
                className="creview__pin"
                style={{ left: `${p.x * 100}%`, top: `${p.y * 100}%` }}
                title={`${ZONE_LABEL.get(p.zone) ?? p.zone}: ${p.instruction}`}
              >
                {i + 1}
              </span>
            ))}

            {/* the pin currently being placed */}
            {pending !== null && (
              <span
                className="creview__pin creview__pin--pending"
                style={{ left: `${pending.x * 100}%`, top: `${pending.y * 100}%` }}
                aria-hidden="true"
              >
                +
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ---- RIGHT: rail ---- */}
      <aside className="creview__rail" aria-label="Review">
        <header className="creview__rail-head">
          <h1 className="creview__title">{job.title}</h1>
          <ReviewStatus status={job.status} />
        </header>

        {mintLink !== undefined && (
          <button
            type="button"
            className="btn btn--secondary btn--sm creview__share"
            disabled={shareState === "working"}
            onClick={(): void => void shareLink()}
          >
            {shareState === "working"
              ? "Creating link…"
              : shareState === "copied"
                ? "✓ Client link copied"
                : "Share with client ↗"}
          </button>
        )}

        {editCopyAction !== undefined && !isTerminal && !editing && (
          <button
            type="button"
            className="btn btn--ghost btn--sm creview__share"
            onClick={startEdit}
          >
            Edit copy → new version
          </button>
        )}

        {editing && (
          <div className="creview__composer">
            <h2 className="creview__label">Edit copy</h2>
            <input
              className="creview__input"
              value={editHeadline}
              maxLength={MAX_TEXT}
              placeholder="Headline"
              aria-label="Headline"
              onChange={(e): void => setEditHeadline(e.target.value)}
            />
            <input
              className="creview__input"
              value={editSubhead}
              maxLength={MAX_TEXT}
              placeholder="Subhead (optional)"
              aria-label="Subhead"
              onChange={(e): void => setEditSubhead(e.target.value)}
            />
            <input
              className="creview__input"
              value={editCta}
              maxLength={MAX_TEXT}
              placeholder="CTA (optional)"
              aria-label="Call to action"
              onChange={(e): void => setEditCta(e.target.value)}
            />
            <div className="creview__composer-actions">
              <button
                type="button"
                className="btn btn--secondary btn--sm"
                onClick={(): void => setEditing(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn--primary btn--sm"
                disabled={savingCopy || editHeadline.trim() === ""}
                onClick={(): void => void saveCopy()}
              >
                {savingCopy ? "Saving…" : "Save as new version"}
              </button>
            </div>
          </div>
        )}

        {/* version selector */}
        {creatives.length > 1 && (
          <div className="creview__versions" role="group" aria-label="Version">
            {creatives.map((c, i) => (
              <button
                key={c.id}
                type="button"
                className={`creview__vchip${i === versionIdx ? " creview__vchip--active" : ""}`}
                aria-pressed={i === versionIdx}
                onClick={(): void => setVersionIdx(i)}
              >
                v{c.version}
                {i === latestIdx && <span className="creview__vchip-latest">latest</span>}
              </button>
            ))}
          </div>
        )}

        {banner !== "" && (
          <p className="creview__banner" role="status">
            {banner}
          </p>
        )}

        {/* pin composer — opens when a canvas pin is being placed */}
        {pending !== null && (
          <div className="creview__composer">
            <h2 className="creview__label">Pin a change</h2>
            <div className="creview__zones" role="group" aria-label="Which part">
              {ZONES.map(({ zone, label }) => (
                <button
                  key={zone}
                  type="button"
                  className={`zone-chip${pending.zone === zone ? " zone-chip--active" : ""}`}
                  aria-pressed={pending.zone === zone}
                  onClick={(): void => setPending({ ...pending, zone })}
                >
                  {label}
                </button>
              ))}
            </div>
            <textarea
              className="creview__input"
              value={pendingText}
              maxLength={MAX_TEXT}
              placeholder="What should change here?"
              aria-label="Change instruction"
              rows={2}
              onChange={(e): void => setPendingText(e.target.value)}
            />
            <div className="creview__composer-actions">
              <button
                type="button"
                className="btn btn--secondary btn--sm"
                onClick={(): void => {
                  setPending(null);
                  setPendingText("");
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn--primary btn--sm"
                disabled={pendingText.trim() === "" || pins.length >= MAX_PINS}
                onClick={commitPin}
              >
                Add pin
              </button>
            </div>
          </div>
        )}

        {/* queued change pins */}
        {pins.length > 0 && (
          <div className="creview__section">
            <h2 className="creview__label">
              Change requests <span className="creview__count">{pins.length}</span>
            </h2>
            <ul className="creview__pinlist">
              {pins.map((p, i) => (
                <li key={p.key} className="creview__pincard">
                  <span className="creview__pincard-num">{i + 1}</span>
                  <span className="creview__pincard-zone">{ZONE_LABEL.get(p.zone) ?? p.zone}</span>
                  <span className="creview__pincard-text">{p.instruction}</span>
                  <button
                    type="button"
                    className="creview__pincard-x"
                    aria-label="Remove pin"
                    onClick={(): void => removePin(p.key)}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* activity thread */}
        <div className="creview__section creview__thread-wrap">
          <h2 className="creview__label">Activity</h2>
          {activity.length === 0 ? (
            <p className="creview__thread-empty">No comments or decisions yet. You&apos;re first.</p>
          ) : (
            <ul className="creview__thread">
              {activity.map((item) =>
                item.kind === "approval" ? (
                  <ApprovalItem key={item.approval.id} approval={item.approval} />
                ) : (
                  <li key={item.delivery.id} className="creview__event">
                    <span className="creview__event-badge creview__event-badge--done">Delivered</span>
                    <span className="creview__event-text">Archived to Drive</span>
                    <time className="creview__event-time">{formatWhen(item.at)}</time>
                  </li>
                ),
              )}
            </ul>
          )}
        </div>

        {/* comment box */}
        {!isTerminal && (
          <div className="creview__section">
            <textarea
              className="creview__input"
              value={comment}
              maxLength={MAX_TEXT}
              placeholder="Add a comment or a note for your decision…"
              aria-label="Comment"
              rows={2}
              onChange={(e): void => setComment(e.target.value)}
            />
            <div className="creview__composer-actions">
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                disabled={comment.trim() === "" || busy}
                onClick={(): void => void sendComment()}
              >
                Comment
              </button>
            </div>
          </div>
        )}

        {error !== "" && (
          <p className="creview__error" role="alert">
            {error} <span className="creview__error-note">Your notes are kept.</span>
          </p>
        )}

        {/* decision bar */}
        {isTerminal ? (
          <div className="creview__decided">This creative is {job.status.replace("_", " ")}.</div>
        ) : rejecting ? (
          <div className="creview__reject">
            <h2 className="creview__label">Why are you rejecting this?</h2>
            <div className="creview__zones" role="group" aria-label="Reject reason">
              {REJECT_REASONS.map(({ tag, label }) => (
                <button
                  key={tag}
                  type="button"
                  className={`zone-chip${reason === tag ? " zone-chip--active" : ""}`}
                  aria-pressed={reason === tag}
                  onClick={(): void => setReason(tag)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="creview__composer-actions">
              <button
                type="button"
                className="btn btn--secondary btn--sm"
                onClick={(): void => setRejecting(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn--danger btn--sm"
                disabled={busy}
                onClick={(): void => void reject()}
              >
                Confirm reject
              </button>
            </div>
          </div>
        ) : (
          <div className="creview__decide">
            <button
              type="button"
              className="btn btn--primary"
              disabled={busy}
              onClick={(): void => void approve()}
            >
              {busy ? "Working…" : "Approve"}
            </button>
            <button
              type="button"
              className="btn btn--secondary"
              disabled={busy || pins.length === 0}
              title={pins.length === 0 ? "Pin a change on the creative first" : undefined}
              onClick={(): void => void requestChanges()}
            >
              Request changes{pins.length > 0 ? ` (${pins.length})` : ""}
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              disabled={busy}
              onClick={(): void => setRejecting(true)}
            >
              Reject
            </button>
          </div>
        )}
      </aside>
    </div>
  );
}

/* ---------------------------------------------------------------------------
   Sub-views.
--------------------------------------------------------------------------- */

function ReviewStatus({ status }: { status: ApiJobStatus }): JSX.Element {
  const tone =
    status === "approved" || status === "delivered" || status === "archived"
      ? "done"
      : status === "blocked"
        ? "risk"
        : "progress";
  return (
    <span className={`creview__status creview__status--${tone}`}>
      <span className="creview__status-dot" aria-hidden="true" />
      {status.replace("_", " ")}
    </span>
  );
}

function ApprovalItem({ approval }: { approval: ApiApproval }): JSX.Element {
  const who = approval.actor.name ?? approval.actor.role;
  const verb =
    approval.action === "approve"
      ? "approved"
      : approval.action === "request_change"
        ? "requested changes"
        : approval.action === "comment"
          ? "commented"
          : approval.action;
  return (
    <li className="creview__event">
      <span className="creview__event-who">{who}</span>
      <span className={`creview__event-badge creview__event-badge--${approval.action}`}>{verb}</span>
      {approval.note !== null && approval.note !== "" && (
        <span className="creview__event-note">{approval.note}</span>
      )}
      {approval.targets.length > 0 && (
        <ul className="creview__event-targets">
          {approval.targets.map((t, i) => (
            <li key={i} className="creview__event-target">
              <span className="creview__event-target-zone">{ZONE_LABEL.get(t.zone) ?? t.zone}</span>
              {t.instruction}
            </li>
          ))}
        </ul>
      )}
      <time className="creview__event-time">{formatWhen(approval.created_at)}</time>
    </li>
  );
}
