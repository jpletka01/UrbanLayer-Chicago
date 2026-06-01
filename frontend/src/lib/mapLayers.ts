import { ScatterplotLayer } from "@deck.gl/layers";

type RGBA = [number, number, number, number];

interface PointLayerOptions<T> {
  getFillColor: (d: T) => RGBA;
  /** Constant radius (meters) or a per-point accessor. Defaults to 40. */
  getRadius?: number | ((d: T) => number);
  radiusMinPixels?: number;
  radiusMaxPixels?: number;
  /** Override position accessor; defaults to [d.longitude, d.latitude]. */
  getPosition?: (d: T) => [number, number];
}

/**
 * Factory for the crime/311/permit scatter layers shared by the landing map
 * and the sidebar map. Bakes in the common defaults (pickable, meter radius
 * units, lng/lat position) so call sites only specify what differs.
 */
export function pointLayer<T extends { longitude: number; latitude: number }>(
  id: string,
  data: T[],
  opts: PointLayerOptions<T>,
): ScatterplotLayer<T> {
  return new ScatterplotLayer<T>({
    id,
    data,
    getPosition: opts.getPosition ?? ((d) => [d.longitude, d.latitude]),
    getRadius: opts.getRadius ?? 40,
    getFillColor: opts.getFillColor,
    radiusMinPixels: opts.radiusMinPixels ?? 3,
    radiusMaxPixels: opts.radiusMaxPixels ?? 8,
    radiusUnits: "meters",
    pickable: true,
  });
}
