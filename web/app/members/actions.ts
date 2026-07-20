"use server";

import { revalidatePath } from "next/cache";
import { createInvitation, revokeInvitation, ApiError } from "@/lib/api";
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
