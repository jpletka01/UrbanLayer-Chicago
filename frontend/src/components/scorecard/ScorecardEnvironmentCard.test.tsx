import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ScorecardEnvironmentCard } from "./ScorecardEnvironmentCard";
import type { RegulatorySummary } from "../../lib/types";

afterEach(cleanup);

const base = {
  overlays: [], in_planned_development: false, in_landmark_district: false, is_landmark_building: false,
  in_historic_district: false, on_national_register: false, in_lakefront_protection: false, on_pedestrian_street: false,
  in_special_district: false, in_pmd: false, in_tod_area: false, in_adu_area: false, in_aro_zone: false, in_ssa: false,
  flood_zone: null, flood_zone_subtype: null, in_special_flood_hazard: false, brownfield_sites: [],
} as unknown as RegulatorySummary;

describe("ScorecardEnvironmentCard — a flood zone FEMA couldn't answer for is not 'no flood zone'", () => {
  it("says the flood zone couldn't be checked, in words, with a way to look it up", () => {
    render(<ScorecardEnvironmentCard data={{ ...base, flood_unchecked: true, in_special_flood_hazard: null }} />);
    const row = screen.getByTestId("module-unchecked");
    expect(row.textContent).toContain("Couldn't check today");
    expect(row.textContent).toContain("FEMA flood zone didn't answer");
    expect(row.textContent).toContain("isn't a \"no\"");
    expect(screen.getByRole("link", { name: /FEMA flood map/ }).getAttribute("href")).toBe("https://msc.fema.gov/portal/home");
    // it does not state a zone, a clear result, or a special flood hazard
    expect(screen.queryByText(/Zone /)).toBeNull();
    expect(screen.queryByText(/special flood hazard/i)).toBeNull();
  });

  it("keeps showing the brownfield sites beside it", () => {
    render(<ScorecardEnvironmentCard data={{ ...base, flood_unchecked: true, in_special_flood_hazard: null, brownfield_sites: [{ site_name: "Old Plating Works" }] }} />);
    expect(screen.getByTestId("flood-unchecked")).toBeTruthy();
    expect(screen.getByText("Old Plating Works")).toBeTruthy();
  });

  it("a flood zone that came back is shown as before, with no unchecked row", () => {
    render(<ScorecardEnvironmentCard data={{ ...base, flood_zone: "AE", in_special_flood_hazard: true }} />);
    expect(screen.queryByTestId("module-unchecked")).toBeNull();
    expect(screen.getByText(/Special Flood Hazard/i)).toBeTruthy();
  });

  it("still renders nothing when FEMA answered 'no zone' and there are no brownfields", () => {
    const { container } = render(<ScorecardEnvironmentCard data={base} />);
    expect(container.firstChild).toBeNull();
  });
});
