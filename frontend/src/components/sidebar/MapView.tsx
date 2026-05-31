import { useEffect, useRef, useState, useCallback } from "react";
import mapboxgl from "mapbox-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { ScatterplotLayer, GeoJsonLayer } from "@deck.gl/layers";
import type { MapData, MapCrime, MapRequest311, MapPermit, SourceTag } from "../../lib/types";
import {
  CRIME_TYPE_COLORS, crimeColor, deptColor, deriveFilterMode, isArrested, CRIME_TYPE_ORDER,
  PERMIT_TYPE_ORDER, normalizePermitType, permitColor,
  srTypeMapColor, srTypeMapColorCSS, permitColorCSS,
} from "../../lib/mapColors";
import type { FilterMode } from "../../lib/mapColors";
import { MapLayerToggles } from "./MapLayerToggles";
import { MapLegend } from "./MapLegend";
import { ArrestFilter } from "./ArrestFilter";
import type { ArrestFilterValue } from "./ArrestFilter";
import { DateRangeSlider } from "./DateRangeSlider";

type SelectedItem =
  | { type: "crime"; data: MapCrime }
  | { type: "311"; data: MapRequest311 }
  | { type: "permit"; data: MapPermit };

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;
const ENABLE_ZONING = import.meta.env.VITE_ENABLE_ZONING_LAYER === "true";

const CHICAGO_CENTER: [number, number] = [-87.6298, 41.8781];
const INITIAL_ZOOM = 11;

function buildCrimeTypeFilters(crimes: MapCrime[]): Record<string, boolean> {
  const counts = new Map<string, number>();
  for (const c of crimes) counts.set(c.primary_type, (counts.get(c.primary_type) ?? 0) + 1);
  const threshold = crimes.length * 0.01;
  const out: Record<string, boolean> = {};
  for (const t of CRIME_TYPE_ORDER) {
    if ((counts.get(t) ?? 0) >= threshold) out[t] = true;
  }
  const hasOther = [...counts.entries()].some(
    ([type, count]) => !CRIME_TYPE_ORDER.includes(type) || count < threshold
  );
  if (hasOther) out["OTHER"] = true;
  return out;
}

function buildSrTypeFilters(requests: MapRequest311[]): Record<string, boolean> {
  const counts = new Map<string, number>();
  for (const r of requests) {
    counts.set(r.sr_type, (counts.get(r.sr_type) ?? 0) + 1);
  }
  const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  const out: Record<string, boolean> = {};
  const top = sorted.slice(0, 8);
  for (const [type] of top) out[type] = true;
  if (sorted.length > 8) out["OTHER"] = true;
  return out;
}

function buildPermitTypeFilters(permits: MapPermit[]): Record<string, boolean> {
  const types = new Set(permits.map(p => normalizePermitType(p.permit_type)));
  const out: Record<string, boolean> = {};
  for (const t of PERMIT_TYPE_ORDER) {
    if (types.has(t)) out[t] = true;
  }
  const remaining = [...types].filter(t => !PERMIT_TYPE_ORDER.includes(t) && t !== "OTHER");
  if (remaining.length > 0) out["OTHER"] = true;
  return out;
}

function formatSrTypeLabel(type: string): string {
  return type.replace(/ Complaint$/i, "").replace(/ Request$/i, "");
}

function formatPermitLabel(type: string): string {
  return type.charAt(0) + type.slice(1).toLowerCase().replace(/_/g, " ");
}

function computeDateBounds(mapData: MapData, filterMode: FilterMode): { min: number; max: number } | null {
  const dates: number[] = [];
  const parse = (s: string) => { const t = new Date(s).getTime(); return isNaN(t) ? null : t; };

  if ((filterMode === "crime" || filterMode === "overview") && mapData.crimes.length) {
    for (const c of mapData.crimes) { const t = parse(c.date); if (t) dates.push(t); }
  }
  if ((filterMode === "311" || filterMode === "overview") && mapData.requests_311.length) {
    for (const r of mapData.requests_311) { const t = parse(r.created_date); if (t) dates.push(t); }
  }
  if ((filterMode === "permits" || filterMode === "overview") && mapData.building_permits.length) {
    for (const p of mapData.building_permits) { const t = parse(p.issue_date); if (t) dates.push(t); }
  }

  if (dates.length === 0) return null;
  return { min: Math.min(...dates), max: Math.max(...dates) };
}

function passesDateFilter(dateStr: string, range: [number, number] | null): boolean {
  if (!range) return true;
  const t = new Date(dateStr).getTime();
  return !isNaN(t) && t >= range[0] && t <= range[1];
}

interface Props {
  mapData: MapData | null;
  loading: boolean;
  sources: SourceTag[];
}

export function MapView({ mapData, loading, sources }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const [mapReady, setMapReady] = useState(false);

  const filterMode = deriveFilterMode(sources);

  const [overviewToggles, setOverviewToggles] = useState<Record<string, boolean>>({
    crimes: true, "requests-311": true, permits: true, zoning: false,
  });
  const [crimeTypeToggles, setCrimeTypeToggles] = useState<Record<string, boolean>>({});
  const [srTypeToggles, setSrTypeToggles] = useState<Record<string, boolean>>({});
  const [permitTypeToggles, setPermitTypeToggles] = useState<Record<string, boolean>>({});
  const [arrestFilter, setArrestFilter] = useState<ArrestFilterValue>("all");
  const [dateRange, setDateRange] = useState<[number, number] | null>(null);
  const [dateBounds, setDateBounds] = useState<{ min: number; max: number } | null>(null);
  const [selectedItem, setSelectedItem] = useState<SelectedItem | null>(null);
  const onClickRef = useRef<(info: { object?: unknown; layer: { id: string } | null }) => void>(() => {});

  // Reset sub-type filters when data changes
  useEffect(() => {
    if (filterMode === "crime" && mapData?.crimes?.length) {
      setCrimeTypeToggles(buildCrimeTypeFilters(mapData.crimes));
      setArrestFilter("all");
    }
    if (filterMode === "311" && mapData?.requests_311?.length) {
      setSrTypeToggles(buildSrTypeFilters(mapData.requests_311));
    }
    if (filterMode === "permits" && mapData?.building_permits?.length) {
      setPermitTypeToggles(buildPermitTypeFilters(mapData.building_permits));
    }
    if (mapData) {
      const bounds = computeDateBounds(mapData, filterMode);
      setDateBounds(bounds);
      setDateRange(bounds ? [bounds.min, bounds.max] : null);
    }
    setSelectedItem(null);
  }, [mapData, filterMode]);

  const toggleOverview = useCallback((id: string) => {
    setOverviewToggles(prev => ({ ...prev, [id]: !prev[id] }));
  }, []);
  const toggleCrimeType = useCallback((id: string) => {
    setCrimeTypeToggles(prev => ({ ...prev, [id]: !prev[id] }));
  }, []);
  const toggleSrType = useCallback((id: string) => {
    setSrTypeToggles(prev => ({ ...prev, [id]: !prev[id] }));
  }, []);
  const togglePermitType = useCallback((id: string) => {
    setPermitTypeToggles(prev => ({ ...prev, [id]: !prev[id] }));
  }, []);

  // Initialize map
  useEffect(() => {
    if (!containerRef.current || !MAPBOX_TOKEN) return;
    mapboxgl.accessToken = MAPBOX_TOKEN;

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center: CHICAGO_CENTER,
      zoom: INITIAL_ZOOM,
      attributionControl: false,
    });

    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "bottom-right");

    const overlay = new MapboxOverlay({
      interleaved: true,
      onClick: (info: { object?: unknown; layer: { id: string } | null }) => {
        onClickRef.current(info);
      },
      getTooltip: (info: { object?: unknown; layer: { id: string } | null }) => {
        if (!info.object) return null;
        const o = info.object as Record<string, unknown>;
        let html = "";
        const lid = info.layer?.id ?? "";
        if (lid === "crimes" || lid.startsWith("crime-")) {
          html = `<strong>${o.primary_type}</strong><br/>${formatDate(o.date as string)}`;
        } else if (lid === "requests-311" || lid.startsWith("dept-")) {
          html = `<strong>${o.sr_type}</strong><br/>${formatDate(o.created_date as string)}`;
        } else if (lid === "permits") {
          html = `<strong>${o.permit_type}</strong><br/>${formatDate(o.issue_date as string)}`;
        } else {
          return null;
        }
        return { html, style: { backgroundColor: "#333", color: "#eee", fontSize: "12px", borderRadius: "8px", padding: "8px 12px", fontFamily: "Inter, system-ui, sans-serif", maxWidth: "240px" } };
      },
    });
    map.addControl(overlay);

    mapRef.current = map;
    overlayRef.current = overlay;
    map.on("load", () => setMapReady(true));

    return () => {
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
      setMapReady(false);
    };
  }, []);

  // Click handler - uses ref to avoid stale closure
  onClickRef.current = (info) => {
    if (!info.object || !info.layer) {
      setSelectedItem(null);
      return;
    }
    const lid = info.layer.id;
    const o = info.object as Record<string, unknown>;
    if (lid === "crimes") {
      setSelectedItem({ type: "crime", data: o as unknown as MapCrime });
    } else if (lid === "requests-311") {
      setSelectedItem({ type: "311", data: o as unknown as MapRequest311 });
    } else if (lid === "permits") {
      setSelectedItem({ type: "permit", data: o as unknown as MapPermit });
    }
  };

  // Resize observer
  useEffect(() => {
    if (!containerRef.current || !mapRef.current) return;
    const observer = new ResizeObserver(() => { mapRef.current?.resize(); });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [mapReady]);

  // Update layers
  useEffect(() => {
    if (!overlayRef.current || !mapReady) return;

    const layers: (ScatterplotLayer | GeoJsonLayer)[] = [];

    if (filterMode === "crime" && mapData?.crimes?.length) {
      const activeTypes = new Set(
        Object.entries(crimeTypeToggles).filter(([, v]) => v).map(([k]) => k)
      );
      const otherActive = activeTypes.has("OTHER");

      const namedTypes = new Set(Object.keys(crimeTypeToggles).filter(k => k !== "OTHER"));
      const filteredCrimes = mapData.crimes.filter(c => {
        const typeMatch = activeTypes.has(c.primary_type) ||
          (otherActive && !namedTypes.has(c.primary_type));
        if (!typeMatch) return false;
        if (arrestFilter === "arrested" && !isArrested(c.arrest)) return false;
        if (arrestFilter === "not-arrested" && isArrested(c.arrest)) return false;
        if (!passesDateFilter(c.date, dateRange)) return false;
        return true;
      });

      if (filteredCrimes.length > 0) {
        layers.push(
          new ScatterplotLayer<MapCrime>({
            id: "crimes",
            data: filteredCrimes,
            getPosition: d => [d.longitude, d.latitude],
            getRadius: 40,
            getFillColor: d => crimeColor(d.primary_type),
            pickable: true,
            radiusMinPixels: 3,
            radiusMaxPixels: 8,
            radiusUnits: "meters",
          })
        );
      }
    } else if (filterMode === "311" && mapData?.requests_311?.length) {
      const activeTypes = new Set(
        Object.entries(srTypeToggles).filter(([, v]) => v).map(([k]) => k)
      );
      const otherActive = activeTypes.has("OTHER");
      const topTypes = new Set(Object.keys(srTypeToggles).filter(k => k !== "OTHER"));

      const filtered = mapData.requests_311.filter(r => {
        const typeMatch = activeTypes.has(r.sr_type) ||
          (otherActive && !topTypes.has(r.sr_type));
        if (!typeMatch) return false;
        if (!passesDateFilter(r.created_date, dateRange)) return false;
        return true;
      });

      if (filtered.length > 0) {
        layers.push(
          new ScatterplotLayer<MapRequest311>({
            id: "requests-311",
            data: filtered,
            getPosition: d => [d.longitude, d.latitude],
            getRadius: 35,
            getFillColor: d => srTypeMapColor(d.sr_type),
            pickable: true,
            radiusMinPixels: 3,
            radiusMaxPixels: 7,
            radiusUnits: "meters",
          })
        );
      }
    } else if (filterMode === "permits" && mapData?.building_permits?.length) {
      const activeTypes = new Set(
        Object.entries(permitTypeToggles).filter(([, v]) => v).map(([k]) => k)
      );
      const otherActive = activeTypes.has("OTHER");

      const filteredPermits = mapData.building_permits.filter(p => {
        const normalized = normalizePermitType(p.permit_type);
        const typeMatch = activeTypes.has(normalized) ||
          (otherActive && !PERMIT_TYPE_ORDER.includes(normalized));
        if (!typeMatch) return false;
        if (!passesDateFilter(p.issue_date, dateRange)) return false;
        return true;
      });

      if (filteredPermits.length > 0) {
        layers.push(
          new ScatterplotLayer<MapPermit>({
            id: "permits",
            data: filteredPermits,
            getPosition: d => [d.longitude, d.latitude],
            getRadius: d => Math.max(40, Math.min(150, Math.sqrt(d.estimated_cost || 0) * 0.3)),
            getFillColor: d => permitColor(d.permit_type),
            pickable: true,
            radiusMinPixels: 3,
            radiusMaxPixels: 12,
            radiusUnits: "meters",
          })
        );
      }
    } else {
      // Overview mode: source-level toggles + date filter
      if (overviewToggles.crimes && mapData?.crimes?.length) {
        const filtered = mapData.crimes.filter(c => passesDateFilter(c.date, dateRange));
        if (filtered.length > 0) {
          layers.push(
            new ScatterplotLayer<MapCrime>({
              id: "crimes",
              data: filtered,
              getPosition: d => [d.longitude, d.latitude],
              getRadius: 40,
              getFillColor: d => crimeColor(d.primary_type),
              pickable: true,
              radiusMinPixels: 3,
              radiusMaxPixels: 8,
              radiusUnits: "meters",
            })
          );
        }
      }
      if (overviewToggles["requests-311"] && mapData?.requests_311?.length) {
        const filtered = mapData.requests_311.filter(r => passesDateFilter(r.created_date, dateRange));
        if (filtered.length > 0) {
          layers.push(
            new ScatterplotLayer<MapRequest311>({
              id: "requests-311",
              data: filtered,
              getPosition: d => [d.longitude, d.latitude],
              getRadius: 35,
              getFillColor: d => deptColor(d.owner_department),
              pickable: true,
              radiusMinPixels: 3,
              radiusMaxPixels: 7,
              radiusUnits: "meters",
            })
          );
        }
      }
      if (overviewToggles.permits && mapData?.building_permits?.length) {
        const filtered = mapData.building_permits.filter(p => passesDateFilter(p.issue_date, dateRange));
        if (filtered.length > 0) {
          layers.push(
            new ScatterplotLayer<MapPermit>({
              id: "permits",
              data: filtered,
              getPosition: d => [d.longitude, d.latitude],
              getRadius: d => Math.max(40, Math.min(150, Math.sqrt(d.estimated_cost || 0) * 0.3)),
              getFillColor: [99, 153, 34, 180],
              pickable: true,
              radiusMinPixels: 3,
              radiusMaxPixels: 12,
              radiusUnits: "meters",
            })
          );
        }
      }
    }

    if (ENABLE_ZONING && overviewToggles.zoning && mapData?.zoning) {
      layers.push(
        new GeoJsonLayer({
          id: "zoning",
          data: mapData.zoning as unknown as GeoJSON.FeatureCollection,
          getFillColor: [201, 100, 66, 40],
          getLineColor: [201, 100, 66, 120],
          lineWidthMinPixels: 1,
          pickable: false,
        })
      );
    }

    if (mapData?.queried_address) {
      layers.push(
        new ScatterplotLayer({
          id: "address-pin",
          data: [mapData.queried_address],
          getPosition: (d: { longitude: number; latitude: number }) => [d.longitude, d.latitude],
          getRadius: 60,
          getFillColor: [55, 138, 221, 220],
          getLineColor: [255, 255, 255, 255],
          stroked: true,
          lineWidthMinPixels: 2,
          radiusMinPixels: 6,
          radiusUnits: "meters",
        })
      );
    }

    overlayRef.current.setProps({ layers });
  }, [mapData, filterMode, overviewToggles, crimeTypeToggles, srTypeToggles, permitTypeToggles, arrestFilter, dateRange, mapReady]);

  // Fly to address
  useEffect(() => {
    if (!mapRef.current || !mapReady || !mapData?.queried_address) return;
    const { longitude, latitude } = mapData.queried_address;
    mapRef.current.flyTo({ center: [longitude, latitude], zoom: 14, duration: 1500 });
  }, [mapData?.queried_address, mapReady]);

  if (!MAPBOX_TOKEN) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted text-sm p-4 text-center">
        Set <code className="text-text-secondary mx-1">VITE_MAPBOX_TOKEN</code> in your environment to enable the map.
      </div>
    );
  }

  // Build dynamic toggle configs
  let toggleConfigs: { id: string; label: string; color: string; active: boolean }[] = [];
  let activeToggles: Record<string, boolean> = {};
  let onToggle: (id: string) => void = toggleOverview;

  if (filterMode === "crime") {
    toggleConfigs = Object.keys(crimeTypeToggles).map(type => {
      const color = type === "OTHER"
        ? "rgb(136,135,128)"
        : `rgba(${(CRIME_TYPE_COLORS[type] ?? [136, 135, 128, 180]).slice(0, 3).join(",")})`;
      return {
        id: type,
        label: type.charAt(0) + type.slice(1).toLowerCase().replace(/_/g, " "),
        color,
        active: crimeTypeToggles[type],
      };
    });
    activeToggles = crimeTypeToggles;
    onToggle = toggleCrimeType;
  } else if (filterMode === "311") {
    toggleConfigs = Object.keys(srTypeToggles).map(type => ({
      id: type,
      label: type === "OTHER" ? "Other" : formatSrTypeLabel(type),
      color: type === "OTHER" ? "rgb(158,158,158)" : srTypeMapColorCSS(type),
      active: srTypeToggles[type],
    }));
    activeToggles = srTypeToggles;
    onToggle = toggleSrType;
  } else if (filterMode === "permits") {
    toggleConfigs = Object.keys(permitTypeToggles).map(type => ({
      id: type,
      label: type === "OTHER" ? "Other" : formatPermitLabel(type),
      color: type === "OTHER" ? "rgb(136,135,128)" : (permitColorCSS(type)),
      active: permitTypeToggles[type],
    }));
    activeToggles = permitTypeToggles;
    onToggle = togglePermitType;
  } else {
    toggleConfigs = [
      { id: "crimes", label: "Crime", color: "rgb(226,75,74)", active: overviewToggles.crimes },
      { id: "requests-311", label: "311", color: "rgb(0,188,212)", active: overviewToggles["requests-311"] },
      { id: "permits", label: "Permits", color: "rgb(99,153,34)", active: overviewToggles.permits },
      ...(ENABLE_ZONING
        ? [{ id: "zoning", label: "Zoning", color: "rgb(201,100,66)", active: overviewToggles.zoning }]
        : []),
    ];
    activeToggles = overviewToggles;
    onToggle = toggleOverview;
  }

  const hasData = mapData && (mapData.crimes.length > 0 || mapData.requests_311.length > 0 || mapData.building_permits.length > 0);

  const arrestCount = mapData?.crimes?.filter(c => isArrested(c.arrest)).length ?? 0;
  const crimeTotal = mapData?.crimes?.length ?? 0;

  const capped = mapData?.capped ?? {};
  const isCapped = Object.values(capped).some(Boolean);
  const cappedCount = (capped.crimes ? mapData!.crimes.length : 0)
    + (capped.requests_311 ? mapData!.requests_311.length : 0)
    + (capped.building_permits ? mapData!.building_permits.length : 0)
    || (mapData ? mapData.crimes.length + mapData.requests_311.length + mapData.building_permits.length : 0);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />

      {mapReady && (
        <div className="absolute top-2 right-2 z-10 flex flex-col gap-1 items-end w-1/2 max-w-[200px] max-h-[calc(100%-16px)] overflow-y-auto">
          {dateBounds && dateRange && hasData && (
            <DateRangeSlider
              minDate={dateBounds.min}
              maxDate={dateBounds.max}
              startDate={dateRange[0]}
              endDate={dateRange[1]}
              onChange={(s, e) => setDateRange([s, e])}
            />
          )}
          {toggleConfigs.length > 0 && (
            <MapLayerToggles layers={toggleConfigs} onToggle={onToggle} />
          )}
        </div>
      )}

      {mapReady && toggleConfigs.length > 0 && (
        <MapLegend activeLayers={activeToggles} filterMode={filterMode} />
      )}

      {mapReady && filterMode === "crime" && crimeTotal > 0 && (
        <ArrestFilter
          value={arrestFilter}
          onChange={setArrestFilter}
          arrestCount={arrestCount}
          totalCount={crimeTotal}
        />
      )}

      {loading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-dark-bg/60 backdrop-blur-sm">
          <div className="text-text-muted text-sm animate-pulse">Loading map data...</div>
        </div>
      )}

      {!loading && !hasData && mapReady && (
        <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
          <span className="text-text-muted text-xs bg-dark-surface/80 backdrop-blur-sm px-3 py-1.5 rounded-lg">
            Ask a question to see data on the map
          </span>
        </div>
      )}

      {!loading && mapReady && isCapped && (
        <div className="absolute bottom-2 right-2 z-10">
          <span className="text-[10px] text-amber-400/80 bg-dark-surface/90 backdrop-blur-sm
                           border border-amber-500/20 rounded-md px-2 py-1">
            Showing most recent {cappedCount.toLocaleString()} results
          </span>
        </div>
      )}

      {selectedItem && (
        <div
          className="absolute inset-0 z-30 flex items-center justify-center bg-black/30"
          onClick={() => setSelectedItem(null)}
        >
          <div
            className="bg-dark-surface border border-dark-border rounded-xl p-4 max-w-[280px] w-[90%] shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-text-primary">
                {selectedItem.type === "crime" ? "Crime Incident" :
                 selectedItem.type === "311" ? "311 Request" : "Building Permit"}
              </h3>
              <button
                onClick={() => setSelectedItem(null)}
                className="text-text-muted hover:text-text-primary transition-colors p-0.5"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-2 text-xs">
              {renderDetailFields(selectedItem)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value, href }: { label: string; value: string; href?: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-text-muted shrink-0">{label}</span>
      {href ? (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 hover:text-blue-300 text-right transition-colors"
        >
          {value} ↗
        </a>
      ) : (
        <span className="text-text-primary text-right">{value}</span>
      )}
    </div>
  );
}

function streetViewUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}`;
}

function renderDetailFields(item: SelectedItem) {
  if (item.type === "crime") {
    const d = item.data;
    return (
      <>
        <DetailRow label="Type" value={d.primary_type} />
        <DetailRow label="Description" value={d.description} />
        <DetailRow label="Date" value={formatDate(d.date)} />
        <DetailRow label="Arrest" value={isArrested(d.arrest) ? "Yes" : "No"} />
        <DetailRow label="Location" value={`${d.latitude.toFixed(4)}, ${d.longitude.toFixed(4)}`}
          href={streetViewUrl(d.latitude, d.longitude)} />
      </>
    );
  }
  if (item.type === "311") {
    const d = item.data;
    return (
      <>
        <DetailRow label="Type" value={d.sr_type} />
        <DetailRow label="Status" value={d.status} />
        <DetailRow label="Department" value={d.owner_department} />
        <DetailRow label="Date" value={formatDate(d.created_date)} />
        <DetailRow label="Location" value={`${d.latitude.toFixed(4)}, ${d.longitude.toFixed(4)}`}
          href={streetViewUrl(d.latitude, d.longitude)} />
      </>
    );
  }
  const d = item.data;
  return (
    <>
      <DetailRow label="Type" value={d.permit_type} />
      <DetailRow label="Work" value={d.work_description || "N/A"} />
      <DetailRow label="Est. Cost" value={`$${Number(d.estimated_cost).toLocaleString()}`} />
      <DetailRow label="Issue Date" value={formatDate(d.issue_date)} />
      <DetailRow label="Location" value={`${d.latitude.toFixed(4)}, ${d.longitude.toFixed(4)}`}
        href={streetViewUrl(d.latitude, d.longitude)} />
    </>
  );
}

function formatDate(iso: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return iso;
  }
}
