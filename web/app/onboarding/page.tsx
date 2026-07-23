import type { JSX } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import {
  type ApiClient,
  type ApiPillarPreset,
  getClient,
  listPillarPresets,
} from "@/lib/api";
import { getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";
import { redirectClientToPortal } from "@/lib/guard";
import { OnboardingWizard } from "./OnboardingWizard";

export const dynamic = "force-dynamic";

interface OnboardingPageProps {
  searchParams: Promise<{ clientId?: string | string[] }>;
}

/** Whether the DEV-ONLY unauthenticated fallback may render (dev + a build-time dev token). */
function devFallbackAllowed(): boolean {
  const appEnv = process.env.APP_ENV;
  const isDev = appEnv === undefined || appEnv === "" || appEnv === "dev";
  const hasDevToken =
    process.env.NEXT_PUBLIC_DEV_TOKEN !== undefined && process.env.NEXT_PUBLIC_DEV_TOKEN !== "";
  return isDev && hasDevToken;
}

/**
 * New-client onboarding wizard (Brand -> Brand Kit -> Content Pillars -> Style reference). Behind
 * the Supabase session gate like the rest of the admin. Pillar presets are loaded server-side with
 * the real bearer; the wizard creates client + brand + pillars + references on submit and lands the
 * user on the auto-drafted brief.
 */
export default async function OnboardingPage({
  searchParams,
}: OnboardingPageProps): Promise<JSX.Element> {
  const { clientId: rawClientId } = await searchParams;
  const clientId =
    typeof rawClientId === "string" && rawClientId.trim() !== ""
      ? rawClientId.trim()
      : undefined;
  const invalidClientScope = rawClientId !== undefined && clientId === undefined;
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  const [sidebar, presets, existingClient] = await Promise.all([
    getSidebarData(bearer, clientId),
    listPillarPresets(bearer).catch((): ApiPillarPreset[] => []),
    clientId === undefined
      ? Promise.resolve<ApiClient | null>(null)
      : getClient(clientId, bearer).catch((): ApiClient | null => null),
  ]);

  if (invalidClientScope || (clientId !== undefined && existingClient === null)) {
    return (
      <AppShell sidebar={sidebar} title="Create brand kit & brief">
        <div className="empty-state">
          <p className="empty-state__title">Client not found</p>
          <p className="empty-state__body">
            The client may have been removed, or it belongs to another workspace.
          </p>
          <Link href="/clients" className="btn-ghost">
            Back to clients
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      sidebar={sidebar}
      title={existingClient === null ? "Onboarding a client" : "Create brand kit & brief"}
      crumb={existingClient?.name}
    >
      <OnboardingWizard presets={presets} existingClient={existingClient ?? undefined} />
    </AppShell>
  );
}
