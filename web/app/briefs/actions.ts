"use server";

import { revalidatePath } from "next/cache";
import {
  ApiError,
  type ApiBriefSections,
  reviseBrief,
  signoffBrief,
  updateBriefSections,
} from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/**
 * Server actions for the brand-brief editor. Every mutation runs SERVER-SIDE so the per-user
 * Supabase bearer (an httpOnly cookie, never in the browser bundle) authorizes it — the token is
 * read via `getSessionToken` and threaded into the API call. Same pattern as the members panel.
 *
 * The freeze invariant is the product's scope-lock: a signed-off brief is immutable, so edits after
 * sign-off surface as 409s here and the UI routes the user to "Revise" (mint a new version) instead.
 */

export interface BriefActionResult {
  ok: boolean;
  error?: string;
}

export async function saveBrief(
  briefId: string,
  sections: ApiBriefSections,
): Promise<BriefActionResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    await updateBriefSections(briefId, sections, token);
    revalidatePath(`/briefs/${briefId}`);
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 409) {
        return { ok: false, error: "This brief is frozen. Revise it to make changes." };
      }
      if (error.status === 403) {
        return { ok: false, error: "You don't have permission to edit this brief." };
      }
      if (error.status === 404) {
        return { ok: false, error: "This brief no longer exists." };
      }
    }
    return { ok: false, error: "Could not save your changes. Try again." };
  }
}

export async function signOffBrief(
  briefId: string,
  signedOffBy: string,
): Promise<BriefActionResult> {
  const name = signedOffBy.trim();
  if (name === "") {
    return { ok: false, error: "Enter who is signing off." };
  }
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    await signoffBrief(briefId, name, token);
    revalidatePath(`/briefs/${briefId}`);
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      return { ok: false, error: "This brief is already signed off." };
    }
    return { ok: false, error: "Could not sign off. Try again." };
  }
}

export interface ReviseResult extends BriefActionResult {
  /** The id of the freshly-minted draft version, on success. */
  newBriefId?: string;
}

export async function reviseBriefAction(briefId: string): Promise<ReviseResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    const created = await reviseBrief(briefId, token);
    revalidatePath("/briefs");
    return { ok: true, newBriefId: created.id };
  } catch {
    return { ok: false, error: "Could not create a new version. Try again." };
  }
}
