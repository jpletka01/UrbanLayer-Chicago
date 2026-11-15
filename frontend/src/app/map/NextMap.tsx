// The new UI's one map (map tracks M1-M3, decision Items 90-91): MapLibre over our own tiles, in the Cities:
// Skylines look (Item 80). Mounted once per page and never remounted: the page hands it a `view` (the active tab's
// camera and layer modes) and its data, and every change is applied in place. A theme switch repaints the layers
// (no style reload), so sources, feature state, the camera and the key all survive it.
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MLMap, MapGeoJSONFeature } from "maplibre-gl";
// MapLibre finds its worker beside its own file, which Vite's bundling moves: point it at the worker explicitly.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";
import { Box, ChevronDown, ChevronUp, Compass, LoaderCircle, LocateFixed, MapPinOff, PersonStanding, RotateCcw, RotateCw, Square, SquareArrowOutUpRight, X } from "lucide-react";
import { useThemeContext } from "../../contexts/ThemeContext";
import { fetchTransitStations, discoveryOutlineRow, type DiscoveryOutlineLookup } from "../../lib/api";
import { apiOrigin, fetchLotOutline, loadMapInfo, streetViewUrl } from "./mapInfo";
import { loadedRoads, streetOfAddress, viewpointFor, type Viewpoint } from "./streetView";
import { addPinImages } from "./pins";
import { addPatternImages } from "./patterns";
import type { ComparableSale, TransitStation } from "../../lib/types";
import type { ConstructionProject } from "../../lib/api";
import { humanizeShoutyCase } from "../../lib/format";
import { rowTitle } from "../../discovery/rowFigures";
import {
  GROUPS, buildStyle, lotPinImage, modeOpacity, themePaint, type GroupId, type LayerMode, type MapTiles, type Theme,
} from "./mapStyle";
import { MapKey, type GroupState } from "./MapKey";
import { BEARING_STEP, LOT_BUILDING_LAYER, MASS_LAYER, MASS_SOURCE, VIEW_3D, can3d, ensure3dLayers, markLotBuildings, massData, nextPitch, repaint3d, set3d } from "./buildings3d";
import type { ZoningMass } from "../profile/profileModel";
import { Toggletip } from "../../components/ui/Toggletip";
import { useIsPhone } from "../../lib/useIsPhone";
import { permitWords } from "../profile/neighborhoodModel";
import { foldAttribution } from "./attribution";

export interface MapView {
  /** Which tab asked for this view; a new id re-applies its camera and modes. */
  id: string;
  zoom: number;
  modes: Record<GroupId, LayerMode>;
  /** Open in 3D (Build, owner 2026-11-11); the 2D/3D button changes it for this tab. */
  threeD?: boolean;
  /** Frame the lot and this group's points when the view opens (and when they arrive late), instead of the
      fixed zoom; the zoom stays the fallback when the group has no points (Money: the nearby sales, Item 99). */
  fit?: GroupId;
}

/** A layer that waits on a late part (Item 89's skeleton rule): loading, ready, or couldn't be checked in time. */
export type LateState = "loading" | "ready" | "timedOut" | "failed" | "absent";

export interface NextMapProps {
  lat: number;
  lon: number;
  geometry: GeoJSON.Geometry | null;
  approximate: boolean;
  /** The lot's PIN10, for its outline's highlight in the parcel layer. */
  pin10: string | null;
  view: MapView;
  sales: ComparableSale[] | null;
  salesState: LateState;
  onRetrySales?: () => void;
  /** Construction nearby (the Neighborhood tab, Item 102): permits as pins, a new building and a renovation by color. */
  building?: ConstructionProject[] | null;
  buildingState?: LateState;
  onRetryBuilding?: () => void;
  /** Fly to this permit and open its card (a permit page's "Show on the map"); `seq` repeats the request. */
  focusBuilding?: { permit: ConstructionProject; seq: number } | null;
  /** The map is the focus of the screen (Expand): the wheel zooms at once, like a full-page map. In the page band
      the wheel scrolls the page until the map is clicked. */
  expanded?: boolean;
  /** The illustrative zoning mass to raise over the lot in 3D (Build only, M6); never drawn when `approximate`. */
  mass?: ZoningMass | null;
  className?: string;
}

maplibregl.setWorkerUrl(workerUrl);

const NEAR_TRANSIT_KM = 1.2;

const reducedMotion = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function km(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const r = Math.PI / 180;
  const x = (bLon - aLon) * r * Math.cos(((aLat + bLat) / 2) * r);
  const y = (bLat - aLat) * r;
  return Math.sqrt(x * x + y * y) * 6371;
}

/** `at` = the click in screen pixels (where the card opens); `ll` = the click on the ground [lon, lat] (Street View). */
type Picked =
  | { kind: "parcel"; pin10: string; at: [number, number]; ll: [number, number]; sv: Viewpoint; lookup: DiscoveryOutlineLookup | null }
  | { kind: "district"; props: Record<string, string>; at: [number, number]; ll: [number, number]; sv: Viewpoint }
  | { kind: "sale"; sale: ComparableSale; at: [number, number]; ll: [number, number]; sv: Viewpoint }
  | { kind: "building"; project: ConstructionProject; at: [number, number]; ll: [number, number]; sv: Viewpoint };

export function NextMap({
  lat, lon, geometry, approximate, pin10, view, sales, salesState, onRetrySales,
  building = null, buildingState = "absent", onRetryBuilding, focusBuilding = null, expanded = false, mass = null, className,
}: NextMapProps) {
  const { t, i18n } = useTranslation("next");
  const { resolvedTheme } = useThemeContext();
  const theme: Theme = resolvedTheme === "dark" ? "dark" : "light";
  const box = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);
  const [tiles, setTiles] = useState<MapTiles | null>(null);
  const [stations, setStations] = useState<TransitStation[]>([]);
  // The active tab's modes, until the visitor changes one (held for that tab only).
  const [override, setOverride] = useState<{ viewId: string; modes: Record<GroupId, LayerMode> } | null>(null);
  const modes = override && override.viewId === view.id ? override.modes : view.modes;
  // 3D (M6, Item 106): the tab's default until the visitor presses 2D/3D; on a phone only the expanded map.
  const phone = useIsPhone();
  const [override3d, setOverride3d] = useState<{ viewId: string; on: boolean } | null>(null);
  const [bigMap, setBigMap] = useState(false);
  const [counts, setCounts] = useState<Partial<Record<GroupId, number>>>({});
  const [families, setFamilies] = useState<string[]>([]);
  const [picked, setPicked] = useState<Picked | null>(null);
  const [away, setAway] = useState(false);
  // The County's full-precision outline for this lot, when it still matches (Item 92); else the page's own.
  const [precise, setPrecise] = useState<{ pin10: string; geometry: GeoJSON.Geometry } | null>(null);
  const lotGeometry = precise && precise.pin10 === pin10 ? precise.geometry : geometry;
  const [boxH, setBoxH] = useState(0);
  const expandedRef = useRef(expanded);
  const themeRef = useRef(theme);
  const modesRef = useRef(modes);
  useEffect(() => { modesRef.current = modes; }, [modes]);

  // Create the map once.
  useEffect(() => {
    let cancelled = false;
    let map: MLMap | null = null;
    loadMapInfo().then((info) => {
      if (cancelled || !box.current) return;
      setTiles(info);
      let m: MLMap;
      try {
        m = new maplibregl.Map({
          container: box.current,
          style: buildStyle({ theme: themeRef.current, apiOrigin: apiOrigin(), glyphsBase: new URL("/map/fonts", window.location.href).href, tiles: info }),
          center: [lon, lat],
          zoom: view.zoom,
          attributionControl: false,
          dragRotate: false,
          pitchWithRotate: false,
          fadeDuration: 0,
        });
      } catch (err) {
        console.warn("Map unavailable in this browser:", err);
        setError(true);
        return;
      }
      map = m;
      m.touchZoomRotate.disableRotation();
      m.addControl(new maplibregl.AttributionControl({
        compact: true,
        customAttribution: t("map.attribution"),
      }), "bottom-left");
      m.once("load", () => foldAttribution(m.getContainer()));
      // No +/- buttons (owner): the wheel and pinch zoom. In the page band the wheel scrolls the page until the
      // map is clicked; in the expanded map it zooms at once.
      if (!expandedRef.current) m.scrollZoom.disable();
      m.on("click", () => m.scrollZoom.enable());
      m.on("mouseout", () => { if (!expandedRef.current) m.scrollZoom.disable(); });
      // Growing to full screen fires a leave event under the pointer; entering again turns the wheel back on.
      m.on("mouseover", () => { if (expandedRef.current) m.scrollZoom.enable(); });
      m.on("mousemove", () => { if (expandedRef.current && !m.scrollZoom.isEnabled()) m.scrollZoom.enable(); });
      // A lost context must not surface as an error ("WebGL context was lost"); the browser restores it.
      m.on("webglcontextlost", () => undefined);
      // A tile request that fails mid-zoom is never retried by MapLibre, which leaves a square gap (owner saw them).
      // Reload that source's tiles once the burst is over; at most every 4 s.
      let retryAt = 0;
      m.on("error", (e) => {
        const id = (e as unknown as { sourceId?: string }).sourceId;
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
      // The pins are drawn once on a canvas; added before any point arrives, and again if a style ever asks.
      m.on("styleimagemissing", () => { addPinImages(m); addPatternImages(m); });
      m.once("load", () => { addPinImages(m); addPatternImages(m); });
      m.on("load", () => {
        if (cancelled) return;
        const el = m.getContainer();
        setBigMap(el.clientHeight >= 440 && el.clientWidth >= 640);
        if (info.buildings) ensure3dLayers(m, themeRef.current, apiOrigin(), info.buildings);
        if (import.meta.env.DEV) (window as unknown as { __nextMap?: MLMap }).__nextMap = m;
        setReady(true);
      });
      mapRef.current = m;
    });
    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
    };
    // Once per mount by design: later props are applied by the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep the canvas sized to its box (the Ask drawer and the Expand view change it).
  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => { mapRef.current?.resize(); setBoxH(el.clientHeight); });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    expandedRef.current = expanded;
    const map = mapRef.current;
    if (!map) return;
    if (expanded) map.scrollZoom.enable(); else map.scrollZoom.disable();
  }, [expanded, ready]);

  // "Back to the property" once the visitor has moved the lot out of the middle of the view or zoomed far off. A view
  // that frames its points (`fit`) counts its framed camera as home: the next stop after the frame records it.
  const fitHome = useRef<{ x: number; y: number; zoom: number } | "pending" | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const check = () => {
      const c = map.getContainer();
      const home = fitHome.current;
      if (home === "pending") {
        const p = map.project([lon, lat]);
        fitHome.current = { x: p.x, y: p.y, zoom: map.getZoom() };
        setAway(false);
        return;
      }
      if (home) {
        const p = map.project([lon, lat]);
        const moved = Math.hypot(p.x - home.x, p.y - home.y) > Math.min(c.clientWidth, c.clientHeight) * 0.35;
        setAway(moved || Math.abs(map.getZoom() - home.zoom) > 1.5);
        return;
      }
      const p = map.project([lon, lat]);
      const inMiddle = p.x > c.clientWidth * 0.15 && p.x < c.clientWidth * 0.85 && p.y > c.clientHeight * 0.15 && p.y < c.clientHeight * 0.85;
      setAway(!inMiddle || Math.abs(map.getZoom() - view.zoom) > 1.5);
    };
    map.on("moveend", check);
    return () => { map.off("moveend", check); };
  }, [ready, lat, lon, view.zoom]);
  const allow3d = can3d(!!tiles?.buildings, phone, expanded);
  const want3d = override3d && override3d.viewId === view.id ? override3d.on : !!view.threeD;
  const on3d = allow3d && want3d;
  const was3d = useRef(false);
  const on3dRef = useRef(on3d);
  on3dRef.current = on3d;
  /** The camera angle a view move keeps: the 3D angle while 3D is on, else flat and north-up. */
  const angle = () => (on3dRef.current ? VIEW_3D : { pitch: 0, bearing: 0 });
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !tiles?.buildings) return;
    if (on3d === was3d.current) return;
    was3d.current = on3d;
    set3d(map, on3d, !reducedMotion());
  }, [on3d, ready, tiles]);
  // Presses in quick succession build on each other: each starts from where the last one is heading (a new easeTo
  // cancels the one in flight), then the target is forgotten once the camera stops.
  const camTarget = useRef<{ bearing: number; pitch: number } | null>(null);
  const aim = (next: (from: { bearing: number; pitch: number }) => { bearing: number; pitch: number }, ms: number) => {
    const m = mapRef.current;
    if (!m) return;
    const to = next(camTarget.current ?? { bearing: m.getBearing(), pitch: m.getPitch() });
    camTarget.current = to;
    m.once("moveend", () => { if (camTarget.current === to) camTarget.current = null; });
    m.easeTo({ ...to, duration: reducedMotion() ? 0 : ms });
  };
  // The lot in 3D: today's building on it in the lot's color, and on Build the illustrative zoning mass over it.
  const showMass = on3d && !!mass && !approximate && !!lotGeometry;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.getSource(MASS_SOURCE)) return;
    (map.getSource(MASS_SOURCE) as GeoJSONSource).setData(massData(showMass ? lotGeometry : null, showMass ? mass!.heightFt : null, mass?.zoneClass ?? null));
    for (const id of [MASS_LAYER, LOT_BUILDING_LAYER]) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", showMass ? "visible" : "none");
  }, [showMass, lotGeometry, mass, ready]);
  const lotIds = useRef<Set<string | number>>(new Set());
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !tiles?.buildings) return;
    const mark = () => { lotIds.current = markLotBuildings(map, on3d && !approximate ? lotGeometry : null, lotIds.current, showMass); };
    mark();
    if (!on3d) return;
    map.on("idle", mark);
    return () => { map.off("idle", mark); };
  }, [on3d, showMass, lotGeometry, approximate, ready, tiles]);

  const turn = (deg: number) => aim((c) => ({ ...c, bearing: c.bearing + deg }), 400);
  const tilt = (dir: 1 | -1) => aim((c) => ({ ...c, pitch: nextPitch(c.pitch, dir) }), 300);
  const reset3d = () => aim(() => ({ ...VIEW_3D }), 600);

  const backToProperty = () => {
    const map = mapRef.current;
    if (!map) return;
    if (view.fit && fitGroup(view.fit)) return;
    const opts = { center: [lon, lat] as [number, number], zoom: view.zoom, ...angle() };
    if (reducedMotion()) map.jumpTo(opts); else map.easeTo({ ...opts, duration: 600 });
  };

  // Transit stations near the lot (the list is cached by the API module).
  useEffect(() => {
    let live = true;
    fetchTransitStations().then((all) => { if (live) setStations(all.filter((s) => km(lat, lon, s.lat, s.lon) <= NEAR_TRANSIT_KM)); });
    return () => { live = false; };
  }, [lat, lon]);

  // Theme: repaint in place.
  useEffect(() => {
    themeRef.current = theme;
    const map = mapRef.current;
    if (!map || !ready) return;
    repaint3d(map, theme);
    for (const { id, paint } of themePaint(theme)) {
      if (!map.getLayer(id)) continue;
      for (const [k, v] of Object.entries(paint)) map.setPaintProperty(id, k as never, v as never);
    }
    // The property's pin is an image per theme (a layout property, so set apart from the paint).
    if (map.getLayer("lot-pin")) map.setLayoutProperty("lot-pin", "icon-image", lotPinImage(theme));
    applyModes(map, modesRef.current, theme);
  }, [theme, ready]);

  // A new view (a tab switch): its modes and its camera. Reduced motion jumps; nothing takes focus.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    // A framing view frames once here; the effect below frames it instead if its points arrive later.
    if (view.fit && fitGroup(view.fit)) { fittedFor.current = view.id; return; }
    fitHome.current = null;
    const opts = { center: [lon, lat] as [number, number], zoom: view.zoom, ...angle() };
    if (reducedMotion()) map.jumpTo(opts); else map.easeTo({ ...opts, duration: 600 });
    // view.id is the trigger; the modes object changes identity with it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view.id, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (map && ready) applyModes(map, modes, theme);
  }, [modes, ready, theme]);

  useEffect(() => {
    if (!pin10) return;
    const c = new AbortController();
    fetchLotOutline(pin10, c.signal).then((g) => { if (g && !c.signal.aborted) setPrecise({ pin10, geometry: g }); });
    return () => c.abort();
  }, [pin10]);

  // The lot.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const src = map.getSource("lot") as GeoJSONSource | undefined;
    src?.setData(lotGeometry
      ? { type: "FeatureCollection", features: [{ type: "Feature", geometry: lotGeometry, properties: { approximate } }] }
      : { type: "FeatureCollection", features: [] });
    (map.getSource("lot-point") as GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "Point", coordinates: [lon, lat] }, properties: {} }],
    });
  }, [lotGeometry, approximate, ready, lat, lon]);

  // The lot's outline is marked in the parcel layer too (feature-state; one tile set serves every page).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !tiles?.parcels || !pin10) return;
    const id = Number(pin10);
    map.setFeatureState({ source: "parcels", sourceLayer: "parcels", id }, { match: true });
    return () => { if (map.getSource("parcels")) map.removeFeatureState({ source: "parcels", sourceLayer: "parcels", id }); };
  }, [pin10, ready, tiles]);

  // Recent sales and transit.
  const saleFeatures = useMemo(() => (sales ?? []).filter((s) => s.lat != null && s.lon != null).map((s, i) => ({
    type: "Feature" as const, id: i, geometry: { type: "Point" as const, coordinates: [s.lon!, s.lat!] }, properties: { i },
  })), [sales]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource("sales") as GeoJSONSource | undefined)?.setData({ type: "FeatureCollection", features: salesState === "ready" ? saleFeatures : [] });
  }, [saleFeatures, salesState, ready]);
  const buildingFeatures = useMemo(() => (building ?? []).map((p, i) => ({
    type: "Feature" as const, id: i, geometry: { type: "Point" as const, coordinates: [p.lon, p.lat] }, properties: { i, kind: p.kind },
  })), [building]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource("building") as GeoJSONSource | undefined)?.setData({ type: "FeatureCollection", features: buildingState === "ready" ? buildingFeatures : [] });
  }, [buildingFeatures, buildingState, ready]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource("transit") as GeoJSONSource | undefined)?.setData({ type: "FeatureCollection", features: stations.map((s, i) => ({
      type: "Feature", id: i, geometry: { type: "Point", coordinates: [s.lon, s.lat] }, properties: { name: s.name },
    })) });
  }, [stations, ready]);

  // The self-building key: counts of what is on screen, recomputed when the map settles.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const recount = () => {
      const q = (layers: string[]) => layers.filter((l) => map.getLayer(l)).length ? map.queryRenderedFeatures({ layers: layers.filter((l) => map.getLayer(l)) }) : [];
      const lots = new Set(q(["parcel-line"]).map((f) => f.id));
      const zfeat = q(["zoning-fill"]);
      const zones = new Map<string, { zone: string; family: string; level: string }>();
      for (const f of zfeat) {
        const p = f.properties as Record<string, string>;
        if (p.zone_class && !zones.has(p.zone_class)) zones.set(p.zone_class, { zone: p.zone_class, family: p.family, level: p.level });
      }
      setCounts({
        parcels: lots.size, zoning: zones.size,
        sales: new Set(q(["sales-pin"]).map((f) => f.id)).size,
        building: new Set(q(["building-pin"]).map((f) => f.id)).size,
        transit: new Set(q(["transit-pin"]).map((f) => f.id)).size,
      });
      setFamilies([...new Set([...zones.values()].map((z) => z.family))]);
    };
    map.on("idle", recount);
    return () => { map.off("idle", recount); };
  }, [ready]);

  // Every outline opens something: a lot, a district, or a sale.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const ctrl = { current: null as AbortController | null };
    const onClick = (e: maplibregl.MapMouseEvent) => {
      const at: [number, number] = [e.point.x, e.point.y];
      const ll: [number, number] = [e.lngLat.lng, e.lngLat.lat];
      const has = (id: string) => !!map.getLayer(id) && map.getLayoutProperty(id, "visibility") !== "none";
      const hit = (ids: string[]): MapGeoJSONFeature | undefined => {
        const live = ids.filter(has);
        return live.length ? map.queryRenderedFeatures([[at[0] - 6, at[1] - 6], [at[0] + 6, at[1] + 6]], { layers: live })[0] : undefined;
      };
      const permit = hit(["building-pin"]);
      if (permit && building) {
        const p = building[Number(permit.properties.i)];
        const pll: [number, number] = [p.lon, p.lat];
        setPicked({ kind: "building", project: p, at, ll: pll, sv: viewpointFor(pll, loadedRoads(map), streetOfAddress(p.address)) });
        return;
      }
      const sale = hit(["sales-pin"]);
      if (sale && sales) {
        const s = sales.filter((x) => x.lat != null && x.lon != null)[Number(sale.properties.i)];
        const sll: [number, number] = [s.lon!, s.lat!];
        setPicked({ kind: "sale", sale: s, at, ll: sll, sv: viewpointFor(sll, loadedRoads(map), null) });
        return;
      }
      const lot = map.queryRenderedFeatures(e.point, { layers: ["parcel-fill"].filter(has) })[0];
      if (lot && lot.id != null) {
        const pin = String(lot.id).padStart(10, "0");
        ctrl.current?.abort();
        const c = new AbortController();
        ctrl.current = c;
        const roads = loadedRoads(map);
        setPicked({ kind: "parcel", pin10: pin, at, ll, sv: viewpointFor(ll, roads, null), lookup: null });
        discoveryOutlineRow(pin, "lot_size", c.signal).then((lookup) => {
          if (c.signal.aborted) return;
          // With the address, stand on the lot's own street (its frontage), facing the lot.
          const street = lookup.status === "found" ? streetOfAddress(lookup.row.address) : null;
          const sv = viewpointFor(ll, roads, street);
          setPicked((p) => (p && p.kind === "parcel" && p.pin10 === pin ? { ...p, lookup, sv } : p));
        });
        return;
      }
      const district = map.queryRenderedFeatures(e.point, { layers: ["zoning-fill"].filter(has) })[0];
      if (district) {
        setPicked({ kind: "district", props: district.properties as Record<string, string>, at, ll, sv: viewpointFor(ll, loadedRoads(map), null) });
        return;
      }
      setPicked(null);
    };
    const pointer = (e: maplibregl.MapMouseEvent) => {
      const ids = ["building-pin", "sales-pin", "parcel-fill", "zoning-fill"].filter((id) => !!map.getLayer(id) && map.getLayoutProperty(id, "visibility") !== "none");
      map.getCanvas().style.cursor = ids.length && map.queryRenderedFeatures(e.point, { layers: ids }).length ? "pointer" : "";
    };
    map.on("click", onClick);
    map.on("mousemove", pointer);
    return () => { map.off("click", onClick); map.off("mousemove", pointer); ctrl.current?.abort(); };
  }, [ready, sales, building]);

  // A permit page's "Show on the map": fly there, then open its card where it lands.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !focusBuilding) return;
    const p = focusBuilding.permit;
    const ll: [number, number] = [p.lon, p.lat];
    const open = () => {
      const pt = map.project(ll);
      setPicked({ kind: "building", project: p, at: [pt.x, pt.y], ll, sv: viewpointFor(ll, loadedRoads(map), streetOfAddress(p.address)) });
    };
    map.once("moveend", open);
    if (reducedMotion()) map.jumpTo({ center: ll, zoom: Math.max(map.getZoom(), 16.5) });
    else map.easeTo({ center: ll, zoom: Math.max(map.getZoom(), 16.5), duration: 600 });
    return () => { map.off("moveend", open); };
    // seq is the trigger
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusBuilding?.seq, ready]);

  // The lot a visitor opened is marked while its card is open.
  const pickedPin = picked?.kind === "parcel" ? picked.pin10 : null;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !pickedPin || !map.getSource("parcels")) return;
    const id = Number(pickedPin);
    map.setFeatureState({ source: "parcels", sourceLayer: "parcels", id }, { match: true });
    return () => { if (map.getSource("parcels") && pickedPin !== pin10) map.setFeatureState({ source: "parcels", sourceLayer: "parcels", id }, { match: false }); };
  }, [pickedPin, ready, pin10]);

  useEffect(() => {
    if (!picked) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setPicked(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [picked]);

  // Fit the lot and a group's points on screen (the key's "Show", and a view's `fit`). False when there is nothing
  // to fit. The right padding leaves room for the open key, but never more than a third of a narrow band.
  function fitGroup(g: GroupId): boolean {
    const map = mapRef.current;
    if (!map) return false;
    const pts: [number, number][] = [[lon, lat]];
    if (g === "sales" && salesState === "ready") for (const f of saleFeatures) pts.push(f.geometry.coordinates as [number, number]);
    if (g === "building" && buildingState === "ready") for (const f of buildingFeatures) pts.push(f.geometry.coordinates as [number, number]);
    if (g === "transit") for (const s of stations) pts.push([s.lon, s.lat]);
    if (pts.length < 2) return false;
    const w = Math.min(...pts.map((p) => p[0])), e = Math.max(...pts.map((p) => p[0]));
    const so = Math.min(...pts.map((p) => p[1])), n = Math.max(...pts.map((p) => p[1]));
    const width = map.getContainer().clientWidth;
    const right = Math.min(300, Math.round(width / 3));
    fitHome.current = "pending";
    map.fitBounds([[w, so], [e, n]], { padding: { top: 56, bottom: 44, left: 48, right }, maxZoom: 17, ...angle(), duration: reducedMotion() ? 0 : 600 });
    return true;
  }
  const showGroup = (g: GroupId) => { fitGroup(g); };

  // A view that frames its points: once they arrive (the sales come with a late part), frame them once per view.
  const fittedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!ready || !view.fit) { fittedFor.current = null; return; }
    if (fittedFor.current === view.id) return;
    if (fitGroup(view.fit)) fittedFor.current = view.id;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, view.id, view.fit, saleFeatures, salesState, buildingFeatures, buildingState, stations]);

  const groups: GroupState[] = GROUPS.flatMap((g): GroupState[] => {
    if (g === "zoning" && !tiles?.zoning) return [];
    if (g === "parcels" && !tiles?.parcels) return [];
    if (g === "streets" && !tiles?.base) return [];
    if (g === "sales" && salesState === "absent") return [];
    if (g === "building" && buildingState === "absent") return [];
    if (g === "transit" && stations.length === 0) return [];
    const total = g === "sales" ? saleFeatures.length : g === "building" ? buildingFeatures.length : g === "transit" ? stations.length : undefined;
    return [{ id: g, mode: modes[g], count: counts[g], total, late: g === "sales" ? salesState : g === "building" ? buildingState : undefined }];
  });

  // The waiting layer named on the map: the one this view shows (the permits on Neighborhood, else the sales).
  const lateGroup: "sales" | "building" = modes.building === "on" && buildingState !== "absent" ? "building" : "sales";
  const lateState = lateGroup === "building" ? buildingState : salesState;
  const lateRetry = lateGroup === "building" ? onRetryBuilding : onRetrySales;
  const late = lateState === "loading" || lateState === "timedOut" || lateState === "failed";

  return (
    <div className={`relative h-full w-full ${className ?? ""}`} data-testid="next-map" data-theme-applied={theme}>
      {/* Inline: MapLibre's stylesheet sets position: relative on its container, which would beat a class. */}
      <div ref={box} style={{ position: "absolute", inset: 0 }} data-testid="next-map-canvas" />
      {error && (
        <div className="absolute inset-0 z-10 flex items-center justify-center p-5" role="status" data-testid="map-unavailable">
          <p className="flex max-w-sm items-start gap-2 rounded-xl bg-nx-page px-4 py-3 shadow-[0_1px_2px_rgb(0_0_0/0.12)]">
            <MapPinOff aria-hidden className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} />
            <span>{t("map.unavailable")}</span>
          </p>
        </div>
      )}
      {ready && tiles && !tiles.base && (
        <p className="absolute bottom-9 left-2 z-10 rounded-lg bg-nx-page/95 px-2 py-1 text-caption nx-muted" role="status">{t("map.noBase")}</p>
      )}
      {ready && (
        <MapKey
          defaultOpen={bigMap}
          maxHeight={boxH > 0 ? boxH - 96 : undefined}
          groups={groups}
          families={families}
          onMode={(g, m) => setOverride({ viewId: view.id, modes: { ...modes, [g]: m } })}
          onRetry={(g) => (g === "building" ? onRetryBuilding : onRetrySales)?.()}
          onShow={showGroup}
        />
      )}
      {/* The skeleton rule on the map (Item 89): a layer that waits on a late part is named in place. */}
      {/* Not in the expanded map (owner): there the key's row says it. */}
      {ready && late && !expanded && (
        <p className="absolute bottom-9 left-2 z-10 flex items-center gap-1.5 rounded-lg bg-nx-page/95 px-2 py-1 text-caption shadow-[0_1px_2px_rgb(0_0_0/0.12)]" role="status" data-testid="map-late-tag">
          {lateState === "loading" ? (
            <><LoaderCircle aria-hidden className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} />{t("map.loading", { layer: t(`map.inSentence.${lateGroup}`) })}</>
          ) : (
            <>
              {t("map.timedOut", { layer: t(`map.inSentence.${lateGroup}`) })}
              {lateRetry && (
                <button type="button" onClick={lateRetry} className="ml-1 inline-flex items-center gap-1 underline underline-offset-2">
                  <RotateCw aria-hidden className="h-3 w-3" strokeWidth={1.5} />{t("map.retry")}
                </button>
              )}
            </>
          )}
        </p>
      )}
      {ready && away && (
        <button
          type="button"
          onClick={backToProperty}
          className={`absolute ${expanded ? "top-3" : "bottom-3"} left-1/2 z-10 flex -translate-x-1/2 items-center gap-1.5 rounded-full bg-nx-primary px-3 py-1.5 text-caption font-semibold text-nx-primary-fg shadow-[0_1px_4px_rgb(0_0_0/0.2)] touch-target`}
          data-testid="map-back"
        >
          <LocateFixed aria-hidden className="h-3.5 w-3.5" strokeWidth={1.5} />
          {t("map.back")}
        </button>
      )}
      {ready && allow3d && (
        // The expanded map stacks the controls above its corner button; the short page band lines them up in a row
        // beside it, so they never reach the key.
        <div className={`absolute z-10 flex gap-1.5 ${expanded ? "bottom-14 right-2 flex-col items-end" : "bottom-2 right-12 flex-row items-end"}`} data-testid="map-3d-controls">
          {on3d && (
            <div className={`flex overflow-hidden rounded-lg bg-nx-page shadow-[0_1px_2px_rgb(0_0_0/0.15)] ${expanded ? "flex-col" : "flex-row"}`} role="group" aria-label={t("map.view3d.controls")}>
              {([
                ["turnLeft", RotateCcw, () => turn(-BEARING_STEP)],
                ["turnRight", RotateCw, () => turn(BEARING_STEP)],
                ["tiltMore", ChevronUp, () => tilt(1)],
                ["tiltLess", ChevronDown, () => tilt(-1)],
                ["reset", Compass, reset3d],
              ] as const).map(([key, Icon, onClick]) => (
                <button key={key} type="button" onClick={onClick} aria-label={t(`map.view3d.${key}`)} title={t(`map.view3d.${key}`)}
                  className="grid h-8 w-8 place-items-center hover:bg-nx-block touch-icon" data-testid={`map-3d-${key}`}>
                  <Icon aria-hidden className="h-4 w-4" strokeWidth={1.5} />
                </button>
              ))}
            </div>
          )}
          <button
            type="button"
            onClick={() => setOverride3d({ viewId: view.id, on: !on3d })}
            aria-pressed={on3d}
            aria-label={on3d ? t("map.view3d.show2d") : t("map.view3d.show3d")}
            title={on3d ? t("map.view3d.show2d") : t("map.view3d.show3d")}
            className="flex h-8 items-center gap-1 rounded-lg bg-nx-page px-2 text-caption font-semibold shadow-[0_1px_2px_rgb(0_0_0/0.15)] hover:bg-nx-block touch-target"
            data-testid="map-3d-toggle"
          >
            {on3d ? <Square aria-hidden className="h-4 w-4" strokeWidth={1.5} /> : <Box aria-hidden className="h-4 w-4" strokeWidth={1.5} />}
            {on3d ? t("map.view3d.off") : t("map.view3d.on")}
          </button>
        </div>
      )}
      {ready && showMass && mass && (
        <div className={`absolute left-3 z-10 flex items-center gap-1 rounded-lg bg-nx-page px-2 py-1 text-caption shadow-[0_1px_2px_rgb(0_0_0/0.12)] ${expanded ? "top-14" : "top-12"}`} data-testid="map-mass-label">
          <span className="inline-block h-2.5 w-2.5 rounded-sm border border-nx-ink/60 bg-nx-ink/20" aria-hidden />
          <span>{t("map.mass.label")}</span>
          <Toggletip label={t("map.mass.explainLabel")}>
            <span className="block max-w-xs space-y-1 text-caption">
              <span className="block">{t("map.mass.included", {
                far: mass.far, area: Math.round(mass.floorAreaSqft).toLocaleString(i18n.language === "es" ? "es-MX" : "en-US"),
                height: Math.round(mass.heightFt), floorFt: 12,
              })}</span>
              {mass.capFt != null && <span className="block">{t(mass.capFromRange ? "map.mass.capRange" : "map.mass.cap", { cap: mass.capFt })}</span>}
              {mass.limitedByHeight && <span className="block">{t("map.mass.limited")}</span>}
              <span className="block">{t("map.mass.notChecked")}</span>
              <span className="block font-semibold">{t("map.mass.notLargest")}</span>
            </span>
          </Toggletip>
        </div>
      )}
      {picked && <PickedCard picked={picked} onClose={() => setPicked(null)} lang={i18n.language} boxH={boxH} />}
    </div>
  );
}

const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function applyModes(map: MLMap, modes: Record<GroupId, LayerMode>, theme: Theme) {
  for (const g of GROUPS) {
    for (const { id, visible, paint } of modeOpacity(g, modes[g], theme)) {
      if (!map.getLayer(id)) continue;
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
      for (const [k, v] of Object.entries(paint)) map.setPaintProperty(id, k as never, v as never);
    }
  }
}

function PickedCard({ picked, onClose, lang, boxH }: { picked: Picked; onClose: () => void; lang: string; boxH: number }) {
  const { t } = useTranslation("next");
  // Below the click, or above it when the click is near the map's bottom edge (the card is about 150 px tall).
  const above = boxH > 0 && picked.at[1] > boxH - 170;
  const style = above
    ? { left: Math.max(8, picked.at[0] - 120), bottom: Math.max(8, boxH - picked.at[1] + 12) }
    : { left: Math.max(8, picked.at[0] - 120), top: Math.max(8, picked.at[1] + 12) };
  const money = (n: number | null) => (n == null ? t("map.card.noPrice") : new Intl.NumberFormat(lang === "es" ? "es-MX" : "en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n));
  let body: React.ReactNode;
  if (picked.kind === "parcel") {
    const l = picked.lookup;
    body = l == null ? (
      <p className="flex items-center gap-1.5 nx-muted"><LoaderCircle aria-hidden className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} />{t("map.card.looking")}</p>
    ) : l.status === "found" ? (
      <>
        <p className="font-semibold">{l.row.address ? `${rowTitle(l.row).approx ? `${t("map.card.approx")} ` : ""}${rowTitle(l.row).title}` : t("map.card.noAddress")}</p>
        <p className="text-caption nx-muted">{[l.row.land_use ? capitalize(humanizeShoutyCase(l.row.land_use)) : null, l.row.zone_class].filter(Boolean).join(" · ")}</p>
        <a href={`/scorecard?pin=${encodeURIComponent(l.row.pin)}`} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 underline underline-offset-2">
          {t("map.card.openProfile")}<SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={1.5} />
        </a>
      </>
    ) : (
      <p>{l.status === "missing" ? t("map.card.notIndexed", { pin: picked.pin10 }) : t("map.card.failed")}</p>
    );
  } else if (picked.kind === "district") {
    const p = picked.props;
    body = (
      <>
        <p className="font-semibold">{t("map.card.district", { zone: p.zone_class })}</p>
        {p.ordinance_num && <p className="text-caption nx-muted">{t("map.card.ordinance", { num: p.ordinance_num, date: p.ordinance_date ?? "" })}</p>}
        <p className="text-caption nx-muted">{t("map.card.districtSource")}</p>
      </>
    );
  } else if (picked.kind === "building") {
    const p = picked.project;
    const words = permitWords(p.description, 160);
    const issued = p.issued ? new Date(`${p.issued}T12:00:00`).toLocaleDateString(lang === "es" ? "es-MX" : "en-US", { month: "short", day: "numeric", year: "numeric" }) : null;
    body = (
      <>
        <p className="font-semibold">{p.address ?? t(p.kind === "new" ? "map.card.kindNew" : "map.card.kindReno")}</p>
        <p className="text-caption nx-muted">{[t(p.kind === "new" ? "map.card.kindNew" : "map.card.kindReno"), p.cost != null ? money(p.cost) : null].filter(Boolean).join(" · ")}</p>
        {words && <p className="line-clamp-3 text-caption">{words}</p>}
        {issued && <p className="text-caption nx-muted">{t("map.card.issued", { date: issued })}</p>}
      </>
    );
  } else {
    const s = picked.sale;
    body = (
      <>
        <p className="font-semibold">{money(s.sale_price)}</p>
        <p className="text-caption nx-muted">{[s.sale_date, s.class_description].filter(Boolean).join(" · ")}</p>
      </>
    );
  }
  return (
    <div className="ui-next absolute z-20 w-60 rounded-xl bg-nx-page p-3 text-body shadow-[0_2px_8px_rgb(0_0_0/0.18)]" style={style} role="dialog" aria-label={t("map.card.label")} data-testid="map-card">
      <button type="button" onClick={onClose} aria-label={t("map.card.close")} className="absolute right-1.5 top-1.5 grid h-6 w-6 place-items-center rounded hover:bg-nx-block">
        <X aria-hidden className="h-3.5 w-3.5" strokeWidth={1.5} />
      </button>
      <div className="flex flex-col gap-0.5 pr-5">
        {body}
        <a href={streetViewUrl(picked.sv.lat, picked.sv.lon, picked.sv.heading)} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-caption underline underline-offset-2" data-testid="map-card-street-view">
          <PersonStanding aria-hidden className="h-3.5 w-3.5" strokeWidth={1.5} />{t("map.streetView.link")}
        </a>
      </div>
    </div>
  );
}
