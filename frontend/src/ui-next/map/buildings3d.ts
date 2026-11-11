// The map's 3D mode, M6 spike (decision Items 105-106): every building raised to its measured height from the
// County's 2022 LiDAR footprints (`/api/map/tiles/buildings`, `h` = feet to the roof's highest point). A spike:
// switched on only by `?map3d=1` in development, so the owner can review how it looks and we can measure frame rate
// before deciding how a visitor enters it (an open question for the owner).
import type { FillExtrusionLayerSpecification, Map as MLMap, VectorSourceSpecification } from "maplibre-gl";
import type { Theme, TileSet } from "./mapStyle";

export const BUILDINGS_SOURCE = "buildings";
export const BUILDINGS_LAYER = "buildings-3d";
const FEET_TO_METERS = 0.3048;

/** Buildings in neutral steps that lighten with height, so a block reads by its massing, not by color; the lot's
    own colors stay the only meaning on the map (Item 74). */
export const BUILDING_COLORS: Record<Theme, { low: string; high: string; opacity: number }> = {
  light: { low: "#E3E7EC", high: "#FFFFFF", opacity: 0.95 },
  dark: { low: "#3A3F46", high: "#727A84", opacity: 0.95 },
};

export function buildingsSource(apiOrigin: string, tiles: TileSet): VectorSourceSpecification {
  return { type: "vector", tiles: [`${apiOrigin}/api/map/tiles/buildings/{z}/{x}/{y}.mvt`], minzoom: tiles.minZoom, maxzoom: tiles.maxZoom };
}

export function buildingsLayer(theme: Theme, minzoom: number): FillExtrusionLayerSpecification {
  const c = BUILDING_COLORS[theme];
  const meters = ["*", ["to-number", ["get", "h"], 0], FEET_TO_METERS];
  return {
    id: BUILDINGS_LAYER, type: "fill-extrusion", source: BUILDINGS_SOURCE, "source-layer": "building", minzoom,
    paint: {
      "fill-extrusion-color": ["interpolate", ["linear"], meters, 3, c.low, 60, c.high] as never,
      "fill-extrusion-height": meters as never,
      "fill-extrusion-base": 0,
      "fill-extrusion-opacity": c.opacity,
      "fill-extrusion-vertical-gradient": true,
    },
  };
}

/** Whether the development switch asks for 3D (`?map3d=1`). Never on in a production build. */
export function wants3d(search: string = typeof window === "undefined" ? "" : window.location.search, dev = import.meta.env.DEV): boolean {
  return dev && new URLSearchParams(search).get("map3d") === "1";
}

/** Raise the buildings and tilt the camera; drag with the right button or Ctrl rotates. */
export function enable3d(map: MLMap, theme: Theme, apiOrigin: string, tiles: TileSet): void {
  if (!map.getSource(BUILDINGS_SOURCE)) map.addSource(BUILDINGS_SOURCE, buildingsSource(apiOrigin, tiles));
  // Below the pins and labels, above every fill (the first symbol layer).
  const before = map.getStyle().layers?.find((l) => l.type === "symbol")?.id;
  if (!map.getLayer(BUILDINGS_LAYER)) map.addLayer(buildingsLayer(theme, tiles.minZoom), before);
  map.dragRotate.enable();
  map.touchPitch.enable();
  // A soft light from the viewer's upper left: roofs stay close to their color, walls step darker.
  map.setLight({ anchor: "viewport", position: [1.4, 210, 35], intensity: 0.35, color: "#ffffff" });
  map.easeTo({ pitch: 55, bearing: -20, zoom: Math.min(Math.max(map.getZoom(), 15), 15.8), duration: 0 });
}

export function repaint3d(map: MLMap, theme: Theme): void {
  if (!map.getLayer(BUILDINGS_LAYER)) return;
  const paint = buildingsLayer(theme, 0).paint as Record<string, unknown>;
  for (const [k, v] of Object.entries(paint)) map.setPaintProperty(BUILDINGS_LAYER, k as never, v as never);
}
