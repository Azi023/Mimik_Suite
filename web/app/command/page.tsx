import type { JSX } from "react";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { CommandCenter } from "@/components/CommandCenter";
import {
  type ApiClient,
  type ApiContentPillar,
  type ApiGenerationQueueItem,
  type ApiQueueStats,
  fetchGenerationQueue,
  fetchQueueStats,
  listClients,
  listPillars,
} from "@/lib/api";
import { getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";
import { redirectClientToPortal } from "@/lib/guard";
import { enqueueGenerationAction } from "./actions";

// The queue reflects live generation state — always per-request, never a build snapshot.
export const dynamic = "force-dynamic";

/** Whether the DEV-ONLY unauthenticated fallback may render (dev + a build-time dev token). */
function devFallbackAllowed(): boolean {
  const appEnv = process.env.APP_ENV;
  const isDev = appEnv === undefined || appEnv === "" || appEnv === "dev";
  const hasDevToken =
    process.env.NEXT_PUBLIC_DEV_TOKEN !== undefined && process.env.NEXT_PUBLIC_DEV_TOKEN !== "";
  return isDev && hasDevToken;
}

/**
 * Command Center — the generation queue (the "generate" entry of the daily ops loop). Loads the
 * live queue + stats + the client/pillar options for the enqueue form server-side with the real
 * bearer. All three queue calls are team-gated at the API; a client principal never reaches here
 * (redirectClientToPortal sends them to the portal). Failed calls stay empty — never faked.
 */
export default async function CommandCenterPage(): Promise<JSX.Element> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  const [sidebar, queue, stats, clients, pillars] = await Promise.all([
    getSidebarData(bearer),
    fetchGenerationQueue(bearer).catch((): ApiGenerationQueueItem[] => []),
    fetchQueueStats(bearer).catch((): ApiQueueStats | null => null),
    listClients(bearer).catch((): ApiClient[] => []),
    listPillars(undefined, bearer).catch((): ApiContentPillar[] => []),
  ]);

  const clientNames: Record<string, string> = {};
  for (const c of clients) {
    clientNames[c.id] = c.name;
  }

  return (
    <AppShell sidebar={sidebar} title="Command Center" crumb="Generation queue">
      <CommandCenter
        queue={queue}
        stats={stats}
        clients={clients.map((c) => ({ id: c.id, name: c.name }))}
        clientNames={clientNames}
        pillars={pillars.map((p) => ({ name: p.name, clientId: p.client_id }))}
        enqueueAction={enqueueGenerationAction}
      />
    </AppShell>
  );
}
