// Parcel outlines on the Discovery map (WS8 Phase 2 prototype, decision Item 68). Mapbox GL draws the
// backend's vector tiles itself (no new dependency); deck.gl's dots stay on top for picking. The tiles hold
// geometry and the PIN only: which parcels the search matched is set per PIN through Mapbox feature-state,
// so one tile set serves every query. Off unless VITE_DISCOVERY_TILES=1.

import type { Map as MapboxMap } from "mapbox-gl";

export const PARCEL_TILES_ENABLED = import.meta.env.VITE_DISCOVERY_TILES === "1";

const SOURCE = "discovery-parcels";
const SOURCE_LAYER = "parcels";
const FILL = "discovery-parcels-fill";
const LINE = "discovery-parcels-line";
// Below this zoom a parcel is a few pixels wide: the dots read better.
export const PARCEL_MIN_ZOOM = 14;

/** Feature id of a PIN: its first ten digits (the tiles carry one outline per PIN10). */
export function pinFeatureId(pin: string): number | null {
  const digits = pin.replace(/\D/g, "");
  return digits.length >= 10 ? Number(digits.slice(0, 10)) : null;
}

/** Add the source and layers (idempotent; call again after a style swap). */
export function addParcelLayers(map: MapboxMap, apiBase: string, theme: "light" | "dark"): void {
  if (!map.getSource(SOURCE)) {
    map.addSource(SOURCE, {
      type: "vector",
      tiles: [`${apiBase}/api/discovery/tiles/{z}/{x}/{y}.mvt`],
      minzoom: 14,
      maxzoom: 16,
    });
  }
  const outline = theme === "light" ? "rgba(23,23,23,0.28)" : "rgba(255,255,255,0.22)";
  if (!map.getLayer(FILL)) {
    map.addLayer({
      id: FILL,
      type: "fill",
      source: SOURCE,
      "source-layer": SOURCE_LAYER,
      minzoom: PARCEL_MIN_ZOOM,
      paint: {
        "fill-color": "#F9A474",
        "fill-opacity": ["case", ["boolean", ["feature-state", "match"], false], 0.45, 0],
      },
    });
  }
  if (!map.getLayer(LINE)) {
    map.addLayer({
      id: LINE,
      type: "line",
      source: SOURCE,
      "source-layer": SOURCE_LAYER,
      minzoom: PARCEL_MIN_ZOOM,
      paint: {
        "line-color": ["case", ["boolean", ["feature-state", "match"], false], "#F9A474", outline],
        "line-width": ["interpolate", ["linear"], ["zoom"], 14, 0.4, 17, 1.2],
      },
    });
  }
}

/** Mark exactly these PINs as matches (clears the previous set). */
export function markMatches(map: MapboxMap, pins: readonly string[]): void {
  if (!map.getSource(SOURCE)) return;
  map.removeFeatureState({ source: SOURCE, sourceLayer: SOURCE_LAYER });
  for (const pin of pins) {
    const id = pinFeatureId(pin);
    if (id != null) map.setFeatureState({ source: SOURCE, sourceLayer: SOURCE_LAYER, id }, { match: true });
  }
}
