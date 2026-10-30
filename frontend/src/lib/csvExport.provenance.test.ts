import { describe, expect, it } from "vitest";
import { buildScorecardCSV } from "./csvExport";
import type { Provenance } from "./api";
import type { ComparablesSummary, ContextObject } from "./types";

function entry(over: Partial<Provenance>): Provenance {
  return {
    label: "Figure", kind: "official_record", source: null, record_id: null, url: null, section: null, as_of: null,
    effective_date: null, query_date: "2026-10-21", note: null, tier: "official_record", as_of_basis: "queried",
    method_key: "recorded", method: "Read as recorded by the publisher", confidence: "standard", confidence_reasons: [],
    ...over,
  };
}

const ctx = {
  property: {
    pin14: "14313320180000", address: "1601 N Milwaukee Ave", stories: 2, bldg_sqft: 15650, land_sqft: 11951,
    total_assessed_value: 398120, estimated_annual_tax: 82586, tax_year: 2024,
    assessment_history: [], sales_history: [], tax_breakdown: [],
  },
} as unknown as ContextObject;
const comps = {
  sales: [{ pin: "x", sale_date: "2026-03-01", sale_price: 300000 }], sales_volume: 2, median_sale_price: 310000,
  median_price_per_land_sqft: 77, median_price_per_bldg_sqft: 155,
} as unknown as ComparablesSummary;

const prov: Record<string, Provenance> = {
  "property.stories": entry({
    source_id: "chi.building_footprints", as_of: "2015-08-15", as_of_basis: "source_updated", age_days: 4085, confidence_reasons: ["old_source"],
  }),
  "property.comps.median_price": entry({
    tier: "our_calculation", method_key: "calculation", confidence: "withheld", confidence_reasons: ["small_sample"],
    coverage: { n: 2, unit: "sales", sample: "comps" },
  }),
};

describe("buildScorecardCSV — source columns", () => {
  const csv = buildScorecardCSV(ctx, "1601 N Milwaukee Ave", comps, prov);
  const row = (label: string) => csv.split("\n").find((l) => l.startsWith(label)) ?? "";

  it("adds source, authority, as-of and the page's caption to each figure with an entry", () => {
    expect(csv).toContain("Field,Value,Source,Authority,As of,Note");
    expect(row("Stories,")).toBe("Stories,2,chi.building_footprints,Official record,2015-08-15,City footprint survey · 2015");
  });

  it("leaves a withheld figure blank and says why", () => {
    expect(row("Median Sale Price,")).toBe("Median Sale Price,,,Our calculation,,Not shown: only 2 sales (needs 3).");
  });

  it("keeps rows without an entry, with empty source columns", () => {
    expect(row("Address,")).toBe("Address,1601 N Milwaukee Ave,,,,");
  });

  it("works without provenance at all", () => {
    expect(buildScorecardCSV(ctx, "x", comps)).toContain("Stories,2,,,,");
  });
});
