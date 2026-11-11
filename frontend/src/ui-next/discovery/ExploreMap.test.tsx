// Discovery's lot card opens Street View on the lot's own address street, facing the lot, not in the alley behind it
// (Item 94 on the Profile map; Item 107 here). jsdom has no WebGL, so the card is rendered on its own.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import type { DiscoveryOutlineLookup } from "../../lib/api";
import type { RoadLine } from "../map/streetView";
import { LotCard, type Picked } from "./ExploreMap";

vi.mock("maplibre-gl", () => ({ setWorkerUrl: () => {} }));
vi.mock("maplibre-gl/dist/maplibre-gl-worker.mjs?url", () => ({ default: "" }));

// The click lands in the lot's middle: ~10 m from the alley behind it (east), ~50 m from its address street (west).
const CLICK: [number, number] = [-87.67700, 41.91000];
const roads: RoadLine[] = [
  { name: "N Milwaukee Ave", kind: "minor", lines: [[[-87.67760, 41.90900], [-87.67760, 41.91100]]] },
  { name: "", kind: "local", lines: [[[-87.67688, 41.90900], [-87.67688, 41.91100]]] },                  // the alley
  { name: "N Damen Ave", kind: "minor", lines: [[[-87.67660, 41.90900], [-87.67660, 41.91100]]] },
];

const found = (address: string | null): DiscoveryOutlineLookup => ({
  status: "found",
  row: { pin: "14313250010000", lat: 41.91, lon: -87.677, address, zone_class: "B3-2", lot_sqft: 3125, room_sqft: 2000 } as never,
});

function card(lookup: DiscoveryOutlineLookup | null) {
  const picked: Picked = { pin10: "1431325001", at: [100, 100], size: [600, 400], ll: CLICK, roads, lookup };
  render(<MemoryRouter><LotCard picked={picked} onClose={() => {}} /></MemoryRouter>);
  return new URL(screen.getByTestId("lot-card-street-view").getAttribute("href")!);
}

afterEach(cleanup);

describe("Discovery lot card: Street View", () => {
  it("stands on the address street facing the lot, though the lot's middle is nearer the alley", () => {
    const url = card(found("1601 N MILWAUKEE AVE"));
    const [lat, lon] = url.searchParams.get("viewpoint")!.split(",").map(Number);
    expect(lon).toBeCloseTo(-87.67760, 5);
    expect(lat).toBeCloseTo(41.91000, 5);
    expect(url.searchParams.get("heading")).toBe("90"); // facing east, at the lot
  });

  it("without an address, the nearest named street, never the unnamed alley", () => {
    const url = card(found(null));
    const [, lon] = url.searchParams.get("viewpoint")!.split(",").map(Number);
    expect(lon).toBeCloseTo(-87.67660, 5);
    expect(url.searchParams.get("heading")).toBe("270");
  });
});
