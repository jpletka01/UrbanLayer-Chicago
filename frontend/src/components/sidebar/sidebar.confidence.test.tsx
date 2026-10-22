import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { DataView } from "./DataView";
import { NeighborhoodCard } from "./NeighborhoodCard";
import { PropertyCard } from "./PropertyCard";
import { ViolationsCard } from "./ViolationsCard";
import { ProvenanceProvider } from "../../contexts/ProvenanceContext";
import type { Provenance } from "../../lib/api";
import type { CensusTractDemographics, ContextObject, NeighborhoodSummary, PropertySummary, ViolationSummary } from "../../lib/types";

// WS0 M6: the chat rail captions its figures from the turn's provenance, quiet by default.

afterEach(cleanup);

function entry(over: Partial<Provenance>): Provenance {
  return {
    label: "Figure", kind: "official_record", source: null, record_id: null, url: null, section: null, as_of: null,
    effective_date: null, query_date: "2026-10-22", note: null, tier: "official_record", as_of_basis: "queried",
    method_key: "recorded", method: "Read as recorded by the publisher", confidence: "standard", confidence_reasons: [],
    ...over,
  };
}

const tract = {
  tract_fips: "17031831000", tract_name: "Census Tract 8310", census_reporter_url: null,
  population: 2431, median_household_income: null, per_capita_income: null, median_age: null, median_home_value: null,
  median_gross_rent: 2435, owner_occupied_pct: null, vacancy_rate: null,
  poverty_rate: null, // withheld on the server: the value is gone from the context
  unemployment_rate: null, bachelors_or_higher_pct: null, foreign_born_pct: null,
  acs_period: "2020–2024", moe: { median_gross_rent: 220 }, cv: {},
  age_distribution: [], income_distribution: [], race_distribution: [], education_distribution: [],
  transportation_distribution: [], county_median_income: null, city_median_income: null,
} as unknown as CensusTractDemographics;

const hood = { census_tract: tract, transit: null, walkscore: null, demographics: null } as unknown as NeighborhoodSummary;

const prov: Record<string, Provenance> = {
  "area.tract.median_gross_rent": entry({
    tier: "official_estimate", method_key: "survey_estimate", source_id: "census.acs", period: "2020–2024", scope: "tract",
    precision: { moe: 220, moe_level: 0.9, cv: 0.055 },
  }),
  "area.tract.poverty_rate": entry({
    label: "Poverty rate", tier: "official_estimate", method_key: "survey_estimate", confidence: "withheld",
    confidence_reasons: ["high_cv"], precision: { moe: 2.5, moe_level: 0.9, cv: 0.61 },
  }),
};

function openTract() {
  fireEvent.click(screen.getByRole("button", { name: /Census Tract 8310/ }));
}

describe("NeighborhoodCard — margins and withheld figures from the turn's provenance", () => {
  it("shows a published margin of error beside its figure and says what ± means", () => {
    render(<ProvenanceProvider value={prov}><NeighborhoodCard data={hood} /></ProvenanceProvider>);
    openTract();
    expect(screen.getAllByTestId("margin").map((e) => e.textContent?.trim())).toContain("±$220");
    expect(screen.getByText(/90% margin of error/)).toBeTruthy();
  });

  it("a withheld figure is not shown and says why", () => {
    render(<ProvenanceProvider value={prov}><NeighborhoodCard data={hood} /></ProvenanceProvider>);
    openTract();
    const note = screen.getByTestId("tract-withheld").textContent ?? "";
    expect(note).toContain("Poverty: Not shown");  // the card's own label for the row
    expect(note).toContain("Not shown: the margin of error is 61% of the estimate.");
  });

  it("without provenance (an older stored message) nothing extra renders", () => {
    render(<NeighborhoodCard data={hood} />);
    openTract();
    expect(screen.queryByTestId("margin")).toBeNull();
    expect(screen.queryByTestId("tract-withheld")).toBeNull();
    expect(screen.queryByText(/90% margin of error/)).toBeNull();
  });

  it("fades a low-confidence community-area income and captions Walk Score as a private company's index", () => {
    const data = {
      ...hood, census_tract: null,
      demographics: { community_area: 24, community_area_name: "West Town", population: 87781, median_household_income: 98000, acs_period: "2019–2023" },
      walkscore: { walk_score: 91, transit_score: null, bike_score: null, walk_description: null, ws_link: null },
    } as unknown as NeighborhoodSummary;
    const p = {
      "area.community_area.median_household_income": entry({ tier: "our_calculation", method_key: "bracket_median", confidence: "low", confidence_reasons: ["bracket_median"] }),
      "neighborhood.walkscore": entry({ tier: "non_government", method_key: "commercial_index", source_id: "private.walkscore" }),
    };
    const { container } = render(<ProvenanceProvider value={p}><NeighborhoodCard data={data} /></ProvenanceProvider>);
    expect(container.querySelector('[data-state="low"]')?.textContent).toBe("$98,000");
    expect(screen.getAllByTestId("confidence-caption").map((e) => e.textContent)).toContain("Walk Score® (private company)");
  });
});

const property = {
  pin14: "14313320180000", address: "1601 N Milwaukee Ave", bldg_class: "517", bldg_class_description: "Retail",
  bldg_sqft: 15650, land_sqft: 11951, stories: 2, units: null, year_built: 1920, bldg_age: 105,
  total_assessed_value: 398120, estimated_annual_tax: 82586, tax_year: 2024, effective_tax_rate: 0.0519,
  assessment_history: [], sales_history: [], tax_exemptions: [], tax_breakdown: [], data_gaps: [],
} as unknown as PropertySummary;

describe("PropertyCard — captions only where the quiet rule allows", () => {
  it("captions the 2015 stories and the calculated rate; the Assessor's floor area stays quiet", () => {
    const p = {
      "property.bldg_sqft": entry({ source_id: "cook.assessor.characteristics", as_of: "2026-10-15", as_of_basis: "source_updated", age_days: 7 }),
      "property.stories": entry({ source_id: "chi.building_footprints", as_of: "2015-08-15", as_of_basis: "source_updated", age_days: 4085, confidence_reasons: ["old_source"] }),
      "property.effective_rate": entry({ tier: "our_calculation", method_key: "calculation", period: "2024", kind: "derived" }),
    };
    render(<ProvenanceProvider value={p}><PropertyCard data={property} /></ProvenanceProvider>);
    const lines = screen.getAllByTestId("confidence-caption").map((e) => e.textContent ?? "");
    expect(lines.some((l) => l.includes("City footprint survey") && l.includes("2015"))).toBe(true);
    expect(lines.some((l) => l.startsWith("Effective") || l.includes("2024"))).toBe(true);
    expect(lines).toHaveLength(2);
  });

  it("without provenance there are no captions", () => {
    render(<PropertyCard data={property} />);
    expect(screen.queryAllByTestId("confidence-caption")).toHaveLength(0);
  });
});

describe("ViolationsCard — the category grouping is ours", () => {
  it("says so under the heading", () => {
    const data = { total: 12, open_count: 3, by_category: { structural: 7, fire: 5 }, top_descriptions: [] } as unknown as ViolationSummary;
    render(<ViolationsCard data={data} />);
    expect(screen.getByText("Grouped by keyword (our grouping)")).toBeTruthy();
  });
});

describe("DataView — hands the turn's provenance to its cards", () => {
  it("captions from context.provenance, and a message without it renders as before", () => {
    const context = { neighborhood: hood, provenance: prov, requires_disclaimer: false, code_chunks: [] } as unknown as ContextObject;
    const { unmount } = render(<DataView context={context} loading={false} />);
    openTract();
    expect(screen.getByTestId("tract-withheld")).toBeTruthy();
    unmount();
    render(<DataView context={{ ...context, provenance: undefined }} loading={false} />);
    openTract();
    expect(screen.queryByTestId("tract-withheld")).toBeNull();
  });
});
