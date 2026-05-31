import { useEffect, useRef, useState, useCallback } from "react";
import mapboxgl from "mapbox-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { ScatterplotLayer, GeoJsonLayer } from "@deck.gl/layers";
import type { MapData, MapCrime, MapRequest311, MapPermit, SourceTag } from "../../lib/types";
import { CRIME_TYPE_COLORS, crimeColor, deptColor, normalizeDept, deriveFilterMode, isArrested, CRIME_TYPE_ORDER } from "../../lib/mapColors";
import type { FilterMode } from "../../lib/mapColors";
import { MapLayerToggles } from "./MapLayerToggles";
import { MapLegend } from "./MapLegend";
import { ArrestFilter } from "./ArrestFilter";
import type { ArrestFilterValue } from "./ArrestFilter";
import { DateRangeSlider } from "./DateRangeSlider";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;
const ENABLE_ZONING = import.meta.env.VITE_ENABLE_ZONING_LAYER === "true";

const CHICAGO_CENTER: [number, number] = [-87.6298, 41.8781];
const INITIAL_ZOOM = 11;

function buildCrimeTypeFilters(crimes: MapCrime[]): Record<string, boolean> {
  const types = new Set(crimes.map(c => c.primary_type));
  const out: Record<string, boolean> = {};
  for (const t of CRIME_TYPE_ORDER) {
    if (types.has(t)) out[t] = true;
  }
  const remaining = [...types].filter(t => !CRIME_TYPE_ORDER.includes(t));
  if (remaining.length > 0) out["OTHER"] = true;
  return out;
}

function buildDeptFilters(requests: MapRequest311[]): Record<string, boolean> {
  const depts = new Set(requests.map(r => normalizeDept(r.owner_department)));
  const ordered = ["Streets & Sanitation", "Buildings", "CDOT"];
  const out: Record<string, boolean> = {};
  for (const d of ordered) {
    if (depts.has(d)) out[d] = true;
  }
  if ([...depts].some(d => !ordered.includes(d))) out["Other"] = true;
  return out;
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
  const [deptToggles, setDeptToggles] = useState<Record<string, boolean>>({});
  const [arrestFilter, setArrestFilter] = useState<ArrestFilterValue>("all");
  const [dateRange, setDateRange] = useState<[number, number] | null>(null);
  const [dateBounds, setDateBounds] = useState<{ min: number; max: number } | null>(null);

  // Reset sub-type filters when data changes
  useEffect(() => {
    if (filterMode === "crime" && mapData?.crimes?.length) {
      setCrimeTypeToggles(buildCrimeTypeFilters(mapData.crimes));
      setArrestFilter("all");
    }
    if (filterMode === "311" && mapData?.requests_311?.length) {
      setDeptToggles(buildDeptFilters(mapData.requests_311));
    }
    if (mapData) {
      const bounds = computeDateBounds(mapData, filterMode);
      setDateBounds(bounds);
      setDateRange(bounds ? [bounds.min, bounds.max] : null);
    }
  }, [mapData, filterMode]);

  const toggleOverview = useCallback((id: string) => {
    setOverviewToggles(prev => ({ ...prev, [id]: !prev[id] }));
  }, []);
  const toggleCrimeType = useCallback((id: string) => {
    setCrimeTypeToggles(prev => ({ ...prev, [id]: !prev[id] }));
  }, []);
  const toggleDept = useCallback((id: string) => {
    setDeptToggles(prev => ({ ...prev, [id]: !prev[id] }));
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
      getTooltip: (info: { object?: unknown; layer: { id: string } | null }) => {
        if (!info.object) return null;
        const o = info.object as Record<string, unknown>;
        let html = "";
        const lid = info.layer?.id ?? "";
        if (lid === "crimes" || lid.startsWith("crime-")) {
          html = `<strong>${o.primary_type}</strong><br/>${o.description}<br/>${formatDate(o.date as string)}<br/>Arrest: ${o.arrest === true || o.arrest === "true" ? "Yes" : "No"}`;
        } else if (lid === "requests-311" || lid.startsWith("dept-")) {
          html = `<strong>${o.sr_type}</strong><br/>Status: ${o.status}<br/>Dept: ${o.owner_department}<br/>${formatDate(o.created_date as string)}`;
        } else if (lid === "permits") {
          html = `<strong>${o.permit_type}</strong><br/>${o.work_description}<br/>Cost: $${Number(o.estimated_cost).toLocaleString()}<br/>${formatDate(o.issue_date as string)}`;
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

      const filteredCrimes = mapData.crimes.filter(c => {
        const typeMatch = activeTypes.has(c.primary_type) ||
          (otherActive && !Object.keys(CRIME_TYPE_COLORS).includes(c.primary_type));
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
      const activeDepts = new Set(
        Object.entries(deptToggles).filter(([, v]) => v).map(([k]) => k)
      );
      const otherActive = activeDepts.has("Other");

      const filtered = mapData.requests_311.filter(r => {
        const normalized = normalizeDept(r.owner_department);
        const deptMatch = activeDepts.has(normalized) ||
          (otherActive && !["Streets & Sanitation", "Buildings", "CDOT"].includes(normalized));
        if (!deptMatch) return false;
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
            getFillColor: d => deptColor(d.owner_department),
            pickable: true,
            radiusMinPixels: 3,
            radiusMaxPixels: 7,
            radiusUnits: "meters",
          })
        );
      }
    } else if (filterMode === "permits" && mapData?.building_permits?.length) {
      const filteredPermits = mapData.building_permits.filter(p =>
        passesDateFilter(p.issue_date, dateRange)
      );
      if (filteredPermits.length > 0) {
        layers.push(
          new ScatterplotLayer<MapPermit>({
            id: "permits",
            data: filteredPermits,
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
  }, [mapData, filterMode, overviewToggles, crimeTypeToggles, deptToggles, arrestFilter, dateRange, mapReady]);

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
    const deptColorMap: Record<string, string> = {
      "Streets & Sanitation": "rgb(0,188,212)",
      Buildings: "rgb(255,112,67)",
      CDOT: "rgb(66,165,245)",
      Other: "rgb(158,158,158)",
    };
    toggleConfigs = Object.keys(deptToggles).map(dept => ({
      id: dept,
      label: dept,
      color: deptColorMap[dept] ?? "rgb(158,158,158)",
      active: deptToggles[dept],
    }));
    activeToggles = deptToggles;
    onToggle = toggleDept;
  } else if (filterMode === "permits") {
    // Permits mode: no sub-type filters, just show all
    toggleConfigs = [];
    activeToggles = {};
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
        <div className="absolute top-2 right-2 z-10 flex flex-col gap-1 items-end w-1/2 max-w-[200px]">
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
    </div>
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
