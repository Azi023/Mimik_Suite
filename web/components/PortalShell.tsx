import type { JSX, ReactNode } from "react";
import Link from "next/link";

interface PortalShellProps {
  children: ReactNode;
  /** Optional heading shown under the wordmark (e.g. the job title on the review screen). */
  title?: string;
  /** When set, a back link to the portal index. */
  back?: boolean;
  /** No-login magic-link mode: hide sign-out + back (there is no session and no index). */
  bare?: boolean;
}

/**
 * Bounded client-portal chrome — deliberately NOT the internal AppShell. No sidebar, no ops nav, no
 * cross-client surfaces (locked constraint #3: the client is a low-privilege, untrusted principal).
 * Just a wordmark, an optional title, a back link, and sign-out. Everything the client sees is their
 * own client's data, enforced at the API data layer (client principals are confined server-side).
 */
export function PortalShell({ children, title, back, bare }: PortalShellProps): JSX.Element {
  return (
    <div className="portal">
      <header className="portal__bar">
        <div className="portal__brand">
          <span className="portal__logo" aria-hidden="true">
            M
          </span>
          <span className="portal__wordmark">Mimik · Review portal</span>
        </div>
        {bare !== true && (
          <div className="portal__bar-right">
            {back === true && (
              <Link href="/portal" className="portal__back">
                ← All creatives
              </Link>
            )}
            {/* Logout is a POST so a prefetch/link can't sign the client out. */}
            <form action="/api/auth/logout" method="post">
              <button type="submit" className="btn btn--ghost btn--sm">
                Sign out
              </button>
            </form>
          </div>
        )}
      </header>
      {title !== undefined && <h1 className="portal__title">{title}</h1>}
      <main className="portal__content">{children}</main>
    </div>
  );
}
