import type { JSX } from "react";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { MembersView } from "@/components/MembersView";
import {
  type ApiCapabilityMatrix,
  type ApiInvitation,
  type ApiUserAccount,
  getCapabilityMatrix,
  listAccounts,
  listInvitations,
} from "@/lib/api";
import { getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";
import { redirectClientToPortal } from "@/lib/guard";

// Members/roles reflect live authЗ state — always per-request, never a build snapshot.
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
 * Members & roles — the admin panel (shadcn "Roles & Permissions" reference). Lists the tenant's
 * accounts, the role→capability matrix, and pending invitations; invites/revokes run through the
 * server actions in `./actions` (per-user token, server-side). Reads render server-side with the
 * real bearer. Unlike the board there is NO mock fallback — an empty tenant gets a real empty state.
 */
export default async function MembersPage(): Promise<JSX.Element> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  // Each read degrades independently — a missing endpoint or a scoped role (403) yields an empty
  // section, never a broken page. The capabilities endpoint is newest, so guard it hardest.
  const [sidebar, accounts, invitations, capabilities] = await Promise.all([
    getSidebarData(bearer),
    listAccounts(bearer).catch((): ApiUserAccount[] => []),
    listInvitations(bearer).catch((): ApiInvitation[] => []),
    getCapabilityMatrix(bearer).catch((): ApiCapabilityMatrix => ({})),
  ]);

  return (
    <AppShell sidebar={sidebar} title="Members & roles">
      <MembersView accounts={accounts} invitations={invitations} capabilities={capabilities} />
    </AppShell>
  );
}
