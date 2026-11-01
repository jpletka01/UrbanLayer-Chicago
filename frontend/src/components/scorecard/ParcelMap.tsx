// ParcelMap — the Property Profile's scoped map family (2026-07-07 v2 spec).
// THREE maps, one question each, instead of one map with a toggle zoo:
//   "place"      (hero)   — satellite⇄streets, parcel outline, comp dots, transit
//   "zoning"     (Build)  — the surrounding zoning quilt, mapColors zone encoding
//   "boundaries" (Reg/Inc)— overlay/TIF/EZ boundaries that touch the parcel
// Shared mechanics: click-to-activate scroll zoom (never scroll-traps the page),
// lazy mount for below-the-fold variants, and graceful absence — a variant with
// nothing to draw renders nothing (an empty map is worse than none). Colors are
// the established functional encodings from lib/mapColors (same as the chat map).
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ScatterplotLayer } from "@deck.gl/layers";
import { useMapboxOverlay } from "../../lib/useMapboxOverlay";
import { useThemeContext } from "../../contexts/ThemeContext";
import {
  zonePrefix, zonePrefixLabel,
  overlayLabel,
} from "../../lib/mapColors";
import { getTermInfo } from "../../lib/termDefinitions";
import { fetchTransitStations } from "../../lib/api";
import {
  unavailableParcelMapSources,
  type ParcelMapLayerState,
  type ParcelMapLayers,
  type ParcelMapSource,
  type ParcelMapVariant,
} from "../../lib/parcelMap";
import type { ComparableSale, TransitStation } from "../../lib/types";
import {
  buildBoundaryMapModel,
  buildZoningMapModel,
} from "./parcelMapModel";
import {
  buildBoundaryDeckLayers,
  buildSubjectParcelLayer,
  buildZoningDeckLayers,
  DEFAULT_PARCEL_MAP_LAYER_STATES,
  type ParcelMapLayerStates,
} from "./parcelMapLayers";
import {
  ParcelMapKeyChip,
  ParcelMapKeyPanel,
  ParcelMapKeySheet,
  type ParcelMapControlSource,
} from "./ParcelMapControls";

export type { ParcelMapLayers } from "../../lib/parcelMap";

const ACCENT: [number, number, number, number] = [249, 164, 116, 255];
/** The open key sits beside the map only when the map's box is at least this wide (map keeps ≥ 2/3 of it). */
const KEY_BESIDE_MIN_PX = 768;

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

interface ParcelMapProps {
  variant: ParcelMapVariant;
  lat: number;
  lon: number;
  parcelGeometry?: GeoJSON.Geometry | null;
  /** Stable Property Profile identity used to reset per-map control state. */
  profileKey?: string | null;
  comps?: ComparableSale[];
  layers?: ParcelMapLayers | null;
  /** Backend parcel-resolution result; approximate identity gets the low-confidence map style. */
  parcelConfidence?: "authoritative" | "approximate" | null;
  showTransit?: boolean;
  className?: string;
  /** Mount GL only when scrolled near the viewport (module maps). */
  lazy?: boolean;
  /** The key row describing this parcel itself (its zoning class), listed first and marked in the key. */
  subjectKey?: string | null;
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

  const unavailable = unavailableParcelMapSources(props.variant, props.layers?.availability);

  // Content gate: module maps render only when they have something to show.
  if (props.variant === "zoning"
    && !(props.layers?.zoning?.features?.length)
    && unavailable.length === 0) return null;
  if (props.variant === "boundaries"
    && !(props.layers?.overlays?.features?.length || props.layers?.tif || props.layers?.ez)
    && unavailable.length === 0) return null;

  return (
    <div ref={sentinelRef} className={props.className}>
      {inView ? (
        <ParcelMapInner
          key={`${props.variant}:${props.profileKey ?? `${props.lat}:${props.lon}`}`}
          {...props}
        />
      ) : (
        <div className="w-full h-full min-h-[16rem] rounded-lg border border-dark-border bg-dark-elevated/40" />
      )}
    </div>
  );
}

function ParcelMapInner({
  variant,
  lat,
  lon,
  parcelGeometry,
  comps,
  layers,
  showTransit,
  parcelConfidence,
  subjectKey,
}: ParcelMapProps) {
  const { t } = useTranslation("pages");
  const { resolvedTheme } = useThemeContext();
  const themeStyle = resolvedTheme === "light"
    ? "mapbox://styles/mapbox/light-v11"
    : "mapbox://styles/mapbox/dark-v11";
  const mapTheme = resolvedTheme === "light" ? "light" : "dark";
  const [satellite, setSatellite] = useState(variant === "place");
  const [transit, setTransit] = useState<TransitStation[] | null>(null);
  const [layerStates, setLayerStates] = useState<ParcelMapLayerStates>({
    ...DEFAULT_PARCEL_MAP_LAYER_STATES,
  });
  const unavailable = unavailableParcelMapSources(variant, layers?.availability);
  const sourceLabel = (source: ParcelMapSource) => t(`scorecard.map.source.${source}`);
  // The key starts collapsed on every screen size; open, it sits beside the map (desktop) or as a sheet (phone).
  const [keyOpen, setKeyOpen] = useState(false);
  const keyButtonRef = useRef<HTMLButtonElement | null>(null);
  const keyId = useId();
  // Beside the map only when the map's box can spare the width; a half-width module map gets the key below it.
  const frameRef = useRef<HTMLDivElement | null>(null);
  const [keyBeside, setKeyBeside] = useState(true);
  useEffect(() => {
    const el = frameRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => setKeyBeside(entry.contentRect.width >= KEY_BESIDE_MIN_PX));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const closeKey = () => {
    setKeyOpen(false);
    keyButtonRef.current?.focus();
  };

  const initialStyle = useMemo(
    () => (variant === "place" ? "mapbox://styles/mapbox/satellite-streets-v12" : themeStyle),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  // Zoning and boundaries share a scale so the two Build-module maps read as
  // one pair (Jack, 2026-07-07); the place map is parcel-tight.
  const zoom = variant === "place" ? 16.8 : 15.2;
  const [mapZoom, setMapZoom] = useState(zoom);
  const zoningModel = useMemo(
    () => buildZoningMapModel(layers?.zoning, layers?.zoning_labels, mapTheme),
    [layers?.zoning, layers?.zoning_labels, mapTheme],
  );
  const boundaryModel = useMemo(
    () => buildBoundaryMapModel(layers, mapTheme),
    [layers, mapTheme],
  );

  const setLayerState = (source: ParcelMapSource, state: ParcelMapLayerState) => {
    setLayerStates((current) => ({ ...current, [source]: state }));
  };

  // The place map only shows what its opening viewport can contain — comps or
  // stations beyond it would exist solely as legend entries nobody can see.
  const VIEW_RADIUS_MI = 0.12;
  const milesFrom = (plat: number, plon: number) => {
    const dLat = (plat - lat) * 69;
    const dLon = (plon - lon) * 69 * Math.cos((lat * Math.PI) / 180);
    return Math.sqrt(dLat * dLat + dLon * dLon);
  };
  const compsInView = useMemo(
    () => (comps ?? []).filter((c) => c.lat != null && c.lon != null
      && (c.distance_mi != null ? c.distance_mi <= VIEW_RADIUS_MI : milesFrom(c.lat!, c.lon!) <= VIEW_RADIUS_MI)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [comps, lat, lon],
  );

  // Box ref so the tooltip closure (created before the hook returns) can
  // multi-pick through the live overlay — the chat map's pattern for points
  // where several boundary layers stack.
  const overlayBoxRef = useRef<import("@deck.gl/mapbox").MapboxOverlay | null>(null);

  const {
    containerRef,
    mapRef,
    overlayRef,
    mapReady,
    contextRestored,
    roadInsertionId,
    styleRevision,
  } = useMapboxOverlay({
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
      } else if (lid.startsWith("overlay-districts") || lid.startsWith("incentive-zones")) {
        // Boundaries stack — list EVERY layer under the pointer (chat map's
        // multi-pick pattern), with the definition of the topmost one.
        const pickInfo = info as { x?: number; y?: number };
        const picks = (pickInfo.x != null && pickInfo.y != null
          ? overlayBoxRef.current?.pickMultipleObjects({ x: pickInfo.x, y: pickInfo.y, radius: 4, depth: 12 })
          : null) ?? [];
        const rows: string[] = [];
        const seen = new Set<string>();
        let topDef = "";
        const source = picks.length > 0 ? picks : [{ layer: { id: lid }, object: p }];
        for (const pk of source) {
          const pid = pk.layer?.id ?? "";
          const pp = ((pk.object as { properties?: Record<string, unknown> } | undefined)?.properties ?? {}) as Record<string, unknown>;
          if (pid.startsWith("overlay-districts")) {
            const type = String(pp.overlay_type ?? pp.layer_type ?? "");
            const label = overlayLabel(type) || type.replace(/_/g, " ");
            const name = String(pp.NAME ?? pp.DIST_NAME ?? pp.PD_NAME ?? pp.name ?? "");
            const key = `${label}|${name}`;
            if (seen.has(key)) continue;
            seen.add(key);
            if (!topDef) topDef = getTermInfo(type)?.description ?? "";
            rows.push(`<strong>${esc(label)}</strong>${name && name !== label ? ` — ${esc(name)}` : ""}`);
          } else if (pid.startsWith("incentive-zones")) {
            const kind = String(pp.__kind ?? "");
            const name = String(pp.name ?? "");
            const key = `${kind}|${name}`;
            if (seen.has(key)) continue;
            seen.add(key);
            if (!topDef) topDef = getTermInfo(kind === "TIF" ? "tif_district" : "enterprise_zone")?.description ?? "";
            rows.push(`<strong>${esc(kind)}</strong>${name ? ` — ${esc(name)}` : ""}`);
          }
        }
        if (rows.length) {
          html = rows.join("<br/>") + (topDef ? `<br/><span style="opacity:0.6">${esc(topDef)}</span>` : "");
        }
      } else if (lid === "comps" && typeof p.sale_price === "number") {
        html = `<strong>${esc(fmtPrice(p.sale_price as number))}</strong>${p.sale_date ? `<br/>${esc(String(p.sale_date).slice(0, 10))}` : ""}`;
      } else if (lid === "transit-stations" && typeof p.name === "string") {
        html = `<strong>${esc(p.name)}</strong>${Array.isArray(p.lines) ? `<br/>${esc((p.lines as string[]).join(", "))}` : ""}`;
      }
      return html ? { html, style: TIP_STYLE } : null;
    },
  });

  useEffect(() => {
    overlayBoxRef.current = overlayRef.current;
  }, [overlayRef, mapReady]);

  // Satellite ⇄ streets toggle (place variant) + theme flips for street styles.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const target = satellite ? "mapbox://styles/mapbox/satellite-streets-v12" : themeStyle;
    map.setStyle(target);
  }, [satellite, themeStyle, mapReady, mapRef]);

  // The desktop key narrows the map's box; tell Mapbox so the canvas follows (no stretched frame).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    map.resize();
  }, [keyOpen, mapReady, mapRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const onZoom = () => setMapZoom(map.getZoom());
    onZoom();
    map.on("zoomend", onZoom);
    return () => {
      map.off("zoomend", onZoom);
    };
  }, [mapReady, mapRef]);

  useEffect(() => {
    if (variant === "place" && showTransit) {
      fetchTransitStations()
        .then((all) => setTransit(all.filter((st) => milesFrom(st.lat, st.lon) <= VIEW_RADIUS_MI)))
        .catch(() => {});
    }
  }, [variant, showTransit]);

  // deck layers
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay || !mapReady) return;
    const layerList: unknown[] = [];

    if (variant === "zoning" && layers?.zoning) {
      layerList.push(...buildZoningDeckLayers({
        model: zoningModel,
        state: layerStates.zoning,
        mapTheme,
        mapZoom,
        roadInsertionId,
      }));
    }

    if (variant === "boundaries" && layers) {
      layerList.push(...buildBoundaryDeckLayers({ model: boundaryModel, states: layerStates }));
    }

    if (variant === "place") {
      if (compsInView.length) {
        layerList.push(new ScatterplotLayer({
          id: "comps",
          data: compsInView,
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

    // Subject parcel stays present above every thematic source. The backend's
    // approximate resolution state is the only thing that can make it low-confidence.
    layerList.push(buildSubjectParcelLayer({
      parcelGeometry,
      lat,
      lon,
      satellite,
      variant,
      confidence: parcelConfidence,
    }));

    // Attach tooltips for comps/transit via object augmentation at pick time.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    overlay.setProps({ layers: layerList as any });
  }, [
    variant, layers, zoningModel, boundaryModel, layerStates, compsInView, transit,
    parcelGeometry, mapReady, contextRestored, satellite, mapTheme, mapZoom,
    roadInsertionId, styleRevision, lat, lon, parcelConfidence, overlayRef,
  ]);

  // Map key (top-RIGHT — the Mapbox wordmark owns the bottom-left corner, so
  // that space stays empty on every map): one row per encoding on the map.
  const legend: Array<{ key: string; swatchCSS: string; label: string; kind: "line" | "fill" | "dot" }> = [];
  legend.push({ key: "parcel", swatchCSS: "rgb(249,164,116)", label: t("scorecard.map.keyParcel"), kind: "line" });
  if (variant === "place") {
    if (compsInView.length) {
      legend.push({
        key: "comps", swatchCSS: "rgb(249,164,116)", kind: "dot",
        label: t("scorecard.map.compsLegend", { count: compsInView.length }),
      });
    }
    if (transit?.length) legend.push({ key: "transit", swatchCSS: "#ffffff", label: t("scorecard.map.keyTransit"), kind: "dot" });
  }

  const controlSources: ParcelMapControlSource[] = [];
  if (variant === "zoning" && layers) {
    controlSources.push({
      source: "zoning",
      label: t("scorecard.map.sourceControl.zoning"),
      availability: layers?.availability?.zoning ?? "available",
      state: layerStates.zoning,
      visibleCount: zoningModel.visibleCount,
      withheldCount: zoningModel.withheldCount,
      rows: zoningModel.legend.map((entry) => ({
        key: entry.zoneClass,
        label: entry.zoneClass,
        swatchCSS: entry.swatchCSS,
        count: entry.count,
        lowConfidenceCount: entry.lowConfidenceCount,
        countKind: "district",
      })),
    });
  } else if (variant === "boundaries" && layers) {
    const boundarySources: Array<Exclude<ParcelMapSource, "zoning">> = ["overlays", "tif", "ez"];
    for (const source of boundarySources) {
      controlSources.push({
        source,
        label: t(`scorecard.map.sourceControl.${source}`),
        availability: layers?.availability?.[source] ?? "available",
        state: layerStates[source],
        visibleCount: boundaryModel.counts[source].visible,
        withheldCount: boundaryModel.counts[source].withheld,
        rows: boundaryModel.legend.filter((entry) => entry.source === source).map((entry) => ({
          key: entry.key,
          label: entry.name && entry.name !== entry.label
            ? `${entry.label} — ${entry.name}`
            : entry.label,
          swatchCSS: entry.swatchCSS,
          count: entry.count,
          lowConfidenceCount: entry.lowConfidenceCount,
          countKind: "feature",
        })),
      });
    }
  }

  const hasKey = variant !== "place" && controlSources.length > 0;
  return (
    <div
      ref={frameRef}
      className={`flex w-full h-full min-h-[16rem] rounded-lg overflow-hidden border border-dark-border ${keyBeside ? "flex-row" : "flex-col"}`}
    >
    <div className="relative min-w-0 min-h-[16rem] flex-1">
      <div ref={containerRef} className="absolute inset-0" />
      {unavailable.length > 0 && (
        <div
          role="status"
          className="absolute z-10 top-2 left-2 max-w-[70%] rounded-md border border-state-warning/40 bg-dark-surface/95 px-2.5 py-1.5 text-micro text-text-secondary shadow-sm backdrop-blur"
        >
          {t("scorecard.map.layerUnavailable", {
            layers: unavailable.map(sourceLabel).join(", "),
          })}
        </div>
      )}
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
      {hasKey && (
        <ParcelMapKeyChip
          sources={controlSources}
          subjectKey={subjectKey}
          open={keyOpen}
          onToggle={() => setKeyOpen((value) => !value)}
          controlsIds={`${keyId}-panel ${keyId}-sheet`}
          buttonRef={keyButtonRef}
        />
      )}
      {hasKey && keyOpen && (
        <ParcelMapKeySheet id={`${keyId}-sheet`} sources={controlSources} subjectKey={subjectKey} onChange={setLayerState} onClose={closeKey} />
      )}
      {variant === "place" && legend.length > 0 && (
        <div className="absolute top-2 right-2 max-w-[55%] max-h-[calc(100%-1rem)] overflow-y-auto rounded-md bg-dark-surface/90 backdrop-blur border border-dark-border px-2 py-1.5 space-y-0.5">
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
    {hasKey && keyOpen && (
      <ParcelMapKeyPanel
        id={`${keyId}-panel`}
        sources={controlSources}
        subjectKey={subjectKey}
        onChange={setLayerState}
        onClose={closeKey}
        placement={keyBeside ? "side" : "below"}
      />
    )}
    </div>
  );
}
