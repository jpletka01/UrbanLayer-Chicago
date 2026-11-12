// An answer's map (Phase 8): the new UI's one map style over our own tiles (Items 80, 90-91; no satellite), showing
// what the question was about (chatLens.ts, owner's review 2026-11-12): the lot and its zoning; crime counted in
// block-sized squares within half a mile, with pins only for the few recent ones nearby; new buildings, demolitions
// and big renovations within half a mile with the closest listed. A key says what is drawn and what is left out.
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import * as maplibregl from "maplibre-gl";
import type { Map as MLMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { MapData, RetrievalPlan } from "../../lib/types";
import { useThemeContext } from "../../contexts/ThemeContext";
import { buildStyle, lotPinImage, themePaint, type Theme } from "../map/mapStyle";
import { apiOrigin, loadMapInfo } from "../map/mapInfo";
import { addPinImages } from "../map/pins";
import { addPatternImages } from "../map/patterns";
import { foldAttribution } from "../map/attribution";
import { chooseLens, lensView, type LensView } from "./chatLens";

maplibregl.setWorkerUrl(workerUrl);

/** Coastal (Item 74), told apart by lightness too. */
export const LENS_COLORS = { violent: "#FE9179", property: "#72B0AB", other: "#B89D47", new: "#72B0AB", renovation: "#B89D47", demolition: "#FE9179", squares: "#FE9179", area: "#72B0AB" } as const;

function bounds(v: LensView): [[number, number], [number, number]] | null {
  const ring = v.ring?.coordinates[0];
  const pts: Array<[number, number]> = ring ? ring.map((c) => [c[0], c[1]] as [number, number])
    : (v.squares?.features ?? []).flatMap((f) => f.geometry.coordinates[0].map((c) => [c[0], c[1]] as [number, number]));
  if (pts.length === 0) return null;
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  return [[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]];
}

function addLensLayers(m: MLMap, v: LensView, theme: Theme) {
  const edge = theme === "dark" ? "#1c1c1c" : "#ffffff";
  const ink = theme === "dark" ? "#ffffff" : "#1c1c1c";
  if (v.squares && v.squares.features.length > 0) {
    m.addSource("lens-squares", { type: "geojson", data: v.squares });
    m.addLayer({ id: "lens-squares", type: "fill", source: "lens-squares",
      paint: { "fill-color": v.lens === "area" ? LENS_COLORS.area : LENS_COLORS.squares, "fill-opacity": ["interpolate", ["linear"], ["get", "share"], 0, 0.15, 1, 0.75] } });
  }
  if (v.ring) {
    m.addSource("lens-ring", { type: "geojson", data: { type: "Feature", geometry: v.ring, properties: {} } });
    m.addLayer({ id: "lens-ring", type: "line", source: "lens-ring", paint: { "line-color": ink, "line-opacity": 0.55, "line-width": 1.5, "line-dasharray": [2, 2] } });
  }
  if (v.pins.features.length > 0) {
    m.addSource("lens-pins", { type: "geojson", data: v.pins });
    const color: maplibregl.ExpressionSpecification = ["match", ["get", "kind"],
      "violent", LENS_COLORS.violent, "property", LENS_COLORS.property, "new", LENS_COLORS.new,
      "renovation", LENS_COLORS.renovation, "demolition", LENS_COLORS.demolition, LENS_COLORS.other];
    m.addLayer({ id: "lens-pins", type: "circle", source: "lens-pins", paint: {
      // Construction: sized by cost (square root, 5–16 px); safety: one size.
      "circle-radius": v.lens === "construction" ? ["interpolate", ["linear"], ["sqrt", ["get", "cost"]], 0, 5, 3000, 16] : 5,
      "circle-color": color, "circle-stroke-color": edge, "circle-stroke-width": 1.5,
    } });
    if (v.lens === "construction") {
      m.addLayer({ id: "lens-units", type: "symbol", source: "lens-pins", filter: [">", ["get", "units"], 0],
        layout: { "text-field": ["concat", ["to-string", ["get", "units"]], " u"], "text-font": ["Noto Sans Regular"], "text-size": 11, "text-offset": [0, 1.4], "text-anchor": "top" },
        paint: { "text-color": ink, "text-halo-color": edge, "text-halo-width": 1.5 } });
    }
  }
  if (v.center) {
    m.addSource("lens-lot", { type: "geojson", data: { type: "Feature", geometry: { type: "Point", coordinates: [v.center.lon, v.center.lat] }, properties: {} } });
    m.addLayer({ id: "lens-lot", type: "symbol", source: "lens-lot", layout: { "icon-image": lotPinImage(theme), "icon-anchor": "bottom", "icon-allow-overlap": true } });
  }
}

export function ChatMap({ data, plan }: { data: MapData; plan?: RetrievalPlan | null }) {
  const { t, i18n } = useTranslation("next");
  const { resolvedTheme } = useThemeContext();
  const theme: Theme = resolvedTheme === "dark" ? "dark" : "light";
  const box = useRef<HTMLDivElement | null>(null);
  const map = useRef<MLMap | null>(null);
  const [error, setError] = useState(false);
  const lens = chooseLens({ mapData: data, plan: plan ?? undefined }) ?? "lot";
  const [now] = useState(() => Date.now());
  const view = useMemo(() => lensView(data, lens, now), [data, lens, now]);
  const live = useRef({ theme, view });
  useEffect(() => { live.current = { theme, view }; });

  useEffect(() => {
    let cancelled = false;
    loadMapInfo().then((info) => {
      if (cancelled || !box.current) return;
      const v = live.current.view;
      const b = v.lens === "lot" ? null : bounds(v);
      let m: MLMap;
      try {
        m = new maplibregl.Map({
          container: box.current,
          style: buildStyle({ theme: live.current.theme, apiOrigin: apiOrigin(), glyphsBase: new URL("/map/fonts", window.location.href).href, tiles: info }),
          ...(b ? { bounds: b, fitBoundsOptions: { padding: 24, maxZoom: 16.5 } }
            : v.center ? { center: [v.center.lon, v.center.lat] as [number, number], zoom: 16.3 } : { center: [-87.68, 41.88] as [number, number], zoom: 11 }),
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
        addLensLayers(m, live.current.view, live.current.theme);
      });
      if (import.meta.env.DEV) (window as unknown as { __chatMap?: MLMap }).__chatMap = m;
    });
    return () => { cancelled = true; map.current?.remove(); map.current = null; };
  }, [t]);

  // A theme switch repaints in place, like the Profile's map.
  useEffect(() => {
    const m = map.current;
    if (!m || !m.isStyleLoaded()) return;
    for (const { id, paint } of themePaint(theme)) {
      if (!m.getLayer(id)) continue;
      for (const [k, v] of Object.entries(paint)) m.setPaintProperty(id, k as never, v as never);
    }
    if (m.getLayer("lens-lot")) m.setLayoutProperty("lens-lot", "icon-image", lotPinImage(theme));
    if (m.getLayer("lens-pins")) m.setPaintProperty("lens-pins", "circle-stroke-color", theme === "dark" ? "#1c1c1c" : "#ffffff");
  }, [theme]);

  const days = plan?.time_range_days ?? 90;
  const area = t("chat.lens.theArea");
  const money = new Intl.NumberFormat(i18n.language.startsWith("es") ? "es-MX" : "en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0, notation: "compact" });
  const key = view.lens === "lot" ? [t("chat.lens.lot"), t("chat.lens.lotLeftOut")]
    : view.lens === "safety" ? [
        view.center ? t("chat.lens.safety", { count: view.counts.shown, days }) : t("chat.lens.safetyArea", { count: view.counts.shown, days }),
        t("chat.lens.split", { violent: view.counts.violent ?? 0, property: view.counts.property ?? 0 }),
        ...(view.center ? [t("chat.lens.inArea", { count: view.counts.inArea, area })] : []),
        view.pins.features.length > 0 ? t("chat.lens.recentPins", { count: view.pins.features.length }) : view.center ? t("chat.lens.noPins") : "",
      ].filter(Boolean)
    : view.lens === "construction" ? [
        view.center ? t("chat.lens.construction", { count: view.counts.shown }) : t("chat.lens.constructionArea", { count: view.counts.shown }),
        t("chat.lens.smallLeftOut", { count: view.counts.inArea - view.counts.shown }),
      ]
    : [t("chat.lens.area", { count: view.counts.shown, days })];
  // An address the chat couldn't place exactly: the map counts the whole community area, and says so.
  if (!view.center && plan?.location?.type === "address" && view.lens !== "lot") key.push(t("chat.lens.noPoint"));

  return (
    <div className="flex h-full min-h-[300px] w-full flex-col gap-3" data-testid="chat-map" data-lens={view.lens}>
      <div className="relative min-h-[260px] flex-1 overflow-hidden rounded-2xl bg-nx-block">
        <div ref={box} className="absolute inset-0" style={{ position: "absolute" }} aria-label={t("chat.mapLabel")} role="region" />
        {error && <p className="absolute inset-0 grid place-items-center p-4 text-caption nx-muted">{t("chat.mapUnavailable")}</p>}
        <div className="absolute right-3 top-3 flex max-w-[70%] flex-col gap-1 rounded-xl bg-nx-page/95 px-3 py-2 text-caption shadow-[0_2px_12px_rgb(0_0_0/0.12)]" data-testid="chat-map-key">
          {view.center && <span className="flex items-center gap-2 font-medium"><span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-sm bg-nx-lot" />{view.center.label}</span>}
          {key.map((line, i) => <span key={i} className={i === 0 ? "font-medium" : "nx-muted"}>{line}</span>)}
        </div>
      </div>
      {view.lens === "construction" && view.closest.length > 0 && (
        <ol className="flex flex-col gap-1.5" data-testid="chat-map-closest">
          {view.closest.map((c, i) => (
            <li key={i} className="flex items-start gap-2 text-caption">
              <span aria-hidden className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: LENS_COLORS[c.kind] }} />
              <span className="min-w-0 flex-1">
                <span className="font-medium">{t(`chat.lens.kind.${c.kind}`)}</span>
                {c.units ? ` · ${t("chat.lens.units", { count: c.units })}` : ""}{c.cost ? ` · ${money.format(c.cost)}` : ""} · {t("chat.lens.away", { feet: Math.round(c.distanceM * 3.281) })}
                <span className="block truncate nx-muted" title={c.description}>{c.description}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
