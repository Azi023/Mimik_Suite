import type { JSX } from "react";
import Image from "next/image";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { type ApiCreativeDoc, listCreatives } from "@/lib/api";
import { getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";
import { redirectClientToPortal } from "@/lib/guard";

// The gallery reflects live creative state — always per-request, never a build snapshot.
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
 * Creatives gallery — every job's latest creative (GET /creatives, tenant-scoped) as a
 * fluid reflowing card grid. Each card shows the preview (same-origin proxy — cookies
 * stay httpOnly, bearer added server-side), the headline, and the version, and opens
 * the canvas editor. Session-gated like the board; empty tenants get a real empty state.
 */
export default async function CreativesPage(): Promise<JSX.Element> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  const [sidebar, creatives] = await Promise.all([
    getSidebarData(bearer),
    listCreatives(bearer).catch((): ApiCreativeDoc[] => []),
  ]);

  // Newest first — the creative someone is most likely reviewing sits at the top.
  const sorted = [...creatives].sort((a, b) => b.created_at.localeCompare(a.created_at));

  return (
    <AppShell sidebar={sidebar} title="Creatives">
      {sorted.length === 0 ? (
        <div className="empty-state">
          <p className="empty-state__title">No creatives yet</p>
          <p className="empty-state__body">
            Generate a creative from a job and it shows up here — the latest version of every job,
            in one gallery.
          </p>
        </div>
      ) : (
        <ul className="gallery" aria-label="Creatives">
          {sorted.map((doc) => {
            const headline = doc.manifest.copy_block?.headline;
            const title = headline !== undefined && headline !== "" ? headline : "Untitled";
            return (
              <li key={doc.id}>
                <Link
                  href={`/creatives/${encodeURIComponent(doc.id)}/edit`}
                  className="gallery-card"
                  aria-label={`Edit ${title} (v${doc.version})`}
                >
                  <span className="gallery-card__thumb" aria-hidden="true">
                    <Image
                      src={`/api/creatives/${encodeURIComponent(doc.id)}/preview`}
                      alt=""
                      width={220}
                      height={220}
                      unoptimized
                    />
                  </span>
                  <span className="gallery-card__meta">
                    <span className="gallery-card__title">{title}</span>
                    <span className="gallery-card__version">v{doc.version}</span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </AppShell>
  );
}
