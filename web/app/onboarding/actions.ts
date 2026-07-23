"use server";

import { revalidatePath } from "next/cache";
import {
  ApiError,
  type ApiBrandTokens,
  type CreateBrandBody,
  createBrand,
  createBrief,
  createClient,
  createPillar,
  uploadReferenceAsset,
} from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/**
 * Onboarding submit. Runs SERVER-SIDE so the per-user Supabase bearer (httpOnly cookie) authorizes
 * every call. Sequence: client -> brand (with tokens + client-shared reference links) -> content
 * pillars -> reference-image uploads -> auto-draft a brief. Client + brand + brief are the critical
 * path (a failure aborts); pillars and uploads are best-effort and surface as warnings so a single
 * flaky upload never loses the whole onboarding.
 */

export interface OnboardingPayload {
  client: { name: string; industry: string; contactEmail: string };
  brand: {
    name: string;
    slug: string;
    niche: string;
    targetAudience: string;
    brandVoice: string;
    imageryStyle: string;
    toneKeywords: string[];
    dos: string[];
    donts: string[];
    handles: Record<string, string>;
  };
  kit: {
    colors: { name: string; hex: string; usage: string }[];
    headingFont: string;
    bodyFont: string;
    logoNotes: string;
    logoMinSize: string;
  };
  pillars: { presets: string[]; custom: { name: string; description: string }[] };
  references: { url: string; source: string; note: string }[];
}

export interface OnboardingResult {
  ok: boolean;
  error?: string;
  /** The auto-drafted brief to land on, on success. */
  briefId?: string;
  /** Non-fatal issues (a pillar or upload that didn't take). */
  warnings?: string[];
}

/** Empty/whitespace -> null, to match the API's `str | None` fields. */
function nn(value: string): string | null {
  const t = value.trim();
  return t === "" ? null : t;
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

function buildTokens(kit: OnboardingPayload["kit"]): ApiBrandTokens {
  const minSize = Number(kit.logoMinSize.trim());
  return {
    colors: kit.colors
      .filter((c) => c.hex.trim() !== "")
      .map((c) => ({ name: c.name.trim() === "" ? c.hex : c.name.trim(), hex: c.hex, usage: nn(c.usage) })),
    typography: { heading_font: nn(kit.headingFont), body_font: nn(kit.bodyFont), hierarchy: [] },
    logo: {
      ref: null,
      clear_space: null,
      min_size_px: Number.isFinite(minSize) && minSize > 0 ? minSize : null,
      assessment: nn(kit.logoNotes),
    },
  };
}

export async function createOnboarding(formData: FormData): Promise<OnboardingResult> {
  const token = await getSessionToken();
  const devToken = process.env.NEXT_PUBLIC_DEV_TOKEN;
  if (token === null && (devToken === undefined || devToken === "")) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  // Match every other write action: when there is no per-user session, let the
  // API client fall back to NEXT_PUBLIC_DEV_TOKEN (dev-only) via `resolveBearer`
  // by passing `token ?? undefined`. Onboarding previously hard-failed here, which
  // blocked the dev/audit flow at the first authorized write.
  const bearer = token ?? undefined;

  let payload: OnboardingPayload;
  try {
    payload = JSON.parse(String(formData.get("payload") ?? "")) as OnboardingPayload;
  } catch {
    return { ok: false, error: "Something went wrong reading the form. Try again." };
  }

  if (payload.client.name.trim() === "" || payload.brand.name.trim() === "") {
    return { ok: false, error: "Client name and brand name are required." };
  }

  const files = formData
    .getAll("refFiles")
    .filter((f): f is File => f instanceof File && f.size > 0);

  const warnings: string[] = [];

  try {
    const client = await createClient(
      {
        name: payload.client.name.trim(),
        industry: nn(payload.client.industry),
        contact_email: nn(payload.client.contactEmail),
      },
      bearer,
    );

    const brandBody: CreateBrandBody = {
      client_id: client.id,
      name: payload.brand.name.trim(),
      slug: slugify(payload.brand.slug.trim() === "" ? payload.brand.name : payload.brand.slug),
      niche: nn(payload.brand.niche),
      target_audience: nn(payload.brand.targetAudience),
      brand_voice: nn(payload.brand.brandVoice),
      imagery_style: nn(payload.brand.imageryStyle),
      tone_keywords: payload.brand.toneKeywords,
      dos: payload.brand.dos,
      donts: payload.brand.donts,
      handles: payload.brand.handles,
      tokens: buildTokens(payload.kit),
      references: payload.references
        .filter((r) => r.url.trim() !== "")
        .map((r) => ({ url: r.url.trim(), source: nn(r.source), note: nn(r.note) })),
    };
    const brand = await createBrand(brandBody, bearer);

    for (const key of payload.pillars.presets) {
      try {
        await createPillar({ client_id: client.id, preset_key: key }, bearer);
      } catch {
        warnings.push(`Couldn't add the "${key}" pillar — add it later from the client.`);
      }
    }
    for (const custom of payload.pillars.custom) {
      if (custom.name.trim() === "") continue;
      try {
        await createPillar(
          { client_id: client.id, name: custom.name.trim(), description: nn(custom.description) },
          bearer,
        );
      } catch {
        warnings.push(`Couldn't add the custom pillar "${custom.name.trim()}".`);
      }
    }

    for (const file of files) {
      try {
        await uploadReferenceAsset(brand.id, file, bearer);
      } catch {
        warnings.push(`Couldn't upload "${file.name}" — add it later from the asset library.`);
      }
    }

    const brief = await createBrief(brand.id, bearer);
    revalidatePath("/briefs");
    return { ok: true, briefId: brief.id, warnings };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 403) {
        return { ok: false, error: "You don't have permission to onboard a client." };
      }
      if (error.status === 422) {
        return { ok: false, error: "Some details were invalid — check the form and try again." };
      }
    }
    return { ok: false, error: "Could not complete onboarding. Try again." };
  }
}
