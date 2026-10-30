import { describe, expect, it } from "vitest";
import type { MapData } from "../../lib/types";
import {
  incentiveZoneColor,
  overlayColor,
  zoneColor,
} from "../../lib/mapColors";
import { buildLayerTooltip } from "../../lib/mapTooltip";

// Recorded-shape fixture: no fetch, chat hook, router, or model call. It pins
// the shared encodings and source tooltip metadata consumed by MapView.
const recordedMapData: MapData = {
  crimes: [],
  requests_311: [],
  building_permits: [],
  queried_address: { latitude: 41.91086, longitude: -87.67778, label: "1601 N Milwaukee Ave" },
  zoning: {
    type: "FeatureCollection",
    features: [
      { type: "Feature", geometry: null, properties: { ZONE_CLASS: "B3-2", ORDINANCE_NUM: "17230" } },
      { type: "Feature", geometry: null, properties: { ZONE_CLASS: "B3-3", ORDINANCE_NUM: "19001" } },
    ],
  },
  overlay_districts: {
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      geometry: null,
      properties: { overlay_type: "landmark_district", NAME: "Milwaukee Avenue District", source: "Chicago DPD" },
    }],
  },
  incentive_zones: {
    type: "FeatureCollection",
    features: [
      { type: "Feature", geometry: null, properties: { zone_type: "tif", name: "Kinzie Industrial" } },
      { type: "Feature", geometry: null, properties: { zone_type: "enterprise_zone", name: "Chicago Enterprise Zone 2" } },
    ],
  },
};

const features = (collection: Record<string, unknown> | null | undefined) => (
  (collection?.features ?? []) as Array<Record<string, unknown>>
);

describe("MapView recorded-map compatibility", () => {
  it("applies exact zoning intensity and semantic boundary colors", () => {
    const zoning = features(recordedMapData.zoning);
    const incentives = features(recordedMapData.incentive_zones);
    const overlays = features(recordedMapData.overlay_districts);
    const props = (feature: Record<string, unknown>) => feature.properties as Record<string, string>;

    expect(zoneColor(props(zoning[0]).ZONE_CLASS)).not.toEqual(zoneColor(props(zoning[1]).ZONE_CLASS));
    expect(overlayColor(props(overlays[0]).overlay_type)[3]).toBeLessThan(8);
    expect(incentiveZoneColor(props(incentives[0]).name, props(incentives[0]).zone_type)).not.toEqual(
      incentiveZoneColor(props(incentives[1]).name, props(incentives[1]).zone_type),
    );
  });

  it("retains exact district and source names in shared tooltips", () => {
    const zoning = features(recordedMapData.zoning)[0];
    const overlay = features(recordedMapData.overlay_districts)[0];
    const tif = features(recordedMapData.incentive_zones)[0];

    expect(buildLayerTooltip({ object: zoning, layer: { id: "zoning" }, x: 0, y: 0 })?.html).toContain("B3-2");
    expect(buildLayerTooltip({ object: overlay, layer: { id: "overlay-districts" }, x: 0, y: 0 })?.html)
      .toContain("Milwaukee Avenue District");
    expect(buildLayerTooltip({ object: tif, layer: { id: "incentive-zones" }, x: 0, y: 0 })?.html)
      .toContain("Kinzie Industrial");
  });
});
