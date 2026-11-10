// The Neighborhood tab's figures (brief "Property Profile", Neighborhood: "What's the area like?"; decision
// Item 102). Pure functions over the assembled Profile; the page decides nothing the backend already decided
// (withheld tract figures stay withheld). Race and ethnicity are left out by the owner's call: nothing here reads
// `race_distribution`. Comparisons are the tract against its community area, never the whole city (rule 6).
import type { TFunction } from "i18next";
import type { ConstructionProject, NextUiSchool, ScorecardResponse } from "../../lib/api";
import { confidenceStateFor, type ConfidenceKind } from "../../lib/confidence";
import type { LateBlockState } from "./moneyModel";

export type NbSource = "crime" | "area_311" | "schools" | "construction_within";

/** A block's state from its late part and its own source: a source past the deadline is "timedOut", a failed one
    "failed" (never "none"). */
export function sourceState(
  data: ScorecardResponse, part: LateBlockState, source: NbSource, timedOut: string[],
): LateBlockState {
  if (part === "loading" || part === "failed") return part;
  const names = source === "crime" ? ["crime", "crime_yoy"] : [source];
  if (source === "crime") {
    if (timedOut.includes("crime")) return "timedOut";
    if (!data.next_ui?.crime) return part === "timedOut" ? "timedOut" : "failed";
    return "ready";
  }
  if (names.some((n) => timedOut.includes(n))) return "timedOut";
  if (data.next_ui?.failed?.includes(source)) return "failed";
  if (data.next_ui?.[source] == null) return part === "timedOut" ? "timedOut" : "failed";
  return "ready";
}

// ── Getting around ───────────────────────────────────────────────────────────────────────────────────────

export interface Score { key: "walk" | "transit" | "bike"; score: number | null; description: string | null }

export function scores(data: ScorecardResponse): Score[] | null {
  const ws = data.context?.neighborhood?.walkscore;
  if (!ws) return null;
  return [
    { key: "walk", score: ws.walk_score, description: ws.walk_description },
    { key: "transit", score: ws.transit_score, description: ws.transit_description },
    { key: "bike", score: ws.bike_score, description: ws.bike_description },
  ];
}

/** The community area's own figures: the parts' copy (the Profile's neighborhood lookup skips them for a parcel),
    else the context's. */
export function areaDemographics(data: ScorecardResponse) {
  return data.next_ui?.area_demographics ?? data.context?.neighborhood?.demographics ?? null;
}

// ── Safety ───────────────────────────────────────────────────────────────────────────────────────────────

export interface CrimeModel {
  areaName: string | null;
  population: number | null;
  violent: number;
  property: number;
  /** Per 1,000 residents of the community area over the 90 days; null without a population. */
  violentPer1k: number | null;
  propertyPer1k: number | null;
  priorViolent: number | null;
  priorProperty: number | null;
  /** Change from the same 90 days a year earlier, in percent (rounded); null when there is no comparison or the
      prior count was 0. */
  violentChange: number | null;
  propertyChange: number | null;
  currentLabel: string | null;
  priorLabel: string | null;
}

const per1k = (n: number, pop: number | null) => (pop && pop > 0 ? Math.round((n / pop) * 10000) / 10 : null);
const change = (now: number, before: number | null) => (before == null || before === 0 ? null : Math.round(((now - before) / before) * 100));

export function crimeModel(data: ScorecardResponse): CrimeModel | null {
  const c = data.next_ui?.crime;
  if (!c) return null;
  const pop = areaDemographics(data)?.population ?? null;
  return {
    areaName: data.community_area_name ?? data.context?.neighborhood?.demographics?.community_area_name ?? null,
    population: pop,
    violent: c.current.violent,
    property: c.current.property,
    violentPer1k: per1k(c.current.violent, pop),
    propertyPer1k: per1k(c.current.property, pop),
    priorViolent: c.prior?.violent ?? null,
    priorProperty: c.prior?.property ?? null,
    violentChange: change(c.current.violent, c.prior?.violent ?? null),
    propertyChange: change(c.current.property, c.prior?.property ?? null),
    currentLabel: c.current_label ?? null,
    priorLabel: c.prior_label ?? null,
  };
}

// ── 311 ──────────────────────────────────────────────────────────────────────────────────────────────────

export function three11Model(data: ScorecardResponse) {
  const a = data.next_ui?.area_311;
  if (!a) return null;
  return { days: a.days, total: a.total, top: a.top };
}

// ── Construction nearby ──────────────────────────────────────────────────────────────────────────────────

export interface ConstructionModel {
  projects: ConstructionProject[];
  newCount: number;
  renovationCount: number;
  /** Homes the permits add, net (the City's residential unit change). */
  unitsAdded: number;
  radiusMi: number;
  months: number;
  costFloor: number;
  capped: boolean;
}

export function constructionModel(data: ScorecardResponse): ConstructionModel | null {
  const c = data.next_ui?.construction_within;
  if (!c) return null;
  return {
    projects: c.projects,
    newCount: c.projects.filter((p) => p.kind === "new").length,
    renovationCount: c.projects.filter((p) => p.kind === "renovation").length,
    unitsAdded: c.projects.reduce((s, p) => s + (p.units_added ?? 0), 0),
    radiusMi: c.radius_mi,
    months: c.months,
    costFloor: c.renovation_cost_floor,
    capped: c.capped,
  };
}

/** A permit's work description, readable: the City writes it in capitals with code boilerplate in front. */
export function permitWords(d: string | null, max = 140): string | null {
  if (!d) return null;
  // The review track and code edition the City writes first ("SELF CERTIFICATION 2019 CBRC --", "Self -cert 2019 cbc:",
  // "SC 2019 CBRC.", "STANDARD PLAN REVIEW", "DIRECT DEVELOPER SERVICES 2019 CBC."): not what is being built.
  const s = d.replace(/\s+/g, " ")
    .replace(/^(self\s*-?\s*cert(ification)?|sc|spr|standard plan review|direct developer services|easy permit)\b\s*[-.:]*\s*/i, "")
    // the code edition: "2019 CBRC" (sometimes run into the next word: "2019 cbrcinterior") or a bare "CBC"
    .replace(/^(\d{4}\s*(cbrc|cbc)|(cbrc|cbc)\b)\s*[-.:]*\s*/i, "")
    .replace(/^[-.:\s]+/, "")
    .trim();
  const lower = s.toLowerCase();
  const sentence = lower.charAt(0).toUpperCase() + lower.slice(1);
  return sentence.length > max ? `${sentence.slice(0, max - 1).trimEnd()}…` : sentence;
}

// ── Who lives here ───────────────────────────────────────────────────────────────────────────────────────

export type TractFact = "median_household_income" | "owner_occupied_pct" | "bachelors_or_higher_pct" | "poverty_rate" | "median_age";

export interface PeopleFact {
  key: TractFact;
  value: number | null;
  /** The backend's call on the figure (Withheld = not shown; Low = shown quieter). */
  state: { kind: ConfidenceKind; low: boolean } | null;
  withheld: boolean;
}

export interface PeopleModel {
  tractName: string | null;
  period: string | null;
  income: { tract: number | null; area: number | null; tractWithheld: boolean; areaLow: boolean };
  facts: PeopleFact[];
}

export function peopleModel(data: ScorecardResponse): PeopleModel | null {
  const nb = data.context?.neighborhood;
  const ct = nb?.census_tract;
  if (!ct) return null;
  const prov = data.provenance ?? {};
  const fact = (k: TractFact): PeopleFact => {
    const entry = prov[`area.tract.${k}`];
    const st = entry ? confidenceStateFor(entry) : null;
    const withheld = st?.kind === "withheld";
    return { key: k, value: withheld ? null : (ct[k] ?? null), state: st, withheld };
  };
  const inc = fact("median_household_income");
  const areaEntry = prov["area.community_area.median_household_income"];
  const areaState = areaEntry ? confidenceStateFor(areaEntry) : null;
  const areaIncome = areaDemographics(data)?.median_household_income ?? null;
  return {
    tractName: ct.tract_name,
    period: ct.acs_period ?? null,
    income: {
      tract: inc.value,
      area: areaState?.kind === "withheld" ? null : areaIncome,
      tractWithheld: inc.withheld,
      // Estimated from five income brackets with no margin (the City's extract), so always read as low confidence.
      areaLow: areaIncome != null,
    },
    // A figure the survey doesn't give is left out; a withheld one stays, saying so.
    facts: (["owner_occupied_pct", "bachelors_or_higher_pct", "poverty_rate", "median_age"] as TractFact[]).map(fact)
      .filter((f) => f.withheld || f.value != null),
  };
}

// ── Schools ──────────────────────────────────────────────────────────────────────────────────────────────

export function schoolsModel(data: ScorecardResponse): { schools: NextUiSchool[]; noneAssigned: Array<"elementary" | "high">; reportYear: number | null; boundaryYear: string } | null {
  const s = data.next_ui?.schools;
  if (!s) return null;
  return {
    schools: [s.elementary, s.high].filter((x): x is NextUiSchool => !!x),
    noneAssigned: ([["elementary", s.elementary], ["high", s.high]] as const).filter(([, v]) => !v).map(([k]) => k),
    reportYear: s.report_year,
    boundaryYear: s.boundary_year,
  };
}

/** ISBE's designation as a pill tone: the state's own words, colored only by what they say. */
export function designationTone(d: string | undefined): "green" | "blue" | "yellow" | "gray" {
  if (d === "Exemplary" || d === "Commendable") return d === "Exemplary" ? "green" : "blue";
  if (d === "Targeted" || d === "Comprehensive" || d === "Intensive") return "yellow";
  return "gray";
}

// ── The sentence ─────────────────────────────────────────────────────────────────────────────────────────

export function neighborhoodSentence(data: ScorecardResponse, t: TFunction, ready: { building: boolean; crime: boolean }): string {
  const parts: string[] = [];
  const sc = scores(data);
  const walk = sc?.find((s) => s.key === "walk");
  if (walk?.score != null) parts.push(t("profile.nb.sentence.walk", { score: walk.score, desc: walk.description ?? "" }).replace(/ \(\)$/, ""));
  const c = ready.building ? constructionModel(data) : null;
  if (c) parts.push(c.projects.length ? t("profile.nb.sentence.building", { count: c.projects.length }) : t("profile.nb.sentence.noBuilding"));
  const cr = ready.crime ? crimeModel(data) : null;
  if (cr?.violentChange != null) {
    parts.push(cr.violentChange === 0
      ? t("profile.nb.sentence.violentFlat")
      : t(cr.violentChange < 0 ? "profile.nb.sentence.violentDown" : "profile.nb.sentence.violentUp", { pct: Math.abs(cr.violentChange) }));
  }
  if (!parts.length) return t("profile.nb.sentence.none");
  const s = parts.join("; ");
  return `${s.charAt(0).toUpperCase()}${s.slice(1)}.`;
}
