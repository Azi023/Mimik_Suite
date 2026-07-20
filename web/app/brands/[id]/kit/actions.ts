"use server";

import { revalidatePath } from "next/cache";
import { ApiError, type ApiBrandTokens, updateBrandTokens } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/**
 * Save the brand kit (design tokens + layout). Runs SERVER-SIDE so the per-user Supabase bearer
 * (httpOnly cookie) authorizes the PATCH. Full-replace of the brand's tokens; the contract
 * validates ranges (logo scale, margins, guide positions), so bad values surface as a 422 here.
 */

export interface KitSaveResult {
  ok: boolean;
  error?: string;
}

export async function saveBrandKit(
  brandId: string,
  tokens: ApiBrandTokens,
): Promise<KitSaveResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    await updateBrandTokens(brandId, tokens, token);
    revalidatePath(`/brands/${brandId}/kit`);
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 403) {
        return { ok: false, error: "You don't have permission to edit this brand kit." };
      }
      if (error.status === 404) {
        return { ok: false, error: "This brand no longer exists." };
      }
      if (error.status === 422) {
        return { ok: false, error: "Some values were out of range — check the layout and try again." };
      }
    }
    return { ok: false, error: "Could not save the brand kit. Try again." };
  }
}
