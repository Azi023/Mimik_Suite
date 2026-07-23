import type { JSX } from "react";
import Link from "next/link";

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
        <p className="empty-state__title">This page doesn&rsquo;t exist</p>
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
