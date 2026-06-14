import { describe, expect, it } from "vitest";
import { upsideColor, UPSIDE_LEGEND } from "./upsideColor";

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
});
