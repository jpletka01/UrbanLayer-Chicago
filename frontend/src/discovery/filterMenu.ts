// Which filters the "+ Add filter" menu lists, and in what order (redesign Phase 3a).
//
//   essentials   the registry's `tier: "essential"` filters that have data
//   more         every other filter that has data
//   soon         filters with NO data in this index, whatever their tier
//
// Tier is presentation only (the registry says so, and no evaluator code reads it); whether a
// filter has data is the index's `populatedFields`, so a data refresh moves a filter out of
// "soon" with no code change. Registry order is kept inside each group.

import { isPopulated } from "./coverage";
import type { FilterDef, Registry } from "./types";

export interface MenuGroups {
  essentials: FilterDef[];
  more: FilterDef[];
  soon: FilterDef[];
}

/** `nameOf` is the localized display name, so the search box matches what the user reads. */
export function menuGroups(registry: Registry, query: string, nameOf: (def: FilterDef) => string): MenuGroups {
  const q = query.trim().toLowerCase();
  const out: MenuGroups = { essentials: [], more: [], soon: [] };
  for (const def of registry.filters) {
    if (q && !nameOf(def).toLowerCase().includes(q)) continue;
    if (!isPopulated(registry, def.id)) out.soon.push(def);
    else if (def.tier === "essential") out.essentials.push(def);
    else out.more.push(def);
  }
  return out;
}

/** Elements that open or toggle the filter popover carry this attribute, so an outside click on
 *  them is theirs to handle (otherwise the popover would close and instantly reopen). */
export const FILTER_POPOVER_ANCHOR = "data-filter-popover-anchor";

/** Filters that are heuristics, not measured facts: the menu and the chip say so. */
export const HEURISTIC_FILTERS: ReadonlySet<string> = new Set(["upside_score"]);
