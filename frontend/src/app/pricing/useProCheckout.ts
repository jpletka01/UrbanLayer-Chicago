// Starting Pro checkout, shared by Pricing and Settings → Plan (Item 123).
import { useState } from "react";
import { CheckoutError, createBillingPortal, createCheckoutSession, type BillingInterval } from "../../lib/api";

export function localeOf(lang: string): string {
  return lang.startsWith("es") ? "es-MX" : "en-US";
}

/** Start Pro checkout (or, for an account that already has it, the billing portal) and leave for Stripe. */
export function useProCheckout(origin: "settings" | "pricing") {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start(interval: BillingInterval) {
    setBusy(true);
    setError(null);
    try {
      const { url } = await createCheckoutSession(interval, origin);
      window.location.assign(url);
    } catch (e) {
      const reason = e instanceof CheckoutError ? e.reason : "error";
      if (reason === "already_subscribed") {
        try {
          window.location.assign((await createBillingPortal()).url);
          return;
        } catch { /* fall through to the message */ }
      }
      setError(reason);
      setBusy(false);
    }
  }

  async function manage() {
    setBusy(true);
    setError(null);
    try {
      window.location.assign((await createBillingPortal()).url);
    } catch {
      setError("portal");
      setBusy(false);
    }
  }

  return { busy, error, start, manage };
}
