// Topic compiler (04.2) — pure static registry lookup: topicId → preset predicates.
// A topic is a named patch; the page folds its presets into panel state client-side so
// they remain individually editable/clearable (cleared-field rule, 04.4). The backend
// never re-expands a topic (topicId rides in meta as telemetry only).

import type { FilterId, Predicate, Registry } from "./types";

/** Pure: expand a topic id to its preset predicates (empty if unknown / no topics). */
export function expandTopic(topicId: string, registry: Registry): Record<FilterId, Predicate> {
  const topic = registry.topics.find((t) => t.id === topicId);
  if (!topic) return {};
  // shallow copy so callers can mutate panel state without touching the registry
  return { ...topic.presets };
}
