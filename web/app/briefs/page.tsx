import type { JSX } from "react";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { BriefsListView } from "@/components/BriefsListView";
import { type ApiBrief, type ApiClient, listBriefs, listClients } from "@/lib/api";
import { getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";

// Briefs reflect live sign-off state — always per-request, never a build snapshot.
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
 * Brand briefs — the tenant's list of versioned brief documents. Like the members panel this is
 * behind the Supabase session gate and has NO mock fallback: an empty tenant gets a real empty
 * state. Client names are resolved from `/clients` so each brief reads by brand, not by raw id.
 */
export default async function BriefsPage(): Promise<JSX.Element> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;

  const [sidebar, briefs, clients] = await Promise.all([
    getSidebarData(bearer),
    listBriefs(undefined, bearer).catch((): ApiBrief[] => []),
    listClients(bearer).catch((): ApiClient[] => []),
  ]);

  const clientNames: Record<string, string> = {};
  for (const c of clients) {
    clientNames[c.id] = c.name;
  }

  return (
    <AppShell sidebar={sidebar} title="Brand briefs">
      <BriefsListView briefs={briefs} clientNames={clientNames} />
    </AppShell>
  );
}
