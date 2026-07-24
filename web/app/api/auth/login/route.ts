/**
 * Login route handler — exchanges email + password for a Supabase session.
 *
 * The browser POSTs form-encoded credentials here (never directly to Supabase), so the
 * anon key and the issued tokens are handled entirely server-side. On success the session
 * lands in httpOnly cookies (see `lib/session`) and we redirect to the board; on failure
 * we redirect back to /login with an `?error=` the page renders inline.
 */

import { NextResponse, type NextRequest } from "next/server";
import { isSupabaseConfigured, sanitizeNextPath, signInWithPassword } from "@/lib/session";

/** Bounce back to /login with a URL-safe error message, preserving the `next` return path. */
function loginError(request: NextRequest, message: string, next: string): NextResponse {
  const url = new URL("/login", request.url);
  url.searchParams.set("error", message);
  if (next !== "") {
    url.searchParams.set("next", next);
  }
  return NextResponse.redirect(url, { status: 303 });
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const form = await request.formData();
  // Same-origin relative path only (open-redirect guard); "" means fall back to the board.
  const next = sanitizeNextPath(
    typeof form.get("next") === "string" ? (form.get("next") as string) : "",
  );

  if (!isSupabaseConfigured()) {
    return loginError(request, "Authentication is not configured on this server.", next);
  }

  const email = form.get("email");
  const password = form.get("password");
  if (typeof email !== "string" || typeof password !== "string" || email === "" || password === "") {
    return loginError(request, "Enter both email and password.", next);
  }

  const result = await signInWithPassword(email, password);
  if (!result.ok) {
    return loginError(request, result.error, next);
  }

  // 303 so the browser follows with a GET. Return to the in-flight path (e.g. invite-accept) if one
  // was carried through the round-trip, else the (now-authenticated) board.
  return NextResponse.redirect(new URL(next !== "" ? next : "/", request.url), { status: 303 });
}
