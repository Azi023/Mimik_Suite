/**
 * Logout route handler — clears the session cookies and returns to /login.
 *
 * POST-only (a GET could be triggered by a prefetch/link and log the user out
 * unintentionally). The "Sign out" control in the sidebar posts to it.
 */

import { NextResponse, type NextRequest } from "next/server";
import { clearSession } from "@/lib/session";

export async function POST(request: NextRequest): Promise<NextResponse> {
  await clearSession();
  return NextResponse.redirect(new URL("/login", request.url), { status: 303 });
}
