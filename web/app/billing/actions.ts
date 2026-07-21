"use server";

import { ApiError, startCheckout } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/**
 * Server action for the billing surface. "Send quote" mints a Stripe checkout/payment link the
 * operator shares with the client. Runs server-side with the httpOnly session bearer; the backend
 * confines a client principal to its own client and 503s gracefully when Stripe isn't configured
 * (constraint #7 — no paid APIs wired in the build phase).
 */

export interface CheckoutLinkResult {
  ok: boolean;
  /** The checkout/payment URL to send the client, on success. */
  url?: string;
  error?: string;
}

export async function sendCheckoutLinkAction(clientId: string): Promise<CheckoutLinkResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    const result = await startCheckout(clientId, token);
    return { ok: true, url: result.checkout_url };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 503) {
        return { ok: false, error: "Billing isn't connected yet (no payment provider configured)." };
      }
      if (error.status === 403 || error.status === 404) {
        return { ok: false, error: "You can't create a quote for this client." };
      }
    }
    return { ok: false, error: "Could not create the quote link. Try again." };
  }
}
