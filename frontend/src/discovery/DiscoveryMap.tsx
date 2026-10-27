// Discovery results map (PR6). Reuses Explore's deck.gl ScatterplotLayer + useMapboxOverlay.
// Renders the FULL ordered coord set from /search/pins (NOT the list window). Colors by
// upside_score with a distinct "no data" swatch (upsideColor). Bidirectional hover sync with
// the result list via shared hoveredPin. No tier gating here — PR9 owns the free/paid line.

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ScatterplotLayer } from "@deck.gl/layers";
import { useThemeContext } from "../contexts/ThemeContext";
import { useMapboxOverlay } from "../lib/useMapboxOverlay";
import { buildDiscoveryMapModel, type DiscoveryMapRenderPoint } from "./discoveryMapModel";
import type { PinPoint } from "./types";

interface DiscoveryMapProps {
  points: PinPoint[];
  truncated: boolean;
  total: number;
  hoveredPin: string | null;
  onHoverPin: (pin: string | null) => void;
  onOpenParcel: (pin: string) => void;
  // PR9 gate: Pro gets upside coloring + interactivity; free gets land-use color, view-only.
  colorBy: "upside" | "land_use";
  interactive: boolean;
  status: "idle" | "loading" | "ready" | "unavailable";
  visible: boolean;
}

const HIGHLIGHT_RING: [number, number, number, number] = [249, 164, 116, 255];
const DARK_STYLE = "mapbox://styles/mapbox/dark-v11";
const LIGHT_STYLE = "mapbox://styles/mapbox/light-v11";

export function DiscoveryMap({
  points,
  truncated,
  total,
  hoveredPin,
  onHoverPin,
  onOpenParcel,
  colorBy,
  interactive,
  status,
  visible,
}: DiscoveryMapProps) {
  const { t } = useTranslation("pages");
  const { resolvedTheme } = useThemeContext();
  const themeStyle = resolvedTheme === "light" ? LIGHT_STYLE : DARK_STYLE;
  const [initialStyle] = useState(themeStyle);
  const {
    containerRef,
    mapRef,
    overlayRef,
    mapReady,
    styleRevision,
  } = useMapboxOverlay({
    center: [-87.6298, 41.8781],
    zoom: 10,
    interleaved: false,
    style: initialStyle,
  });

  const model = useMemo(
    () => buildDiscoveryMapModel(points, total, truncated, colorBy),
    [points, total, truncated, colorBy],
  );
  const { renderPoints } = model;
  const visibleLegendRows = useMemo(
    () => model.legendRows.filter((row) => row.count > 0),
    [model.legendRows],
  );
  const [sizeRevision, setSizeRevision] = useState(0);
  const [keyOpen, setKeyOpen] = useState(false);
  const lastSizeRef = useRef({ width: -1, height: -1 });
  const appliedStyleRef = useRef(initialStyle);

  // Row hover/focus highlights the corresponding dot for both tiers. The ring
  // is a separate non-pickable layer, so the encoded data fill never changes.
  const highlightedPoint = useMemo(
    () => hoveredPin ? renderPoints.find((point) => point.pin === hoveredPin) ?? null : null,
    [renderPoints, hoveredPin],
  );

  const layers = useMemo(() => {
    if (!renderPoints.length) return [];
    const pointsLayer = new ScatterplotLayer<DiscoveryMapRenderPoint>({
      id: "discovery-pins",
      data: renderPoints,
      getPosition: (d) => [d.lon as number, d.lat as number],
      getFillColor: (d) => d.fillColor,
      getRadius: 8,
      radiusMinPixels: 2,
      radiusMaxPixels: 9,
      pickable: interactive,
      autoHighlight: false,
      onHover: interactive
        ? (info) => onHoverPin(info.object ? (info.object as PinPoint).pin : null)
        : undefined,
      onClick: interactive
        ? (info) => {
            if (info.object) onOpenParcel((info.object as PinPoint).pin);
          }
        : undefined,
      updateTriggers: { getFillColor: [colorBy] },
    });
    if (!highlightedPoint) return [pointsLayer];
    const highlightLayer = new ScatterplotLayer<DiscoveryMapRenderPoint>({
      id: "discovery-pin-highlight",
      data: [highlightedPoint],
      getPosition: (d) => [d.lon as number, d.lat as number],
      getRadius: 12,
      radiusUnits: "pixels",
      filled: false,
      stroked: true,
      getLineColor: HIGHLIGHT_RING,
      getLineWidth: 2.5,
      lineWidthUnits: "pixels",
      pickable: false,
    });
    return [pointsLayer, highlightLayer];
  }, [renderPoints, highlightedPoint, colorBy, interactive, onHoverPin, onOpenParcel]);

  const legendTitle = colorBy === "upside" ? t("discovery.legendUpside") : t("discovery.legendLandUse");

  useEffect(() => {
    if (!overlayRef.current) return;
    overlayRef.current.setProps({
      layers,
      // Hover identity on the map itself — the list window may not contain this pin.
      getTooltip: interactive
        ? ({ object }: { object?: PinPoint }) =>
            object
              ? {
                  text:
                    object.upside != null
                      ? `${object.pin}\n${t("discovery.upsideShort", { n: Math.round(object.upside) })}`
                      : object.pin,
                }
              : null
        : undefined,
    });
  }, [layers, overlayRef, interactive, styleRevision, t]);

  // Theme changes swap only the Discovery basemap. Mapbox keeps its camera
  // through setStyle(); capture/restore it explicitly and rebuild the Deck
  // layers on the resulting style.load revision for a deterministic contract.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || appliedStyleRef.current === themeStyle) return;
    const camera = {
      center: map.getCenter(),
      zoom: map.getZoom(),
      bearing: map.getBearing(),
      pitch: map.getPitch(),
    };
    const restoreCamera = () => {
      map.jumpTo(camera);
      map.resize();
    };
    map.once("style.load", restoreCamera);
    appliedStyleRef.current = themeStyle;
    map.setStyle(themeStyle);
    return () => {
      map.off("style.load", restoreCamera);
    };
  }, [mapReady, mapRef, themeStyle]);

  // Mapbox can initialize while this pane is display:none. Resize it when the
  // pane is revealed and whenever its real container changes size, then let the
  // fit-bounds effect run against the resized canvas.
  useEffect(() => {
    const container = containerRef.current;
    const map = mapRef.current;
    if (!container || !map || !mapReady || !visible) return;

    let frame = 0;
    const resize = (force: boolean) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const { width, height } = container.getBoundingClientRect();
        if (width <= 0 || height <= 0) return;
        const previous = lastSizeRef.current;
        if (!force && previous.width === width && previous.height === height) return;
        lastSizeRef.current = { width, height };
        map.resize();
        setSizeRevision((revision) => revision + 1);
      });
    };

    resize(true);
    const observer = typeof ResizeObserver === "undefined"
      ? null
      : new ResizeObserver(() => resize(false));
    observer?.observe(container);
    return () => {
      cancelAnimationFrame(frame);
      observer?.disconnect();
    };
  }, [containerRef, mapReady, mapRef, visible]);

  // Fit to the mapped points' bounds when they change.
  useEffect(() => {
    if (!mapRef.current || !mapReady || !visible || renderPoints.length === 0) return;
    mapRef.current.resize();
    let minLat = 90, minLon = 180, maxLat = -90, maxLon = -180;
    for (const p of renderPoints) {
      minLat = Math.min(minLat, p.lat as number);
      maxLat = Math.max(maxLat, p.lat as number);
      minLon = Math.min(minLon, p.lon as number);
      maxLon = Math.max(maxLon, p.lon as number);
    }
    mapRef.current.fitBounds(
      [[minLon, minLat], [maxLon, maxLat]],
      { padding: 48, duration: 800, maxZoom: 15 },
    );
  }, [renderPoints, mapReady, mapRef, sizeRevision, visible]);

  const stateMessage =
    status === "idle"
      ? t("discovery.mapIdle")
      : status === "loading"
        ? t("discovery.mapLoading")
        : status === "unavailable"
          ? t("discovery.mapUnavailable")
          : total === 0
            ? t("discovery.mapEmpty")
            : renderPoints.length === 0
              ? t("discovery.mapNoCoordinates", { count: model.returnedCount })
              : null;

  const summary = t("discovery.mapSummary", {
    plotted: renderPoints.length.toLocaleString(),
    unlocated: model.unlocatedCount.toLocaleString(),
    omitted: model.omittedByCapCount.toLocaleString(),
  });

  return (
    <div
      className="relative h-full w-full"
      role="region"
      aria-label={t("discovery.mapAria")}
      data-testid="discovery-map"
    >
      <div ref={containerRef} className="absolute inset-0" data-testid="discovery-map-container" />

      <p className="sr-only" role="status" aria-live="polite">
        {stateMessage ?? summary}
      </p>

      {stateMessage && (
        <div className="absolute inset-0 z-10 flex items-center justify-center p-5" aria-hidden="true">
          <p className="max-w-sm rounded-lg border border-dark-border bg-dark-surface/95 px-4 py-3 text-center text-body text-text-secondary shadow-lg">
            {stateMessage}
          </p>
        </div>
      )}

      {/* Phones disclose the counted key from the top-left, away from Mapbox's
          bottom attribution/wordmark and bottom-right navigation controls. */}
      {renderPoints.length > 0 && (
        <button
          type="button"
          aria-expanded={keyOpen}
          aria-controls="discovery-map-key"
          onClick={() => setKeyOpen((open) => !open)}
          className="absolute left-3 top-3 z-20 rounded-lg border border-dark-border bg-dark-surface/95 px-3 py-2 text-caption text-text-secondary shadow-card md:hidden"
          data-testid="discovery-map-key-button"
        >
          {t("discovery.mapKey")}
        </button>
      )}

      {renderPoints.length > 0 && (
        <div
          id="discovery-map-key"
          className={`${keyOpen ? "block" : "hidden"} absolute left-3 top-14 z-20 max-h-[calc(100%-7rem)] min-w-44 overflow-y-auto rounded-lg border border-dark-border bg-dark-surface/95 px-3 py-2 shadow-card md:left-auto md:right-3 md:top-3 md:block`}
          data-testid="discovery-map-legend"
        >
          <div className="mb-1 text-overline uppercase text-text-muted">
            {legendTitle}
          </div>
          {visibleLegendRows.map((item) => (
            <div key={item.key} className="flex items-center gap-2 text-micro text-text-secondary">
              <span
                className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <span className="min-w-0 flex-1">{t(`discovery.${item.i18nKey}`, item.label)}</span>
              <span className="tabular-nums text-text-muted">{item.count.toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}

      {status === "ready" && (model.unlocatedCount > 0 || model.omittedByCapCount > 0) && (
        <div className="absolute bottom-8 left-3 z-10 max-w-[calc(100%-5rem)] space-y-1 rounded-lg border border-dark-border bg-dark-surface/95 px-3 py-2 text-micro text-text-secondary">
          <p>{t("discovery.mapPlotted", {
            count: model.returnedCount,
            plotted: renderPoints.length.toLocaleString(),
            returned: model.returnedCount.toLocaleString(),
          })}</p>
          {model.unlocatedCount > 0 && (
            <p>{t("discovery.mapUnlocated", { count: model.unlocatedCount })}</p>
          )}
          {model.omittedByCapCount > 0 && (
            <p>{t("discovery.mapCapped", { count: model.omittedByCapCount })}</p>
          )}
        </div>
      )}
    </div>
  );
}
