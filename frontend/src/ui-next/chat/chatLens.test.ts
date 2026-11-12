import { describe, expect, it } from "vitest";
import type { MapData, RetrievalPlan } from "../../lib/types";
import { HALF_MILE_M, buildKind, chooseLens, crimeKind, distanceM, lensView, permitUnits, squareCounts } from "./chatLens";

const LOT = { latitude: 41.9278, longitude: -87.7105, label: "2541 N Spaulding Ave" };
const NOW = Date.parse("2026-11-12T12:00:00Z");
const near = (dLat: number) => LOT.latitude + dLat;

const map = (over: Partial<MapData> = {}): MapData => ({
  crimes: [
    { latitude: near(0.001), longitude: LOT.longitude, primary_type: "BATTERY", date: "2026-11-01", description: "", arrest: false },
    { latitude: near(0.002), longitude: LOT.longitude, primary_type: "THEFT", date: "2026-08-01", description: "", arrest: false },
    { latitude: near(0.03), longitude: LOT.longitude, primary_type: "THEFT", date: "2026-11-01", description: "", arrest: false },
  ],
  requests_311: [],
  building_permits: [
    { latitude: near(0.001), longitude: LOT.longitude, permit_type: "PERMIT - NEW CONSTRUCTION", work_description: "ERECT 3-STORY BUILDING WITH 6 DWELLING UNITS", estimated_cost: 1_200_000, issue_date: "2026-10-01" },
    { latitude: near(0.002), longitude: LOT.longitude, permit_type: "PERMIT – EXPRESS PERMIT PROGRAM", work_description: "ROOFTOP UNIT", estimated_cost: 60_000, issue_date: "2026-10-02" },
    { latitude: near(0.003), longitude: LOT.longitude, permit_type: "PERMIT - RENOVATION/ALTERATION", work_description: "GUT REHAB", estimated_cost: 800_000, issue_date: "2026-10-03" },
    { latitude: near(0.04), longitude: LOT.longitude, permit_type: "PERMIT - NEW CONSTRUCTION", work_description: "FAR AWAY", estimated_cost: 900_000, issue_date: "2026-10-04" },
  ],
  queried_address: LOT,
  ...over,
});
const plan = (intent: string, sources: string[]) => ({ intent, sources } as unknown as RetrievalPlan);

describe("which lens", () => {
  it("a question about a lot gets the lot, even when crime and permits came back", () => {
    expect(chooseLens({ mapData: map(), plan: plan("legal_question", ["zoning", "crime_api", "permits_api"]) })).toBe("lot");
  });
  it("an incident question gets its subject: crime first, then construction", () => {
    expect(chooseLens({ mapData: map(), plan: plan("incident_lookup", ["crime_api"]) })).toBe("safety");
    expect(chooseLens({ mapData: map(), plan: plan("event_query", ["permits_api"]) })).toBe("construction");
  });
  it("no address and no subject: the area summary; nothing to map: no lens", () => {
    expect(chooseLens({ mapData: map({ queried_address: null }), plan: plan("neighborhood_overview", ["311_api"]) })).toBe("area");
    expect(chooseLens({ mapData: undefined, plan: undefined })).toBeNull();
  });
});

describe("the safety lens", () => {
  it("counts within half a mile, splits violent from property, and pins only recent crimes a quarter mile away", () => {
    const v = lensView(map(), "safety", NOW);
    expect(v.radiusM).toBe(HALF_MILE_M);
    expect(v.counts).toMatchObject({ shown: 2, inArea: 3, violent: 1, property: 1, recentNear: 1 });
    expect(v.pins.features).toHaveLength(1);
    expect(v.squares!.features.reduce((n, f) => n + (f.properties as { n: number }).n, 0)).toBe(2);
  });
  it("shows no pins once there are too many to read", () => {
    const many = Array.from({ length: 60 }, () => ({ latitude: near(0.0005), longitude: LOT.longitude, primary_type: "THEFT", date: "2026-11-10", description: "", arrest: false }));
    expect(lensView(map({ crimes: many }), "safety", NOW).pins.features).toHaveLength(0);
  });
});

describe("the construction lens", () => {
  it("keeps new buildings, demolitions and big renovations within half a mile, nearest first", () => {
    const v = lensView(map(), "construction", NOW);
    expect(v.counts).toEqual({ shown: 2, inArea: 4 });
    expect(v.closest.map((c) => [c.kind, c.units])).toEqual([["new", 6], ["renovation", null]]);
  });
  it("classifies permits and reads units from their own words", () => {
    expect(buildKind({ permit_type: "PERMIT - WRECKING/DEMOLITION", estimated_cost: 0 })).toBe("demolition");
    expect(buildKind({ permit_type: "PERMIT - RENOVATION/ALTERATION", estimated_cost: 499_999 })).toBeNull();
    expect(permitUnits("NEW 4 RESIDENTIAL UNIT(S) BUILDING")).toBe(4);
    expect(permitUnits("ROOF")).toBeNull();
  });
});

describe("helpers", () => {
  it("measures distance and buckets points into squares", () => {
    expect(Math.round(distanceM(41.9, -87.7, 41.91, -87.7))).toBe(1112);
    const sq = squareCounts([{ latitude: 41.9, longitude: -87.7 }, { latitude: 41.9001, longitude: -87.7001 }]);
    expect(sq.features).toHaveLength(1);
    expect((sq.features[0].properties as { n: number }).n).toBe(2);
  });
  it("sorts crimes the way the Profile does", () => {
    expect(crimeKind({ primary_type: "ROBBERY" })).toBe("violent");
    expect(crimeKind({ primary_type: "DECEPTIVE PRACTICE" })).toBe("other");
  });
});
