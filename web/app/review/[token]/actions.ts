"use server";

import { revalidatePath } from "next/cache";
import { ApiError, type MagicApprovalSubmission, submitMagicApproval } from "@/lib/api";

/**
 * Server action for the NO-LOGIN magic-link review flow. Authorization here is the magic-link token
 * (carried in the body), NOT a session cookie — so it runs server-side purely to keep the API call
 * off the browser (no CORS surface) and consistent with the in-app path. The backend re-verifies the
 * signed, single-job grant on every call (api/routers/approvals.py::magic_approval).
 */

export interface ReviewActionResult {
  ok: boolean;
  error?: string;
}

export async function submitMagicApprovalAction(
  body: MagicApprovalSubmission,
): Promise<ReviewActionResult> {
  try {
    await submitMagicApproval(body);
    revalidatePath(`/review/${body.token}`);
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 401) {
        return { ok: false, error: "This review link has expired. Ask your team for a fresh one." };
      }
      if (error.status === 409) {
        return { ok: false, error: "This creative is already decided — reload to see the latest." };
      }
      if (error.status === 404) {
        return { ok: false, error: "This creative is no longer available." };
      }
      if (error.status === 422) {
        return { ok: false, error: "That request wasn't valid — check your change pins and try again." };
      }
    }
    return { ok: false, error: "Could not submit your decision. Your notes are kept — try again." };
  }
}
