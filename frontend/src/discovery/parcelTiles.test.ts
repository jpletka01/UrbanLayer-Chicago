import { describe, expect, it, vi } from "vitest";
import { MATCH_COLORS, addParcelLayers, markMatches, pinFeatureId, tileUrlTemplate } from "./parcelTiles";

describe("parcel tiles", () => {
  it("keys a PIN by its first ten digits, dashed or not", () => {
    expect(pinFeatureId("14-31-300-012-1001")).toBe(1431300012);
    expect(pinFeatureId("14313000121001")).toBe(1431300012);
    expect(pinFeatureId("bad")).toBeNull();
  });

  it("clears the previous matches before marking the new ones", () => {
    const calls: string[] = [];
    const map = {
      getSource: () => ({}),
      removeFeatureState: vi.fn(() => calls.push("clear")),
      setFeatureState: vi.fn((f: { id: number }) => calls.push(`set ${f.id}`)),
    };
    markMatches(map as never, ["14-31-300-012-1001", "x"]);
    expect(calls).toEqual(["clear", "set 1431300012"]);
  });

  it("does nothing before the source exists", () => {
    const map = { getSource: () => undefined, removeFeatureState: vi.fn(), setFeatureState: vi.fn() };
    markMatches(map as never, ["14-31-300-012-1001"]);
    expect(map.removeFeatureState).not.toHaveBeenCalled();
  });

  it("adds the source and layers once, from the registry's zooms, in the theme's palette colors", () => {
    const sources: Record<string, { minzoom: number; maxzoom: number; tiles: string[] }> = {};
    const layers: Record<string, { minzoom: number; paint: Record<string, unknown> }> = {};
    const map = {
      getSource: (id: string) => sources[id],
      addSource: (id: string, s: (typeof sources)[string]) => { sources[id] = s; },
      getLayer: (id: string) => layers[id],
      addLayer: (l: { id: string; minzoom: number; paint: Record<string, unknown> }) => { layers[l.id] = l; },
    };
    addParcelLayers(map as never, "https://x", "light", { minZoom: 14, maxZoom: 16 });
    addParcelLayers(map as never, "https://x", "light", { minZoom: 14, maxZoom: 16 });
    expect(Object.keys(sources)).toEqual(["discovery-parcels"]);
    expect(sources["discovery-parcels"].tiles).toEqual(["https://x/api/discovery/tiles/{z}/{x}/{y}.mvt"]);
    expect(sources["discovery-parcels"]).toMatchObject({ minzoom: 14, maxzoom: 16 });
    expect(Object.keys(layers)).toEqual(["discovery-parcels-fill", "discovery-parcels-line"]);
    expect(layers["discovery-parcels-fill"].minzoom).toBe(14);
    expect(layers["discovery-parcels-fill"].paint["fill-color"]).toBe(MATCH_COLORS.light.fill);
    expect(MATCH_COLORS.light.fill).toBe("#d89552");
    expect(MATCH_COLORS.dark.fill).toBe("#e7c07f");
  });

  it("always hands Mapbox an absolute tile URL (production's API base is empty)", () => {
    expect(tileUrlTemplate("", "https://urbanlayerchicago.com/discovery?x=1"))
      .toBe("https://urbanlayerchicago.com/api/discovery/tiles/{z}/{x}/{y}.mvt");
    expect(tileUrlTemplate("http://localhost:5175", "http://localhost:5175/discovery"))
      .toBe("http://localhost:5175/api/discovery/tiles/{z}/{x}/{y}.mvt");
  });
});
