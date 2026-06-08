// Shared display formatters.

import i18n from "./i18n";

const LOCALE_MAP: Record<string, string> = { en: "en-US", es: "es-MX" };

/** Format an ISO date string as e.g. "Jan 5, 2026". Falls back to the raw string. */
export function formatDate(iso: string): string {
  if (!iso) return "";
  const t = new Date(iso);
  if (isNaN(t.getTime())) return iso;
  const locale = LOCALE_MAP[i18n.language] ?? "en-US";
  return t.toLocaleDateString(locale, { month: "short", day: "numeric", year: "numeric" });
}
