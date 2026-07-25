import type { JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { BrandBookCanvas } from "@/components/brand-kit/BrandBookCanvas";
import { BrandKitControls, type KitSectionLink } from "@/components/brand-kit/BrandKitControls";
import { KIT_TABS } from "@/components/brand-kit/registry";
import { getClientBrandEditData, getSidebarData } from "@/lib/data";
import { redirectClientToPortal } from "@/lib/guard";
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
 * Brand Kit v2 — the per-client brand book, STUDIO surface (chapters 01–04 read-only;
 * 05–06 placeholders). The chapters themselves live in `components/brand-kit/` — one
 * template, two surfaces — and render here with `view="studio"` (ghost cards, full-size
 * specimen placeholders) plus the studio-only publish/share/export control bar.
 * Tenant scoping is enforced at the API; this page only forwards the caller's own session.
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
  await redirectClientToPortal(sessionToken);

  const [sidebar, editData] = await Promise.all([
    getSidebarData(bearer, id),
    getClientBrandEditData(id, bearer),
  ]);

  if (editData === null) {
    return (
      <AppShell sidebar={sidebar} title="Brand kit">
        <div className="empty-state">
          <p className="empty-state__title">Client not found</p>
          <p className="empty-state__body">
            It may have been removed, or it belongs to another workspace.
          </p>
          <Link href="/" className="btn-ghost">
            Back to board
          </Link>
        </div>
      </AppShell>
    );
  }

  const { client, brand } = editData;

  if (brand === null) {
    return (
      <AppShell sidebar={sidebar} title="Brand kit" crumb={client.name}>
        <div className="empty-state">
          <p className="empty-state__title">No brand book yet</p>
          <p className="empty-state__body">
            The brand book generates from live brand tokens once onboarding drafts this
            client&apos;s brief.
          </p>
          <Link href={`/clients/${encodeURIComponent(client.id)}/edit`} className="btn-ghost">
            Open client editor
          </Link>
        </div>
      </AppShell>
    );
  }

  // Export endpoints (spec §8) — served by the API's Playwright export stack, reached through
  // SAME-ORIGIN proxies so the plain-navigation download links authenticate via the httpOnly
  // session cookie (the bearer is attached server-side in the proxy, never exposed to the browser).
  const proxyBase = `/api/brand-kit/${encodeURIComponent(brand.id)}`;
  const pdfHref = `${proxyBase}/brand-book.pdf`;
  const sectionLinks: KitSectionLink[] = KIT_TABS.map((tab) => ({
    key: tab.key,
    label: `${tab.number} · ${tab.label}`,
    href: `${proxyBase}/section/${encodeURIComponent(tab.key)}`,
  }));

  return (
    <AppShell sidebar={sidebar} title="Brand kit" crumb={client.name}>
      <BrandBookCanvas
        brand={brand}
        clientName={client.name}
        view="studio"
        controls={
          <BrandKitControls
            brandId={brand.id}
            initialPublished={brand.kit?.published ?? false}
            pdfHref={pdfHref}
            sectionLinks={sectionLinks}
          />
        }
      />
    </AppShell>
  );
}
