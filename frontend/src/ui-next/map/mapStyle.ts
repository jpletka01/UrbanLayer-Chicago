// The new UI's map style (map track M1, decision Items 90-91): the Cities: Skylines look (Item 80) drawn from our
// own tiles. Pure: builds a MapLibre style document and the per-theme paint for every layer, so a theme switch
// repaints in place (setPaintProperty) and never reloads the style: sources, feature state, the camera and every
// overlay survive it.
//
// What the look is made of (research/15 §2.4): a dim, desaturated base; our shapes filled and outlined thinly in a
// color that means something; roads drawn by the map over the fills in a few classes; names only zoomed in;
// On / Off per layer (the owner dropped Dim after his first review: zoning reads best fully on).

import type { LayerSpecification, StyleSpecification } from "maplibre-gl";

export type Theme = "light" | "dark";
export type LayerMode = "on" | "off";

/** The groups a visitor can turn On / Off, in the key's order. The base land and water are not a group. */
export type GroupId = "zoning" | "parcels" | "streets" | "sales" | "transit";
export const GROUPS: GroupId[] = ["zoning", "parcels", "sales", "transit", "streets"];

/** Street names appear from this zoom (brief: names only when zoomed in). */
export const STREET_LABEL_MIN_ZOOM = 15;

export interface TileSet { minZoom: number; maxZoom: number }
export interface MapTiles { base: TileSet | null; parcels: TileSet | null; zoning: TileSet | null }

// ---------------------------------------------------------------- colors

interface Palette {
  outside: string; land: string; water: string; park: string;
  highway: string; major: string; minor: string; local: string; ramp: string; casing: string;
  label: string; halo: string;
  parcelLine: string; parcelLineOpacity: number; parcelHit: string;
  lot: string; lotEdge: string;
  sale: string; saleEdge: string; transit: string; transitEdge: string;
  zoningLabel: string; zoningFill: number; zoningLine: number;
}

// Light: a pale, cool base where streets read as white gaps; dark: the reference's dim gray base with warm
// arterials. "This lot" is black with a white edge in light and white with a dark edge in dark (Item 74).
export const PALETTES: Record<Theme, Palette> = {
  light: {
    outside: "#E4E7EB", land: "#EEF0F3", water: "#C6D9E3", park: "#D6E8D8",
    highway: "#EE9580", major: "#F3C58C", minor: "#FFFFFF", local: "#FFFFFF", ramp: "#F2AE9C", casing: "#D3D8DE",
    label: "#3C4249", halo: "#F4F6F8",
    parcelLine: "#1C1C1C", parcelLineOpacity: 0.16, parcelHit: "#1C1C1C",
    lot: "#1C1C1C", lotEdge: "#FFFFFF",
    sale: "#72B0AB", saleEdge: "#FFFFFF", transit: "#355E58", transitEdge: "#FFFFFF",
    zoningLabel: "#1C1C1C", zoningFill: 0.42, zoningLine: 0.85,
  },
  dark: {
    outside: "#141516", land: "#1E2023", water: "#18252D", park: "#1B2620",
    highway: "#E8806F", major: "#D9AE73", minor: "#8A9097", local: "#6B7178", ramp: "#B56F62", casing: "#141516",
    label: "#C9CDD2", halo: "#1E2023",
    parcelLine: "#FFFFFF", parcelLineOpacity: 0.14, parcelHit: "#FFFFFF",
    lot: "#FFFFFF", lotEdge: "#1C1C1C",
    sale: "#72B0AB", saleEdge: "#1C1C1C", transit: "#B1E3D9", transitEdge: "#1C1C1C",
    zoningLabel: "#FFFFFF", zoningFill: 0.30, zoningLine: 0.75,
  },
};

/** Zoning colors by family, four steps darker as intensity rises (Item 74's provisional family hues). The same
    steps in both themes; the fill opacity differs per theme. */
export const ZONING_COLORS: Record<string, [string, string, string, string]> = {
  residential: ["#E4D9FA", "#CDB7F6", "#AE91E8", "#8A6AD0"],
  business: ["#F5BDBF", "#ED8A8E", "#D9666B", "#B8464C"],
  manufacturing: ["#D9C47E", "#B99C3A", "#977C24", "#735D16"],
  downtown: ["#A6CCE3", "#63A8CF", "#3F86B0", "#2A6488"],
  park: ["#A7E2B2", "#A7E2B2", "#A7E2B2", "#A7E2B2"],
  transport: ["#8F959C", "#8F959C", "#8F959C", "#8F959C"],
  planned: ["#C9CED6", "#C9CED6", "#C9CED6", "#C9CED6"],
  other: ["#C9CED6", "#C9CED6", "#C9CED6", "#C9CED6"],
};
export const ZONING_FAMILIES = ["residential", "business", "manufacturing", "downtown", "planned", "park", "transport"] as const;

function zoningColorExpr(): unknown {
  // match on family, then on level 1-4.
  const byFamily: unknown[] = ["match", ["get", "family"]];
  for (const [fam, steps] of Object.entries(ZONING_COLORS)) {
    byFamily.push(fam, ["match", ["get", "level"], "2", steps[1], "3", steps[2], "4", steps[3], steps[0]]);
  }
  byFamily.push(ZONING_COLORS.other[0]);
  return byFamily;
}

// ---------------------------------------------------------------- layers

/** Every style layer: its group (or none), the paint for a theme, and the opacity properties Dim scales. */
interface LayerDef {
  group: GroupId | null;
  spec: (t: Theme) => LayerSpecification;
  /** Paint properties holding an opacity that On restores after a theme change. */
  opacity: string[];
  needs: keyof MapTiles | "sales" | "transit" | "lot" | null;
}

const zoomWidth = (stops: Array<[number, number]>) =>
  ["interpolate", ["exponential", 1.6], ["zoom"], ...stops.flat()] as unknown as number;

/** Ground metres per pixel at Chicago's latitude (41.88°) at a zoom. */
export const metersPerPixel = (z: number) => 116_630 / 2 ** z;

/** A road drawn at its real width from zoom 14 up (it scales with the map, base 2, so a street fills the gap between
    the lots on either side: streets read as clean negative space, owner's review), and at a readable minimum below. */
export const roadWidth = (meters: number, lowZoomPx: number) =>
  ["interpolate", ["exponential", 2], ["zoom"],
    10, lowZoomPx, 14, Math.max(lowZoomPx, meters / metersPerPixel(14)), 20, meters / metersPerPixel(20)] as unknown as number;

/** Street widths in metres, a little under Chicago's usual right-of-way (66 ft local, 80-100 ft arterials) so the lot
    lines at its edges stay visible. */
export const ROAD_METERS = { local: 16, minor: 20, major: 24, highway: 34, ramp: 8 } as const;

const roadLayer = (kind: keyof typeof ROAD_METERS, minzoom: number, lowZoomPx: number, color: keyof Palette): LayerDef => ({
  group: "streets", needs: "base", opacity: ["line-opacity"],
  spec: (t) => ({
    id: `road-${kind}`, type: "line", source: "base", "source-layer": "road", minzoom,
    filter: ["==", ["get", "kind"], kind],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": PALETTES[t][color] as string, "line-width": roadWidth(ROAD_METERS[kind], lowZoomPx), "line-opacity": 1 },
  }),
});

export const LAYERS: LayerDef[] = [
  { group: null, needs: null, opacity: [], spec: (t) => ({ id: "background", type: "background", paint: { "background-color": PALETTES[t].outside } }) },
  { group: null, needs: "base", opacity: [], spec: (t) => ({ id: "city", type: "fill", source: "base", "source-layer": "city", paint: { "fill-color": PALETTES[t].land } }) },
  { group: null, needs: "base", opacity: [], spec: (t) => ({ id: "park", type: "fill", source: "base", "source-layer": "park", paint: { "fill-color": PALETTES[t].park } }) },
  {
    group: "zoning", needs: "zoning", opacity: ["fill-opacity"],
    spec: (t) => ({ id: "zoning-fill", type: "fill", source: "zoning", "source-layer": "zoning",
      paint: { "fill-color": zoningColorExpr() as string, "fill-opacity": PALETTES[t].zoningFill } }),
  },
  // Water draws over the zoning fill (owner's review): the City zones lagoons with their parks (POS), and the
  // zoning fill covered the water. Parks stay under the zoning, so their green is the POS fill over the park color.
  { group: null, needs: "base", opacity: [], spec: (t) => ({ id: "water", type: "fill", source: "base", "source-layer": "water", paint: { "fill-color": PALETTES[t].water } }) },
  {
    group: "parcels", needs: "parcels", opacity: ["fill-opacity"],
    // Invisible except where a lot is marked (a search match or a sale): fill only under feature-state.
    spec: (t) => ({ id: "parcel-fill", type: "fill", source: "parcels", "source-layer": "parcels",
      paint: { "fill-color": PALETTES[t].parcelHit,
        "fill-opacity": ["case", ["boolean", ["feature-state", "match"], false], 0.18, 0] as unknown as number } }),
  },
  {
    group: "zoning", needs: "zoning", opacity: ["line-opacity"],
    spec: (t) => ({ id: "zoning-line", type: "line", source: "zoning", "source-layer": "zoning",
      paint: { "line-color": zoningColorExpr() as string, "line-opacity": PALETTES[t].zoningLine,
        "line-width": zoomWidth([[13, 0.6], [16, 1.4], [18, 2.4]]) } }),
  },
  {
    group: "parcels", needs: "parcels", opacity: ["line-opacity"],
    spec: (t) => ({ id: "parcel-line", type: "line", source: "parcels", "source-layer": "parcels",
      paint: { "line-color": PALETTES[t].parcelLine, "line-opacity": PALETTES[t].parcelLineOpacity,
        "line-width": zoomWidth([[14, 0.3], [16, 0.7], [19, 1.4]]) } }),
  },
  // Roads over the fills, quietest first (a white gap in light, warm arterials in dark).
  roadLayer("local", 13, 0.6, "local"),
  roadLayer("minor", 12, 0.8, "minor"),
  roadLayer("ramp", 12, 0.6, "ramp"),
  roadLayer("major", 10, 1.0, "major"),
  roadLayer("highway", 10, 1.6, "highway"),
  {
    group: null, needs: "lot", opacity: [],
    spec: (t) => ({ id: "lot-edge", type: "line", source: "lot",
      paint: { "line-color": PALETTES[t].lotEdge, "line-width": 5, "line-opacity": 0.9 } }),
  },
  {
    group: null, needs: "lot", opacity: [],
    spec: (t) => ({ id: "lot-line", type: "line", source: "lot",
      paint: { "line-color": PALETTES[t].lot, "line-width": 2.5,
        // Approximate identity is drawn dashed: "confidence in the drawing" (Items 80, 89).
        "line-dasharray": ["case", ["==", ["get", "approximate"], true], ["literal", [2, 1.5]], ["literal", [1, 0]]] as unknown as number[] } }),
  },
  {
    group: "sales", needs: "sales", opacity: ["circle-opacity", "circle-stroke-opacity"],
    spec: (t) => ({ id: "sales-circle", type: "circle", source: "sales",
      paint: { "circle-color": PALETTES[t].sale, "circle-radius": zoomWidth([[13, 3], [16, 6], [18, 9]]),
        "circle-stroke-color": PALETTES[t].saleEdge, "circle-stroke-width": 1.5, "circle-opacity": 1, "circle-stroke-opacity": 1 } }),
  },
  {
    group: "transit", needs: "transit", opacity: ["circle-opacity", "circle-stroke-opacity"],
    spec: (t) => ({ id: "transit-circle", type: "circle", source: "transit",
      paint: { "circle-color": PALETTES[t].transit, "circle-radius": zoomWidth([[12, 3], [16, 6], [18, 8]]),
        "circle-stroke-color": PALETTES[t].transitEdge, "circle-stroke-width": 1.5, "circle-opacity": 1, "circle-stroke-opacity": 1 } }),
  },
  {
    group: "streets", needs: "base", opacity: ["text-opacity"],
    spec: (t) => ({ id: "road-label", type: "symbol", source: "base", "source-layer": "road", minzoom: STREET_LABEL_MIN_ZOOM,
      filter: ["all", ["!=", ["get", "name"], ""], ["match", ["get", "kind"], ["highway", "major", "minor", "local"], true, false]],
      layout: { "symbol-placement": "line", "text-field": ["get", "name"], "text-font": ["Noto Sans Regular"],
        "text-size": zoomWidth([[15, 10.5], [18, 13]]), "symbol-spacing": 320, "text-max-angle": 30, "text-padding": 4 },
      paint: { "text-color": PALETTES[t].label, "text-halo-color": PALETTES[t].halo, "text-halo-width": 1.4, "text-opacity": 1 } }),
  },
  {
    group: "zoning", needs: "zoning", opacity: ["text-opacity"],
    spec: (t) => ({ id: "zoning-label", type: "symbol", source: "zoning", "source-layer": "zoning_label",
      layout: { "text-field": ["get", "zone_class"], "text-font": ["Noto Sans Regular"],
        "text-size": zoomWidth([[13, 10], [17, 13]]), "text-padding": 6, "text-allow-overlap": false },
      paint: { "text-color": PALETTES[t].zoningLabel, "text-halo-color": PALETTES[t].halo, "text-halo-width": 1.6, "text-opacity": 1 } }),
  },
];

export const LAYER_IDS = LAYERS.map((l) => l.spec("light").id);

/** The style layers that belong to a group. */
export function groupLayerIds(group: GroupId): string[] {
  return LAYERS.filter((l) => l.group === group).map((l) => l.spec("light").id);
}

// ---------------------------------------------------------------- the document

export interface StyleInput {
  theme: Theme;
  /** Absolute URL of the API (production: the page's origin; the workers don't resolve relative URLs, Item 68). */
  apiOrigin: string;
  /** Absolute URL the committed glyphs are served from. */
  glyphsBase: string;
  tiles: MapTiles;
}

const EMPTY = { type: "FeatureCollection", features: [] } as const;

/** The full style for the first paint. Later changes go through `themePaint` / `modeOpacity`, never a reload. */
export function buildStyle({ theme, apiOrigin, glyphsBase, tiles }: StyleInput): StyleSpecification {
  const sources: StyleSpecification["sources"] = {
    // The lot is drawn exactly: no simplification, and cut finely up to zoom 22.
    lot: { type: "geojson", data: EMPTY as never, tolerance: 0, maxzoom: 22 },
    sales: { type: "geojson", data: EMPTY as never },
    transit: { type: "geojson", data: EMPTY as never },
  };
  if (tiles.base) sources.base = { type: "vector", tiles: [`${apiOrigin}/api/map/tiles/base/{z}/{x}/{y}.mvt`], minzoom: tiles.base.minZoom, maxzoom: tiles.base.maxZoom };
  if (tiles.zoning) sources.zoning = { type: "vector", tiles: [`${apiOrigin}/api/map/tiles/zoning/{z}/{x}/{y}.mvt`], minzoom: tiles.zoning.minZoom, maxzoom: tiles.zoning.maxZoom };
  if (tiles.parcels) sources.parcels = { type: "vector", tiles: [`${apiOrigin}/api/discovery/tiles/{z}/{x}/{y}.mvt`], minzoom: tiles.parcels.minZoom, maxzoom: tiles.parcels.maxZoom, promoteId: undefined };
  const layers = LAYERS.filter((l) => l.needs === null || l.needs === "lot" || l.needs === "sales" || l.needs === "transit" || tiles[l.needs] != null)
    .map((l) => l.spec(theme));
  return {
    version: 8,
    glyphs: `${glyphsBase}/{fontstack}/{range}.pbf`,
    sources,
    layers,
  };
}

/** Every paint property of every layer for a theme: what a theme switch sets. */
export function themePaint(theme: Theme): Array<{ id: string; paint: Record<string, unknown> }> {
  return LAYERS.map((l) => {
    const s = l.spec(theme) as { id: string; paint?: Record<string, unknown> };
    return { id: s.id, paint: s.paint ?? {} };
  });
}

/** A group's layers in a mode: Off hides them (visibility); On restores the theme's opacity. */
export function modeOpacity(group: GroupId, mode: LayerMode, theme: Theme): Array<{ id: string; visible: boolean; paint: Record<string, unknown> }> {
  return LAYERS.filter((l) => l.group === group).map((l) => {
    const s = l.spec(theme) as { id: string; paint?: Record<string, unknown> };
    const paint: Record<string, unknown> = {};
    for (const p of l.opacity) paint[p] = s.paint?.[p] ?? 1;
    return { id: s.id, visible: mode !== "off", paint };
  });
}
