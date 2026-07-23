import type { JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { CanvasEditor } from "@/components/canvas/CanvasEditor";
import {
  type ApiBrand,
  type ApiJob,
  type ApiVersionHistory,
  fetchCreativeSvg,
  getBrand,
  getJob,
  listCreativeVersions,
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

function EditorEmptyState({
  sidebar,
  title,
  body,
}: {
  sidebar: Awaited<ReturnType<typeof getSidebarData>>;
  title: string;
  body: string;
}): JSX.Element {
  return (
    <AppShell sidebar={sidebar} title="Canvas editor">
      <div className="creview creview--empty">
        <div className="empty-state">
          <p className="empty-state__title">{title}</p>
          <p className="empty-state__body">{body}</p>
          <Link href="/" className="btn-ghost">
            Back to the board
          </Link>
        </div>
      </div>
    </AppShell>
  );
}

/**
 * B-09: the full-page canvas editor. Loads the creative's SVG master, its brand
 * palette, and the persisted version history server-side with the real bearer,
 * then hands them to the client CanvasEditor. Tenant scoping lives at the data
 * layer — a foreign / missing creative id 404s into a real not-found state.
 */
export default async function CanvasEditPage({
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

  const [sidebar, svg, versions] = await Promise.all([
    getSidebarData(bearer),
    fetchCreativeSvg(id, bearer).catch((): string | null => null),
    listCreativeVersions(id, bearer).catch((): ApiVersionHistory | null => null),
  ]);

  if (svg === null || versions === null) {
    return (
      <EditorEmptyState
        sidebar={sidebar}
        title="Creative not found"
        body="It may have been removed, or it belongs to another workspace."
      />
    );
  }

  // Brand palette for the recolor swatches: versions → job → brand.tokens.colors.
  const job = await getJob(versions.job_id, bearer).catch((): ApiJob | null => null);
  const brand =
    job === null
      ? null
      : await getBrand(job.brand_id, bearer).catch((): ApiBrand | null => null);

  if (job === null || brand === null) {
    return (
      <EditorEmptyState
        sidebar={sidebar}
        title="Brand unavailable"
        body="This creative's brand couldn't be loaded, so the editor can't offer its palette."
      />
    );
  }

  return (
    <AppShell sidebar={sidebar} title="Canvas editor" crumb={job.title}>
      <CanvasEditor
        creativeId={id}
        svg={svg}
        brandColors={brand.tokens.colors}
        initialVersions={versions}
      />
    </AppShell>
  );
}
