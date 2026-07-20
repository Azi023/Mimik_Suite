"use client";

import { useMemo, useState, useTransition, type JSX } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ApiTask } from "@/lib/api";
import { advanceTaskAction } from "@/app/tasks/actions";

/** Task statuses (mimik_contracts.enums.TaskStatus) + the "all" filter sentinel. */
const STATUSES = ["open", "in_progress", "done"] as const;
type Status = (typeof STATUSES)[number];

/** Task types (mimik_contracts.enums.TaskType). */
const TYPE_LABEL: ReadonlyMap<string, string> = new Map([
  ["change_request", "Change request"],
  ["comment", "Comment"],
  ["editor_assignment", "Editor assignment"],
  ["generation", "Generation"],
]);

const STATUS_LABEL: ReadonlyMap<string, string> = new Map([
  ["open", "Open"],
  ["in_progress", "In progress"],
  ["done", "Done"],
]);

/** open -> in_progress -> done; done is terminal. */
const NEXT_STATUS: ReadonlyMap<Status, Status> = new Map([
  ["open", "in_progress"],
  ["in_progress", "done"],
]);

const PAGE_SIZE = 12;

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

interface TasksViewProps {
  tasks: ApiTask[];
  /** client_id -> display name (for the client column). */
  clientNames: Record<string, string>;
}

/**
 * Filterable, paginated tasks table. Filters (status + type) and pagination are client-side over
 * the tenant's full task set; status advances go through a server action (team-gated at the API,
 * so a client session's advance simply 403s with an inline message). Real empty state when the
 * tenant has no tasks or the filters exclude everything.
 */
export function TasksView({ tasks, clientNames }: TasksViewProps): JSX.Element {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [statusFilter, setStatusFilter] = useState<Status | "all">("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const filtered = useMemo(
    () =>
      tasks.filter(
        (t) =>
          (statusFilter === "all" || t.status === statusFilter) &&
          (typeFilter === "all" || t.type === typeFilter),
      ),
    [tasks, statusFilter, typeFilter],
  );

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const rows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  function resetPage<T>(setter: (v: T) => void): (v: T) => void {
    return (v: T): void => {
      setter(v);
      setPage(0);
    };
  }

  function advance(task: ApiTask): void {
    const next = NEXT_STATUS.get(task.status as Status);
    if (next === undefined || pending) return;
    setBusyId(task.id);
    setError("");
    startTransition(async () => {
      const result = await advanceTaskAction(task.id, next);
      setBusyId(null);
      if (result.ok) {
        router.refresh();
      } else {
        setError(result.error ?? "Could not update the task.");
      }
    });
  }

  return (
    <div className="tasks">
      <div className="tasks__filters">
        <div className="tasks__filter-group" role="group" aria-label="Filter by status">
          <button
            type="button"
            className={`seg${statusFilter === "all" ? " seg--active" : ""}`}
            onClick={(): void => resetPage(setStatusFilter)("all")}
          >
            All
          </button>
          {STATUSES.map((s) => (
            <button
              key={s}
              type="button"
              className={`seg${statusFilter === s ? " seg--active" : ""}`}
              onClick={(): void => resetPage(setStatusFilter)(s)}
            >
              {STATUS_LABEL.get(s)}
            </button>
          ))}
        </div>

        <select
          className="tasks__select"
          aria-label="Filter by type"
          value={typeFilter}
          onChange={(e): void => resetPage(setTypeFilter)(e.target.value)}
        >
          <option value="all">All types</option>
          {[...TYPE_LABEL.entries()].map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>

        <span className="tasks__count">{filtered.length} task{filtered.length === 1 ? "" : "s"}</span>
      </div>

      {error !== "" && (
        <p className="tasks__error" role="alert">
          {error}
        </p>
      )}

      {rows.length === 0 ? (
        <div className="empty-state">
          <p className="empty-state__title">No tasks here</p>
          <p className="empty-state__body">
            {tasks.length === 0
              ? "Change requests, comments and assignments will show up here as the review loop runs."
              : "No tasks match these filters."}
          </p>
        </div>
      ) : (
        <div className="tasks__table-wrap">
          <table className="tasks__table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Type</th>
                <th>Client</th>
                <th>Status</th>
                <th>Updated</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {rows.map((task) => {
                const next = NEXT_STATUS.get(task.status as Status);
                return (
                  <tr key={task.id}>
                    <td>
                      <span className="tasks__title">{task.title}</span>
                      {task.job_id !== null && (
                        <Link className="tasks__joblink" href={`/jobs/${task.job_id}/review`}>
                          open review ↗
                        </Link>
                      )}
                    </td>
                    <td>
                      <span className="tasks__type">{TYPE_LABEL.get(task.type) ?? task.type}</span>
                    </td>
                    <td className="tasks__client">{clientNames[task.client_id] ?? "—"}</td>
                    <td>
                      <span className={`tasks__pill tasks__pill--${task.status}`}>
                        {STATUS_LABEL.get(task.status) ?? task.status}
                      </span>
                    </td>
                    <td className="tasks__when">{formatWhen(task.updated_at ?? task.created_at)}</td>
                    <td className="tasks__actions">
                      {next !== undefined ? (
                        <button
                          type="button"
                          className="btn btn--secondary btn--sm"
                          disabled={pending && busyId === task.id}
                          onClick={(): void => advance(task)}
                        >
                          {pending && busyId === task.id
                            ? "…"
                            : `Mark ${STATUS_LABEL.get(next)?.toLowerCase()}`}
                        </button>
                      ) : (
                        <span className="tasks__done-tick" aria-label="Done">
                          ✓
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {pageCount > 1 && (
        <div className="tasks__pager">
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={safePage === 0}
            onClick={(): void => setPage((p) => Math.max(0, p - 1))}
          >
            Prev
          </button>
          <span className="tasks__pager-label">
            {safePage + 1} / {pageCount}
          </span>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={safePage >= pageCount - 1}
            onClick={(): void => setPage((p) => Math.min(pageCount - 1, p + 1))}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
