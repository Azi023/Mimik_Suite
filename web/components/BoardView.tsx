"use client";

import { useMemo, useState, type JSX } from "react";
import { type CreativeDoc, type Job, jobToReviewDoc, type Pillar } from "@/lib/mock";
import { Board } from "./Board";
import { ALL_PILLARS, PillarChips } from "./PillarChips";
import { ReviewPanel } from "./ReviewPanel";

interface BoardViewProps {
  pillars: Pillar[];
  jobs: Job[];
  /**
   * The server-resolved creative for the default-selected job — the only doc that
   * carries real API ids (jobId / creativeDocId), so its Approve / Request-change
   * actually hit the backend. Clicking any other card falls back to a display-only
   * preview doc (honest offline note on submit).
   */
  reviewDoc: CreativeDoc;
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
  // *label* (`Job.pillar`), while chips carry an id + label. Match on label so this
  // works whether ids come from the API (`data.ts` toPillarChips) or the mock set.
  const activePillarLabel = useMemo<string | null>(() => {
    if (activePillarId === ALL_PILLARS) return null;
    return pillars.find((pillar) => pillar.id === activePillarId)?.label ?? null;
  }, [activePillarId, pillars]);

  const visibleJobs = useMemo<Job[]>(() => {
    if (activePillarLabel === null) return jobs;
    return jobs.filter((job) => job.pillar === activePillarLabel);
  }, [jobs, activePillarLabel]);

  // Which doc the panel shows. Default (nothing clicked): the server doc with real
  // ids. When a card is clicked: reuse the server doc if it backs that same job
  // (keeps the real ids → live submits), else a display-only preview of the job.
  const activeDoc = useMemo<CreativeDoc>(() => {
    if (selectedJobId === null) return reviewDoc;
    if (reviewDoc.jobId === selectedJobId) return reviewDoc;
    const job = jobs.find((candidate) => candidate.id === selectedJobId);
    return job !== undefined ? jobToReviewDoc(job) : reviewDoc;
  }, [selectedJobId, reviewDoc, jobs]);

  function handleSelectJob(job: Job): void {
    setSelectedJobId(job.id);
  }

  return (
    <div className="board-view">
      <div className="board-view__main">
        <section className="board-view__filters" aria-label="Content pillars">
          <h2 className="visually-hidden">Content pillars</h2>
          <PillarChips
            pillars={pillars}
            activePillarId={activePillarId}
            onSelect={setActivePillarId}
          />
        </section>

        <section aria-label="This week's approvals">
          <h2 className="visually-hidden">This week · approvals</h2>
          <Board
            jobs={visibleJobs}
            selectedJobId={selectedJobId}
            onSelectJob={handleSelectJob}
          />
        </section>
      </div>

      {/* Keying on the doc identity remounts the panel when the selection changes,
          so its internal submit / pin-composer state resets cleanly per creative. */}
      <ReviewPanel key={activeDoc.creativeDocId ?? activeDoc.id} doc={activeDoc} />
    </div>
  );
}
