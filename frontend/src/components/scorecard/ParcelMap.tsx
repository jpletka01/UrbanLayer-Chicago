// ParcelMap — the Property Profile's scoped map family (2026-07-07 v2 spec).
// THREE maps, one question each, instead of one map with a toggle zoo:
//   "place"      (hero)   — satellite⇄streets, parcel outline, comp dots, transit
//   "zoning"     (Build)  — the surrounding zoning quilt, mapColors zone encoding
//   "boundaries" (Reg/Inc)— overlay/TIF/EZ boundaries that touch the parcel
// Shared mechanics: click-to-activate scroll zoom (never scroll-traps the page),
// lazy mount for below-the-fold variants, and graceful absence — a variant with
// nothing to draw renders nothing (an empty map is worse than none). Colors are
// the established functional encodings from lib/mapColors (same as the chat map).
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { GeoJsonLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { useMapboxOverlay } from "../../lib/useMapboxOverlay";
import { useThemeContext } from "../../contexts/ThemeContext";
import {
  zoneColor, zoneColorCSS, zonePrefix, zonePrefixLabel,
  overlayColor, overlayColorCSS, overlayLabel,
  incentiveZoneColor, incentiveZoneColorCSS,
} from "../../lib/mapColors";
import { getTermInfo } from "../../lib/termDefinitions";
import { fetchTransitStations } from "../../lib/api";
import type { ComparableSale, TransitStation } from "../../lib/types";

export interface ParcelMapLayers {
  zoning: GeoJSON.FeatureCollection | null;
  overlays: GeoJSON.FeatureCollection | null;
  tif: GeoJSON.Feature | null;
  ez: GeoJSON.Feature | null;
}

const ACCENT: [number, number, number, number] = [249, 164, 116, 255];

const TIP_STYLE: Record<string, string> = {
  backgroundColor: "#333",
  color: "#eee",
  fontSize: "12px",
  borderRadius: "8px",
  padding: "6px 10px",
  fontFamily: "Inter, system-ui, sans-serif",
  maxWidth: "240px",
};

/** Layer labels come from external datasets — escape before tooltip HTML. */
function esc(s: string): string {
  return s.replace(/[&<>"']/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]!
  ));
}

function fmtPrice(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n)}`;
}

/** Rough polygon label point: mean of the outer ring. */
function ringCentroid(geom: GeoJSON.Geometry): [number, number] | null {
  const ring = geom.type === "Polygon" ? geom.coordinates[0]
    : geom.type === "MultiPolygon" ? geom.coordinates[0]?.[0]
    : null;
  if (!ring || ring.length === 0) return null;
  let x = 0, y = 0;
  for (const [px, py] of ring as [number, number][]) { x += px; y += py; }
  return [x / ring.length, y / ring.length];
}

interface ParcelMapProps {
  variant: "place" | "zoning" | "boundaries";
  lat: number;
  lon: number;
  parcelGeometry?: GeoJSON.Geometry | null;
  comps?: ComparableSale[];
  layers?: ParcelMapLayers | null;
  showTransit?: boolean;
  className?: string;
  /** Mount GL only when scrolled near the viewport (module maps). */
  lazy?: boolean;
}

export function ParcelMap(props: ParcelMapProps) {
  const [inView, setInView] = useState(!props.lazy);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!props.lazy || inView) return;
    const el = sentinelRef.current;
    // The sentinel may not exist yet (content gate below returns null until
    // `layers` arrives) — re-run when layers land so the observer attaches.
    if (!el) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) setInView(true);
    }, { rootMargin: "200px" });
    io.observe(el);
    return () => io.disconnect();
  }, [props.lazy, inView, props.layers, props.variant]);

  const token = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;
  if (!token) return null;

  // Content gate: module maps render only when they have something to show.
  if (props.variant === "zoning" && !(props.layers?.zoning?.features?.length)) return null;
  if (props.variant === "boundaries"
    && !(props.layers?.overlays?.features?.length || props.layers?.tif || props.layers?.ez)) return null;

  return (
    <div ref={sentinelRef} className={props.className}>
      {inView ? <ParcelMapInner {...props} /> : <div className="w-full h-full min-h-[16rem] rounded-lg border border-dark-border bg-dark-elevated/40" />}
    </div>
  );
}

function ParcelMapInner({ variant, lat, lon, parcelGeometry, comps, layers, showTransit }: ParcelMapProps) {
  const { t } = useTranslation("pages");
  const { resolvedTheme } = useThemeContext();
  const themeStyle = resolvedTheme === "light"
    ? "mapbox://styles/mapbox/light-v11"
    : "mapbox://styles/mapbox/dark-v11";
  const [satellite, setSatellite] = useState(variant === "place");
  const [transit, setTransit] = useState<TransitStation[] | null>(null);

  const initialStyle = useMemo(
    () => (variant === "place" ? "mapbox://styles/mapbox/satellite-streets-v12" : themeStyle),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const zoom = variant === "zoning" ? 15.2 : variant === "boundaries" ? 14.2 : 16.8;

  const { containerRef, mapRef, overlayRef, mapReady, contextRestored } = useMapboxOverlay({
    center: [lon, lat],
    zoom,
    interactive: true,
    clickToActivate: true,
    style: initialStyle,
    pickingRadius: 14,
    // Definition-carrying tooltips, same content model as the chat map
    // (label + name) extended with the termDefinitions description — works on
    // tap too (deck picks on touch; pickingRadius widens the target).
    getTooltip: (info) => {
      const p = (info as { object?: Record<string, unknown> & { properties?: Record<string, unknown> } }).object;
      const lid = (info as { layer?: { id?: string } }).layer?.id ?? "";
      if (!p) return null;
      const props = (p.properties ?? {}) as Record<string, unknown>;
      let html: string | null = null;
      if (lid === "zoning") {
        const zc = String(props.ZONE_CLASS ?? "");
        const cat = zonePrefixLabel(zonePrefix(zc));
        const def = getTermInfo(zc)?.description ?? getTermInfo(zonePrefix(zc))?.description ?? "";
        html = `<strong>${esc(zc)}</strong>${cat ? `<br/><span style="opacity:0.75">${esc(cat)}</span>` : ""}${def ? `<br/><span style="opacity:0.6">${esc(def)}</span>` : ""}`;
      } else if (lid.startsWith("overlay-districts")) {
        const type = String(props.overlay_type ?? props.layer_type ?? "");
        const label = overlayLabel(type) || type.replace(/_/g, " ");
        const name = String(props.NAME ?? props.DIST_NAME ?? props.PD_NAME ?? props.name ?? "");
        const def = getTermInfo(type)?.description ?? "";
        html = `<strong>${esc(label)}</strong>${name && name !== label ? `<br/>${esc(name)}` : ""}${def ? `<br/><span style="opacity:0.6">${esc(def)}</span>` : ""}`;
      } else if (lid.startsWith("incentive-zones")) {
        const kind = String(props.__kind ?? "");
        const name = String(props.name ?? "");
        const term = kind === "TIF" ? "tif_district" : "enterprise_zone";
        const def = getTermInfo(term)?.description ?? "";
        html = `<strong>${esc(kind)}</strong>${name ? `<br/>${esc(name)}` : ""}${def ? `<br/><span style="opacity:0.6">${esc(def)}</span>` : ""}`;
      } else if (lid === "comps" && typeof p.sale_price === "number") {
        html = `<strong>${esc(fmtPrice(p.sale_price as number))}</strong>${p.sale_date ? `<br/>${esc(String(p.sale_date).slice(0, 10))}` : ""}`;
      } else if (lid === "transit-stations" && typeof p.name === "string") {
        html = `<strong>${esc(p.name)}</strong>${Array.isArray(p.lines) ? `<br/>${esc((p.lines as string[]).join(", "))}` : ""}`;
      }
      return html ? { html, style: TIP_STYLE } : null;
    },
  });

  // Satellite ⇄ streets toggle (place variant) + theme flips for street styles.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const target = satellite ? "mapbox://styles/mapbox/satellite-streets-v12" : themeStyle;
    map.setStyle(target);
  }, [satellite, themeStyle, mapReady, mapRef]);

  useEffect(() => {
    if (variant === "place" && showTransit) fetchTransitStations().then(setTransit).catch(() => {});
  }, [variant, showTransit]);

  // deck layers
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay || !mapReady) return;
    const layerList: unknown[] = [];

    if (variant === "zoning" && layers?.zoning) {
      layerList.push(new GeoJsonLayer({
        id: "zoning",
        data: layers.zoning as unknown as GeoJSON.FeatureCollection,
        getFillColor: (f: GeoJSON.Feature) => {
          const c = zoneColor(String(f.properties?.ZONE_CLASS ?? ""));
          return [c[0], c[1], c[2], 70];
        },
        getLineColor: (f: GeoJSON.Feature) => {
          const c = zoneColor(String(f.properties?.ZONE_CLASS ?? ""));
          return [c[0], c[1], c[2], 200];
        },
        lineWidthMinPixels: 1,
        pickable: true,
      }));
      const labels = (layers.zoning.features ?? [])
        .map((f) => {
          const pos = f.geometry ? ringCentroid(f.geometry) : null;
          return pos ? { pos, label: String(f.properties?.ZONE_CLASS ?? "") } : null;
        })
        .filter((d): d is { pos: [number, number]; label: string } => !!d && !!d.label);
      layerList.push(new TextLayer({
        id: "pm-zone-labels",
        data: labels,
        getPosition: (d: { pos: [number, number] }) => d.pos,
        getText: (d: { label: string }) => d.label,
        getSize: 11,
        getColor: resolvedTheme === "light" ? [26, 26, 26, 220] : [255, 255, 255, 220],
        fontFamily: "JetBrains Mono, monospace",
      }));
    }

    if (variant === "boundaries" && layers) {
      // Same color encodings as the chat map (overlayColor by type,
      // incentiveZoneColor by name) — distinct hues per boundary; overlap
      // stays readable because fills are faint washes and identity rides the
      // 2px strokes + the legend.
      (layers.overlays?.features ?? []).forEach((f, i) => {
        const type = String(f.properties?.overlay_type ?? f.properties?.layer_type ?? "overlay");
        const c = overlayColor(type);
        layerList.push(new GeoJsonLayer({
          id: `overlay-districts-${i}`,
          data: [f],
          getFillColor: [c[0], c[1], c[2], 35],
          getLineColor: [c[0], c[1], c[2], 230],
          lineWidthMinPixels: 2,
          pickable: true,
        }));
      });
      for (const [feat, kind] of [[layers.tif, "TIF"], [layers.ez, "Enterprise Zone"]] as const) {
        if (!feat) continue;
        const name = String(feat.properties?.name ?? kind);
        const c = incentiveZoneColor(name);
        layerList.push(new GeoJsonLayer({
          id: `incentive-zones-${kind}`,
          data: [{ ...feat, properties: { ...feat.properties, __kind: kind, name } }],
          getFillColor: [c[0], c[1], c[2], 25],
          getLineColor: [c[0], c[1], c[2], 230],
          lineWidthMinPixels: 2,
          pickable: true,
        }));
      }
    }

    if (variant === "place") {
      if (comps?.length) {
        layerList.push(new ScatterplotLayer({
          id: "comps",
          data: comps.filter((c) => c.lat != null && c.lon != null),
          getPosition: (c: ComparableSale) => [c.lon!, c.lat!],
          getRadius: 6,
          radiusUnits: "pixels",
          getFillColor: ACCENT,
          getLineColor: satellite ? [10, 10, 10, 255] : [255, 255, 255, 255],
          getLineWidth: 2,
          lineWidthUnits: "pixels",
          stroked: true,
          pickable: true,
        }));
      }
      if (transit?.length) {
        layerList.push(new ScatterplotLayer({
          id: "transit-stations",
          data: transit,
          getPosition: (s: TransitStation) => [s.lon, s.lat],
          getRadius: 5,
          radiusUnits: "pixels",
          getFillColor: [255, 255, 255, 230],
          getLineColor: [10, 10, 10, 255],
          getLineWidth: 1.5,
          lineWidthUnits: "pixels",
          stroked: true,
          pickable: true,
        }));
      }
    }

    // Parcel outline — every variant, always on top.
    if (parcelGeometry) {
      layerList.push(new GeoJsonLayer({
        id: "pm-parcel",
        data: [{ type: "Feature", geometry: parcelGeometry, properties: {} }],
        getFillColor: [249, 164, 116, satellite && variant === "place" ? 0 : 25],
        getLineColor: ACCENT,
        lineWidthMinPixels: 2.5,
        pickable: false,
      }));
    } else {
      layerList.push(new ScatterplotLayer({
        id: "pm-pin",
        data: [{ lat, lon }],
        getPosition: () => [lon, lat],
        getRadius: 7,
        radiusUnits: "pixels",
        getFillColor: ACCENT,
        getLineColor: [10, 10, 10, 255],
        getLineWidth: 2,
        lineWidthUnits: "pixels",
        stroked: true,
      }));
    }

    // Attach tooltips for comps/transit via object augmentation at pick time.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    overlay.setProps({ layers: layerList as any });
  }, [variant, layers, comps, transit, parcelGeometry, mapReady, contextRestored, satellite, resolvedTheme, lat, lon, overlayRef]);

  // Map key (top-RIGHT — the Mapbox wordmark owns the bottom-left corner, so
  // that space stays empty on every map): one row per encoding on the map.
  const legend: Array<{ key: string; swatchCSS: string; label: string; kind: "line" | "fill" | "dot" }> = [];
  legend.push({ key: "parcel", swatchCSS: "rgb(249,164,116)", label: t("scorecard.map.keyParcel"), kind: "line" });
  if (variant === "place") {
    if (comps?.some((c) => c.lat != null)) {
      legend.push({
        key: "comps", swatchCSS: "rgb(249,164,116)", kind: "dot",
        label: t("scorecard.map.compsLegend", { count: comps.filter((c) => c.lat != null).length }),
      });
    }
    if (showTransit) legend.push({ key: "transit", swatchCSS: "#ffffff", label: t("scorecard.map.keyTransit"), kind: "dot" });
  } else if (variant === "zoning" && layers?.zoning) {
    const seen = new Map<string, string>();
    for (const f of layers.zoning.features ?? []) {
      const zc = String(f.properties?.ZONE_CLASS ?? "");
      const pfx = zonePrefix(zc);
      if (pfx && !seen.has(pfx)) seen.set(pfx, zoneColorCSS(zc));
    }
    for (const [pfx, css] of [...seen.entries()].slice(0, 6)) {
      legend.push({ key: `z-${pfx}`, swatchCSS: css, label: zonePrefixLabel(pfx) || pfx, kind: "fill" });
    }
  } else if (variant === "boundaries" && layers) {
    const seenTypes = new Set<string>();
    for (const f of layers.overlays?.features ?? []) {
      const type = String(f.properties?.overlay_type ?? f.properties?.layer_type ?? "");
      if (!type || seenTypes.has(type)) continue;
      seenTypes.add(type);
      legend.push({
        key: `ov-${type}`, swatchCSS: overlayColorCSS(type),
        label: overlayLabel(type) || type.replace(/_/g, " "), kind: "fill",
      });
    }
    if (layers.tif) {
      const name = String(layers.tif.properties?.name ?? "TIF");
      legend.push({ key: "tif", swatchCSS: incentiveZoneColorCSS(name), label: `TIF — ${name}`, kind: "fill" });
    }
    if (layers.ez) {
      const name = String(layers.ez.properties?.name ?? "Enterprise Zone");
      legend.push({ key: "ez", swatchCSS: incentiveZoneColorCSS(name), label: t("scorecard.map.keyEz"), kind: "fill" });
    }
  }

  return (
    <div className="relative w-full h-full min-h-[16rem] rounded-lg overflow-hidden border border-dark-border">
      <div ref={containerRef} className="absolute inset-0" />
      {variant === "place" && (
        <div className="absolute top-2 left-2 flex rounded-md overflow-hidden border border-dark-border bg-dark-surface/90 backdrop-blur text-micro">
          <button
            type="button"
            onClick={() => setSatellite(true)}
            className={`px-2 py-1 transition-colors ${satellite ? "bg-dark-elevated text-text-primary" : "text-text-muted hover:text-text-secondary"}`}
          >
            {t("scorecard.map.satellite")}
          </button>
          <button
            type="button"
            onClick={() => setSatellite(false)}
            className={`px-2 py-1 transition-colors ${!satellite ? "bg-dark-elevated text-text-primary" : "text-text-muted hover:text-text-secondary"}`}
          >
            {t("scorecard.map.streets")}
          </button>
        </div>
      )}
      {legend.length > 0 && (
        <div className="absolute top-2 right-2 max-w-[55%] rounded-md bg-dark-surface/90 backdrop-blur border border-dark-border px-2 py-1.5 space-y-0.5">
          {legend.map((row) => (
            <div key={row.key} className="flex items-center gap-1.5 text-micro text-text-secondary leading-tight">
              {row.kind === "dot" ? (
                <span className="w-2 h-2 rounded-full shrink-0 border border-dark-bg" style={{ background: row.swatchCSS }} aria-hidden />
              ) : row.kind === "line" ? (
                <span className="w-3 h-0 border-t-2 shrink-0" style={{ borderColor: row.swatchCSS }} aria-hidden />
              ) : (
                <span className="w-2.5 h-2.5 rounded-[3px] shrink-0 opacity-80" style={{ background: row.swatchCSS }} aria-hidden />
              )}
              <span className="truncate">{row.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
