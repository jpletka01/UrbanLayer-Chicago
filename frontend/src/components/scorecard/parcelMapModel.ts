import {
  boundaryColorCSS,
  boundaryFillColor,
  boundaryLineColor,
  overlayLabel,
  zoneColorCSS,
  type BoundaryFamily,
  type MapTheme,
} from "../../lib/mapColors";
import {
  mapFeatureConfidence,
  type MapFeatureConfidence,
  type ParcelMapLayers,
  type ParcelMapSource,
  type ZoningLabelPoint,
} from "../../lib/parcelMap";

export const ZONE_LABEL_MIN_ZOOM = 14.25;

export interface ZoningLegendModelEntry {
  zoneClass: string;
  swatchCSS: string;
  count: number;
  lowConfidenceCount: number;
  /** Untouched government properties from the first feature in this class. */
  properties: GeoJSON.GeoJsonProperties;
}

export interface ZoningLabelModelEntry {
  zoneClass: string;
  position: [number, number];
  /** Untouched government properties paired back to the exact class. */
  properties: GeoJSON.GeoJsonProperties;
}

export interface ZoningMapModel {
  /** Renderable and pickable features only; withheld features never cross this seam. */
  featureCollection: GeoJSON.FeatureCollection;
  legend: ZoningLegendModelEntry[];
  labels: ZoningLabelModelEntry[];
  visibleCount: number;
  withheldCount: number;
}

function exactZoneClass(properties: GeoJSON.GeoJsonProperties): string {
  return String(properties?.ZONE_CLASS ?? "").trim();
}

/**
 * The only label coordinates accepted here are the backend polylabel anchors.
 * Missing anchors stay missing so this seam can never drift back to browser
 * ring centroids. Entries are deduplicated by exact district class.
 */
export function buildZoningMapModel(
  zoning: GeoJSON.FeatureCollection | null | undefined,
  anchors: readonly ZoningLabelPoint[] | null | undefined,
  theme: MapTheme,
): ZoningMapModel {
  const visibleFeatures: GeoJSON.Feature[] = [];
  let withheldCount = 0;
  const byClass = new Map<string, {
    properties: GeoJSON.GeoJsonProperties;
    count: number;
    lowConfidenceCount: number;
  }>();
  for (const feature of zoning?.features ?? []) {
    const confidence = mapFeatureConfidence(feature);
    if (confidence === "withheld") {
      withheldCount += 1;
      continue;
    }
    visibleFeatures.push(feature);
    const zoneClass = exactZoneClass(feature.properties);
    if (!zoneClass) continue;
    const existing = byClass.get(zoneClass);
    if (existing) {
      existing.count += 1;
      if (confidence === "low") existing.lowConfidenceCount += 1;
    } else {
      byClass.set(zoneClass, {
        properties: feature.properties,
        count: 1,
        lowConfidenceCount: confidence === "low" ? 1 : 0,
      });
    }
  }

  const legend = [...byClass.entries()].map(([zoneClass, entry]) => ({
    zoneClass,
    swatchCSS: zoneColorCSS(zoneClass, theme),
    count: entry.count,
    lowConfidenceCount: entry.lowConfidenceCount,
    properties: entry.properties,
  }));

  const seenLabels = new Set<string>();
  const labels: ZoningLabelModelEntry[] = [];
  for (const anchor of anchors ?? []) {
    const zoneClass = String(anchor.zone_class ?? "").trim();
    const entry = byClass.get(zoneClass);
    if (!zoneClass || !entry || seenLabels.has(zoneClass)) continue;
    if (!Array.isArray(anchor.position) || anchor.position.length !== 2
      || !anchor.position.every(Number.isFinite)) continue;
    seenLabels.add(zoneClass);
    labels.push({ zoneClass, position: anchor.position, properties: entry.properties });
  }

  return {
    featureCollection: { type: "FeatureCollection", features: visibleFeatures },
    legend,
    labels,
    visibleCount: visibleFeatures.length,
    withheldCount,
  };
}

export function zoneLabelsVisible(zoom: number): boolean {
  return zoom >= ZONE_LABEL_MIN_ZOOM;
}

export interface BoundaryRenderModelEntry {
  id: string;
  source: Exclude<ParcelMapSource, "zoning">;
  family: BoundaryFamily;
  feature: GeoJSON.Feature;
  confidence: MapFeatureConfidence;
  fillColor: [number, number, number, number];
  lineColor: [number, number, number, number];
  swatchCSS: string;
  label: string;
  name: string;
  area: number;
  ordinal: number;
}

export interface BoundaryLegendModelEntry {
  key: string;
  source: Exclude<ParcelMapSource, "zoning">;
  family: BoundaryFamily;
  swatchCSS: string;
  label: string;
  name: string;
  count: number;
  lowConfidenceCount: number;
}

export interface BoundarySourceCount {
  visible: number;
  withheld: number;
}

export interface BoundaryMapModel {
  entries: BoundaryRenderModelEntry[];
  legend: BoundaryLegendModelEntry[];
  counts: Record<Exclude<ParcelMapSource, "zoning">, BoundarySourceCount>;
}

function ringArea(ring: GeoJSON.Position[]): number {
  let twice = 0;
  for (let i = 0; i < ring.length; i += 1) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % ring.length];
    twice += x1 * y2 - x2 * y1;
  }
  return Math.abs(twice) / 2;
}

function polygonArea(coordinates: GeoJSON.Position[][]): number {
  if (coordinates.length === 0) return 0;
  return Math.max(0, ringArea(coordinates[0])
    - coordinates.slice(1).reduce((sum, hole) => sum + ringArea(hole), 0));
}

/** Degree-squared area is sufficient for deterministic broad-to-narrow order. */
export function approximateFeatureArea(feature: GeoJSON.Feature): number {
  const geometry = feature.geometry;
  if (!geometry) return 0;
  if (geometry.type === "Polygon") return polygonArea(geometry.coordinates);
  if (geometry.type === "MultiPolygon") {
    return geometry.coordinates.reduce((sum, polygon) => sum + polygonArea(polygon), 0);
  }
  return 0;
}

function boundaryEntry(
  id: string,
  source: Exclude<ParcelMapSource, "zoning">,
  family: BoundaryFamily,
  feature: GeoJSON.Feature,
  label: string,
  name: string,
  theme: MapTheme,
  ordinal: number,
): BoundaryRenderModelEntry {
  return {
    id,
    source,
    family,
    feature,
    confidence: mapFeatureConfidence(feature),
    fillColor: boundaryFillColor(family, theme),
    lineColor: boundaryLineColor(family, theme),
    swatchCSS: boundaryColorCSS(family, theme),
    label,
    name,
    area: approximateFeatureArea(feature),
    ordinal,
  };
}

/** Broad boundaries paint first; narrow special-purpose overlays remain legible. */
export function buildBoundaryMapModel(
  layers: Pick<ParcelMapLayers, "overlays" | "tif" | "ez"> | null | undefined,
  theme: MapTheme,
): BoundaryMapModel {
  const counts: BoundaryMapModel["counts"] = {
    overlays: { visible: 0, withheld: 0 },
    tif: { visible: 0, withheld: 0 },
    ez: { visible: 0, withheld: 0 },
  };
  if (!layers) return { entries: [], legend: [], counts };
  const entries: BoundaryRenderModelEntry[] = [];
  let ordinal = 0;

  for (const [index, feature] of (layers.overlays?.features ?? []).entries()) {
    const confidence = mapFeatureConfidence(feature);
    if (confidence === "withheld") {
      counts.overlays.withheld += 1;
      continue;
    }
    counts.overlays.visible += 1;
    const properties = feature.properties ?? {};
    const type = String(properties.overlay_type ?? properties.layer_type ?? "overlay");
    const name = String(properties.NAME ?? properties.DIST_NAME ?? properties.PD_NAME ?? properties.name ?? "");
    entries.push(boundaryEntry(
      `overlay-districts-${index}`,
      "overlays",
      "overlay",
      feature,
      overlayLabel(type) || type.replace(/_/g, " "),
      name,
      theme,
      ordinal++,
    ));
  }

  if (layers.tif) {
    const name = String(layers.tif.properties?.name ?? "TIF");
    const feature = {
      ...layers.tif,
      properties: { ...layers.tif.properties, __kind: "TIF", name, zone_type: "tif" },
    } as GeoJSON.Feature;
    if (mapFeatureConfidence(feature) === "withheld") {
      counts.tif.withheld += 1;
    } else {
      counts.tif.visible += 1;
      entries.push(boundaryEntry(
        "incentive-zones-tif",
        "tif",
        "tif",
        feature,
        "TIF",
        name,
        theme,
        ordinal++,
      ));
    }
  }

  if (layers.ez) {
    const name = String(layers.ez.properties?.name ?? "Enterprise Zone");
    const feature = {
      ...layers.ez,
      properties: { ...layers.ez.properties, __kind: "Enterprise Zone", name, zone_type: "enterprise_zone" },
    } as GeoJSON.Feature;
    if (mapFeatureConfidence(feature) === "withheld") {
      counts.ez.withheld += 1;
    } else {
      counts.ez.visible += 1;
      entries.push(boundaryEntry(
        "incentive-zones-enterprise-zone",
        "ez",
        "enterprise_zone",
        feature,
        "Enterprise Zone",
        name,
        theme,
        ordinal,
      ));
    }
  }

  entries.sort((a, b) => (b.area - a.area) || (a.ordinal - b.ordinal));
  const legendByKey = new Map<string, BoundaryLegendModelEntry>();
  for (const entry of entries) {
    const key = `${entry.source}|${entry.label}|${entry.name}`;
    const existing = legendByKey.get(key);
    if (existing) {
      existing.count += 1;
      if (entry.confidence === "low") existing.lowConfidenceCount += 1;
    } else {
      legendByKey.set(key, {
        key,
        source: entry.source,
        family: entry.family,
        swatchCSS: entry.swatchCSS,
        label: entry.label,
        name: entry.name,
        count: 1,
        lowConfidenceCount: entry.confidence === "low" ? 1 : 0,
      });
    }
  }

  return { entries, legend: [...legendByKey.values()], counts };
}

/** Compatibility export retained for the M2 model seam and its callers. */
export function buildBoundaryRenderModel(
  layers: Pick<ParcelMapLayers, "overlays" | "tif" | "ez"> | null | undefined,
  theme: MapTheme,
): BoundaryRenderModelEntry[] {
  return buildBoundaryMapModel(layers, theme).entries;
}
