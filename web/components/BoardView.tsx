"use client";

import { useMemo, useState, type JSX } from "react";
import type { CreativeDoc, Job, Pillar } from "@/lib/view-models";
import { Board } from "./Board";
import { ALL_PILLARS, PillarChips } from "./PillarChips";
import { ReviewPanel } from "./ReviewPanel";

interface BoardViewProps {
  pillars: Pillar[];
  jobs: Job[];
  /**
   * The server-resolved creative for the default-selected job. Null means the API
   * returned no creative or the request failed.
   */
  reviewDoc: CreativeDoc | null;
}

/**
 * Interactive shell over the board + review panel. Owns the two pieces of client
 * state the server component can't: which pillar filters the board, and which job
 * is open in the review panel. Data still flows in from the server component as
 * props (see app/page.tsx) — this only adds selection + filtering on top.
 */
export function BoardView({ pillars, jobs, reviewDoc }: BoardViewProps): JSX.Element {
  const [activePillarId, setActivePillarId] = useState<string>(ALL_PILLARS);
  // null = nothing clicked yet → the review panel shows the server-resolved default doc.
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  // Pillars filter by the label shown on the card: jobs carry a denormalized pillar
  // label (`Job.pillar`), while chips carry an id + label.
  const activePillarLabel = useMemo<string | null>(() => {
    if (activePillarId === ALL_PILLARS) return null;
    return pillars.find((pillar) => pillar.id === activePillarId)?.label ?? null;
  }, [activePillarId, pillars]);

  const visibleJobs = useMemo<Job[]>(() => {
    if (activePillarLabel === null) return jobs;
    return jobs.filter((job) => job.pillar === activePillarLabel);
  }, [jobs, activePillarLabel]);

  // Never synthesize a creative for a selected job. If the server-resolved creative
  // does not belong to it, the review area renders its real empty state.
  const activeDoc = useMemo<CreativeDoc | null>(() => {
    if (selectedJobId === null) return reviewDoc;
    return reviewDoc?.jobId === selectedJobId ? reviewDoc : null;
  }, [selectedJobId, reviewDoc]);

  function handleSelectJob(job: Job): void {
    setSelectedJobId(job.id);
  }

  return (
    <div className="board-view">
      <div className="board-view__main">
        {pillars.length > 0 && (
          <section className="board-view__filters" aria-label="Content pillars">
            <h2 className="visually-hidden">Content pillars</h2>
            <PillarChips
              pillars={pillars}
              activePillarId={activePillarId}
              onSelect={setActivePillarId}
            />
          </section>
        )}

        <section aria-label="This week's approvals">
          <h2 className="visually-hidden">This week · approvals</h2>
          {jobs.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state__title">No jobs yet</p>
              <p className="empty-state__body">Jobs will appear here when they are created.</p>
            </div>
          ) : (
            <Board
              jobs={visibleJobs}
              selectedJobId={selectedJobId}
              onSelectJob={handleSelectJob}
            />
          )}
        </section>
      </div>

      {activeDoc !== null ? (
        <ReviewPanel key={activeDoc.creativeDocId} doc={activeDoc} />
      ) : (
        <aside className="review-panel" aria-label="Creative review">
          <header className="review-panel__head">
            <h2 className="review-panel__title">Creative review</h2>
          </header>
          <div className="empty-state">
            <p className="empty-state__title">No creative to review yet</p>
            <p className="empty-state__body">
              A creative will appear here when one is ready for review.
            </p>
          </div>
        </aside>
      )}
    </div>
  );
}
