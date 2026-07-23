import type { JSX } from "react";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { BrandAssetLibrary } from "@/components/BrandAssetLibrary";
import {
  type ApiBrandAsset,
  type ApiClient,
  fetchBrandAssets,
  getBrand,
  listBriefs,
  listClients,
} from "@/lib/api";
import { getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";
import { redirectClientToPortal } from "@/lib/guard";
import {
  approveAssetAction,
  ingestReferenceAction,
  knockoutLogoAction,
  uploadAssetAction,
} from "./actions";

// Asset approval/ingest state changes per action — never a build snapshot.
export const dynamic = "force-dynamic";

interface AssetsPageProps {
  /** `?client=<id>` selects which client's brand library to show; defaults to the first client. */
  searchParams: Promise<{ client?: string | string[] }>;
}

/** Whether the DEV-ONLY unauthenticated fallback may render (dev + a build-time dev token). */
function devFallbackAllowed(): boolean {
  const appEnv = process.env.APP_ENV;
  const isDev = appEnv === undefined || appEnv === "" || appEnv === "dev";
  const hasDevToken =
    process.env.NEXT_PUBLIC_DEV_TOKEN !== undefined && process.env.NEXT_PUBLIC_DEV_TOKEN !== "";
  return isDev && hasDevToken;
}

/** Resolve a client's brand via its latest brief (the same path the brand editor uses). */
async function resolveBrandId(clientId: string, bearer: string | undefined): Promise<string | null> {
  const briefs = await listBriefs(clientId, bearer).catch(() => []);
  const latest = briefs[briefs.length - 1];
  return latest === undefined ? null : latest.brand_id;
}

/**
 * Brand-asset library — the ops surface for curating per-client brand material (logos, fonts,
 * product photos, reference creatives) the engine composites on top of. Assets are brand-scoped,
 * so the page resolves the selected client's brand (via its latest brief) and loads its assets
 * server-side with the real bearer. All asset endpoints are team-gated; a client principal never
 * reaches here (redirectClientToPortal sends them to the portal). Failed calls stay empty — the UI
 * renders real empty states, never faked rows.
 */
export default async function AssetsPage({ searchParams }: AssetsPageProps): Promise<JSX.Element> {
  const { client: rawClient } = await searchParams;
  const requestedClientId =
    typeof rawClient === "string" && rawClient.trim() !== "" ? rawClient.trim() : undefined;

  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  const [sidebar, clients] = await Promise.all([
    getSidebarData(bearer, requestedClientId),
    listClients(bearer).catch((): ApiClient[] => []),
  ]);

  // Honor the requested client only if it's really one of ours; otherwise fall back to the first.
  const selectedClient =
    clients.find((c) => c.id === requestedClientId) ?? clients[0] ?? null;

  let brandId: string | null = null;
  let assets: ApiBrandAsset[] = [];
  if (selectedClient !== null) {
    brandId = await resolveBrandId(selectedClient.id, bearer);
    if (brandId !== null) {
      // Confirm the brand is really the tenant's before listing (getBrand 404s cross-tenant).
      const brand = await getBrand(brandId, bearer).catch(() => null);
      if (brand === null) {
        brandId = null;
      } else {
        assets = await fetchBrandAssets(brandId, undefined, bearer).catch(
          (): ApiBrandAsset[] => [],
        );
      }
    }
  }

  return (
    <AppShell sidebar={sidebar} title="Brand assets" crumb="Asset library">
      <BrandAssetLibrary
        clients={clients.map((c) => ({ id: c.id, name: c.name }))}
        selectedClientId={selectedClient?.id ?? ""}
        brandId={brandId}
        assets={assets}
        uploadAction={uploadAssetAction}
        approveAction={approveAssetAction}
        knockoutAction={knockoutLogoAction}
        ingestAction={ingestReferenceAction}
      />
    </AppShell>
  );
}
