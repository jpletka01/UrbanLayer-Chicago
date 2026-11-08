// Which tile sets the server has, and the API's absolute origin for the map's tile URLs (map track M1).
import { API_BASE } from "../../lib/api";
import type { MapTiles } from "./mapStyle";

let infoPromise: Promise<MapTiles> | null = null;
/** Which tile sets the server has (once per page load). A failure means no base, not no map. */
export function loadMapInfo(): Promise<MapTiles> {
  infoPromise ??= fetch(`${API_BASE}/api/map/info`)
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => ({ base: j?.base ?? null, parcels: j?.parcels ?? null, zoning: j?.zoning ?? null }))
    .catch(() => ({ base: null, parcels: null, zoning: null }));
  return infoPromise;
}

/** The API's absolute origin: production builds have an empty base, and the tile workers don't resolve relative
    URLs (Item 68's lesson). */
export function apiOrigin(pageUrl: string = window.location.href): string {
  return new URL(`${API_BASE}/`, pageUrl).href.replace(/\/$/, "");
}

/** The lot outline the map draws (Item 92): the County's full-precision outline where it still matches today's
    lot, else PTAXSIM's (1 m rounding). Null when the server has none or can't be reached: the page's own outline
    stays. */
export async function fetchLotOutline(pin10: string, signal?: AbortSignal): Promise<GeoJSON.Geometry | null> {
  try {
    const r = await fetch(`${API_BASE}/api/map/lot?pin10=${encodeURIComponent(pin10)}`, { signal });
    if (!r.ok) return null;
    const j = await r.json();
    return j?.source === "county_2021" ? (j.geometry as GeoJSON.Geometry) : null;
  } catch {
    return null;
  }
}
