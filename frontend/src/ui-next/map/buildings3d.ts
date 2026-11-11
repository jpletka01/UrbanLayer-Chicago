// The map's 3D mode (M6, decision Items 105-106): every building raised to its measured height from the County's 2022
// LiDAR footprints (`/api/map/tiles/buildings`, `h` = feet to the roof's highest point), tinted by the zoning under
// it. A visitor turns it on with the 2D/3D button on every map (owner, 2026-11-11); Build opens in 3D; on a phone only
// the expanded map can show it. Turn, tilt and reset are buttons beside it; a right-drag / Ctrl-drag or two fingers
// also turn and tilt.
import type { FillExtrusionLayerSpecification, Map as MLMap, VectorSourceSpecification } from "maplibre-gl";
import { PALETTES, ZONING_COLORS, type Theme, type TileSet } from "./mapStyle";

export const BUILDINGS_SOURCE = "buildings";
export const BUILDINGS_LAYER = "buildings-3d";
/** A building piece whose height wasn't measured (a merged County outline split along the City's footprints, Item
    106): drawn low and see-through, never as a measured height. */
export const UNMEASURED_LAYER = "buildings-3d-unmeasured";
/** The illustrative zoning mass over the lot (Build, in 3D): a see-through block in the lot's color. */
export const MASS_SOURCE = "lot-mass";
export const MASS_LAYER = "lot-mass-3d";
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

/** Today's building on this lot is drawn in the lot's color (black in light, white in dark, Item 74), marked by
    feature state; every other building by its zoning tint. */
function colorExpr(theme: Theme): unknown {
  return ["case", ["boolean", ["feature-state", "lot"], false], PALETTES[theme].lot, tintExpr(theme)];
}

function tintExpr(theme: Theme): unknown {
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
    filter: measuredFilter() as never,
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

/** A district's color family, as the zoning tiles name it (`backend/map_tiles/zoning_tiles.family`). */
export function zoningFamily(zoneClass: string | null | undefined): string {
  const z = (zoneClass ?? "").toUpperCase().trim();
  if (z.startsWith("PMD")) return "manufacturing";
  if (z.startsWith("POS")) return "park";
  if (z.startsWith("PD")) return "planned";
  if (/^(RS|RT|RM)/.test(z)) return "residential";
  if (/^D[CXRS]/.test(z)) return "downtown";
  if (/^[BC]/.test(z)) return "business";
  if (z.startsWith("M")) return "manufacturing";
  if (z.startsWith("T")) return "transport";
  return "other";
}

/** The mass is drawn nearly solid in its district's darkest zoning step, so it reads as "the zoning"; today's building
    on the lot becomes a see-through ghost in the lot's color around it (taller or wider than the mass, it still shows). */
export function massLayer(theme: Theme): FillExtrusionLayerSpecification {
  return {
    id: MASS_LAYER, type: "fill-extrusion", source: MASS_SOURCE,
    paint: {
      "fill-extrusion-color": ["get", "c"] as never,
      "fill-extrusion-height": ["get", "m"] as never,
      "fill-extrusion-base": 0,
      "fill-extrusion-opacity": theme === "light" ? 0.85 : 0.9,
    },
  };
}

/** Today's building on the lot, see-through while the mass is shown (drawn from the loaded building pieces). */
export const LOT_BUILDING_SOURCE = "lot-building";
export const LOT_BUILDING_LAYER = "lot-building-3d";
export function lotBuildingLayer(theme: Theme): FillExtrusionLayerSpecification {
  return {
    id: LOT_BUILDING_LAYER, type: "fill-extrusion", source: LOT_BUILDING_SOURCE,
    paint: {
      "fill-extrusion-color": PALETTES[theme].lot,
      "fill-extrusion-height": METERS as never,
      "fill-extrusion-base": 0,
      "fill-extrusion-opacity": theme === "light" ? 0.28 : 0.32,
    },
  };
}

/** The mass as GeoJSON: the lot's outline raised to the mass height (feet → metres). */
export function massData(lot: GeoJSON.Geometry | null, heightFt: number | null, zoneClass: string | null = null): GeoJSON.FeatureCollection {
  if (!lot || heightFt == null || !(heightFt > 0) || (lot.type !== "Polygon" && lot.type !== "MultiPolygon")) {
    return { type: "FeatureCollection", features: [] };
  }
  const steps = ZONING_COLORS[zoningFamily(zoneClass)] ?? ZONING_COLORS.other;
  return { type: "FeatureCollection", features: [{ type: "Feature", geometry: lot, properties: { m: heightFt * FEET_TO_METERS, c: steps[3] } }] };
}

type Ring = number[][];
function inRing(x: number, y: number, ring: Ring): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
/** Whether a point is inside a (Multi)Polygon (holes respected). */
export function pointInLot(x: number, y: number, lot: GeoJSON.Geometry): boolean {
  const polys: Ring[][] = lot.type === "Polygon" ? [lot.coordinates as Ring[]] : lot.type === "MultiPolygon" ? (lot.coordinates as Ring[][]) : [];
  return polys.some(([outer, ...holes]) => inRing(x, y, outer) && !holes.some((h) => inRing(x, y, h)));
}

/** A building piece's middle: the average of its outer ring's corners (enough to tell which lot it stands on). */
export function ringMiddle(g: GeoJSON.Geometry): [number, number] | null {
  const ring = g.type === "Polygon" ? (g.coordinates[0] as Ring) : g.type === "MultiPolygon" ? (g.coordinates[0][0] as Ring) : null;
  if (!ring || ring.length < 3) return null;
  const pts = ring.slice(0, -1);
  return [pts.reduce((a, p) => a + p[0], 0) / pts.length, pts.reduce((a, p) => a + p[1], 0) / pts.length];
}

/** The measured layer's filter, leaving out `hidden` ids (the lot's own pieces while their see-through copy is drawn:
    MapLibre doesn't apply feature state to an extrusion's height, so they are filtered out instead). */
export function measuredFilter(hidden: Array<string | number> = []): unknown {
  const measured = ["!=", ["get", "m"], "u"];
  return hidden.length ? ["all", measured, ["!", ["in", ["id"], ["literal", hidden]]]] : measured;
}

/** Mark the loaded building pieces that stand on the lot (feature state `lot`: the lot's color); while `ghost` they
    leave the measured layer and a see-through copy goes into LOT_BUILDING_SOURCE. Returns the ids. */
export function markLotBuildings(map: MLMap, lot: GeoJSON.Geometry | null, previous: Set<string | number>, ghost = false): Set<string | number> {
  const next = new Set<string | number>();
  const copies: GeoJSON.Feature[] = [];
  if (lot && map.getSource(BUILDINGS_SOURCE)) {
    for (const f of map.querySourceFeatures(BUILDINGS_SOURCE, { sourceLayer: "building" })) {
      if (f.id == null) continue;
      const mid = ringMiddle(f.geometry);
      if (!mid || !pointInLot(mid[0], mid[1], lot)) continue;
      // A piece split across tiles comes once per tile: every copy is drawn (they meet at the tile edge).
      next.add(f.id);
      copies.push({ type: "Feature", geometry: f.geometry, properties: { h: f.properties?.h } });
    }
  }
  const at = (id: string | number) => ({ source: BUILDINGS_SOURCE, sourceLayer: "building", id });
  for (const id of previous) if (!next.has(id)) map.setFeatureState(at(id), { lot: false });
  for (const id of next) map.setFeatureState(at(id), { lot: true });
  if (map.getLayer(BUILDINGS_LAYER)) map.setFilter(BUILDINGS_LAYER, measuredFilter(ghost ? [...next] : []) as never);
  const src = map.getSource(LOT_BUILDING_SOURCE) as { setData?: (d: GeoJSON.FeatureCollection) => void } | undefined;
  src?.setData?.({ type: "FeatureCollection", features: ghost ? copies : [] });
  return next;
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
  // Above every flat layer, the lot's fill and lines included (a flat layer drawn later paints over an extrusion),
  // and below the first symbol (labels and pins) after them.
  const layers = map.getStyle().layers ?? [];
  const lastFlat = layers.reduce((at, l, i) => (l.type === "symbol" ? at : i), -1);
  const before = layers.slice(lastFlat + 1).find((l) => l.type === "symbol")?.id;
  if (!map.getSource(MASS_SOURCE)) map.addSource(MASS_SOURCE, { type: "geojson", data: massData(null, null) });
  if (!map.getSource(LOT_BUILDING_SOURCE)) map.addSource(LOT_BUILDING_SOURCE, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  for (const spec of [unmeasuredLayer(theme, tiles.minZoom), buildingsLayer(theme, tiles.minZoom), lotBuildingLayer(theme), massLayer(theme)]) {
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
  for (const layer of [buildingsLayer(theme, 0), unmeasuredLayer(theme, 0), lotBuildingLayer(theme), massLayer(theme)]) {
    if (!map.getLayer(layer.id)) continue;
    for (const [k, v] of Object.entries(layer.paint ?? {})) map.setPaintProperty(layer.id, k as never, v as never);
  }
}
