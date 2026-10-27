import { describe, expect, it } from "vitest";
import { buildDiscoveryMapModel } from "./discoveryMapModel";
import type { PinPoint } from "./types";

const point = (pin: string, lat: number | null, lon: number | null): PinPoint => ({
  pin,
  lat,
  lon,
  upside: null,
  landUse: null,
});

describe("buildDiscoveryMapModel", () => {
  it("separates valid points, returned points without coordinates, and cap omissions", () => {
    const model = buildDiscoveryMapModel([
      point("valid", 41.9, -87.7),
      point("missing", null, -87.6),
      point("nan", Number.NaN, -87.5),
      point("range", 95, -87.4),
    ], 9, true);

    expect(model.renderPoints.map((entry) => entry.pin)).toEqual(["valid"]);
    expect(model.returnedCount).toBe(4);
    expect(model.unlocatedCount).toBe(3);
    expect(model.omittedByCapCount).toBe(5);
  });

  it("does not label an unexplained non-truncated gap as a cap omission", () => {
    expect(buildDiscoveryMapModel([point("one", 41.9, -87.7)], 3, false).omittedByCapCount).toBe(0);
  });

  it("derives exact land-use key counts from the same points sent to Deck", () => {
    const values = [
      "vacant", "residential", "multi_family", "commercial", "industrial",
      "mixed_use", "institutional", "exempt", "unknown", null,
    ];
    const points = values.map((landUse, index) => ({
      ...point(String(index), 41.8 + index / 1000, -87.7),
      landUse,
    }));
    const model = buildDiscoveryMapModel(points, points.length, false, "land_use");
    const counts = Object.fromEntries(model.legendRows.map((row) => [row.key, row.count]));

    expect(model.renderPoints).toHaveLength(points.length);
    expect(counts).toMatchObject({
      "land_use:vacant": 1,
      "land_use:residential": 1,
      "land_use:multi_family": 1,
      "land_use:commercial": 1,
      "land_use:industrial": 1,
      "land_use:mixed_use": 1,
      "land_use:institutional": 1,
      "land_use:exempt": 1,
      "land_use:no_data": 2,
    });
    expect(model.legendRows.reduce((sum, row) => sum + row.count, 0)).toBe(model.renderPoints.length);
  });

  it("derives exact upside-bin counts from the Deck data", () => {
    const scores = [90, 80, 79, 50, 49, 0, null];
    const points = scores.map((upside, index) => ({
      ...point(String(index), 41.8 + index / 1000, -87.7),
      upside,
    }));
    const model = buildDiscoveryMapModel(points, points.length, false, "upside");
    const counts = Object.fromEntries(model.legendRows.map((row) => [row.key, row.count]));

    expect(counts).toEqual({
      "upside:high": 2,
      "upside:mid": 2,
      "upside:low": 2,
      "upside:no_data": 1,
    });
    expect(model.legendRows.reduce((sum, row) => sum + row.count, 0)).toBe(model.renderPoints.length);
  });
});
