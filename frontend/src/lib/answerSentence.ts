// The Profile's answer sentence (redesign plan §4 principle 1, decision Item 50): ONE deterministic,
// number-backed sentence that answers "what can I build here?" and, when there is one, names the
// single biggest thing in the way. Templates per verdict state, filled from the verdict's own signals
// and the backend's unit yield: no LLM, no production credits, nothing recomputed. Jack reviews the
// wording once in the PR (Q2).
//
// Wording rules: the table "allows" (never "you can build"); a figure the verdict does not trust
// (a building area of low confidence) is not stated; a nominal assessment says so instead of a value.
import type { ScorecardResponse } from "./api";
import type { ScorecardVerdict, TFunc } from "./scorecardVerdict";

/** In the order the sentence names them: the first that applies is the blocker. */
export const BLOCKER_ORDER = [
  "nominal",
  "landmark_bldg",
  "landmark_dist",
  "historic",
  "pd_overlay",
  "flood",
  "lakefront",
  "natl_register",
] as const;
export type BlockerKey = (typeof BLOCKER_ORDER)[number];

/** Everything on this parcel that changes the build answer, most decisive first. */
export function blockersFor(data: ScorecardResponse, verdict: ScorecardVerdict): BlockerKey[] {
  const present = new Set<string>(verdict.signals.frictionFlags);
  if (data.context?.property?.nominal_assessment) present.add("nominal");
  return BLOCKER_ORDER.filter((k) => present.has(k));
}

function fmtFar(n: number): string {
  return n.toFixed(1);
}

/** The build half of the sentence: what the district allows here. */
export function buildClause(data: ScorecardResponse, verdict: ScorecardVerdict, t: TFunc): string {
  const s = verdict.signals;
  const zone = s.zoneClass;
  if (!zone) return t("scorecard.answer.noZone");
  if (verdict.category === "entitlement_defined" || s.allowedFar == null) {
    return t("scorecard.answer.ownOrdinance", { zone });
  }
  const units = data.context?.unit_yield?.units ?? 0;
  const unitsPart = units > 0 ? t("scorecard.answer.units", { count: units }) : "";
  const trusted = s.existingFar != null && s.existingFar > 0 && !s.bldgAreaLowConfidence;
  if (s.capacityBand === "vacant_or_teardown") {
    return t("scorecard.answer.mostlyUnbuilt", { zone, far: fmtFar(s.allowedFar) }) + unitsPart;
  }
  if (trusted && s.capacityBand === "at_cap") {
    const pct = Math.round((s.existingFar! / s.allowedFar) * 100);
    return t("scorecard.answer.atCap", { zone, pct });
  }
  if (trusted && s.capacityRatio != null && s.capacityRatio > 1) {
    return t("scorecard.answer.headroom", { zone, x: s.capacityRatio.toFixed(1) }) + unitsPart;
  }
  return t("scorecard.answer.allowsFar", { zone, far: fmtFar(s.allowedFar) }) + unitsPart;
}

/** The whole sentence: "{build}; {blocker}." or "{build}." */
export function answerSentence(data: ScorecardResponse, verdict: ScorecardVerdict, t: TFunc): string {
  const build = buildClause(data, verdict, t);
  const [first] = blockersFor(data, verdict);
  return first ? `${build}; ${t(`scorecard.answer.blocker.${first}`)}.` : `${build}.`;
}
