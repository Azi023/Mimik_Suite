import type { JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { BriefEditorView } from "@/components/BriefEditorView";
import { type ApiBrief, type ApiClient, getBrief, listClients } from "@/lib/api";
import { getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";

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
 * Brand-brief editor + sign-off. Loads one brief server-side with the real bearer, then hands it to
 * the client editor. A DRAFT is editable + sign-off-able; a FROZEN brief renders read-only with a
 * Revise action (mint version N+1). A missing / cross-tenant id yields a real not-found state — the
 * tenant scoping lives at the data layer, so another tenant's id simply 404s into this empty state.
 */
export default async function BriefEditorPage({
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

  const [sidebar, brief, clients] = await Promise.all([
    getSidebarData(bearer),
    getBrief(id, bearer).catch((): ApiBrief | null => null),
    listClients(bearer).catch((): ApiClient[] => []),
  ]);

  if (brief === null) {
    return (
      <AppShell sidebar={sidebar} title="Brand brief">
        <div className="brief">
          <div className="empty-state">
            <p className="empty-state__title">Brief not found</p>
            <p className="empty-state__body">
              It may have been removed, or it belongs to another workspace.
            </p>
            <Link href="/briefs" className="btn-ghost">
              Back to briefs
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  const clientName = clients.find((c) => c.id === brief.client_id)?.name ?? null;

  return (
    <AppShell sidebar={sidebar} title="Brand brief">
      <BriefEditorView brief={brief} clientName={clientName} />
    </AppShell>
  );
}
