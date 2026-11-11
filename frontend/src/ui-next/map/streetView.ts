// Where to stand for Street View (owner's review, Item 94): Google opens the panorama nearest the point we send, and
// a point inside a lot is often nearer the alley behind it than the street in front. So the viewpoint is moved onto
// the street: for a lot, the nearest spot on its own address street (its frontage); otherwise the nearest named
// street. The heading faces the place that was clicked. Pure, except `loadedRoads`, which reads the road lines a map
// has loaded (both maps, Profile and Discovery, use it).
import type { Map as MLMap } from "maplibre-gl";

export type LonLat = [number, number];

export interface RoadLine {
  name: string;
  kind: string;
  /** One or more lines of [lon, lat] points. */
  lines: LonLat[][];
}

export interface Viewpoint {
  lat: number;
  lon: number;
  /** Compass heading, 0 = north, clockwise, toward the place. */
  heading?: number;
}

/** Beyond this the street is not the place's street; send the clicked point as is. */
export const MAX_SNAP_METERS = 60;

const M_PER_DEG_LAT = 110_540;
const mPerDegLon = (lat: number) => 111_320 * Math.cos((lat * Math.PI) / 180);

/** "1530 N Milwaukee Ave", "1530-32 N MILWAUKEE AVE Unit 2" → "n milwaukee ave" (number and unit dropped, case and
    spacing normalized), comparable with the road tiles' sign-style names. Null when nothing street-like is left. */
export function streetOfAddress(address: string | null | undefined): string | null {
  if (!address) return null;
  let s = address.replace(/^~/, "").trim();
  s = s.replace(/\b(unit|apt|#|ste|suite)\b.*$/i, "");
  s = s.replace(/^\d+[A-Z]?(-\d+[A-Z]?)?\s+/i, "");
  s = s.replace(/\s+/g, " ").trim().toLowerCase();
  return s ? s : null;
}

const norm = (name: string) => name.replace(/\s+/g, " ").trim().toLowerCase();

/** Compass bearing from a to b in degrees (0 = north, clockwise). */
export function bearing(a: LonLat, b: LonLat): number {
  const dx = (b[0] - a[0]) * mPerDegLon((a[1] + b[1]) / 2);
  const dy = (b[1] - a[1]) * M_PER_DEG_LAT;
  return (Math.atan2(dx, dy) * 180 / Math.PI + 360) % 360;
}

/** The nearest point on any of the lines to p, and its distance in metres (planar, fine at street scale). */
export function nearestOnLines(lines: LonLat[][], p: LonLat): { point: LonLat; meters: number } | null {
  const kx = mPerDegLon(p[1]);
  let best: { point: LonLat; meters: number } | null = null;
  for (const line of lines) {
    for (let i = 0; i + 1 < line.length; i++) {
      const ax = (line[i][0] - p[0]) * kx, ay = (line[i][1] - p[1]) * M_PER_DEG_LAT;
      const bx = (line[i + 1][0] - p[0]) * kx, by = (line[i + 1][1] - p[1]) * M_PER_DEG_LAT;
      const dx = bx - ax, dy = by - ay;
      const len2 = dx * dx + dy * dy;
      const t = len2 > 0 ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2)) : 0;
      const cx = ax + t * dx, cy = ay + t * dy;
      const d = Math.hypot(cx, cy);
      if (!best || d < best.meters) best = { point: [p[0] + cx / kx, p[1] + cy / M_PER_DEG_LAT], meters: d };
    }
  }
  return best;
}

/** Where to stand to see `target`: on its address street when one is given and loaded nearby, else on the nearest
    named non-expressway street; facing the target. The target itself (no heading) when no street is near. */
export function viewpointFor(target: LonLat, roads: RoadLine[], addressStreet: string | null): Viewpoint {
  const named = roads.filter((r) => r.name && r.kind !== "ramp");
  const own = addressStreet ? named.filter((r) => norm(r.name) === addressStreet) : [];
  const pool = own.length ? own : named.filter((r) => r.kind !== "highway");
  const hit = nearestOnLines(pool.flatMap((r) => r.lines), target);
  if (!hit || hit.meters > MAX_SNAP_METERS) return { lat: target[1], lon: target[0] };
  return { lat: hit.point[1], lon: hit.point[0], heading: Math.round(bearing(hit.point, target)) };
}

/** The City street centerlines the map has loaded from its "base" tiles (Street View's viewpoint snaps onto them). */
export function loadedRoads(map: Pick<MLMap, "getSource" | "querySourceFeatures">): RoadLine[] {
  if (!map.getSource("base")) return [];
  return map.querySourceFeatures("base", { sourceLayer: "road" }).map((f) => {
    const g = f.geometry;
    const lines = g.type === "LineString" ? [g.coordinates as LonLat[]]
      : g.type === "MultiLineString" ? (g.coordinates as LonLat[][]) : [];
    return { name: String(f.properties?.name ?? ""), kind: String(f.properties?.kind ?? ""), lines };
  });
}
