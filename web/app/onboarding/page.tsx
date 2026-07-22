import type { JSX } from "react";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { type ApiPillarPreset, listPillarPresets } from "@/lib/api";
import { getSidebarData } from "@/lib/data";
import { getSessionToken } from "@/lib/session";
import { redirectClientToPortal } from "@/lib/guard";
import { OnboardingWizard } from "./OnboardingWizard";

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
 * New-client onboarding wizard (Brand -> Brand Kit -> Content Pillars -> Style reference). Behind
 * the Supabase session gate like the rest of the admin. Pillar presets are loaded server-side with
 * the real bearer; the wizard creates client + brand + pillars + references on submit and lands the
 * user on the auto-drafted brief.
 */
export default async function OnboardingPage(): Promise<JSX.Element> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null && !devFallbackAllowed()) {
    redirect("/login");
  }
  const bearer = sessionToken ?? undefined;
  await redirectClientToPortal(sessionToken);

  const [sidebar, presets] = await Promise.all([
    getSidebarData(bearer),
    listPillarPresets(bearer).catch((): ApiPillarPreset[] => []),
  ]);

  return (
    <AppShell sidebar={sidebar} title="Onboarding a client">
      <OnboardingWizard presets={presets} />
    </AppShell>
  );
}
