import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ScorecardPropertyCard } from "./ScorecardPropertyCard";
import type { PropertySummary } from "../../lib/types";

afterEach(cleanup);

const base = {
  pin14: "14171060250000",
  address: "1500 W Wilson Ave",
  bldg_class: "517",
  bldg_class_description: "Retail strip center",
  bldg_sqft: null,
  land_sqft: 4347,
  assessment_history: [],
  sales_history: [],
  tax_exemptions: [],
  data_gaps: [],
} as unknown as PropertySummary;

describe("ScorecardPropertyCard — member of a multi-parcel complex (F6)", () => {
  it("says the building area belongs to the complex and shows no floor area for this lot", () => {
    render(<ScorecardPropertyCard data={{ ...base, complex_bldg_sqft: 43790, complex_member_pins: ["a", "b", "c", "d", "e", "f", "g"] }} />);
    const note = screen.getByTestId("complex-building-note");
    expect(note.textContent).toContain("one of 7");
    expect(note.textContent).toContain("43,790");
    expect(screen.queryByText("43,790 ft²")).toBeNull(); // never presented as this lot's floor area
  });

  it("shows no note on an ordinary parcel", () => {
    render(<ScorecardPropertyCard data={{ ...base, bldg_sqft: 2400 }} />);
    expect(screen.queryByTestId("complex-building-note")).toBeNull();
  });
});
