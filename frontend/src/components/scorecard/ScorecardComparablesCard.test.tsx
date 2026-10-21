import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ScorecardComparablesCard } from "./ScorecardComparablesCard";
import { ProvenanceProvider } from "../../contexts/ProvenanceContext";
import type { Provenance } from "../../lib/api";
import type { ComparablesSummary } from "../../lib/types";

afterEach(cleanup);

const sale = (price: number, i: number) => ({
  pin: `p${i}`, sale_date: "2026-03-01", sale_price: price, land_sqft: 4000, bldg_sqft: 2000,
  price_per_land_sqft: price / 4000, price_per_bldg_sqft: price / 2000, distance_mi: 0.1, deed_type: "Warranty", class_code: "517",
});
const data = {
  sales: [sale(300000, 1), sale(320000, 2)], sales_volume: 2, median_sale_price: 310000,
  median_price_per_land_sqft: 77, median_price_per_bldg_sqft: 155, price_range_min: 300000, price_range_max: 320000,
  median_price_per_buildable_sqft: null,
} as unknown as ComparablesSummary;

function entry(n: number, over: Partial<Provenance> = {}): Provenance {
  return {
    label: "Median", kind: "derived", source: null, record_id: null, url: null, section: null, as_of: null,
    effective_date: null, query_date: "2026-10-21", note: null, tier: "our_calculation", as_of_basis: "queried",
    method_key: "calculation", method: "Our calculation", confidence: "standard", confidence_reasons: [],
    scope: "radius", period: "last 3 years", method_params: { radius_mi: 0.28, window_years: 3 },
    coverage: { n, unit: "sales", sample: "comps" }, ...over,
  };
}

describe("ScorecardComparablesCard — confidence", () => {
  it("without provenance, renders exactly as before", () => {
    render(<ScorecardComparablesCard data={data} />);
    expect(screen.getByText("$310,000")).toBeTruthy();
    expect(screen.queryByTestId("confidence-caption")).toBeNull();
  });

  it("captions the median with the search's real basis", () => {
    render(
      <ProvenanceProvider value={{ "property.comps.median_price": entry(8) }}>
        <ScorecardComparablesCard data={data} />
      </ProvenanceProvider>,
    );
    expect(screen.getByTestId("comps-confidence").textContent).toBe("8 sales · 0.28 mi · 3 yr");
    expect(screen.getByText("$310,000")).toBeTruthy();
  });

  it("shows a dash and the reason when the median is withheld, but keeps the sales list", () => {
    render(
      <ProvenanceProvider value={{
        "property.comps.median_price": entry(2, { confidence: "withheld", confidence_reasons: ["small_sample"] }),
      }}>
        <ScorecardComparablesCard data={data} />
      </ProvenanceProvider>,
    );
    expect(screen.queryByText("$310,000")).toBeNull();
    expect(screen.getByText("Not shown: only 2 sales (needs 3).")).toBeTruthy();
    expect(screen.getByText("$300,000")).toBeTruthy(); // the sales table still lists every sale
    expect(screen.getByText("$320,000")).toBeTruthy();
  });

  it("names a faded per-ft² median on its own line", () => {
    render(
      <ProvenanceProvider value={{
        "property.comps.median_price": entry(4, { confidence: "low", confidence_reasons: ["small_sample"] }),
        "property.comps.median_price_per_land_sqft": entry(4, { confidence: "low", confidence_reasons: ["small_sample"] }),
      }}>
        <ScorecardComparablesCard data={data} />
      </ProvenanceProvider>,
    );
    const lines = screen.getAllByTestId("confidence-caption").map((e) => e.textContent);
    expect(lines).toContain("Low confidence · 4 sales · 0.28 mi · 3 yr");
    expect(lines).toContain("$/Land Sqft: Low confidence · 4 sales · 0.28 mi · 3 yr");
  });
});
