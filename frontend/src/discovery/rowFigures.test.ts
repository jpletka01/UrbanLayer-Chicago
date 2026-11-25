import { describe, expect, it } from "vitest";
import { profileAddress } from "./rowFigures";
import type { ResultRow } from "./types";

const row = (over: Partial<ResultRow>): ResultRow => ({
  pin: "14-28-319-102-0000", lat: null, lon: null, address: null, community_area: null, land_use: "residential",
  class: "2-99", lot_sqft: 143900, bldg_sqft: null, year_built: null, units: null, assessed_value: 1,
  price_per_sf: null, last_sale_price: null, last_sale_date: null, improvement_ratio: null, value_percentile: null,
  upside_score: null, is_teardown_candidate: false, sortValue: 1, ...over,
});

describe("the address a Profile link carries (Item 109)", () => {
  it("only an Address Point address; never an approximate or an Assessor one, which can be next door's", () => {
    expect(profileAddress(row({ address: "2626 S TROY ST" }))).toBe("2626 S Troy St");
    expect(profileAddress(row({ address: "2626 S TROY ST", address_source: "assessor" }))).toBeNull();
    expect(profileAddress(row({ address: "~2624 S TROY ST" }))).toBeNull();
    expect(profileAddress(row({ address: null }))).toBeNull();
  });
});

describe("titleCaseAddress", async () => {
  const { titleCaseAddress } = await import("../lib/format");
  it("title-cases a dataset address, keeping directionals and ordinals", () => {
    expect(titleCaseAddress("9171 S HARVARD AVE")).toBe("9171 S Harvard Ave");
    expect(titleCaseAddress("2400 W 51ST ST")).toBe("2400 W 51st St");
  });
});
