/**
 * Server-only Supabase session helper.
 *
 * The frontend talks to Supabase's GoTrue REST API by plain `fetch` (no
 * @supabase/supabase-js) and holds the resulting session entirely server-side in
 * httpOnly cookies. Nothing here ever runs in the browser bundle:
 *   - `SUPABASE_URL` / `SUPABASE_ANON_KEY` are read WITHOUT the `NEXT_PUBLIC_` prefix,
 *     so they are never inlined into client JS.
 *   - the access/refresh tokens live in httpOnly cookies (not readable from JS).
 *
 * Auth flow this module owns:
 *   1. login (`signInWithPassword`) — POST .../token?grant_type=password
 *   2. session read (`getSessionToken`) — read the access-token cookie; if it is
 *      expired (or about to expire), refresh via .../token?grant_type=refresh_token
 *      and rotate the cookies.
 *   3. logout (`clearSession`) — delete both cookies.
 *
 * The returned access token is the Bearer the FastAPI backend verifies
 * (api/core/supabase_auth.py) — issuer/audience `authenticated`.
 *
 * Server-only by construction: it uses `next/headers` (`cookies()`), which throws
 * if reached from a client component, and reads non-`NEXT_PUBLIC_` env. Do not
 * import this from a `"use client"` module.
 */

import { cookies } from "next/headers";

/** httpOnly cookie holding the Supabase access token (JWT). */
export const ACCESS_COOKIE = "mimik_sb_access";
/** httpOnly cookie holding the Supabase refresh token (opaque). */
export const REFRESH_COOKIE = "mimik_sb_refresh";

/** Refresh a token this many seconds BEFORE its `exp` to avoid edge-of-expiry 401s. */
const EXPIRY_SKEW_SECONDS = 30;

/** Shape of a GoTrue token response (the subset we consume). */
interface GoTrueTokenResponse {
  access_token: string;
  refresh_token: string;
  /** Absolute unix seconds; present on modern GoTrue. Prefer this over `expires_in`. */
  expires_at?: number;
  /** Seconds-from-now lifetime; fallback when `expires_at` is absent. */
  expires_in?: number;
}

/** A normalized login/refresh outcome the caller (route handler) can act on. */
export type AuthResult =
  | { ok: true }
  | { ok: false; error: string };

/** Read a required server-side env var; throws (misconfig) rather than silently degrade. */
function requireEnv(name: "SUPABASE_URL" | "SUPABASE_ANON_KEY"): string {
  const value = process.env[name];
  if (value === undefined || value === "") {
    throw new Error(`${name} is not configured (server-side env)`);
  }
  return name === "SUPABASE_URL" ? value.replace(/\/+$/, "") : value;
}

/** Whether Supabase login is even wired up (both server-side env vars present). */
export function isSupabaseConfigured(): boolean {
  return (
    process.env.SUPABASE_URL !== undefined &&
    process.env.SUPABASE_URL !== "" &&
    process.env.SUPABASE_ANON_KEY !== undefined &&
    process.env.SUPABASE_ANON_KEY !== ""
  );
}

/** Decode a JWT's `exp` (unix seconds) without verifying — we only trust it post-verify server-side. */
function readJwtExp(token: string): number | null {
  const parts = token.split(".");
  if (parts.length !== 3) {
    return null;
  }
  try {
    const payloadJson = Buffer.from(parts[1], "base64url").toString("utf8");
    const payload = JSON.parse(payloadJson) as { exp?: unknown };
    return typeof payload.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}

/** Cookie options: httpOnly, path-wide, secure in prod, lax same-site. */
function cookieOptions(maxAgeSeconds: number): {
  httpOnly: true;
  secure: boolean;
  sameSite: "lax";
  path: string;
  maxAge: number;
} {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: maxAgeSeconds,
  };
}

/** Persist a fresh token pair into httpOnly cookies. */
async function writeSessionCookies(tokens: GoTrueTokenResponse): Promise<void> {
  const store = await cookies();
  // Access cookie lifetime tracks the JWT; refresh cookie gets a long window so a
  // returning user can silently re-auth. Both are httpOnly.
  const nowSeconds = Math.floor(Date.now() / 1000);
  const accessExp = tokens.expires_at ?? nowSeconds + (tokens.expires_in ?? 3600);
  const accessMaxAge = Math.max(accessExp - nowSeconds, 60);
  store.set(ACCESS_COOKIE, tokens.access_token, cookieOptions(accessMaxAge));
  store.set(REFRESH_COOKIE, tokens.refresh_token, cookieOptions(60 * 60 * 24 * 30));
}

/** POST to a GoTrue token grant endpoint; normalize the outcome. */
async function goTrueToken(
  grant: "password" | "refresh_token",
  body: Record<string, string>,
): Promise<{ ok: true; tokens: GoTrueTokenResponse } | { ok: false; error: string }> {
  const url = `${requireEnv("SUPABASE_URL")}/auth/v1/token?grant_type=${grant}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        apikey: requireEnv("SUPABASE_ANON_KEY"),
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return { ok: false, error: "Could not reach the authentication service." };
  }

  if (!response.ok) {
    // GoTrue returns { error_description } (400) or { msg } — surface a safe generic message.
    const detail = (await response.json().catch(() => null)) as
      | { error_description?: string; msg?: string; error?: string }
      | null;
    const message =
      grant === "password"
        ? "Invalid email or password."
        : detail?.error_description ?? detail?.msg ?? "Session expired. Please sign in again.";
    return { ok: false, error: message };
  }

  const tokens = (await response.json()) as GoTrueTokenResponse;
  if (typeof tokens.access_token !== "string" || typeof tokens.refresh_token !== "string") {
    return { ok: false, error: "Authentication service returned an unexpected response." };
  }
  return { ok: true, tokens };
}

/**
 * Exchange email + password for a session, storing tokens in httpOnly cookies.
 * Returns a normalized result so the route handler can render an inline error.
 */
export async function signInWithPassword(email: string, password: string): Promise<AuthResult> {
  const result = await goTrueToken("password", { email, password });
  if (!result.ok) {
    return { ok: false, error: result.error };
  }
  await writeSessionCookies(result.tokens);
  return { ok: true };
}

/** Attempt to refresh the session from the refresh cookie; rotate cookies on success. */
async function refreshSession(refreshToken: string): Promise<string | null> {
  const result = await goTrueToken("refresh_token", { refresh_token: refreshToken });
  if (!result.ok) {
    return null;
  }
  await writeSessionCookies(result.tokens);
  return result.tokens.access_token;
}

/**
 * The server-side session accessor. Returns a usable access token, or null when
 * there is no valid session:
 *   - no access cookie AND no refresh cookie -> null (unauthenticated).
 *   - access cookie still valid (beyond the skew window) -> return it.
 *   - access cookie expired/near-expiry but a refresh cookie exists -> refresh + rotate.
 *   - refresh fails -> null (caller redirects to /login).
 */
export async function getSessionToken(): Promise<string | null> {
  const store = await cookies();
  const access = store.get(ACCESS_COOKIE)?.value;
  const refresh = store.get(REFRESH_COOKIE)?.value;

  if (access !== undefined && access !== "") {
    const exp = readJwtExp(access);
    const nowSeconds = Math.floor(Date.now() / 1000);
    if (exp === null || exp - EXPIRY_SKEW_SECONDS > nowSeconds) {
      // Valid (or undecodable — let the API be the authority and reject if truly bad).
      return access;
    }
  }

  if (refresh !== undefined && refresh !== "") {
    return await refreshSession(refresh);
  }

  return null;
}

/** True when a usable session exists — the board's auth gate. */
export async function hasSession(): Promise<boolean> {
  return (await getSessionToken()) !== null;
}

/**
 * Best-effort read of the signed-in identity's `email` claim from the access token — for DISPLAY
 * only (e.g. "signed in as …" on the invite-accept screen). The token is never trusted here: the API
 * re-verifies it on every call and is the authority on the email. Returns null when unauthenticated
 * or the claim is absent/undecodable.
 */
export async function getSessionEmail(): Promise<string | null> {
  const token = await getSessionToken();
  if (token === null) {
    return null;
  }
  const parts = token.split(".");
  if (parts.length !== 3) {
    return null;
  }
  try {
    const payloadJson = Buffer.from(parts[1], "base64url").toString("utf8");
    const payload = JSON.parse(payloadJson) as { email?: unknown };
    return typeof payload.email === "string" && payload.email !== "" ? payload.email : null;
  } catch {
    return null;
  }
}

/**
 * Sanitize a post-auth return path (the login `?next=` round-trip). Allows ONLY a same-origin
 * relative path (starts with a single "/"); an absolute URL, a protocol-relative "//", a
 * backslash-trick "/\\", or a missing value collapses to "" so the caller falls back to its default
 * landing route. This blocks open-redirect through the `next` parameter.
 */
export function sanitizeNextPath(value: string | null | undefined): string {
  if (typeof value !== "string" || value === "") {
    return "";
  }
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) {
    return "";
  }
  return value;
}

/** Clear both session cookies (logout). */
export async function clearSession(): Promise<void> {
  const store = await cookies();
  store.delete(ACCESS_COOKIE);
  store.delete(REFRESH_COOKIE);
}
