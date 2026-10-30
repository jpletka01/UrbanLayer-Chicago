import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NeighborhoodCard } from "./NeighborhoodCard";
import type { CensusTractDemographics, NeighborhoodSummary } from "../../lib/types";

afterEach(cleanup);

const tract = {
  tract_fips: "17031242400", tract_name: "Census Tract 2424", census_reporter_url: null,
  population: 3084, median_household_income: 110795, per_capita_income: null, median_age: null,
  median_home_value: null, median_gross_rent: null, owner_occupied_pct: null, vacancy_rate: null,
  poverty_rate: 8.9, unemployment_rate: 5.0, bachelors_or_higher_pct: null, foreign_born_pct: null,
  acs_period: "2020–2024",
  age_distribution: [], income_distribution: [], race_distribution: [], education_distribution: [],
  transportation_distribution: [], county_median_income: null, city_median_income: null,
} as CensusTractDemographics;

const base = { census_tract: null, transit: null, walkscore: null } as unknown as NeighborhoodSummary;

describe("NeighborhoodCard — two ACS vintages, never unlabeled (WS0 M1)", () => {
  it("captions the community-area block with its vintage and how the income median was made", () => {
    render(<NeighborhoodCard data={{ ...base, demographics: { community_area: 24, community_area_name: "West Town", population: 87781, median_household_income: 111111, acs_period: "2019–2023" } }} />);
    const cap = screen.getByTestId("ca-demographics-caption").textContent ?? "";
    expect(cap).toContain("West Town");
    expect(cap).toContain("ACS 2019–2023");
    expect(cap).toContain("estimated from 5 brackets");
  });

  it("never shows the retired 2008–2012 figures from an old stored context", () => {
    // A conversation saved before 2026-10-20 still carries kn9c poverty/unemployment.
    const old = { community_area: 24, community_area_name: "West Town", population: 87781, median_household_income: 82000,
      poverty_rate: 12.4, unemployment_rate: 6.1, median_age: 33.5 } as unknown as NeighborhoodSummary["demographics"];
    const { container } = render(<NeighborhoodCard data={{ ...base, demographics: old }} />);
    expect(container.textContent).not.toContain("12.4%");
    expect(container.textContent).not.toContain("6.1%");
    expect(container.textContent).not.toContain("33.5");
  });

  it("labels the tract block with its release and shows tract poverty and unemployment", () => {
    render(<NeighborhoodCard data={{ ...base, demographics: null, census_tract: tract }} />);
    const toggle = screen.getByRole("button", { name: /Census Tract 2424/ });
    expect(toggle.textContent).toContain("ACS 2020–2024");
    fireEvent.click(toggle);
    expect(screen.getByText("8.9%")).toBeTruthy();
    expect(screen.getByText("5.0%")).toBeTruthy();
  });
});
