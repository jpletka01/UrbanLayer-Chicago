import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ScorecardIncentivesCard } from "./ScorecardIncentivesCard";
import type { IncentivesSummary } from "../../lib/types";

afterEach(cleanup);

const base = {
  in_tif_district: false, tif_name: null, tif_fund_history: [], in_opportunity_zone: false, oz_tract: null,
  in_enterprise_zone: false, enterprise_zone_name: null, in_qct: false, qct_tract: null,
  in_nmtc: false, nmtc_tract: null, nmtc_severe_distress: false, grant_programs: null, property_tax_class: null,
} as unknown as IncentivesSummary;

describe("ScorecardIncentivesCard — an Enterprise Zone layer that failed is not 'Not in' (Item 64)", () => {
  it("shows Enterprise Zone as Not checked, and leaves it out of the 'Not in' line", () => {
    render(<ScorecardIncentivesCard data={{ ...base, enterprise_zone_unchecked: true }} />);
    const row = screen.getByTestId("ez-unchecked");
    expect(row.textContent).toContain("Enterprise Zone");
    expect(row.textContent).toContain("Not checked");
    const notIn = screen.getByText(/^Not in:/);
    expect(notIn.textContent).not.toContain("Enterprise Zone");
    expect(notIn.textContent).toContain("TIF");
  });

  it("a checked miss stays in the 'Not in' line with no Not-checked row", () => {
    render(<ScorecardIncentivesCard data={base} />);
    expect(screen.queryByTestId("ez-unchecked")).toBeNull();
    expect(screen.getByText(/^Not in:/).textContent).toContain("Enterprise Zone");
  });

  it("a zone hit shows the zone and no Not-checked row", () => {
    render(<ScorecardIncentivesCard data={{ ...base, in_enterprise_zone: true, enterprise_zone_name: "Chicago Enterprise Zone 5" }} />);
    expect(screen.getByText("Chicago Enterprise Zone 5")).toBeTruthy();
    expect(screen.queryByTestId("ez-unchecked")).toBeNull();
  });
});
