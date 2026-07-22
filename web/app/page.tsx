import type { JSX } from "react";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { BoardView } from "@/components/BoardView";
import { getBoardData, getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";
import { redirectClientToPortal } from "@/lib/guard";

// The board reflects live job state — always render per-request, never a build-time
// snapshot (and never let `next build` try to reach the API).
export const dynamic = "force-dynamic";

/**
 * Whether a DEV-ONLY unauthenticated fallback is allowed to render the board.
 *
 * True only when running in dev (`APP_ENV` unset or "dev") AND a build-time dev token
 * is configured. In that mode the board renders against the bootstrap token without a
 * Supabase login — the pre-auth developer convenience. In every other case (prod, or no
 * dev token) an unauthenticated request is redirected to /login. Never a prod path.
 */
function devFallbackAllowed(): boolean {
  const appEnv = process.env.APP_ENV;
  const isDev = appEnv === undefined || appEnv === "" || appEnv === "dev";
  const hasDevToken =
    process.env.NEXT_PUBLIC_DEV_TOKEN !== undefined && process.env.NEXT_PUBLIC_DEV_TOKEN !== "";
  return isDev && hasDevToken;
}

/** Board view — the default dashboard screen, gated behind a Supabase session.
 *
 * Auth gate: read the server-side session token. When there is no session AND the
 * dev fallback is not allowed, redirect to /login. Otherwise the token (or `undefined`,
 * which triggers the dev-token fallback inside `lib/data`) is threaded into the data
 * layer so API fetches carry the REAL user's bearer.
 *
 * Data comes from the `lib/data.ts` facade. Empty responses and request failures stay
 * empty. The server component fetches; `BoardView` adds selection and filtering. */
export default async function BoardPage(): Promise<JSX.Element> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }

  // `?? undefined` keeps the dev-fallback path (dev token) usable when there is no
  // session but the fallback is allowed.
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);
  const [{ pillars, jobs, reviewDoc }, sidebar] = await Promise.all([
    getBoardData(bearer),
    getSidebarData(bearer),
  ]);

  return (
    <AppShell sidebar={sidebar} title="Board" crumb="This week · approvals">
      <BoardView
        pillars={pillars}
        jobs={jobs}
        reviewDoc={reviewDoc}
        clients={sidebar.groups.flatMap((group) =>
          group.projects.map((project) => ({ id: project.id, name: project.name })),
        )}
        initialClientId={sidebar.activeClient?.id ?? null}
      />
    </AppShell>
  );
}
