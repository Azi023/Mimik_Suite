import { NextResponse } from "next/server";
import { ApiError, fetchBrandBookExport, isApiConfigured } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

interface PdfRouteContext {
  params: Promise<{ id: string }>;
}

/**
 * Same-origin proxy for the brand-book PDF export (mirrors the creative-artifact proxy). The
 * studio "Download PDF" button is a plain browser navigation carrying the httpOnly session
 * cookie — no bearer — so this handler attaches the per-user bearer server-side and streams the
 * PDF back. The API stays bearer-only + team-gated + tenant-scoped.
 */
export async function GET(_request: Request, context: PdfRouteContext): Promise<Response> {
  const { id } = await context.params;
  const token = await getSessionToken();
  if (token === null && !isApiConfigured()) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }
  try {
    const upstream = await fetchBrandBookExport(id, "brand-book.pdf", token ?? undefined);
    const headers = new Headers();
    for (const name of ["content-type", "content-disposition", "content-length"] as const) {
      const value = upstream.headers.get(name);
      if (value !== null) headers.set(name, value);
    }
    headers.set("Cache-Control", "private, no-store");
    return new Response(upstream.body, { status: 200, headers });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 502;
    return NextResponse.json({ error: "Brand book unavailable" }, { status });
  }
}
