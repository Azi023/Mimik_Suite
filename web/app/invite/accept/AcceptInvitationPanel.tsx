"use client";

import type { JSX } from "react";
import { useState } from "react";
import Link from "next/link";
import { acceptInvitationAction, type AcceptErrorKind } from "./actions";

interface AcceptInvitationPanelProps {
  /** The signed invite token from `?token=` — passed straight back to the server action. */
  token: string;
  /** The signed-in identity's email (display only), or null when the claim is unavailable. */
  email: string | null;
}

type Phase =
  | { status: "idle" }
  | { status: "success" }
  | { status: "error"; message: string; kind: AcceptErrorKind };

/** The path to re-authenticate as the invited email, carrying this invite through the round-trip. */
function loginHrefForToken(token: string): string {
  const next = `/invite/accept?token=${encodeURIComponent(token)}`;
  return `/login?next=${encodeURIComponent(next)}`;
}

/** Heading copy per outcome — the backend `detail` is always shown verbatim beneath it. */
function errorHeading(kind: AcceptErrorKind): string {
  switch (kind) {
    case "session":
      return "Sign in to accept";
    case "email_mismatch":
      return "Wrong account";
    case "expired":
      return "This invitation has expired";
    case "revoked":
      return "This invitation was revoked";
    case "already_accepted":
      return "Already accepted";
    case "already_account":
      return "You already have an account";
    case "invalid":
      return "This invitation link isn't valid";
    default:
      return "Couldn't accept the invitation";
  }
}

/**
 * The signed-in half of the invite-accept screen. Accepting is an explicit, user-triggered POST (no
 * side-effect on page load): the button fires the server action, and each outcome renders an honest
 * state — success routes into the app, while every failure shows the backend's own error detail plus
 * the recovery path that fits it (re-auth, switch account, or go to the dashboard).
 */
export function AcceptInvitationPanel({ token, email }: AcceptInvitationPanelProps): JSX.Element {
  const [phase, setPhase] = useState<Phase>({ status: "idle" });
  const [busy, setBusy] = useState(false);

  async function onAccept(): Promise<void> {
    setBusy(true);
    setPhase({ status: "idle" });
    const result = await acceptInvitationAction(token);
    setBusy(false);
    if (result.ok) {
      setPhase({ status: "success" });
      return;
    }
    setPhase({
      status: "error",
      message: result.error ?? "Something went wrong. Try again.",
      kind: result.kind ?? "generic",
    });
  }

  if (phase.status === "success") {
    return (
      <div className="auth-form">
        <div className="auth-form__head">
          <h1 className="auth-form__title">You&apos;re in</h1>
          <p className="auth-form__sub">
            Your account is ready{email !== null ? ` for ${email}` : ""}. Welcome to Mimik Suite.
          </p>
        </div>
        <Link className="auth-form__submit auth-form__submit--link" href="/">
          Go to your dashboard
        </Link>
      </div>
    );
  }

  if (phase.status === "error") {
    const { kind, message } = phase;
    return (
      <div className="auth-form">
        <div className="auth-form__head">
          <h1 className="auth-form__title">{errorHeading(kind)}</h1>
        </div>
        <p className="auth-form__error" role="alert">
          {message}
        </p>

        {kind === "session" || kind === "email_mismatch" ? (
          <div className="auth-actions">
            {kind === "email_mismatch" && email !== null && (
              <p className="auth-form__sub">
                You&apos;re signed in as <strong>{email}</strong>. Sign out and sign back in with the
                address this invitation was sent to.
              </p>
            )}
            {/* Sign out (POST — never a link, so a prefetch can't drop the session), then return here. */}
            <form action="/api/auth/logout" method="post">
              <button className="auth-form__submit" type="submit">
                Sign out &amp; use a different account
              </button>
            </form>
            <Link className="auth-form__secondary" href={loginHrefForToken(token)}>
              Sign in again
            </Link>
          </div>
        ) : kind === "already_account" || kind === "already_accepted" ? (
          <Link className="auth-form__submit auth-form__submit--link" href="/">
            Go to your dashboard
          </Link>
        ) : (
          <button className="auth-form__submit" type="button" onClick={onAccept} disabled={busy}>
            {busy ? "Trying again…" : "Try again"}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="auth-form">
      <div className="auth-form__head">
        <h1 className="auth-form__title">Accept your invitation</h1>
        <p className="auth-form__sub">
          {email !== null ? (
            <>
              You&apos;re signed in as <strong>{email}</strong>. Accept to join your Mimik Suite
              workspace. This must match the address the invite was sent to.
            </>
          ) : (
            "Accept to join your Mimik Suite workspace. Your signed-in email must match the address the invite was sent to."
          )}
        </p>
      </div>

      <button className="auth-form__submit" type="button" onClick={onAccept} disabled={busy}>
        {busy ? "Accepting…" : "Accept invitation"}
      </button>

      <form action="/api/auth/logout" method="post">
        <button className="auth-form__secondary" type="submit">
          Not you? Sign out
        </button>
      </form>
    </div>
  );
}
