/**
 * Per-tenant white-label branding — the single source of truth for the app shell's
 * product name, wordmark/logo, and accent.
 *
 * WHERE BRANDING COMES FROM
 * -------------------------
 * The product is multi-tenant: a second agency (e.g. Jasmine Media) must see the app as
 * THEIR product ("Jasmin Suite"), not "Mimik Suite". Branding is keyed by the caller's own
 * tenant **slug** — a stable, human-readable key returned by `GET /me` (`tenant_slug`), which
 * only ever exposes the caller's own tenant (never cross-tenant). Slugs are stable across
 * environments (the Mimik tenant seeds as `mimik`); tenant UUIDs are not, which is why we key
 * on the slug rather than `tenant_id`.
 *
 * ADDING A NEW TENANT
 * -------------------
 * Add one entry to `BRANDING_BY_SLUG` keyed by that tenant's slug. That's the whole change —
 * no code edits elsewhere. Until an agency is added here it inherits `DEFAULT_BRANDING` (Mimik,
 * the platform front door). A tenant whose slug is missing therefore looks like the platform
 * default, never a blank.
 *
 * PRE-AUTH SURFACES (login / invite)
 * ----------------------------------
 * The login and invite screens render BEFORE a session exists, so the tenant is unknown there.
 * They resolve to `DEFAULT_BRANDING` (the Mimik front door). True per-tenant pre-auth branding
 * needs a host/subdomain (or invite-token) signal to pick the tenant — that is a documented
 * follow-up, not part of this foundation slice.
 */

import { getMe } from "@/lib/api";

/** The brandable shell surface for one tenant. */
export interface TenantBranding {
  /** Full product name — page titles, auth headline, sidebar aria-label. e.g. "Mimik Suite". */
  product_name: string;
  /** Short name — the compact wordmark; its first letter is the fallback logo bubble. e.g. "Mimik". */
  short_name: string;
  /** Optional logo image URL/data-URI. When null, the shell renders a text wordmark of the
   *  tenant's OWN name (never another tenant's logo). */
  logo_ref: string | null;
  /** Optional CSS accent (hex/rgb). When set, exposed as `--brand-primary` on the shell root.
   *  When null, the shell keeps its default accent (a no-op — Mimik looks exactly as today). */
  primary_color: string | null;
}

/**
 * Branding per tenant slug. Trivially extended: add one entry per agency.
 * The `mimik` entry MUST equal the historical hardcoded values so this is a no-op for Mimik.
 */
export const BRANDING_BY_SLUG: Readonly<Record<string, TenantBranding>> = {
  mimik: {
    product_name: "Mimik Suite",
    short_name: "Mimik",
    logo_ref: null,
    primary_color: null,
  },
  jasmine: {
    product_name: "Jasmin Suite",
    short_name: "Jasmin",
    logo_ref: null,
    // Seam for the accent rebrand — surfaced as `--brand-primary`. The shadcn accent tokens
    // (`--accent` + its paired `--accent-ink`) are NOT yet remapped to this (doing so safely
    // needs a matching ink for contrast). See the TODO in AppShell.
    primary_color: "#0F766E",
  },
};

/**
 * The platform default — the Mimik front door. Used for pre-auth surfaces (login/invite) and
 * for any authenticated tenant whose slug has no entry yet.
 */
export const DEFAULT_BRANDING: TenantBranding = BRANDING_BY_SLUG.mimik;

/** Map a tenant slug (or null/unknown) to its branding, falling back to the platform default. */
export function resolveBrandingForSlug(slug: string | null | undefined): TenantBranding {
  if (slug === null || slug === undefined || slug === "") {
    return DEFAULT_BRANDING;
  }
  return BRANDING_BY_SLUG[slug] ?? DEFAULT_BRANDING;
}

/**
 * Resolve the CURRENT (authenticated) tenant's branding from the session token by reading its
 * own `GET /me`. Any failure — no token, API unreachable, unknown tenant — degrades to the
 * platform default (no mock data, a truthful default). Call from server components only.
 */
export async function resolveTenantBranding(
  sessionToken?: string,
): Promise<TenantBranding> {
  if (sessionToken === undefined || sessionToken === "") {
    return DEFAULT_BRANDING;
  }
  try {
    const me = await getMe(sessionToken);
    return resolveBrandingForSlug(me.tenant_slug);
  } catch {
    return DEFAULT_BRANDING;
  }
}
