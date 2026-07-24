import type { JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import {
  type ApiClient,
  type ApiPreferenceProfile,
  getPreferenceProfile,
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

const SOURCE_LABEL: Record<string, string> = {
  pick: "Picked",
  edit: "Edited",
  rejection: "Rejected",
  approval: "Approved",
};

/**
 * Preference profile — the per-client learned taste (the learning loop made visible). Shows the
 * human-readable summary, whether the ranker is active yet (enough signals), and the raw signal
 * feed (pick/edit/rejection/approval + attributes). Read-only. Client-confined at the API.
 */
export default async function PreferencesPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<JSX.Element> {
  const { id } = await params;

  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  const [sidebar, clients, data] = await Promise.all([
    getSidebarData(bearer),
    listClients(bearer).catch((): ApiClient[] => []),
    getPreferenceProfile(id, bearer).catch((): ApiPreferenceProfile | null => null),
  ]);
  const clientName = clients.find((c) => c.id === id)?.name ?? "Client";

  if (data === null) {
    return (
      <AppShell sidebar={sidebar} title="Preferences" crumb={clientName}>
        <div className="empty-state">
          <p className="empty-state__title">No preference profile</p>
          <p className="empty-state__body">
            This client&apos;s taste profile isn&apos;t available. It builds as they pick, edit, and approve creatives.
          </p>
          <Link href="/billing" className="btn-ghost">
            Back to billing
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell sidebar={sidebar} title="Preference profile" crumb={clientName}>
      <div className="prefs">
        <div className="prefs__cards">
          <div className="prefs__card">
            <span className="prefs__card-num">{data.signal_count}</span>
            <span className="prefs__card-label">Signals collected</span>
          </div>
          <div className="prefs__card">
            <span className={`prefs__card-num prefs__card-num--${data.ranker_active ? "on" : "off"}`}>
              {data.ranker_active ? "Active" : "Learning"}
            </span>
            <span className="prefs__card-label">
              {data.ranker_active
                ? "Orders A/B variants by this client's learned preferences"
                : "Not enough signals yet"}
            </span>
          </div>
        </div>

        <p className="prefs__summary">{data.profile.summary}</p>

        {data.profile.signals.length > 0 && (
          <div className="prefs__section">
            <h2 className="creview__label">Signal feed</h2>
            <ul className="prefs__signals">
              {data.profile.signals
                .slice()
                .reverse()
                .map((s, i) => (
                  <li key={i} className="prefs__signal">
                    <span className={`prefs__signal-source prefs__signal-source--${s.source}`}>
                      {SOURCE_LABEL[s.source] ?? s.source}
                    </span>
                    {s.reason_tag !== null && s.reason_tag !== "" && (
                      <span className="prefs__signal-reason">{s.reason_tag}</span>
                    )}
                    <span className="prefs__signal-attrs">
                      {Object.entries(s.attributes)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(" · ") || "—"}
                    </span>
                  </li>
                ))}
            </ul>
          </div>
        )}
      </div>
    </AppShell>
  );
}
