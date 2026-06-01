import { useEffect } from "react";
import mapboxgl from "mapbox-gl";
import type { Layer } from "@deck.gl/core";
import type { MapData } from "../../lib/types";
import { crimeColor, srTypeMapColor, permitColor } from "../../lib/mapColors";
import { useMapboxOverlay } from "../../lib/useMapboxOverlay";
import { buildLayerTooltip } from "../../lib/mapTooltip";
import { pointLayer } from "../../lib/mapLayers";
import type { LandingSource } from "./DataSourceTabs";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;
const CHICAGO_CENTER: [number, number] = [-87.6298, 41.8781];

interface Props {
  mapData: MapData | null;
  source: LandingSource;
  loading: boolean;
}

export function LandingMap({ mapData, source, loading }: Props) {
  const { containerRef, mapRef, overlayRef, mapReady, contextRestored } = useMapboxOverlay({
    center: CHICAGO_CENTER,
    zoom: 12,
    getTooltip: buildLayerTooltip,
  });

  // Update layers when data or source changes
  useEffect(() => {
    if (!mapReady || !overlayRef.current || !mapData) return;

    const showCrime = source === "all" || source === "crime";
    const show311 = source === "all" || source === "311";
    const showPermits = source === "all" || source === "permits";

    const layers: Layer[] = [];

    if (showCrime && mapData.crimes.length > 0) {
      layers.push(pointLayer("crimes", mapData.crimes, {
        getFillColor: (d) => crimeColor(d.primary_type),
      }));
    }
    if (show311 && mapData.requests_311.length > 0) {
      layers.push(pointLayer("requests-311", mapData.requests_311, {
        getFillColor: (d) => srTypeMapColor(d.sr_type),
      }));
    }
    if (showPermits && mapData.building_permits.length > 0) {
      layers.push(pointLayer("permits", mapData.building_permits, {
        getFillColor: (d) => permitColor(d.permit_type),
        getRadius: 40,
        radiusMinPixels: 4,
        radiusMaxPixels: 10,
      }));
    }

    overlayRef.current.setProps({ layers });
  }, [mapReady, mapData, source, overlayRef, contextRestored]);

  // Fit bounds when data changes
  useEffect(() => {
    if (!mapReady || !mapRef.current || !mapData) return;

    const points: [number, number][] = [];
    for (const c of mapData.crimes) points.push([c.longitude, c.latitude]);
    for (const r of mapData.requests_311) points.push([r.longitude, r.latitude]);
    for (const p of mapData.building_permits) points.push([p.longitude, p.latitude]);

    if (points.length < 2) return;

    const lngs = points.map((p) => p[0]);
    const lats = points.map((p) => p[1]);
    const bounds = new mapboxgl.LngLatBounds(
      [Math.min(...lngs), Math.min(...lats)],
      [Math.max(...lngs), Math.max(...lats)],
    );

    mapRef.current.fitBounds(bounds, { padding: 40, duration: 1000 });
  }, [mapReady, mapData, mapRef]);

  if (!MAPBOX_TOKEN) {
    return (
      <div className="w-full h-full bg-dark-elevated rounded-xl flex items-center justify-center text-text-muted text-sm">
        Map unavailable
      </div>
    );
  }

  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden border border-dark-border">
      <div ref={containerRef} className="w-full h-full" />
      {loading && (
        <div className="absolute inset-0 bg-dark-bg/60 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
        </div>
      )}
    </div>
  );
}
