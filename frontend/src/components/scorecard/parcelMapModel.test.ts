import { describe, expect, it } from "vitest";
import {
  buildBoundaryMapModel,
  buildBoundaryRenderModel,
  buildZoningMapModel,
  zoneLabelsVisible,
} from "./parcelMapModel";

const square = (size: number): GeoJSON.Polygon => ({
  type: "Polygon",
  coordinates: [[[0, 0], [size, 0], [size, size], [0, size], [0, 0]]],
});

const zoning: GeoJSON.FeatureCollection = {
  type: "FeatureCollection",
  features: [
    { type: "Feature", geometry: square(3), properties: { ZONE_CLASS: "B3-2", ORDINANCE_NUM: "17230", source: "Chicago zoning" } },
    { type: "Feature", geometry: square(2), properties: { ZONE_CLASS: "B3-2", ORDINANCE_NUM: "17230", source: "Chicago zoning" } },
    { type: "Feature", geometry: square(1), properties: { ZONE_CLASS: "B3-3", ORDINANCE_NUM: "19001", source: "Chicago zoning" } },
  ],
};

describe("buildZoningMapModel", () => {
  it("emits one legend and backend-anchor label entry per exact district class", () => {
    const model = buildZoningMapModel(zoning, [
      { zone_class: "B3-2", position: [-87.677, 41.91] },
      { zone_class: "B3-2", position: [-87.676, 41.911] },
      { zone_class: "B3-3", position: [-87.675, 41.912] },
    ], "dark");

    expect(model.legend.map((entry) => entry.zoneClass)).toEqual(["B3-2", "B3-3"]);
    expect(model.legend.map((entry) => entry.count)).toEqual([2, 1]);
    expect(model.visibleCount).toBe(3);
    expect(model.withheldCount).toBe(0);
    expect(model.labels.map((entry) => entry.zoneClass)).toEqual(["B3-2", "B3-3"]);
    expect(model.labels[0].position).toEqual([-87.677, 41.91]);
    expect(model.labels[0].properties).toMatchObject({
      ZONE_CLASS: "B3-2",
      ORDINANCE_NUM: "17230",
      source: "Chicago zoning",
    });
  });

  it("does not manufacture a browser centroid when the backend anchor is absent", () => {
    const model = buildZoningMapModel(zoning, [
      { zone_class: "B3-2", position: [-87.677, 41.91] },
    ], "light");

    expect(model.legend).toHaveLength(2);
    expect(model.labels.map((entry) => entry.zoneClass)).toEqual(["B3-2"]);
  });

  it("applies a sensible minimum zoom to zoning labels", () => {
    expect(zoneLabelsVisible(14)).toBe(false);
    expect(zoneLabelsVisible(14.25)).toBe(true);
  });

  it("filters withheld features and counts visible and low-confidence districts exactly", () => {
    const confidenceFixture: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: [
        { type: "Feature", geometry: square(4), properties: { ZONE_CLASS: "B3-2", confidence: "standard" } },
        { type: "Feature", geometry: square(3), properties: { ZONE_CLASS: "B3-2", confidence: "low" } },
        { type: "Feature", geometry: square(2), properties: { ZONE_CLASS: "B3-2", confidence: "withheld" } },
        { type: "Feature", geometry: square(1), properties: { ZONE_CLASS: "B3-3", confidence: "withheld" } },
      ],
    };
    const model = buildZoningMapModel(confidenceFixture, [
      { zone_class: "B3-2", position: [-87.677, 41.91] },
      { zone_class: "B3-3", position: [-87.675, 41.912] },
    ], "dark");

    expect(model.featureCollection.features).toHaveLength(2);
    expect(model.featureCollection.features.every((feature) => feature.properties?.confidence !== "withheld")).toBe(true);
    expect(model.legend).toEqual([
      expect.objectContaining({ zoneClass: "B3-2", count: 2, lowConfidenceCount: 1 }),
    ]);
    expect(model.labels.map((entry) => entry.zoneClass)).toEqual(["B3-2"]);
    expect(model.visibleCount).toBe(2);
    expect(model.withheldCount).toBe(2);
  });
});

describe("buildBoundaryRenderModel", () => {
  it("orders broad polygons below narrow overlays and preserves source metadata", () => {
    const model = buildBoundaryRenderModel({
      overlays: {
        type: "FeatureCollection",
        features: [{
          type: "Feature",
          geometry: square(1),
          properties: { overlay_type: "landmark_district", NAME: "Milwaukee Avenue District", source: "Chicago DPD" },
        }],
      },
      tif: { type: "Feature", geometry: square(5), properties: { name: "Kinzie Industrial" } },
      ez: { type: "Feature", geometry: square(3), properties: { name: "Chicago Enterprise Zone 2" } },
    }, "dark");

    expect(model.map((entry) => entry.family)).toEqual(["tif", "enterprise_zone", "overlay"]);
    expect(model[2].feature.properties).toMatchObject({
      overlay_type: "landmark_district",
      NAME: "Milwaukee Avenue District",
      source: "Chicago DPD",
    });
    expect(new Set(model.map((entry) => entry.swatchCSS)).size).toBe(3);
    expect(model.every((entry) => entry.fillColor[3] <= 7)).toBe(true);
  });

  it("groups exact boundary names, preserves long labels, and counts withheld by logical source", () => {
    const longName = "Milwaukee Avenue Special Character Overlay District with an intentionally long official boundary name";
    const model = buildBoundaryMapModel({
      overlays: {
        type: "FeatureCollection",
        features: [
          { type: "Feature", geometry: square(2), properties: { overlay_type: "special_district", NAME: longName } },
          { type: "Feature", geometry: square(1), properties: { overlay_type: "special_district", NAME: longName, confidence: "low" } },
          { type: "Feature", geometry: square(1), properties: { overlay_type: "landmark_district", NAME: "Hidden", confidence: "withheld" } },
        ],
      },
      tif: { type: "Feature", geometry: square(5), properties: { name: "Hidden TIF", confidence: "withheld" } },
      ez: { type: "Feature", geometry: square(3), properties: { name: "Chicago Enterprise Zone 2" } },
    }, "light");

    expect(model.entries).toHaveLength(3);
    expect(model.entries.some((entry) => entry.feature.properties?.confidence === "withheld")).toBe(false);
    expect(model.legend).toContainEqual(expect.objectContaining({
      source: "overlays",
      name: longName,
      count: 2,
      lowConfidenceCount: 1,
    }));
    expect(model.counts).toEqual({
      overlays: { visible: 2, withheld: 1 },
      tif: { visible: 0, withheld: 1 },
      ez: { visible: 1, withheld: 0 },
    });
  });
});
