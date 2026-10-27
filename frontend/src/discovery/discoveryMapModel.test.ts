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

    expect(model.mappable.map((entry) => entry.pin)).toEqual(["valid"]);
    expect(model.returnedCount).toBe(4);
    expect(model.unlocatedCount).toBe(3);
    expect(model.omittedByCapCount).toBe(5);
  });

  it("does not label an unexplained non-truncated gap as a cap omission", () => {
    expect(buildDiscoveryMapModel([point("one", 41.9, -87.7)], 3, false).omittedByCapCount).toBe(0);
  });
});
