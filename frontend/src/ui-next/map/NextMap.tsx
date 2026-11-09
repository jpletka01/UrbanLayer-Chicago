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
import { LoaderCircle, LocateFixed, MapPinOff, RotateCw, SquareArrowOutUpRight, X } from "lucide-react";
import { useThemeContext } from "../../contexts/ThemeContext";
import { fetchTransitStations, discoveryOutlineRow, type DiscoveryOutlineLookup } from "../../lib/api";
import { apiOrigin, fetchLotOutline, loadMapInfo } from "./mapInfo";
import type { ComparableSale, TransitStation } from "../../lib/types";
import { humanizeShoutyCase } from "../../lib/format";
import { rowTitle } from "../../discovery/rowFigures";
import {
  GROUPS, buildStyle, modeOpacity, themePaint, type GroupId, type LayerMode, type MapTiles, type Theme,
} from "./mapStyle";
import { MapKey, type GroupState } from "./MapKey";

export interface MapView {
  /** Which tab asked for this view; a new id re-applies its camera and modes. */
  id: string;
  zoom: number;
  modes: Record<GroupId, LayerMode>;
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
  /** The map is the focus of the screen (Expand): the wheel zooms at once, like a full-page map. In the page band
      the wheel scrolls the page until the map is clicked. */
  expanded?: boolean;
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

type Picked =
  | { kind: "parcel"; pin10: string; at: [number, number]; lookup: DiscoveryOutlineLookup | null }
  | { kind: "district"; props: Record<string, string>; at: [number, number] }
  | { kind: "sale"; sale: ComparableSale; at: [number, number] };

export function NextMap({ lat, lon, geometry, approximate, pin10, view, sales, salesState, onRetrySales, expanded = false, className }: NextMapProps) {
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
  const [bigMap, setBigMap] = useState(false);
  const [counts, setCounts] = useState<Partial<Record<GroupId, number>>>({});
  const [districts, setDistricts] = useState<Array<{ zone: string; family: string; level: string }>>([]);
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
      m.on("load", () => {
        if (cancelled) return;
        const el = m.getContainer();
        setBigMap(el.clientHeight >= 440 && el.clientWidth >= 640);
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

  // "Back to the property" once the visitor has moved the lot out of the middle of the view or zoomed far off.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const check = () => {
      const p = map.project([lon, lat]);
      const c = map.getContainer();
      const inMiddle = p.x > c.clientWidth * 0.15 && p.x < c.clientWidth * 0.85 && p.y > c.clientHeight * 0.15 && p.y < c.clientHeight * 0.85;
      setAway(!inMiddle || Math.abs(map.getZoom() - view.zoom) > 1.5);
    };
    map.on("moveend", check);
    return () => { map.off("moveend", check); };
  }, [ready, lat, lon, view.zoom]);
  const backToProperty = () => {
    const map = mapRef.current;
    if (!map) return;
    const opts = { center: [lon, lat] as [number, number], zoom: view.zoom };
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
    for (const { id, paint } of themePaint(theme)) {
      if (!map.getLayer(id)) continue;
      for (const [k, v] of Object.entries(paint)) map.setPaintProperty(id, k as never, v as never);
    }
    applyModes(map, modesRef.current, theme);
  }, [theme, ready]);

  // A new view (a tab switch): its modes and its camera. Reduced motion jumps; nothing takes focus.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const opts = { center: [lon, lat] as [number, number], zoom: view.zoom };
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
  }, [lotGeometry, approximate, ready]);

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
        sales: new Set(q(["sales-circle"]).map((f) => f.id)).size,
        transit: new Set(q(["transit-circle"]).map((f) => f.id)).size,
      });
      setDistricts([...zones.values()].sort((a, b) => a.zone.localeCompare(b.zone)).slice(0, 8));
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
      const has = (id: string) => !!map.getLayer(id) && map.getLayoutProperty(id, "visibility") !== "none";
      const hit = (ids: string[]): MapGeoJSONFeature | undefined => {
        const live = ids.filter(has);
        return live.length ? map.queryRenderedFeatures([[at[0] - 6, at[1] - 6], [at[0] + 6, at[1] + 6]], { layers: live })[0] : undefined;
      };
      const sale = hit(["sales-circle"]);
      if (sale && sales) {
        setPicked({ kind: "sale", sale: sales.filter((s) => s.lat != null && s.lon != null)[Number(sale.properties.i)], at });
        return;
      }
      const lot = map.queryRenderedFeatures(e.point, { layers: ["parcel-fill"].filter(has) })[0];
      if (lot && lot.id != null) {
        const pin = String(lot.id).padStart(10, "0");
        ctrl.current?.abort();
        const c = new AbortController();
        ctrl.current = c;
        setPicked({ kind: "parcel", pin10: pin, at, lookup: null });
        discoveryOutlineRow(pin, "lot_size", c.signal).then((lookup) => {
          if (!c.signal.aborted) setPicked((p) => (p && p.kind === "parcel" && p.pin10 === pin ? { ...p, lookup } : p));
        });
        return;
      }
      const district = map.queryRenderedFeatures(e.point, { layers: ["zoning-fill"].filter(has) })[0];
      if (district) {
        setPicked({ kind: "district", props: district.properties as Record<string, string>, at });
        return;
      }
      setPicked(null);
    };
    const pointer = (e: maplibregl.MapMouseEvent) => {
      const ids = ["sales-circle", "parcel-fill", "zoning-fill"].filter((id) => !!map.getLayer(id) && map.getLayoutProperty(id, "visibility") !== "none");
      map.getCanvas().style.cursor = ids.length && map.queryRenderedFeatures(e.point, { layers: ids }).length ? "pointer" : "";
    };
    map.on("click", onClick);
    map.on("mousemove", pointer);
    return () => { map.off("click", onClick); map.off("mousemove", pointer); ctrl.current?.abort(); };
  }, [ready, sales]);

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

  const groups: GroupState[] = GROUPS.flatMap((g): GroupState[] => {
    if (g === "zoning" && !tiles?.zoning) return [];
    if (g === "parcels" && !tiles?.parcels) return [];
    if (g === "streets" && !tiles?.base) return [];
    if (g === "sales" && salesState === "absent") return [];
    if (g === "transit" && stations.length === 0) return [];
    return [{ id: g, mode: modes[g], count: counts[g], late: g === "sales" ? salesState : undefined }];
  });

  const late = salesState === "loading" || salesState === "timedOut" || salesState === "failed";

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
          districts={districts}
          onMode={(g, m) => setOverride({ viewId: view.id, modes: { ...modes, [g]: m } })}
          onRetry={onRetrySales}
        />
      )}
      {/* The skeleton rule on the map (Item 89): a layer that waits on a late part is named in place. */}
      {/* Not in the expanded map (owner): there the key's row says it. */}
      {ready && late && !expanded && (
        <p className="absolute bottom-9 left-2 z-10 flex items-center gap-1.5 rounded-lg bg-nx-page/95 px-2 py-1 text-caption shadow-[0_1px_2px_rgb(0_0_0/0.12)]" role="status" data-testid="map-late-tag">
          {salesState === "loading" ? (
            <><LoaderCircle aria-hidden className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} />{t("map.loading", { layer: t("map.inSentence.sales") })}</>
          ) : (
            <>
              {t("map.timedOut", { layer: t("map.inSentence.sales") })}
              {onRetrySales && (
                <button type="button" onClick={onRetrySales} className="ml-1 inline-flex items-center gap-1 underline underline-offset-2">
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
      {picked && <PickedCard picked={picked} onClose={() => setPicked(null)} lang={i18n.language} />}
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

function PickedCard({ picked, onClose, lang }: { picked: Picked; onClose: () => void; lang: string }) {
  const { t } = useTranslation("next");
  const style = { left: Math.max(8, picked.at[0] - 120), top: Math.max(8, picked.at[1] + 12) };
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
      <div className="flex flex-col gap-0.5 pr-5">{body}</div>
    </div>
  );
}
