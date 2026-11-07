// The new UI's cleaned base style (decision Item 76; brief "Maps": a quiet base, no business or point-of-interest
// labels, street names only when zoomed in). Applied on every `style.load`, opt-in through
// useMapboxOverlay({ quiet: true }), so today's maps keep exactly the base they have (POI labels already hidden
// everywhere, Item 72d). No new tiles: it only hides or delays layers of the Mapbox styles we already load.

import type { StyleLayerLike } from "./mapPoiLabels";
import { poiLabelLayerIds } from "./mapPoiLabels";

interface MapLike {
  getStyle(): { layers?: StyleLayerLike[] } | undefined;
  setLayoutProperty(layerId: string, name: string, value: unknown): unknown;
  setLayerZoomRange(layerId: string, minzoom: number, maxzoom: number): unknown;
}

/** Label layers that only add noise on a parcel map: nature and water names, airports, neighborhoods' sub-areas,
    house numbers, route shields and building names. Road and transit labels stay (they are how a reader finds
    the place). */
const NOISE = /natural|water(way)?-?.*label|airport|settlement-subdivision|housenum|building-number|road-number|shield|building-label/i;

/** Street names appear from this zoom up. */
export const STREET_LABEL_MIN_ZOOM = 15;

export function quietLayerPlan(layers: readonly StyleLayerLike[]): { hide: string[]; delay: string[] } {
  const symbols = layers.filter((l) => l.type === "symbol");
  const hide = new Set(poiLabelLayerIds(layers));
  for (const l of symbols) if (NOISE.test(l.id)) hide.add(l.id);
  const delay = symbols.filter((l) => /^road-label/.test(l.id) && !hide.has(l.id)).map((l) => l.id);
  return { hide: [...hide], delay };
}

/** Apply the plan. Never throws: a style without these layers, or a map mid-teardown, keeps its labels. */
export function applyQuietBaseStyle(map: MapLike): { hide: string[]; delay: string[] } {
  try {
    const plan = quietLayerPlan(map.getStyle()?.layers ?? []);
    for (const id of plan.hide) map.setLayoutProperty(id, "visibility", "none");
    for (const id of plan.delay) map.setLayerZoomRange(id, STREET_LABEL_MIN_ZOOM, 24);
    return plan;
  } catch {
    return { hide: [], delay: [] };
  }
}
