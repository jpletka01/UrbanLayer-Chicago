// Business and point-of-interest names on every map (decision Item 72d, Jack 2026-11-07). A tester saw "business
// names everywhere": the Mapbox base styles (dark-v11, light-v11, satellite-streets-v12) print shop and venue
// names through their `poi-label` symbol layer, which competes with our parcels and data. Hidden on every
// `style.load`, because a theme or satellite swap (setStyle) brings the layer back. Street names, transit and
// station labels (`road-label*`, `transit-label`) stay: they are how a reader finds the place.

export interface StyleLayerLike {
  id: string;
  type: string;
}

interface MapLike {
  getStyle(): { layers?: StyleLayerLike[] } | undefined;
  setLayoutProperty(layerId: string, name: string, value: unknown): unknown;
}

/** The base style's point-of-interest label layers: symbol layers whose id names "poi". */
export function poiLabelLayerIds(layers: readonly StyleLayerLike[]): string[] {
  return layers.filter((l) => l.type === "symbol" && /poi/i.test(l.id)).map((l) => l.id);
}

/** Hide them. Never throws: a style without them, or a map mid-teardown, just keeps its labels. */
export function hidePoiLabels(map: MapLike): string[] {
  try {
    const ids = poiLabelLayerIds(map.getStyle()?.layers ?? []);
    for (const id of ids) map.setLayoutProperty(id, "visibility", "none");
    return ids;
  } catch {
    return [];
  }
}
