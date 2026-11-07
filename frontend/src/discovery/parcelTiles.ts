// Parcel outlines on the Discovery map (WS8 Phase 2, decision Item 68). Mapbox GL draws the backend's vector
// tiles itself (no extra dependency); deck.gl's dots stay on top for picking. The tiles hold geometry and the PIN
// only: which parcels the search matched is set per PIN through Mapbox feature-state, so one tile set serves
// every query. On when the registry lists a tile file (`registry.parcelTiles`), from its `minZoom`.
//
// Colors: Jack's data palette (2026-11-04; warm earth tones, light to dark #f2e2c0 #e7c07f #d89552 #bf6236
// #8a3a38 #4b3a5e). A match is filled with one of its middle tones, lighter on the dark basemap; every other
// lot gets a faint neutral outline.

import type { Map as MapboxMap } from "mapbox-gl";

const SOURCE = "discovery-parcels";
const SOURCE_LAYER = "parcels";
const FILL = "discovery-parcels-fill";
const LINE = "discovery-parcels-line";

export const MATCH_COLORS = {
  dark: { fill: "#e7c07f", line: "#e7c07f", outline: "rgba(255,255,255,0.22)" },
  light: { fill: "#d89552", line: "#bf6236", outline: "rgba(23,23,23,0.28)" },
} as const;

/** Feature id of a PIN: its first ten digits (the tiles carry one outline per PIN10). */
export function pinFeatureId(pin: string): number | null {
  const digits = pin.replace(/\D/g, "");
  return digits.length >= 10 ? Number(digits.slice(0, 10)) : null;
}

/** The tile URL template, always absolute. Production builds with an empty API base, and Mapbox fetches tiles from
 *  a web worker, where a relative URL does not resolve against the page: no tile was ever requested (2026-11-04). */
export function tileUrlTemplate(apiBase: string, pageUrl: string = window.location.href): string {
  return `${new URL(`${apiBase}/api/discovery/tiles/`, pageUrl).href}{z}/{x}/{y}.mvt`;
}

/** Add the source and layers (idempotent; call again after a style swap, which drops them). */
export function addParcelLayers(
  map: MapboxMap, apiBase: string, theme: "light" | "dark", zooms: { minZoom: number; maxZoom: number },
): void {
  if (!map.getSource(SOURCE)) {
    map.addSource(SOURCE, {
      type: "vector",
      tiles: [tileUrlTemplate(apiBase)],
      minzoom: zooms.minZoom,
      maxzoom: zooms.maxZoom,
    });
  }
  const c = MATCH_COLORS[theme];
  const matched = ["boolean", ["feature-state", "match"], false];
  if (!map.getLayer(FILL)) {
    map.addLayer({
      id: FILL, type: "fill", source: SOURCE, "source-layer": SOURCE_LAYER, minzoom: zooms.minZoom,
      paint: { "fill-color": c.fill, "fill-opacity": ["case", matched, 0.5, 0] },
    });
  }
  if (!map.getLayer(LINE)) {
    map.addLayer({
      id: LINE, type: "line", source: SOURCE, "source-layer": SOURCE_LAYER, minzoom: zooms.minZoom,
      paint: {
        "line-color": ["case", matched, c.line, c.outline],
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

/** The PIN10 of the outline drawn at a screen point, or null (no outline there, or outlines not added). Every
 *  outline is queryable, matched or not: the fill layer covers every lot (opacity 0 for non-matches). */
export function outlineAt(map: MapboxMap, x: number, y: number): string | null {
  if (!map.getLayer(FILL)) return null;
  const hit = map.queryRenderedFeatures([x, y], { layers: [FILL] })[0];
  const id = hit?.id;
  if (id == null) return null;
  const digits = String(id).replace(/\D/g, "");
  return digits ? digits.padStart(10, "0") : null;
}
