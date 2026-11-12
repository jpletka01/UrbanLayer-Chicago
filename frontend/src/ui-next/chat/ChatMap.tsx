// An answer's map, opened from its preview (brief "Chat"): the new UI's one map style over our own tiles (Items 80,
// 90-91; no satellite), with the answer's crimes, 311 requests and permits as dots by kind and the asked-about
// address as the lot's pin. A key counts what's drawn.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import * as maplibregl from "maplibre-gl";
import type { Map as MLMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { MapData } from "../../lib/types";
import { useThemeContext } from "../../contexts/ThemeContext";
import { buildStyle, lotPinImage, themePaint, type Theme } from "../map/mapStyle";
import { apiOrigin, loadMapInfo } from "../map/mapInfo";
import { addPinImages } from "../map/pins";
import { addPatternImages } from "../map/patterns";
import { foldAttribution } from "../map/attribution";
import { mapBounds, mapPoints, pointCounts, type PointKind } from "./chatModel";

maplibregl.setWorkerUrl(workerUrl);

/** Coastal (Item 74): one color per kind, told apart by lightness too. */
export const POINT_COLORS: Record<PointKind, string> = { crime: "#FE9179", request: "#72B0AB", permit: "#B89D47" };

function addPoints(m: MLMap, data: MapData, theme: Theme) {
  const ring = theme === "dark" ? "#1c1c1c" : "#ffffff";
  m.addSource("chat-points", { type: "geojson", data: mapPoints(data) });
  m.addLayer({
    id: "chat-points", type: "circle", source: "chat-points",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 3, 16, 6],
      "circle-color": ["match", ["get", "kind"], "crime", POINT_COLORS.crime, "request", POINT_COLORS.request, POINT_COLORS.permit],
      "circle-stroke-color": ring, "circle-stroke-width": 1,
    },
  });
  const q = data.queried_address;
  if (q) {
    m.addSource("chat-address", { type: "geojson", data: { type: "Feature", geometry: { type: "Point", coordinates: [q.longitude, q.latitude] }, properties: {} } });
    m.addLayer({ id: "chat-address", type: "symbol", source: "chat-address",
      layout: { "icon-image": lotPinImage(theme), "icon-anchor": "bottom", "icon-allow-overlap": true } });
  }
}

export function ChatMap({ data }: { data: MapData }) {
  const { t } = useTranslation("next");
  const { resolvedTheme } = useThemeContext();
  const theme: Theme = resolvedTheme === "dark" ? "dark" : "light";
  const box = useRef<HTMLDivElement | null>(null);
  const map = useRef<MLMap | null>(null);
  const [error, setError] = useState(false);
  const live = useRef({ theme, data });
  useEffect(() => { live.current = { theme, data }; });

  useEffect(() => {
    let cancelled = false;
    loadMapInfo().then((info) => {
      if (cancelled || !box.current) return;
      const b = mapBounds(live.current.data);
      let m: MLMap;
      try {
        m = new maplibregl.Map({
          container: box.current,
          style: buildStyle({ theme: live.current.theme, apiOrigin: apiOrigin(), glyphsBase: new URL("/map/fonts", window.location.href).href, tiles: info }),
          ...(b ? { bounds: b, fitBoundsOptions: { padding: 48, maxZoom: 16 } } : { center: [-87.68, 41.88] as [number, number], zoom: 11 }),
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
        // No lot is "this lot" here: the parcel layer's match fill stays off.
        if (m.getLayer("parcel-fill")) m.setLayoutProperty("parcel-fill", "visibility", "none");
        addPoints(m, live.current.data, live.current.theme);
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
    if (m.getLayer("chat-points")) m.setPaintProperty("chat-points", "circle-stroke-color", theme === "dark" ? "#1c1c1c" : "#ffffff");
    if (m.getLayer("chat-address")) m.setLayoutProperty("chat-address", "icon-image", lotPinImage(theme));
  }, [theme]);

  const counts = pointCounts(data);
  const kinds = (Object.keys(counts) as PointKind[]).filter((k) => counts[k] > 0);

  return (
    <div className="relative h-full min-h-[280px] w-full overflow-hidden rounded-2xl bg-nx-block" data-testid="chat-map">
      <div ref={box} className="absolute inset-0" style={{ position: "absolute" }} aria-label={t("chat.mapLabel")} role="region" />
      {error && <p className="absolute inset-0 grid place-items-center p-4 text-caption nx-muted">{t("chat.mapUnavailable")}</p>}
      <div className="absolute right-3 top-3 flex flex-col gap-1 rounded-xl bg-nx-page/95 px-3 py-2 text-caption shadow-[0_2px_12px_rgb(0_0_0/0.12)]" data-testid="chat-map-key">
        {data.queried_address && (
          <span className="flex items-center gap-2"><span aria-hidden className="h-2.5 w-2.5 rounded-sm bg-nx-lot" />{data.queried_address.label}</span>
        )}
        {kinds.map((k) => (
          <span key={k} className="flex items-center gap-2">
            <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: POINT_COLORS[k] }} />
            {t(`chat.point.${k}`, { count: counts[k] })}
          </span>
        ))}
      </div>
    </div>
  );
}
