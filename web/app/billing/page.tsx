import type { JSX } from "react";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { BillingView, type ClientBilling } from "@/components/BillingView";
import {
  type ApiClient,
  type ApiSubscription,
  getClientSubscription,
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

/**
 * Billing — per-client subscription status + "Send quote" (mint a checkout/payment link to share).
 * Read-mostly ops surface; the only mutation (create a quote link) goes through a server action.
 * A client-role session is steered to the portal. Subscriptions 404 into a "no subscription" state.
 */
export default async function BillingPage(): Promise<JSX.Element> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  const [sidebar, clients] = await Promise.all([
    getSidebarData(bearer),
    listClients(bearer).catch((): ApiClient[] => []),
  ]);

  // Each client's subscription (404 = none yet → null). Small N (an agency's client list).
  const rows: ClientBilling[] = await Promise.all(
    clients.map(async (c): Promise<ClientBilling> => {
      const subscription = await getClientSubscription(c.id, bearer).catch(
        (): ApiSubscription | null => null,
      );
      return { clientId: c.id, clientName: c.name, subscription };
    }),
  );

  return (
    <AppShell sidebar={sidebar} title="Billing">
      <BillingView rows={rows} />
    </AppShell>
  );
}
