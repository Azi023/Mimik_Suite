"use server";

import { revalidatePath } from "next/cache";
import {
  ApiError,
  type ApiFontLibraryEntry,
  type AssetKind,
  approveAsset,
  fetchFontLibrary,
  ingestReference,
  knockoutLogo,
  materializeBuiltinFont,
  uploadBrandAsset,
} from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/**
 * Server actions for the brand-asset library. All run SERVER-SIDE so the per-user Supabase bearer
 * (httpOnly cookie, never in the client bundle) authorizes them — upload/knockout/ingest are
 * team-gated at the API and approve is owner/ops-gated, so a client-role session simply 403s here.
 * Filenames and notes on an asset are DATA, never instructions (constraint #3); nothing here ever
 * merges free text into a prompt. The backend sniffs the real mime from the uploaded bytes and
 * 415s a disallowed type — that error is surfaced verbatim so the operator sees exactly what was
 * rejected.
 */

export interface AssetActionResult {
  ok: boolean;
  error?: string;
  /** A short success note (e.g. the ingest verdict) worth surfacing back to the operator. */
  message?: string;
}

/** The set of kinds the library uploads — mirrors mimik_contracts.AssetKind. */
const KINDS: ReadonlySet<AssetKind> = new Set<AssetKind>([
  "logo",
  "font",
  "imagery",
  "reference_creative",
]);

function isAssetKind(value: string): value is AssetKind {
  return KINDS.has(value as AssetKind);
}

/** Map an ApiError from an upload/mutation to an operator-readable line (never leaks internals). */
function messageForStatus(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    // The backend's `detail` is a safe, human-authored line (mime rejected, too large, wrong
    // kind, unconfigured vision backend) — prefer it so the operator sees the real reason.
    if (error.status === 403) return "You don't have permission for that action.";
    if (error.status === 404) return "That asset or brand no longer exists.";
    if (error.message.trim() !== "") return error.message;
    if (error.status === 413) return "That file is too large (10 MB max).";
    if (error.status === 415) return "That file type isn't allowed for this asset kind.";
  }
  return fallback;
}

export async function uploadAssetAction(
  brandId: string,
  kind: string,
  formData: FormData,
): Promise<AssetActionResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  if (brandId.trim() === "") {
    return { ok: false, error: "No brand is selected for this client yet." };
  }
  if (!isAssetKind(kind)) {
    return { ok: false, error: "Unknown asset kind." };
  }
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return { ok: false, error: "Choose a file to upload." };
  }
  try {
    await uploadBrandAsset(brandId, kind, file, token);
    revalidatePath("/assets");
    return { ok: true };
  } catch (error) {
    return { ok: false, error: messageForStatus(error, "Couldn't upload that file. Try again.") };
  }
}

export async function approveAssetAction(assetId: string): Promise<AssetActionResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    await approveAsset(assetId, token);
    revalidatePath("/assets");
    return { ok: true };
  } catch (error) {
    return { ok: false, error: messageForStatus(error, "Couldn't approve that asset. Try again.") };
  }
}

export async function knockoutLogoAction(assetId: string): Promise<AssetActionResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    await knockoutLogo(assetId, token);
    revalidatePath("/assets");
    return { ok: true, message: "Knockout variant derived — approve it to use it." };
  } catch (error) {
    return {
      ok: false,
      error: messageForStatus(error, "Couldn't derive the knockout variant. Try again."),
    };
  }
}

export async function ingestReferenceAction(assetId: string): Promise<AssetActionResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    const result = await ingestReference(assetId, token);
    revalidatePath("/assets");
    const fit = result.verdict.fits ? "fits the brand" : "off-brand";
    return {
      ok: true,
      message: `Ingested — ${fit} (fit ${result.verdict.fit_score.toFixed(2)}).`,
    };
  } catch (error) {
    return {
      ok: false,
      error: messageForStatus(error, "Couldn't ingest that reference. Try again."),
    };
  }
}

/** Result of a lazy built-in-font-library load — the picker fetches this on open. */
export interface FontLibraryResult {
  ok: boolean;
  fonts?: ApiFontLibraryEntry[];
  error?: string;
}

/**
 * Load the built-in font catalog (GET /fonts/library) server-side so the picker never touches a
 * bearer. Team-gated at the API; a client-role session 403s here (surfaced as a real error state).
 */
export async function loadFontLibraryAction(): Promise<FontLibraryResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    const fonts = await fetchFontLibrary(token);
    return { ok: true, fonts };
  } catch (error) {
    return {
      ok: false,
      error: messageForStatus(error, "Couldn't load the built-in fonts. Try again."),
    };
  }
}

/**
 * Materialize a built-in font (POST /brands/{id}/fonts/{key}) as an approved FONT asset for the
 * brand. `fontKey` is a catalog key (data, never an instruction). Team-gated at the API.
 */
export async function materializeBuiltinFontAction(
  brandId: string,
  fontKey: string,
): Promise<AssetActionResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  if (brandId.trim() === "" || fontKey.trim() === "") {
    return { ok: false, error: "Pick a font to add." };
  }
  try {
    await materializeBuiltinFont(brandId, fontKey, token);
    revalidatePath("/assets");
    return { ok: true, message: "Font added to the brand library." };
  } catch (error) {
    return { ok: false, error: messageForStatus(error, "Couldn't add that font. Try again.") };
  }
}
