import { redirect } from "next/navigation";
import { getMe } from "@/lib/api";

/**
 * Route-gating (defense-in-depth, NOT the security boundary — the DATA is already confined per-role
 * at the API). Steers a `client`-role session away from internal ops surfaces to its bounded portal.
 *
 * Pass the raw session token (may be null on the dev-token path, which is always a team principal, so
 * it is a no-op there). MUST be called from a server component — `redirect()` throws the Next control
 * signal, so it is invoked OUTSIDE the try/catch (never swallow the redirect). A failed `/me` lookup
 * is non-fatal: the page renders and the data layer still protects every query.
 */
export async function redirectClientToPortal(sessionToken: string | null): Promise<void> {
  if (sessionToken === null) {
    return;
  }
  let role: string | null = null;
  try {
    role = (await getMe(sessionToken)).role;
  } catch {
    role = null;
  }
  if (role === "client") {
    redirect("/portal");
  }
}

/**
 * The mirror for portal pages: a non-`client` internal session is redirected to the ops app. Kept
 * lenient — only redirects when the role is positively known AND internal, so the dev-token preview
 * (a team principal) still renders the portal for development.
 */
export async function redirectInternalToApp(sessionToken: string | null): Promise<void> {
  if (sessionToken === null) {
    return;
  }
  let role: string | null = null;
  try {
    role = (await getMe(sessionToken)).role;
  } catch {
    role = null;
  }
  // Only steer away roles we KNOW are internal client-facing mismatches; unknown/team dev preview stays.
  if (role !== null && role !== "client") {
    // Intentionally a no-op for now (dev preview + team-viewing-portal is harmless). Left as the
    // seam for when portal accounts are strictly client-only. See docs/SECURITY_FINDINGS.md H-001.
    return;
  }
}
