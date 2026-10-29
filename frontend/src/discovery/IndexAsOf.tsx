// "Index built <date> · all 77 community areas" — the one honest line about how current and
// how wide the data under this page is. Sourced ONLY from registry.coverage (presentational;
// never the CQS). Nothing is shown when there is no index or no build date, so it can never
// claim a date it does not have.

import { useTranslation } from "react-i18next";
import { coverageOf } from "./coverage";
import type { Registry } from "./types";

/** ISO date (YYYY-MM-DD) → a localized date that cannot shift with the viewer's time zone. */
export function formatAsOf(iso: string, language: string): string | null {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(language, { timeZone: "UTC", year: "numeric", month: "short", day: "numeric" });
}

export function IndexAsOf({ registry, className = "" }: { registry: Registry; className?: string }) {
  const { t, i18n } = useTranslation("pages");
  const coverage = coverageOf(registry);
  if (coverage.mode === "none" || !coverage.asOf) return null;
  const date = formatAsOf(coverage.asOf, i18n.language);
  if (!date) return null;
  const count = coverage.liveAreas.length;
  const areas =
    coverage.mode === "all" ? t("discovery.indexAreasAll", { count }) : t("discovery.indexAreasSome", { count });
  return (
    <p className={`text-micro text-text-muted ${className}`} data-testid="discovery-index-as-of">
      {t("discovery.indexAsOf", { date, areas })}
    </p>
  );
}
