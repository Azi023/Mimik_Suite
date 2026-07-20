import type { JSX } from "react";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { TasksView } from "@/components/TasksView";
import { type ApiClient, type ApiTask, listClients, listTasks } from "@/lib/api";
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

/**
 * Tasks — the shared ops/portal work table (reference: Studio Admin tasks). One row per Task
 * (change requests, comments, editor assignments, generation nudges). Loaded server-side with the
 * real bearer; a client-role session is auto-confined to its own client's tasks at the data layer.
 */
export default async function TasksPage(): Promise<JSX.Element> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  const [sidebar, tasks, clients] = await Promise.all([
    getSidebarData(bearer),
    listTasks({}, bearer).catch((): ApiTask[] => []),
    listClients(bearer).catch((): ApiClient[] => []),
  ]);

  const clientNames: Record<string, string> = {};
  for (const c of clients) {
    clientNames[c.id] = c.name;
  }

  return (
    <AppShell sidebar={sidebar} title="Tasks">
      <TasksView tasks={tasks} clientNames={clientNames} />
    </AppShell>
  );
}
