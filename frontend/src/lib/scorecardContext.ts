import i18n from "./i18n";
import type { ScorecardResponse } from "./api";
import type { ScorecardContext, VerdictGrounding, AddressViolationsGrounding } from "./types";
import { computeVerdict, type TFunc } from "./scorecardVerdict";

// Sales beyond the nearest few add tokens without changing the comp picture;
// the summary stats (median, range, volume) already span the full set.
const MAX_COMP_SALES = 8;

// Starter chips fire on heavy traffic only when it's decision-relevant.
const HEAVY_TRAFFIC_ADT = 15000;

/**
 * Flag-aware starter keys for the grounded "Ask about this property" empty
 * state, priority-ordered and capped at 4 (ChatInterface translates them via
 * chat:propertyStarters.*). Conditional slots fire on NOTABLE data only:
 * - chrs: an orange/red CHRS rating triggers demolition-permit review —
 *   consequence-laden, exactly what an analyst chat is for.
 * - comparables: only when sales back it (never a dead-end prompt).
 * - traffic: only at retail-relevant volume (≥15k vehicles/day).
 * - incentives: only the discriminating designations (TIF/OZ/EZ — grants, TOD,
 *   ADU, ARO are near-universal and would make the fallback dead code).
 * - neighborhood: the fallback when nothing rarer claims the last slot.
 */
export function propertyStarterKeys(ctx: ScorecardContext | null): string[] {
  if (!ctx) return [];
  const cmp = ctx.comparables;
  const hasComps = !!cmp && ((cmp.sales_volume ?? 0) > 0 || (cmp.sales?.length ?? 0) > 0);
  const inc = ctx.incentives;
  const hasProgram = !!(inc?.in_tif_district || inc?.in_opportunity_zone || inc?.in_enterprise_zone);
  const chrsRating = ctx.property?.flags?.chrs_rating;
  const hasChrs = chrsRating === "orange" || chrsRating === "red";
  const hasHeavyTraffic = (ctx.traffic?.daily_vehicles ?? 0) >= HEAVY_TRAFFIC_ADT;
  return [
    "build",
    "zoning",
    ...(hasChrs ? ["chrs"] : []),
    ...(hasComps ? ["comparables"] : []),
    ...(hasHeavyTraffic ? ["traffic"] : []),
    ...(hasProgram ? ["incentives"] : []),
    "neighborhood",
  ].slice(0, 4);
}

// Verdict strings resolve through the pages namespace (same keys the band uses).
const groundingT: TFunc = (key, opts) => i18n.t(key, { ns: "pages", ...opts }) as string;

// Distill the computed ScorecardVerdict to the grounding shape: drop the UI-only
// nextStep/cardAnchor, surface the dominant negative reason as the binding constraint.
function distillVerdict(resp: ScorecardResponse): VerdictGrounding {
  const v = computeVerdict(resp, groundingT);
  const binding = v.reasons.find((r) => r.polarity === "negative")?.text ?? null;
  return {
    category: v.category,
    headline: v.headline,
    binding_constraint: binding,
    reasons: v.reasons.map((r) => ({ text: r.text, polarity: r.polarity })),
    confidence: v.confidence,
    caveats: v.caveats,
    signals: {
      allowedFar: v.signals.allowedFar,
      existingFar: v.signals.existingFar,
      capacityBand: v.signals.capacityBand,
      incentiveStrength: v.signals.incentiveStrength,
      frictionFlags: v.signals.frictionFlags,
    },
  };
}

// Derive the address-scoped violation tri-state from the held response — the SAME
// three states ScorecardPage renders. context.violations is address-exact here (the
// /api/scorecard path fills it from _address_violations_data, not the area feed), so
// a non-null summary is a real at-address record. violations_checked distinguishes a
// confirmed zero (lookup ran, none) from an unconfirmed lookup (address didn't parse).
function deriveAddressViolations(resp: ScorecardResponse): AddressViolationsGrounding {
  const summary = resp.context.violations ?? null;
  if (summary) return { status: "present", summary };
  if (resp.violations_checked) return { status: "confirmed_zero", summary: null };
  return { status: "unconfirmed", summary: null };
}

/**
 * Build the chat-grounding payload from a held ScorecardResponse.
 *
 * Parcel-only by design (see backend ScorecardContext): property / regulatory /
 * incentives / zoning facts + comparables + the computed verdict — never the
 * neighborhood-activity feeds (crime/311/permits/...), which are area-level and
 * re-fetch via normal retrieval when a question needs them.
 *
 * Two tiers, by identity confidence:
 *  - **pin present** (authoritative parcel): full grounding incl. property/comps.
 *  - **pin null** (unverified/nearest): zoning-only — ship the point-resolved,
 *    identity-independent facts (zoning/regulatory/incentives) + the (already
 *    caveated) verdict, and OMIT property/comparables, which are PIN-keyed and
 *    could belong to a neighbor. Returns null only when there's no zoning at all.
 */
export function buildScorecardContext(resp: ScorecardResponse | null): ScorecardContext | null {
  if (!resp) return null;
  const hasPin = !!resp.resolved_pin;

  // Point-resolved, identity-independent facts ship in both tiers.
  if (!hasPin && !resp.zone_definition && !resp.context.parcel_zoning) return null;

  const base: ScorecardContext = {
    pin: resp.resolved_pin,
    address: resp.address,
    community_area_name: resp.community_area_name,
    lat: resp.resolved_lat,
    lon: resp.resolved_lon,
    parcel_zoning: resp.context.parcel_zoning ?? null,
    zone_definition: (resp.zone_definition as Record<string, unknown> | null) ?? null,
    regulatory: resp.context.regulatory ?? null,
    incentives: resp.context.incentives ?? null,
    verdict: distillVerdict(resp),
    // Address-keyed (not PIN-keyed) → identity-independent, so it ships in BOTH
    // tiers: the page shows the at-address violation state regardless of pin, so
    // the chat must be able to affirm it on the nearest-parcel case too.
    address_violations: deriveAddressViolations(resp),
    // Nearest measured street (lat/lon-scoped, identity-independent) — lets a
    // grounded "what's the traffic like here" answer from the page's number.
    traffic: resp.context.neighborhood?.traffic ?? null,
  };

  // Zoning-only tier. DO NOT add property/comparables here: with no verified PIN
  // the parcel resolved nearest-by-distance, so those PIN-keyed fields may belong
  // to a NEIGHBOR. Shipping them as grounding (even caveated) re-introduces the
  // exact parcel/area conflation this payload exists to prevent — omit, don't
  // ship-and-caveat. Signed off 2026-06-29. (Covered by scorecardContext.test.ts.)
  if (!hasPin) return base;

  const comps = resp.comparables;
  return {
    ...base,
    property: resp.context.property ?? null,
    comparables: comps ? { ...comps, sales: comps.sales.slice(0, MAX_COMP_SALES) } : null,
  };
}
