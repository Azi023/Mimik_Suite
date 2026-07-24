import type { JSX, ReactNode } from "react";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { themeScript } from "./theme-script";
import { getSessionToken } from "@/lib/session";
import { resolveTenantBranding } from "@/lib/branding";
import "./globals.css";

/** Inter, self-hosted at build time via next/font. Exposed as --font-inter. */
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

/**
 * Document title/description are per-tenant: resolved from the caller's own tenant branding so the
 * browser tab reads "Jasmin Suite …" for Jasmine, "Mimik Suite …" for Mimik. Pre-auth (no session)
 * falls back to the platform default. Per-request, never a build-time snapshot.
 */
export async function generateMetadata(): Promise<Metadata> {
  const sessionToken = await getSessionToken();
  const branding = await resolveTenantBranding(sessionToken ?? undefined);
  return {
    title: `${branding.short_name} Studio — Board`,
    description: `${branding.product_name} creative ops dashboard.`,
  };
}

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}): JSX.Element {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <head>
        {/* Resolve theme before paint to avoid a flash of the wrong ground. */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      {/* Browser extensions (Grammarly, etc.) inject attributes onto <body> before React
          hydrates; suppress the resulting benign attribute-mismatch warning. */}
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
