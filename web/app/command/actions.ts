"use server";

import { revalidatePath } from "next/cache";
import { ApiError, type EnqueueGenerationBody, enqueueGeneration } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/**
 * Server action for the Command Center enqueue form. Runs SERVER-SIDE so the per-user Supabase
 * bearer (httpOnly cookie, never in the client bundle) authorizes it — enqueue is team-gated at
 * the API, so a client-role session simply 403s here. The topic is the only free-text field; it
 * fills a constrained slot on the request, never a system prompt (constraint #3).
 */

export interface EnqueueResult {
  ok: boolean;
  error?: string;
}

export async function enqueueGenerationAction(
  body: EnqueueGenerationBody,
): Promise<EnqueueResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  if (body.client_id.trim() === "") {
    return { ok: false, error: "Pick a client first." };
  }
  if (body.topic.trim() === "") {
    return { ok: false, error: "Give the generation a topic." };
  }
  try {
    await enqueueGeneration(body, token);
    revalidatePath("/command");
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 403) {
        return { ok: false, error: "You don't have permission to queue generations." };
      }
      if (error.status === 404) {
        return { ok: false, error: "That client no longer exists." };
      }
      if (error.status === 422) {
        return { ok: false, error: "That wasn't valid — check the topic and format, then try again." };
      }
    }
    return { ok: false, error: "Could not queue the generation. Try again." };
  }
}
