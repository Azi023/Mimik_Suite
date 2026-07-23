"use client";

import { useMemo, useState, useTransition, type JSX } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ApiGenerationQueueItem, ApiQueueStats, EnqueueGenerationBody } from "@/lib/api";

/** Format presets the API accepts (mimik_contracts.formats.PRESETS keys) → display labels. */
const FORMATS: ReadonlyArray<{ key: string; label: string }> = [
  { key: "ig_post", label: "IG Post" },
  { key: "ig_story", label: "Story" },
  { key: "fb_post", label: "FB Post" },
  { key: "poster_a", label: "Poster" },
  { key: "carousel", label: "Carousel" },
];

const FORMAT_LABEL: ReadonlyMap<string, string> = new Map(FORMATS.map((f) => [f.key, f.label]));

/** Queue-item status (TaskStatus) → the pill label shown in the queue table. */
const STATUS_LABEL: ReadonlyMap<string, string> = new Map([
  ["open", "Queued"],
  ["in_progress", "Running"],
  ["done", "Done"],
]);

/** Contract cap on the enqueue topic/pillar (creative_generation: pillar max_length=120). */
const MAX_TOPIC_CHARS = 200;
const MAX_PILLAR_CHARS = 120;

interface ClientOption {
  id: string;
  name: string;
}

interface PillarOption {
  name: string;
  clientId: string;
}

interface CommandCenterProps {
  queue: ApiGenerationQueueItem[];
  /** Aggregate counters; null when the stats call failed (rendered as a quiet note, never faked). */
  stats: ApiQueueStats | null;
  clients: ClientOption[];
  /** client_id → display name, for the queue's client column. */
  clientNames: Record<string, string>;
  pillars: PillarOption[];
  enqueueAction: (body: EnqueueGenerationBody) => Promise<{ ok: boolean; error?: string }>;
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  // Explicit locale — an implicit (environment) locale is hydration-unsafe on SSR'd markup.
  return d.toLocaleString("en-GB", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

/**
 * The Command Center's generation queue — the "generate" entry of the daily ops loop
 * (backend: GET /ops/queue + /ops/queue/stats, POST /ops/queue). A four-counter header, an
 * enqueue form (client + topic + optional pillar + format), and the live queue with status pills
 * and a surfaced error for failed items. Team-gated at the API, so a client session's enqueue
 * simply 403s with an inline message; the queue renders a real empty state when nothing is queued.
 */
export function CommandCenter({
  queue,
  stats,
  clients,
  clientNames,
  pillars,
  enqueueAction,
}: CommandCenterProps): JSX.Element {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [clientId, setClientId] = useState<string>(clients[0]?.id ?? "");
  const [topic, setTopic] = useState("");
  const [pillar, setPillar] = useState("");
  const [formatKey, setFormatKey] = useState<string>(FORMATS[0].key);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Pillars belong to a client, so only the selected client's pillars are offered.
  const clientPillars = useMemo(
    () => pillars.filter((p) => p.clientId === clientId),
    [pillars, clientId],
  );

  function selectClient(next: string): void {
    setClientId(next);
    // A pillar from the previous client no longer applies — drop it.
    setPillar("");
  }

  const canSubmit = clientId !== "" && topic.trim() !== "" && !pending;

  function submit(): void {
    if (!canSubmit) return;
    setError("");
    setNotice("");
    const trimmedPillar = pillar.trim();
    const body: EnqueueGenerationBody = {
      client_id: clientId,
      topic: topic.trim(),
      format_key: formatKey,
      ...(trimmedPillar !== "" ? { pillar: trimmedPillar } : {}),
    };
    startTransition(async () => {
      const result = await enqueueAction(body);
      if (result.ok) {
        setTopic("");
        setPillar("");
        setNotice("Queued — the engine will pick it up.");
        router.refresh();
      } else {
        setError(result.error ?? "Could not queue the generation.");
      }
    });
  }

  return (
    <div className="command">
      <section className="command__stats" aria-label="Queue stats">
        {stats === null ? (
          <p className="command__stats-note">Queue stats are unavailable right now.</p>
        ) : (
          <>
            <StatTile label="Pending" value={stats.pending} tone="progress" />
            <StatTile label="Running" value={stats.in_progress} tone="accent" />
            <StatTile label="Done today" value={stats.done_today} tone="done" />
            <StatTile label="Failed today" value={stats.failed_today} tone="risk" />
          </>
        )}
      </section>

      <section className="command__enqueue" aria-label="Enqueue a generation">
        <h2 className="command__label">Queue a generation</h2>
        {clients.length === 0 ? (
          <p className="command__stats-note">
            Add a client first — generations are always queued against a client&apos;s brand.
          </p>
        ) : (
          <div className="command__form">
            <label className="command__field">
              <span className="command__field-label">Client</span>
              <select
                className="tasks__select"
                aria-label="Client"
                value={clientId}
                onChange={(e): void => selectClient(e.target.value)}
              >
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="command__field command__field--grow">
              <span className="command__field-label">Topic</span>
              <input
                className="command__input"
                type="text"
                value={topic}
                maxLength={MAX_TOPIC_CHARS}
                placeholder="What should this creative be about?"
                aria-label="Topic"
                onChange={(e): void => setTopic(e.target.value)}
                onKeyDown={(e): void => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    submit();
                  }
                }}
              />
            </label>

            <label className="command__field">
              <span className="command__field-label">Pillar</span>
              {clientPillars.length > 0 ? (
                <select
                  className="tasks__select"
                  aria-label="Content pillar"
                  value={pillar}
                  onChange={(e): void => setPillar(e.target.value)}
                >
                  <option value="">General</option>
                  {clientPillars.map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="command__input"
                  type="text"
                  value={pillar}
                  maxLength={MAX_PILLAR_CHARS}
                  placeholder="General"
                  aria-label="Content pillar"
                  onChange={(e): void => setPillar(e.target.value)}
                />
              )}
            </label>

            <label className="command__field">
              <span className="command__field-label">Format</span>
              <select
                className="tasks__select"
                aria-label="Format"
                value={formatKey}
                onChange={(e): void => setFormatKey(e.target.value)}
              >
                {FORMATS.map((f) => (
                  <option key={f.key} value={f.key}>
                    {f.label}
                  </option>
                ))}
              </select>
            </label>

            <button
              type="button"
              className="btn btn--primary"
              disabled={!canSubmit}
              onClick={submit}
            >
              {pending ? "Queuing…" : "Queue generation"}
            </button>
          </div>
        )}

        {error !== "" && (
          <p className="tasks__error" role="alert">
            {error}
          </p>
        )}
        {notice !== "" && (
          <p className="command__notice" role="status">
            {notice}
          </p>
        )}
      </section>

      <section className="command__queue" aria-label="Generation queue">
        <div className="command__queue-head">
          <h2 className="command__label">Queue</h2>
          <span className="tasks__count">
            {queue.length} item{queue.length === 1 ? "" : "s"}
          </span>
        </div>

        {queue.length === 0 ? (
          <div className="empty-state">
            <p className="empty-state__title">Nothing queued</p>
            <p className="empty-state__body">
              Queue a generation above and it shows up here — pending, running, then done, with any
              failure surfaced inline.
            </p>
          </div>
        ) : (
          <div className="tasks__table-wrap">
            <table className="tasks__table">
              <thead>
                <tr>
                  <th>Topic</th>
                  <th>Client</th>
                  <th>Format</th>
                  <th>Pillar</th>
                  <th>Status</th>
                  <th>Requested by</th>
                  <th>Queued</th>
                </tr>
              </thead>
              <tbody>
                {queue.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <span className="tasks__title">{item.topic}</span>
                      {item.job_id !== "" && (
                        <Link className="tasks__joblink" href={`/jobs/${item.job_id}/review`}>
                          open review ↗
                        </Link>
                      )}
                      {item.error !== null && item.error !== "" && (
                        <span className="command__err">{item.error}</span>
                      )}
                    </td>
                    <td className="tasks__client">{clientNames[item.client_id] ?? "—"}</td>
                    <td className="tasks__client">{FORMAT_LABEL.get(item.format_key) ?? item.format_key}</td>
                    <td className="tasks__client">{item.pillar ?? "General"}</td>
                    <td>
                      <span className={`tasks__pill tasks__pill--${item.status}`}>
                        {STATUS_LABEL.get(item.status) ?? item.status}
                      </span>
                    </td>
                    <td className="tasks__client">
                      {item.requested_by.name ?? item.requested_by.role}
                    </td>
                    <td className="tasks__when">{formatWhen(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

/** One counter tile in the queue-stats header. Tone drives only the number's semantic colour. */
function StatTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "progress" | "accent" | "done" | "risk";
}): JSX.Element {
  return (
    <div className="command__stat">
      <span className={`command__stat-value command__stat-value--${tone}`}>{value}</span>
      <span className="command__stat-label">{label}</span>
    </div>
  );
}
