"use server";

import { revalidatePath } from "next/cache";
import {
  ApiError,
  type ApprovalSubmission,
  mintMagicLink,
  submitApproval,
} from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/**
 * Server action for the creative review + approval loop. Every decision (approve /
 * request-change / reject / comment) runs SERVER-SIDE so the per-user Supabase bearer (an
 * httpOnly cookie, never in the browser bundle) authorizes it — read via `getSessionToken`
 * and threaded into the API call. Same pattern as the brief + brand-kit editors.
 *
 * The backend records an append-only, attributed Approval row (the audit trail) and fires the
 * side-effects: approve → auto-archive to Drive; request_change → spawn an ops task. We
 * revalidate the review page so the freshly-recorded action shows in the thread on refresh.
 */

export interface ReviewActionResult {
  ok: boolean;
  error?: string;
}

export async function submitReviewAction(
  body: ApprovalSubmission,
): Promise<ReviewActionResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    await submitApproval(body, token);
    revalidatePath(`/jobs/${body.job_id}/review`);
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 409) {
        return { ok: false, error: "This creative is already decided — reload to see the latest." };
      }
      if (error.status === 403) {
        return { ok: false, error: "You don't have permission to review this creative." };
      }
      if (error.status === 404) {
        return { ok: false, error: "This job or creative no longer exists." };
      }
      if (error.status === 422) {
        return { ok: false, error: "That request wasn't valid — check your change pins and try again." };
      }
    }
    return { ok: false, error: "Could not submit your decision. Your notes are kept — try again." };
  }
}

export interface MintLinkResult {
  ok: boolean;
  /** The magic-link token, on success — the caller builds the shareable /review/{token} URL. */
  token?: string;
  error?: string;
}

/** Mint a shareable, no-login client review link for a job (72h). Team-gated at the API. */
export async function mintMagicLinkAction(jobId: string): Promise<MintLinkResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    const result = await mintMagicLink(jobId, 72, token);
    return { ok: true, token: result.token };
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return { ok: false, error: "You don't have permission to share this creative." };
    }
    return { ok: false, error: "Could not create a share link. Try again." };
  }
}
