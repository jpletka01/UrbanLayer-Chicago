// Human-readable values for range filters.
//
// `RangeDisplay` has been on the registry's range metadata since PR2 but nothing ever
// consumed it — min/max boxes showed raw numbers. The slider needs it for `aria-valuetext`
// (a screen reader announcing "250000" for a price is far worse than "$250,000") and the
// same formatting reads better in the visible bounds.

import type { RangeDisplay } from "./types";

/** Thousands separators, no decimals. `year` deliberately opts out — 1954, not 1,954. */
const group = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 0 });

/**
 * Format one endpoint of a range for display and for `aria-valuetext`.
 *
 * `unit` is the registry's optional free-text unit; it is appended only for displays that
 * don't already carry their own symbol, so we never produce "$250,000 dollars".
 */
export function formatRangeValue(
  value: number,
  display: RangeDisplay | undefined,
  unit?: string | null,
): string {
  if (!Number.isFinite(value)) return "";

  switch (display) {
    case "usd":
      // Money is grouped and prefixed; large domains (up to $5M here) stay readable
      // as full numbers, which is what a search filter wants — $1.2M hides precision
      // the user just typed.
      return `$${group(value)}`;

    case "percent":
      // Stored 0–1 on the registry (improvement_ratio domain is [0, 1]).
      return `${Math.round(value * 100)}%`;

    case "far":
      // FAR is meaningful to one decimal (step is 0.5) and must not be grouped.
      return Number.isInteger(value) ? String(value) : value.toFixed(1);

    case "mi":
      return `${value} mi`;

    case "year":
      // No separator: a year is an identifier, not a quantity.
      return String(Math.round(value));

    case "score":
    case "count":
    case "number":
    default: {
      const base = group(value);
      return unit ? `${base} ${unit}` : base;
    }
  }
}
