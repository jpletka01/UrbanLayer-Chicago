import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ScorecardPropertyCard } from "./ScorecardPropertyCard";
import { PropertyCard } from "../sidebar/PropertyCard";
import type { PropertySummary } from "../../lib/types";

afterEach(cleanup);

// PIN 14-28-319-102-0000: the County's $1 class-100 parcel (decision Item 46). The backend sends no assessed
// value, market value or tax for it, and keeps the County's number in nominal_assessed_value.
const dollarParcel = {
  pin14: "14283191020000", address: null, bldg_class: "1-00", bldg_class_description: "Vacant land",
  bldg_sqft: null, land_sqft: 143032, stories: null, units: null, year_built: null, bldg_age: null,
  total_assessed_value: null, nominal_assessment: true, nominal_assessed_value: 1,
  estimated_annual_tax: null, implied_market_value: null, effective_tax_rate: null, tax_year: null,
  assessment_history: [
    { year: 2026, land: 1, building: 0, total: 1 },
    { year: 2025, land: 1, building: 0, total: 1 },
  ],
  sales_history: [], tax_exemptions: [], tax_breakdown: [], data_gaps: [],
} as unknown as PropertySummary;

describe("nominal assessment", () => {
  it("states the fact on the Profile and shows no dollar figure", () => {
    render(<ScorecardPropertyCard data={dollarParcel} />);
    const box = screen.getByTestId("nominal-assessment");
    expect(box.textContent).toContain("Nominal");
    expect(box.textContent).toContain("not a market value");
    expect(box.textContent).toContain("35 ILCS 200/10-35");
    // No "$1", "$10" or "$0" anywhere outside the statute's own "$1 a year".
    const text = document.body.textContent ?? "";
    expect(text.replace("$1 a year", "")).not.toMatch(/\$\s?[01]\b|\$10\b/);
    // The flat $1 timeline is not drawn.
    expect(screen.queryByText("Assessment History")).toBeNull();
  });

  it("states the fact in the chat rail card", () => {
    render(<PropertyCard data={dollarParcel} />);
    expect(screen.getByTestId("nominal-assessment").textContent).toContain("Nominal");
  });
});
