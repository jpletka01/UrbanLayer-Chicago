// Pricing in the new UI (decision Items 119, 123): Pro is $19 a month or $199 a year. Pure figures, so the page and
// Settings say the same thing. Prices are whole cents; the browser never sends a price, only the interval.
import type { BillingInterval } from "../../lib/api";

export const PRICE_CENTS: Record<BillingInterval, number> = { month: 1900, year: 19900 };

/** What a year costs paying monthly, minus the yearly price: $29. */
export function yearlySavingsCents(): number {
  return PRICE_CENTS.month * 12 - PRICE_CENTS.year;
}

/** The yearly price per month, rounded down to the cent ($16.58), so the page never overstates the saving. */
export function yearlyPerMonthCents(): number {
  return Math.floor(PRICE_CENTS.year / 12);
}

export function dollars(cents: number, locale: string): string {
  const whole = cents % 100 === 0;
  return new Intl.NumberFormat(locale, {
    style: "currency", currency: "USD",
    minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: whole ? 0 : 2,
  }).format(cents / 100);
}

/** A Chicago day (YYYY-MM-DD from the server) as "Dec 13, 2026" / "13 dic 2026", read at noon so no time zone moves it. */
export function chicagoDay(day: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { month: "short", day: "numeric", year: "numeric" })
    .format(new Date(`${day}T12:00:00`));
}

export type PlanState = "admin" | "confirming" | "pro_ending" | "pro_past_due" | "pro_renewing" | "voucher" | "free";

/** Which Plan state Settings shows. `confirming`: back from Stripe (`?checkout=done`) and the webhook hasn't landed. */
export function planState(sub: {
  plan: "free" | "pro" | "admin"; source: "stripe" | "voucher" | null; ends_on: string | null; past_due: boolean;
} | null, tier: string | undefined, returning: boolean): PlanState {
  const plan = sub?.plan ?? (tier === "admin" ? "admin" : tier === "premium" ? "pro" : "free");
  if (plan === "admin") return "admin";
  if (sub?.source === "stripe") {
    if (sub.past_due) return "pro_past_due";
    return sub.ends_on ? "pro_ending" : "pro_renewing";
  }
  if (returning) return "confirming";
  if (plan === "pro") return "voucher";
  return "free";
}
