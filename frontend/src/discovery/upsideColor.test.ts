import { describe, expect, it } from "vitest";
import {
  landUseColor,
  landUseLegendKey,
  LAND_USE_LEGEND,
  RENDERABLE_LAND_USES,
  upsideColor,
  UPSIDE_LEGEND,
} from "./upsideColor";

describe("upsideColor", () => {
  it("maps null/undefined to a DISTINCT no-data swatch, not the low-upside end", () => {
    const noData = upsideColor(null);
    expect(noData).toEqual(upsideColor(undefined));
    // Must differ from every scored bucket — pre-index this is ~every parcel, and it must
    // never read as "low opportunity".
    expect(noData).not.toEqual(upsideColor(0));
    expect(noData).not.toEqual(upsideColor(49));
    expect(noData).not.toEqual(upsideColor(90));
  });

  it("ramps high/mid/low by score", () => {
    expect(upsideColor(90)).toEqual(upsideColor(80)); // high bucket
    expect(upsideColor(60)).toEqual(upsideColor(50)); // mid bucket
    expect(upsideColor(10)).toEqual(upsideColor(49)); // low bucket
    expect(upsideColor(80)).not.toEqual(upsideColor(79));
    expect(upsideColor(50)).not.toEqual(upsideColor(49));
  });

  it("legend includes the no-data swatch", () => {
    expect(UPSIDE_LEGEND.map((l) => l.label)).toContain("No data");
  });

  it("gives every renderable land-use value exactly one named key entry", () => {
    for (const value of RENDERABLE_LAND_USES) {
      const key = landUseLegendKey(value);
      expect(LAND_USE_LEGEND.filter((entry) => entry.key === key)).toHaveLength(1);
      expect(LAND_USE_LEGEND.find((entry) => entry.key === key)?.rgba).toEqual(landUseColor(value));
    }
    expect(RENDERABLE_LAND_USES).toEqual([
      "vacant", "residential", "multi_family", "commercial", "industrial",
      "mixed_use", "institutional", "exempt",
    ]);
  });

  it("maps unknown and null land use to the named no-data entry", () => {
    const noData = LAND_USE_LEGEND.find((entry) => entry.key === "land_use:no_data");
    expect(noData?.label).toBe("No data");
    expect(landUseLegendKey("unknown")).toBe("land_use:no_data");
    expect(landUseLegendKey(null)).toBe("land_use:no_data");
    expect(landUseColor("unknown")).toEqual(noData?.rgba);
    expect(landUseColor(null)).toEqual(noData?.rgba);
  });
});
