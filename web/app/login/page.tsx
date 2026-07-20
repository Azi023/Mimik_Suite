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
 * Split-screen sign-in (shadcn "Studio Admin" reference): a theme-invariant dark
 * brand panel beside the form. The form POSTs to the `/api/auth/login` route handler,
 * which does the Supabase exchange server-side and sets httpOnly cookies — so it works
 * with JavaScript disabled and never exposes the anon key to the client. Accounts are
 * invite-only (no self-serve register); social login is deferred.
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
      <aside className="auth-brand" aria-hidden="true">
        <div className="auth-brand__inner">
          <span className="auth-brand__mark">M</span>
          <h2 className="auth-brand__headline">Mimik Suite</h2>
          <p className="auth-brand__tagline">Done-for-you creative, on autopilot.</p>
        </div>
      </aside>

      <section className="auth-panel">
        <form className="auth-form" action="/api/auth/login" method="post">
          <div className="auth-form__head">
            <h1 className="auth-form__title">Sign in</h1>
            <p className="auth-form__sub">Welcome back. Enter your details to continue.</p>
          </div>

          {error !== undefined && error !== "" && (
            <p className="auth-form__error" role="alert">
              {error}
            </p>
          )}

          <label className="auth-field">
            <span className="auth-field__label">Email address</span>
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

          <button className="auth-form__submit" type="submit">
            Sign in
          </button>
        </form>
      </section>
    </main>
  );
}
