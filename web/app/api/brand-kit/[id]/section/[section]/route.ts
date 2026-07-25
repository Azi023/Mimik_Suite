import { NextResponse } from "next/server";
import { isKitSectionKey } from "@/components/brand-kit/registry";
import { ApiError, fetchBrandBookExport, isApiConfigured } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

interface SectionRouteContext {
  params: Promise<{ id: string; section: string }>;
}

/**
 * Same-origin proxy for a brand-book section PNG export (mirrors the PDF proxy). The studio
 * "Export PNG" links are plain browser navigations carrying the httpOnly session cookie — no
 * bearer — so this handler attaches the per-user bearer server-side and streams the PNG back.
 * The section key is validated against the known chapters before forwarding (the API also 422s
 * an unknown key, but rejecting here avoids a needless round-trip). The API stays bearer-only.
 */
export async function GET(_request: Request, context: SectionRouteContext): Promise<Response> {
  const { id, section } = await context.params;
  if (!isKitSectionKey(section)) {
    return NextResponse.json({ error: "Unknown section" }, { status: 404 });
  }
  const token = await getSessionToken();
  if (token === null && !isApiConfigured()) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }
  try {
    const upstream = await fetchBrandBookExport(
      id,
      `brand-book/${encodeURIComponent(section)}.png`,
      token ?? undefined,
    );
    const headers = new Headers();
    for (const name of ["content-type", "content-disposition", "content-length"] as const) {
      const value = upstream.headers.get(name);
      if (value !== null) headers.set(name, value);
    }
    headers.set("Cache-Control", "private, no-store");
    return new Response(upstream.body, { status: 200, headers });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 502;
    return NextResponse.json({ error: "Section unavailable" }, { status });
  }
}
