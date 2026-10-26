// Discovery results map (PR6). Reuses Explore's deck.gl ScatterplotLayer + useMapboxOverlay.
// Renders the FULL ordered coord set from /search/pins (NOT the list window). Colors by
// upside_score with a distinct "no data" swatch (upsideColor). Bidirectional hover sync with
// the result list via shared hoveredPin. No tier gating here — PR9 owns the free/paid line.

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ScatterplotLayer } from "@deck.gl/layers";
import { useMapboxOverlay } from "../lib/useMapboxOverlay";
import { buildDiscoveryMapModel } from "./discoveryMapModel";
import { landUseColor, LAND_USE_LEGEND, upsideColor, UPSIDE_LEGEND } from "./upsideColor";
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

const HIGHLIGHT: [number, number, number, number] = [238, 238, 238, 255];

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
  const { containerRef, mapRef, overlayRef, mapReady } = useMapboxOverlay({
    center: [-87.6298, 41.8781],
    zoom: 10,
    interleaved: false,
  });

  const model = useMemo(
    () => buildDiscoveryMapModel(points, total, truncated),
    [points, total, truncated],
  );
  const { mappable } = model;
  const [sizeRevision, setSizeRevision] = useState(0);
  const lastSizeRef = useRef({ width: -1, height: -1 });

  // Row → dot highlight only when interactive (Pro); free is view-only.
  const highlightedIndex = useMemo(
    () => (interactive && hoveredPin ? mappable.findIndex((p) => p.pin === hoveredPin) : -1),
    [mappable, hoveredPin, interactive],
  );

  const layer = useMemo(() => {
    if (!mappable.length) return null;
    return new ScatterplotLayer({
      id: "discovery-pins",
      data: mappable,
      getPosition: (d: PinPoint) => [d.lon as number, d.lat as number],
      getFillColor: (d: PinPoint) =>
        colorBy === "upside" ? upsideColor(d.upside) : landUseColor(d.landUse),
      getRadius: 8,
      radiusMinPixels: 2,
      radiusMaxPixels: 9,
      pickable: interactive,
      autoHighlight: interactive,
      highlightColor: HIGHLIGHT,
      highlightedObjectIndex: highlightedIndex,
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
  }, [mappable, highlightedIndex, colorBy, interactive, onHoverPin, onOpenParcel]);

  const legend = colorBy === "upside" ? UPSIDE_LEGEND : LAND_USE_LEGEND;
  const legendTitle = colorBy === "upside" ? t("discovery.legendUpside") : t("discovery.legendLandUse");

  useEffect(() => {
    if (!overlayRef.current) return;
    overlayRef.current.setProps({
      layers: layer ? [layer] : [],
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
  }, [layer, overlayRef, interactive, t]);

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
    if (!mapRef.current || !mapReady || !visible || mappable.length === 0) return;
    mapRef.current.resize();
    let minLat = 90, minLon = 180, maxLat = -90, maxLon = -180;
    for (const p of mappable) {
      minLat = Math.min(minLat, p.lat as number);
      maxLat = Math.max(maxLat, p.lat as number);
      minLon = Math.min(minLon, p.lon as number);
      maxLon = Math.max(maxLon, p.lon as number);
    }
    mapRef.current.fitBounds(
      [[minLon, minLat], [maxLon, maxLat]],
      { padding: 48, duration: 800, maxZoom: 15 },
    );
  }, [mappable, mapReady, mapRef, sizeRevision, visible]);

  const stateMessage =
    status === "idle"
      ? t("discovery.mapIdle")
      : status === "loading"
        ? t("discovery.mapLoading")
        : status === "unavailable"
          ? t("discovery.mapUnavailable")
          : total === 0
            ? t("discovery.mapEmpty")
            : mappable.length === 0
              ? t("discovery.mapNoCoordinates", { count: model.returnedCount })
              : null;

  const summary = t("discovery.mapSummary", {
    plotted: mappable.length.toLocaleString(),
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

      {/* Legend — upside (Pro) or land use (free), each named */}
      {mappable.length > 0 && (
        <div
          className="absolute right-3 top-3 z-10 space-y-1 rounded-lg border border-dark-border bg-dark-surface/95 px-3 py-2"
          data-testid="discovery-map-legend"
        >
          <div className="mb-1 text-overline uppercase text-text-muted">
            {legendTitle}
          </div>
          {legend.map((item) => (
            <div key={item.i18nKey} className="flex items-center gap-2 text-micro text-text-secondary">
              <span
                className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              {t(`discovery.${item.i18nKey}`, item.label)}
            </div>
          ))}
        </div>
      )}

      {status === "ready" && (model.unlocatedCount > 0 || model.omittedByCapCount > 0) && (
        <div className="absolute bottom-8 left-3 z-10 max-w-[calc(100%-5rem)] space-y-1 rounded-lg border border-dark-border bg-dark-surface/95 px-3 py-2 text-micro text-text-secondary">
          <p>{t("discovery.mapPlotted", {
            count: model.returnedCount,
            plotted: mappable.length.toLocaleString(),
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
