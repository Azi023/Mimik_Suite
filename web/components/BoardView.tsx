"use client";

import { useMemo, useState, useTransition, type FormEvent, type JSX } from "react";
import { useRouter } from "next/navigation";
import { generateCreativeAction } from "@/app/actions";
import type { ApiBoardResponse } from "@/lib/api";
import type { CreativeDoc, Job, Pillar } from "@/lib/view-models";
import { Board } from "./Board";
import { ALL_PILLARS, PillarChips } from "./PillarChips";
import { ReviewPanel } from "./ReviewPanel";

interface BoardViewProps {
  pillars: Pillar[];
  jobs: Job[];
  /**
   * The live GET /ops/board response, fetched server-side (app/page.tsx). Null means
   * the API is unconfigured or the request failed — the board renders its empty state.
   */
  board: ApiBoardResponse | null;
  /**
   * The server-resolved creative for the default-selected job. Null means the API
   * returned no creative or the request failed.
   */
  reviewDoc: CreativeDoc | null;
  clients: ReadonlyArray<{ id: string; name: string }>;
  initialClientId: string | null;
}

/**
 * Interactive shell over the board + review panel. Owns the two pieces of client
 * state the server component can't: which pillar filters the board, and which job
 * is open in the review panel. Data still flows in from the server component as
 * props (see app/page.tsx) — this only adds selection + filtering on top.
 */
export function BoardView({
  pillars,
  jobs,
  board,
  reviewDoc,
  clients,
  initialClientId,
}: BoardViewProps): JSX.Element {
  const router = useRouter();
  const [activePillarId, setActivePillarId] = useState<string>(ALL_PILLARS);
  // null = nothing clicked yet → the review panel shows the server-resolved default doc.
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedClientId, setSelectedClientId] = useState(
    initialClientId ?? clients[0]?.id ?? "",
  );
  const [topic, setTopic] = useState("");
  const [generatedDoc, setGeneratedDoc] = useState<CreativeDoc | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [isGenerating, startGenerating] = useTransition();

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

  // Empty is decided by the server board, not the flattened job list — real empty
  // columns still render as a (truthful) empty pipeline when any card exists.
  const boardHasCards = useMemo<boolean>(() => {
    if (board === null) return false;
    return Object.values(board.columns).some((cards) => cards.length > 0);
  }, [board]);

  // Never synthesize a creative for a selected job. If the server-resolved creative
  // does not belong to it, the review area renders its real empty state.
  const activeDoc = useMemo<CreativeDoc | null>(() => {
    if (selectedJobId === null) return generatedDoc ?? reviewDoc;
    if (generatedDoc?.jobId === selectedJobId) return generatedDoc;
    return reviewDoc?.jobId === selectedJobId ? reviewDoc : null;
  }, [generatedDoc, selectedJobId, reviewDoc]);

  function handleSelectJob(job: Job): void {
    setSelectedJobId(job.id);
  }

  function handleGenerate(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setGenerateError(null);
    startGenerating(async (): Promise<void> => {
      const result = await generateCreativeAction(
        selectedClientId,
        topic,
        activePillarLabel ?? undefined,
      );
      if (!result.ok) {
        setGenerateError(result.error);
        return;
      }
      setGeneratedDoc(result.doc);
      setSelectedJobId(result.doc.jobId);
      setTopic("");
      router.refresh();
    });
  }

  return (
    <div className="board-view">
      <div className="board-view__main">
        <form className="generate-control" onSubmit={handleGenerate}>
          <label className="visually-hidden" htmlFor="generate-client">
            Client
          </label>
          <select
            id="generate-client"
            className="generate-control__select"
            value={selectedClientId}
            disabled={clients.length === 0 || isGenerating}
            onChange={(event): void => setSelectedClientId(event.target.value)}
          >
            {clients.length === 0 ? (
              <option value="">No clients yet</option>
            ) : (
              clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.name}
                </option>
              ))
            )}
          </select>
          <label className="visually-hidden" htmlFor="generate-topic">
            Creative topic
          </label>
          <input
            id="generate-topic"
            className="generate-control__input"
            value={topic}
            maxLength={500}
            placeholder="Topic, offer, or idea"
            disabled={isGenerating}
            onChange={(event): void => setTopic(event.target.value)}
          />
          <button
            type="submit"
            className="btn btn--primary"
            disabled={selectedClientId === "" || topic.trim() === "" || isGenerating}
          >
            {isGenerating ? "Generating…" : "Generate"}
          </button>
          {generateError !== null && (
            <p className="generate-control__error" role="status">
              {generateError}
            </p>
          )}
        </form>

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
          {board !== null && boardHasCards ? (
            <Board
              board={board}
              jobs={visibleJobs}
              selectedJobId={selectedJobId}
              onSelectJob={handleSelectJob}
            />
          ) : (
            <div className="empty-state">
              <p className="empty-state__title">No jobs yet</p>
              <p className="empty-state__body">Jobs will appear here when they are created.</p>
            </div>
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
