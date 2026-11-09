// The Money tab's figures (brief "Property Profile", Money: "What would it cost or earn?"; decision Item 99).
// Pure functions over the Profile so far (`/api/profile/*`, Item 89), nothing recomputed that the backend
// decided: the tax bill, the class's assessment level and implied market value, each figure's confidence state
// (from provenance), and the comparables' search. Rules of our own are kept few and written down here:
//  - the Assessor's value is flagged only against this lot's own recent market sale (Item 99);
//  - rent is read for this building's unit size only when the records give bedrooms and units (Item 99).
import type { Provenance, ScorecardResponse } from "../../lib/api";
import type { ComparableSale } from "../../lib/types";
import { confidenceStateFor, displayState } from "../../lib/confidence";
import type { TFunc } from "../../lib/scorecardVerdict";
import type { FigureState } from "./profileModel";
import { isMarketSale } from "./profileModel";

/** Where a late part stands, for the block that reads it (Item 89's skeleton rule). */
export type LateBlockState = "loading" | "ready" | "timedOut" | "failed";

// ── Taxes ──────────────────────────────────────────────────────────────────────────────────────────────

export interface TaxModel {
  kind: "bill" | "exempt" | "nominal" | "none";
  tax: number | null;
  /** The bill year (PTAXSIM lags the calendar one to two years). */
  year: string | null;
  /** Tax ÷ implied market value, as a fraction (server-side, class-aware). */
  rate: number | null;
  /** A typical effective rate for this class (the City's common composite rate × the class's level), a fraction. */
  typicalRate: number | null;
  /** The Assessor's value: assessed ÷ the class's assessment level. */
  marketValue: number | null;
  state: FigureState;
  exemptions: string[];
}

function provValue(entry: Provenance | undefined): number | null {
  const v = (entry as (Provenance & { value?: unknown }) | undefined)?.value;
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function taxModel(data: ScorecardResponse): TaxModel {
  const prop = data.context?.property ?? null;
  const prov = data.provenance ?? {};
  const typicalRate = provValue(prov["property.tax_class_norm"]);
  const base = { tax: null, year: null, rate: null, typicalRate, marketValue: null, state: null, exemptions: [] };
  if (!prop) return { kind: "none", ...base };
  if (prop.nominal_assessment) return { kind: "nominal", ...base };
  if (prop.tax_exempt) return { kind: "exempt", ...base };
  if (prop.estimated_annual_tax == null) return { kind: "none", ...base, marketValue: prop.implied_market_value ?? null };
  const year = prov["property.tax_estimate"]?.period ?? (prop.tax_year != null ? String(prop.tax_year) : null);
  return {
    kind: "bill",
    tax: prop.estimated_annual_tax,
    year,
    rate: prop.effective_tax_rate ?? null,
    typicalRate,
    marketValue: prop.implied_market_value ?? null,
    state: confidenceStateFor(prov["property.tax_estimate"]),
    exemptions: [...new Set((prop.tax_exemptions ?? []).map((e) => e.kind))],
  };
}

// ── The Assessor's value over time, and against this lot's own sale ────────────────────────────────────

export interface ValueYear { year: number; land: number; building: number; total: number }

/** The Assessor's value by year (assessed ÷ the class's level, so it reads in dollars of market value). Repeated
    years are the reassessment holding between cycles; each year is kept so the bars read as a timeline. */
export function valueHistory(data: ScorecardResponse): { years: ValueYear[]; basis: "market" | "assessed" } {
  const prop = data.context?.property;
  const level = prop?.assessment_level && prop.assessment_level > 0 ? prop.assessment_level : null;
  const byYear = new Map<number, ValueYear>();
  for (const r of prop?.assessment_history ?? []) {
    if (r.year == null || r.total == null || r.total <= 0) continue;
    const k = level ?? 1;
    byYear.set(r.year, { year: r.year, land: (r.land ?? 0) / k, building: (r.building ?? 0) / k, total: r.total / k });
  }
  return { years: [...byYear.values()].sort((a, b) => a.year - b.year), basis: level ? "market" : "assessed" };
}

/** The flag fires when the Assessor's value is below this share of the lot's own sale price. */
export const ASSESSOR_FLAG_RATIO = 0.6;
/** Only a sale this recent is compared (an old price says little about today's value). */
export const ASSESSOR_FLAG_YEARS = 5;

/** The Assessor's value far below this lot's own recent market sale (brief: "flagged when far below sales").
    Compared against the lot's own sale only, never the nearby median: those are other buildings of other sizes. */
export function assessorBelowSale(data: ScorecardResponse, now = new Date()): { pctBelow: number; saleYear: string; salePrice: number } | null {
  const prop = data.context?.property;
  const mv = prop?.implied_market_value;
  if (!prop || mv == null || mv <= 0 || prop.tax_exempt || prop.nominal_assessment) return null;
  const cutoff = `${now.getFullYear() - ASSESSOR_FLAG_YEARS}`;
  const sale = [...(prop.sales_history ?? [])]
    .filter((s) => s.date && isMarketSale(s) && s.date.slice(0, 4) >= cutoff)
    .sort((a, b) => (b.date! < a.date! ? -1 : 1))[0];
  if (!sale || sale.price == null || mv >= ASSESSOR_FLAG_RATIO * sale.price) return null;
  return { pctBelow: Math.round((1 - mv / sale.price) * 100), saleYear: sale.date!.slice(0, 4), salePrice: sale.price };
}

// ── Chart scales ───────────────────────────────────────────────────────────────────────────────────────

/** A round top for a chart's scale (1, 2, 2.5 or 5 × a power of ten) at or above `max`. */
export function niceCeil(max: number): number {
  if (max <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(max));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= max) return m * p;
  return 10 * p;
}

// ── Comparable sales ───────────────────────────────────────────────────────────────────────────────────

export interface CompsModel {
  sales: Array<ComparableSale & { sale_price: number }>;
  median: number | null;
  /** The backend's state for the median: withheld shows "—" and its reason. */
  medianState: FigureState;
  medianWithheld: boolean;
  /** The "nearby" rule as chips: class, radius, window, count, widened. */
  rule: { classGroup: string | null; radiusMi: number | null; years: number | null; n: number; widened: boolean };
  perBuildable: number | null;
  perBuildableState: FigureState;
  perBuildableWithheld: boolean;
}

export function compsModel(data: ScorecardResponse): CompsModel | null {
  const c = data.comparables;
  if (!c) return null;
  const prov = data.provenance ?? {};
  const sales = (c.sales ?? [])
    .filter((s): s is ComparableSale & { sale_price: number } => s.sale_price != null && s.sale_price > 0)
    .sort((a, b) => ((b.sale_date ?? "") < (a.sale_date ?? "") ? -1 : 1));
  const medianEntry = prov["property.comps.median_price"];
  const bEntry = prov["property.comps.median_price_per_buildable_sqft"];
  const classGroup = /Class (\d)xx/.exec(c.comp_basis ?? "")?.[1] ?? null;
  return {
    sales,
    median: c.median_sale_price,
    medianState: confidenceStateFor(medianEntry),
    medianWithheld: displayState(medianEntry) === "withheld",
    rule: {
      classGroup,
      radiusMi: c.comp_radius_mi ?? null,
      years: c.comp_window_years ?? null,
      n: c.sales_volume ?? sales.length,
      widened: !!c.comp_widened,
    },
    perBuildable: c.median_price_per_buildable_sqft,
    perBuildableState: confidenceStateFor(bEntry),
    perBuildableWithheld: displayState(bEntry) === "withheld",
  };
}

// ── Rent for this building's unit size ─────────────────────────────────────────────────────────────────

export type BedroomKey = "1_bedroom" | "2_bedrooms" | "3_bedrooms";
export const BEDROOM_KEYS: BedroomKey[] = ["1_bedroom", "2_bedrooms", "3_bedrooms"];

export interface RentModel {
  bars: Array<{ key: BedroomKey; rent: number | null; scope: "tract" | "puma" | null; state: FigureState; withheld: boolean }>;
  /** The bedroom count of this building's typical unit (bedrooms ÷ units), when the records give both. */
  thisSize: BedroomKey | null;
  area: { rent: number; state: FigureState } | null;
  period: string | null;
  /** Rent was asked and nothing came back for the bedroom medians (the API couldn't read them). */
  unchecked: boolean;
}

export function unitSize(bedrooms: number | null | undefined, units: number | null | undefined): BedroomKey | null {
  if (!bedrooms || !units || units <= 0 || bedrooms < units) return null;
  const per = Math.round(bedrooms / units);
  return per <= 1 ? "1_bedroom" : per === 2 ? "2_bedrooms" : "3_bedrooms";
}

export function rentModel(data: ScorecardResponse): RentModel | null {
  const rent = data.context?.neighborhood?.rent;
  if (!rent) return null;
  const prov = data.provenance ?? {};
  const prop = data.context?.property;
  // Only residential buildings have unit sizes worth reading (class 2xx and 3xx apartments).
  const residential = /^[23]/.test(prop?.bldg_class ?? "");
  const bars = BEDROOM_KEYS.map((key) => {
    const cell = rent.bedrooms.find((b) => b.bedrooms === key);
    const entry = prov[`area.rent.${key}`];
    const withheld = displayState(entry) === "withheld";
    return { key, rent: withheld ? null : (cell?.estimate ?? null), scope: cell?.scope ?? null, state: confidenceStateFor(entry), withheld };
  });
  const caEntry = prov["area.rent.community_area"];
  const ca = rent.community_area?.median;
  return {
    bars,
    thisSize: residential ? unitSize(prop?.bedrooms, prop?.units) : null,
    area: ca != null && displayState(caEntry) !== "withheld" ? { rent: ca, state: confidenceStateFor(caEntry) } : null,
    period: rent.acs_period ?? null,
    unchecked: rent.bedrooms.length === 0 && (rent.unchecked ?? []).some((u) => u === "tract_rent" || u === "puma_rent"),
  };
}

// ── Incentives as yes / no / not-checked chips ─────────────────────────────────────────────────────────

export type IncentiveKey = "tif" | "oz" | "ez" | "qct" | "nmtc";
export type IncentiveAnswer = "yes" | "no" | "notChecked" | "checking";
export interface IncentiveChip { key: IncentiveKey; answer: IncentiveAnswer; name: string | null }

/** TIF, Opportunity Zone and Enterprise Zone come with the Overview (by point); QCT and NMTC are tract-keyed and
    come with the late `incentives` part (Item 89): "checking" while it waits, and "not checked" if it timed out or
    failed (its fields then hold defaults, and a default `false` must never read as "No"). */
export function incentiveChips(data: ScorecardResponse, incentives: LateBlockState | boolean): IncentiveChip[] {
  const state: LateBlockState = incentives === true ? "loading" : incentives === false ? "ready" : incentives;
  const inc = data.context?.incentives ?? null;
  const unchecked = new Set(inc?.unchecked ?? []);
  const late = new Set<IncentiveKey>(["qct", "nmtc"]);
  // A tract-keyed answer needs the tract: without it the false is a default, not a check (seen when a later part's
  // response lost the incentives part's data; Item 99).
  const noTract = !inc?.census_tract && !inc?.qct_tract && !inc?.nmtc_tract;
  const ans = (k: IncentiveKey, yes: boolean | undefined): IncentiveAnswer =>
    late.has(k) && state === "loading" ? "checking"
    : late.has(k) && (state === "timedOut" || state === "failed" || (noTract && !yes)) ? "notChecked"
    : inc == null || unchecked.has(k) || (k === "ez" && inc.enterprise_zone_unchecked) ? "notChecked" : yes ? "yes" : "no";
  const chips: IncentiveChip[] = [
    { key: "tif", answer: ans("tif", inc?.in_tif_district), name: inc?.tif_name ?? null },
    { key: "oz", answer: ans("oz", inc?.in_opportunity_zone), name: null },
    { key: "ez", answer: ans("ez", inc?.in_enterprise_zone), name: inc?.enterprise_zone_name ?? null },
    { key: "qct", answer: ans("qct", inc?.in_qct), name: null },
    { key: "nmtc", answer: ans("nmtc", inc?.in_nmtc), name: null },
  ];
  const rank = (c: IncentiveChip) => (c.answer === "yes" ? 0 : c.answer === "no" ? 1 : 2);
  return chips.sort((a, b) => rank(a) - rank(b));
}

// ── The tab's sentence ─────────────────────────────────────────────────────────────────────────────────

export const usd = (n: number, lng: string) =>
  new Intl.NumberFormat(lng.startsWith("es") ? "es-MX" : "en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

/** The tab's one sentence: what the lot costs to hold, then what nearby lots sold for when that holds up. */
export function moneySentence(data: ScorecardResponse, t: TFunc, lng: string): string {
  const tax = taxModel(data);
  const comps = compsModel(data);
  const first =
    tax.kind === "bill" && tax.tax != null
      ? tax.marketValue != null
        ? t("profile.money.sentence.billValue", { tax: usd(tax.tax, lng), value: usd(tax.marketValue, lng) })
        : t("profile.money.sentence.bill", { tax: usd(tax.tax, lng) })
      : t(`profile.money.sentence.${tax.kind}`);
  const second = comps && !comps.medianWithheld && comps.median != null && comps.sales.length > 0
    ? t("profile.money.sentence.comps", { count: comps.rule.n, median: usd(comps.median, lng) })
    : null;
  return second ? `${first}; ${second}.` : `${first}.`;
}
