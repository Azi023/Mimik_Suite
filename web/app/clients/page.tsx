import type { JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { ShapeIcon } from "@/components/icons";
import { getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";
import { redirectClientToPortal } from "@/lib/guard";

// The client list reflects live tenant state — always per-request, never a build snapshot.
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
 * Clients index — the tenant's client roster as a fluid card grid, sourced from the SAME
 * data facade the sidebar renders (`getSidebarData`: tenant-scoped clients + per-client
 * job counts off the board). Each card opens the client + brand-brief editor.
 * Session-gated like the board; empty tenants get a real empty state.
 */
export default async function ClientsPage(): Promise<JSX.Element> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  const sidebar = await getSidebarData(bearer);
  const clients = sidebar.groups.flatMap((group) => group.projects);

  return (
    <AppShell sidebar={sidebar} title="Clients">
      {clients.length === 0 ? (
        <div className="empty-state">
          <p className="empty-state__title">No clients yet</p>
          <p className="empty-state__body">
            Add a client to start building their workspace.
          </p>
          <Link href="/onboarding" className="btn btn--primary">
            New client
          </Link>
        </div>
      ) : (
        <ul className="gallery" aria-label="Clients">
          {clients.map((client) => (
            <li key={client.id}>
              <Link
                href={`/clients/${encodeURIComponent(client.id)}/edit`}
                className="gallery-card gallery-card--client"
                aria-label={`Edit ${client.name}`}
              >
                <span className={`project-row__shape shape--${client.tone}`} aria-hidden="true">
                  <ShapeIcon shape={client.shape} />
                </span>
                <span className="gallery-card__meta">
                  <span className="gallery-card__title">{client.name}</span>
                  <span className="gallery-card__version">
                    {client.count === 1 ? "1 open job" : `${client.count} open jobs`}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}
