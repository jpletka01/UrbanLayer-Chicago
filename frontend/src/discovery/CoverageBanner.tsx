// Coverage banner (PR4). A standalone, dataset-level scope notice sourced ONLY from
// registry.coverage — never from response.cqs. It is NOT a chip: it cannot be removed,
// never enters the CQS / userFilters / panelState, and renders even before any search.

import { useTranslation } from "react-i18next";
import { coverageOf, liveAreaNames } from "./coverage";
import type { Registry } from "./types";

export function CoverageBanner({ registry }: { registry: Registry }) {
  const { t } = useTranslation("pages");
  const coverage = coverageOf(registry);
  if (coverage.mode === "all") return null; // full city — no scope caveat needed

  const text =
    coverage.mode === "none"
      ? t("discovery.coverageNone")
      : t("discovery.coveragePartial", { areas: liveAreaNames(registry) });

  return (
    <div
      role="status"
      className="flex items-start gap-2 border-b border-dark-border bg-dark-elevated/40 px-4 py-2 text-micro text-text-secondary"
    >
      <span aria-hidden className="mt-px text-text-muted">
        ⓘ
      </span>
      <span>{text}</span>
    </div>
  );
}
