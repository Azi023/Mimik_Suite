import type { JSX, ReactNode } from "react";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { themeScript } from "./theme-script";
import "./globals.css";

/** Inter, self-hosted at build time via next/font. Exposed as --font-inter. */
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Mimik Studio — Board",
  description: "Mimik Suite creative ops dashboard.",
};

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
      <body>{children}</body>
    </html>
  );
}
