// Discovery's server reads beyond the search itself (decision Item 104). Every count and every match comes from the
// server's evaluation (INV-1); these hooks only ask and hold the answers.
import { useEffect, useRef, useState } from "react";
import { API_BASE } from "../../lib/api";
import { runSearch } from "../../discovery/searchClient";
import type { PanelState, Registry, SpatialScope } from "../../discovery/types";
import { LOTS_MIN_ZOOM } from "./discoveryModel";
import type { ViewBox } from "./ExploreMap";

export interface ViewMatches {
  /** PIN10s of the matches in view (lot zoom only). */
  pins: string[];
  total: number;
  areaCounts: Record<string, number> | null;
  /** More matches than the map can outline at once (the server's point cap). */
  truncated: boolean;
}

/** The part of a view inside a search's own view (west, south, east, north), or null when they do not overlap. */
export function clipBox(view: [number, number, number, number], clip: [number, number, number, number] | null) {
  if (!clip) return view;
  const b: [number, number, number, number] = [Math.max(view[0], clip[0]), Math.max(view[1], clip[1]),
    Math.min(view[2], clip[2]), Math.min(view[3], clip[3])];
  return b[0] < b[2] && b[1] < b[3] ? b : null;
}

/** Explore with quick filters on: the server evaluates them for the current view (the whole city below lot zoom,
    where the areas carry the counts), debounced; the latest request wins. Null when no filter is on. */
export function useViewMatches(registry: Registry | null, panel: PanelState | null, view: ViewBox | null, delayMs = 350,
  includeUnusual = false, clip: [number, number, number, number] | null = null) {
  const [answer, setAnswer] = useState<{ key: string; data: ViewMatches | null; failed: boolean } | null>(null);
  const seq = useRef(0);
  const panelKey = panel ? JSON.stringify(panel) : "";
  const lotZoom = !!view && view.zoom >= LOTS_MIN_ZOOM;
  const viewKey = view && lotZoom ? view.bbox.map((v) => v.toFixed(4)).join(",") : "city";
  const clipKey = clip ? clip.join(",") : "";
  const key = `${panelKey}|${viewKey}|${includeUnusual}|${clipKey}`;
  const asking = !!registry && !!panel && !!view;
  useEffect(() => {
    if (!registry || !panel || !view) return;
    const id = ++seq.current;
    const controller = new AbortController();
    const setState = (s: { data: ViewMatches | null; loading: boolean; failed: boolean }) => setAnswer({ key, data: s.data, failed: s.failed });
    const timer = window.setTimeout(async () => {
      const bbox = lotZoom ? clipBox(view.bbox, clip) : null;
      if (lotZoom && !bbox) {  // the view is outside the search's own view: nothing matches here
        if (id === seq.current) setState({ data: { pins: [], total: 0, areaCounts: null, truncated: false }, loading: false, failed: false });
        return;
      }
      const scope: SpatialScope | null = bbox ? { mode: "viewport", bbox } : (clip ? { mode: "viewport", bbox: clip } : null);
      try {
        const resp = await runSearch(
          { panelState: panel, scope, limit: 1, includeMatchIds: lotZoom, includeAreaCounts: true, includeUnusual },
          registry, controller.signal,
        );
        if (id !== seq.current) return;
        if (!resp) { setState({ data: null, loading: false, failed: true }); return; }
        setState({
          data: {
            // Every match's lot id (not the 5,000 capped points, largest first: a zoomed-out neighborhood outlined
            // only its biggest lots, owner's review 2026-11-16, Item 128).
            pins: (resp.matchIds ?? []).map((n) => String(n).padStart(10, "0")),
            total: resp.result.total,
            areaCounts: resp.areaCounts ?? null,
            truncated: !!resp.matchIdsTruncated,
          },
          loading: false, failed: false,
        });
      } catch {
        if (id === seq.current && !controller.signal.aborted) setState({ data: null, loading: false, failed: true });
      }
    }, delayMs);
    return () => { window.clearTimeout(timer); controller.abort(); };
    // panelKey, viewKey and clipKey stand for panel, view and clip.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [registry, panelKey, viewKey, delayMs, includeUnusual, clipKey]);
  if (!asking) return { data: null, loading: false, failed: false };
  // While a new answer is on its way the previous matches stay on the map.
  return { data: answer?.data ?? null, loading: answer?.key !== key, failed: answer?.key === key && answer.failed };
}

export interface Distribution {
  total: number;
  unknown: number;
  bins?: Array<{ min: number; max: number; n: number }>;
  values?: Record<string, number>;
}

const distCache = new Map<string, Promise<Distribution | null>>();
/** A filter's values across the index (coverage and histogram); cached per page load. */
export function fetchDistribution(filterId: string): Promise<Distribution | null> {
  let p = distCache.get(filterId);
  if (!p) {
    p = fetch(`${API_BASE}/api/discovery/distribution?filter=${encodeURIComponent(filterId)}`)
      .then((r) => (r.ok ? r.json() : null)).catch(() => null);
    distCache.set(filterId, p);
  }
  return p;
}

export function useDistribution(filterId: string | null): Distribution | null | undefined {
  const [d, setD] = useState<{ id: string; dist: Distribution | null } | null>(null);
  useEffect(() => {
    if (!filterId) return;
    let live = true;
    fetchDistribution(filterId).then((x) => { if (live) setD({ id: filterId, dist: x }); });
    return () => { live = false; };
  }, [filterId]);
  return d && d.id === filterId ? d.dist : undefined;
}
const contextCache = new Map<string, Promise<GeoJSON.FeatureCollection | null>>();
// A list of 50 cards would ask for 50 outlines at once; four at a time keeps the server's thread pool free.
const SHAPE_CONCURRENCY = 4;
let shapeActive = 0;
const shapeQueue: Array<() => void> = [];
function nextShape() {
  if (shapeActive >= SHAPE_CONCURRENCY) return;
  const run = shapeQueue.shift();
  if (run) { shapeActive += 1; run(); }
}

/** A lot and its neighbors (`/api/discovery/lot-context`), each with its room band, for a card's picture. */
export function fetchLotContext(pin10: string): Promise<GeoJSON.FeatureCollection | null> {
  let p = contextCache.get(pin10);
  if (!p) {
    p = new Promise<GeoJSON.FeatureCollection | null>((resolve) => {
      shapeQueue.push(() => {
        fetch(`${API_BASE}/api/discovery/lot-context?pin10=${encodeURIComponent(pin10)}`)
          .then((r) => (r.ok ? r.json() : null)).then((j) => resolve(j))
          .catch(() => { contextCache.delete(pin10); resolve(null); })
          .finally(() => { shapeActive -= 1; nextShape(); });
      });
      nextShape();
    });
    contextCache.set(pin10, p);
  }
  return p;
}

/** Project a lot and its neighbors into a w x h box, the lot centered and about a third of the width: SVG paths. */
export function contextPaths(fc: GeoJSON.FeatureCollection, w: number, h: number): Array<{ d: string; r: string | null; me: boolean }> {
  const ringsOf = (g: GeoJSON.Geometry) => (g.type === "Polygon" ? [g.coordinates[0]] : g.type === "MultiPolygon" ? g.coordinates.map((p) => p[0]) : []);
  const me = fc.features.find((f) => f.properties?.me);
  if (!me?.geometry) return [];
  const mine = ringsOf(me.geometry).flat();
  const lat0 = mine[0]?.[1] ?? 41.85;
  const k = Math.cos((lat0 * Math.PI) / 180);
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const [x, y] of mine) { minX = Math.min(minX, x * k); maxX = Math.max(maxX, x * k); minY = Math.min(minY, y); maxY = Math.max(maxY, y); }
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  // The lot takes about a third of the box's width (or 80% of its height), whichever is tighter.
  const s = Math.min((w * 0.34) / (maxX - minX || 1e-9), (h * 0.8) / (maxY - minY || 1e-9));
  const P = ([x, y]: number[]) => `${(w / 2 + (x * k - cx) * s).toFixed(1)},${(h / 2 - (y - cy) * s).toFixed(1)}`;
  return fc.features.filter((f) => f.geometry).map((f) => ({
    d: ringsOf(f.geometry!).map((r) => r.map((pt, i) => `${i ? "L" : "M"}${P(pt)}`).join("") + "Z").join(""),
    r: (f.properties?.r as string | null) ?? null,
    me: !!f.properties?.me,
  })).sort((a, b) => Number(a.me) - Number(b.me));
}

export interface Hood { slug: string; name: string; geometry: GeoJSON.Geometry }
let hoodsPromise: Promise<Hood[]> | null = null;
/** The City's 98 named neighborhoods (Item 104): names for the search box and chips, outlines for the map. */
export function fetchNeighborhoods(): Promise<Hood[]> {
  hoodsPromise ??= fetch(`${API_BASE}/api/discovery/neighborhoods`)
    .then((r) => (r.ok ? r.json() : { features: [] }))
    .then((fc: GeoJSON.FeatureCollection) => fc.features.map((f) => ({
      slug: String(f.properties?.slug), name: String(f.properties?.name), geometry: f.geometry,
    })))
    .catch(() => { hoodsPromise = null; return []; });
  return hoodsPromise;
}

export function useNeighborhoods(): Hood[] {
  const [hoods, setHoods] = useState<Hood[]>([]);
  useEffect(() => { let live = true; fetchNeighborhoods().then((h) => { if (live) setHoods(h); }); return () => { live = false; }; }, []);
  return hoods;
}
