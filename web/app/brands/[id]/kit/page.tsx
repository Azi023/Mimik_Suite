import type { JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { BrandKitEditor } from "@/components/BrandKitEditor";
import { type ApiBrand, type ApiClient, getBrand, listClients } from "@/lib/api";
import { getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";

export const dynamic = "force-dynamic";

/** Whether the DEV-ONLY unauthenticated fallback may render (dev + a build-time dev token). */
function devFallbackAllowed(): boolean {
  const appEnv = process.env.APP_ENV;
  const isDev = appEnv === undefined || appEnv === "" || appEnv === "dev";
  const hasDevToken =
    process.env.NEXT_PUBLIC_DEV_TOKEN !== undefined && process.env.NEXT_PUBLIC_DEV_TOKEN !== "";
  return isDev && hasDevToken;
}

/**
 * Brand-kit editor — colors, typography, logo, and the Layout box (logo placement/size, margins,
 * header/footer, grid + guides) with a live artboard preview. Behind the Supabase session gate; a
 * missing / cross-tenant brand id yields a real not-found state (data-layer scoping 404s).
 */
export default async function BrandKitPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<JSX.Element> {
  const { id } = await params;

  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;

  const [sidebar, brand, clients] = await Promise.all([
    getSidebarData(bearer),
    getBrand(id, bearer).catch((): ApiBrand | null => null),
    listClients(bearer).catch((): ApiClient[] => []),
  ]);

  if (brand === null) {
    return (
      <AppShell sidebar={sidebar} title="Brand kit">
        <div className="kit">
          <div className="empty-state">
            <p className="empty-state__title">Brand not found</p>
            <p className="empty-state__body">
              It may have been removed, or it belongs to another workspace.
            </p>
            <Link href="/briefs" className="btn-ghost">
              Back to briefs
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  const clientName = clients.find((c) => c.id === brand.client_id)?.name ?? null;

  return (
    <AppShell sidebar={sidebar} title="Brand kit">
      <BrandKitEditor brand={brand} clientName={clientName} />
    </AppShell>
  );
}
