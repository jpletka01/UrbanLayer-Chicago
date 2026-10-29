// "Index built <date> · all 77 community areas" — the one honest line about how current and
// how wide the data under this page is. Sourced ONLY from registry.coverage (presentational;
// never the CQS). Nothing is shown when there is no index or no build date, so it can never
// claim a date it does not have.

import { useTranslation } from "react-i18next";
import { coverageOf, formatAsOf } from "./coverage";
import type { Registry } from "./types";

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
