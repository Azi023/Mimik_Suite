import type { JSX, ReactNode } from "react";
import type { Metadata } from "next";
import { themeScript } from "./theme-script";
import "./globals.css";

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
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Resolve theme before paint to avoid a flash of the wrong ground. */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
