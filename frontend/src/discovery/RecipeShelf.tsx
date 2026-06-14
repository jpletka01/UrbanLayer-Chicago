// Recipe shelf (PR8) — the query-first front door. Each recipe is a topic preset; clicking
// one expands it into panel state on the FE (the backend never re-expands; topicId is
// telemetry). Badges are honest, in three states: "Needs data" when a field the recipe
// touches is unpopulated; "No matches yet" when the fields ARE populated but the recipe's
// subset is empty in this index (the LIVE-but-empty trap a field-only check misses); else
// "Live · N" with the real result count. Coverage copy is read from registry.coverage
// (presentational) — recipes never touch the CQS coverage path.

import { coverageOf, liveAreaNames, missingFieldsFor } from "./coverage";
import type { Registry, TopicDef } from "./types";

function labelsFor(registry: Registry, ids: string[]): string[] {
  return ids.map((id) => registry.filters.find((f) => f.id === id)?.label ?? id);
}

export function RecipeShelf({
  registry,
  onPick,
  horizontal = false,
}: {
  registry: Registry;
  onPick: (topic: TopicDef) => void;
  horizontal?: boolean; // mobile: a horizontal scroll-snap row instead of a stacked grid
}) {
  if (!registry.topics.length) return null;
  const coverage = coverageOf(registry);
  const coverageNote = coverage.mode === "partial" ? ` · live in ${liveAreaNames(registry)}` : "";

  return (
    <div>
      <h3 className="mb-2 text-[10px] uppercase tracking-wider text-text-muted">
        Common recipes{coverageNote}
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
          const missingLabels = labelsFor(registry, missing);

          let badge: string;
          let badgeClass: string;
          let title: string | undefined;
          if (!fieldsReady) {
            badge = "Needs data";
            badgeClass = "text-amber-400/80";
            title = `Needs data: ${missingLabels.join(", ")}`;
          } else if (count === 0) {
            badge = "No matches yet";
            badgeClass = "text-text-muted";
            title = "No parcels match this recipe in the indexed area yet.";
          } else {
            badge = `● Live · ${count.toLocaleString()}`;
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
                <span className="text-xs font-medium text-text-primary">{topic.label}</span>
                <span className={`flex-shrink-0 text-[10px] ${badgeClass}`}>{badge}</span>
              </div>
              {topic.description && (
                <p className="mt-0.5 text-[11px] text-text-muted">{topic.description}</p>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
