import type { JSX } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { DEFAULT_BRANDING } from "@/lib/branding";

// The global 404 can render outside any tenant session, so it uses the platform default name
// (not a hardcoded literal). Per-tenant 404 titles would need a resolved session — a follow-up.
export const metadata: Metadata = {
  title: `Not found — ${DEFAULT_BRANDING.short_name} Studio`,
};

/**
 * Token-styled 404 — a bad URL lands on the design system, not Next's bare page,
 * with a way back to the board.
 */
export default function NotFound(): JSX.Element {
  return (
    <main className="not-found">
      <div className="empty-state not-found__card">
        <p className="not-found__code" aria-hidden="true">
          404
        </p>
        <h1 className="empty-state__title">This page doesn&rsquo;t exist</h1>
        <p className="empty-state__body">
          The link may be stale, or the record it pointed at was moved.
        </p>
        <Link href="/" className="btn btn--primary">
          Back to board
        </Link>
      </div>
    </main>
  );
}
