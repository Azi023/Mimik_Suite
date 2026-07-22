"use server";

import { revalidatePath } from "next/cache";
import { ApiError, generateCreative } from "@/lib/api";
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
