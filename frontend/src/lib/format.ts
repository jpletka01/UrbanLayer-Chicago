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

/**
 * Translate a FEMA flood-zone subtype (free-text `ZONE_SUBTY`, e.g.
 * "AREA OF MINIMAL FLOOD HAZARD") into the active language. Falls back to a
 * humanized version of the raw value when no translation exists.
 */
export function translateFloodSubtype(subtype: string | null | undefined): string {
  if (!subtype) return "";
  const norm = subtype.toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_|_$/g, "");
  const key = `data:terms.floodSubtypes.${norm}`;
  const translated = i18n.t(key);
  if (translated !== key) return translated;
  return humanizeShoutyCase(subtype);
}

/**
 * Localize the enumerable free-text qualifiers embedded in backend zone-definition
 * values ("50 ft (varies by lot frontage)", "No max (bonuses available)") and the
 * "ft" unit. English passes through byte-identical.
 */
export function localizeZoningValue(value: string | null | undefined): string {
  if (!value) return value ?? "";
  if (i18n.language.startsWith("en")) return value;
  if (value === "No max (bonuses available)") return i18n.t("data:zoning.noMaxBonuses");
  return value
    .replace("(varies by lot frontage)", `(${i18n.t("data:zoning.variesByLotFrontage")})`)
    .replace(/\bft\b/g, i18n.t("data:zoning.feetUnit"));
}
