// The Neighborhood tab (decision Item 102), rendered from a typed fixture with no network, with axe checks.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import i18n from "../../lib/i18n";
import { profileFixture } from "../test/fixtures";
import { axeViolations } from "../test/axe";
import { NeighborhoodTab } from "./NeighborhoodTab";
import { crimeModel, permitQuarters, permitWords, sourceState } from "./neighborhoodModel";
import { PermitPanel } from "./PermitPanel";
import { AskContext } from "../ask/askContext";
import type { ScorecardResponse } from "../../lib/api";

afterEach(async () => { cleanup(); await i18n.changeLanguage("en"); });

const TRACT = {
  tract: { median_age: 33, housing_units: 1269, households: 1172, persons_per_household: 2.07, travel_minutes: 30.9, moved_pct: 22.3, occupied_pct: 92.4, per_capita_income: 142484, median_household_income: 110000, median_home_value: 961200 },
  city: null,
  structure: [{ key: "single_family", pct: 33, low: true }, { key: "two", pct: 10, low: false }, { key: "three_four", pct: 17, low: false }, { key: "five_19", pct: 10, low: false }, { key: "twenty_plus", pct: 29, low: false }, { key: "other", pct: 1, low: false }],
  tenure: [{ key: "owner", pct: 30, low: false }, { key: "renter", pct: 70, low: false }],
  occupancy: [{ key: "occupied", pct: 92, low: false }, { key: "vacant", pct: 8, low: false }],
  moved_in: [{ key: "2020 to 2022", pct: 40, low: false }], home_value: null,
  household_type: [{ key: "married", pct: 47, low: false }, { key: "other_family", pct: 3, low: false }, { key: "alone", pct: 31, low: false }, { key: "roommates", pct: 19, low: false }],
  mobility: null, travel_time: null, income: [{ key: "under_50k", pct: 10, low: false }, { key: "over_200k", pct: 53, low: false }],
};

const NEXT_UI = {
  tract: TRACT,
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
        race_distribution: [{ label: "RACE-SHOULD-NOT-SHOW", value: 50 }],
        transportation_distribution: [{ label: "Drove alone", value: 30 }, { label: "Public transit", value: 20 }] },
      transit: { nearest_cta_rail: "Damen (Blue)", cta_rail_distance_mi: 0.07, cta_lines: ["Blue Line"], nearest_metra: null, metra_distance_mi: null, metra_line: null, tod_eligible: true, tod_type: "CTA rail" },
      ward: { ward: 32, alderman: "Doe, Pat", phone: "(773) 555-0100", email: "ward@example.org", website: "https://example.org" },
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
    expect(screen.getByTestId("nb-building-counts").textContent).toContain("1new building");
    expect(screen.getByTestId("nb-building-counts").textContent).toContain("8homes added");
    expect(screen.getByTestId("ring-walk").getAttribute("data-share")).toBe("0.99");
    expect(screen.getByRole("img", { name: "Walk score: 99 of 100" })).toBeTruthy();
    expect(screen.getByText("Gut rehab")).toBeTruthy(); // the City's boilerplate dropped
    expect(screen.getByTestId("nb-school-elementary").textContent).toContain("Commendable");
    expect(screen.getByText(/No CPS high school attendance boundary/)).toBeTruthy();
    expect(screen.getByTestId("nb-311-bars").textContent).toContain("Graffiti Removal Request");
    expect(container.textContent).not.toContain("RACE-SHOULD-NOT-SHOW"); // race and ethnicity left out (owner)
    expect(screen.getByTestId("nb-commute-cols").textContent).toContain("Public transit");
    expect(screen.getByTestId("nb-ratio-badge").textContent).toBe("1.2× West Town");
    expect(screen.getByTestId("nb-income-headline").textContent).toContain("West Town: $90,000");
    expect(screen.getByTestId("nb-violent-badge").textContent).toBe("17% vs a year ago");
    expect(screen.getByTestId("nb-violent-badge").querySelector("[data-pill]")!.getAttribute("data-pill")).toBe("green"); // down is good
    expect(screen.getByTestId("nb-rating-elementary").textContent).toContain("Commendable");
    expect(screen.getByTestId("nb-donut-tenure").textContent).toContain("Renter occupied");
    expect(screen.getByTestId("nb-structure-cols").textContent).toContain("3–4 units");
    // "Low confidence" defines itself on hover or tap, in place of a note far below
    const low = within(screen.getByTestId("nb-structure-cols")).getByRole("button", { name: "What does Low confidence mean?" });
    fireEvent.click(low);
    expect(screen.getByText(/margin is at least 10% of the figure/)).toBeTruthy();
    expect(screen.getByTestId("nb-311-donut").textContent).toContain("Graffiti Removal Request");
    expect(screen.getByTestId("nb-311-donut").textContent).toContain("700 · 23%"); // count and share
    const commute = within(screen.getByTestId("nb-commute-cols")).getAllByRole("listitem", { hidden: true }).map((li) => li.textContent);
    expect(commute[0]).toContain("Drove alone"); // highest first
    const cards = within(screen.getByTestId("nb-nearby")).getAllByRole("listitem").map((li) => li.getAttribute("data-card"));
    expect(cards).toEqual(["cta", "ward", "area"]);
    // Pages open in a new tab; mailto and tel open another app (the repo's link rule).
    for (const a of container.querySelectorAll('a[href]:not([href^="mailto:"]):not([href^="tel:"])')) expect(a.getAttribute("target")).toBe("_blank");
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


describe("Construction nearby", () => {
  const many = Array.from({ length: 8 }, (_, i) => ({
    permit: String(200 + i), kind: i % 2 ? "renovation" : "new", description: `PROJECT ${i}`, issued: `2026-0${(i % 9) + 1}-01`, cost: 100000 * (i + 1),
    units_added: i % 2 ? null : 2, address: `${100 + i} N Damen Ave`, lat: 41.91, lon: -87.67, distance_mi: 0.1 * (8 - i),
  }));
  const withMany = () => data({ next_ui: { ...NEXT_UI, construction_within: { ...NEXT_UI.construction_within, projects: many } } });

  it("filters, sorts, expands in place, and opens a permit's page", () => {
    const openPermit = vi.fn();
    render(<AskContext.Provider value={{ ready: true, address: "1601 N Milwaukee Ave", open: vi.fn(), openPermit }}><div className="ui-next"><NeighborhoodTab data={withMany()} late={ready} timedOutActivity={[]} onRetry={vi.fn()} /></div></AskContext.Provider>);
    const list = () => within(screen.getByTestId("nb-projects")).getAllByRole("listitem");
    expect(list()).toHaveLength(5);
    fireEvent.click(screen.getByTestId("nb-projects-more"));
    expect(list()).toHaveLength(8);
    fireEvent.click(within(screen.getByTestId("nb-building-filter")).getByRole("radio", { name: /Renovations 4/ }));
    expect(list().every((li) => li.getAttribute("data-kind") === "renovation")).toBe(true);
    fireEvent.change(screen.getByTestId("nb-building-sort"), { target: { value: "closest" } });
    expect(list()[0].textContent).toContain("107 N Damen Ave");
    fireEvent.click(within(list()[0]).getByRole("button"));
    expect(openPermit).toHaveBeenCalledWith(expect.objectContaining({ permit: "207" }));
    expect(screen.getByTestId("nb-permit-quarters")).toBeTruthy();
  });
});

describe("Permit page", () => {
  it("shows what is built, its stage, its facts and the City's records", async () => {
    const onShow = vi.fn();
    const permit = { ...NEXT_UI.construction_within.projects[0], status: "ACTIVE", milestone: "INSPECTIONS (CERTIFICATE OF OCCUPANCY REQUIRED)", applied: "2025-10-08", processing_days: 237, review_type: "STANDARD PLAN REVIEW" } as never;
    const { container } = render(<div className="ui-next"><PermitPanel permit={permit} onClose={vi.fn()} onShowOnMap={onShow} /></div>);
    expect(screen.getByTestId("permit-description").textContent).toBe("Erect 4-story 8-unit building");
    const current = screen.getByTestId("permit-stages").querySelector('[aria-current="step"]')!;
    expect(current.textContent).toContain("Inspections");
    expect(current.textContent).toContain("certificate of occupancy");
    expect(screen.getByText("237 days")).toBeTruthy();
    fireEvent.click(screen.getByTestId("permit-show-map"));
    expect(onShow).toHaveBeenCalled();
    for (const a of container.querySelectorAll("a[href]")) expect(a.getAttribute("target")).toBe("_blank");
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("permitQuarters", () => {
  it("counts each quarter by kind, keeping empty quarters after the first permit", () => {
    const q = permitQuarters([
      { kind: "new", issued: "2026-01-15" }, { kind: "renovation", issued: "2026-02-01" }, { kind: "new", issued: "2026-07-01" },
    ] as never, 24, new Date("2026-11-10T12:00:00"));
    expect(q.map((x) => [x.key, x.newCount, x.renoCount])).toEqual([["2026Q1", 1, 1], ["2026Q2", 0, 0], ["2026Q3", 1, 0], ["2026Q4", 0, 0]]);
  });
});
