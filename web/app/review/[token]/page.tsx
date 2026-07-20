import type { JSX } from "react";
import { CreativeReview } from "@/components/CreativeReview";
import { PortalShell } from "@/components/PortalShell";
import { type PortalBundle, getPortalSession } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * No-login magic-link review — the frictionless, WhatsApp-shareable client path. The `[token]` in the
 * URL is a signed, expiring, single-job capability; the server resolves it via POST /portal/session
 * (which returns ONLY that one job's bundle) and hands it to the SAME review component the team uses.
 * Decisions post back through the magic grant (see actions.ts + api/routers/approvals.py). No session,
 * no other jobs, no enumeration — the token is the whole authority (docs/SECURITY_FINDINGS.md D-001).
 */
export default async function MagicReviewPage({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<JSX.Element> {
  const { token } = await params;

  const bundle = await getPortalSession(token).catch((): PortalBundle | null => null);

  if (bundle === null || bundle.brand === null) {
    return (
      <PortalShell title="Creative review" bare>
        <div className="empty-state">
          <p className="empty-state__title">This review link isn&apos;t valid</p>
          <p className="empty-state__body">
            It may have expired or already been used. Ask your Mimik contact to send a fresh link.
          </p>
        </div>
      </PortalShell>
    );
  }

  return (
    <PortalShell title={bundle.job.title} bare>
      <CreativeReview
        job={bundle.job}
        brand={bundle.brand}
        clientName={null}
        creatives={bundle.creatives}
        approvals={bundle.approvals}
        deliveries={bundle.deliveries}
        magicToken={token}
      />
    </PortalShell>
  );
}
