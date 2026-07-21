import type { JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import {
  type ApiClient,
  type ApiDeliveryRecord,
  listClients,
  listDeliveries,
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

function formatWhen(iso: string | null): string {
  if (iso === null) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/**
 * Deliveries — the archive record. On approval, the auto-archive procedure renders the creative and
 * records a Delivery at a stable per-client Drive path (never a manual upload). Read-only ledger of
 * what shipped, where. Session-gated; a client-role session is auto-confined to its own deliveries.
 */
export default async function DeliveriesPage(): Promise<JSX.Element> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  const [sidebar, deliveries, clients] = await Promise.all([
    getSidebarData(bearer),
    listDeliveries(bearer).catch((): ApiDeliveryRecord[] => []),
    listClients(bearer).catch((): ApiClient[] => []),
  ]);
  const clientName: Record<string, string> = {};
  for (const c of clients) clientName[c.id] = c.name;

  return (
    <AppShell sidebar={sidebar} title="Deliveries">
      {deliveries.length === 0 ? (
        <div className="empty-state">
          <p className="empty-state__title">No deliveries yet</p>
          <p className="empty-state__body">
            When a creative is approved it auto-archives to Drive and shows up here — the shipped-work ledger.
          </p>
        </div>
      ) : (
        <div className="tasks__table-wrap">
          <table className="tasks__table">
            <thead>
              <tr>
                <th>Creative</th>
                <th>Client</th>
                <th>Drive path</th>
                <th>Delivered</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {deliveries.map((d) => (
                <tr key={d.id}>
                  <td>
                    <span className="tasks__title">{d.job_title}</span>
                  </td>
                  <td className="tasks__client">{clientName[d.client_id] ?? "—"}</td>
                  <td>
                    <code className="deliveries__path">{d.drive_path}</code>
                  </td>
                  <td className="tasks__when">{formatWhen(d.delivered_at ?? d.created_at)}</td>
                  <td className="tasks__actions">
                    <Link className="tasks__joblink" href={`/jobs/${d.job_id}/review`}>
                      open ↗
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
