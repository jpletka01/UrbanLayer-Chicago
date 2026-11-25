// Shared display formatters.

import i18n from "./i18n";
import type { Amendment } from "./types";

const LOCALE_MAP: Record<string, string> = { en: "en-US", es: "es-MX" };

/** Format an ISO date string as e.g. "Jan 5, 2026". Falls back to the raw string. */
export function formatDate(iso: string): string {
  if (!iso) return "";
  const t = new Date(iso);
  if (isNaN(t.getTime())) return iso;
  const locale = LOCALE_MAP[i18n.language] ?? "en-US";
  return t.toLocaleDateString(locale, { month: "short", day: "numeric", year: "numeric" });
}

/** Format a calendar day ("2026-10-14") as "Oct 14, 2026" without a timezone shift
 * (`formatDate` parses day-only strings as UTC, which shows the day before in Chicago). */
export function formatDay(iso: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  if (!m) return iso ?? "";
  const locale = LOCALE_MAP[i18n.language] ?? "en-US";
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).toLocaleDateString(locale, {
    month: "short", day: "numeric", year: "numeric",
  });
}

// Tokens kept uppercase when re-casing ALL-CAPS dataset values.
const ACRONYMS = new Set([
  "CTA", "CDOT", "CPD", "CFD", "ADA", "TIF", "ARO", "TOD", "SSA",
  "LIHTC", "NMTC", "DOB", "UIC", "IDOT", "II", "III", "IV",
]);

/**
 * Re-case an ALL-CAPS dataset value for display ("MOTOR VEHICLE THEFT" →
 * "Motor vehicle theft"). In mixed-case values only long shouty words are
 * tamed ("Tree Trim Request (NO LONGER BEING ACCEPTED)" → "(no longer being
 * accepted)") so human-edited casing and short acronyms survive.
 */
export function humanizeShoutyCase(value: string): string {
  const allCaps = value === value.toUpperCase();
  const words = value.split(/\s+/);
  const shouty = words.map(w => w === w.toUpperCase() && /[A-Z]/.test(w));
  return words
    .map((w, i) => {
      const bare = w.replace(/[^a-zA-Z0-9]/g, "").toUpperCase();
      if (ACRONYMS.has(bare)) return w.toUpperCase();
      if (!shouty[i]) return w;
      // In mixed-case values, lone short caps ("US", "PD") are likely acronyms —
      // recase them only inside a shouty run ("NO LONGER BEING ACCEPTED").
      const inRun = shouty[i - 1] || shouty[i + 1];
      if (!allCaps && bare.length <= 3 && !inRun) return w;
      const lower = w.toLowerCase();
      return i === 0 ? lower.charAt(0).toUpperCase() + lower.slice(1) : lower;
    })
    .join(" ");
}

/** applied → reflected; pending / never reviewed → not yet reviewed; reviewed, no change → not reflected. */
export function amendmentStatus(a: Pick<Amendment, "review_status" | "product_effect">): "applied" | "none" | "pending" {
  if (a.review_status !== "reviewed" || a.product_effect === "pending" || !a.product_effect) return "pending";
  return a.product_effect === "applied" ? "applied" : "none";
}

/** "100 N STATE ST" → "100 N State St": an all-caps record address in title case, with compass
    directions kept as capitals. */
export function titleCaseAddress(value: string): string {
  return value
    .split(/\s+/)
    .map((w) => {
      if (/^[NSEW]$/i.test(w)) return w.toUpperCase();
      if (/^\d/.test(w)) return w.toLowerCase(); // 1600-1610, 21st
      return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
    })
    .join(" ");
}
