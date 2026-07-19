"use client";

import { useLayoutEffect, useRef, type JSX } from "react";
import { boardColumns, type Job } from "@/lib/mock";
import { animateCount, staggerFadeUp } from "@/lib/motion";
import { JobRow } from "./JobRow";
import { DotsIcon, PlusIcon } from "./icons";

interface BoardProps {
  jobs: Job[];
}

/**
 * The approvals board as a kanban: one column per lifecycle status, headed by
 * a status dot + count (reference: red = at risk, orange = in review,
 * green = approved). Cards stagger-fade-up on first paint; counts tick up.
 */
export function Board({ jobs }: BoardProps): JSX.Element {
  const rootRef = useRef<HTMLDivElement>(null);

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
  }, []);

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
              aria-label={`Add job to ${column.title}`}
            >
              <PlusIcon size={14} />
            </button>

            <div className="kanban-col__cards">
              {columnJobs.map((job) => (
                <JobRow key={job.id} job={job} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
