"use server";

import { acceptInvitation, ApiError } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/**
 * Server action for redeeming an invitation. The accept MUST run server-side: the per-user Supabase
 * bearer lives in an httpOnly cookie (never in the browser bundle), is read here via
 * `getSessionToken`, and is threaded into `POST /invitations/accept`. The backend is the authority —
 * it re-verifies the signed token, the invite's live status/expiry, and that the caller's verified
 * email matches the invited email — so this action only classifies the outcome for the UI.
 */

/** The taxonomy the panel switches on to pick a heading + the right recovery CTA. */
export type AcceptErrorKind =
  | "session" // no/invalid session — sign in (as the invited email) again
  | "invalid" // bad or unknown token
  | "expired" // invite window elapsed
  | "revoked" // invite was pulled by an admin
  | "already_accepted" // the invite itself is already consumed
  | "already_account" // this identity is already provisioned — just go in
  | "email_mismatch" // signed in as a different email than invited
  | "generic";

export interface AcceptInvitationResult {
  ok: boolean;
  /** The backend's error `detail`, surfaced verbatim (never fabricated). */
  error?: string;
  kind?: AcceptErrorKind;
}

export async function acceptInvitationAction(token: string): Promise<AcceptInvitationResult> {
  const trimmed = token.trim();
  if (trimmed === "") {
    return { ok: false, error: "This invitation link is missing its token.", kind: "invalid" };
  }

  const sessionToken = await getSessionToken();
  if (sessionToken === null) {
    return {
      ok: false,
      error: "Your session has expired — sign in with the invited email to accept.",
      kind: "session",
    };
  }

  try {
    await acceptInvitation(trimmed, sessionToken);
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      const detail = error.message;
      const lower = detail.toLowerCase();
      if (error.status === 401) return { ok: false, error: detail, kind: "session" };
      if (error.status === 403) return { ok: false, error: detail, kind: "email_mismatch" };
      if (error.status === 410) return { ok: false, error: detail, kind: "expired" };
      if (error.status === 400 || error.status === 404) {
        return { ok: false, error: detail, kind: "invalid" };
      }
      if (error.status === 409) {
        // 409 covers three distinct DB states; the detail string tells them apart.
        if (lower.includes("already has an account")) {
          return { ok: false, error: detail, kind: "already_account" };
        }
        if (lower.includes("accepted")) return { ok: false, error: detail, kind: "already_accepted" };
        if (lower.includes("revoked")) return { ok: false, error: detail, kind: "revoked" };
        if (lower.includes("expired")) return { ok: false, error: detail, kind: "expired" };
        return { ok: false, error: detail, kind: "generic" };
      }
      return { ok: false, error: detail, kind: "generic" };
    }
    // Network / timeout — the API was never reached.
    return {
      ok: false,
      error: "Could not reach the server. Check your connection and try again.",
      kind: "generic",
    };
  }
}
