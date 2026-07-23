"use client";

import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
  type DragEvent,
  type JSX,
} from "react";
import { useRouter } from "next/navigation";
import { transitionJobAction } from "@/app/actions";
import type { ApiBoardCard, ApiBoardResponse, ApiJobStatus } from "@/lib/api";
import type { Job } from "@/lib/view-models";
import { animateCount, staggerFadeUp } from "@/lib/motion";
import { JobRow } from "./JobRow";
import { DotsIcon, PlusIcon } from "./icons";

interface BoardProps {
  /** The live GET /ops/board response — the single source of column membership. */
  board: ApiBoardResponse;
  /**
   * The (pillar-filtered) view jobs, joined to board cards by id. A card whose job
   * is not in this list is hidden — that is how the pillar filter subsets the board.
   */
  jobs: Job[];
  /** Id of the job currently open in the review panel (null = none clicked yet). */
  selectedJobId: string | null;
  /** Fired when a card is clicked — selects it into the review panel. */
  onSelectJob: (job: Job) => void;
}

interface PipelineColumn {
  status: ApiJobStatus;
  title: string;
  /** Maps to the kanban-col__dot tone classes (red = attention, orange = in flight, green = done). */
  dot: "new" | "progress" | "done";
}

/** The API's stable pipeline order (GET /ops/board returns every key, even when empty). */
const PIPELINE_COLUMNS: readonly PipelineColumn[] = [
  { status: "draft", title: "Draft", dot: "progress" },
  { status: "generating", title: "Generating", dot: "progress" },
  { status: "internal_review", title: "Internal review", dot: "progress" },
  { status: "client_review", title: "Client review", dot: "progress" },
  { status: "approved", title: "Approved", dot: "done" },
  { status: "delivered", title: "Delivered", dot: "done" },
  { status: "archived", title: "Archived", dot: "done" },
  { status: "blocked", title: "Blocked", dot: "new" },
];

/**
 * Compact "how long ago" for the generating-since hint: "just now", "4m ago", "2h ago", "1d ago".
 * `now` is a post-mount timestamp (never `Date.now()` in render — SSR/client hydration mismatch).
 */
function relativeSince(iso: string, now: number): string {
  const elapsedMs = now - new Date(iso).getTime();
  if (!Number.isFinite(elapsedMs) || elapsedMs < 60_000) return "just now";
  const minutes = Math.floor(elapsedMs / 60_000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/**
 * Pipeline-board styles with no existing class in globals.css (which is outside this
 * task's file list): the 8-column scrollable grid, the dashed drop-target highlight,
 * and the drag affordances. Tokens only — matches the locked design system.
 */
const PIPELINE_CSS = `
.kanban--pipeline {
  grid-template-columns: repeat(${PIPELINE_COLUMNS.length}, minmax(235px, 1fr));
  overflow-x: auto;
  padding-bottom: var(--sp-2);
}
@media (max-width: 860px) {
  .kanban--pipeline {
    grid-template-columns: 1fr;
    overflow-x: visible;
  }
}
.kanban-col {
  border-radius: var(--r-md);
}
.kanban-col--drop {
  outline: 2px dashed var(--accent);
  outline-offset: 2px;
  background: color-mix(in srgb, var(--accent-soft) 60%, transparent);
}
.job-card--draggable { cursor: grab; }
.job-card--draggable:active { cursor: grabbing; }
.job-card--dragging { opacity: 0.45; }
`;

interface DisplayCard {
  job: Job;
  /** Preformatted "generating since" hint — present only in the generating column. */
  generatingSince: string | undefined;
}

/**
 * The approvals board as a live Kanban driven by GET /ops/board: one column per
 * pipeline status in the API's stable order, headed by a status dot + count. Cards
 * drag between columns; a drop persists via the transition server action with an
 * optimistic move that snaps back on 409 (the server's detail is surfaced inline).
 * Cards stagger-fade-up on data changes; counts tick up. Clicking a card selects
 * it into the review panel.
 */
export function Board({ board, jobs, selectedJobId, onSelectJob }: BoardProps): JSX.Element {
  const rootRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const [, startTransition] = useTransition();
  /** jobId -> optimistic destination column, shown until the next server board lands. */
  const [pendingMoves, setPendingMoves] = useState<Record<string, ApiJobStatus>>({});
  const [dragJobId, setDragJobId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<ApiJobStatus | null>(null);
  const [moveError, setMoveError] = useState<string | null>(null);
  /**
   * Post-mount clock for the "Generating · Nm ago" hint. Null on the server and the
   * first client paint (both render the stable "Generating" label), then set in an
   * effect so SSR and hydration markup always match.
   */
  const [sinceNow, setSinceNow] = useState<number | null>(null);
  useEffect(() => {
    setSinceNow(Date.now());
  }, [board]);

  // A fresh server board is the truth — drop the optimistic overlay it replaces.
  useEffect(() => {
    setPendingMoves({});
  }, [board]);

  const jobsById = useMemo<ReadonlyMap<string, Job>>(
    () => new Map(jobs.map((job) => [job.id, job])),
    [jobs],
  );

  const cardById = useMemo<ReadonlyMap<string, ApiBoardCard>>(() => {
    const map = new Map<string, ApiBoardCard>();
    for (const column of PIPELINE_COLUMNS) {
      for (const card of board.columns[column.status]) {
        map.set(card.job.id, card);
      }
    }
    return map;
  }, [board]);

  // Server columns + the optimistic overlay, joined to the (pillar-filtered) view jobs.
  const columns = useMemo(() => {
    return PIPELINE_COLUMNS.map((column) => {
      const staying = board.columns[column.status].filter((card) => {
        const movedTo = pendingMoves[card.job.id];
        return movedTo === undefined || movedTo === column.status;
      });
      const movedIn = Object.entries(pendingMoves)
        .filter(
          ([jobId, toStatus]) =>
            toStatus === column.status && cardById.get(jobId)?.job.status !== column.status,
        )
        .map(([jobId]) => cardById.get(jobId))
        .filter((card): card is ApiBoardCard => card !== undefined);
      const cards: DisplayCard[] = [...staying, ...movedIn].flatMap((card) => {
        const viewJob = jobsById.get(card.job.id);
        if (viewJob === undefined) return []; // hidden by the active pillar filter
        const effectiveStatus = pendingMoves[card.job.id] ?? card.job.status;
        const job: Job = {
          ...viewJob,
          atRisk: card.at_risk,
          generating: effectiveStatus === "generating",
        };
        const generatingSince =
          effectiveStatus === "generating" &&
          card.job.generation_started_at !== null &&
          sinceNow !== null
            ? relativeSince(card.job.generation_started_at, sinceNow)
            : undefined;
        return [{ job, generatingSince }];
      });
      return { column, cards };
    });
  }, [board, cardById, jobsById, pendingMoves, sinceNow]);

  // Re-run the entrance + count tick-up when the server data (or the filter) changes —
  // NOT on optimistic drag moves, so a drop never re-animates the whole board.
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
  }, [board, jobs]);

  function beginDrag(event: DragEvent<HTMLElement>, jobId: string): void {
    event.dataTransfer.setData("text/plain", jobId);
    event.dataTransfer.effectAllowed = "move";
    setDragJobId(jobId);
    setMoveError(null);
  }

  function endDrag(): void {
    setDragJobId(null);
    setDropTarget(null);
  }

  function handleDragOver(event: DragEvent<HTMLElement>, status: ApiJobStatus): void {
    if (dragJobId === null) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDropTarget((current) => (current === status ? current : status));
  }

  function handleDragLeave(event: DragEvent<HTMLElement>, status: ApiJobStatus): void {
    const related = event.relatedTarget;
    if (related instanceof Node && event.currentTarget.contains(related)) return;
    setDropTarget((current) => (current === status ? null : current));
  }

  function handleDrop(event: DragEvent<HTMLElement>, status: ApiJobStatus): void {
    event.preventDefault();
    const fromData = event.dataTransfer.getData("text/plain");
    const jobId = fromData !== "" ? fromData : dragJobId;
    setDragJobId(null);
    setDropTarget(null);
    if (jobId === null) return;
    const card = cardById.get(jobId);
    if (card === undefined) return;
    if ((pendingMoves[jobId] ?? card.job.status) === status) return; // same-column drop = no-op

    setMoveError(null);
    // Optimistic move; the server action validates and the board is re-fetched after.
    setPendingMoves((moves) => ({ ...moves, [jobId]: status }));
    startTransition(async (): Promise<void> => {
      const result = await transitionJobAction(jobId, status);
      if (!result.ok) {
        // Snap back: remove the optimistic move and surface the server's detail.
        setPendingMoves((moves) => {
          const next = { ...moves };
          delete next[jobId];
          return next;
        });
        setMoveError(result.error);
        return;
      }
      // Land where the server put it (→approved may auto-archive), then re-fetch the truth.
      setPendingMoves((moves) => ({ ...moves, [jobId]: result.job.status }));
      router.refresh();
    });
  }

  return (
    <>
      <style>{PIPELINE_CSS}</style>
      {moveError !== null && (
        <p
          className="generate-control__error"
          role="alert"
          style={{ margin: "0 0 var(--sp-2)" }}
        >
          {moveError}
        </p>
      )}
      <div className="kanban kanban--pipeline" ref={rootRef}>
        {columns.map(({ column, cards }) => {
          const isDropTarget = dropTarget === column.status && dragJobId !== null;
          return (
            <section
              key={column.status}
              className={`kanban-col${isDropTarget ? " kanban-col--drop" : ""}`}
              aria-label={`${column.title} — ${cards.length} jobs`}
              onDragOver={(event): void => handleDragOver(event, column.status)}
              onDragLeave={(event): void => handleDragLeave(event, column.status)}
              onDrop={(event): void => handleDrop(event, column.status)}
            >
              <header className="kanban-col__head">
                <span
                  className={`kanban-col__dot kanban-col__dot--${column.dot}`}
                  aria-hidden="true"
                />
                <h3 className="kanban-col__title">{column.title}</h3>
                <span
                  className="kanban-col__count"
                  data-count={cards.length}
                  aria-hidden="true"
                >
                  {cards.length}
                </span>
                <button
                  type="button"
                  className="kanban-col__menu"
                  aria-label={`${column.title} column options (coming soon)`}
                  aria-disabled="true"
                  title="Column actions coming soon"
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
                {cards.map(({ job, generatingSince }) => (
                  <JobRow
                    key={job.id}
                    job={job}
                    selected={job.id === selectedJobId}
                    onSelect={onSelectJob}
                    draggable
                    dragging={job.id === dragJobId}
                    generatingSince={generatingSince}
                    onDragStart={(event): void => beginDrag(event, job.id)}
                    onDragEnd={endDrag}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </>
  );
}
