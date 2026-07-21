"use client";

import { useLayoutEffect, useRef, type JSX } from "react";
import { boardColumns, type Job } from "@/lib/view-models";
import { animateCount, staggerFadeUp } from "@/lib/motion";
import { JobRow } from "./JobRow";
import { DotsIcon, PlusIcon } from "./icons";

interface BoardProps {
  jobs: Job[];
  /** Id of the job currently open in the review panel (null = none clicked yet). */
  selectedJobId: string | null;
  /** Fired when a card is clicked — selects it into the review panel. */
  onSelectJob: (job: Job) => void;
}

/**
 * The approvals board as a kanban: one column per lifecycle status, headed by
 * a status dot + count (reference: red = at risk, orange = in review,
 * green = approved). Cards stagger-fade-up on first paint; counts tick up.
 * Clicking a card selects it into the review panel.
 */
export function Board({ jobs, selectedJobId, onSelectJob }: BoardProps): JSX.Element {
  const rootRef = useRef<HTMLDivElement>(null);

  // Re-run the entrance + count tick-up whenever the visible set changes (e.g. a
  // pillar filter), so newly-shown cards animate in and counts re-settle.
  useLayoutEffect(() => {
    const root = rootRef.current;
    if (root === null) return;

    const cardTween = staggerFadeUp(root.querySelectorAll("[data-animate='card']"));
    const countTweens = Array.from(
      root.querySelectorAll<HTMLElement>("[data-count]"),
    ).map((el) => animateCount(el, Number(el.dataset.count ?? "0")));

    return (): void => {
      cardTween?.kill();
      countTweens.forEach((tween) => tween?.kill());
    };
  }, [jobs]);

  return (
    <div className="kanban" ref={rootRef}>
      {boardColumns.map((column) => {
        const columnJobs = jobs.filter((job) => job.status === column.status);
        return (
          <section
            key={column.status}
            className="kanban-col"
            aria-label={`${column.title} — ${columnJobs.length} jobs`}
          >
            <header className="kanban-col__head">
              <span
                className={`kanban-col__dot kanban-col__dot--${column.dot}`}
                aria-hidden="true"
              />
              <h3 className="kanban-col__title">{column.title}</h3>
              <span
                className="kanban-col__count"
                data-count={columnJobs.length}
                aria-hidden="true"
              >
                {columnJobs.length}
              </span>
              <button
                type="button"
                className="kanban-col__menu"
                aria-label={`${column.title} column options`}
              >
                <DotsIcon size={14} />
              </button>
            </header>

            <button
              type="button"
              className="kanban-col__add"
              aria-label={`Add job to ${column.title} (coming soon)`}
              aria-disabled="true"
              title="Adding jobs is coming soon"
            >
              <PlusIcon size={14} />
            </button>

            <div className="kanban-col__cards">
              {columnJobs.map((job) => (
                <JobRow
                  key={job.id}
                  job={job}
                  selected={job.id === selectedJobId}
                  onSelect={onSelectJob}
                />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
