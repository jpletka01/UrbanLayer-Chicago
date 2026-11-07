import { describe, expect, it, vi } from "vitest";
import { hidePoiLabels, poiLabelLayerIds } from "./mapPoiLabels";

// The label layers of Mapbox's dark-v11 / light-v11 / satellite-streets-v12 that matter here (ids as published).
const STYLE = [
  { id: "land", type: "background" },
  { id: "road-primary", type: "line" },
  { id: "road-label-simple", type: "symbol" },
  { id: "road-number-shield", type: "symbol" },
  { id: "waterway-label", type: "symbol" },
  { id: "poi-label", type: "symbol" },
  { id: "transit-label", type: "symbol" },
  { id: "airport-label", type: "symbol" },
  { id: "settlement-subdivision-label", type: "symbol" },
  { id: "poi-fill-demo", type: "fill" }, // not a label: never touched
];

describe("POI labels", () => {
  it("picks only symbol layers named for points of interest; street, transit and place labels stay", () => {
    expect(poiLabelLayerIds(STYLE)).toEqual(["poi-label"]);
  });

  it("hides them on the map, and can run again after a style swap", () => {
    const map = { getStyle: () => ({ layers: STYLE }), setLayoutProperty: vi.fn() };
    expect(hidePoiLabels(map)).toEqual(["poi-label"]);
    expect(hidePoiLabels(map)).toEqual(["poi-label"]);
    expect(map.setLayoutProperty).toHaveBeenCalledWith("poi-label", "visibility", "none");
    expect(map.setLayoutProperty).toHaveBeenCalledTimes(2);
  });

  it("a style with no POI layer, or one that is gone, changes nothing and never throws", () => {
    expect(hidePoiLabels({ getStyle: () => ({ layers: [{ id: "road-label", type: "symbol" }] }), setLayoutProperty: vi.fn() })).toEqual([]);
    expect(hidePoiLabels({ getStyle: () => { throw new Error("removed"); }, setLayoutProperty: vi.fn() })).toEqual([]);
  });
});
