"use server";

import { revalidatePath } from "next/cache";
import {
  createInvitation,
  revokeInvitation,
  updateAccount,
  ApiError,
  type ApiUserAccount,
} from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/**
 * Server actions for the admin panel. Mutations run SERVER-SIDE so the per-user Supabase
 * bearer (an httpOnly cookie, never in the browser bundle) authorizes them — the token is
 * read via `getSessionToken` and threaded into the API call. This is stricter than the
 * board's client-side fetch and is the correct pattern for a security-sensitive surface.
 */

export interface InviteResult {
  ok: boolean;
  /** The copyable accept-link on success (email delivery is deferred). */
  acceptUrl?: string;
  error?: string;
}

export async function inviteMember(formData: FormData): Promise<InviteResult> {
  const email = String(formData.get("email") ?? "").trim();
  const role = String(formData.get("role") ?? "").trim();
  if (email === "" || role === "") {
    return { ok: false, error: "Email and role are required." };
  }

  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }

  try {
    const created = await createInvitation({ email, role }, token);
    revalidatePath("/members");
    return { ok: true, acceptUrl: created.accept_url };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 409) return { ok: false, error: "A pending invite for this email already exists." };
      if (error.status === 403) return { ok: false, error: "You are not allowed to invite that role." };
      if (error.status === 422) return { ok: false, error: "That role is not recognized." };
    }
    return { ok: false, error: "Could not send the invite. Try again." };
  }
}

export interface UpdateAccountResult {
  ok: boolean;
  /** The updated account on success — the row reflects it without waiting for the refresh. */
  account?: ApiUserAccount;
  error?: string;
}

/** Owner-only: change a member's role and/or per-client access (empty scopes = all clients). */
export async function updateAccountAction(
  accountId: string,
  body: { role?: string; client_scopes?: string[] },
): Promise<UpdateAccountResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }

  try {
    const account = await updateAccount(accountId, body, token);
    revalidatePath("/members");
    return { ok: true, account };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 403)
        return { ok: false, error: "Only the workspace owner can change roles or access." };
      if (error.status === 404)
        return { ok: false, error: "Member not found — it may have been removed." };
      if (error.status === 422)
        return { ok: false, error: "That role or client selection isn't valid." };
    }
    return { ok: false, error: "Could not save the changes. Try again." };
  }
}

export async function revokeInvite(invitationId: string): Promise<{ ok: boolean; error?: string }> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    await revokeInvitation(invitationId, token);
    revalidatePath("/members");
    return { ok: true };
  } catch {
    return { ok: false, error: "Could not revoke the invite." };
  }
}
