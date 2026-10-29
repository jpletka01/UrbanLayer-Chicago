// The honest three-state recipe badge, shared by the recipe shelf and the Start panel:
// "Needs data" when a field the recipe touches is unpopulated; "No matches yet" when the
// fields ARE populated but the recipe's subset is empty in this index (the LIVE-but-empty
// trap a field-only check misses); else "Live · N" with the real result count.

import type { TFunction } from "i18next";
import { missingFieldsFor } from "./coverage";
import type { Registry, TopicDef } from "./types";

export type BadgeTone = "neutral" | "positive" | "warning";

export interface RecipeStatus {
  live: boolean;
  badge: string;
  tone: BadgeTone;
  title?: string;
}

/** The honest three-state badge, shared by the shelf and the Start panel: "Needs data" when a
 * field the recipe touches is unpopulated, "No matches yet" when the fields are populated
 * but the subset is empty in this index, else "Live · N". */
export function recipeStatus(
  registry: Registry,
  topic: TopicDef,
  t: TFunction<"pages">,
): RecipeStatus {
  const missing = missingFieldsFor(registry, Object.keys(topic.presets));
  const count = registry.recipeCounts?.[topic.id] ?? 0;
  if (missing.length > 0) {
    const labels = missing.map((id) => t(`discovery.filter.${id}`, { defaultValue: registry.filters.find((f) => f.id === id)?.label ?? id }));
    return { live: false, badge: t("discovery.needsData"), tone: "warning", title: t("discovery.needsDataTitle", { labels: labels.join(", ") }) };
  }
  if (count === 0) {
    return { live: false, badge: t("discovery.noMatchesYet"), tone: "neutral", title: t("discovery.noMatchesTitle") };
  }
  return { live: true, badge: t("discovery.liveBadge", { count: count.toLocaleString() }), tone: "positive" };
}

