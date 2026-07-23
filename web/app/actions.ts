"use server";

import { revalidatePath } from "next/cache";
import {
  ApiError,
  type ApiGeneratedCreative,
  type ApiJob,
  type ApiJobStatus,
  type ApiVersionHistory,
  type ReviseCreativeBody,
  fetchCreativeSvg,
  generateCreative,
  listCreativeVersions,
  reviseCreative,
  revertCreative,
  transitionJob,
} from "@/lib/api";
import { toReviewDoc } from "@/lib/data";
import { getSessionToken } from "@/lib/session";
import type { CreativeDoc } from "@/lib/view-models";

export type GenerateCreativeActionResult =
  | { ok: true; doc: CreativeDoc }
  | { ok: false; error: string };

/** Run generation server-side so the browser never receives the httpOnly Supabase bearer. */
export async function generateCreativeAction(
  clientId: string,
  topic: string,
  pillar?: string,
): Promise<GenerateCreativeActionResult> {
  const cleanTopic = topic.trim();
  if (clientId === "" || cleanTopic === "") {
    return { ok: false, error: "Choose a client and enter a topic." };
  }
  const token = await getSessionToken();
  const devToken = process.env.NEXT_PUBLIC_DEV_TOKEN;
  if (token === null && (devToken === undefined || devToken === "")) {
    return { ok: false, error: "Your session has expired. Sign in again." };
  }
  try {
    const generated = await generateCreative(
      clientId,
      {
        topic: cleanTopic,
        ...(pillar !== undefined && pillar !== "" ? { pillar } : {}),
        format_key: "ig_post",
      },
      token ?? undefined,
    );
    revalidatePath("/");
    return { ok: true, doc: toReviewDoc(generated.creative) };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 403) {
        return { ok: false, error: "You don't have permission to generate for this client." };
      }
      if (error.status === 404) {
        return { ok: false, error: "This client needs a brand before Generate can run." };
      }
      if (error.status === 422) {
        return { ok: false, error: "Check the topic and creative format, then try again." };
      }
      if (error.status === 502) {
        return { ok: false, error: "Imagery or rendering failed. Try again when providers are available." };
      }
    }
    return { ok: false, error: "Generate failed. Try again." };
  }
}

/* ---------------------------------------------------------------------------
   Canvas editor (B-09) — Apply / Revert run server-side so the browser never
   receives the httpOnly Supabase bearer (same model as the review actions).
--------------------------------------------------------------------------- */

/** The new head after a canvas mutation: its id, its rendered SVG, and the refreshed rail. */
export type CanvasEditActionResult =
  | { ok: true; creativeId: string; version: number; svg: string; versions: ApiVersionHistory }
  | { ok: false; error: string };

/** Resolve the bearer exactly like generateCreativeAction: session first, dev token fallback. */
async function resolveCanvasBearer(): Promise<string | undefined | null> {
  const token = await getSessionToken();
  const devToken = process.env.NEXT_PUBLIC_DEV_TOKEN;
  if (token === null && (devToken === undefined || devToken === "")) return null;
  return token ?? undefined;
}

/** Post-mutation bundle: fetch the new head's SVG master + the refreshed version history. */
async function bundleHead(
  result: ApiGeneratedCreative,
  bearer: string | undefined,
): Promise<CanvasEditActionResult> {
  const [svg, versions] = await Promise.all([
    fetchCreativeSvg(result.creative.id, bearer),
    listCreativeVersions(result.creative.id, bearer),
  ]);
  return {
    ok: true,
    creativeId: result.creative.id,
    version: result.creative.version,
    svg,
    versions,
  };
}

function canvasErrorMessage(error: unknown, verb: string): string {
  if (error instanceof ApiError) {
    if (error.status === 403) return `You don't have permission to ${verb} this creative.`;
    if (error.status === 404) return "Creative not found. It may belong to another workspace.";
    if (error.status === 422) return "The change was rejected as invalid. Adjust it and retry.";
    if (error.status === 502) {
      return "Rendering failed. Try again when providers are available.";
    }
  }
  return `Could not ${verb} the creative. Try again.`;
}

/** POST /creatives/{id}/revise with the typed canvas body, then return the new head. */
export async function reviseCreativeCanvasAction(
  creativeId: string,
  body: ReviseCreativeBody,
): Promise<CanvasEditActionResult> {
  const bearer = await resolveCanvasBearer();
  if (bearer === null) {
    return { ok: false, error: "Your session has expired. Sign in again." };
  }
  try {
    const result = await reviseCreative(creativeId, body, bearer);
    const bundle = await bundleHead(result, bearer);
    revalidatePath(`/creatives/${creativeId}/edit`);
    return bundle;
  } catch (error) {
    return { ok: false, error: canvasErrorMessage(error, "revise") };
  }
}

/* ---------------------------------------------------------------------------
   Board transitions (A-06) — drag-and-drop moves run server-side so the browser
   never receives the httpOnly Supabase bearer (same model as the actions above).
--------------------------------------------------------------------------- */

export type TransitionJobActionResult =
  | { ok: true; job: ApiJob }
  | { ok: false; error: string; status?: number };

/**
 * POST /ops/jobs/{id}/transition with the bearer resolved server-side. A 409 (illegal
 * transition) returns the API's own `detail` plus `status` so the board can snap the
 * card back and surface the reason; other failures return a canned message.
 */
export async function transitionJobAction(
  jobId: string,
  toStatus: ApiJobStatus,
  note?: string,
): Promise<TransitionJobActionResult> {
  const bearer = await resolveCanvasBearer();
  if (bearer === null) {
    return { ok: false, error: "Your session has expired. Sign in again." };
  }
  try {
    const result = await transitionJob(jobId, toStatus, note, bearer);
    revalidatePath("/");
    return { ok: true, job: result.job };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 409) {
        // The server's detail names the rejected move, e.g. "Illegal transition archived -> draft".
        return { ok: false, error: error.message, status: 409 };
      }
      if (error.status === 403) {
        return { ok: false, error: "You don't have permission to move this job.", status: 403 };
      }
      if (error.status === 404) {
        return { ok: false, error: "Job not found. It may belong to another workspace.", status: 404 };
      }
      return { ok: false, error: "Could not move the job. Try again.", status: error.status };
    }
    return { ok: false, error: "Could not move the job. Try again." };
  }
}

/** POST /creatives/{id}/revert to an older version, then return the new head. */
export async function revertCreativeAction(
  creativeId: string,
  toCreativeId: string,
): Promise<CanvasEditActionResult> {
  const bearer = await resolveCanvasBearer();
  if (bearer === null) {
    return { ok: false, error: "Your session has expired. Sign in again." };
  }
  try {
    const result = await revertCreative(creativeId, toCreativeId, bearer);
    const bundle = await bundleHead(result, bearer);
    revalidatePath(`/creatives/${creativeId}/edit`);
    return bundle;
  } catch (error) {
    return { ok: false, error: canvasErrorMessage(error, "revert") };
  }
}
