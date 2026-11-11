// The map's 3D mode (M6, decision Items 105-106): every building raised to its measured height from the County's 2022
// LiDAR footprints (`/api/map/tiles/buildings`, `h` = feet to the roof's highest point), tinted by the zoning under
// it. A visitor turns it on with the 2D/3D button on every map (owner, 2026-11-11); Build opens in 3D; on a phone only
// the expanded map can show it. Turn, tilt and reset are buttons beside it; a right-drag / Ctrl-drag or two fingers
// also turn and tilt.
import type { FillExtrusionLayerSpecification, Map as MLMap, VectorSourceSpecification } from "maplibre-gl";
import { ZONING_COLORS, type Theme, type TileSet } from "./mapStyle";

export const BUILDINGS_SOURCE = "buildings";
export const BUILDINGS_LAYER = "buildings-3d";
/** A building piece whose height wasn't measured (a merged County outline split along the City's footprints, Item
    106): drawn low and see-through, never as a measured height. */
export const UNMEASURED_LAYER = "buildings-3d-unmeasured";
export const BUILDING_LAYERS = [BUILDINGS_LAYER, UNMEASURED_LAYER];
const FEET_TO_METERS = 0.3048;

/** Buildings in neutral steps that lighten with height, each with a slight tint of the zoning family under it (owner,
    2026-11-11): the family's color mixed into the neutral, so a block reads by its massing first and its zoning
    second. */
export const BUILDING_COLORS: Record<Theme, { low: string; high: string; opacity: number; tint: number }> = {
  light: { low: "#E3E7EC", high: "#FFFFFF", opacity: 0.95, tint: 0.42 },
  dark: { low: "#3A3F46", high: "#727A84", opacity: 0.95, tint: 0.34 },
};

const hex = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
/** `a` mixed into `b` by `t` (0 = all b), in sRGB. */
export function mix(a: string, b: string, t: number): string {
  const [x, y] = [hex(a), hex(b)];
  return "#" + x.map((v, i) => Math.round(v * t + y[i] * (1 - t)).toString(16).padStart(2, "0")).join("");
}

/** The tint per zoning family: its second step (its usual, mid-density color). */
export function tintedColors(theme: Theme): Record<string, { low: string; high: string }> {
  const c = BUILDING_COLORS[theme];
  const out: Record<string, { low: string; high: string }> = {};
  for (const [fam, steps] of Object.entries(ZONING_COLORS)) {
    if (fam === "other") continue;
    out[fam] = { low: mix(steps[1], c.low, c.tint), high: mix(steps[1], c.high, c.tint * 0.75) };
  }
  return out;
}

export function buildingsSource(apiOrigin: string, tiles: TileSet): VectorSourceSpecification {
  // The version changes with every rebuild, so a day-cached tile never outlives a correction.
  const v = tiles.version ? `?v=${encodeURIComponent(tiles.version)}` : "";
  return { type: "vector", tiles: [`${apiOrigin}/api/map/tiles/buildings/{z}/{x}/{y}.mvt${v}`], minzoom: tiles.minZoom, maxzoom: tiles.maxZoom };
}

const METERS = ["*", ["to-number", ["get", "h"], 0], FEET_TO_METERS];

function colorExpr(theme: Theme): unknown {
  const c = BUILDING_COLORS[theme];
  const ramp = (low: string, high: string) => ["interpolate", ["linear"], METERS, 3, low, 60, high];
  const byFamily: unknown[] = ["match", ["get", "f"]];
  for (const [fam, t] of Object.entries(tintedColors(theme))) byFamily.push(fam, ramp(t.low, t.high));
  byFamily.push(ramp(c.low, c.high));
  return byFamily;
}

export function buildingsLayer(theme: Theme, minzoom: number): FillExtrusionLayerSpecification {
  return {
    id: BUILDINGS_LAYER, type: "fill-extrusion", source: BUILDINGS_SOURCE, "source-layer": "building", minzoom,
    filter: ["!=", ["get", "m"], "u"],
    paint: {
      "fill-extrusion-color": colorExpr(theme) as never,
      "fill-extrusion-height": METERS as never,
      "fill-extrusion-base": 0,
      "fill-extrusion-opacity": BUILDING_COLORS[theme].opacity,
      "fill-extrusion-vertical-gradient": true,
    },
  };
}

export function unmeasuredLayer(theme: Theme, minzoom: number): FillExtrusionLayerSpecification {
  return {
    id: UNMEASURED_LAYER, type: "fill-extrusion", source: BUILDINGS_SOURCE, "source-layer": "building", minzoom,
    filter: ["==", ["get", "m"], "u"],
    paint: {
      "fill-extrusion-color": colorExpr(theme) as never,
      "fill-extrusion-height": METERS as never,
      "fill-extrusion-base": 0,
      "fill-extrusion-opacity": 0.45,
    },
  };
}

/** The camera 3D opens at, and what Reset returns to. */
export const VIEW_3D = { pitch: 55, bearing: -20 } as const;
export const PITCH_STEP = 10;
export const PITCH_MAX = 70;
export const BEARING_STEP = 45;

/** The next pitch after a Tilt press: the next step of 10° up or down from where it is, within 0..PITCH_MAX. */
export function nextPitch(pitch: number, dir: 1 | -1): number {
  const next = dir === 1
    ? Math.floor((pitch + 0.5) / PITCH_STEP) * PITCH_STEP + PITCH_STEP
    : Math.ceil((pitch - 0.5) / PITCH_STEP) * PITCH_STEP - PITCH_STEP;
  return Math.min(PITCH_MAX, Math.max(0, next));
}

/** Whether 3D can show here: the server has building tiles, and on a phone only in the expanded map. */
export function can3d(hasBuildings: boolean, phone: boolean, expanded: boolean): boolean {
  return hasBuildings && (!phone || expanded);
}

/** Add the building layers once (hidden), below the pins and labels and above every fill. */
export function ensure3dLayers(map: MLMap, theme: Theme, apiOrigin: string, tiles: TileSet): void {
  if (!map.getSource(BUILDINGS_SOURCE)) map.addSource(BUILDINGS_SOURCE, buildingsSource(apiOrigin, tiles));
  const before = map.getStyle().layers?.find((l) => l.type === "symbol")?.id;
  for (const spec of [unmeasuredLayer(theme, tiles.minZoom), buildingsLayer(theme, tiles.minZoom)]) {
    if (!map.getLayer(spec.id)) map.addLayer({ ...spec, layout: { visibility: "none" } }, before);
  }
  // A soft light from the viewer's upper left: roofs stay close to their color, walls step darker.
  map.setLight({ anchor: "viewport", position: [1.4, 210, 35], intensity: 0.35, color: "#ffffff" });
}

/** Show or hide the buildings and move the camera: tilted and turned in 3D, flat and north-up in 2D. */
export function set3d(map: MLMap, on: boolean, animate: boolean): void {
  for (const id of BUILDING_LAYERS) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
  if (on) {
    map.dragRotate.enable();
    map.touchPitch.enable();
    map.touchZoomRotate.enableRotation();
  } else {
    map.dragRotate.disable();
    map.touchPitch.disable();
    map.touchZoomRotate.disableRotation();
  }
  const cam = on ? VIEW_3D : { pitch: 0, bearing: 0 };
  map.easeTo({ ...cam, duration: animate ? 600 : 0 });
}

export function repaint3d(map: MLMap, theme: Theme): void {
  for (const layer of [buildingsLayer(theme, 0), unmeasuredLayer(theme, 0)]) {
    if (!map.getLayer(layer.id)) continue;
    for (const [k, v] of Object.entries(layer.paint ?? {})) map.setPaintProperty(layer.id, k as never, v as never);
  }
}
