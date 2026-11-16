// An answer's map (Phase 8, wireframe v2 approved 2026-11-12): the new UI's one map style over our own tiles (Items
// 80, 90-91; no satellite) drawn the Profile's way. Building nearby uses the Profile's own building pins (a building
// for new construction, a wrench for renovations and demolitions); violent incidents of the last 30 days are dots,
// off unless the question was about crime; the lot is the house pin inside a half-mile ring. Hovering names a point;
// clicking opens its card with Street View. The answer's sources with places are the layer buttons above the map.
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MLMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { SquareArrowOutUpRight, X } from "lucide-react";
import type { MapCrime, MapData, MapPermit, RetrievalPlan } from "../../lib/types";
import { useThemeContext } from "../../contexts/ThemeContext";
import { formatDay, humanizeShoutyCase } from "../../lib/format";
import { buildStyle, groupLayerIds, lotPinImage, themePaint, type Theme } from "../map/mapStyle";
import { apiOrigin, loadMapInfo, streetViewUrl } from "../map/mapInfo";
import { addPinImages } from "../map/pins";
import { addPatternImages } from "../map/patterns";
import { foldAttribution } from "../map/attribution";
import { STROKE } from "../icons";
import { HALF_MILE_M, LENS_COLORS, buildKind, chooseLens, circle, crimeKind, distanceM, permitUnits, type BuildKind } from "./chatLens";
import type { MapLayer } from "./EvidenceSources";

maplibregl.setWorkerUrl(workerUrl);

export const RECENT_DAYS = 30;

type Card =
  | { kind: "building"; build: BuildKind; p: MapPermit }
  | { kind: "crime"; c: MapCrime };

export function ChatMap({ data, plan, show }: { data: MapData; plan?: RetrievalPlan | null; show?: MapLayer }) {
  const { t, i18n } = useTranslation("next");
  const { resolvedTheme } = useThemeContext();
  const theme: Theme = resolvedTheme === "dark" ? "dark" : "light";
  const box = useRef<HTMLDivElement | null>(null);
  const map = useRef<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);
  const [card, setCard] = useState<Card | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number; text: string } | null>(null);
  const [keyOpen, setKeyOpen] = useState(false);
  const [now] = useState(() => Date.now());
  const lens = chooseLens({ mapData: data, plan: plan ?? undefined }) ?? "lot";
  const q = data.queried_address;
  const center = q ? { lat: q.latitude, lon: q.longitude, label: q.label } : null;

  const building = useMemo(() => data.building_permits
    .map((p) => ({ p, kind: buildKind(p) }))
    .filter((x): x is { p: MapPermit; kind: BuildKind } => x.kind !== null && Number.isFinite(x.p.latitude) && Number.isFinite(x.p.longitude)
      && (!center || distanceM(center.lat, center.lon, x.p.latitude, x.p.longitude) <= HALF_MILE_M)), [data, center?.lat, center?.lon]); // eslint-disable-line react-hooks/exhaustive-deps
  const incidents = useMemo(() => center ? data.crimes.filter((c) => crimeKind(c) === "violent" && Number.isFinite(c.latitude)
    && distanceM(center.lat, center.lon, c.latitude, c.longitude) <= HALF_MILE_M && now - Date.parse(c.date) <= RECENT_DAYS * 86_400_000) : [], [data, center?.lat, center?.lon, now]); // eslint-disable-line react-hooks/exhaustive-deps

  const [layers, setLayers] = useState(() => ({
    building: lens === "construction" || show === "building",
    crime: lens === "safety" || show === "crime",
    zoning: true,
  }));
  const live = useRef({ theme, layers, building, incidents });
  useEffect(() => { live.current = { theme, layers, building, incidents }; });

  useEffect(() => {
    let cancelled = false;
    loadMapInfo().then((info) => {
      if (cancelled || !box.current) return;
      const ring = center ? circle(center.lat, center.lon, HALF_MILE_M) : null;
      const pts = [...live.current.building.map((b) => [b.p.longitude, b.p.latitude]), ...live.current.incidents.map((c) => [c.longitude, c.latitude])];
      const coords = ring ? ring.coordinates[0] : pts;
      const b = coords.length > 1 && (lens !== "lot" || show || !center)
        ? [[Math.min(...coords.map((c) => c[0])), Math.min(...coords.map((c) => c[1]))], [Math.max(...coords.map((c) => c[0])), Math.max(...coords.map((c) => c[1]))]] as [[number, number], [number, number]]
        : null;
      let m: MLMap;
      try {
        m = new maplibregl.Map({
          container: box.current,
          style: buildStyle({ theme: live.current.theme, apiOrigin: apiOrigin(), glyphsBase: new URL("/map/fonts", window.location.href).href, tiles: info }),
          ...(b ? { bounds: b, fitBoundsOptions: { padding: 28, maxZoom: 16.5 } }
            : center ? { center: [center.lon, center.lat] as [number, number], zoom: 16.3 } : { center: [-87.68, 41.88] as [number, number], zoom: 11 }),
          minZoom: 10, maxBounds: [[-88.3, 41.5], [-87.2, 42.2]],
          attributionControl: false, dragRotate: false, pitchWithRotate: false, fadeDuration: 0,
        });
      } catch (err) {
        console.warn("Map unavailable in this browser:", err);
        setError(true);
        return;
      }
      map.current = m;
      m.touchZoomRotate.disableRotation();
      m.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: t("map.attribution") }), "bottom-left");
      try { addPinImages(m); addPatternImages(m); } catch { /* added on load */ }
      m.on("styleimagemissing", () => { addPinImages(m); addPatternImages(m); });
      m.once("load", () => {
        if (cancelled) return;
        foldAttribution(m.getContainer());
        addPinImages(m);
        addPatternImages(m);
        if (m.getLayer("parcel-fill")) m.setLayoutProperty("parcel-fill", "visibility", "none");
        const th = live.current.theme;
        const ink = th === "dark" ? "#ffffff" : "#1c1c1c";
        if (ring) {
          m.addSource("chat-ring", { type: "geojson", data: { type: "Feature", geometry: ring, properties: {} } });
          m.addLayer({ id: "chat-ring", type: "line", source: "chat-ring", paint: { "line-color": ink, "line-opacity": 0.5, "line-width": 1.5, "line-dasharray": [2, 2] } }, m.getLayer("building-pin") ? "building-pin" : undefined);
        }
        // Building nearby, on the Profile's own building pins.
        (m.getSource("building") as GeoJSONSource | undefined)?.setData({
          type: "FeatureCollection",
          features: live.current.building.map(({ p, kind }, i) => ({ type: "Feature", id: i, geometry: { type: "Point", coordinates: [p.longitude, p.latitude] }, properties: { kind: kind === "new" ? "new" : "reno", i } })),
        });
        m.addSource("chat-crime", { type: "geojson", data: { type: "FeatureCollection", features: live.current.incidents.map((c, i) => ({ type: "Feature", geometry: { type: "Point", coordinates: [c.longitude, c.latitude] }, properties: { i } })) } });
        m.addLayer({ id: "chat-crime", type: "circle", source: "chat-crime", paint: { "circle-radius": 6, "circle-color": LENS_COLORS.incident, "circle-stroke-color": th === "dark" ? "#1c1c1c" : "#ffffff", "circle-stroke-width": 2 } });
        if (center) {
          m.addSource("chat-lot", { type: "geojson", data: { type: "Feature", geometry: { type: "Point", coordinates: [center.lon, center.lat] }, properties: {} } });
          m.addLayer({ id: "chat-lot", type: "symbol", source: "chat-lot", layout: { "icon-image": lotPinImage(th), "icon-anchor": "bottom", "icon-allow-overlap": true } });
        }
        const pick = ["building-pin", "chat-crime"];
        const describe = (f: maplibregl.MapGeoJSONFeature): { card: Card; text: string } | null => {
          const i = Number(f.properties?.i);
          if (f.layer.id === "building-pin") {
            const b = live.current.building[i];
            if (!b) return null;
            const units = permitUnits(b.p.work_description);
            return { card: { kind: "building", build: b.kind, p: b.p }, text: `${t(`chat.lens.kind.${b.kind}`)}${units ? ` · ${t("chat.lens.units", { count: units })}` : ""}` };
          }
          const c = live.current.incidents[i];
          return c ? { card: { kind: "crime", c }, text: humanizeShoutyCase(c.primary_type) } : null;
        };
        m.on("mousemove", (e) => {
          const f = m.queryRenderedFeatures(e.point, { layers: pick.filter((l) => m.getLayer(l)) })[0];
          const d = f ? describe(f) : null;
          m.getCanvas().style.cursor = d ? "pointer" : "";
          setHover(d ? { x: e.point.x, y: e.point.y, text: d.text } : null);
        });
        m.on("mouseout", () => setHover(null));
        m.on("click", (e) => {
          const f = m.queryRenderedFeatures(e.point, { layers: pick.filter((l) => m.getLayer(l)) })[0];
          const d = f ? describe(f) : null;
          setCard(d ? d.card : null);
        });
        setReady(true);
      });
      if (import.meta.env.DEV) (window as unknown as { __chatMap?: MLMap }).__chatMap = m;
    });
    return () => { cancelled = true; map.current?.remove(); map.current = null; };
  }, [t]); // eslint-disable-line react-hooks/exhaustive-deps

  // "Show on map" from a source turns its layer on.
  useEffect(() => { if (show) setLayers((l) => (l[show] ? l : { ...l, [show]: true })); }, [show]);

  // Turning on a layer whose points sit off-screen frames the half-mile ring (the points live inside it).
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !center) return;
    const pts = [...(layers.building ? building.map((b) => [b.p.longitude, b.p.latitude]) : []), ...(layers.crime ? incidents.map((c) => [c.longitude, c.latitude]) : [])];
    const view = m.getBounds();
    if (!pts.some(([x, y]) => !view.contains([x, y]))) return;
    const ring = circle(center.lat, center.lon, HALF_MILE_M).coordinates[0];
    m.fitBounds([[Math.min(...ring.map((c) => c[0])), Math.min(...ring.map((c) => c[1]))], [Math.max(...ring.map((c) => c[0])), Math.max(...ring.map((c) => c[1]))]], { padding: 28, maxZoom: 16.5, duration: 500 });
  }, [layers.building, layers.crime, ready]); // eslint-disable-line react-hooks/exhaustive-deps

  // Layer buttons: visibility only, nothing reloads.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const vis = (id: string, on: boolean) => { if (m.getLayer(id)) m.setLayoutProperty(id, "visibility", on ? "visible" : "none"); };
    vis("building-pin", layers.building);
    vis("chat-crime", layers.crime);
    for (const id of groupLayerIds("zoning")) vis(id, layers.zoning);
  }, [layers, ready]);

  // A theme switch repaints in place, like the Profile's map.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    for (const { id, paint } of themePaint(theme)) {
      if (!m.getLayer(id)) continue;
      for (const [k, v] of Object.entries(paint)) m.setPaintProperty(id, k as never, v as never);
    }
    if (m.getLayer("chat-lot")) m.setLayoutProperty("chat-lot", "icon-image", lotPinImage(theme));
    if (m.getLayer("chat-ring")) m.setPaintProperty("chat-ring", "line-color", theme === "dark" ? "#ffffff" : "#1c1c1c");
  }, [theme, ready]);

  const money = new Intl.NumberFormat(i18n.language.startsWith("es") ? "es-MX" : "en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0, notation: "compact" });
  const nNew = building.filter((b) => b.kind === "new").length;
  const nOther = building.length - nNew;
  const chips: Array<{ id: keyof typeof layers; label: string }> = [
    ...(building.length > 0 ? [{ id: "building" as const, label: t("chat.map.building", { count: building.length }) }] : []),
    ...(incidents.length > 0 ? [{ id: "crime" as const, label: t("chat.map.incidents", { count: incidents.length }) }] : []),
    { id: "zoning", label: t("chat.map.zoning") },
  ];
  const link = "inline-flex items-center gap-1 text-caption underline underline-offset-2 hover:no-underline touch-target";

  return (
    <div className="flex h-full min-h-[300px] w-full flex-col gap-2" data-testid="chat-map" data-lens={lens}>
      <div className="flex gap-1.5 overflow-x-auto pb-0.5 [scrollbar-width:none]" role="group" aria-label={t("chat.map.layers")}>
        {chips.map((c) => (
          <button key={c.id} type="button" aria-pressed={layers[c.id]} onClick={() => setLayers((l) => ({ ...l, [c.id]: !l[c.id] }))}
            className={`shrink-0 rounded-full px-3 py-1.5 text-caption font-medium touch-target ${layers[c.id] ? "bg-nx-ink text-nx-on-ink" : "ring-1 ring-nx-ink/15 hover:bg-nx-ink/5"}`}
            data-testid={`map-layer-${c.id}`}>
            {c.label}
          </button>
        ))}
      </div>
      <div className="relative min-h-[260px] flex-1 overflow-hidden rounded-2xl bg-nx-block">
        <div ref={box} className="absolute inset-0" style={{ position: "absolute" }} aria-label={t("chat.mapLabel")} role="region" />
        {error && <p className="absolute inset-0 grid place-items-center p-4 text-caption nx-muted">{t("chat.mapUnavailable")}</p>}
        {hover && !card && (
          <div className="pointer-events-none absolute z-10 rounded-lg bg-nx-page px-2.5 py-1 text-caption font-medium shadow-[0_2px_10px_rgb(0_0_0/0.15)]" style={{ left: hover.x + 12, top: hover.y - 32 }} data-testid="map-hover">{hover.text}</div>
        )}
        {/* The key: open on wide maps, one button on a phone. */}
        <div className="absolute right-2 top-2 z-10 flex flex-col items-end gap-1">
          <button type="button" onClick={() => setKeyOpen((o) => !o)} aria-expanded={keyOpen} className="rounded-lg bg-nx-page/95 px-2.5 py-1 text-caption font-medium shadow-[0_1px_4px_rgb(0_0_0/0.15)] sm:hidden touch-target">{t("chat.map.key")}</button>
          <div className={`${keyOpen ? "flex" : "hidden"} max-w-[15rem] flex-col gap-1 rounded-xl bg-nx-page/95 px-3 py-2 text-caption shadow-[0_2px_12px_rgb(0_0_0/0.12)] sm:flex`} data-testid="chat-map-key">
            {center && <span className="flex items-center gap-2 font-medium"><span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-sm bg-nx-lot" />{center.label}</span>}
            {center && <span className="nx-muted">{t("chat.map.ring")}</span>}
            {layers.building && nNew > 0 && <span className="flex items-center gap-2"><span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: LENS_COLORS.new }} />{t("chat.map.new", { count: nNew })}</span>}
            {layers.building && nOther > 0 && <span className="flex items-center gap-2"><span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: LENS_COLORS.renovation }} />{t("chat.map.reno", { count: nOther })}</span>}
            {layers.crime && incidents.length > 0 && <span className="flex items-center gap-2"><span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: LENS_COLORS.incident }} />{t("chat.map.incidentsKey", { count: incidents.length })}</span>}
            {!center && plan?.location?.type === "address" && <span className="nx-muted">{t("chat.lens.noPoint")}</span>}
            {lens === "lot" && building.length === 0 && incidents.length === 0 && <span className="nx-muted">{t("chat.lens.lot")}</span>}
          </div>
        </div>
        {card && (
          <div className="absolute inset-x-2 bottom-2 z-20 flex flex-col gap-1 rounded-2xl bg-nx-page p-3 text-caption shadow-[0_6px_24px_rgb(0_0_0/0.2)] sm:inset-x-auto sm:left-3 sm:w-80" data-testid="map-card">
            <div className="flex items-center gap-2">
              <span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: card.kind === "crime" ? LENS_COLORS.incident : LENS_COLORS[card.build] }} />
              <strong className="text-body">{card.kind === "crime" ? humanizeShoutyCase(card.c.primary_type) : `${t(`chat.lens.kind.${card.build}`)}${permitUnits(card.p.work_description) ? ` · ${t("chat.lens.units", { count: permitUnits(card.p.work_description) })}` : ""}`}</strong>
              <span className="flex-1" />
              <button type="button" onClick={() => setCard(null)} aria-label={t("chat.map.closeCard")} className="grid h-7 w-7 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon"><X aria-hidden className="h-4 w-4" strokeWidth={STROKE} /></button>
            </div>
            {card.kind === "building" ? (
              <>
                <span className="nx-muted">{[card.p.estimated_cost ? money.format(card.p.estimated_cost) : null, card.p.issue_date ? t("chat.src.issued", { date: formatDay(card.p.issue_date) }) : null].filter(Boolean).join(" · ")}</span>
                <span className="line-clamp-3">{humanizeShoutyCase(card.p.work_description)}</span>
              </>
            ) : (
              <>
                <span className="nx-muted">{[formatDay(card.c.date), card.c.arrest === true || card.c.arrest === "true" ? t("chat.map.arrest") : t("chat.map.noArrest")].filter(Boolean).join(" · ")}</span>
                {card.c.description && <span>{humanizeShoutyCase(card.c.description)}</span>}
              </>
            )}
            <a href={streetViewUrl(card.kind === "crime" ? card.c.latitude : card.p.latitude, card.kind === "crime" ? card.c.longitude : card.p.longitude)} target="_blank" rel="noopener noreferrer" className={link}>
              {t("chat.src.streetView")}<SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} /><span className="sr-only">{t("common:opensInNewTab")}</span>
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
