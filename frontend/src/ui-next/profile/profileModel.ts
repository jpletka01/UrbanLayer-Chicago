// The new Profile's figures (decision Item 76), derived from today's `/api/scorecard` response with no backend
// change and nothing recomputed that the backend already decided: the verdict's signals (computeVerdict), the
// unit yield, the provenance states (confidenceStateFor / displayState). Pure functions with an injected `t`,
// so the pages render from typed fixtures in tests.
import type { ScorecardResponse } from "../../lib/api";
import type { ScorecardVerdict, TFunc } from "../../lib/scorecardVerdict";
import { confidenceStateFor, displayState, type ConfidenceKind } from "../../lib/confidence";
import type { UpcomingZoningFiling } from "../../lib/types";

export type FigureState = { kind: ConfidenceKind; low: boolean } | null;

// ── Allowed vs built ──────────────────────────────────────────────────────────────────────────────────

export interface LimitRow {
  key: "floorArea" | "units" | "height";
  /** What the district allows, as a number when the bars can compare it. */
  allowed: number | null;
  allowedText: string;
  built: number | null;
  builtText: string;
  /** built ÷ allowed, 0–1+, when both are numbers. */
  share: number | null;
  /** The limit closest to its cap: it decides how much more can be built. */
  deciding: boolean;
  state: FigureState;
}

const fmtInt = (n: number, lng: string) => Math.round(n).toLocaleString(lng);

/** Parse the table's height ("45 ft", "65'") to feet; null when it isn't a plain number of feet. */
export function heightFeet(text: string | null | undefined): number | null {
  if (!text) return null;
  const m = /^\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|'|’)?\s*$/i.exec(text);
  return m ? parseFloat(m[1]) : null;
}

export function allowedVsBuilt(data: ScorecardResponse, verdict: ScorecardVerdict, t: TFunc, lng = "en"): LimitRow[] {
  const ctx = data.context;
  const prop = ctx?.property;
  const sig = verdict.signals;
  const prov = data.provenance ?? {};
  const rows: LimitRow[] = [];
  const land = prop?.land_sqft ?? null;

  if (sig.allowedFar != null && land && land > 0) {
    const allowed = sig.allowedFar * land;
    const built = prop?.bldg_sqft ?? null;
    // A building area the verdict doesn't trust is shown as an estimate, never compared as fact.
    const builtState = built != null ? confidenceStateFor(prov["property.far_used"]) : null;
    rows.push({
      key: "floorArea",
      allowed,
      allowedText: t("profile.build.sqft", { value: fmtInt(allowed, lng) }),
      built,
      builtText: built != null ? t("profile.build.sqft", { value: fmtInt(built, lng) }) : t("profile.build.notOnRecord"),
      share: built != null && !sig.bldgAreaLowConfidence ? built / allowed : null,
      deciding: false,
      state: sig.bldgAreaLowConfidence && built != null ? { kind: "estimate", low: true } : builtState,
    });
  }

  const uy = ctx?.unit_yield;
  if (uy && uy.units > 0) {
    const built = prop?.units ?? null;
    rows.push({
      key: "units",
      allowed: uy.units,
      allowedText: t("profile.build.units", { count: uy.units }),
      built,
      builtText: built != null ? t("profile.build.units", { count: built }) : t("profile.build.notOnRecord"),
      share: built != null ? built / uy.units : null,
      deciding: false,
      state: { kind: "estimate", low: false },
    });
  }

  const hText = data.zone_definition?.max_height ?? null;
  if (hText) {
    const allowed = heightFeet(hText);
    const stories = prop?.stories ?? null;
    rows.push({
      key: "height",
      allowed,
      allowedText: allowed != null ? t("profile.build.feet", { value: allowed }) : hText,
      // The records give stories, not feet: shown as stories and never compared against feet.
      built: null,
      builtText: stories != null ? t("profile.build.stories", { count: stories }) : t("profile.build.notOnRecord"),
      share: null,
      deciding: false,
      state: null,
    });
  }

  // The deciding limit: of the limits we can compare, the one most used up.
  let best: LimitRow | null = null;
  for (const r of rows) if (r.share != null && (best == null || r.share > best.share!)) best = r;
  if (best) best.deciding = true;
  return rows;
}

// ── Pending rezonings ─────────────────────────────────────────────────────────────────────────────────

export const STAGES = ["introduced", "committee", "council", "inEffect"] as const;
export type Stage = (typeof STAGES)[number];

/** Where a Clerk filing stands, from the Clerk's numbered workflow state (backend/retrieval/clerk.py
    KNOWN_PENDING_STATUSES: 2-Submitted to Clerk, 3-Council Introduction, 4-In Committee, 5-Council Consideration;
    90-Final with a passed sub-status). Never from loose words: "Council Introduction" is an introduction, not a
    vote. An unknown state returns null and the page shows the Clerk's own words instead of a tracker. */
export function stageOf(f: Pick<UpcomingZoningFiling, "status" | "sub_status">): Stage | null {
  const code = /^(\d+)\s*-/.exec(f.status ?? "")?.[1];
  if (code === "2" || code === "3") return "introduced";
  if (code === "4") return "committee";
  if (code === "5") return "council";
  if (code === "90" && /^(Passed|Passed as Substitute|Signed|Adopted|Approved|Approved as Substitute)$/.test((f.sub_status ?? "").trim())) return "inEffect";
  return null;
}

export interface PendingModel {
  state: "ready" | "stale" | "unavailable" | "none";
  /** The parcel's own filings first, then the nearest (at most three in all). */
  filings: Array<UpcomingZoningFiling & { stage: Stage | null; onThisLot: boolean }>;
  nearbyTotal: number;
  radiusMi: number | null;
  checkedAt: string | null;
}

export function pendingRezonings(data: ScorecardResponse): PendingModel {
  const up = data.context?.upcoming_zoning;
  if (!up) return { state: "unavailable", filings: [], nearbyTotal: 0, radiusMi: null, checkedAt: null };
  if (up.status === "unavailable") return { state: "unavailable", filings: [], nearbyTotal: 0, radiusMi: up.radius_mi, checkedAt: up.checked_at ?? null };
  const own = up.subject_filings.map((f) => ({ ...f, stage: stageOf(f), onThisLot: true }));
  const near = [...up.nearby_filings]
    .sort((a, b) => (a.distance_mi ?? 99) - (b.distance_mi ?? 99))
    .map((f) => ({ ...f, stage: stageOf(f), onThisLot: false }));
  const filings = [...own, ...near].slice(0, 3);
  const state = filings.length === 0 ? "none" : up.status === "stale" ? "stale" : "ready";
  return { state: up.status === "stale" && filings.length ? "stale" : state, filings, nearbyTotal: near.length, radiusMi: up.radius_mi, checkedAt: up.checked_at ?? null };
}

// ── Rules as yes/no chips ─────────────────────────────────────────────────────────────────────────────

export type RuleAnswer = "yes" | "no" | "notChecked";
export interface RuleChip {
  key: "landmark" | "historic" | "pd" | "flood" | "lakefront" | "tod" | "adu" | "aro" | "tif";
  answer: RuleAnswer;
  /** A "yes" that changes the build answer (verdict friction). */
  blocks: boolean;
}

export function ruleChips(data: ScorecardResponse, verdict: ScorecardVerdict): RuleChip[] {
  const ctx = data.context;
  const reg = ctx?.regulatory ?? null;
  const inc = ctx?.incentives ?? null;
  const unchecked = (reg?.unchecked_overlays ?? []).map((s) => s.toLowerCase());
  const wasChecked = (core: string) => reg != null && !unchecked.some((u) => u.includes(core));
  const ans = (core: string, yes: boolean | null | undefined): RuleAnswer =>
    !wasChecked(core) ? "notChecked" : yes ? "yes" : "no";
  const friction = new Set(verdict.signals.frictionFlags);

  const chips: RuleChip[] = [
    { key: "landmark", answer: ans("landmark", reg?.in_landmark_district || reg?.is_landmark_building), blocks: friction.has("landmark_dist") || friction.has("landmark_bldg") },
    { key: "historic", answer: ans("historic", reg?.in_historic_district), blocks: friction.has("historic") },
    { key: "pd", answer: ans("planned", reg?.in_planned_development), blocks: friction.has("pd_overlay") },
    {
      key: "flood",
      answer: reg == null || reg.flood_unchecked || (data.failed_sources ?? []).some((f) => f.key === "flood")
        ? "notChecked"
        : reg.flood_zone != null && reg.flood_zone !== "X" ? "yes" : "no",
      blocks: friction.has("flood"),
    },
    { key: "lakefront", answer: ans("lakefront", reg?.in_lakefront_protection), blocks: friction.has("lakefront") },
    { key: "tod", answer: ans("tod", reg?.in_tod_area), blocks: false },
    { key: "adu", answer: ctx?.adu ? (ctx.adu.status === "not_allowed" ? "no" : "yes") : ans("adu", reg?.in_adu_area), blocks: false },
    { key: "aro", answer: ans("aro", reg?.in_aro_zone), blocks: false },
    {
      key: "tif",
      answer: inc == null || (inc.unchecked ?? []).includes("tif") ? "notChecked" : inc.in_tif_district ? "yes" : "no",
      blocks: false,
    },
  ];
  // Things that change the answer first, then the other yeses, then no, then not checked.
  const rank = (c: RuleChip) => (c.blocks && c.answer === "yes" ? 0 : c.answer === "yes" ? 1 : c.answer === "no" ? 2 : 3);
  return chips.sort((a, b) => rank(a) - rank(b));
}

// ── The Overview's tiles (provisional set: units allowed, zoning, property tax, price per sq ft) ──────────

export interface Tile {
  key: "units" | "zoning" | "tax" | "pricePerSqft";
  label: string;
  figure: string;
  unit?: string;
  note?: string;
  /** At most one warning per tile (brief: "at most one warning"). */
  warning?: string;
  state: FigureState;
  /** The tab that proves it; null while that tab isn't built. */
  tab: "build" | null;
  /** The small visual: the built share of the allowed figure, when there is one. */
  share?: number | null;
}

const money = (n: number, lng: string) =>
  new Intl.NumberFormat(lng.startsWith("es") ? "es-MX" : "en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

export function overviewTiles(data: ScorecardResponse, verdict: ScorecardVerdict, t: TFunc, lng = "en"): Tile[] {
  const ctx = data.context;
  const prop = ctx?.property;
  const prov = data.provenance ?? {};
  const tiles: Tile[] = [];

  // Units allowed
  const uy = ctx?.unit_yield;
  if (uy && uy.units > 0) {
    const built = prop?.units ?? null;
    tiles.push({
      key: "units", label: t("profile.tiles.units"), figure: `≤ ${uy.units}`,
      note: built != null ? t("profile.tiles.unitsBuilt", { count: built }) : t("profile.tiles.unitsByLotArea"),
      state: { kind: "estimate", low: false }, tab: "build",
      share: built != null ? Math.min(built / uy.units, 1) : null,
    });
  } else if (verdict.category === "entitlement_defined") {
    tiles.push({ key: "units", label: t("profile.tiles.units"), figure: "—", note: t("profile.tiles.ownOrdinance"), state: null, tab: "build" });
  } else {
    tiles.push({ key: "units", label: t("profile.tiles.units"), figure: "—", note: t("profile.tiles.unitsNoRule"), state: { kind: "na", low: false }, tab: "build" });
  }

  // Zoning
  const zone = (data.zone_definition?.zone_class as string | undefined) ?? verdict.signals.zoneClass;
  const pending = pendingRezonings(data);
  const ownPending = pending.filings.filter((f) => f.onThisLot).length;
  tiles.push({
    key: "zoning", label: t("profile.tiles.zoning"), figure: zone ?? "—",
    note: !zone ? t("profile.tiles.zoningUnchecked")
      : ownPending > 0 ? undefined
      : pending.state === "unavailable" ? t("profile.tiles.pendingUnchecked")
      : t("profile.tiles.noPendingHere"),
    warning: ownPending > 0 ? t("profile.tiles.pendingHere", { count: ownPending }) : undefined,
    state: zone ? null : { kind: "not_checked", low: false },
    tab: "build",
  });

  // Property tax
  if (prop?.nominal_assessment) {
    tiles.push({ key: "tax", label: t("profile.tiles.tax"), figure: "—", note: t("profile.tiles.nominal"), state: { kind: "na", low: false }, tab: null });
  } else if (prop?.tax_exempt) {
    tiles.push({ key: "tax", label: t("profile.tiles.tax"), figure: t("profile.tiles.exempt"), state: null, tab: null });
  } else if (prop?.estimated_annual_tax != null) {
    const year = prov["property.tax_estimate"]?.period ?? (prop.tax_year != null ? String(prop.tax_year) : null);
    const rate = prop.effective_tax_rate;
    tiles.push({
      key: "tax", label: t("profile.tiles.tax"), figure: money(prop.estimated_annual_tax, lng), unit: t("profile.tiles.perYear"),
      note: [year ? t("profile.tiles.taxYear", { year }) : null, rate != null ? t("profile.tiles.taxRate", { rate: (rate * 100).toFixed(2) }) : null].filter(Boolean).join(" · ") || undefined,
      state: confidenceStateFor(prov["property.tax_estimate"]), tab: null,
    });
  } else {
    tiles.push({ key: "tax", label: t("profile.tiles.tax"), figure: "—", note: t("profile.tiles.notOnRecord"), state: { kind: "not_checked", low: false }, tab: null });
  }

  // Price per sq ft: nearby market sales per building sq ft (the backend decides whether it is shown).
  const comps = data.comparables;
  const compsState = displayState(prov["property.comps.median_price"]);
  const psf = comps?.median_price_per_bldg_sqft ?? null;
  if (psf != null && compsState !== "withheld") {
    tiles.push({
      key: "pricePerSqft", label: t("profile.tiles.pricePerSqft"), figure: money(psf, lng), unit: t("profile.tiles.perSqft"),
      note: t("profile.tiles.nearbySales", { count: comps?.sales_volume ?? 0 }),
      warning: (comps?.sales_volume ?? 0) < 3 ? t("profile.tiles.fewSales") : undefined,
      state: confidenceStateFor(prov["property.comps.median_price"]), tab: null,
    });
  } else {
    tiles.push({
      key: "pricePerSqft", label: t("profile.tiles.pricePerSqft"), figure: "—",
      note: compsState === "withheld" ? t("profile.tiles.tooFewSales") : t("profile.tiles.noSales"),
      state: { kind: compsState === "withheld" ? "withheld" : "none_found", low: false }, tab: null,
    });
  }
  return tiles;
}
