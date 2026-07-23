import type { JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { CreativeReview } from "@/components/CreativeReview";
import { PortalShell } from "@/components/PortalShell";
import {
  type ApiBrand,
  type ApiJob,
  type JobAuditTrail,
  getBrand,
  getJob,
  getJobAuditTrail,
  listJobCreatives,
} from "@/lib/api";
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
 * Client-portal review — the SAME creative review + approval component the team uses, in the bounded
 * portal chrome (no internal nav). A client principal is confined to its own client's jobs at the
 * data layer, so a foreign / missing id simply 404s into a not-found state — never a cross-client
 * leak (see api/routers/jobs.py, creatives.py, approvals.py). The client acts as itself; the backend
 * records the approval attributed to the client actor.
 */
export default async function PortalReviewPage({
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

  const job = await getJob(id, bearer).catch((): ApiJob | null => null);
  if (job === null) {
    return (
      <PortalShell title="Creative" back>
        <div className="empty-state">
          <p className="empty-state__title">Not found</p>
          <p className="empty-state__body">This creative isn&apos;t available on your portal.</p>
          <Link href="/portal" className="btn-ghost">
            Back to your creatives
          </Link>
        </div>
      </PortalShell>
    );
  }

  const [brand, creatives, audit] = await Promise.all([
    getBrand(job.brand_id, bearer).catch((): ApiBrand | null => null),
    listJobCreatives(job.id, bearer).catch(() => []),
    getJobAuditTrail(job.id, bearer).catch(
      (): JobAuditTrail => ({ approvals: [], deliveries: [] }),
    ),
  ]);

  if (brand === null) {
    return (
      <PortalShell title={job.title} back>
        <div className="empty-state">
          <p className="empty-state__title">Creative unavailable</p>
          <p className="empty-state__body">We couldn&apos;t load this creative. Try again shortly.</p>
        </div>
      </PortalShell>
    );
  }

  return (
    <PortalShell title={job.title} back>
      <CreativeReview
        job={job}
        brand={brand}
        clientName={null}
        creatives={creatives}
        approvals={audit.approvals}
        deliveries={audit.deliveries}
      />
    </PortalShell>
  );
}
