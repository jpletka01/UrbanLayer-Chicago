import type { PinPoint } from "./types";

export interface DiscoveryMapModel {
  mappable: PinPoint[];
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

  return {
    mappable,
    returnedCount: points.length,
    unlocatedCount: points.length - mappable.length,
    // Only call the unseen tail a cap omission when the response says it was
    // truncated. A shorter non-truncated response proves no reason for a gap.
    omittedByCapCount: truncated ? Math.max(0, total - points.length) : 0,
  };
}
