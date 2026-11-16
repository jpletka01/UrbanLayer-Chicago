// Deep analysis (decision Item 124): the break-even arithmetic, pure.
//
// The tab's answer is the most a builder can pay for the lot (the residual land value) for one project, sold as units
// or rented out, from numbers that are all visible and editable: the lot's own figures (its last sale, the area's
// sale prices and rents, its tax rate) and stated assumptions (build cost, soft costs, the loan, a profit target).
// It is arithmetic against the builder's own targets, never a judgement of the deal (brief rule 11's one exception).
import type { DeepInputs } from "../../lib/api";

export type Mode = "sell" | "rent";
export type ProjectKind = "largest" | "three_flat" | "townhouses" | "own";

export interface Project {
  kind: ProjectKind;
  units: number;
  floors: number;
  floorAreaSqft: number;
}

export interface Numbers {
  /** What the lot costs (its last sale to start); null when there is none on record. */
  landPrice: number | null;
  salePriceUnit: number;
  rentUnitMonth: number;
  buildCostSqft: number;
  softCostPct: number;
  loanToCost: number;
  loanRate: number;
  buildMonths: number;
  sellingPct: number;
  profitOnCost: number;
  vacancyPct: number;
  opexPct: number;
  capRate: number;
  targetYield: number;
  /** Property tax as a share of market value once built (the parcel's effective rate). */
  taxRate: number;
}

/** Where each starting number came from, for the line under its slider. */
export type NumberSource =
  | { kind: "lot_sale"; date: string }
  | { kind: "area_sales"; group: string; year: string; n: number }
  | { kind: "new_construction"; perSqft: number; low: number; high: number; unitSqft: number; n: number;
      pooled: boolean; newSales: number; years: [string, string]; premium: number; premiumN: number }
  | { kind: "census_rent"; bedrooms: string; scope: string; period: string | null; moe: number | null }
  | { kind: "hud_rent"; bedrooms: string; fy: number }
  | { kind: "tax_rate"; year: number | null }
  | { kind: "chicago_tax_rate" }
  | { kind: "assumption"; source: string; asOf: string; low: number; high: number }
  | { kind: "none" };

/** Chicago's 2024 effective rate on residential market value: 10% assessment × 3.0355 equalizer × 6.6186% composite
    (Cook County Clerk, 2024 tax rate report). Used only when the parcel's own rate is unknown (an exempt lot). */
export const CHICAGO_EFFECTIVE_RATE = 0.1 * 3.0355 * 0.066186;
/** A unit this size or smaller is compared with 2-bedroom rents, larger with 3-bedroom. */
export const TWO_BED_MAX_SQFT = 1100;

const fa = (v: number | null | undefined) => (v != null && Number.isFinite(v) && v > 0 ? v : null);

/** The district's limits for a project on this lot. Height is the floors at `floorFt` each. */
export function allowedOf(inputs: DeepInputs) {
  const lot = inputs.lot;
  const area = fa(lot.land_sqft);
  const far = fa(lot.far);
  return {
    floorAreaSqft: area && far ? Math.round(area * far) : null,
    units: fa(lot.units_allowed),
    heightFt: fa(lot.max_height_ft),
    floorFt: inputs.floor_ft || 11,
  };
}

/** The ready-made projects for this lot: the largest by the numbers we checked, and a 3-flat. Null when the lot's
    numbers aren't known (a planned development sets its own; no lot area). */
export function startingProjects(inputs: DeepInputs): Project[] {
  const a = allowedOf(inputs);
  if (!a.floorAreaSqft) return [];
  const maxFloors = a.heightFt ? Math.max(1, Math.floor(a.heightFt / a.floorFt)) : 4;
  const out: Project[] = [];
  const units = a.units ?? Math.max(1, Math.floor(a.floorAreaSqft / 900));
  out.push({ kind: "largest", units, floors: maxFloors, floorAreaSqft: a.floorAreaSqft });
  if (!a.units || a.units >= 3) {
    const floors = Math.min(3, maxFloors);
    out.push({ kind: "three_flat", units: 3, floors, floorAreaSqft: Math.min(a.floorAreaSqft, 3 * 1500) });
  }
  return out;
}

export interface LimitUse { key: "floorArea" | "units" | "height"; used: number; allowed: number | null; share: number | null; over: boolean }

/** How much of each limit the project uses (a share for the rings; over 1 = over the limit, drawn red). */
export function limitUse(p: Project, inputs: DeepInputs): LimitUse[] {
  const a = allowedOf(inputs);
  const row = (key: LimitUse["key"], used: number, allowed: number | null): LimitUse => {
    const share = allowed ? used / allowed : null;
    return { key, used, allowed, share, over: share != null && share > 1 + 1e-9 };
  };
  return [
    row("floorArea", p.floorAreaSqft, a.floorAreaSqft),
    row("units", p.units, a.units),
    row("height", p.floors * a.floorFt, a.heightFt),
  ];
}

/** The project's height and the limit, for the map's mass (anything above `capFt` is red). */
export function projectMass(p: Project, inputs: DeepInputs): { heightFt: number; capFt: number | null } {
  const a = allowedOf(inputs);
  return { heightFt: p.floors * a.floorFt, capFt: a.heightFt };
}

function assumption(inputs: DeepInputs, key: string, fallback: number): { value: number; source: NumberSource } {
  const a = inputs.assumptions[key];
  if (!a) return { value: fallback, source: { kind: "none" } };
  return { value: a.value, source: { kind: "assumption", source: a.source, asOf: a.as_of, low: a.low, high: a.high } };
}

/** The starting numbers for a project, each with its source. */
export function startingNumbers(inputs: DeepInputs, p: Project): { numbers: Numbers; sources: Record<keyof Numbers, NumberSource> } {
  const sources = {} as Record<keyof Numbers, NumberSource>;
  const pick = (k: keyof Numbers, key: string, fallback: number) => {
    const r = assumption(inputs, key, fallback);
    sources[k] = r.source;
    return r.value;
  };

  const sale = inputs.last_sale;
  sources.landPrice = sale ? { kind: "lot_sale", date: sale.date } : { kind: "none" };

  // The sale price per unit: what a new condo sells for per gross sq ft here x this project's gross area per unit
  // (the zoning floor area, common space included, which is the basis the figure was measured on). Without it, the
  // area's median condo of any size or age, per unit, as before (and labeled so).
  const unitSize = p.units > 0 ? p.floorAreaSqft / p.units : 0;
  const nc = inputs.new_construction;
  const condo = inputs.area_sales.condo;
  let salePriceUnit = 0;
  if (nc && unitSize > 0) {
    salePriceUnit = Math.round((nc.value * unitSize) / 1000) * 1000;
    sources.salePriceUnit = { kind: "new_construction", perSqft: nc.value, low: nc.low, high: nc.high, unitSqft: Math.round(unitSize),
      n: nc.n, pooled: !!nc.pooled_areas, newSales: nc.new_sales, years: nc.years, premium: nc.premium, premiumN: nc.premium_n };
  } else if (condo) {
    salePriceUnit = condo.median;
    sources.salePriceUnit = { kind: "area_sales", group: "condo", year: condo.year, n: condo.n };
  } else sources.salePriceUnit = { kind: "none" };

  const bed = unitSize <= TWO_BED_MAX_SQFT ? "2_bedrooms" : "3_bedrooms";
  const census = inputs.rents.census[bed];
  const hudKey = bed === "2_bedrooms" ? "2" : "3";
  const hud = inputs.rents.hud?.by_bedroom?.[hudKey];
  let rent = 0;
  if (census) {
    rent = census.estimate;
    sources.rentUnitMonth = { kind: "census_rent", bedrooms: bed, scope: census.scope, period: inputs.rents.acs_period, moe: census.moe };
  } else if (hud) {
    rent = hud;
    sources.rentUnitMonth = { kind: "hud_rent", bedrooms: bed, fy: inputs.rents.hud!.fy };
  } else sources.rentUnitMonth = { kind: "none" };

  const ownRate = fa(inputs.tax.effective_rate);
  sources.taxRate = ownRate ? { kind: "tax_rate", year: inputs.tax.tax_year } : { kind: "chicago_tax_rate" };

  const numbers: Numbers = {
    landPrice: sale?.price ?? null,
    salePriceUnit,
    rentUnitMonth: rent,
    buildCostSqft: pick("buildCostSqft", "build_cost_sqft", 250),
    softCostPct: pick("softCostPct", "soft_cost_pct", 0.18),
    loanToCost: pick("loanToCost", "loan_to_cost", 0.65),
    loanRate: pick("loanRate", "loan_rate", 0.09),
    buildMonths: pick("buildMonths", "build_months", 14),
    sellingPct: pick("sellingPct", "selling_pct", 0.06),
    profitOnCost: pick("profitOnCost", "profit_on_cost", 0.2),
    vacancyPct: pick("vacancyPct", "vacancy_pct", 0.05),
    opexPct: pick("opexPct", "opex_pct", 0.3),
    capRate: pick("capRate", "cap_rate", 0.0625),
    targetYield: pick("targetYield", "target_yield", 0.0775),
    taxRate: ownRate ?? CHICAGO_EFFECTIVE_RATE,
  };
  return { numbers, sources };
}

export interface Result {
  /** Hard + soft costs + the loan's interest while building. */
  buildCost: number;
  /** The most the land can cost and still meet the target (negative = no land price works). */
  landBid: number;
  /** Per unit, at the land price: the sale price (sell) or monthly rent (rent) that just meets the target. */
  breakEven: number | null;
  /** The property tax once built, a year. */
  taxesOnceBuilt: number;
  /** Cash the builder brings: total cost less the loan, at the land price (else at the land bid). */
  cashIn: number | null;
}

export function buildCost(p: Project, n: Numbers): number {
  const hard = p.floorAreaSqft * n.buildCostSqft;
  const soft = hard * n.softCostPct;
  // Interest on a loan drawn evenly while building: about half the loan is out on average.
  const carry = n.loanRate * (n.buildMonths / 12) * 0.5 * n.loanToCost * (hard + soft);
  return hard + soft + carry;
}

export function compute(p: Project, n: Numbers, mode: Mode): Result {
  const build = buildCost(p, n);
  const land = n.landPrice;
  let landBid: number;
  let breakEven: number | null = null;
  let taxesOnceBuilt: number;
  if (mode === "sell") {
    const revenue = p.units * n.salePriceUnit;
    landBid = (revenue * (1 - n.sellingPct)) / (1 + n.profitOnCost) - build;
    taxesOnceBuilt = revenue * n.taxRate;
    if (land != null && p.units > 0) breakEven = ((land + build) * (1 + n.profitOnCost)) / (1 - n.sellingPct) / p.units;
  } else {
    // A rental's value is its income after tax at the cap rate, and its tax is a share of that value, so:
    // value = NOI before tax / (cap + tax rate).
    const noiBeforeTax = p.units * n.rentUnitMonth * 12 * (1 - n.vacancyPct) * (1 - n.opexPct);
    const value = noiBeforeTax / (n.capRate + n.taxRate);
    taxesOnceBuilt = value * n.taxRate;
    const noi = noiBeforeTax - taxesOnceBuilt;
    landBid = noi / n.targetYield - build;
    if (land != null && p.units > 0) {
      const needNoi = (land + build) * n.targetYield;
      const needBeforeTax = (needNoi * (n.capRate + n.taxRate)) / n.capRate;
      breakEven = needBeforeTax / (1 - n.opexPct) / (1 - n.vacancyPct) / 12 / p.units;
    }
  }
  const basis = land ?? (landBid > 0 ? landBid : null);
  return { buildCost: build, landBid, breakEven, taxesOnceBuilt, cashIn: basis != null ? (basis + build) * (1 - n.loanToCost) : null };
}

export const STRESS_STEPS = [-0.1, 0, 0.1] as const;

/** "If things move": the land bid with the sale price (or rent) and the build cost each 10% lower, as set, higher.
    Rows = price, columns = build cost. */
export function stressGrid(p: Project, n: Numbers, mode: Mode): number[][] {
  return STRESS_STEPS.map((dp) => STRESS_STEPS.map((dc) => compute(p, {
    ...n,
    salePriceUnit: n.salePriceUnit * (1 + dp),
    rentUnitMonth: n.rentUnitMonth * (1 + dp),
    buildCostSqft: n.buildCostSqft * (1 + dc),
  }, mode).landBid));
}

/** A project changed by − / + (units, floors, floor area), held to sane bounds. Floor area follows floors when the
    floors change (the same floor plate), so the drawing and the numbers stay one building. */
export function step(p: Project, field: "units" | "floors" | "floorAreaSqft", dir: 1 | -1): Project {
  const next = { ...p, kind: "own" as const };
  if (field === "units") next.units = Math.max(1, Math.min(200, p.units + dir));
  if (field === "floors") {
    const floors = Math.max(1, Math.min(30, p.floors + dir));
    const plate = p.floors > 0 ? p.floorAreaSqft / p.floors : p.floorAreaSqft;
    next.floors = floors;
    next.floorAreaSqft = Math.round(plate * floors);
  }
  if (field === "floorAreaSqft") next.floorAreaSqft = Math.max(500, Math.round((p.floorAreaSqft + dir * 250) / 50) * 50);
  return next;
}

/** "$1.75M", "$725k", "$3,514": short money for the big figures. */
export function money(v: number, lng: string, { short = true } = {}): string {
  const loc = lng.startsWith("es") ? "es-MX" : "en-US";
  const sign = v < 0 ? "−" : "";
  const a = Math.abs(v);
  if (short && a >= 1_000_000) return `${sign}$${(a / 1_000_000).toLocaleString(loc, { maximumFractionDigits: 2 })}M`;
  if (short && a >= 10_000) return `${sign}$${Math.round(a / 1000).toLocaleString(loc)}k`;
  return `${sign}$${Math.round(a).toLocaleString(loc)}`;
}
