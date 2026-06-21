import type { ScorecardResponse } from "./api";
import type { ScorecardContext } from "./types";

// Sales beyond the nearest few add tokens without changing the comp picture;
// the summary stats (median, range, volume) already span the full set.
const MAX_COMP_SALES = 8;

/**
 * Build the chat-grounding payload from a held ScorecardResponse.
 *
 * Selective by design (see backend ScorecardContext): only the property /
 * regulatory / incentives / zoning facts + comparables — never the
 * neighborhood-activity feeds (crime/311/permits/...) or code_chunks, which are
 * stale-prone or cheaply re-fetched when a question actually needs them. The
 * sub-objects are lifted verbatim from the already-assembled response; only the
 * comparables sales list is trimmed.
 *
 * Returns null when the response has no authoritative pin — without one the
 * backend gate can't match it to the turn, so there's nothing to ship.
 */
export function buildScorecardContext(resp: ScorecardResponse | null): ScorecardContext | null {
  if (!resp || !resp.resolved_pin) return null;

  const comps = resp.comparables;
  const trimmedComparables = comps
    ? { ...comps, sales: comps.sales.slice(0, MAX_COMP_SALES) }
    : null;

  return {
    pin: resp.resolved_pin,
    address: resp.address,
    community_area_name: resp.community_area_name,
    lat: resp.resolved_lat,
    lon: resp.resolved_lon,
    parcel_zoning: resp.context.parcel_zoning ?? null,
    zone_definition: (resp.zone_definition as Record<string, unknown> | null) ?? null,
    property: resp.context.property ?? null,
    regulatory: resp.context.regulatory ?? null,
    incentives: resp.context.incentives ?? null,
    comparables: trimmedComparables,
  };
}
