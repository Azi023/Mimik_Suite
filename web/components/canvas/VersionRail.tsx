"use client";

import { useState, type JSX } from "react";
import Image from "next/image";
import type { ApiCreativeVersionInfo } from "@/lib/api";

export interface VersionRailProps {
  /** Persisted history from GET /creatives/{id}/versions (any order — rendered newest-first). */
  versions: ApiCreativeVersionInfo[];
  /** Fallback while an empty history is loading; populated histories derive their own head. */
  currentId: string;
  onRevert: (toCreativeId: string, ordinal: number) => void;
  /** True while a revert is in flight — all revert buttons disable together. */
  reverting: boolean;
}

const THUMB_SIZE = 44;

interface OrderedVersion {
  version: ApiCreativeVersionInfo;
  ordinal: number;
}

const REVERT_NOTE_PATTERN = /^revert to v(\d+)$/i;
const INTERNAL_LAYER_NOTE_PATTERN = /^layer ops:\s*\d+$/i;

function compareStableStrings(left: string, right: string): number {
  if (left < right) return -1;
  if (left > right) return 1;
  return 0;
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  // Explicit locale — implicit (environment) locale is hydration-unsafe on SSR'd markup.
  return d.toLocaleString("en-GB", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Ascending form of the API's canonical head rule: version, created_at, creative_id. */
export function compareCreativeVersions(
  left: ApiCreativeVersionInfo,
  right: ApiCreativeVersionInfo,
): number {
  const byVersion = left.version - right.version;
  if (byVersion !== 0) return byVersion;

  // API datetimes are ISO-8601 strings in one normalized representation. Comparing
  // the full value preserves database microseconds that JavaScript Date would truncate.
  const byTimestamp = compareStableStrings(left.created_at, right.created_at);
  if (byTimestamp !== 0) return byTimestamp;

  return compareStableStrings(left.creative_id, right.creative_id);
}

/** Highest canonical version, including deterministic handling for legacy version ties. */
export function canonicalCreativeHead(
  versions: readonly ApiCreativeVersionInfo[],
): ApiCreativeVersionInfo | null {
  if (versions.length === 0) return null;
  return versions.reduce((head, candidate) =>
    compareCreativeVersions(candidate, head) > 0 ? candidate : head
  );
}

function orderVersions(
  versions: readonly ApiCreativeVersionInfo[],
): OrderedVersion[] {
  const oldestFirst = [...versions].sort(compareCreativeVersions);
  return oldestFirst
    .map((version, index) => ({ version, ordinal: index + 1 }))
    .reverse();
}

function actorLabel(version: ApiCreativeVersionInfo): string | null {
  if (version.created_by === null) return null;
  const name = version.created_by.name?.trim();
  if (name !== undefined && name !== "") return name;
  const role = version.created_by.role.trim().replaceAll("_", " ");
  return role === "" ? null : role.charAt(0).toUpperCase() + role.slice(1);
}

function publicOrdinalByStoredVersion(
  ordered: readonly OrderedVersion[],
): ReadonlyMap<number, number> {
  const ordinals = new Map<number, number>();
  for (const { version, ordinal } of ordered) {
    if (!ordinals.has(version.version)) ordinals.set(version.version, ordinal);
  }
  return ordinals;
}

function actionSummary(
  version: ApiCreativeVersionInfo,
  ordinal: number,
  publicOrdinals: ReadonlyMap<number, number>,
): string {
  if (ordinal === 1) return "Original";
  const revertMatch = version.note?.trim().match(REVERT_NOTE_PATTERN);
  if (revertMatch !== null && revertMatch !== undefined) {
    const storedTarget = Number.parseInt(revertMatch[1] ?? "", 10);
    const publicTarget = publicOrdinals.get(storedTarget);
    return publicTarget === undefined
      ? "Reverted"
      : `Reverted to v${publicTarget}`;
  }
  return "Edited";
}

function versionNote(version: ApiCreativeVersionInfo): string | null {
  const note = version.note?.trim();
  if (
    note === undefined ||
    note === "" ||
    REVERT_NOTE_PATTERN.test(note) ||
    INTERNAL_LAYER_NOTE_PATTERN.test(note)
  ) {
    return null;
  }
  return note;
}

/** Preview thumb via the same-origin proxy (cookies stay httpOnly, bearer added server-side). */
function VersionThumb({
  version,
  ordinal,
}: {
  version: ApiCreativeVersionInfo;
  ordinal: number;
}): JSX.Element {
  const [failed, setFailed] = useState(false);
  return (
    <span
      aria-hidden="true"
      style={{
        flex: `0 0 ${THUMB_SIZE}px`,
        width: THUMB_SIZE,
        height: THUMB_SIZE,
        borderRadius: "var(--r-sm)",
        overflow: "hidden",
        background: "var(--surface-2)",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "11px",
        fontWeight: 600,
        color: "var(--muted)",
      }}
    >
      {failed ? (
        <>v{ordinal}</>
      ) : (
        <Image
          src={`/api/creatives/${encodeURIComponent(version.creative_id)}/preview`}
          alt=""
          width={THUMB_SIZE}
          height={THUMB_SIZE}
          unoptimized
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
          onError={(): void => setFailed(true)}
        />
      )}
    </span>
  );
}

/**
 * The persisted version history rail (B-09): newest-first rows with a stable
 * public ordinal, timestamp, action, author, and preview thumb — with Revert
 * on every version that isn't the current head.
 */
export function VersionRail({
  versions,
  currentId,
  onRevert,
  reverting,
}: VersionRailProps): JSX.Element {
  const ordered = orderVersions(versions);
  const publicOrdinals = publicOrdinalByStoredVersion(ordered);
  const canonicalCurrentId = canonicalCreativeHead(versions)?.creative_id ?? currentId;

  return (
    <div className="creview__section" aria-label="Version history">
      <h2 className="creview__label">
        Versions <span className="creview__count">{ordered.length}</span>
      </h2>

      {ordered.length === 0 ? (
        <p className="creview__thread-empty">
          No versions recorded yet. Apply a change to mint the first one.
        </p>
      ) : (
        <ul className="creview__thread">
          {ordered.map(({ version, ordinal }) => {
            const isCurrent = version.creative_id === canonicalCurrentId;
            const author = actorLabel(version);
            const action = actionSummary(version, ordinal, publicOrdinals);
            const note = versionNote(version);
            const when = formatWhen(version.created_at);
            return (
              <li key={version.creative_id} className="creview__event">
                <VersionThumb version={version} ordinal={ordinal} />
                <span
                  style={{
                    flex: "1 1 auto",
                    minWidth: 0,
                    display: "inline-flex",
                    flexDirection: "column",
                    gap: "2px",
                  }}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
                    <span className="creview__event-who">
                      v{ordinal}
                      {when !== "" && (
                        <>
                          {" "}·{" "}
                          <time dateTime={version.created_at}>{when}</time>
                        </>
                      )}
                    </span>
                    {isCurrent && (
                      <span className="creview__vchip-latest">current</span>
                    )}
                  </span>
                  <span className="creview__event-text">
                    {action}
                    {author !== null && <> · {author}</>}
                  </span>
                  {note !== null && (
                    <span className="creview__event-note">{note}</span>
                  )}
                </span>
                {!isCurrent && (
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    disabled={reverting}
                    onClick={(): void => onRevert(version.creative_id, ordinal)}
                  >
                    Revert
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
