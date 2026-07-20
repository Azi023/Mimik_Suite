"use client";

import { useMemo, useState, type JSX } from "react";
import Link from "next/link";
import type { ApiJobStatus } from "@/lib/api";

/** One dated job on the calendar. `publishDate` is an ISO datetime string. */
export interface CalendarEntry {
  jobId: string;
  title: string;
  publishDate: string;
  status: ApiJobStatus;
  atRisk: boolean;
  clientName: string | null;
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** Local YYYY-MM-DD key for a Date (calendar cells are keyed by local day). */
function dayKey(y: number, m: number, d: number): string {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/** Bucket entries by their local publish day. */
function bucketByDay(entries: CalendarEntry[]): ReadonlyMap<string, CalendarEntry[]> {
  const map = new Map<string, CalendarEntry[]>();
  for (const e of entries) {
    const d = new Date(e.publishDate);
    if (Number.isNaN(d.getTime())) continue;
    const key = dayKey(d.getFullYear(), d.getMonth(), d.getDate());
    const list = map.get(key);
    if (list === undefined) map.set(key, [e]);
    else list.push(e);
  }
  return map;
}

/** Monday-first weekday index (JS getDay: 0=Sun..6=Sat -> 0=Mon..6=Sun). */
function mondayIndex(jsDay: number): number {
  return (jsDay + 6) % 7;
}

interface CalendarViewProps {
  entries: CalendarEntry[];
}

/**
 * Month grid of scheduled jobs (Monday-first). Navigable month-to-month; the initial month is the
 * one holding the soonest scheduled job, or the current month when nothing is scheduled. Each cell
 * lists its jobs with an at-risk badge; clicking a job opens its creative review. Read-only.
 */
export function CalendarView({ entries }: CalendarViewProps): JSX.Element {
  const byDay = useMemo(() => bucketByDay(entries), [entries]);

  // Anchor on the soonest scheduled job so the grid opens where the work is.
  const initial = useMemo(() => {
    const dates = entries
      .map((e) => new Date(e.publishDate))
      .filter((d) => !Number.isNaN(d.getTime()))
      .sort((a, b) => a.getTime() - b.getTime());
    const anchor = dates[0] ?? new Date();
    return { year: anchor.getFullYear(), month: anchor.getMonth() };
  }, [entries]);

  const [view, setView] = useState(initial);
  const today = new Date();
  const todayKey = dayKey(today.getFullYear(), today.getMonth(), today.getDate());

  const firstOfMonth = new Date(view.year, view.month, 1);
  const daysInMonth = new Date(view.year, view.month + 1, 0).getDate();
  const leadBlanks = mondayIndex(firstOfMonth.getDay());
  const cells: Array<number | null> = [
    ...Array.from({ length: leadBlanks }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  function shift(delta: number): void {
    setView((v) => {
      const m = v.month + delta;
      return { year: v.year + Math.floor(m / 12), month: ((m % 12) + 12) % 12 };
    });
  }

  const scheduledThisMonth = cells.reduce<number>((acc, day) => {
    if (day === null) return acc;
    return acc + (byDay.get(dayKey(view.year, view.month, day))?.length ?? 0);
  }, 0);

  return (
    <div className="cal">
      <div className="cal__head">
        <div className="cal__nav">
          <button type="button" className="btn btn--ghost btn--sm" onClick={(): void => shift(-1)} aria-label="Previous month">
            ‹
          </button>
          <h2 className="cal__month">
            {MONTHS[view.month]} {view.year}
          </h2>
          <button type="button" className="btn btn--ghost btn--sm" onClick={(): void => shift(1)} aria-label="Next month">
            ›
          </button>
          <button
            type="button"
            className="btn btn--secondary btn--sm"
            onClick={(): void => setView({ year: today.getFullYear(), month: today.getMonth() })}
          >
            Today
          </button>
        </div>
        <span className="cal__count">
          {scheduledThisMonth} scheduled this month
        </span>
      </div>

      <div className="cal__grid" role="grid">
        {WEEKDAYS.map((w) => (
          <div key={w} className="cal__weekday" role="columnheader">
            {w}
          </div>
        ))}
        {cells.map((day, i) => {
          if (day === null) {
            return <div key={`b${i}`} className="cal__cell cal__cell--blank" aria-hidden="true" />;
          }
          const key = dayKey(view.year, view.month, day);
          const dayEntries = byDay.get(key) ?? [];
          const isToday = key === todayKey;
          return (
            <div key={key} className={`cal__cell${isToday ? " cal__cell--today" : ""}`} role="gridcell">
              <span className="cal__daynum">{day}</span>
              <div className="cal__events">
                {dayEntries.map((e) => (
                  <Link
                    key={e.jobId}
                    href={`/jobs/${e.jobId}/review`}
                    className={`cal__event${e.atRisk ? " cal__event--risk" : ""}`}
                    title={`${e.title}${e.clientName !== null ? ` · ${e.clientName}` : ""}`}
                  >
                    {e.atRisk && <span className="cal__event-dot" aria-label="At risk" />}
                    <span className="cal__event-title">{e.title}</span>
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {entries.length === 0 && (
        <div className="empty-state cal__empty">
          <p className="empty-state__title">Nothing scheduled yet</p>
          <p className="empty-state__body">
            Jobs with a publish date land on this calendar. Set publish dates on the board to plan the month.
          </p>
        </div>
      )}
    </div>
  );
}
