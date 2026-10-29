// Recipe shelf (PR8) — the query-first front door. Each recipe is a topic preset; clicking
// one expands it into panel state on the FE (the backend never re-expands; topicId is
// telemetry). Badges are honest, in three states: "Needs data" when a field the recipe
// touches is unpopulated; "No matches yet" when the fields ARE populated but the recipe's
// subset is empty in this index (the LIVE-but-empty trap a field-only check misses); else
// "Live · N" with the real result count. Coverage copy is read from registry.coverage
// (presentational) — recipes never touch the CQS coverage path.

import { useTranslation } from "react-i18next";
import { Chip } from "../components/ui/Chip";
import { coverageOf, liveAreaNames } from "./coverage";
import { recipeStatus } from "./recipeStatus";
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
  if (!registry.topics.length) return null;
  const coverage = coverageOf(registry);
  const coverageNote = coverage.mode === "partial" ? t("discovery.liveIn", { areas: liveAreaNames(registry) }) : "";

  return (
    <div>
      <h3 className="mb-2 text-overline uppercase text-text-muted">
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
          const { live, badge, tone: badgeTone, title } = recipeStatus(registry, topic, t);
          return (
            <button
              key={topic.id}
              type="button"
              onClick={() => onPick(topic)}
              title={title}
              className={`rounded-lg border border-dark-border p-2.5 text-left transition-colors hover:border-dark-border-strong ${
                live ? "" : "opacity-70"
              } ${horizontal ? "min-w-[200px] flex-shrink-0 snap-start" : ""}`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-caption font-medium text-text-primary">
                  {t(`discovery.topic.${topic.id}.label`, { defaultValue: topic.label ?? "" })}
                </span>
                <Chip size="sm" tone={badgeTone} className="flex-shrink-0">{badge}</Chip>
              </div>
              {topic.description && (
                <p className="mt-0.5 text-micro text-text-muted">
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
