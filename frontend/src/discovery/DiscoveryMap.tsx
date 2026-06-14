// Discovery results map (PR6). Reuses Explore's deck.gl ScatterplotLayer + useMapboxOverlay.
// Renders the FULL ordered coord set from /search/pins (NOT the list window). Colors by
// upside_score with a distinct "no data" swatch (upsideColor). Bidirectional hover sync with
// the result list via shared hoveredPin. No tier gating here — PR9 owns the free/paid line.

import { useEffect, useMemo } from "react";
import { ScatterplotLayer } from "@deck.gl/layers";
import { useMapboxOverlay } from "../lib/useMapboxOverlay";
import { upsideColor, UPSIDE_LEGEND } from "./upsideColor";
import type { PinPoint } from "./types";

interface DiscoveryMapProps {
  points: PinPoint[];
  truncated: boolean;
  total: number;
  hoveredPin: string | null;
  onHoverPin: (pin: string | null) => void;
  onOpenParcel: (pin: string) => void;
}

const HIGHLIGHT: [number, number, number, number] = [238, 238, 238, 255];

export function DiscoveryMap({
  points,
  truncated,
  total,
  hoveredPin,
  onHoverPin,
  onOpenParcel,
}: DiscoveryMapProps) {
  const { containerRef, mapRef, overlayRef, mapReady } = useMapboxOverlay({
    center: [-87.6298, 41.8781],
    zoom: 10,
  });

  const mappable = useMemo(
    () => points.filter((p) => p.lat != null && p.lon != null),
    [points],
  );

  // Row → dot: highlight the hovered pin via deck.gl's highlightedObjectIndex (cheap; no
  // recolor of the whole layer).
  const highlightedIndex = useMemo(
    () => (hoveredPin ? mappable.findIndex((p) => p.pin === hoveredPin) : -1),
    [mappable, hoveredPin],
  );

  const layer = useMemo(() => {
    if (!mappable.length) return null;
    return new ScatterplotLayer({
      id: "discovery-pins",
      data: mappable,
      getPosition: (d: PinPoint) => [d.lon as number, d.lat as number],
      getFillColor: (d: PinPoint) => upsideColor(d.upside),
      getRadius: 8,
      radiusMinPixels: 2,
      radiusMaxPixels: 9,
      pickable: true,
      autoHighlight: true,
      highlightColor: HIGHLIGHT,
      highlightedObjectIndex: highlightedIndex,
      onHover: (info) => onHoverPin(info.object ? (info.object as PinPoint).pin : null),
      onClick: (info) => {
        if (info.object) onOpenParcel((info.object as PinPoint).pin);
      },
    });
  }, [mappable, highlightedIndex, onHoverPin, onOpenParcel]);

  useEffect(() => {
    if (!overlayRef.current) return;
    overlayRef.current.setProps({ layers: layer ? [layer] : [] });
  }, [layer, overlayRef]);

  // Fit to the mapped points' bounds when they change.
  useEffect(() => {
    if (!mapRef.current || !mapReady || mappable.length === 0) return;
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
  }, [mappable, mapReady, mapRef]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="absolute inset-0" />

      {/* Legend (includes the no-data swatch) */}
      {mappable.length > 0 && (
        <div className="absolute bottom-6 left-3 z-10 space-y-1 rounded-lg border border-dark-border bg-dark-surface/95 px-3 py-2">
          <div className="mb-1 text-[9px] uppercase tracking-wider text-text-muted">
            Redevelopment upside
          </div>
          {UPSIDE_LEGEND.map((item) => (
            <div key={item.label} className="flex items-center gap-2 text-[10px] text-text-secondary">
              <span
                className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              {item.label}
            </div>
          ))}
        </div>
      )}

      {/* Honest cap note: the map shows the first MAX_MAP_POINTS of a larger set. */}
      {truncated && (
        <div className="absolute left-3 top-3 z-10 rounded-lg border border-dark-border bg-dark-surface/90 px-3 py-1.5 text-[11px] text-text-secondary">
          Mapping {mappable.length.toLocaleString()} of {total.toLocaleString()} — refine to map
          the rest.
        </div>
      )}
    </div>
  );
}
