// Street View's viewpoint (Item 94, owner's review): on the lot's own street, facing the lot, never the alley.
import { describe, expect, it } from "vitest";
import { MAX_SNAP_METERS, bearing, streetOfAddress, viewpointFor, type RoadLine } from "./streetView";

// A lot between Milwaukee Ave (west, its address street) and an unnamed alley (east, nearer).
const LOT: [number, number] = [-87.67700, 41.91000];
const roads: RoadLine[] = [
  { name: "N Milwaukee Ave", kind: "minor", lines: [[[-87.67760, 41.90900], [-87.67760, 41.91100]]] },   // ~50 m west
  { name: "N Damen Ave", kind: "minor", lines: [[[-87.67660, 41.90900], [-87.67660, 41.91100]]] },       // ~33 m east
  { name: "", kind: "local", lines: [[[-87.67690, 41.90900], [-87.67690, 41.91100]]] },                   // alley-like, unnamed
];

describe("streetOfAddress", () => {
  it("keeps the street and drops the number and unit", () => {
    expect(streetOfAddress("1530 N Milwaukee Ave")).toBe("n milwaukee ave");
    expect(streetOfAddress("1530-32 N MILWAUKEE AVE Unit 2")).toBe("n milwaukee ave");
    expect(streetOfAddress("~2029 W Pierce Ave")).toBe("w pierce ave");
    expect(streetOfAddress(null)).toBeNull();
  });
});

describe("viewpointFor", () => {
  it("stands on the lot's own address street, facing the lot, even when another street is nearer", () => {
    const v = viewpointFor(LOT, roads, "n milwaukee ave");
    expect(v.lon).toBeCloseTo(-87.67760, 5);
    expect(v.lat).toBeCloseTo(41.91000, 5);
    expect(v.heading).toBe(90); // facing east, toward the lot
  });

  it("without an address, the nearest named street (never an unnamed line), facing the point", () => {
    const v = viewpointFor(LOT, roads, null);
    expect(v.lon).toBeCloseTo(-87.67660, 5);
    expect(v.heading).toBe(270);
  });

  it("sends the point itself when no street is near", () => {
    const far: [number, number] = [-87.60000, 41.91000];
    expect(viewpointFor(far, roads, null)).toEqual({ lat: 41.91, lon: -87.6 });
    expect(MAX_SNAP_METERS).toBeLessThan(100);
  });

  it("bearing is a compass bearing", () => {
    expect(Math.round(bearing([0, 0], [0, 1]))).toBe(0);
    expect(Math.round(bearing([0, 0], [1, 0]))).toBe(90);
  });
});
