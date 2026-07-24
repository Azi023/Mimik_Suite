import type { JSX } from "react";
import { redirect } from "next/navigation";
import { hasSession, sanitizeNextPath } from "@/lib/session";
import { DEFAULT_BRANDING } from "@/lib/branding";

// Auth state is per-request — never a build-time snapshot.
export const dynamic = "force-dynamic";

interface LoginPageProps {
  /**
   * `?error=` is set by the login route handler on a failed attempt. `?next=` is the same-origin
   * path to return to after a successful sign-in (e.g. an invite-accept round-trip); it is
   * sanitized before use and threaded through the form + any error re-render.
   */
  searchParams: Promise<{ error?: string; next?: string }>;
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
  const { error, next } = await searchParams;
  const safeNext = sanitizeNextPath(next);
  if (await hasSession()) {
    // Already authenticated: honor an in-flight return path (e.g. invite-accept), else the board.
    redirect(safeNext !== "" ? safeNext : "/");
  }

  // Pre-auth: the tenant is unknown (no session yet), so this uses the platform default branding.
  // True per-tenant login branding needs a host/subdomain signal — see the follow-up in lib/branding.ts.
  const branding = DEFAULT_BRANDING;

  return (
    <main className="auth">
      <aside className="auth-brand" aria-hidden="true">
        <div className="auth-brand__inner">
          <span className="auth-brand__mark">{branding.short_name.slice(0, 1).toUpperCase()}</span>
          <h2 className="auth-brand__headline">{branding.product_name}</h2>
          <p className="auth-brand__tagline">Done-for-you creative, on autopilot.</p>
        </div>
      </aside>

      <section className="auth-panel">
        <form className="auth-form" action="/api/auth/login" method="post">
          <div className="auth-form__head">
            <h1 className="auth-form__title">Sign in</h1>
            <p className="auth-form__sub">Welcome back. Enter your details to continue.</p>
          </div>

          {safeNext !== "" && <input type="hidden" name="next" value={safeNext} />}

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
