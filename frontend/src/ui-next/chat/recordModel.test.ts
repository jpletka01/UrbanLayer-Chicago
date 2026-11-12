import { describe, expect, it } from "vitest";
import type { MapData } from "../../lib/types";
import { constructionRecord, crimeRecord, factTiles, requestsRecord } from "./recordModel";

const LOT = { latitude: 41.9278, longitude: -87.7105, label: "2541 N Spaulding Ave" };
const at = (dLat: number) => ({ latitude: LOT.latitude + dLat, longitude: LOT.longitude });
const MAP: MapData = {
  crimes: [
    { ...at(0.001), primary_type: "THEFT", date: "2026-11-01", description: "", arrest: false },
    { ...at(0.002), primary_type: "THEFT", date: "2026-11-02", description: "", arrest: false },
    { ...at(0.002), primary_type: "BATTERY", date: "2026-11-03", description: "", arrest: true },
    { ...at(0.05), primary_type: "ROBBERY", date: "2026-11-03", description: "", arrest: false },
  ],
  requests_311: [
    { ...at(0.001), sr_type: "Graffiti Removal Request", status: "Completed", created_date: "", owner_department: "" },
    { ...at(0.001), sr_type: "Graffiti Removal Request", status: "Open", created_date: "", owner_department: "" },
    { ...at(0.002), sr_type: "Street Light Out Complaint", status: "Open", created_date: "", owner_department: "" },
  ],
  building_permits: [
    { ...at(0.003), permit_type: "PERMIT - NEW CONSTRUCTION", work_description: "6 DWELLING UNITS", estimated_cost: 1_200_000, issue_date: "2026-10-01" },
    { ...at(0.001), permit_type: "PERMIT – EXPRESS PERMIT PROGRAM", work_description: "ROOF", estimated_cost: 5_000, issue_date: "2026-10-01" },
  ],
  queried_address: LOT,
};

describe("crime near the lot", () => {
  it("counts within half a mile, splits violent from property, counts arrests", () => {
    const r = crimeRecord({ crime_last_90d: { total: 386, arrest_rate: 0.1, by_type: {} } } as never, MAP)!;
    expect(r).toMatchObject({ scope: "near", total: 3, violent: 1, property: 2, arrests: 1, areaTotal: 386 });
    expect(r.byType.map((t) => `${t.type}:${t.n}:${t.kind}`)).toEqual(["THEFT:2:property", "BATTERY:1:violent"]);
  });
  it("falls back to the community area when the address has no point", () => {
    const r = crimeRecord({ crime_last_90d: { total: 10, arrest_rate: 0, by_type: { THEFT: 7, ASSAULT: 3 } } } as never, { ...MAP, queried_address: null, crimes: [] })!;
    expect(r).toMatchObject({ scope: "area", total: 10, violent: 3, property: 7, arrests: null });
  });
});

describe("building nearby", () => {
  it("keeps the big projects near the lot and counts the small ones left out", () => {
    const r = constructionRecord(MAP)!;
    expect(r.cards.map((c) => [c.kind, c.units])).toEqual([["new", 6]]);
    expect(r.leftOut).toBe(1);
  });
});

describe("311 requests", () => {
  it("groups by type with the open ones counted apart", () => {
    expect(requestsRecord(undefined, MAP)!.rows).toEqual([
      { type: "Graffiti Removal Request", n: 2, open: 1 },
      { type: "Street Light Out Complaint", n: 1, open: 1 },
    ]);
  });
});

describe("the lot's facts", () => {
  it("shows only what the record has, and a sale only when it was a market sale", () => {
    const tiles = factTiles({ land_sqft: 3125, units: 2, bldg_sqft: 2400, estimated_annual_tax: 12478, tax_year: 2024,
      sales_history: [{ date: "2019-05-01", price: 612000, deed_type: "W", arms_length: true }, { date: "2021-01-01", price: 1, deed_type: "Q", arms_length: false }] } as never);
    expect(tiles.map((t) => [t.key, t.value])).toEqual([["lot", 3125], ["building", 2], ["tax", 12478], ["sale", 612000]]);
    expect(factTiles({ estimated_annual_tax: 9000, tax_exempt: true, sales_history: [] } as never)).toEqual([]);
  });
});
