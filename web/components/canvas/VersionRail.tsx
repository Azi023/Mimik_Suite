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

/** Preview thumb via the same-origin proxy (cookies stay httpOnly, bearer added server-side). */
function VersionThumb({ version }: { version: ApiCreativeVersionInfo }): JSX.Element {
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
        <>v{version.version}</>
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
 * oldest-to-newest ordinal, timestamp, stored version metadata, note, author,
 * and a preview thumb — with Revert on every version that isn't the current head.
 */
export function VersionRail({
  versions,
  currentId,
  onRevert,
  reverting,
}: VersionRailProps): JSX.Element {
  const ordered = orderVersions(versions);
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
            return (
              <li key={version.creative_id} className="creview__event">
                <VersionThumb version={version} />
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
                      Version {ordinal} ·{" "}
                      <time dateTime={version.created_at}>
                        {formatWhen(version.created_at)}
                      </time>
                    </span>
                    {isCurrent && (
                      <span className="creview__vchip-latest">current</span>
                    )}
                  </span>
                  <span className="creview__event-text">
                    Stored v{version.version}
                    {version.created_by !== null && (
                      <> · {version.created_by.name ?? version.created_by.role}</>
                    )}
                  </span>
                  {version.note !== null && version.note !== "" && (
                    <span className="creview__event-note">{version.note}</span>
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
