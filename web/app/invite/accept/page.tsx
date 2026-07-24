import type { JSX, ReactNode } from "react";
import Link from "next/link";
import { getSessionEmail, getSessionToken } from "@/lib/session";
import { AcceptInvitationPanel } from "./AcceptInvitationPanel";

// The signed-in identity is per-request — never a build-time snapshot.
export const dynamic = "force-dynamic";

interface InviteAcceptPageProps {
  /** `?token=` — the signed invite token minted by the backend accept-link. */
  searchParams: Promise<{ token?: string }>;
}

/** Split-screen frame mirroring the login reference (dark brand panel + content), reused so the
 *  invite flow reads as the same product surface. */
function AuthFrame({ children }: { children: ReactNode }): JSX.Element {
  return (
    <main className="auth">
      <aside className="auth-brand" aria-hidden="true">
        <div className="auth-brand__inner">
          <span className="auth-brand__mark">M</span>
          <h2 className="auth-brand__headline">Mimik Suite</h2>
          <p className="auth-brand__tagline">You&apos;ve been invited to the workspace.</p>
        </div>
      </aside>
      <section className="auth-panel">{children}</section>
    </main>
  );
}

/**
 * Invitation-accept landing (`/invite/accept?token=…`) — the target of the backend accept-link
 * (`{app_base_url}/invite/accept?token=<signed token>`). Three server-resolved branches:
 *   (a) no token in the link          → dead-end copy asking for a fresh invite;
 *   (b) not signed in                 → route to /login carrying `?next=` so the token survives the
 *                                        round-trip and lands the invitee right back here;
 *   (c) signed in                     → hand off to the client panel, where an explicit Accept action
 *                                        redeems the token and every outcome gets an honest state.
 * The accept endpoint requires a real Supabase identity whose verified email matches the invite, so
 * there is NO dev-token fallback here — an unauthenticated visitor is always sent to sign in.
 */
export default async function InviteAcceptPage({
  searchParams,
}: InviteAcceptPageProps): Promise<JSX.Element> {
  const { token } = await searchParams;
  const trimmedToken = typeof token === "string" ? token.trim() : "";

  // (a) The link arrived without a token — nothing to redeem.
  if (trimmedToken === "") {
    return (
      <AuthFrame>
        <div className="auth-form">
          <div className="auth-form__head">
            <h1 className="auth-form__title">Invitation link incomplete</h1>
            <p className="auth-form__sub">
              This link is missing its invitation token. Ask your Mimik contact to send a fresh
              invite.
            </p>
          </div>
        </div>
      </AuthFrame>
    );
  }

  const sessionToken = await getSessionToken();

  // (b) Not signed in — send to login, carrying the invite through the round-trip.
  if (sessionToken === null) {
    const next = `/invite/accept?token=${encodeURIComponent(trimmedToken)}`;
    return (
      <AuthFrame>
        <div className="auth-form">
          <div className="auth-form__head">
            <h1 className="auth-form__title">Sign in to accept</h1>
            <p className="auth-form__sub">
              Sign in with the email address this invitation was sent to. You&apos;ll come straight
              back here to finish joining.
            </p>
          </div>
          <Link
            className="auth-form__submit auth-form__submit--link"
            href={`/login?next=${encodeURIComponent(next)}`}
          >
            Sign in to continue
          </Link>
        </div>
      </AuthFrame>
    );
  }

  // (c) Signed in — the client panel drives the explicit accept + all outcome states.
  const email = await getSessionEmail();
  return (
    <AuthFrame>
      <AcceptInvitationPanel token={trimmedToken} email={email} />
    </AuthFrame>
  );
}
