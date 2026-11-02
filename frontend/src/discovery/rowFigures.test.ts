import { describe, expect, it } from "vitest";
import i18n from "i18next";
import { rowFigures } from "./DiscoveryResults";
import type { ResultRow } from "./types";

const t = (key: string, opts?: Record<string, unknown>) => i18n.t(key, { ns: "pages", ...opts });
const row = (over: Partial<ResultRow>): ResultRow => ({
  pin: "14-28-319-102-0000", lat: null, lon: null, address: null, community_area: null, land_use: "residential",
  class: "2-99", lot_sqft: 143900, bldg_sqft: null, year_built: null, units: null, assessed_value: 1,
  price_per_sf: null, last_sale_price: null, last_sale_date: null, improvement_ratio: null, value_percentile: null,
  upside_score: null, is_teardown_candidate: false, sortValue: 1, ...over,
});

describe("Discovery row figures (decision Items 46, 57)", () => {
  it("a nominal assessment reads Nominal, never $1", () => {
    const f = rowFigures(row({ nominal_assessment: true }), "assessed_value", t);
    expect(f.primary).toBe("Nominal");
    expect(JSON.stringify(f)).not.toContain("$1");
    const byLot = rowFigures(row({ nominal_assessment: true }), "lot_size", t);
    expect(byLot.secondary).toBe("Nominal assessment");
  });

  it("$0 is a value and stays $0; a missing value stays missing", () => {
    expect(rowFigures(row({ assessed_value: 0 }), "assessed_value", t).primary).toBe("$0");
    const missing = rowFigures(row({ assessed_value: null }), "assessed_value", t);
    expect(missing.primary).toBeNull();
    expect(missing.secondary).toBeNull();
  });
});

describe("titleCaseAddress", async () => {
  const { titleCaseAddress } = await import("../lib/format");
  it("title-cases a dataset address, keeping directionals and ordinals", () => {
    expect(titleCaseAddress("9171 S HARVARD AVE")).toBe("9171 S Harvard Ave");
    expect(titleCaseAddress("2400 W 51ST ST")).toBe("2400 W 51st St");
  });
});
