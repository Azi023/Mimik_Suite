import type { JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { CreativeReview } from "@/components/CreativeReview";
import {
  type ApiBrand,
  type ApiClient,
  type ApiJob,
  type JobAuditTrail,
  getBrand,
  getJob,
  getJobAuditTrail,
  listClients,
  listJobCreatives,
} from "@/lib/api";
import { getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";
import { redirectClientToPortal } from "@/lib/guard";
import { editCopyAction, mintMagicLinkAction } from "./actions";

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
 * Creative review + approval — the sellable core loop (reference: Filestage). Loads one job's
 * latest creatives + audit trail server-side with the real bearer, then hands them to the client
 * canvas. Tenant scoping lives at the data layer, so a foreign / missing job id simply 404s into
 * a real not-found empty state — never a cross-tenant leak.
 */
export default async function CreativeReviewPage({
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

  const [sidebar, job] = await Promise.all([
    getSidebarData(bearer),
    getJob(id, bearer).catch((): ApiJob | null => null),
  ]);

  if (job === null) {
    return (
      <AppShell sidebar={sidebar} title="Creative review">
        <div className="creview creview--empty">
          <div className="empty-state">
            <p className="empty-state__title">Job not found</p>
            <p className="empty-state__body">
              It may have been removed, or it belongs to another workspace.
            </p>
            <Link href="/" className="btn-ghost">
              Back to the board
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  const [brand, creatives, audit, clients] = await Promise.all([
    getBrand(job.brand_id, bearer).catch((): ApiBrand | null => null),
    listJobCreatives(job.id, bearer).catch(() => []),
    getJobAuditTrail(job.id, bearer).catch(
      (): JobAuditTrail => ({ approvals: [], deliveries: [] }),
    ),
    listClients(bearer).catch((): ApiClient[] => []),
  ]);

  if (brand === null) {
    return (
      <AppShell sidebar={sidebar} title="Creative review" crumb={job.title}>
        <div className="creview creview--empty">
          <div className="empty-state">
            <p className="empty-state__title">Brand unavailable</p>
            <p className="empty-state__body">
              This job&apos;s brand couldn&apos;t be loaded, so its creative can&apos;t be composed.
            </p>
          </div>
        </div>
      </AppShell>
    );
  }

  const clientName = clients.find((c) => c.id === job.client_id)?.name ?? null;

  return (
    <AppShell sidebar={sidebar} title="Creative review" crumb={job.title}>
      <CreativeReview
        job={job}
        brand={brand}
        clientName={clientName}
        creatives={creatives}
        approvals={audit.approvals}
        deliveries={audit.deliveries}
        mintLink={mintMagicLinkAction.bind(null, job.id)}
        editCopyAction={editCopyAction.bind(null, job.id, job.client_id)}
      />
    </AppShell>
  );
}
