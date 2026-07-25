"use server";

import { revalidatePath } from "next/cache";
import {
  ApiError,
  deleteBrand,
  deleteBrief,
  deleteClient,
  deleteCreative,
  updateCreativeMetadata,
} from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export interface CrudActionResult {
  ok: boolean;
  error?: string;
}

function mutationError(error: unknown, entity: string): string {
  if (error instanceof ApiError) {
    if (error.status === 403) return `You don't have permission to remove this ${entity}.`;
    if (error.status === 404) return `This ${entity} no longer exists.`;
    if (error.status === 422) return `The ${entity} update is invalid.`;
  }
  return `Could not update this ${entity}. Try again.`;
}

async function tokenOrError(): Promise<string | CrudActionResult> {
  const token = await getSessionToken();
  return token ?? { ok: false, error: "Your session has expired. Sign in again." };
}

export async function removeClientAction(clientId: string): Promise<CrudActionResult> {
  const token = await tokenOrError();
  if (typeof token !== "string") return token;
  try {
    await deleteClient(clientId, token);
    revalidatePath("/clients");
    revalidatePath("/");
    revalidatePath("/assets");
    revalidatePath("/briefs");
    return { ok: true };
  } catch (error) {
    return { ok: false, error: mutationError(error, "client") };
  }
}

export async function removeBrandAction(brandId: string): Promise<CrudActionResult> {
  const token = await tokenOrError();
  if (typeof token !== "string") return token;
  try {
    await deleteBrand(brandId, token);
    revalidatePath("/");
    revalidatePath("/assets");
    revalidatePath("/briefs");
    return { ok: true };
  } catch (error) {
    return { ok: false, error: mutationError(error, "brand") };
  }
}

export async function removeBriefAction(briefId: string): Promise<CrudActionResult> {
  const token = await tokenOrError();
  if (typeof token !== "string") return token;
  try {
    await deleteBrief(briefId, token);
    revalidatePath("/briefs");
    return { ok: true };
  } catch (error) {
    return { ok: false, error: mutationError(error, "brief") };
  }
}

export async function removeCreativeAction(creativeId: string): Promise<CrudActionResult> {
  const token = await tokenOrError();
  if (typeof token !== "string") return token;
  try {
    await deleteCreative(creativeId, token);
    revalidatePath("/");
    revalidatePath("/creatives");
    return { ok: true };
  } catch (error) {
    return { ok: false, error: mutationError(error, "creative") };
  }
}

export async function updateCreativeMetadataAction(
  creativeId: string,
  copyStatus: "draft" | "approved" | "edited",
  revisionNote: string,
): Promise<CrudActionResult> {
  const token = await tokenOrError();
  if (typeof token !== "string") return token;
  try {
    await updateCreativeMetadata(
      creativeId,
      {
        copy_status: copyStatus,
        revision_note: revisionNote.trim() === "" ? null : revisionNote.trim(),
      },
      token,
    );
    revalidatePath("/");
    return { ok: true };
  } catch (error) {
    return { ok: false, error: mutationError(error, "creative") };
  }
}
