"use client";

import { useState, useTransition, type JSX } from "react";
import Link from "next/link";
import type { ApiSubscription, ApiSubscriptionStatus } from "@/lib/api";
import { sendCheckoutLinkAction } from "@/app/billing/actions";

/** One client's billing row (subscription may be null = never subscribed). */
export interface ClientBilling {
  clientId: string;
  clientName: string;
  subscription: ApiSubscription | null;
}

const STATUS_LABEL: Record<ApiSubscriptionStatus, string> = {
  trialing: "Trialing",
  active: "Active",
  past_due: "Past due",
  canceled: "Canceled",
  incomplete: "Incomplete",
};

/** trialing/active grant access → green; past_due/incomplete → amber; canceled → red. */
function statusTone(status: ApiSubscriptionStatus): "ok" | "warn" | "bad" {
  if (status === "trialing" || status === "active") return "ok";
  if (status === "canceled") return "bad";
  return "warn";
}

function formatWhen(iso: string | null): string {
  if (iso === null) return "—";
  const d = new Date(iso);
  // Explicit locale — an implicit (environment) locale can differ between server and
  // client and cause a hydration mismatch. Same pattern as BriefsListView.formatDate.
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString("en-GB", { month: "short", day: "numeric", year: "numeric" });
}

interface BillingViewProps {
  rows: ClientBilling[];
}

/**
 * Per-client subscription overview + "Send quote". The quote action mints a checkout/payment link
 * via the server action and reveals it to copy + send (WhatsApp/email). Degrades honestly when the
 * payment provider isn't configured (constraint #7) — the button surfaces the 503 message inline.
 */
export function BillingView({ rows }: BillingViewProps): JSX.Element {
  const [pending, startTransition] = useTransition();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [links, setLinks] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [copied, setCopied] = useState<string | null>(null);

  function sendQuote(clientId: string): void {
    if (pending) return;
    setBusyId(clientId);
    setErrors((e) => ({ ...e, [clientId]: "" }));
    startTransition(async () => {
      const result = await sendCheckoutLinkAction(clientId);
      setBusyId(null);
      if (result.ok && result.url !== undefined) {
        setLinks((l) => ({ ...l, [clientId]: result.url as string }));
      } else {
        setErrors((e) => ({ ...e, [clientId]: result.error ?? "Could not create the quote." }));
      }
    });
  }

  async function copy(clientId: string, url: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(clientId);
    } catch {
      // clipboard blocked — the link is already visible for manual copy.
    }
  }

  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <p className="empty-state__title">No clients yet</p>
        <p className="empty-state__body">
          Onboard a client to manage their subscription and send a quote.
        </p>
        <Link href="/onboarding" className="btn-ghost">
          Onboard a client
        </Link>
      </div>
    );
  }

  return (
    <div className="tasks__table-wrap">
      <table className="tasks__table">
        <thead>
          <tr>
            <th>Client</th>
            <th>Subscription</th>
            <th>Renews</th>
            <th aria-label="Quote actions" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const link = links[row.clientId];
            const error = errors[row.clientId];
            return (
              <tr key={row.clientId}>
                <td>
                  <span className="tasks__title">{row.clientName}</span>
                  <Link className="tasks__joblink" href={`/clients/${row.clientId}/preferences`}>
                    taste profile ↗
                  </Link>
                </td>
                <td>
                  {row.subscription === null ? (
                    <span className="tasks__pill">No subscription</span>
                  ) : (
                    <span className={`billing__pill billing__pill--${statusTone(row.subscription.status)}`}>
                      {STATUS_LABEL[row.subscription.status]}
                    </span>
                  )}
                </td>
                <td className="tasks__when">
                  {formatWhen(row.subscription?.current_period_end ?? null)}
                </td>
                <td className="tasks__actions">
                  {link !== undefined ? (
                    <span className="billing__link">
                      <a href={link} target="_blank" rel="noreferrer" className="tasks__joblink">
                        quote link
                      </a>
                      <button
                        type="button"
                        className="btn btn--secondary btn--sm"
                        onClick={(): void => void copy(row.clientId, link)}
                      >
                        {copied === row.clientId ? "✓ Copied" : "Copy"}
                      </button>
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="btn btn--secondary btn--sm"
                      disabled={pending && busyId === row.clientId}
                      onClick={(): void => sendQuote(row.clientId)}
                    >
                      {pending && busyId === row.clientId ? "…" : "Send quote"}
                    </button>
                  )}
                  {error !== undefined && error !== "" && (
                    <span className="billing__err">{error}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
