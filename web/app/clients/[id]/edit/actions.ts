"use server";

import { revalidatePath } from "next/cache";
import {
  ApiError,
  type ApiColorRole,
  updateBrandBrief,
  updateClient,
} from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export interface ClientBrandSaveResult {
  ok: boolean;
  error?: string;
}

function value(formData: FormData, key: string): string {
  return String(formData.get(key) ?? "").trim();
}

function nullable(formData: FormData, key: string): string | null {
  const result = value(formData, key);
  return result === "" ? null : result;
}

function values(formData: FormData, key: string): string[] {
  return formData
    .getAll(key)
    .map((entry) => String(entry).trim())
    .filter((entry) => entry !== "");
}

function colors(formData: FormData): ApiColorRole[] {
  const names = formData.getAll("color_name").map((entry) => String(entry).trim());
  const hexes = formData.getAll("color_hex").map((entry) => String(entry).trim());
  const usages = formData.getAll("color_usage").map((entry) => String(entry).trim());
  return hexes
    .map((hex, index) => ({
      name: names[index] === undefined || names[index] === "" ? hex : names[index],
      hex,
      usage: usages[index] === undefined || usages[index] === "" ? null : usages[index],
    }))
    .filter((color) => color.hex !== "");
}

/** Persist both halves of the edit surface with the signed-in team's bearer. */
export async function saveClientBrand(
  clientId: string,
  brandId: string | null,
  formData: FormData,
): Promise<ClientBrandSaveResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired. Sign in again." };
  }

  const name = value(formData, "client_name");
  if (name === "") {
    return { ok: false, error: "Client name is required." };
  }

  try {
    await updateClient(
      clientId,
      {
        name,
        industry: nullable(formData, "industry"),
        contact_email: nullable(formData, "contact_email"),
      },
      token,
    );
    if (brandId !== null) {
      await updateBrandBrief(
        brandId,
        {
          niche: nullable(formData, "niche"),
          target_audience: nullable(formData, "target_audience"),
          brand_voice: nullable(formData, "brand_voice"),
          tone_keywords: values(formData, "tone_keywords"),
          imagery_style: nullable(formData, "imagery_style"),
          dos: values(formData, "dos"),
          donts: values(formData, "donts"),
          tokens: { colors: colors(formData) },
        },
        token,
      );
    }
    revalidatePath(`/clients/${clientId}/edit`);
    revalidatePath("/");
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 403) {
        return { ok: false, error: "You don't have permission to edit this client." };
      }
      if (error.status === 404) {
        return { ok: false, error: "This client or brand brief is no longer available." };
      }
      if (error.status === 422) {
        return { ok: false, error: "Some details are invalid. Check the form and try again." };
      }
    }
    return { ok: false, error: "Could not save the changes. Try again." };
  }
}
