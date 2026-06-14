// Topic compiler (04.2) — pure static registry lookup: topicId → preset predicates.
// A topic is a named patch; the page folds its presets into panel state client-side so
// they remain individually editable/clearable (cleared-field rule, 04.4). The backend
// never re-expands a topic (topicId rides in meta as telemetry only).

import type { CQS, FilterId, PanelState, Predicate, Registry } from "./types";

/** Pure: expand a topic id to its preset predicates (empty if unknown / no topics). */
export function expandTopic(topicId: string, registry: Registry): Record<FilterId, Predicate> {
  const topic = registry.topics.find((t) => t.id === topicId);
  if (!topic) return {};
  // shallow copy so callers can mutate panel state without touching the registry
  return { ...topic.presets };
}

/** Pure: fold an evaluated CQS back into editable panel state (cleared-field rule, 06).
 * The ONLY way a one-tap re-issue rebuilds the panel — it never re-expands a topic (nor
 * does the backend; topicId is telemetry), so removing a chip drops exactly that id and
 * keeps the rest as plain user filters. */
export function panelFromCqs(cqs: CQS): PanelState {
  const out: PanelState = {};
  for (const [id, assignment] of Object.entries(cqs.filters)) {
    out[id] = assignment.predicate;
  }
  return out;
}
