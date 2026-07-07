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
import { zoneColor, overlayColor, incentiveZoneColor } from "../../lib/mapColors";
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
    pickingRadius: 8,
    getTooltip: (info) => {
      const p = (info as { object?: Record<string, unknown> & { properties?: Record<string, unknown> } }).object;
      if (!p) return null;
      let tip = (p.__tip as string | undefined)
        ?? (p.properties?.__tip as string | undefined)
        ?? (p.properties?.ZONE_CLASS as string | undefined);
      if (!tip && typeof p.sale_price === "number") {
        tip = `${fmtPrice(p.sale_price as number)}${p.sale_date ? ` · ${String(p.sale_date).slice(0, 10)}` : ""}`;
      }
      if (!tip && typeof p.name === "string" && (p.type === "cta_rail" || p.type === "metra")) {
        tip = `${p.name}${Array.isArray(p.lines) ? ` · ${(p.lines as string[]).join(", ")}` : ""}`;
      }
      return tip ? { html: `<div>${esc(tip)}</div>`, style: TIP_STYLE } : null;
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
        id: "pm-zoning",
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
      for (const f of layers.overlays?.features ?? []) {
        const type = String(f.properties?.layer_type ?? f.properties?.type ?? "overlay");
        const c = overlayColor(type);
        layerList.push(new GeoJsonLayer({
          id: `pm-ov-${type}-${layerList.length}`,
          data: [{ ...f, properties: { ...f.properties, __tip: String(f.properties?.name ?? type).replace(/_/g, " ") } }],
          getFillColor: [c[0], c[1], c[2], 40],
          getLineColor: [c[0], c[1], c[2], 220],
          lineWidthMinPixels: 2,
          pickable: true,
        }));
      }
      for (const [feat, kind] of [[layers.tif, "TIF"], [layers.ez, "Enterprise Zone"]] as const) {
        if (!feat) continue;
        const name = String(feat.properties?.name ?? kind);
        const c = incentiveZoneColor(name);
        layerList.push(new GeoJsonLayer({
          id: `pm-inc-${kind}`,
          data: [{ ...feat, properties: { ...feat.properties, __tip: `${kind}: ${name}` } }],
          getFillColor: [c[0], c[1], c[2], 30],
          getLineColor: [c[0], c[1], c[2], 220],
          lineWidthMinPixels: 2,
          pickable: true,
        }));
      }
    }

    if (variant === "place") {
      if (comps?.length) {
        layerList.push(new ScatterplotLayer({
          id: "pm-comps",
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
          id: "pm-transit",
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
      {variant === "place" && comps?.some((c) => c.lat != null) && (
        <div className="absolute bottom-2 left-2 rounded-md bg-dark-surface/90 backdrop-blur border border-dark-border px-2 py-1 text-micro text-text-secondary">
          <span className="inline-block w-2 h-2 rounded-full bg-accent mr-1.5 align-middle" aria-hidden />
          {t("scorecard.map.compsLegend", { count: comps.filter((c) => c.lat != null).length })}
          {comps[0]?.sale_price != null && (
            <span className="text-text-muted"> · {fmtPrice(comps[0].sale_price)}…</span>
          )}
        </div>
      )}
    </div>
  );
}
