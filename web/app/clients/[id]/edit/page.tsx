import type { JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { ClientBrandEditor } from "@/components/ClientBrandEditor";
import { getClientBrandEditData, getSidebarData } from "@/lib/data";
import { redirectClientToPortal } from "@/lib/guard";
import { getSessionToken } from "@/lib/session";

export const dynamic = "force-dynamic";

function devFallbackAllowed(): boolean {
  const appEnv = process.env.APP_ENV;
  const isDev = appEnv === undefined || appEnv === "" || appEnv === "dev";
  const hasDevToken =
    process.env.NEXT_PUBLIC_DEV_TOKEN !== undefined && process.env.NEXT_PUBLIC_DEV_TOKEN !== "";
  return isDev && hasDevToken;
}

/** Team-only client details and brand brief editor, prefilled from tenant-scoped API reads. */
export default async function ClientEditPage({
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
      <AppShell sidebar={sidebar} title="Edit client">
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

  return (
    <AppShell sidebar={sidebar} title="Edit client" crumb={editData.client.name}>
      <ClientBrandEditor client={editData.client} brand={editData.brand} />
    </AppShell>
  );
}
