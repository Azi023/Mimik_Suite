import { NextResponse } from "next/server";
import {
  ApiError,
  generateBrandKit,
  isApiConfigured,
  type GenerateBrandKitBody,
} from "@/lib/api";
import { getSessionToken } from "@/lib/session";

interface GenerateRouteContext {
  params: Promise<{ id: string }>;
}

function parseGenerateBody(body: unknown): GenerateBrandKitBody | null {
  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    return null;
  }
  const record = body as Record<string, unknown>;
  if (Object.keys(record).length !== 1 || typeof record.overwrite !== "boolean") {
    return null;
  }
  return { overwrite: record.overwrite };
}

/** Same-origin generation proxy; the server-held bearer never reaches browser code. */
export async function POST(request: Request, context: GenerateRouteContext): Promise<Response> {
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
  const options = parseGenerateBody(body);
  if (options === null) {
    return NextResponse.json(
      { error: "Choose whether existing copy may be replaced" },
      { status: 400 },
    );
  }

  try {
    return NextResponse.json(await generateBrandKit(id, options, token ?? undefined));
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 502;
    return NextResponse.json(
      {
        error:
          "Brand kit generation failed. Check the brand brief and text provider, then try again.",
      },
      { status },
    );
  }
}
