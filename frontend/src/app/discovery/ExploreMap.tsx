// Discovery's map (decision Item 104): the one map design (Items 80, 90-98) for the whole city. Same style document
// as the Profile's map (`mapStyle.buildStyle`: our base, zoning and lot tiles, theme repaint in place, failed tiles
// retried); Discovery adds the city's community areas below lot zoom, every lot filled by the chosen measure (the
// tiles' banded properties), matches as outlines only (owner, Item 99: no dots, no pins), the rest dimmed while a
// search or quick filter is on, the address ring, and a lot card that opens its Profile.
import { useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MLMap } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";
import { ArrowRight, LoaderCircle, MapPinOff, MapPinned, PersonStanding, UserCheck, X } from "lucide-react";
import { useThemeContext } from "../../contexts/ThemeContext";
import { profileAddress } from "../../discovery/rowFigures";
import { discoveryOutlineRow, fetchTransitStations, type DiscoveryOutlineLookup } from "../../lib/api";
import { apiOrigin, googleMapsUrl, loadMapInfo, streetViewUrl } from "../map/mapInfo";
import { loadedRoads, streetOfAddress, viewpointFor, type RoadLine } from "../map/streetView";
import { PIN_IMAGE, addPinImages } from "../map/pins";
import { PATTERN_IMAGE, addPatternImages } from "../map/patterns";
import {
  PALETTES, SATELLITE_BEFORE, SATELLITE_FILL_OPACITY, SATELLITE_LAYER, SATELLITE_ZONING_OPACITY, ZONING_COLORS, buildStyle, groupLayerIds, satelliteSource, themePaint, versionedTiles,
  type MapTiles, type Theme,
} from "../map/mapStyle";
import type { Basemap } from "../map/LayersControl";
import { watchTiles, type TileWatch } from "../map/tileWatch";
import { STROKE } from "../icons";
import { SuggestCorrection } from "./SuggestCorrection";
import {
  LOTS_MIN_ZOOM, NOT_DRAWN, cardModel, formatAt, parseAt, clampMiles, measureColorExpr, measureTexture, unknownMeasureFilter, milesBetween, ownerLine, ringPolygon, type MeasureId,
} from "./discoveryModel";

maplibregl.setWorkerUrl(workerUrl);

const CHICAGO: [number, number] = [-87.6847, 41.8366];
const CITY_ZOOM = 10.2;
const reducedMotion = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export interface ViewBox { bbox: [number, number, number, number]; zoom: number; center: [number, number] }
export interface Ring { lat: number; lon: number; miles: number }

export interface ExploreMapProps {
  measure: MeasureId;
  /** The PIN10s to outline (a search's or the view's matches); null = nothing is being searched. */
  matches: string[] | null;
  /** Community area -> matches, labeled on the city view. */
  areaCounts: Record<string, number> | null;
  ring: Ring | null;
  onRingChange?: (miles: number) => void;
  /** An address the visitor picked: a marker, and the camera goes there. */
  place: { lat: number; lon: number; label: string } | null;
  /** Where the camera should go (a new `seq` repeats it). */
  focus: { bbox?: [number, number, number, number]; center?: [number, number]; zoom?: number; seq: number } | null;
  /** Frame a new search's matches once (`key` changes per search). */
  fit?: { bbox: [number, number, number, number]; key: unknown } | null;
  showZoning: boolean;
  /** Rail lines, rail land and stations (Item 128); on by default. */
  showRail?: boolean;
  /** Standard (our style) or Satellite (Cook County's photos, opt-in from the Layers button, Item 128). */
  basemap?: Basemap;
  /** Satellite's photos didn't arrive (Cook County's image server not answering, Item 136): the page goes back to the
      map and says so, rather than a click that seems to do nothing. */
  onBasemapFailed?: () => void;
  /** The visitor's saved lots as pins (the Layers button's Saved lots, on by default; Item 128). */
  savedPoints?: Array<{ lat: number; lon: number; address: string }>;
  showSaved?: boolean;
  /** The places the search is limited to, outlined (a neighborhood's outline, or a community area by number). */
  highlight?: Array<{ kind: "hood"; geometry: GeoJSON.Geometry | null } | { kind: "area"; id: number }> | null;
  /** The Transit panel's walk, in miles: a ring of that size around every L stop (null = none). */
  walkMiles?: number | null;
  onView: (v: ViewBox) => void;
  onPickArea?: (ca: number) => void;
  /** The sort key for a lot card's row (the card shows the same row as the list). */
  sortKey: string;
  /** The clicked lot, when the page holds it (on a phone the page shows it in its bottom sheet, Item 129 §1). */
  picked?: Picked | null;
  onPickedChange?: Dispatch<SetStateAction<Picked | null>>;
  /** Draw the floating lot card over the map (laptop); false = the page shows the lot itself (phone sheet). */
  inlineCard?: boolean;
  /** Pixels of the map hidden under the page's bottom sheet: a picked lot is kept in view above them. */
  bottomInset?: number;
  className?: string;
}

const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

/** Each zoning family's middle color (the measure "zoning" fills lots with it). */
const ZONING_FAMILY_FILL: Record<string, string> = {
  residential: ZONING_COLORS.residential[1], business: ZONING_COLORS.business[1], commercial: ZONING_COLORS.business[1],
  manufacturing: ZONING_COLORS.manufacturing[1], downtown: ZONING_COLORS.downtown[1], planned: ZONING_COLORS.planned[0],
  park: ZONING_COLORS.park[0], transport: ZONING_COLORS.transport[0],
};

const NO_POINTS: Array<{ lat: number; lon: number; address: string }> = [];

/** A width only where the lot matches a search or is the lot the visitor clicked (feature state; the click outline
    is the owner's ask, Item 128), inside a zoom interpolation (zoom must be outermost). */
const matchW = (w: number) => ["case", ["any", ["boolean", ["feature-state", "match"], false],
  ["boolean", ["feature-state", "picked"], false]], w, 0];

function ownPaint(theme: Theme, measure: MeasureId, dim: boolean) {
  const p = PALETTES[theme];
  const lotOn = theme === "dark" ? 0.62 : 0.78;
  return {
    "lot-measure": {
      "fill-color": measureColorExpr(measure, ZONING_FAMILY_FILL),
      "fill-opacity": (dim
        ? ["case", ["boolean", ["feature-state", "match"], false], lotOn, 0.14]
        : lotOn) as unknown,
    },
    "lot-match-edge": {
      "line-color": p.lotEdge,
      "line-width": ["interpolate", ["linear"], ["zoom"], 14, matchW(3), 17, matchW(5.5)],
      "line-opacity": 0.95,
    },
    "lot-match": {
      "line-color": p.lot,
      "line-width": ["interpolate", ["linear"], ["zoom"], 14, matchW(1.4), 17, matchW(2.6)],
    },
    "area-line": { "line-color": p.label, "line-opacity": 0.45, "line-width": 1 },
    "area-fill": {
      "fill-color": p.lot,
      "fill-opacity": ["case", [">", ["coalesce", ["get", "n"], 0], 0], ["interpolate", ["linear"], ["get", "share"], 0, 0.06, 1, 0.34], 0] as unknown,
    },
    "area-label": { "text-color": p.label, "text-halo-color": p.halo, "text-halo-width": 1.6 },
    "grid-measure": { "fill-color": measureColorExpr(measure, ZONING_FAMILY_FILL), "fill-opacity": theme === "dark" ? 0.62 : 0.78 },
    "walk-fill": { "fill-color": p.lot, "fill-opacity": 0.07 },
    "walk-line": { "line-color": p.lot, "line-width": 1.2, "line-opacity": 0.55 },
    "ring-fill": { "fill-color": p.lot, "fill-opacity": 0.06 },
    "ring-line": { "line-color": p.lot, "line-width": 2, "line-dasharray": [2, 1.5] },
    "highlight-edge": { "line-color": p.lotEdge, "line-width": 6, "line-opacity": 0.9 },
    "highlight-line": { "line-color": p.lot, "line-width": 2.5 },
    "ring-handle": { "circle-color": p.lotEdge, "circle-stroke-color": p.lot, "circle-stroke-width": 2.5, "circle-radius": 8 },
    "place-dot": { "circle-color": p.lot, "circle-stroke-color": p.lotEdge, "circle-stroke-width": 3, "circle-radius": 7 },
  } as Record<string, Record<string, unknown>>;
}

function addOwnLayers(map: MLMap, theme: Theme, measure: MeasureId, dim: boolean, hasParcels: boolean, grid: MapTiles["grid"]) {
  const paint = ownPaint(theme, measure, dim);
  map.addSource("walk", { type: "geojson", data: EMPTY });
  map.addSource("highlight", { type: "geojson", data: EMPTY });
  map.addSource("areas", { type: "geojson", data: EMPTY });
  map.addSource("area-labels", { type: "geojson", data: EMPTY });
  map.addSource("ring", { type: "geojson", data: EMPTY });
  map.addSource("ring-handle", { type: "geojson", data: EMPTY });
  map.addSource("place", { type: "geojson", data: EMPTY });
  const before = map.getLayer("road-local") ? "road-local" : undefined;
  if (hasParcels) {
    // A lot whose measure is unknown is hatched (dots), never colored as if it were low.
    map.addLayer({ id: "lot-unknown", type: "fill", source: "parcels", "source-layer": "parcels",
      filter: unknownFilter(measure), paint: { "fill-pattern": PATTERN_IMAGE("dots", theme), "fill-opacity": dim ? 0.35 : 1 } }, map.getLayer("parcel-line") ? "parcel-line" : before);
    map.addLayer({ id: "lot-measure", type: "fill", source: "parcels", "source-layer": "parcels", filter: NOT_DRAWN as never,
      paint: paint["lot-measure"] as never }, map.getLayer("parcel-line") ? "parcel-line" : before);
    // Marks over some measure colors (land in use: "P" on surface parking, "+" on road land), so color isn't alone.
    const tex = measureTexture(measure, theme);
    map.addLayer({ id: "lot-texture", type: "fill", source: "parcels", "source-layer": "parcels",
      filter: (tex?.filter ?? NONE) as never, paint: { "fill-pattern": (tex?.pattern ?? PATTERN_IMAGE("plus", theme)) as never,
        "fill-opacity": dim ? 0.35 : 1 } }, map.getLayer("parcel-line") ? "parcel-line" : before);
  }
  // Zoomed out, the city is a grid of about a block each in the same measure (Item 104), so the map is never empty.
  if (grid) {
    map.addSource("grid", { type: "vector", tiles: [versionedTiles(`${apiOrigin()}/api/discovery/grid/{z}/{x}/{y}.mvt`, grid)], minzoom: grid.minZoom, maxzoom: grid.maxZoom });
    map.addLayer({ id: "grid-unknown", type: "fill", source: "grid", "source-layer": "grid", maxzoom: LOTS_MIN_ZOOM,
      filter: unknownFilter(measure), paint: { "fill-pattern": PATTERN_IMAGE("dots", theme), "fill-opacity": 0.7 } }, before);
    map.addLayer({ id: "grid-measure", type: "fill", source: "grid", "source-layer": "grid", maxzoom: LOTS_MIN_ZOOM,
      paint: paint["grid-measure"] as never }, before);
    const gtex = measureTexture(measure, theme);
    map.addLayer({ id: "grid-texture", type: "fill", source: "grid", "source-layer": "grid", maxzoom: LOTS_MIN_ZOOM,
      filter: (gtex?.filter ?? NONE) as never, paint: { "fill-pattern": (gtex?.pattern ?? PATTERN_IMAGE("plus", theme)) as never } }, before);
  }
  map.addLayer({ id: "area-fill", type: "fill", source: "areas", maxzoom: LOTS_MIN_ZOOM, paint: paint["area-fill"] as never }, before);
  map.addLayer({ id: "walk-fill", type: "fill", source: "walk", paint: paint["walk-fill"] as never }, before);
  map.addLayer({ id: "walk-line", type: "line", source: "walk", paint: paint["walk-line"] as never }, before);
  map.addLayer({ id: "area-line", type: "line", source: "areas", maxzoom: LOTS_MIN_ZOOM + 0.5, paint: paint["area-line"] as never }, before);
  map.addLayer({ id: "ring-fill", type: "fill", source: "ring", paint: paint["ring-fill"] as never }, before);
  if (hasParcels) {
    map.addLayer({ id: "lot-match-edge", type: "line", source: "parcels", "source-layer": "parcels", paint: paint["lot-match-edge"] as never });
    map.addLayer({ id: "lot-match", type: "line", source: "parcels", "source-layer": "parcels", paint: paint["lot-match"] as never });
  }
  map.addLayer({ id: "ring-line", type: "line", source: "ring", paint: paint["ring-line"] as never });
  map.addLayer({ id: "highlight-edge", type: "line", source: "highlight", paint: paint["highlight-edge"] as never });
  map.addLayer({ id: "highlight-line", type: "line", source: "highlight", paint: paint["highlight-line"] as never });
  map.addLayer({
    id: "area-label", type: "symbol", source: "area-labels", maxzoom: LOTS_MIN_ZOOM,
    layout: { "text-field": ["get", "text"], "text-font": ["Noto Sans Regular"], "text-size": 12, "text-padding": 4,
      "text-max-width": 8, "text-line-height": 1.15 },
    paint: paint["area-label"] as never,
  });
  map.addLayer({ id: "place-dot", type: "circle", source: "place", paint: paint["place-dot"] as never });
  map.addLayer({ id: "ring-handle", type: "circle", source: "ring-handle", paint: paint["ring-handle"] as never });
}

const unknownFilter = (m: MeasureId) => unknownMeasureFilter(m) as never;
const NONE = ["==", ["get", "__none__"], "__never__"];

/** A lot's card: the list's own row (`/api/discovery/parcel`). */
/** `ll` = the click on the ground [lon, lat]; `roads` = the street lines loaded at the click (Street View, Item 94). */
export interface Picked { pin10: string; at: [number, number]; size: [number, number]; ll: [number, number]; roads: RoadLine[]; lookup: DiscoveryOutlineLookup | null }

export function ExploreMap({
  measure, matches, areaCounts, ring, onRingChange, place, focus, fit = null, showZoning, showRail = true, basemap = "standard", onBasemapFailed, savedPoints = NO_POINTS, showSaved = true, walkMiles = null, highlight = null, onView, onPickArea, sortKey,
  picked: pickedProp, onPickedChange, inlineCard = true, bottomInset = 0, className,
}: ExploreMapProps) {
  const { t, i18n } = useTranslation("next");
  const { resolvedTheme } = useThemeContext();
  const theme: Theme = resolvedTheme === "dark" ? "dark" : "light";
  const box = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);
  const [tiles, setTiles] = useState<MapTiles | null>(null);
  const [ownPicked, setOwnPicked] = useState<Picked | null>(null);
  // Held by the page when it passes `onPickedChange` (the phone's lot sheet), else here.
  const picked = onPickedChange ? pickedProp ?? null : ownPicked;
  const setPicked = onPickedChange ?? setOwnPicked;
  // The clicked lot is outlined like a match while its card is open; a click elsewhere or closing the card clears it.
  const pickedId = useRef<number | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.getSource("parcels")) return;
    const next = picked ? Number(picked.pin10) : null;
    if (pickedId.current === next) return;
    if (pickedId.current != null) map.setFeatureState({ source: "parcels", sourceLayer: "parcels", id: pickedId.current }, { picked: false });
    if (next != null) map.setFeatureState({ source: "parcels", sourceLayer: "parcels", id: next }, { picked: true });
    pickedId.current = next;
  }, [picked, ready]);
  const [areas, setAreas] = useState<GeoJSON.FeatureCollection | null>(null);
  const live = useRef({ theme, measure, dim: matches !== null, onView, onPickArea, onRingChange, ring, setPicked, onBasemapFailed });
  useEffect(() => { live.current = { theme, measure, dim: matches !== null, onView, onPickArea, onRingChange, ring, setPicked, onBasemapFailed }; });
  // Whether Satellite's photo tiles are arriving since it was switched on (Item 136).
  const satWatch = useRef<TileWatch | null>(null);

  // Create the map once.
  useEffect(() => {
    let cancelled = false;
    let map: MLMap | null = null;
    const startAt = parseAt(new URLSearchParams(window.location.search).get("at"));
    loadMapInfo().then((info) => {
      if (cancelled || !box.current) return;
      setTiles(info);
      let m: MLMap;
      try {
        m = new maplibregl.Map({
          container: box.current,
          style: buildStyle({ theme: live.current.theme, apiOrigin: apiOrigin(), glyphsBase: new URL("/map/fonts", window.location.href).href, tiles: info }),
          // A view named in the URL (`at`, owner's map review) wins over the whole city.
          center: startAt?.center ?? CHICAGO, zoom: startAt?.zoom ?? CITY_ZOOM, minZoom: 10, maxBounds: [[-88.3, 41.5], [-87.2, 42.2]],
          attributionControl: false, dragRotate: false, pitchWithRotate: false, fadeDuration: 0,
        });
      } catch (err) {
        console.warn("Map unavailable in this browser:", err);
        setError(true);
        return;
      }
      map = m;
      m.touchZoomRotate.disableRotation();
      // No credit button on the map (owner's look: the "i" was wasted space); the credits sit under the Layers row.
      m.on("webglcontextlost", () => undefined);
      let retryAt = 0;
      m.on("error", (e) => {
        const id = (e as unknown as { sourceId?: string }).sourceId;
        if (id === SATELLITE_LAYER) { satWatch.current?.error(); return; }
        if (!id || !["base", "zoning", "parcels"].includes(id)) { console.warn("map:", e.error ?? e); return; }
        const now = Date.now();
        if (now - retryAt < 4000) return;
        retryAt = now;
        window.setTimeout(() => {
          const src = m.getSource(id) as unknown as { tiles?: string[]; setTiles?: (t: string[]) => void } | undefined;
          if (src?.tiles && src.setTiles) src.setTiles(src.tiles);
        }, 1500);
      });
      // The pin and pattern images go in before the first tile is cut: a tile cut while a fill pattern is missing was
      // drawn without its zoning until the next zoom reloaded it (owner saw a quarter-mile square missing at
      // 1601 N Milwaukee, 2026-11-11). The handlers below stay as a safety net.
      try { addPinImages(m); addPatternImages(m); } catch { /* the style isn't ready: the handlers add them */ }
      m.on("styleimagemissing", () => { addPinImages(m); addPatternImages(m); });
      m.once("load", () => {
        if (cancelled) return;
        addPinImages(m);
        addPatternImages(m);
        // Discovery draws matches as outlines only: the parcel layer's match fill stays off.
        if (m.getLayer("parcel-fill")) m.setLayoutProperty("parcel-fill", "visibility", "none");
        addOwnLayers(m, live.current.theme, live.current.measure, live.current.dim, !!info.parcels, info.grid ?? null);
        setReady(true);
        report(m);
      });
      const report = (mm: MLMap) => {
        const b = mm.getBounds();
        const c = mm.getCenter();
        live.current.onView({ bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], zoom: mm.getZoom(), center: [c.lng, c.lat] });
        // Keep the place in the URL without a new history entry, so Back from a lot's Profile returns here.
        const url = new URL(window.location.href);
        url.searchParams.set("at", formatAt([c.lng, c.lat], mm.getZoom()));
        window.history.replaceState(window.history.state, "", url.toString());
      };
      m.on("moveend", () => report(m));
      m.on("sourcedata", (e) => { if (e.sourceId === SATELLITE_LAYER && e.tile) satWatch.current?.loaded(); });
      m.on("click", (e) => {
        if (m.getZoom() < LOTS_MIN_ZOOM) {
          const hit = m.queryRenderedFeatures(e.point, { layers: ["area-fill", "area-line"].filter((l) => m.getLayer(l)) })[0];
          const ca = hit?.properties?.ca;
          if (ca != null) live.current.onPickArea?.(Number(ca));
          return;
        }
        const f = m.getLayer("lot-measure") ? m.queryRenderedFeatures(e.point, { layers: ["lot-measure"] })[0] : undefined;
        if (!f || f.id == null) { live.current.setPicked(null); return; }
        const pin10 = String(f.id).padStart(10, "0");
        const c = m.getContainer();
        live.current.setPicked({ pin10, at: [e.point.x, e.point.y], size: [c.clientWidth, c.clientHeight], ll: [e.lngLat.lng, e.lngLat.lat], roads: loadedRoads(m), lookup: null });
      });
      m.on("mouseenter", "lot-measure", () => { m.getCanvas().style.cursor = "pointer"; });
      m.on("mouseleave", "lot-measure", () => { m.getCanvas().style.cursor = ""; });
      // The ring's handle resizes it (mouse and touch).
      const startDrag = (ev: maplibregl.MapMouseEvent | maplibregl.MapTouchEvent) => {
        if (!live.current.ring) return;
        ev.preventDefault();
        m.dragPan.disable();
        const move = (e2: maplibregl.MapMouseEvent | maplibregl.MapTouchEvent) => {
          const r = live.current.ring;
          if (r) live.current.onRingChange?.(clampMiles(milesBetween(r.lat, r.lon, e2.lngLat.lat, e2.lngLat.lng)));
        };
        const end = () => { m.off("mousemove", move); m.off("touchmove", move); m.dragPan.enable(); };
        m.on("mousemove", move);
        m.on("touchmove", move);
        m.once("mouseup", end);
        m.once("touchend", end);
      };
      m.on("mousedown", "ring-handle", startDrag);
      m.on("touchstart", "ring-handle", startDrag);
      m.on("mouseenter", "ring-handle", () => { m.getCanvas().style.cursor = "ew-resize"; });
      m.on("mouseleave", "ring-handle", () => { m.getCanvas().style.cursor = ""; });
      mapRef.current = m;
      if (import.meta.env.DEV) (window as unknown as { __exploreMap?: MLMap }).__exploreMap = m;
    });
    const watch = satWatch;
    return () => { cancelled = true; watch.current?.stop(); watch.current = null; map?.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => mapRef.current?.resize());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Theme, measure and dimming: repaint in place.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const { id, paint } of themePaint(theme)) {
      if (!map.getLayer(id)) continue;
      for (const [k, v] of Object.entries(paint)) map.setPaintProperty(id, k as never, v as never);
    }
    if (map.getLayer("grid-unknown")) {
      map.setFilter("grid-unknown", unknownFilter(measure));
      map.setPaintProperty("grid-unknown", "fill-pattern", PATTERN_IMAGE("dots", theme));
    }
    if (map.getLayer("lot-unknown")) {
      map.setFilter("lot-unknown", unknownFilter(measure));
      map.setPaintProperty("lot-unknown", "fill-pattern", PATTERN_IMAGE("dots", theme));
      map.setPaintProperty("lot-unknown", "fill-opacity", matches !== null ? 0.35 : 1);
    }
    for (const [id, paint] of Object.entries(ownPaint(theme, measure, matches !== null))) {
      if (!map.getLayer(id)) continue;
      for (const [k, v] of Object.entries(paint)) map.setPaintProperty(id, k as never, v as never);
    }
    const tex = measureTexture(measure, theme);
    for (const id of ["lot-texture", "grid-texture"]) {
      if (!map.getLayer(id)) continue;
      map.setFilter(id, (tex?.filter ?? NONE) as never);
      if (tex) map.setPaintProperty(id, "fill-pattern", tex.pattern as never);
      if (id === "lot-texture") map.setPaintProperty(id, "fill-opacity", matches !== null ? 0.35 : 1);
    }
  }, [theme, measure, matches, ready]);

  // Zoning on or off (off by default: the lots carry the measure).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const id of groupLayerIds("zoning")) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", showZoning ? "visible" : "none");
  }, [showZoning, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const data = { type: "FeatureCollection", features: savedPoints.map((p) => ({ type: "Feature", properties: { address: p.address },
      geometry: { type: "Point", coordinates: [p.lon, p.lat] } })) } as never;
    const src = map.getSource("saved-lots") as GeoJSONSource | undefined;
    if (src) src.setData(data);
    else {
      map.addSource("saved-lots", { type: "geojson", data });
      map.addLayer({ id: "saved-pin", type: "symbol", source: "saved-lots",
        layout: { "icon-image": PIN_IMAGE.saved, "icon-anchor": "bottom", "icon-allow-overlap": true, "icon-ignore-placement": true,
          "icon-size": ["interpolate", ["linear"], ["zoom"], 11, 0.6, 14, 0.85, 16, 1] as never } });
    }
    map.setLayoutProperty("saved-pin", "visibility", showSaved ? "visible" : "none");
  }, [savedPoints, showSaved, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const id of groupLayerIds("rail")) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", showRail ? "visible" : "none");
  }, [showRail, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const sat = basemap === "satellite";
    if (sat) {
      if (!map.getSource(SATELLITE_LAYER)) map.addSource(SATELLITE_LAYER, satelliteSource(t("map.layers.satelliteCredit")) as never);
      if (!map.getLayer(SATELLITE_LAYER)) {
        satWatch.current?.stop();
        satWatch.current = watchTiles(() => { satWatch.current = null; live.current.onBasemapFailed?.(); });
        const before = map.getLayer(SATELLITE_BEFORE) ? SATELLITE_BEFORE : map.getLayer("parcel-line") ? "parcel-line" : undefined;
        map.addLayer({ id: SATELLITE_LAYER, type: "raster", source: SATELLITE_LAYER, paint: { "raster-fade-duration": 0 } }, before);
      }
    } else {
      satWatch.current?.stop();
      satWatch.current = null;
      if (map.getLayer(SATELLITE_LAYER)) map.removeLayer(SATELLITE_LAYER);
      if (map.getSource(SATELLITE_LAYER)) map.removeSource(SATELLITE_LAYER);
    }
    // Over the photo the lots' colors and the zoning go see-through, so room to build and the photo both read.
    const own = ownPaint(live.current.theme, live.current.measure, live.current.dim);
    for (const id of ["lot-measure", "grid-measure"]) {
      if (map.getLayer(id)) map.setPaintProperty(id, "fill-opacity", (sat ? SATELLITE_FILL_OPACITY : own[id as "lot-measure"]["fill-opacity"]) as never);
    }
    if (map.getLayer("zoning-fill")) {
      map.setPaintProperty("zoning-fill", "fill-opacity", sat ? SATELLITE_ZONING_OPACITY : PALETTES[live.current.theme].zoningFill);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basemap, ready, theme, measure, matches]);  // after the theme effect, which resets these paints

  // Matches as outlines (feature state on the lot tiles).
  const marked = useRef<Set<string>>(new Set());
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !tiles?.parcels) return;
    const next = new Set(matches ?? []);
    for (const p of marked.current) if (!next.has(p)) map.removeFeatureState({ source: "parcels", sourceLayer: "parcels", id: Number(p) });
    for (const p of next) if (!marked.current.has(p)) map.setFeatureState({ source: "parcels", sourceLayer: "parcels", id: Number(p) }, { match: true });
    marked.current = next;
  }, [matches, ready, tiles]);

  // Community areas: their outlines once, their labels with the match counts.
  useEffect(() => {
    let live2 = true;
    fetch(`${apiOrigin()}/api/discovery/areas`).then((r) => (r.ok ? r.json() : null)).then((fc) => { if (live2 && fc) setAreas(fc); }).catch(() => undefined);
    return () => { live2 = false; };
  }, []);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !areas) return;
    const max = Math.max(1, ...Object.values(areaCounts ?? {}));
    const fmt = new Intl.NumberFormat(i18n.language.startsWith("es") ? "es-MX" : "en-US");
    const withCounts: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: areas.features.map((f) => {
        const n = areaCounts?.[String(f.properties?.ca)] ?? 0;
        return { ...f, properties: { ...f.properties, n, share: n / max } };
      }),
    };
    (map.getSource("areas") as GeoJSONSource | undefined)?.setData(withCounts);
    (map.getSource("area-labels") as GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features: areas.features.map((f) => {
        const n = areaCounts?.[String(f.properties?.ca)];
        return {
          type: "Feature",
          geometry: { type: "Point", coordinates: [f.properties?.lx, f.properties?.ly] },
          properties: { text: areaCounts ? (n ? `${f.properties?.name}\n${fmt.format(n)}` : "") : f.properties?.name },
        };
      }),
    });
  }, [areas, areaCounts, ready, i18n.language]);

  // The ring and the picked address.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource("ring") as GeoJSONSource | undefined)?.setData(ring
      ? { type: "FeatureCollection", features: [{ type: "Feature", geometry: ringPolygon(ring.lat, ring.lon, ring.miles), properties: {} }] }
      : EMPTY);
    const dLon = ring ? (ring.miles * 1.609344) / (111.32 * Math.cos((ring.lat * Math.PI) / 180)) : 0;
    (map.getSource("ring-handle") as GeoJSONSource | undefined)?.setData(ring
      ? { type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "Point", coordinates: [ring.lon + dLon, ring.lat] }, properties: {} }] }
      : EMPTY);
    (map.getSource("place") as GeoJSONSource | undefined)?.setData(place
      ? { type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "Point", coordinates: [place.lon, place.lat] }, properties: {} }] }
      : EMPTY);
  }, [ring, place, ready]);

  // The places the search is limited to: outlined, and framed once per new outline.
  const highlightKey = JSON.stringify((highlight ?? []).map((h) => (h.kind === "area" ? h.id : !!h.geometry)));
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const geoms: GeoJSON.Geometry[] = [];
    for (const h of highlight ?? []) {
      if (h.kind === "hood" && h.geometry) geoms.push(h.geometry);
      if (h.kind === "area") {
        const f = areas?.features.find((x) => Number(x.properties?.ca) === h.id);
        if (f?.geometry) geoms.push(f.geometry);
      }
    }
    (map.getSource("highlight") as GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection", features: geoms.map((g) => ({ type: "Feature", geometry: g, properties: {} })),
    });
    if (!geoms.length) return;
    let w = 180, s = 90, e = -180, n = -90;
    const visit = (c: unknown): void => {
      if (Array.isArray(c) && typeof c[0] === "number") { const [x, y] = c as number[]; w = Math.min(w, x); e = Math.max(e, x); s = Math.min(s, y); n = Math.max(n, y); }
      else if (Array.isArray(c)) c.forEach(visit);
    };
    geoms.forEach((g) => visit((g as GeoJSON.Polygon).coordinates));
    map.fitBounds([[w, s], [e, n]], { padding: 60, duration: reducedMotion() ? 0 : 700, maxZoom: 16 });
    // highlightKey stands for highlight.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlightKey, ready, areas]);

  // Walking distance around the L stops while the Transit panel is open.
  const [stops, setStops] = useState<Array<[number, number]>>([]);
  useEffect(() => {
    if (walkMiles == null || stops.length) return;
    let live2 = true;
    fetchTransitStations().then((all) => { if (live2) setStops(all.filter((s) => s.type === "cta_rail").map((s) => [s.lat, s.lon])); });
    return () => { live2 = false; };
  }, [walkMiles, stops.length]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource("walk") as GeoJSONSource | undefined)?.setData(walkMiles == null ? EMPTY : {
      type: "FeatureCollection",
      features: stops.map(([lat, lon]) => ({ type: "Feature", geometry: ringPolygon(lat, lon, walkMiles, 40), properties: {} })),
    });
  }, [walkMiles, stops, ready]);

  // Camera requests.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !focus) return;
    if (focus.bbox) {
      map.fitBounds([[focus.bbox[0], focus.bbox[1]], [focus.bbox[2], focus.bbox[3]]], { padding: 40, duration: reducedMotion() ? 0 : 700, maxZoom: 17 });
    } else if (focus.center) {
      const opts = { center: focus.center, zoom: focus.zoom ?? map.getZoom() };
      if (reducedMotion()) map.jumpTo(opts); else map.easeTo({ ...opts, duration: 700 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.seq, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !fit) return;
    map.fitBounds([[fit.bbox[0], fit.bbox[1]], [fit.bbox[2], fit.bbox[3]]], { padding: 48, duration: reducedMotion() ? 0 : 700, maxZoom: 16 });
    // fit.key stands for the search being framed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fit?.key, ready]);

  // The picked lot's row.
  useEffect(() => {
    if (!picked || picked.lookup) return;
    const c = new AbortController();
    discoveryOutlineRow(picked.pin10, sortKey, c.signal).then((lookup) => {
      if (!c.signal.aborted) setPicked((p) => (p && p.pin10 === picked.pin10 ? { ...p, lookup } : p));
    });
    return () => c.abort();
  }, [picked, sortKey, setPicked]);

  // On a phone the lot opens in the bottom sheet: when the sheet would cover it, the map moves it into the part above.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !picked || bottomInset <= 0) return;
    const h = map.getContainer().clientHeight;
    const visible = h - bottomInset;
    const y = map.project(picked.ll as [number, number]).y;
    if (visible > 48 && (y > visible - 24 || y < 24)) map.panBy([0, y - visible / 2], { duration: reducedMotion() ? 0 : 300 });
    // The lot (its click point) and the sheet's height decide; the rest of `picked` (its row arriving) doesn't.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [picked?.pin10, picked?.ll, bottomInset, ready]);

  if (error) {
    return (
      <div className={`grid place-items-center bg-nx-block p-6 text-center ${className ?? ""}`}>
        <p className="flex max-w-xs flex-col items-center gap-2 nx-muted">
          <MapPinOff aria-hidden className="h-5 w-5" strokeWidth={STROKE} />
          {t("discovery.map.noWebgl")}
        </p>
      </div>
    );
  }

  return (
    <div className={`overflow-hidden ${className ?? "relative"}`} data-testid="explore-map">
      <div ref={box} style={{ position: "absolute", inset: 0 }} aria-label={t("discovery.map.label")} role="region" />
      {!ready && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center">
          <LoaderCircle aria-hidden className="h-5 w-5 animate-spin nx-muted" strokeWidth={STROKE} />
        </div>
      )}
      {picked && inlineCard && <LotCard picked={picked} onClose={() => setPicked(null)} />}
    </div>
  );
}

/** What a picked lot shows, shared by the floating card (laptop) and the phone's lot sheet. */
function useLotCard(picked: Picked) {
  const { i18n } = useTranslation("next");
  const n = (v: number) => Math.round(v).toLocaleString(i18n.language.startsWith("es") ? "es-MX" : "en-US");
  const row = picked.lookup?.status === "found" ? picked.lookup.row : null;
  const card = row ? cardModel(row) : null;
  // Stand on the lot's own address street (its frontage), facing the lot, not in the alley behind it (Item 94).
  const sv = useMemo(() => viewpointFor(picked.ll, picked.roads, streetOfAddress(row?.address)), [picked.ll, picked.roads, row?.address]);
  const profileAddr = row ? profileAddress(row) : null;
  const href = row ? `/scorecard?${new URLSearchParams({ pin: row.pin, ...(profileAddr ? { address: profileAddr } : {}) })}` : null;
  // What the correction form asks about (Item 129): a lot we show empty asks "There's a building", a condo "Not a condo".
  const lot = row ? { hasBuilding: row.structure !== "empty", condo: !!card?.condo } : null;
  return { card, sv, href, n, lot };
}

type LotCardModel = ReturnType<typeof useLotCard>;

function titleText(t: (k: string, o?: Record<string, unknown>) => string, card: NonNullable<LotCardModel["card"]>): string {
  return card.approx ? t("discovery.card.near", { address: card.title }) : card.title;
}

function LotTitle({ card }: { card: NonNullable<LotCardModel["card"]> }) {
  const { t } = useTranslation("next");
  return <>{titleText(t, card)}</>;
}

function LotStatus({ picked }: { picked: Picked }) {
  const { t } = useTranslation("next");
  if (!picked.lookup) return <p className="flex items-center gap-2 nx-muted"><LoaderCircle aria-hidden className="h-4 w-4 animate-spin" strokeWidth={STROKE} />{t("discovery.map.loading")}</p>;
  if (picked.lookup.status === "missing") return <p className="nx-muted">{t("discovery.map.missing")}</p>;
  if (picked.lookup.status === "failed") return <p className="nx-muted">{t("discovery.map.failed")}</p>;
  return null;
}

/** The lot's figures under its title: district and lot size, room to build, a condo's heads-up, an exempt owner. */
function LotFacts({ card, n }: Pick<LotCardModel, "n"> & { card: NonNullable<LotCardModel["card"]> }) {
  const { t } = useTranslation("next");
  return (
    <>
      <p className="nx-muted">
        {[card.zone, card.lotSqft != null ? t("discovery.card.lotValue", { value: n(card.lotSqft) }) : null].filter(Boolean).join(" · ")}
      </p>
      <p className="flex items-center gap-1">
        {card.roomSqft != null ? t("discovery.card.roomValue", { value: n(card.roomSqft) })
          : card.roomNamed ? t(`discovery.card.named.${card.roomNamed}`) : t("discovery.card.roomUnknown")}
        {card.roomSqft != null && card.userReport && <UserReportIcon stories={card.userReport.stories} />}
      </p>
      {/* A condo building: a heads-up, not a wall (owner): many owners, and where the room comes from. */}
      {card.condo && (
        <p className="nx-muted" data-testid="lot-card-condo">
          {card.condo.units != null ? t("discovery.card.condoUnits", { count: card.condo.units }) : t("discovery.card.condo")}
          {" · "}{card.condo.measured ? t("discovery.card.condoMeasured") : t("discovery.card.condoNoArea")}
        </p>
      )}
      {/* Who owns a tax-exempt lot, and empty public land named as such (owner's review, Item 128). */}
      {card.owner && <p className="nx-muted [overflow-wrap:anywhere]" data-testid="lot-card-owner">{ownerLine(t, card.owner)}</p>}
    </>
  );
}

/** The room comes from a reviewed user report (Item 129 §1): an icon, not a label; its tooltip (hover and keyboard focus)
    says so with the reviewed story count. Who reviewed it and when stay off the card. */
function UserReportIcon({ stories }: { stories: number }) {
  const { t } = useTranslation("next");
  const label = stories > 0 ? t("discovery.card.userReport", { count: stories }) : t("discovery.card.userReportEmpty");
  return (
    <span className="group relative inline-flex" data-testid="lot-card-user-report">
      <span tabIndex={0} role="img" aria-label={label} className="inline-flex rounded focus-visible:outline focus-visible:outline-2">
        <UserCheck aria-hidden className="h-3.5 w-3.5 nx-muted" strokeWidth={STROKE} />
      </span>
      <span role="tooltip" aria-hidden
        className="pointer-events-none absolute left-1/2 top-full z-30 mt-1 hidden w-max max-w-[14rem] -translate-x-1/2 rounded-md bg-nx-ink px-2 py-1 text-[11px] text-nx-on-ink group-hover:block group-focus-within:block">
        {label}
      </span>
    </span>
  );
}

/** Open profile at full width, then Street View and Google Maps side by side (owner's review); the last two open in a
 * new tab. `tall` = 44 px buttons (the phone sheet). */
function LotButtons({ picked, sv, href, tall = false }: Pick<LotCardModel, "sv" | "href"> & { picked: Picked; tall?: boolean }) {
  const { t } = useTranslation("next");
  const navigate = useNavigate();
  const h = tall ? "h-11" : "h-9";
  return (
    <div className="mt-3 flex flex-col gap-2">
      {href && (
        <button type="button" onClick={() => navigate(href)} data-testid="lot-card-open"
          className={`inline-flex ${h} w-full items-center justify-center gap-1.5 rounded-lg bg-nx-ink px-3 font-semibold text-nx-on-ink touch-target`}>
          {t("discovery.card.open")}<ArrowRight aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
        </button>
      )}
      <div className="grid grid-cols-2 gap-2">
        <a href={streetViewUrl(sv.lat, sv.lon, sv.heading)} target="_blank" rel="noopener noreferrer" data-testid="lot-card-street-view"
          className={`inline-flex ${h} min-w-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg bg-nx-ink/5 px-2 font-medium hover:bg-nx-ink/10 touch-target`}>
          <PersonStanding aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />{t("map.streetView.button")}
          <span className="sr-only">{t("profile.opensInNewTab")}</span>
        </a>
        <a href={googleMapsUrl(picked.ll[1], picked.ll[0])} target="_blank" rel="noopener noreferrer" data-testid="lot-card-google-maps"
          className={`inline-flex ${h} min-w-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg bg-nx-ink/5 px-2 font-medium hover:bg-nx-ink/10 touch-target`}>
          <MapPinned aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />{t("map.googleMaps")}
          <span className="sr-only">{t("profile.opensInNewTab")}</span>
        </a>
      </div>
    </div>
  );
}

export function LotCard({ picked, onClose }: { picked: Picked; onClose: () => void }) {
  const { t } = useTranslation("next");
  const { card, sv, href, n, lot } = useLotCard(picked);
  const [w, h] = picked.size;
  const left = Math.min(Math.max(8, picked.at[0] - 140), w - 288);
  const above = picked.at[1] > h * 0.55;
  const style = above ? { left, bottom: h - picked.at[1] + 12 } : { left, top: picked.at[1] + 12 };
  return (
    <div role="dialog" aria-label={card?.title ?? t("discovery.map.lot")} data-testid="lot-card"
      className="absolute z-10 w-[17.5rem] rounded-2xl bg-nx-page p-4 text-caption shadow-[0_8px_32px_rgb(0_0_0/0.18)]" style={style}>
      <div className="absolute right-2 top-2 flex items-center">
        {/* Suggest a correction (Item 129): one muted pencil beside the ×, its name in a tooltip. */}
        {card && lot && <SuggestCorrection pin10={picked.pin10} title={titleText(t, card)} hasBuilding={lot.hasBuilding} condo={lot.condo} phone={false} />}
        <button type="button" onClick={onClose} aria-label={t("discovery.map.close")} className="grid h-7 w-7 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon">
          <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
        </button>
      </div>
      <LotStatus picked={picked} />
      {card && (
        <div className="flex flex-col gap-1.5 pr-14">
          <p className="text-body font-semibold [overflow-wrap:anywhere]"><LotTitle card={card} /></p>
          <LotFacts card={card} n={n} />
        </div>
      )}
      {card && <LotButtons picked={picked} sv={sv} href={href} />}
    </div>
  );
}

/** The phone's lot sheet head (Item 129 §1): the address (or the lookup's state) and ×. */
export function LotSheetHead({ picked, onClose }: { picked: Picked; onClose: () => void }) {
  const { t } = useTranslation("next");
  const { card, lot } = useLotCard(picked);
  return (
    <>
      <div className="min-w-0 flex-1 text-left" data-testid="lot-sheet-title">
        {card ? <p className="font-semibold [overflow-wrap:anywhere]"><LotTitle card={card} /></p> : <LotStatus picked={picked} />}
      </div>
      {card && lot && <SuggestCorrection pin10={picked.pin10} title={titleText(t, card)} hasBuilding={lot.hasBuilding} condo={lot.condo} phone />}
      <button type="button" onClick={onClose} aria-label={t("discovery.map.close")} data-testid="lot-sheet-close"
        className="grid h-11 w-11 shrink-0 place-items-center rounded-full hover:bg-nx-ink/5">
        <X aria-hidden className="h-5 w-5" strokeWidth={STROKE} />
      </button>
    </>
  );
}

/** The phone's lot sheet body: the same figures and buttons as the laptop card, the buttons 44 px tall. */
export function LotSheetBody({ picked }: { picked: Picked }) {
  const { card, sv, href, n } = useLotCard(picked);
  if (!card) return null;
  return (
    <div className="flex flex-col gap-1.5 px-4 pb-[max(1rem,env(safe-area-inset-bottom))] text-caption" data-testid="lot-sheet-body">
      <LotFacts card={card} n={n} />
      <LotButtons picked={picked} sv={sv} href={href} tall />
    </div>
  );
}
