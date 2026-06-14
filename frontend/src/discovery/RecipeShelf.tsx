// Recipe shelf (PR8) — the query-first front door. Each recipe is a topic preset; clicking
// one expands it into panel state on the FE (the backend never re-expands; topicId is
// telemetry). Badges are honest: LIVE iff every field the recipe touches is populated, else
// "Needs data" (pre-index that's every recipe). Coverage copy is read from registry.coverage
// (presentational) — recipes never touch the CQS coverage path.

import { coverageOf, liveAreaNames, missingFieldsFor } from "./coverage";
import type { Registry, TopicDef } from "./types";

function labelsFor(registry: Registry, ids: string[]): string[] {
  return ids.map((id) => registry.filters.find((f) => f.id === id)?.label ?? id);
}

export function RecipeShelf({
  registry,
  onPick,
}: {
  registry: Registry;
  onPick: (topic: TopicDef) => void;
}) {
  if (!registry.topics.length) return null;
  const coverage = coverageOf(registry);
  const coverageNote = coverage.mode === "partial" ? ` · live in ${liveAreaNames(registry)}` : "";

  return (
    <div>
      <h3 className="mb-2 text-[10px] uppercase tracking-wider text-text-muted">
        Common recipes{coverageNote}
      </h3>
      <div className="grid grid-cols-1 gap-2">
        {registry.topics.map((topic) => {
          const missing = missingFieldsFor(registry, Object.keys(topic.presets));
          const live = missing.length === 0;
          const missingLabels = labelsFor(registry, missing);
          return (
            <button
              key={topic.id}
              type="button"
              onClick={() => onPick(topic)}
              title={live ? undefined : `Needs data: ${missingLabels.join(", ")}`}
              className={`rounded-lg border border-dark-border p-2.5 text-left transition-colors hover:border-text-muted ${
                live ? "" : "opacity-70"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-medium text-text-primary">{topic.label}</span>
                <span
                  className={`flex-shrink-0 text-[10px] ${
                    live ? "text-emerald-400/90" : "text-amber-400/80"
                  }`}
                >
                  {live ? "● Live" : "Needs data"}
                </span>
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
