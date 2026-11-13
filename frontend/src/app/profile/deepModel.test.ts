import { describe, expect, it } from "vitest";
import type { DeepInputs } from "../../lib/api";
import {
  CHICAGO_EFFECTIVE_RATE, buildCost, compute, limitUse, money, projectMass, startingNumbers, startingProjects, step,
  stressGrid, type Numbers, type Project,
} from "./deepModel";

// 642 W Belden (RM-5), the board's lot.
const A = (value: number, low: number, high: number) => ({ value, low, high, unit: "x", source: "test", as_of: "2026" });
const INPUTS: DeepInputs = {
  lot: { land_sqft: 3350, far: 2, max_height_ft: 45, units_allowed: 8, lot_area_per_unit: 400, footprint_sqft: null },
  last_sale: { price: 1_207_000, date: "2023-05-01", deed_type: "WARRANTY" },
  area_sales: { condo: { median: 605_000, n: 900, year: "2025" }, two_to_six: { median: 1_432_500, n: 84, year: "2025" } },
  rents: { census: { "2_bedrooms": { estimate: 3084, moe: 487, scope: "tract" }, "3_bedrooms": { estimate: 3250, moe: 722, scope: "tract" } },
    hud: { by_bedroom: { "2": 3020, "3": 3880 }, fy: 2027, zip: "60614" }, acs_period: "2020–2024" },
  tax: { effective_rate: 0.0201, tax_year: 2024, current_bill: 23024 },
  assumptions: {
    build_cost_sqft: A(250, 200, 275), soft_cost_pct: A(0.18, 0.15, 0.25), loan_to_cost: A(0.65, 0.6, 0.75),
    loan_rate: A(0.09, 0.0775, 0.1175), build_months: A(14, 10, 24), selling_pct: A(0.06, 0.04, 0.08),
    profit_on_cost: A(0.2, 0.15, 0.25), vacancy_pct: A(0.05, 0.03, 0.08), opex_pct: A(0.3, 0.25, 0.4),
    cap_rate: A(0.0625, 0.055, 0.07), target_yield: A(0.0775, 0.07, 0.09),
  },
  floor_ft: 11,
};

describe("starting projects", () => {
  it("largest by the numbers and a 3-flat, from the district's own limits", () => {
    const [largest, flat] = startingProjects(INPUTS);
    expect(largest).toEqual({ kind: "largest", units: 8, floors: 4, floorAreaSqft: 6700 });
    expect(flat).toEqual({ kind: "three_flat", units: 3, floors: 3, floorAreaSqft: 4500 });
  });
  it("no lot area or FAR: no projects (never a made-up building)", () => {
    expect(startingProjects({ ...INPUTS, lot: { ...INPUTS.lot, far: null } })).toEqual([]);
  });
});

describe("limits", () => {
  it("the largest fills floor area and units; 4 floors of 11 ft under 45 ft", () => {
    const [largest] = startingProjects(INPUTS);
    const u = Object.fromEntries(limitUse(largest, INPUTS).map((r) => [r.key, r]));
    expect(u.floorArea.share).toBe(1);
    expect(u.units.share).toBe(1);
    expect(u.height.used).toBe(44);
    expect(u.height.over).toBe(false);
  });
  it("a fifth floor goes over the height limit; the map's mass knows where", () => {
    const five = step(startingProjects(INPUTS)[0], "floors", 1);
    expect(five.kind).toBe("own");
    expect(limitUse(five, INPUTS).find((r) => r.key === "height")!.over).toBe(true);
    expect(projectMass(five, INPUTS)).toEqual({ heightFt: 55, capFt: 45 });
  });
});

describe("the arithmetic (the board's worked figures)", () => {
  const [largest] = startingProjects(INPUTS);
  const { numbers, sources } = startingNumbers(INPUTS, largest);

  it("starts from the lot's figures, each with its source", () => {
    expect(numbers.landPrice).toBe(1_207_000);
    expect(numbers.salePriceUnit).toBe(605_000);
    expect(numbers.rentUnitMonth).toBe(3084); // 837 sq ft a unit → 2-bedroom
    expect(sources.rentUnitMonth).toMatchObject({ kind: "census_rent", bedrooms: "2_bedrooms", moe: 487 });
    expect(sources.buildCostSqft).toMatchObject({ kind: "assumption", low: 200, high: 275 });
    expect(numbers.taxRate).toBe(0.0201);
  });

  it("build cost = hard + soft + interest while building", () => {
    expect(Math.round(buildCost(largest, numbers))).toBe(2_043_948);
  });

  it("selling 8 condos supports about $1.75M for the land; break-even $519k a unit at the $1.21M price", () => {
    const r = compute(largest, numbers, "sell");
    expect(Math.round(r.landBid)).toBe(1_747_385);
    expect(Math.round(r.breakEven!)).toBe(518_768);
    expect(Math.round(r.cashIn!)).toBe(Math.round((1_207_000 + buildCost(largest, numbers)) * 0.35));
  });

  it("as rentals no land price works, and break-even rent is far above the area's", () => {
    const r = compute(largest, numbers, "rent");
    expect(r.landBid).toBeLessThan(0);
    expect(r.breakEven!).toBeGreaterThan(5000);
    // The rental's value carries its own tax: tax = value × rate, value = NOI before tax ÷ (cap + rate).
    const noiBT = 8 * 3084 * 12 * 0.95 * 0.7;
    expect(r.taxesOnceBuilt).toBeCloseTo((noiBT / (0.0625 + 0.0201)) * 0.0201, 0);
  });

  it("the stress grid recomputes the land bid with price and build cost ±10%", () => {
    const g = stressGrid(largest, numbers, "sell");
    expect(Math.round(g[1][1])).toBe(1_747_385);
    expect(g[0][2]).toBeLessThan(g[1][1]); // lower price, higher cost
    expect(g[2][0]).toBeGreaterThan(g[1][1]);
  });

  it("no last sale: no break-even at a price, cash from the land bid", () => {
    const n: Numbers = { ...numbers, landPrice: null };
    const r = compute(largest, n, "sell");
    expect(r.breakEven).toBeNull();
    expect(r.cashIn).toBeCloseTo((r.landBid + r.buildCost) * 0.35, 0);
  });
});

describe("an exempt lot", () => {
  it("uses Chicago's 2024 effective rate and says so", () => {
    const p: Project = startingProjects(INPUTS)[0];
    const { numbers, sources } = startingNumbers({ ...INPUTS, tax: { effective_rate: null, tax_year: null, current_bill: null } }, p);
    expect(numbers.taxRate).toBeCloseTo(CHICAGO_EFFECTIVE_RATE, 6);
    expect(sources.taxRate).toEqual({ kind: "chicago_tax_rate" });
  });
});

describe("money", () => {
  it("short figures", () => {
    expect(money(1_747_386, "en")).toBe("$1.75M");
    expect(money(518_768, "en")).toBe("$519k");
    expect(money(3514, "en")).toBe("$3,514");
    expect(money(-121_000, "en")).toBe("−$121k");
  });
});
