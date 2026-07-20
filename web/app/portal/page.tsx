import type { JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { PortalShell } from "@/components/PortalShell";
import { type ApiJob, type ApiJobStatus, listJobs } from "@/lib/api";
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

const STATUS_LABEL: Record<ApiJobStatus, string> = {
  draft: "Draft",
  generating: "In production",
  internal_review: "In review",
  client_review: "Ready for you",
  approved: "Approved",
  delivered: "Delivered",
  archived: "Archived",
  blocked: "On hold",
};

/** Statuses the client should act on show first. */
const AWAITING: ReadonlySet<ApiJobStatus> = new Set<ApiJobStatus>(["client_review"]);

/**
 * Client portal index — the bounded review surface. Lists ONLY the signed-in client's own jobs
 * (the API confines a client principal to its own client_id at the data layer). "Ready for you"
 * jobs sort to the top. Each opens a stripped-down review reusing the same review components the
 * team uses. Low-privilege: no ops board, no other clients, no internal nav (constraint #3).
 */
export default async function PortalIndexPage(): Promise<JSX.Element> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;

  const jobs = await listJobs(undefined, bearer).catch((): ApiJob[] => []);
  // Surface actionable work first, then the rest by newest.
  const sorted = [...jobs].sort((a, b) => {
    const aw = AWAITING.has(a.status) ? 0 : 1;
    const bw = AWAITING.has(b.status) ? 0 : 1;
    if (aw !== bw) return aw - bw;
    return b.created_at.localeCompare(a.created_at);
  });

  return (
    <PortalShell title="Your creatives">
      {sorted.length === 0 ? (
        <div className="empty-state">
          <p className="empty-state__title">Nothing to review yet</p>
          <p className="empty-state__body">
            When your team shares a creative for approval, it will appear here.
          </p>
        </div>
      ) : (
        <ul className="portal-list">
          {sorted.map((job) => {
            const awaiting = AWAITING.has(job.status);
            return (
              <li key={job.id}>
                <Link href={`/portal/jobs/${job.id}`} className="portal-card">
                  <span className="portal-card__title">{job.title}</span>
                  <span className="portal-card__meta">{job.format_key}</span>
                  <span
                    className={`portal-card__status${awaiting ? " portal-card__status--awaiting" : ""}`}
                  >
                    {STATUS_LABEL[job.status]}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </PortalShell>
  );
}
