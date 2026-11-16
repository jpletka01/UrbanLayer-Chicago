// The list card says "Empty lot" from what stands on the lot (decision Item 110), not the Assessor's tax class.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { ResultRow } from "../../discovery/types";
import { LotCard } from "./LotCard";

const base = {
  pin: "16-25-300-030-0000", lat: 41.84, lon: -87.7, address: "2626 S TROY ST", lot_sqft: 3125, bldg_sqft: null,
  year_built: null, zone_class: "RS-3", allowed_far: 0.9, room_sqft: 2812,
} as unknown as ResultRow;

afterEach(cleanup);

describe("LotCard: empty land", () => {
  it("names a City-owned empty lot, though its tax class isn't vacant", () => {
    render(<LotCard row={{ ...base, land_use: "exempt", empty_land: true, land_kind: "city_owned" } as ResultRow} hoodName={null} onOpen={() => {}} />);
    expect(screen.getByText(/Empty lot, City-owned/)).toBeTruthy();
  });

  it("doesn't call a vacant-class lot empty when a building stands on it, and shows that building", () => {
    render(<LotCard row={{ ...base, land_use: "vacant", empty_land: false, land_kind: "vacant", bldg_sqft: 1800, year_built: 1924 } as ResultRow}
      hoodName={null} onOpen={() => {}} />);
    expect(screen.queryByText(/Empty lot/)).toBeNull();
    expect(screen.getByText(/1924/)).toBeTruthy();
  });

  it("says when the empty lot has a garage or shed", () => {
    render(<LotCard row={{ ...base, land_use: "vacant", empty_land: true, land_kind: "vacant", structure: "accessory" } as ResultRow}
      hoodName={null} onOpen={() => {}} />);
    expect(screen.getByText(/Empty lot, garage or shed only/)).toBeTruthy();
  });

  it("falls back to the tax class on an index built before the measurement", () => {
    render(<LotCard row={{ ...base, land_use: "vacant" } as ResultRow} hoodName={null} onOpen={() => {}} />);
    expect(screen.getByText(/Empty lot/)).toBeTruthy();
  });

  it("names a parking lot with no building as surface parking (Item 112)", () => {
    render(<LotCard row={{ ...base, land_use: "commercial", empty_land: true, land_kind: "parking", surface_parking: true } as ResultRow}
      hoodName={null} onOpen={() => {}} />);
    expect(screen.getByText(/Surface parking lot/)).toBeTruthy();
    expect(screen.queryByText(/Empty lot or parking/)).toBeNull();
  });

  it("keeps the old words for a parking-class lot an index marked before Item 112", () => {
    render(<LotCard row={{ ...base, land_use: "commercial", empty_land: true, land_kind: "parking" } as ResultRow}
      hoodName={null} onOpen={() => {}} />);
    expect(screen.getByText(/Empty lot or parking/)).toBeTruthy();
  });
});
