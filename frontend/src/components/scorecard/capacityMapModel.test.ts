import { describe, expect, it } from "vitest";
import { binOf, buildCapacityMapModel, type CapacityFeatureProps, type CapacityMapResponse } from "./capacityMapModel";

const square: GeoJSON.Polygon = { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] };

function feat(over: Partial<CapacityFeatureProps>): GeoJSON.Feature<GeoJSON.Geometry, CapacityFeatureProps> {
  return {
    type: "Feature",
    geometry: square,
    properties: {
      pin10: "17-09-100-001", pin: "17-09-100-001-0000", state: "computable", existing_far: 0.6, allowed_far: 1.2,
      utilization: 0.5, zone_class: "RT-4", confidence: "standard", reason: null, ...over,
    },
  };
}

function resp(features: GeoJSON.Feature<GeoJSON.Geometry, CapacityFeatureProps>[], verdict: CapacityMapResponse["summary"]["verdict"] = "standard"): CapacityMapResponse {
  return {
    radius_mi: 0.1,
    features: { type: "FeatureCollection", features },
    summary: { polygons: features.length, colorable: features.filter((f) => f.properties.state === "computable").length, colorable_share: 0, verdict, states: {} },
    unchecked: [],
  };
}

describe("capacityMapModel", () => {
  it("bins at the edges", () => {
    expect(binOf(0)).toBe("under25");
    expect(binOf(0.2499)).toBe("under25");
    expect(binOf(0.25)).toBe("25to50");
    expect(binOf(0.5)).toBe("50to80");
    expect(binOf(0.8)).toBe("over80");
    expect(binOf(2.5)).toBe("over80");
  });

  it("every polygon is drawn and counted exactly once in the key", () => {
    const m = buildCapacityMapModel(resp([
      feat({ utilization: 0.1 }), feat({ utilization: 0.9 }), feat({ utilization: 0.6 }),
      feat({ state: "unknown_gfa", utilization: null }), feat({ state: "multi_pin_member", utilization: null }),
      feat({ state: "apparently_overbuilt", utilization: null }),
    ]), "light");
    expect(m.drawn).toHaveLength(6);
    const keyed = [...m.bins, ...m.uncolored].reduce((n, r) => n + r.count, 0);
    expect(keyed).toBe(m.total);
    expect(m.colored).toBe(3);
    expect(m.bins.map((r) => [r.key, r.count])).toEqual([["under25", 1], ["25to50", 0], ["50to80", 1], ["over80", 1]]);
  });

  it("unknown building area is never colored as low", () => {
    const m = buildCapacityMapModel(resp([feat({ state: "unknown_gfa", utilization: null })]), "dark");
    expect(m.drawn[0].bin).toBeNull();
    expect(m.bins.every((r) => r.count === 0)).toBe(true);
    expect(m.uncolored).toEqual([expect.objectContaining({ key: "unknown_gfa", count: 1 })]);
  });

  it("overbuilt is flagged with an outline, never binned", () => {
    const m = buildCapacityMapModel(resp([feat({ state: "apparently_overbuilt", utilization: null })]), "light");
    expect(m.drawn[0].bin).toBeNull();
    expect(m.uncolored[0].outlineCSS).toBeTruthy();
    expect(m.drawn[0].line).not.toEqual(buildCapacityMapModel(resp([feat({ state: "exempt", utilization: null })]), "light").drawn[0].line);
  });

  it("low confidence halves the fill and dashes the outline", () => {
    const std = buildCapacityMapModel(resp([feat({})]), "light").drawn[0];
    const low = buildCapacityMapModel(resp([feat({ confidence: "low" })]), "light").drawn[0];
    expect(low.dashed).toBe(true);
    expect(low.fill[3]).toBe(Math.round(std.fill[3] / 2));
  });

  it("a withheld view draws no bins even if a utilization slipped through", () => {
    const m = buildCapacityMapModel(resp([feat({ utilization: 0.4 }), feat({ state: "exempt", utilization: null })], "withheld"), "light");
    expect(m.binsDrawn).toBe(false);
    expect(m.bins).toEqual([]);
    expect(m.drawn.every((d) => d.bin === null)).toBe(true);
    expect(m.uncolored.map((r) => r.key)).toContain("computable");
    expect(m.uncolored.reduce((n, r) => n + r.count, 0)).toBe(2);
  });

  it("the subject is found and colors differ by theme", () => {
    const m = buildCapacityMapModel(resp([feat({ subject: true })]), "light");
    expect(m.subject?.feature.properties.subject).toBe(true);
    expect(buildCapacityMapModel(resp([feat({})]), "dark").drawn[0].fill).not.toEqual(m.drawn[0].fill);
  });

  it("no response is an unavailable, empty model", () => {
    const m = buildCapacityMapModel(null, "light");
    expect(m.total).toBe(0);
    expect(m.verdict).toBe("unavailable");
  });
});
