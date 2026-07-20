import type { JSX } from "react";
import Link from "next/link";
import type { ApiBrief, ApiBriefStatus } from "@/lib/api";
import { ChevronRightIcon } from "./icons";

interface BriefsListViewProps {
  briefs: ApiBrief[];
  /** client_id -> display name, resolved from /clients. */
  clientNames: Record<string, string>;
}

const STATUS_LABEL: Record<ApiBriefStatus, string> = {
  draft: "Draft",
  in_review: "In review",
  signed_off: "Signed off",
  frozen: "Signed off",
};

/** Frozen/signed-off share one "locked" pill tone; draft/in-review are open. */
function statusClass(status: ApiBriefStatus): string {
  return status === "frozen" || status === "signed_off" ? "brief-pill--locked" : "brief-pill--open";
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function firstLine(text: string | null, max = 120): string | null {
  if (text === null) return null;
  const trimmed = text.trim();
  if (trimmed === "") return null;
  return trimmed.length > max ? `${trimmed.slice(0, max)}…` : trimmed;
}

export function BriefsListView({ briefs, clientNames }: BriefsListViewProps): JSX.Element {
  // Newest first — the brief someone is most likely working on sits at the top.
  const sorted = [...briefs].sort((a, b) => b.created_at.localeCompare(a.created_at));

  return (
    <div className="brief">
      <header className="brief-head">
        <div>
          <h1 className="brief-head__title">Brand briefs</h1>
          <p className="brief-head__sub">
            The versioned, sign-off-able brief for each brand. Editing a signed-off brief mints a new
            version — nothing is overwritten.
          </p>
        </div>
      </header>

      {sorted.length === 0 ? (
        <div className="empty-state">
          <p className="empty-state__title">No briefs yet</p>
          <p className="empty-state__body">
            A brief is drafted when a client is onboarded. Once one exists it shows up here to edit
            and sign off.
          </p>
        </div>
      ) : (
        <ul className="brief-cards">
          {sorted.map((brief) => {
            const name = clientNames[brief.client_id] ?? "Untitled client";
            const preview = firstLine(brief.sections.snapshot);
            return (
              <li key={brief.id}>
                <Link href={`/briefs/${brief.id}`} className="brief-card">
                  <div className="brief-card__main">
                    <div className="brief-card__titlerow">
                      <span className="brief-card__name">{name}</span>
                      <span className="brief-card__ver">v{brief.version}</span>
                    </div>
                    <p className="brief-card__preview">
                      {preview ?? "No snapshot yet — open to fill in the brief."}
                    </p>
                  </div>
                  <div className="brief-card__meta">
                    <span className={`brief-pill ${statusClass(brief.status)}`}>
                      {STATUS_LABEL[brief.status]}
                    </span>
                    <span className="brief-card__date">
                      {brief.frozen_at !== null
                        ? `Signed off ${formatDate(brief.frozen_at)}`
                        : `Updated ${formatDate(brief.created_at)}`}
                    </span>
                  </div>
                  <ChevronRightIcon />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
