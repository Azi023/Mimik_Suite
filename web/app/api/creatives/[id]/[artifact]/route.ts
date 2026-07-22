import { NextResponse } from "next/server";
import {
  ApiError,
  type CreativeArtifactKind,
  fetchCreativeArtifact,
  isApiConfigured,
} from "@/lib/api";
import { getSessionToken } from "@/lib/session";

interface ArtifactRouteContext {
  params: Promise<{ id: string; artifact: string }>;
}

const ARTIFACTS: ReadonlySet<string> = new Set(["preview", "svg", "psd"]);

/** Same-origin proxy: browser cookies stay httpOnly while FastAPI still receives a bearer. */
export async function GET(
  _request: Request,
  context: ArtifactRouteContext,
): Promise<Response> {
  const { id, artifact } = await context.params;
  if (!ARTIFACTS.has(artifact)) {
    return NextResponse.json({ error: "Artifact not found" }, { status: 404 });
  }
  const token = await getSessionToken();
  if (token === null && !isApiConfigured()) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }
  try {
    const upstream = await fetchCreativeArtifact(
      id,
      artifact as CreativeArtifactKind,
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
    return NextResponse.json({ error: "Artifact unavailable" }, { status });
  }
}
