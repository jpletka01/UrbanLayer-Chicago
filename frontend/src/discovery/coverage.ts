// Coverage + populatedFields selectors (PR4) — the SINGLE source both consumers read
// (the filter panel's "coming" disable + the recipe shelf's LIVE/NEEDS-DATA badges).
//
// Safe defaults are baked in here: a registry missing these fields (e.g. an older
// localStorage-cached payload) reads as fully dormant — coverage "none", nothing
// populated — never "all available". This mirrors the backend's missing-meta default.

import type { Registry } from "./types";

/** True only when the filter's underlying field has real data in the current index. */
export function isPopulated(registry: Registry, filterId: string): boolean {
  return (registry.populatedFields ?? []).includes(filterId);
}

/** Filter ids a recipe touches that are NOT yet populated (drives its NEEDS-DATA badge). */
export function missingFieldsFor(registry: Registry, filterIds: string[]): string[] {
  return filterIds.filter((id) => !isPopulated(registry, id));
}
