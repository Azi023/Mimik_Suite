import { NextResponse } from "next/server";
import {
  ApiError,
  isApiConfigured,
  type ApiBrandDiscoveryTextField,
  type ApiCreativeDirectionTextField,
  type UpdateBrandKitBody,
  updateBrandKit,
} from "@/lib/api";
import { getSessionToken } from "@/lib/session";

interface BrandKitRouteContext {
  params: Promise<{ id: string }>;
}

const DISCOVERY_FIELDS = new Set<ApiBrandDiscoveryTextField>([
  "purpose",
  "mission",
  "vision",
  "personality",
  "tone_of_voice",
  "key_usp",
  "visual_competitor_analysis",
  "existing_brand_review",
  "timeline",
]);

const DIRECTION_FIELDS = new Set<ApiCreativeDirectionTextField>([
  "palette_rationale",
  "visual_tone",
  "personality_alignment",
  "competitor_differentiation",
]);

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

/** Accept exactly one editable text field so the proxy cannot broaden a UI save. */
function parseKitPatch(body: unknown): UpdateBrandKitBody | null {
  const root = record(body);
  const kit = record(root?.kit);
  if (root === null || kit === null || Object.keys(root).length !== 1) return null;
  const sections = Object.entries(kit);
  if (sections.length !== 1) return null;

  const [section, rawPatch] = sections[0];
  const patch = record(rawPatch);
  if (patch === null) return null;
  const fields = Object.entries(patch);
  if (fields.length !== 1) return null;
  const [field, value] = fields[0];
  if (value !== null && typeof value !== "string") return null;

  if (section === "discovery" && DISCOVERY_FIELDS.has(field as ApiBrandDiscoveryTextField)) {
    const discoveryField = field as ApiBrandDiscoveryTextField;
    return { kit: { discovery: { [discoveryField]: value } } };
  }
  if (section === "direction" && DIRECTION_FIELDS.has(field as ApiCreativeDirectionTextField)) {
    const directionField = field as ApiCreativeDirectionTextField;
    return { kit: { direction: { [directionField]: value } } };
  }
  return null;
}

/**
 * Same-origin text-edit proxy. It attaches the server-held bearer, then forwards the
 * one-field kit patch to the tenant-scoped API route.
 */
export async function PATCH(request: Request, context: BrandKitRouteContext): Promise<Response> {
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
  const patch = parseKitPatch(body);
  if (patch === null) {
    return NextResponse.json({ error: "Invalid brand-kit field" }, { status: 400 });
  }

  try {
    return NextResponse.json(await updateBrandKit(id, patch, token ?? undefined));
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 502;
    return NextResponse.json({ error: "Brand-kit field unchanged" }, { status });
  }
}
