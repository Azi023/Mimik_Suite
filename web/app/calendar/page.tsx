import type { JSX } from "react";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { CalendarView, type CalendarEntry } from "@/components/CalendarView";
import {
  type ApiBoardResponse,
  type ApiClient,
  type ApiJobStatus,
  fetchBoard,
  listClients,
} from "@/lib/api";
import { getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";
import { redirectClientToPortal } from "@/lib/guard";

export const dynamic = "force-dynamic";

/** Whether the DEV-ONLY unauthenticated fallback may render (dev + a build-time dev token). */
function devFallbackAllowed(): boolean {
  const appEnv = process.env.APP_ENV;
  const isDev = appEnv === undefined || appEnv === "" || appEnv === "dev";
  const hasDevToken =
    process.env.NEXT_PUBLIC_DEV_TOKEN !== undefined && process.env.NEXT_PUBLIC_DEV_TOKEN !== "";
  return isDev && hasDevToken;
}

const EMPTY_BOARD: ApiBoardResponse = {
  columns: {} as Record<ApiJobStatus, never[]>,
};

/**
 * Content calendar — a month grid of every scheduled job by publish date, with at-risk badges
 * (reference: shadcn Calendar). Sourced from GET /ops/board (each card carries the job + the
 * computed at_risk flag). Read-only; clicking a job opens its creative review.
 */
export default async function CalendarPage(): Promise<JSX.Element> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  const [sidebar, board, clients] = await Promise.all([
    getSidebarData(bearer),
    fetchBoard(bearer).catch((): ApiBoardResponse => EMPTY_BOARD),
    listClients(bearer).catch((): ApiClient[] => []),
  ]);

  const clientNames: Record<string, string> = {};
  for (const c of clients) {
    clientNames[c.id] = c.name;
  }

  // Flatten the board into dated calendar entries (jobs with a publish date).
  const entries: CalendarEntry[] = [];
  for (const cards of Object.values(board.columns)) {
    for (const card of cards) {
      if (card.job.publish_date !== null) {
        entries.push({
          jobId: card.job.id,
          title: card.job.title,
          publishDate: card.job.publish_date,
          status: card.job.status,
          atRisk: card.at_risk,
          clientName: clientNames[card.job.client_id] ?? null,
        });
      }
    }
  }

  return (
    <AppShell sidebar={sidebar} title="Content calendar">
      <CalendarView entries={entries} />
    </AppShell>
  );
}
