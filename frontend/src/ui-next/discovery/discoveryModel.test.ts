import { describe, expect, it } from "vitest";
import type { ResultRow } from "../../discovery/types";
import { shapePath } from "./discoveryData";
import {
  areaSuggestions, cardModel, foldComplexes, clampMiles, classifyQuery, measureColorExpr, measureSteps, milesBetween, placeRegion, placeSuggestions, quickFromPanel,
  quickPanel, ringMiles, ringPolygon, ringRegion,
} from "./discoveryModel";

const AREAS = { 22: "Logan Square", 24: "West Town", 7: "Lincoln Park" };

describe("quick filters compile to a panel the server evaluates", () => {
  it("adds and removes only their own predicates", () => {
    const panel = quickPanel(new Set(["vacant", "lot5k"]), { tif: { kind: "flag", value: true }, ward: { kind: "region", regions: ["ward:1"] } });
    expect(panel.vacancy).toEqual({ kind: "flag", value: true });
    expect(panel.lot_size).toEqual({ kind: "range", min: 5000 });
    expect(panel.ward).toBeDefined();
    // "In a TIF" was in the panel exactly; turning it off (not in the set) removes it.
    expect(panel.tif).toBeUndefined();
    expect([...quickFromPanel(panel)].sort()).toEqual(["lot5k", "vacant"]);
  });
  it("leaves a different predicate on the same filter alone", () => {
    const panel = quickPanel(new Set(), { lot_size: { kind: "range", min: 9000 } });
    expect(panel.lot_size).toEqual({ kind: "range", min: 9000 });
    expect(quickFromPanel(panel).has("lot5k")).toBe(false);
  });
});

describe("the map's measure", () => {
  it("has a key step per tile band and colors unknown as transparent (the hatch layer draws it)", () => {
    expect(measureSteps("room").map((s) => s.value)).toEqual(["0", "1", "2", "3", "4", "x", "p", "t"]);
    const expr = measureColorExpr("room") as unknown[];
    expect(expr.slice(0, 2)).toEqual(["match", ["get", "r"]]);
    expect(expr[expr.length - 1]).toBe("rgba(0,0,0,0)");
    expect((measureColorExpr("zoning", { residential: "#abc" }) as unknown[]).slice(2, 4)).toEqual(["residential", "#abc"]);
  });
});

describe("a card", () => {
  const row = (over: Partial<ResultRow>): ResultRow => ({
    pin: "14313250010000", lat: 41.9, lon: -87.7, address: "1601 N MILWAUKEE AVE", community_area: 24, land_use: "commercial",
    class: "5-17", lot_sqft: 11250, bldg_sqft: 14700, year_built: 1920, units: 4, assessed_value: 1, price_per_sf: null,
    last_sale_price: 1200000, last_sale_date: "2019-06-24", improvement_ratio: null, value_percentile: null,
    upside_score: null, is_teardown_candidate: false, sortValue: null, ...over,
  } as ResultRow);
  it("says a sale under $10,000 is a transfer, and names the complex and the building-area source", () => {
    expect(cardModel(row({ last_sale_price: 1 })).sale).toEqual({ price: 1, year: "2019", transfer: true });
    const c = cardModel(row({ room_sqft: 12000, room_scope: "complex", complex_lots: 3, bldg_sqft_source: "commercial_valuation" }));
    expect(c.complexLots).toBe(3);
    expect(c.roomBasis).toBe("commercial_valuation");
    expect(cardModel(row({ room_sqft: null, bldg_sqft_source: "footprint" })).roomBasis).toBeNull();
  });
  it("shows the server's one warning, else nominal", () => {
    expect(cardModel(row({ warning: { kind: "landmark", detail: "Wicker Park" } })).warning?.kind).toBe("landmark");
    expect(cardModel(row({ nominal_assessment: true })).warning?.kind).toBe("nominal");
  });
});

describe("the search box", () => {
  it("tells an address, a community area and a description apart", () => {
    expect(classifyQuery("1601 N Milwaukee Ave", AREAS)).toEqual({ kind: "address" });
    expect(classifyQuery("logan square", AREAS)).toEqual({ kind: "area", id: 22, name: "Logan Square" });
    expect(classifyQuery("vacant lots near the L", AREAS)).toEqual({ kind: "describe" });
  });
  it("suggests areas by a word's start", () => {
    expect(areaSuggestions("squ", AREAS).map((a) => a.name)).toEqual(["Logan Square"]);
    expect(areaSuggestions("1", AREAS)).toEqual([]);
  });
});

describe("the ring", () => {
  it("round-trips its region handle and draws a closed circle of the right size", () => {
    const region = ringRegion(41.9105, -87.6775, 0.5);
    expect(region).toBe("radius:41.910500,-87.677500,0.50");
    expect(ringMiles(region)).toBe(0.5);
    const ring = ringPolygon(41.9105, -87.6775, 0.5).coordinates[0];
    expect(ring[0]).toEqual(ring[ring.length - 1]);
    expect(milesBetween(41.9105, -87.6775, ring[0][1], ring[0][0])).toBeCloseTo(0.5, 2);
    expect(clampMiles(7)).toBe(2);
    expect(clampMiles(0.33)).toBe(0.35);
  });
});

describe("a lot's picture", () => {
  it("draws the outline to scale inside the box", () => {
    const d = shapePath({ type: "Polygon", coordinates: [[[-87.7, 41.9], [-87.6999, 41.9], [-87.6999, 41.9003], [-87.7, 41.9003], [-87.7, 41.9]]] }, 160, 72);
    expect(d).toMatch(/^M[\d.]+,[\d.]+L/);
    for (const n of d!.match(/[\d.]+/g)!.map(Number)) expect(n).toBeLessThanOrEqual(160);
  });
});

describe("places: the City's neighborhoods and its community areas", () => {
  const HOODS = [{ slug: "wicker_park", name: "Wicker Park" }, { slug: "logan_square", name: "Logan Square" }];
  it("suggests neighborhoods first, then community areas not already named that way", () => {
    expect(placeSuggestions("lo", AREAS, HOODS)).toEqual([{ kind: "hood", slug: "logan_square", name: "Logan Square" }]);
    expect(placeSuggestions("wic", AREAS, HOODS)).toEqual([{ kind: "hood", slug: "wicker_park", name: "Wicker Park" }]);
    expect(placeSuggestions("west", AREAS, HOODS)).toEqual([{ kind: "area", id: 24, name: "West Town" }]);
  });
  it("reads a typed neighborhood as a place, and gives each place its region handle", () => {
    expect(classifyQuery("wicker park", AREAS, HOODS)).toEqual({ kind: "hood", slug: "wicker_park", name: "Wicker Park" });
    expect(placeRegion({ kind: "hood", slug: "wicker_park", name: "Wicker Park" })).toBe("hood:wicker_park");
    expect(placeRegion({ kind: "area", id: 24, name: "West Town" })).toBe("neighborhood:24");
  });
});

describe("one card per complex", () => {
  it("folds the lots of one complex into the first, and leaves other lots alone", () => {
    const r = (pin: string, over: Partial<ResultRow>) => ({ pin, lat: 41.9, lon: -87.7, ...over } as ResultRow);
    const rows = [
      r("1", { room_scope: "complex", room_sqft: 9000, complex_lots: 3 }),
      r("2", { room_scope: "complex", room_sqft: 9000, complex_lots: 3, lat: 41.9005 }),
      r("3", { room_sqft: 9000 }),
      r("4", { room_scope: "complex", room_sqft: 9000, complex_lots: 3, lat: 41.95 }),  // another complex, far away
    ];
    expect(foldComplexes(rows).map((x) => [x.row.pin, x.more])).toEqual([["1", 1], ["3", 0], ["4", 0]]);
  });
});
