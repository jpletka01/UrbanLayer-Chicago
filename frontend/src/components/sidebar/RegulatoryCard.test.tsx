import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { RegulatoryCard } from "./RegulatoryCard";
import type { RegulatorySummary } from "../../lib/types";

afterEach(cleanup);

const base = {
  overlays: [], in_planned_development: false, in_landmark_district: false, is_landmark_building: false,
  in_historic_district: false, on_national_register: false, in_lakefront_protection: false, on_pedestrian_street: false,
  in_special_district: false, in_pmd: false, in_tod_area: false, in_adu_area: false, in_aro_zone: false, in_ssa: false,
  flood_zone: null, flood_zone_subtype: null, in_special_flood_hazard: false, brownfield_sites: [], aro_housing: null,
} as unknown as RegulatorySummary;

describe("sidebar RegulatoryCard — flood zone", () => {
  it("says FEMA's flood map didn't answer instead of leaving the flood zone out", () => {
    render(<RegulatoryCard data={{ ...base, flood_unchecked: true, in_special_flood_hazard: null }} />);
    expect(screen.getByTestId("flood-unchecked").textContent).toContain("FEMA flood zone didn't answer");
  });

  it("shows nothing about flood when FEMA answered 'no zone'", () => {
    render(<RegulatoryCard data={base} />);
    expect(screen.queryByTestId("flood-unchecked")).toBeNull();
  });
});
