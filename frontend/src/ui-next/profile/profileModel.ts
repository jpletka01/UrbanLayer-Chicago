// The new Profile's figures (decision Item 76), derived from today's `/api/scorecard` response with no backend
// change and nothing recomputed that the backend already decided: the verdict's signals (computeVerdict), the
// unit yield, the provenance states (confidenceStateFor / displayState). Pure functions with an injected `t`,
// so the pages render from typed fixtures in tests.
import type { ScorecardResponse } from "../../lib/api";
import type { ScorecardVerdict, TFunc } from "../../lib/scorecardVerdict";
import { confidenceStateFor, type ConfidenceKind } from "../../lib/confidence";
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

/** The number locale for a UI language: Spanish is Mexico's (es-MX), never Spain's `es` (Item 82). */
export const numLocale = (lng: string) => (lng.startsWith("es") ? "es-MX" : "en-US");
export const fmtInt = (n: number, lng: string) => Math.round(n).toLocaleString(numLocale(lng));

/** Parse the table's height ("45 ft", "65'") to feet; null when it isn't a plain number of feet. */
export function heightFeet(text: string | null | undefined): number | null {
  if (!text) return null;
  const m = /^\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|'|’)?\s*$/i.exec(text);
  return m ? parseFloat(m[1]) : null;
}

/** The illustrative zoning mass drawn in 3D on Build (M6, decision Items 75, 106): the district's floor-area ratio
    times the lot area, spread evenly over the whole lot at FLOOR_FT a floor, cut at the district's height limit
    (a range's lower end). Never "the largest allowed": setbacks, coverage, density, parking, bonuses and overlays
    are not applied. Null without a FAR or a lot area (a planned development sets its own size), or when the lot's
    identity or outline is approximate. */
export const FLOOR_FT = 12;
export interface ZoningMass {
  /** The district (the mass takes its zoning color). */
  zoneClass: string | null;
  far: number;
  lotSqft: number;
  floorAreaSqft: number;
  heightFt: number;
  /** The height limit applied, in feet; null when the district states none we can read. */
  capFt: number | null;
  /** The limit is the lower end of a range ("45–50 ft, varies by frontage"). */
  capFromRange: boolean;
  /** The floor area doesn't fit under the height limit when spread over the lot. */
  limitedByHeight: boolean;
}

/** A height range's lower end in feet ("45–50 ft (varies …)" → 45); null when there's no range. */
export function heightRangeLow(text: string | null | undefined): number | null {
  const m = /(\d+(?:\.\d+)?)\s*(?:ft\s*)?[–-]\s*\d+(?:\.\d+)?\s*(?:ft|feet)/i.exec(text ?? "");
  return m ? parseFloat(m[1]) : null;
}

export function zoningMass(data: ScorecardResponse, verdict: ScorecardVerdict, approximate: boolean): ZoningMass | null {
  const far = verdict.signals.allowedFar;
  const lot = data.context?.property?.land_sqft ?? null;
  if (approximate || far == null || !(far > 0) || lot == null || !(lot > 0)) return null;
  const text = data.zone_definition?.max_height ?? null;
  const exact = heightFeet(text);
  const low = exact == null ? heightRangeLow(text) : null;
  const capFt = exact ?? low;
  const spread = far * FLOOR_FT;
  const limitedByHeight = capFt != null && spread > capFt;
  return {
    zoneClass: data.zone_definition?.zone_class ?? null,
    far, lotSqft: lot, floorAreaSqft: far * lot,
    heightFt: limitedByHeight ? capFt! : spread,
    capFt, capFromRange: low != null, limitedByHeight,
  };
}

/** `buildingPending`: the City's building records (the Profile's late `building` part, Item 89) haven't answered,
    so a built figure that isn't on record yet reads "checking", not "not on record". */
export function allowedVsBuilt(
  data: ScorecardResponse, verdict: ScorecardVerdict, t: TFunc, lng = "en", { buildingPending = false } = {},
): LimitRow[] {
  const notYet = () => (buildingPending ? t("profile.parts.unitsBuiltChecking") : t("profile.build.notOnRecord"));
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
      builtText: built != null ? t("profile.build.sqft", { value: fmtInt(built, lng) }) : notYet(),
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
      builtText: built != null ? t("profile.build.units", { count: built }) : notYet(),
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
      builtText: stories != null ? t("profile.build.stories", { count: stories }) : notYet(),
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

// ── The Overview's tiles: one per tab (brief "Overview", Approved; decision Item 77) ─────────────────────
// Build: units allowed vs built · Money: property tax · Neighborhood: walk score · History: last market sale.
// The zoning district lives in the answer sentence and the map band, not in a tile.

export type TabId = "build" | "money" | "neighborhood" | "history";
/** The tabs built so far, which a tile can open. */
export type TileTab = "build" | "money" | "neighborhood" | "history";

export interface Tile {
  key: "units" | "tax" | "walk" | "lastSale";
  /** The tab this tile summarizes (its label names it). */
  tabOf: TabId;
  label: string;
  figure: string;
  unit?: string;
  note?: string;
  /** At most one warning per tile (brief: "at most one warning"). */
  warning?: string;
  state: FigureState;
  /** The tab that proves it, when that tab is built; null opens nothing yet. */
  tab: TileTab | null;
  /** The small visual: a share of the whole (built of allowed units). */
  share?: number | null;
  /** A 0–100 score drawn as a ring on the tile's right (the walk score, Item 102). */
  score?: number | null;
  /** The first screen (Item 82): no figure yet; the note says what the tile waits for. */
  checking?: boolean;
}

const money = (n: number, lng: string) =>
  new Intl.NumberFormat(lng.startsWith("es") ? "es-MX" : "en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

/** A market sale, by the County's own sale filters as the server reads them (`arms_length`, decision Item 89; it
    retired Item 77's client-side deed test). Unknown (null or absent) is not counted as a market sale. */
// ── What the lot is used for today (Item 112) ─────────────────────────────────────────────────────────

export interface LotInUse { kind: "parking" | "empty"; words: string }

/** The Overview's line from Discovery's row: surface parking or empty land, in the list card's own words; else null. */
export function lotInUse(row: { surface_parking?: boolean | null; empty_land?: boolean | null; land_kind?: string | null; structure?: string | null } | null, t: TFunc): LotInUse | null {
  if (!row?.empty_land && !row?.surface_parking) return null;
  const base = row.surface_parking ? t("discovery.card.now.surfaceParking")
    : t(`discovery.card.now.emptyKind.${row.land_kind ?? "vacant"}`, { defaultValue: t("discovery.card.now.empty") });
  const words = row.structure === "accessory" ? `${base}, ${t("discovery.card.now.shed")}` : base;
  return { kind: row.surface_parking ? "parking" : "empty", words };
}

export function isMarketSale(s: { price: number | null; arms_length?: boolean | null }): boolean {
  return s.price != null && s.arms_length === true;
}

export function overviewTiles(
  data: ScorecardResponse, verdict: ScorecardVerdict, t: TFunc, lng = "en", { buildingPending = false } = {},
): Tile[] {
  const ctx = data.context;
  const prop = ctx?.property;
  const prov = data.provenance ?? {};
  const tiles: Tile[] = [];

  // Build: units allowed vs built
  const uy = ctx?.unit_yield;
  const label = (k: Tile["key"]) => t(`profile.tiles.${k}`);
  if (uy && uy.units > 0) {
    const built = prop?.units ?? null;
    tiles.push({
      key: "units", tabOf: "build", label: label("units"), figure: `≤ ${uy.units}`,
      note: built != null
        ? t("profile.tiles.unitsBuilt", { count: built })
        : buildingPending ? t("profile.parts.unitsBuiltChecking") : t("profile.tiles.unitsBuiltUnknown"),
      state: { kind: "estimate", low: false }, tab: "build",
      share: built != null ? Math.min(built / uy.units, 1) : null,
    });
  } else if (verdict.category === "entitlement_defined") {
    tiles.push({ key: "units", tabOf: "build", label: label("units"), figure: "—", note: t("profile.tiles.ownOrdinance"), state: null, tab: "build" });
  } else {
    tiles.push({ key: "units", tabOf: "build", label: label("units"), figure: "—", note: t("profile.tiles.unitsNoRule"), state: { kind: "na", low: false }, tab: "build" });
  }

  // Money: property tax
  if (prop?.nominal_assessment) {
    tiles.push({ key: "tax", tabOf: "money", label: label("tax"), figure: "—", note: t("profile.tiles.nominal"), state: { kind: "na", low: false }, tab: "money" });
  } else if (prop?.tax_exempt) {
    tiles.push({ key: "tax", tabOf: "money", label: label("tax"), figure: t("profile.tiles.exempt"), state: null, tab: "money" });
  } else if (prop?.estimated_annual_tax != null) {
    const year = prov["property.tax_estimate"]?.period ?? (prop.tax_year != null ? String(prop.tax_year) : null);
    const rate = prop.effective_tax_rate;
    tiles.push({
      key: "tax", tabOf: "money", label: label("tax"), figure: money(prop.estimated_annual_tax, lng), unit: t("profile.tiles.perYear"),
      note: [year ? t("profile.tiles.taxYear", { year }) : null, rate != null ? t("profile.tiles.taxRate", { rate: (rate * 100).toFixed(2) }) : null].filter(Boolean).join(" · ") || undefined,
      state: confidenceStateFor(prov["property.tax_estimate"]), tab: "money",
    });
  } else {
    tiles.push({ key: "tax", tabOf: "money", label: label("tax"), figure: "—", note: t("profile.tiles.notOnRecord"), state: { kind: "not_checked", low: false }, tab: "money" });
  }

  // Neighborhood: walk score (a private company's index, named as such)
  const ws = ctx?.neighborhood?.walkscore;
  if (ws?.walk_score != null) {
    tiles.push({
      key: "walk", tabOf: "neighborhood", label: label("walk"), figure: String(ws.walk_score), unit: t("profile.tiles.of100"),
      note: [ws.walk_description, t("profile.tiles.walkSource")].filter(Boolean).join(" · "),
      state: null, tab: "neighborhood", share: null, score: ws.walk_score,
    });
  } else {
    tiles.push({ key: "walk", tabOf: "neighborhood", label: label("walk"), figure: "—", note: t("profile.tiles.walkUnchecked"), state: { kind: "not_checked", low: false }, tab: "neighborhood" });
  }

  // History: last market sale. A $1 transfer, a quit claim or an unknown deed is never shown as the sale price.
  const sales = [...(prop?.sales_history ?? [])].filter((s) => s.date).sort((a, b) => (b.date! < a.date! ? -1 : 1));
  const market = sales.find(isMarketSale);
  const newerTransfer = market ? sales.find((s) => s.date! > market.date! && !isMarketSale(s)) : null;
  const year = (d: string) => d.slice(0, 4);
  if (!prop) {
    tiles.push({ key: "lastSale", tabOf: "history", label: label("lastSale"), figure: "—", note: t("profile.tiles.notOnRecord"), state: { kind: "not_checked", low: false }, tab: "history" });
  } else if (market) {
    tiles.push({
      key: "lastSale", tabOf: "history", label: label("lastSale"), figure: money(market.price!, lng),
      note: t("profile.tiles.soldIn", { year: year(market.date!) }),
      warning: newerTransfer ? t("profile.tiles.laterTransfer", { year: year(newerTransfer.date!) }) : undefined,
      state: confidenceStateFor(prov["property.sales"]), tab: "history",
    });
  } else {
    tiles.push({
      key: "lastSale", tabOf: "history", label: label("lastSale"), figure: "—",
      note: sales.length > 0 ? t("profile.tiles.onlyTransfers", { count: sales.length }) : t("profile.tiles.noSaleOnRecord"),
      state: { kind: "none_found", low: false }, tab: "history",
    });
  }
  return tiles;
}
