export type ParcelMapVariant = "place" | "zoning" | "boundaries";
export type ParcelMapSource = "zoning" | "overlays" | "tif" | "ez";
export type ParcelMapAvailability = Record<ParcelMapSource, "available" | "unavailable">;
export type ParcelMapLayerState = "on" | "dim" | "off";
export type MapFeatureConfidence = "standard" | "low" | "withheld";

export const PARCEL_MAP_LAYER_OPACITY: Record<ParcelMapLayerState, number> = {
  on: 1,
  dim: 0.3,
  off: 0,
};

/**
 * Confidence is supplied by the server on feature properties. Existing
 * authoritative government polygons predate the field, so absence keeps the
 * adopted standard's explicit `standard` default. No geometry heuristic lives
 * in the browser.
 */
export function mapFeatureConfidence(feature: GeoJSON.Feature): MapFeatureConfidence {
  const state = feature.properties?.confidence;
  return state === "low" || state === "withheld" ? state : "standard";
}

export function mapFeatureIsRendered(
  feature: GeoJSON.Feature,
  layerState: ParcelMapLayerState,
): boolean {
  return layerState !== "off" && mapFeatureConfidence(feature) !== "withheld";
}

/** Low confidence halves fill alpha; Dim applies its independent 0.30 multiplier. */
export function mapFeatureFillAlpha(
  alpha: number,
  feature: GeoJSON.Feature,
): number {
  return Math.round(alpha * (mapFeatureConfidence(feature) === "low" ? 0.5 : 1));
}

export function mapFeatureHasDashedOutline(feature: GeoJSON.Feature): boolean {
  return mapFeatureConfidence(feature) === "low";
}

export interface ZoningLabelPoint {
  zone_class: string;
  position: [number, number];
}

export interface ParcelMapLayers {
  zoning: GeoJSON.FeatureCollection | null;
  zoning_labels: ZoningLabelPoint[];
  overlays: GeoJSON.FeatureCollection | null;
  tif: GeoJSON.Feature | null;
  ez: GeoJSON.Feature | null;
  availability: ParcelMapAvailability;
}

/** Sources whose geometry could not be checked for this scoped map. */
export function unavailableParcelMapSources(
  variant: ParcelMapVariant,
  availability: Partial<ParcelMapAvailability> | null | undefined,
): ParcelMapSource[] {
  if (variant === "place" || !availability) return [];
  const sources: ParcelMapSource[] = variant === "zoning"
    ? ["zoning"]
    : ["overlays", "tif", "ez"];
  return sources.filter((source) => availability[source] === "unavailable");
}
