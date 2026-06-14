// UI compiler (04.1) — pure: filter-panel control state → userFilters.
// One predicate per active control; a cleared/invalid control omits its key (absent = no
// constraint, R1). The result is the `user` fragment the backend tags source:"user".

import type { FilterId, PanelState, Predicate } from "./types";

/** R1/R6: empty enum/region or a boundless range is invalid; an inverted range is valid. */
export function predicateIsValid(p: Predicate): boolean {
  switch (p.kind) {
    case "enum":
      return p.values.length > 0;
    case "region":
      return p.regions.length > 0;
    case "range":
      return p.min != null || p.max != null;
    case "flag":
      return true;
  }
}

/** Pure: panel state → userFilters, dropping cleared/invalid controls. */
export function compilePanel(state: PanelState): Record<FilterId, Predicate> {
  const out: Record<FilterId, Predicate> = {};
  for (const [id, pred] of Object.entries(state)) {
    if (predicateIsValid(pred)) out[id] = pred;
  }
  return out;
}
