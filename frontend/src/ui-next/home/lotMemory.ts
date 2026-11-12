// The lots a visitor opened and the lots they saved, kept in this browser (Phase 8, owner 2026-11-12): the signed-in
// home shows Saved lots first, then the last six Recent lots with "Clear all" and a bookmark on each. Saved moves to
// the account when the Saved epic ships (Phase 9); until then nothing leaves the browser. A lot is keyed by its PIN
// when the Profile resolved one, else by its address.
import { useCallback, useEffect, useState } from "react";

export interface RememberedLot {
  key: string;
  address: string;
  pin: string | null;
  /** The zoning district, e.g. "RS-3". */
  zone: string | null;
  /** The community area's name. */
  area: string | null;
  /** The lot's outer ring, lon/lat, simplified, for the card's little drawing. */
  outline: Array<[number, number]> | null;
  /** When it was opened or saved (epoch ms). */
  at: number;
}

export const RECENT_KEY = "urbanlayer-next-recent-lots:v1";
export const SAVED_KEY = "urbanlayer-next-saved-lots:v1";
export const RECENT_MAX = 6;
const SAVED_MAX = 200;
const CHANGED = "urbanlayer-next-lots-changed";

export function lotKey(pin: string | null | undefined, address: string): string {
  return pin ? `pin:${pin}` : `addr:${address.trim().toLowerCase()}`;
}

/** The outer ring of a lot's outline, at most `max` points, rounded to about 10 cm. Null for anything else. */
export function outlineRing(geom: GeoJSON.Geometry | null | undefined, max = 40): Array<[number, number]> | null {
  if (!geom) return null;
  const ring = geom.type === "Polygon" ? geom.coordinates[0] : geom.type === "MultiPolygon" ? geom.coordinates[0]?.[0] : null;
  if (!ring || ring.length < 4) return null;
  const step = Math.max(1, Math.ceil(ring.length / max));
  const out: Array<[number, number]> = [];
  for (let i = 0; i < ring.length; i += step) out.push([+ring[i][0].toFixed(6), +ring[i][1].toFixed(6)]);
  return out.length >= 3 ? out : null;
}

/** An SVG path for a ring, fitted into w×h with padding, north up (lat grows upward). */
export function outlinePath(ring: Array<[number, number]>, w: number, h: number, pad = 6): string {
  const xs = ring.map((p) => p[0]), ys = ring.map((p) => p[1]);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  // Longitude degrees are shorter than latitude degrees at Chicago's latitude.
  const kx = Math.cos((((minY + maxY) / 2) * Math.PI) / 180);
  const spanX = Math.max((maxX - minX) * kx, 1e-9), spanY = Math.max(maxY - minY, 1e-9);
  const s = Math.min((w - 2 * pad) / spanX, (h - 2 * pad) / spanY);
  const ox = (w - spanX * s) / 2, oy = (h - spanY * s) / 2;
  return ring
    .map(([x, y], i) => `${i ? "L" : "M"}${(ox + (x - minX) * kx * s).toFixed(1)} ${(h - oy - (y - minY) * s).toFixed(1)}`)
    .join(" ") + " Z";
}

/** The Profile link for a remembered lot. */
export function lotHref(lot: Pick<RememberedLot, "pin" | "address">): string {
  const p = new URLSearchParams(lot.pin ? { pin: lot.pin, address: lot.address } : { address: lot.address });
  return `/scorecard?${p}`;
}

function read(key: string): RememberedLot[] {
  try {
    const raw = localStorage.getItem(key);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.filter((l) => l && typeof l.key === "string" && typeof l.address === "string") : [];
  } catch {
    return [];
  }
}

function write(key: string, list: RememberedLot[]): void {
  try { localStorage.setItem(key, JSON.stringify(list)); } catch { /* no storage: the home just stays empty */ }
  try { window.dispatchEvent(new Event(CHANGED)); } catch { /* not in a browser */ }
}

export const readRecent = () => read(RECENT_KEY);
export const readSaved = () => read(SAVED_KEY);

/** A lot was opened: newest first, once, six at most. */
export function rememberRecent(lot: Omit<RememberedLot, "at">, now = Date.now()): void {
  const list = readRecent().filter((l) => l.key !== lot.key);
  write(RECENT_KEY, [{ ...lot, at: now }, ...list].slice(0, RECENT_MAX));
}

export function clearRecent(): void {
  write(RECENT_KEY, []);
}

/** Save or unsave a lot; returns whether it is saved now. */
export function toggleSaved(lot: Omit<RememberedLot, "at">, now = Date.now()): boolean {
  const list = readSaved();
  if (list.some((l) => l.key === lot.key)) {
    write(SAVED_KEY, list.filter((l) => l.key !== lot.key));
    return false;
  }
  write(SAVED_KEY, [{ ...lot, at: now }, ...list].slice(0, SAVED_MAX));
  return true;
}

/** Recent and saved lots, kept current across this tab and others. */
export function useLotMemory() {
  const [recent, setRecent] = useState<RememberedLot[]>(readRecent);
  const [saved, setSaved] = useState<RememberedLot[]>(readSaved);
  useEffect(() => {
    const sync = () => { setRecent(readRecent()); setSaved(readSaved()); };
    window.addEventListener(CHANGED, sync);
    window.addEventListener("storage", sync);
    return () => { window.removeEventListener(CHANGED, sync); window.removeEventListener("storage", sync); };
  }, []);
  const isSaved = useCallback((key: string) => saved.some((l) => l.key === key), [saved]);
  return { recent, saved, isSaved, toggleSaved, clearRecent };
}
