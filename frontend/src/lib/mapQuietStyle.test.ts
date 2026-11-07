import { describe, expect, it, vi } from "vitest";
import { applyQuietBaseStyle, quietLayerPlan, STREET_LABEL_MIN_ZOOM } from "./mapQuietStyle";
import { buildSubjectParcelLayersNext } from "../components/scorecard/parcelMapLayers";

const LAYERS = [
  { id: "land", type: "background" },
  { id: "road-primary", type: "line" },
  { id: "building", type: "fill" },
  { id: "land-structure-polygon", type: "fill" },
  { id: "aeroway-polygon", type: "fill" },
  { id: "landuse", type: "fill" },
  { id: "water", type: "fill" },
  { id: "poi-label", type: "symbol" },
  { id: "natural-point-label", type: "symbol" },
  { id: "waterway-label", type: "symbol" },
  { id: "airport-label", type: "symbol" },
  { id: "settlement-subdivision-label", type: "symbol" },
  { id: "road-number-shield", type: "symbol" },
  { id: "road-label-simple", type: "symbol" },
  { id: "transit-label", type: "symbol" },
];

describe("the new UI's quiet base style", () => {
  it("hides point-of-interest and noise labels, keeps transit, delays street names to zoomed-in", () => {
    const plan = quietLayerPlan(LAYERS);
    expect(plan.hide.sort()).toEqual([
      "aeroway-polygon", "airport-label", "building", "land-structure-polygon", "natural-point-label", "poi-label",
      "road-number-shield", "settlement-subdivision-label", "waterway-label",
    ]);
    expect(plan.hide).not.toContain("water");
    expect(plan.hide).not.toContain("landuse");
    expect(plan.delay).toEqual(["road-label-simple"]);
    expect(plan.hide).not.toContain("transit-label");
    expect(plan.hide).not.toContain("road-primary");
  });

  it("applies the plan and never throws on a map mid-teardown", () => {
    const map = { getStyle: () => ({ layers: LAYERS }), setLayoutProperty: vi.fn(), setLayerZoomRange: vi.fn() };
    applyQuietBaseStyle(map);
    expect(map.setLayerZoomRange).toHaveBeenCalledWith("road-label-simple", STREET_LABEL_MIN_ZOOM, 24);
    expect(map.setLayoutProperty).toHaveBeenCalledWith("poi-label", "visibility", "none");
    const broken = { getStyle: () => { throw new Error("gone"); }, setLayoutProperty: vi.fn(), setLayerZoomRange: vi.fn() };
    expect(applyQuietBaseStyle(broken)).toEqual({ hide: [], delay: [] });
  });
});

describe("this lot on the new map", () => {
  const geometry = { type: "Polygon", coordinates: [[[0, 0], [0, 1], [1, 1], [0, 0]]] } as GeoJSON.Geometry;
  const props = (l: unknown) => (l as { props: Record<string, unknown> }).props;

  it("is a black outline over a white edge (white over dark on dark streets), never the orange accent", () => {
    const [edge, line] = buildSubjectParcelLayersNext({ parcelGeometry: geometry, lat: 0, lon: 0, onDarkStreets: false, confidence: "authoritative" });
    expect(props(edge).id).toBe("pm-parcel-edge");
    expect(props(edge).getLineColor).toEqual([255, 255, 255, 235]);
    expect(props(line).getLineColor).toEqual([28, 28, 28, 255]);
    const [, dark] = buildSubjectParcelLayersNext({ parcelGeometry: geometry, lat: 0, lon: 0, onDarkStreets: true, confidence: "authoritative" });
    expect(props(dark).getLineColor).toEqual([255, 255, 255, 255]);
  });

  it("keeps the dashed low-confidence outline for an approximate parcel", () => {
    const [, line] = buildSubjectParcelLayersNext({ parcelGeometry: geometry, lat: 0, lon: 0, onDarkStreets: false, confidence: "approximate" });
    expect(props(line).getDashArray).toEqual([4, 3]);
  });
});
