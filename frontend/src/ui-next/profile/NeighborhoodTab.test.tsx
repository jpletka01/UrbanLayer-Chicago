// The Neighborhood tab (decision Item 102), rendered from a typed fixture with no network, with axe checks.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import i18n from "../../lib/i18n";
import { profileFixture } from "../test/fixtures";
import { axeViolations } from "../test/axe";
import { NeighborhoodTab } from "./NeighborhoodTab";
import { crimeModel, permitWords, sourceState } from "./neighborhoodModel";
import type { ScorecardResponse } from "../../lib/api";

afterEach(async () => { cleanup(); await i18n.changeLanguage("en"); });

const NEXT_UI = {
  crime: { window_days: 90, current: { violent: 50, property: 120, other: 9 }, prior: { violent: 60, property: 100, other: 4 }, current_label: "Aug–Nov 2026", prior_label: "Aug–Nov 2025" },
  area_311: { days: 365, total: 3000, top: [{ type: "Graffiti Removal Request", count: 700 }, { type: "Pothole in Street Complaint", count: 100 }] },
  schools: {
    boundary_year: "2025-26", report_year: 2025,
    elementary: { school_id: "610229", level: "elementary", name: "A.N. Pritzker School", grades: "PK - 8", address: null, cps_url: "https://www.cps.edu/schools/schoolprofiles/610229", report_card_url: "https://www.illinoisreportcard.com/school.aspx?source=profile&Schoolid=150162990252510", report_card: { year: 2025, designation: "Commendable", enrollment: 673, ela_pct: 78.4, math_pct: 67 } },
    high: null,
  },
  construction_within: {
    radius_mi: 0.5, months: 24, renovation_cost_floor: 250000, capped: false,
    projects: [
      { permit: "101", kind: "new", description: "ERECT 4-STORY 8-UNIT BUILDING", issued: "2026-05-01", cost: 2400000, units_added: 8, address: "1700 N Milwaukee Ave", lat: 41.911, lon: -87.678, distance_mi: 0.1 },
      { permit: "102", kind: "renovation", description: "SELF CERTIFICATION 2019 CBRC -- GUT REHAB", issued: "2025-12-01", cost: 300000, units_added: null, address: "1550 N Damen Ave", lat: 41.909, lon: -87.677, distance_mi: 0.2 },
    ],
  },
};

function data(over: Record<string, unknown> = {}): ScorecardResponse {
  return profileFixture({
    next_ui: NEXT_UI,
    context: { neighborhood: {
      demographics: { community_area: 24, community_area_name: "West Town", population: 50000, median_household_income: 90000 },
      census_tract: { tract_fips: "17031243000", tract_name: "Census Tract 2430", census_reporter_url: null, median_household_income: 110000, owner_occupied_pct: 41.2, bachelors_or_higher_pct: 70.1, poverty_rate: 8.3, median_age: 33, acs_period: "2020–2024",
        race_distribution: [{ label: "RACE-SHOULD-NOT-SHOW", value: 50 }] },
    } },
    ...over,
  } as never);
}

const ready = { neighborhood: "ready", activity: "ready" } as const;

describe("Neighborhood", () => {
  it("leads with the sentence, then score and crime tiles, construction, safety, 311, people and schools", async () => {
    const { container } = render(<div className="ui-next"><NeighborhoodTab data={data()} late={ready} timedOutActivity={[]} onRetry={vi.fn()} /></div>);
    expect(screen.getByTestId("nb-sentence").textContent).toMatch(/^Walk score 99 \(Walker's Paradise\); 2 permits .*; violent crime in the area down 17% from a year ago\.$/);
    const tiles = within(screen.getByTestId("nb-tiles")).getAllByRole("listitem");
    expect(tiles).toHaveLength(4);
    expect(screen.getByTestId("tile-violent").textContent).toContain("1.0per 1,000"); // 50 of 50,000 residents
    expect(screen.getByTestId("nb-building-counts").textContent).toBe("1 new building · 1 major renovation · adds 8 homes");
    expect(screen.getByText("Gut rehab")).toBeTruthy(); // the City's boilerplate dropped
    expect(screen.getByTestId("nb-school-elementary").textContent).toContain("Commendable");
    expect(screen.getByText(/No CPS high school attendance boundary/)).toBeTruthy();
    expect(screen.getByTestId("nb-311-bars").textContent).toContain("Graffiti Removal Request");
    expect(container.textContent).not.toContain("RACE-SHOULD-NOT-SHOW"); // race and ethnicity left out (owner)
    for (const a of container.querySelectorAll("a[href]")) expect(a.getAttribute("target")).toBe("_blank");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("keeps each late block's outline while activity waits, and says Retry in place when it ran out of time", () => {
    const onRetry = vi.fn();
    const { rerender } = render(<div className="ui-next"><NeighborhoodTab data={data({ next_ui: undefined })} late={{ neighborhood: "ready", activity: "loading" }} timedOutActivity={[]} onRetry={onRetry} /></div>);
    expect(screen.getByText("Checking building permits…")).toBeTruthy();
    expect(screen.getByText("Checking schools…")).toBeTruthy();
    rerender(<div className="ui-next"><NeighborhoodTab data={data({ next_ui: { ...NEXT_UI, schools: undefined } })} late={{ neighborhood: "ready", activity: "timedOut" }} timedOutActivity={["schools"]} onRetry={onRetry} /></div>);
    const retry = screen.getByText(/Couldn.t check in time: schools/).closest("p")!;
    fireEvent.click(within(retry).getByRole("button"));
    expect(onRetry).toHaveBeenCalledWith("activity");
    expect(screen.getByTestId("nb-building-counts")).toBeTruthy(); // the other blocks still show
  });

  it("names a failed source as failed, never as none", () => {
    render(<div className="ui-next"><NeighborhoodTab data={data({ next_ui: { ...NEXT_UI, area_311: undefined, failed: ["area_311"] } })} late={ready} timedOutActivity={[]} onRetry={vi.fn()} /></div>);
    expect(screen.getByText(/Couldn.t load: 311 requests/)).toBeTruthy();
    expect(screen.queryByText(/No 311 requests/)).toBeNull();
  });

  it("renders in Spanish (usted) with the jump links", async () => {
    await i18n.changeLanguage("es");
    render(<div className="ui-next"><NeighborhoodTab data={data()} late={ready} timedOutActivity={[]} onRetry={vi.fn()} /></div>);
    const jump = screen.getByTestId("nb-jump").textContent ?? "";
    expect(jump).toContain("Seguridad");
    expect(jump).toContain("Escuelas");
    expect(screen.getByTestId("nb-building-counts").textContent).toContain("edificio nuevo");
    expect(screen.getByTestId("nb-school-elementary").textContent).toContain("Encomiable");
  });
});

describe("neighborhoodModel", () => {
  it("rates crime per 1,000 community-area residents and the change from a year earlier", () => {
    const c = crimeModel(data())!;
    expect(c.violentPer1k).toBe(1);
    expect(c.propertyPer1k).toBe(2.4);
    expect(c.violentChange).toBe(-17);
    expect(c.propertyChange).toBe(20);
  });

  it("gives no rate without a population and no change without a prior count", () => {
    const d = data({ next_ui: { crime: { window_days: 90, current: { violent: 5, property: 0, other: 0 }, prior: null } } });
    d.context.neighborhood!.demographics = null;
    const c = crimeModel(d)!;
    expect(c.violentPer1k).toBeNull();
    expect(c.violentChange).toBeNull();
  });

  it("reads a block's state from its part and its own source", () => {
    const d = data({ next_ui: { ...NEXT_UI, failed: ["schools"], schools: undefined } });
    expect(sourceState(d, "loading", "schools", [])).toBe("loading");
    expect(sourceState(d, "ready", "schools", [])).toBe("failed");
    expect(sourceState(d, "ready", "area_311", ["area_311"])).toBe("timedOut");
    expect(sourceState(d, "ready", "construction_within", [])).toBe("ready");
  });

  it("words a permit without the City's boilerplate", () => {
    expect(permitWords("STANDARD PLAN REVIEW 2019 CBC - ERECT A 3-STORY BUILDING")).toBe("Erect a 3-story building");
    expect(permitWords("Self -cert 2019 cbc: erect a 3 story building")).toBe("Erect a 3 story building");
    expect(permitWords("SC 2019 CBRC. ERECT A 4 STORY BUILDING")).toBe("Erect a 4 story building");
    expect(permitWords("SELF CERTIFICATION 2019 CBRC -- INTERIOR BUILD OUT")).toBe("Interior build out");
    expect(permitWords("Spr 2019 cbrc: interior alteration")).toBe("Interior alteration");
    expect(permitWords("2019 cbrcinterior alterations")).toBe("Interior alterations");
    expect(permitWords("SCAFFOLD AND MASONRY REPAIR")).toBe("Scaffold and masonry repair");
    expect(permitWords(null)).toBeNull();
  });
});
