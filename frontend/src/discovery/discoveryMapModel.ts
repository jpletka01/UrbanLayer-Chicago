import type { PinPoint } from "./types";
import {
  landUseColor,
  landUseLegendKey,
  legendFor,
  upsideColor,
  upsideLegendKey,
  type DiscoveryColorMode,
  type DiscoveryLegendDefinition,
  type RGBA,
} from "./upsideColor";

export interface DiscoveryMapRenderPoint extends PinPoint {
  colorKey: string;
  fillColor: RGBA;
}

export interface DiscoveryMapLegendRow extends DiscoveryLegendDefinition {
  count: number;
}

export interface DiscoveryMapModel {
  renderPoints: DiscoveryMapRenderPoint[];
  legendRows: DiscoveryMapLegendRow[];
  returnedCount: number;
  unlocatedCount: number;
  omittedByCapCount: number;
}

/**
 * Derive every M1 map-coverage count from the pins response without inventing
 * coordinates or sampling the canonical result set.
 */
export function buildDiscoveryMapModel(
  points: PinPoint[],
  total: number,
  truncated: boolean,
  colorBy: DiscoveryColorMode = "land_use",
): DiscoveryMapModel {
  const mappable = points.filter((point) => {
    if (point.lat == null || point.lon == null) return false;
    return (
      Number.isFinite(point.lat) &&
      Number.isFinite(point.lon) &&
      point.lat >= -90 &&
      point.lat <= 90 &&
      point.lon >= -180 &&
      point.lon <= 180
    );
  });
  const renderPoints = mappable.map((point): DiscoveryMapRenderPoint => ({
    ...point,
    colorKey: colorBy === "upside"
      ? upsideLegendKey(point.upside)
      : landUseLegendKey(point.landUse),
    fillColor: colorBy === "upside"
      ? upsideColor(point.upside)
      : landUseColor(point.landUse),
  }));
  const counts = new Map<string, number>();
  for (const point of renderPoints) {
    counts.set(point.colorKey, (counts.get(point.colorKey) ?? 0) + 1);
  }

  return {
    renderPoints,
    legendRows: legendFor(colorBy).map((definition) => ({
      ...definition,
      count: counts.get(definition.key) ?? 0,
    })),
    returnedCount: points.length,
    unlocatedCount: points.length - mappable.length,
    // Only call the unseen tail a cap omission when the response says it was
    // truncated. A shorter non-truncated response proves no reason for a gap.
    omittedByCapCount: truncated ? Math.max(0, total - points.length) : 0,
  };
}
