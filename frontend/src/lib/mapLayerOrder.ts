/** The small part of a Mapbox style layer needed to place the zoning wash. */
export interface MapStyleLayerLike {
  id: string;
  type?: string;
  "source-layer"?: string;
  sourceLayer?: string;
}

export interface MapStyleOrderRevision {
  roadInsertionId: string | null;
  revision: number;
}

const ROAD_TOKEN = /(?:^|[-_])(road|street|motorway|trunk|bridge|tunnel|path)(?:[-_]|$)/i;

function isRoadLayer(layer: MapStyleLayerLike): boolean {
  const sourceLayer = layer["source-layer"] ?? layer.sourceLayer ?? "";
  return ROAD_TOKEN.test(layer.id) || ROAD_TOKEN.test(sourceLayer);
}

/**
 * Pick the first road line in style order. A deck layer inserted immediately
 * before it sits above land/buildings but beneath every road stroke and label.
 * The fallbacks are intentionally conservative: beneath the first line, then
 * beneath the first symbol, is safer than silently putting a thematic wash on
 * top of the basemap when a future Mapbox style renames its road layers.
 */
export function selectRoadLineInsertionPoint(layers: readonly MapStyleLayerLike[]): string | null {
  return layers.find((layer) => layer.type === "line" && isRoadLayer(layer))?.id
    ?? layers.find((layer) => layer.type === "line")?.id
    ?? layers.find((layer) => layer.type === "symbol")?.id
    ?? null;
}

/** One pure transition used by the hook on every Mapbox `style.load`. */
export function reviseMapStyleOrder(
  previous: MapStyleOrderRevision,
  layers: readonly MapStyleLayerLike[],
): MapStyleOrderRevision {
  return {
    roadInsertionId: selectRoadLineInsertionPoint(layers),
    revision: previous.revision + 1,
  };
}
