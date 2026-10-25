export type ParcelMapVariant = "place" | "zoning" | "boundaries";
export type ParcelMapSource = "zoning" | "overlays" | "tif" | "ez";
export type ParcelMapAvailability = Record<ParcelMapSource, "available" | "unavailable">;

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
