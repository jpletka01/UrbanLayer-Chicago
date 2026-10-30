import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ScorecardPropertyCard } from "./ScorecardPropertyCard";
import { ProvenanceProvider } from "../../contexts/ProvenanceContext";
import type { Provenance } from "../../lib/api";
import type { PropertySummary } from "../../lib/types";

afterEach(cleanup);

const data = {
  pin14: "14313320180000", address: "1601 N Milwaukee Ave", bldg_class: "517", bldg_class_description: "Retail",
  bldg_sqft: 15650, land_sqft: 11951, stories: 2, units: null, year_built: 1920, bldg_age: 105,
  total_assessed_value: 398120, estimated_annual_tax: 82586, tax_year: 2024, effective_tax_rate: 0.0519,
  assessment_history: [], sales_history: [], tax_exemptions: [], data_gaps: [],
  flags: { chrs_rating: "orange", tax_sale_years: [], scavenger_sale_years: [] },
} as unknown as PropertySummary;

function entry(over: Partial<Provenance>): Provenance {
  return {
    label: "Figure", kind: "official_record", source: null, record_id: null, url: null, section: null, as_of: null,
    effective_date: null, query_date: "2026-10-21", note: null, tier: "official_record", as_of_basis: "queried",
    method_key: "recorded", method: "Read as recorded by the publisher", confidence: "standard", confidence_reasons: [],
    ...over,
  };
}

const prov: Record<string, Provenance> = {
  "property.bldg_sqft": entry({ source_id: "cook.assessor.characteristics", as_of: "2026-10-15", as_of_basis: "source_updated", age_days: 6 }),
  "property.land_sqft": entry({
    kind: "derived", tier: "our_calculation", source_id: "cook.ptaxsim", method_key: "calculation", method: "Our calculation",
    source: "Parcel polygon area (Cook County property-tax database)",
  }),
  "property.stories": entry({
    source_id: "chi.building_footprints", as_of: "2015-08-15", as_of_basis: "source_updated", age_days: 4085, confidence_reasons: ["old_source"],
  }),
  "property.tax_estimate": entry({
    kind: "derived", tier: "official_estimate", source_id: "cook.ptaxsim", method_key: "government_model", method: "A government agency's model",
    as_of: "2024-12-31", as_of_basis: "tax_year", period: "2024", age_days: 659,
  }),
  "property.flags.chrs": entry({
    source_id: "artifact.chrs", as_of: "1996-12-31", as_of_basis: "vintage", period: "1996", age_days: 10886, confidence_reasons: ["old_source"],
  }),
};

describe("ScorecardPropertyCard — confidence captions", () => {
  it("without provenance there are no captions", () => {
    render(<ScorecardPropertyCard data={data} />);
    expect(screen.queryAllByTestId("confidence-caption")).toHaveLength(0);
  });

  it("captions only what the quiet rule allows: the 2015 stories, the lot area, the tax model, the 1996 survey", () => {
    render(
      <ProvenanceProvider value={prov}>
        <ScorecardPropertyCard data={data} />
      </ProvenanceProvider>,
    );
    const lines = screen.getAllByTestId("confidence-caption").map((e) => e.textContent);
    expect(lines).toContain("City footprint survey · 2015");
    expect(lines).toContain("Parcel polygon area (Cook County property-tax database)");
    expect(lines).toContain("Government model");
    expect(lines).toContain("Historic Resources Survey (frozen) · 1996");
    expect(lines).toHaveLength(4); // floor area from the assessor stays quiet
  });
});
