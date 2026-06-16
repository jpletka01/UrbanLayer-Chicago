// Recipe shelf (PR8) — the query-first front door. Each recipe is a topic preset; clicking
// one expands it into panel state on the FE (the backend never re-expands; topicId is
// telemetry). Badges are honest, in three states: "Needs data" when a field the recipe
// touches is unpopulated; "No matches yet" when the fields ARE populated but the recipe's
// subset is empty in this index (the LIVE-but-empty trap a field-only check misses); else
// "Live · N" with the real result count. Coverage copy is read from registry.coverage
// (presentational) — recipes never touch the CQS coverage path.

import { useTranslation } from "react-i18next";
import { coverageOf, liveAreaNames, missingFieldsFor } from "./coverage";
import type { Registry, TopicDef } from "./types";

export function RecipeShelf({
  registry,
  onPick,
  horizontal = false,
}: {
  registry: Registry;
  onPick: (topic: TopicDef) => void;
  horizontal?: boolean; // mobile: a horizontal scroll-snap row instead of a stacked grid
}) {
  const { t } = useTranslation("pages");
  const labelsFor = (ids: string[]): string[] =>
    ids.map((id) => t(`discovery.filter.${id}`, registry.filters.find((f) => f.id === id)?.label ?? id));
  if (!registry.topics.length) return null;
  const coverage = coverageOf(registry);
  const coverageNote = coverage.mode === "partial" ? t("discovery.liveIn", { areas: liveAreaNames(registry) }) : "";

  return (
    <div>
      <h3 className="mb-2 text-[10px] uppercase tracking-wider text-text-muted">
        {t("discovery.commonRecipes")}{coverageNote}
      </h3>
      <div
        className={
          horizontal
            ? "flex snap-x snap-mandatory gap-2 overflow-x-auto pb-1"
            : "grid grid-cols-1 gap-2"
        }
      >
        {registry.topics.map((topic) => {
          const missing = missingFieldsFor(registry, Object.keys(topic.presets));
          const fieldsReady = missing.length === 0;
          const count = registry.recipeCounts?.[topic.id] ?? 0;
          const live = fieldsReady && count > 0;
          const missingLabels = labelsFor(missing);

          let badge: string;
          let badgeClass: string;
          let title: string | undefined;
          if (!fieldsReady) {
            badge = t("discovery.needsData");
            badgeClass = "text-amber-400/80";
            title = t("discovery.needsDataTitle", { labels: missingLabels.join(", ") });
          } else if (count === 0) {
            badge = t("discovery.noMatchesYet");
            badgeClass = "text-text-muted";
            title = t("discovery.noMatchesTitle");
          } else {
            badge = t("discovery.liveBadge", { count: count.toLocaleString() });
            badgeClass = "text-emerald-400/90";
          }
          return (
            <button
              key={topic.id}
              type="button"
              onClick={() => onPick(topic)}
              title={title}
              className={`rounded-lg border border-dark-border p-2.5 text-left transition-colors hover:border-text-muted ${
                live ? "" : "opacity-70"
              } ${horizontal ? "min-w-[200px] flex-shrink-0 snap-start" : ""}`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-medium text-text-primary">
                  {t(`discovery.topic.${topic.id}.label`, { defaultValue: topic.label ?? "" })}
                </span>
                <span className={`flex-shrink-0 text-[10px] ${badgeClass}`}>{badge}</span>
              </div>
              {topic.description && (
                <p className="mt-0.5 text-[11px] text-text-muted">
                  {t(`discovery.topic.${topic.id}.description`, topic.description)}
                </p>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
