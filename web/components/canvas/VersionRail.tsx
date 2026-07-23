"use client";

import { useState, type JSX } from "react";
import Image from "next/image";
import type { ApiCreativeVersionInfo } from "@/lib/api";

export interface VersionRailProps {
  /** Persisted history from GET /creatives/{id}/versions (any order — rendered newest-first). */
  versions: ApiCreativeVersionInfo[];
  /** The creative currently on the stage — its row is tagged and not revertable. */
  currentId: string;
  onRevert: (toCreativeId: string) => void;
  /** True while a revert is in flight — all revert buttons disable together. */
  reverting: boolean;
}

const THUMB_SIZE = 44;

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
 * The persisted version history rail (B-09): newest-first rows of version number,
 * note, author role, timestamp, and a preview thumb — with a Revert action on
 * every version that isn't the current head. Replaces ReviewPanel v1's in-memory
 * `history[]` with the server's GET /creatives/{id}/versions record.
 */
export function VersionRail({
  versions,
  currentId,
  onRevert,
  reverting,
}: VersionRailProps): JSX.Element {
  const ordered = [...versions].sort((a, b) => b.version - a.version);

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
          {ordered.map((version) => {
            const isCurrent = version.creative_id === currentId;
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
                    <span className="creview__event-who">v{version.version}</span>
                    {isCurrent && (
                      <span className="creview__vchip-latest">current</span>
                    )}
                    {version.created_by !== null && (
                      <span className="creview__event-text">
                        {version.created_by.name ?? version.created_by.role}
                      </span>
                    )}
                  </span>
                  {version.note !== null && version.note !== "" && (
                    <span className="creview__event-note">{version.note}</span>
                  )}
                  <time className="creview__event-time">{formatWhen(version.created_at)}</time>
                </span>
                {!isCurrent && (
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    disabled={reverting}
                    onClick={(): void => onRevert(version.creative_id)}
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
