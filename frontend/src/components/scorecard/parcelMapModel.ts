import {
  boundaryColorCSS,
  boundaryFillColor,
  boundaryLineColor,
  overlayLabel,
  zoneColorCSS,
  type BoundaryFamily,
  type MapTheme,
} from "../../lib/mapColors";
import type { ParcelMapLayers, ZoningLabelPoint } from "../../lib/parcelMap";

export const ZONE_LABEL_MIN_ZOOM = 14.25;

export interface ZoningLegendModelEntry {
  zoneClass: string;
  swatchCSS: string;
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
  legend: ZoningLegendModelEntry[];
  labels: ZoningLabelModelEntry[];
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
  const byClass = new Map<string, GeoJSON.GeoJsonProperties>();
  for (const feature of zoning?.features ?? []) {
    const zoneClass = exactZoneClass(feature.properties);
    if (zoneClass && !byClass.has(zoneClass)) byClass.set(zoneClass, feature.properties);
  }

  const legend = [...byClass.entries()].map(([zoneClass, properties]) => ({
    zoneClass,
    swatchCSS: zoneColorCSS(zoneClass, theme),
    properties,
  }));

  const seenLabels = new Set<string>();
  const labels: ZoningLabelModelEntry[] = [];
  for (const anchor of anchors ?? []) {
    const zoneClass = String(anchor.zone_class ?? "").trim();
    const properties = byClass.get(zoneClass);
    if (!zoneClass || !properties || seenLabels.has(zoneClass)) continue;
    if (!Array.isArray(anchor.position) || anchor.position.length !== 2
      || !anchor.position.every(Number.isFinite)) continue;
    seenLabels.add(zoneClass);
    labels.push({ zoneClass, position: anchor.position, properties });
  }

  return { legend, labels };
}

export function zoneLabelsVisible(zoom: number): boolean {
  return zoom >= ZONE_LABEL_MIN_ZOOM;
}

export interface BoundaryRenderModelEntry {
  id: string;
  family: BoundaryFamily;
  feature: GeoJSON.Feature;
  fillColor: [number, number, number, number];
  lineColor: [number, number, number, number];
  swatchCSS: string;
  label: string;
  name: string;
  area: number;
  ordinal: number;
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
  family: BoundaryFamily,
  feature: GeoJSON.Feature,
  label: string,
  name: string,
  theme: MapTheme,
  ordinal: number,
): BoundaryRenderModelEntry {
  return {
    id,
    family,
    feature,
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
export function buildBoundaryRenderModel(
  layers: Pick<ParcelMapLayers, "overlays" | "tif" | "ez"> | null | undefined,
  theme: MapTheme,
): BoundaryRenderModelEntry[] {
  if (!layers) return [];
  const entries: BoundaryRenderModelEntry[] = [];
  let ordinal = 0;

  for (const [index, feature] of (layers.overlays?.features ?? []).entries()) {
    const properties = feature.properties ?? {};
    const type = String(properties.overlay_type ?? properties.layer_type ?? "overlay");
    const name = String(properties.NAME ?? properties.DIST_NAME ?? properties.PD_NAME ?? properties.name ?? "");
    entries.push(boundaryEntry(
      `overlay-districts-${index}`,
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
    entries.push(boundaryEntry(
      "incentive-zones-tif",
      "tif",
      feature,
      "TIF",
      name,
      theme,
      ordinal++,
    ));
  }

  if (layers.ez) {
    const name = String(layers.ez.properties?.name ?? "Enterprise Zone");
    const feature = {
      ...layers.ez,
      properties: { ...layers.ez.properties, __kind: "Enterprise Zone", name, zone_type: "enterprise_zone" },
    } as GeoJSON.Feature;
    entries.push(boundaryEntry(
      "incentive-zones-enterprise-zone",
      "enterprise_zone",
      feature,
      "Enterprise Zone",
      name,
      theme,
      ordinal,
    ));
  }

  return entries.sort((a, b) => (b.area - a.area) || (a.ordinal - b.ordinal));
}
