import { describe, expect, it } from "vitest";
import { unavailableParcelMapSources, type ParcelMapAvailability } from "./parcelMap";

const available: ParcelMapAvailability = {
  zoning: "available",
  overlays: "available",
  tif: "available",
  ez: "available",
};

describe("unavailableParcelMapSources", () => {
  it("reports only the source used by the zoning map", () => {
    expect(unavailableParcelMapSources("zoning", {
      ...available,
      zoning: "unavailable",
      tif: "unavailable",
    })).toEqual(["zoning"]);
  });

  it("reports each unavailable boundaries source in stable order", () => {
    expect(unavailableParcelMapSources("boundaries", {
      ...available,
      overlays: "unavailable",
      ez: "unavailable",
    })).toEqual(["overlays", "ez"]);
  });

  it("never adds a thematic-source warning to the place map", () => {
    expect(unavailableParcelMapSources("place", {
      ...available,
      zoning: "unavailable",
    })).toEqual([]);
  });
});
