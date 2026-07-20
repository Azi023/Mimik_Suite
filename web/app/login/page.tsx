import type { JSX } from "react";
import { redirect } from "next/navigation";
import { hasSession } from "@/lib/session";

// Auth state is per-request — never a build-time snapshot.
export const dynamic = "force-dynamic";

interface LoginPageProps {
  /** `?error=` set by the login route handler on a failed attempt. */
  searchParams: Promise<{ error?: string }>;
}

/**
 * Sign-in screen: a centered card on the dashboard canvas, styled with tokens only
 * (no new colors or radii). The form POSTs to the `/api/auth/login` route handler,
 * which handles the Supabase exchange server-side and sets httpOnly cookies — so it
 * works with JavaScript disabled and never exposes the anon key to the client.
 *
 * Already-authenticated visitors are bounced straight to the board.
 */
export default async function LoginPage({ searchParams }: LoginPageProps): Promise<JSX.Element> {
  if (await hasSession()) {
    redirect("/");
  }
  const { error } = await searchParams;

  return (
    <main className="auth">
      <form className="auth-card" action="/api/auth/login" method="post">
        <div className="auth-card__brand">
          <span className="auth-card__logo" aria-hidden="true">
            M
          </span>
          <div>
            <h1 className="auth-card__title">Mimik Studio</h1>
            <p className="auth-card__subtitle">Sign in to the creative ops board</p>
          </div>
        </div>

        {error !== undefined && error !== "" && (
          <p className="auth-card__error" role="alert">
            {error}
          </p>
        )}

        <label className="auth-field">
          <span className="auth-field__label">Email</span>
          <input
            className="auth-field__input"
            type="email"
            name="email"
            autoComplete="email"
            required
            placeholder="you@agency.com"
          />
        </label>

        <label className="auth-field">
          <span className="auth-field__label">Password</span>
          <input
            className="auth-field__input"
            type="password"
            name="password"
            autoComplete="current-password"
            required
            placeholder="••••••••"
          />
        </label>

        <button className="auth-card__submit" type="submit">
          Sign in
        </button>
      </form>
    </main>
  );
}
