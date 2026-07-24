import { NextResponse } from "next/server";
import { ApiError, fetchAssetRaw, isApiConfigured } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

interface AssetRawRouteContext {
  params: Promise<{ id: string }>;
}

/**
 * Same-origin proxy for a brand asset's raw bytes (mirrors the creative-artifact proxy):
 * the browser `<img>` hits this route, which attaches the per-user Supabase bearer (or the
 * dev bootstrap token) server-side and streams the upstream `/assets/{id}/raw` bytes back.
 * The bearer never reaches the client, and the backend stays the tenant/brand + team gate.
 */
export async function GET(_request: Request, context: AssetRawRouteContext): Promise<Response> {
  const { id } = await context.params;
  const token = await getSessionToken();
  if (token === null && !isApiConfigured()) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }
  try {
    const upstream = await fetchAssetRaw(id, token ?? undefined);
    const headers = new Headers();
    for (const name of ["content-type", "content-disposition", "content-length"] as const) {
      const value = upstream.headers.get(name);
      if (value !== null) headers.set(name, value);
    }
    headers.set("Cache-Control", "private, no-store");
    return new Response(upstream.body, { status: 200, headers });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 502;
    return NextResponse.json({ error: "Asset unavailable" }, { status });
  }
}
