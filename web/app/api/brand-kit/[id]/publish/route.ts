import { NextResponse } from "next/server";
import { ApiError, isApiConfigured, setBrandBookPublished } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

interface PublishRouteContext {
  params: Promise<{ id: string }>;
}

/** Narrow the request body to `{ publish: boolean }` — anything else is a 400. */
function parsePublishFlag(body: unknown): boolean | null {
  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    return null;
  }
  const flag = (body as Record<string, unknown>).publish;
  return typeof flag === "boolean" ? flag : null;
}

/**
 * Same-origin proxy for the brand-book publish toggle (mirrors the creative-artifact
 * proxy): the browser POSTs `{ publish: boolean }` here; this handler attaches the
 * per-user Supabase bearer (or the dev bootstrap token) server-side and forwards to
 * `POST /brands/{id}/brand-book/publish|unpublish`. The bearer never reaches the client,
 * and the backend stays the tenant + team gate.
 */
export async function POST(request: Request, context: PublishRouteContext): Promise<Response> {
  const { id } = await context.params;
  const token = await getSessionToken();
  if (token === null && !isApiConfigured()) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }
  const publish = parsePublishFlag(body);
  if (publish === null) {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  try {
    const share = await setBrandBookPublished(id, publish, token ?? undefined);
    return NextResponse.json(share);
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 502;
    return NextResponse.json({ error: "Publish state unchanged" }, { status });
  }
}
