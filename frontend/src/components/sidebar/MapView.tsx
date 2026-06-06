import { useEffect, useState, useCallback, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ScatterplotLayer, GeoJsonLayer } from "@deck.gl/layers";
import { PathStyleExtension } from "@deck.gl/extensions";
import type { MapData, MapCrime, MapRequest311, MapPermit, SourceTag, TransitStation } from "../../lib/types";
import { fetchTransitStations } from "../../lib/api";
import {
  CRIME_TYPE_COLORS, crimeColor, deriveFilterMode, isArrested, CRIME_TYPE_ORDER,
  PERMIT_TYPE_ORDER, normalizePermitType, permitColor,
  srTypeMapColor, srTypeMapColorCSS, permitColorCSS, capLabel,
  zoneColor, zoneLineColor, zonePrefix, ZONE_INFO,
  overlayColor, overlayLineColor, overlayColorCSS, overlayLabel, incentiveLabel, OVERLAY_INFO,
  incentiveZoneColor, incentiveZoneLineColor, incentiveZoneColorCSS,
} from "../../lib/mapColors";
import type { FilterMode } from "../../lib/mapColors";
import { useMapboxOverlay } from "../../lib/useMapboxOverlay";
import { buildLayerTooltip, type LayerPickInfo } from "../../lib/mapTooltip";
import { pointLayer } from "../../lib/mapLayers";
import { formatDate } from "../../lib/format";
import { MapLayerToggles } from "./MapLayerToggles";
import { MapLegend } from "./MapLegend";
import { ToggleGroup } from "./ToggleGroup";
import type { ArrestFilterValue } from "./ArrestFilter";
import type { StatusFilterValue } from "./StatusFilter";
import { costBucket } from "./CostFilter";
import type { CostFilterValue } from "./CostFilter";
import { DateRangeSlider } from "./DateRangeSlider";

interface ZoningClickData {
  zone_class: string;
  zone_type: number | null;
  ordinance_num: string | null;
}

interface OverlayClickData {
  overlay_type: string;
  overlay_name: string;
  feature_name: string | null;
  ordinance: string | null;
}

interface IncentiveClickData {
  zone_type: string;
  name: string;
}

type SelectedItem =
  | { type: "crime"; data: MapCrime }
  | { type: "311"; data: MapRequest311 }
  | { type: "permit"; data: MapPermit }
  | { type: "zoning"; data: ZoningClickData }
  | { type: "regulatory"; zones: {
      zoning: ZoningClickData | null;
      overlays: OverlayClickData[];
      incentives: IncentiveClickData[];
    }};

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;

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
  parcelGeometry?: Record<string, unknown> | null;
  hasTransitContext?: boolean;
  isMobile?: boolean;
}

export function MapView({ mapData, loading, sources, parcelGeometry, hasTransitContext, isMobile = false }: Props) {
  const rawFilterMode = deriveFilterMode(sources);

  type SourceTab = "crime" | "311" | "permits";
  const availableTabs: SourceTab[] = [];
  if (mapData?.crimes?.length) availableTabs.push("crime");
  if (mapData?.requests_311?.length) availableTabs.push("311");
  if (mapData?.building_permits?.length) availableTabs.push("permits");

  const [activeTab, setActiveTab] = useState<SourceTab | null>(null);
  const isMultiSource = rawFilterMode === "overview";
  const filterMode: FilterMode = isMultiSource
    ? (activeTab && availableTabs.includes(activeTab) ? activeTab : availableTabs[0] ?? "crime")
    : rawFilterMode;

  useEffect(() => {
    if (isMultiSource && availableTabs.length > 0) {
      if (!activeTab || !availableTabs.includes(activeTab)) {
        setActiveTab(availableTabs[0]);
      }
    }
  }, [mapData, isMultiSource]);

  const [crimeTypeToggles, setCrimeTypeToggles] = useState<Record<string, boolean>>({});
  const [srTypeToggles, setSrTypeToggles] = useState<Record<string, boolean>>({});
  const [permitTypeToggles, setPermitTypeToggles] = useState<Record<string, boolean>>({});
  const [arrestFilter, setArrestFilter] = useState<ArrestFilterValue>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>("all");
  const [costFilter, setCostFilter] = useState<CostFilterValue>("all");
  const [dateRange, setDateRange] = useState<[number, number] | null>(null);
  const [dateBounds, setDateBounds] = useState<{ min: number; max: number } | null>(null);
  const [selectedItem, setSelectedItem] = useState<SelectedItem | null>(null);
  const [showZoning, setShowZoning] = useState(true);
  const [showPoints, setShowPoints] = useState(true);
  const [showTransit, setShowTransit] = useState(false);
  const [showIncentives, setShowIncentives] = useState(true);
  const [showOverlays, setShowOverlays] = useState(true);
  const [transitStations, setTransitStations] = useState<TransitStation[]>([]);
  const [filterPopoverOpen, setFilterPopoverOpen] = useState(false);

  const hasZoning = !!(mapData?.zoning && (mapData.zoning as Record<string, unknown>)?.features &&
    ((mapData.zoning as Record<string, unknown>).features as unknown[]).length > 0);
  const hasIncentiveZones = !!(mapData?.incentive_zones &&
    (mapData.incentive_zones as Record<string, unknown>).features &&
    ((mapData.incentive_zones as Record<string, unknown>).features as unknown[]).length > 0);
  const hasOverlayDistricts = !!(mapData?.overlay_districts &&
    (mapData.overlay_districts as Record<string, unknown>).features &&
    ((mapData.overlay_districts as Record<string, unknown>).features as unknown[]).length > 0);

  // Reset sub-type filters when data changes
  useEffect(() => {
    if (mapData?.crimes?.length) {
      setCrimeTypeToggles(buildCrimeTypeFilters(mapData.crimes));
      setArrestFilter("all");
    }
    if (mapData?.requests_311?.length) {
      setSrTypeToggles(buildSrTypeFilters(mapData.requests_311));
      setStatusFilter("all");
    }
    if (mapData?.building_permits?.length) {
      setPermitTypeToggles(buildPermitTypeFilters(mapData.building_permits));
      setCostFilter("all");
    }
    setSelectedItem(null);
  }, [mapData]);

  // Recompute date bounds when active tab or data changes
  useEffect(() => {
    if (mapData) {
      const bounds = computeDateBounds(mapData, filterMode);
      setDateBounds(bounds);
      setDateRange(bounds ? [bounds.min, bounds.max] : null);
    }
  }, [mapData, filterMode]);

  useEffect(() => {
    if (hasTransitContext) {
      setShowTransit(true);
    }
  }, [hasTransitContext]);

  useEffect(() => {
    if (showTransit && transitStations.length === 0) {
      fetchTransitStations().then(setTransitStations);
    }
  }, [showTransit]);

  const soloToggle = useCallback(
    (prev: Record<string, boolean>, id: string): Record<string, boolean> => {
      const keys = Object.keys(prev);
      const allActive = keys.every(k => prev[k]);
      const activeKeys = keys.filter(k => prev[k]);
      const isOnlySolo = activeKeys.length === 1 && activeKeys[0] === id;

      if (isOnlySolo) {
        return Object.fromEntries(keys.map(k => [k, true]));
      }
      if (allActive || !prev[id]) {
        return Object.fromEntries(keys.map(k => [k, k === id]));
      }
      return Object.fromEntries(keys.map(k => [k, k === id]));
    },
    [],
  );

  const toggleCrimeType = useCallback((id: string) => {
    setCrimeTypeToggles(prev => soloToggle(prev, id));
  }, [soloToggle]);
  const toggleSrType = useCallback((id: string) => {
    setSrTypeToggles(prev => soloToggle(prev, id));
  }, [soloToggle]);
  const togglePermitType = useCallback((id: string) => {
    setPermitTypeToggles(prev => soloToggle(prev, id));
  }, [soloToggle]);

  // Initialize Mapbox + deck.gl overlay (shared lifecycle hook).
  // Declared before handleMapClick so overlayRef is available for multi-pick.
  // The hook reads onClick through a ref, so late-binding is safe.
  const onClickRef = useRef<(info: LayerPickInfo) => void>(() => {});
  const { containerRef, mapRef, overlayRef, mapReady, contextRestored } = useMapboxOverlay({
    center: CHICAGO_CENTER,
    zoom: INITIAL_ZOOM,
    getTooltip: buildLayerTooltip,
    onClick: (info: LayerPickInfo) => onClickRef.current(info),
  });

  // Map click → open the detail modal for the picked feature.
  // For zone layers, multi-pick to find ALL overlapping features at the click point.
  const handleMapClick = useCallback((info: LayerPickInfo) => {
    if (!info.object || !info.layer) {
      setSelectedItem(null);
      return;
    }
    const lid = info.layer.id;
    const o = info.object as Record<string, unknown>;

    if (lid === "crimes") {
      setSelectedItem({ type: "crime", data: o as unknown as MapCrime });
      return;
    }
    if (lid === "requests-311") {
      setSelectedItem({ type: "311", data: o as unknown as MapRequest311 });
      return;
    }
    if (lid === "permits") {
      setSelectedItem({ type: "permit", data: o as unknown as MapPermit });
      return;
    }

    if (lid === "zoning" || lid === "overlay-districts" || lid === "incentive-zones") {
      const allPicks = overlayRef.current?.pickMultipleObjects({
        x: info.x,
        y: info.y,
        layerIds: ["zoning", "overlay-districts", "incentive-zones"],
        depth: 20,
      }) ?? [];

      let zoningData: ZoningClickData | null = null;
      const overlays: OverlayClickData[] = [];
      const incentives: IncentiveClickData[] = [];

      for (const pick of allPicks) {
        if (!pick.object || !pick.layer) continue;
        const pickObj = pick.object as Record<string, unknown>;
        const pickProps = (pickObj.properties as Record<string, unknown>) ?? {};
        const pickLayerId = pick.layer.id;

        if (pickLayerId === "zoning" && !zoningData) {
          zoningData = {
            zone_class: (pickProps.ZONE_CLASS as string) ?? "Unknown",
            zone_type: (pickProps.ZONE_TYPE as number) ?? null,
            ordinance_num: (pickProps.ORDINANCE_NUM as string) ?? null,
          };
        } else if (pickLayerId === "overlay-districts") {
          const ot = (pickProps.overlay_type as string) ?? "";
          if (!overlays.some(ov => ov.overlay_type === ot)) {
            overlays.push({
              overlay_type: ot,
              overlay_name: (pickProps.overlay_name as string) ?? "",
              feature_name: (pickProps.NAME ?? pickProps.DIST_NAME ?? pickProps.PD_NAME ?? null) as string | null,
              ordinance: (pickProps.ORDINANCE ?? pickProps.ORD_NO ?? null) as string | null,
            });
          }
        } else if (pickLayerId === "incentive-zones") {
          const zt = (pickProps.zone_type as string) ?? "";
          if (!incentives.some(inc => inc.zone_type === zt)) {
            incentives.push({
              zone_type: zt,
              name: (pickProps.name as string) ?? "",
            });
          }
        }
      }

      if (overlays.length > 0 || incentives.length > 0) {
        setSelectedItem({ type: "regulatory", zones: { zoning: zoningData, overlays, incentives } });
      } else if (zoningData) {
        setSelectedItem({ type: "zoning", data: zoningData });
      } else {
        setSelectedItem(null);
      }
      return;
    }

    setSelectedItem(null);
  }, [overlayRef]);

  onClickRef.current = handleMapClick;

  // Resize observer
  useEffect(() => {
    if (!containerRef.current || !mapRef.current) return;
    const observer = new ResizeObserver(() => { mapRef.current?.resize(); });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [mapReady, containerRef, mapRef]);

  // Update layers
  useEffect(() => {
    if (!overlayRef.current || !mapReady) return;

    const layers: (ScatterplotLayer | GeoJsonLayer)[] = [];

    // Zoning polygons render first (underneath scatter dots)
    if (showZoning && hasZoning) {
      layers.push(
        new GeoJsonLayer({
          id: "zoning",
          data: mapData!.zoning as unknown as GeoJSON.FeatureCollection,
          getFillColor: (f: unknown) => {
            const props = (f as Record<string, unknown>).properties as Record<string, unknown> | undefined;
            return zoneColor((props?.ZONE_CLASS as string) ?? "");
          },
          getLineColor: (f: unknown) => {
            const props = (f as Record<string, unknown>).properties as Record<string, unknown> | undefined;
            return zoneLineColor((props?.ZONE_CLASS as string) ?? "");
          },
          lineWidthMinPixels: 1,
          pickable: true,
        })
      );
    }

    if (parcelGeometry) {
      const feature = {
        type: "Feature" as const,
        geometry: parcelGeometry,
        properties: {},
      };
      layers.push(
        new GeoJsonLayer({
          id: "parcel-boundary",
          data: { type: "FeatureCollection", features: [feature] } as unknown as GeoJSON.FeatureCollection,
          getFillColor: [201, 100, 66, 35],
          getLineColor: [201, 100, 66, 220],
          lineWidthMinPixels: 2,
          pickable: false,
        })
      );
    }

    // Incentive zone boundary polygons (dashed outlines)
    if (showIncentives && hasIncentiveZones) {
      layers.push(
        new GeoJsonLayer({
          id: "incentive-zones",
          data: mapData!.incentive_zones as unknown as GeoJSON.FeatureCollection,
          getFillColor: (f: unknown) => {
            const props = (f as Record<string, unknown>).properties as Record<string, unknown> | undefined;
            const name = (props?.name as string) ?? (props?.zone_type as string) ?? "";
            return incentiveZoneColor(name);
          },
          getLineColor: (f: unknown) => {
            const props = (f as Record<string, unknown>).properties as Record<string, unknown> | undefined;
            const name = (props?.name as string) ?? (props?.zone_type as string) ?? "";
            return incentiveZoneLineColor(name);
          },
          lineWidthMinPixels: 2,
          getDashArray: [8, 4],
          dashJustified: true,
          extensions: [new PathStyleExtension({ dash: true })],
          pickable: true,
        })
      );
    }

    // Overlay district polygons (regulatory overlays)
    if (showOverlays && hasOverlayDistricts) {
      layers.push(
        new GeoJsonLayer({
          id: "overlay-districts",
          data: mapData!.overlay_districts as unknown as GeoJSON.FeatureCollection,
          getFillColor: (f: unknown) => {
            const props = (f as Record<string, unknown>).properties as Record<string, unknown> | undefined;
            return overlayColor((props?.overlay_type as string) ?? "");
          },
          getLineColor: (f: unknown) => {
            const props = (f as Record<string, unknown>).properties as Record<string, unknown> | undefined;
            return overlayLineColor((props?.overlay_type as string) ?? "");
          },
          lineWidthMinPixels: 2,
          pickable: true,
        })
      );
    }

    if (showPoints && filterMode === "crime" && mapData?.crimes?.length) {
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
        layers.push(pointLayer("crimes", filteredCrimes, {
          getFillColor: d => crimeColor(d.primary_type),
        }));
      }
    } else if (showPoints && filterMode === "311" && mapData?.requests_311?.length) {
      const activeTypes = new Set(
        Object.entries(srTypeToggles).filter(([, v]) => v).map(([k]) => k)
      );
      const otherActive = activeTypes.has("OTHER");
      const topTypes = new Set(Object.keys(srTypeToggles).filter(k => k !== "OTHER"));

      const filtered = mapData.requests_311.filter(r => {
        const typeMatch = activeTypes.has(r.sr_type) ||
          (otherActive && !topTypes.has(r.sr_type));
        if (!typeMatch) return false;
        if (statusFilter === "closed" && r.status !== "Closed") return false;
        if (statusFilter === "open" && r.status === "Closed") return false;
        if (!passesDateFilter(r.created_date, dateRange)) return false;
        return true;
      });

      if (filtered.length > 0) {
        layers.push(pointLayer("requests-311", filtered, {
          getFillColor: d => srTypeMapColor(d.sr_type),
          getRadius: 35,
          radiusMaxPixels: 7,
        }));
      }
    } else if (showPoints && filterMode === "permits" && mapData?.building_permits?.length) {
      const activeTypes = new Set(
        Object.entries(permitTypeToggles).filter(([, v]) => v).map(([k]) => k)
      );
      const otherActive = activeTypes.has("OTHER");

      const filteredPermits = mapData.building_permits.filter(p => {
        const normalized = normalizePermitType(p.permit_type);
        const typeMatch = activeTypes.has(normalized) ||
          (otherActive && !PERMIT_TYPE_ORDER.includes(normalized));
        if (!typeMatch) return false;
        if (costFilter !== "all" && costBucket(p.estimated_cost) !== costFilter) return false;
        if (!passesDateFilter(p.issue_date, dateRange)) return false;
        return true;
      });

      if (filteredPermits.length > 0) {
        layers.push(pointLayer("permits", filteredPermits, {
          getFillColor: d => permitColor(d.permit_type),
          getRadius: d => Math.max(40, Math.min(150, Math.sqrt(d.estimated_cost || 0) * 0.3)),
          radiusMaxPixels: 12,
        }));
      }
    }

    if (showTransit && transitStations.length > 0) {
      layers.push(
        new ScatterplotLayer<TransitStation>({
          id: "transit-stations",
          data: transitStations,
          getPosition: d => [d.lon, d.lat],
          getRadius: 50,
          getFillColor: d => d.type === "cta_rail" ? [0, 161, 222, 200] : [0, 93, 170, 200],
          getLineColor: [255, 255, 255, 180],
          stroked: true,
          lineWidthMinPixels: 1,
          radiusMinPixels: 4,
          radiusMaxPixels: 7,
          radiusUnits: "meters",
          pickable: true,
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
  }, [mapData, filterMode, crimeTypeToggles, srTypeToggles, permitTypeToggles, arrestFilter, statusFilter, costFilter, dateRange, mapReady, showZoning, showPoints, hasZoning, hasIncentiveZones, hasOverlayDistricts, showTransit, showIncentives, showOverlays, transitStations, parcelGeometry, overlayRef, contextRestored]);

  // Fit map bounds to data points
  useEffect(() => {
    if (!mapRef.current || !mapReady || !mapData) return;

    const lngs: number[] = [];
    const lats: number[] = [];

    for (const c of mapData.crimes) { lngs.push(c.longitude); lats.push(c.latitude); }
    for (const r of mapData.requests_311) { lngs.push(r.longitude); lats.push(r.latitude); }
    for (const p of mapData.building_permits) { lngs.push(p.longitude); lats.push(p.latitude); }
    if (mapData.queried_address) {
      lngs.push(mapData.queried_address.longitude);
      lats.push(mapData.queried_address.latitude);
    }

    if (lngs.length === 0) return;

    const sw: [number, number] = [Math.min(...lngs), Math.min(...lats)];
    const ne: [number, number] = [Math.max(...lngs), Math.max(...lats)];

    if (sw[0] === ne[0] && sw[1] === ne[1]) {
      mapRef.current.flyTo({ center: sw, zoom: 14, duration: 1500 });
    } else {
      mapRef.current.fitBounds([sw, ne], { padding: 40, duration: 1500, maxZoom: 15 });
    }
  }, [mapData, mapReady, mapRef]);

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
  let onToggle: (id: string) => void = () => {};

  if (filterMode === "crime") {
    toggleConfigs = Object.keys(crimeTypeToggles).map(type => {
      const color = type === "OTHER"
        ? "rgb(136,135,128)"
        : `rgba(${(CRIME_TYPE_COLORS[type] ?? [136, 135, 128, 180]).slice(0, 3).join(",")})`;
      return {
        id: type,
        label: capLabel(type),
        color,
        active: crimeTypeToggles[type],
      };
    });
    activeToggles = crimeTypeToggles;
    onToggle = toggleCrimeType;
  } else if (filterMode === "311") {
    toggleConfigs = Object.keys(srTypeToggles).map(type => ({
      id: type,
      label: type === "OTHER" ? "Other" : capLabel(type),
      color: type === "OTHER" ? "rgb(158,158,158)" : srTypeMapColorCSS(type),
      active: srTypeToggles[type],
    }));
    activeToggles = srTypeToggles;
    onToggle = toggleSrType;
  } else if (filterMode === "permits") {
    toggleConfigs = Object.keys(permitTypeToggles).map(type => ({
      id: type,
      label: type === "OTHER" ? "Other" : capLabel(type),
      color: type === "OTHER" ? "rgb(136,135,128)" : (permitColorCSS(type)),
      active: permitTypeToggles[type],
    }));
    activeToggles = permitTypeToggles;
    onToggle = togglePermitType;
  }

  const hasData = mapData && (mapData.crimes.length > 0 || mapData.requests_311.length > 0 || mapData.building_permits.length > 0);

  const arrestCount = mapData?.crimes?.filter(c => isArrested(c.arrest)).length ?? 0;
  const crimeTotal = mapData?.crimes?.length ?? 0;

  const closedCount = mapData?.requests_311?.filter(r => r.status === "Closed").length ?? 0;
  const requests311Total = mapData?.requests_311?.length ?? 0;

  const permitsTotal = mapData?.building_permits?.length ?? 0;
  const permitCostCounts: Record<CostFilterValue, number> = {
    all: permitsTotal,
    "under25k": mapData?.building_permits?.filter(p => p.estimated_cost < 25_000).length ?? 0,
    "25k-250k": mapData?.building_permits?.filter(p => p.estimated_cost >= 25_000 && p.estimated_cost <= 250_000).length ?? 0,
    "over250k": mapData?.building_permits?.filter(p => p.estimated_cost > 250_000).length ?? 0,
  };

  const capped = mapData?.capped ?? {};
  const isCapped = Object.values(capped).some(Boolean);
  const cappedCount = (capped.crimes ? mapData!.crimes.length : 0)
    + (capped.requests_311 ? mapData!.requests_311.length : 0)
    + (capped.building_permits ? mapData!.building_permits.length : 0)
    || (mapData ? mapData.crimes.length + mapData.requests_311.length + mapData.building_permits.length : 0);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />

      {/* Desktop: right-side filters (DateRangeSlider + MapLayerToggles) */}
      {!isMobile && mapReady && showPoints && (
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

      {/* Mobile: filter button (top-right) */}
      {isMobile && mapReady && showPoints && hasData && (
        <button
          onClick={() => setFilterPopoverOpen(o => !o)}
          className="absolute top-2 right-2 z-10 flex items-center gap-1.5 px-2 py-1 text-[10px] font-medium
                     rounded-md backdrop-blur-sm bg-dark-surface/90 border border-dark-border shadow-sm
                     text-text-primary transition-colors duration-150"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
          </svg>
          Filters
        </button>
      )}

      {/* Mobile: filter popover */}
      <AnimatePresence>
        {isMobile && filterPopoverOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="absolute inset-0 z-20 bg-black/20"
              onClick={() => setFilterPopoverOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -4 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -4 }}
              transition={{ duration: 0.15 }}
              className="absolute top-10 right-2 z-30 w-[240px] max-h-[60vh] overflow-y-auto
                         bg-dark-surface border border-dark-border rounded-xl p-3 shadow-2xl space-y-2.5"
            >
              {isMultiSource && availableTabs.length > 1 && (
                <div className="flex w-full bg-dark-bg rounded-md overflow-hidden">
                  {availableTabs.map((tab) => {
                    const label = tab === "crime" ? "Crime" : tab === "311" ? "311" : "Permits";
                    return (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`flex-1 px-2 py-1 text-[11px] font-medium transition-colors duration-150
                          ${filterMode === tab
                            ? "bg-dark-elevated text-text-primary"
                            : "text-text-muted hover:text-text-secondary"
                          }
                          ${tab !== availableTabs[0] ? "border-l border-dark-border" : ""}`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              )}

              {toggleConfigs.length > 0 && (
                <div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1.5">Type Filters</div>
                  <MapLayerToggles layers={toggleConfigs} onToggle={onToggle} />
                </div>
              )}

              {filterMode === "crime" && crimeTotal > 0 && (
                <div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1.5">Arrest Status</div>
                  <ToggleGroup<ArrestFilterValue>
                    value={arrestFilter}
                    onChange={setArrestFilter}
                    options={[
                      { value: "all", label: `All (${crimeTotal})` },
                      { value: "arrested", label: `Arrested (${arrestCount})` },
                      { value: "not-arrested", label: `No Arrest (${crimeTotal - arrestCount})` },
                    ]}
                  />
                </div>
              )}

              {filterMode === "311" && requests311Total > 0 && (
                <div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1.5">Status</div>
                  <ToggleGroup<StatusFilterValue>
                    value={statusFilter}
                    onChange={setStatusFilter}
                    options={[
                      { value: "all", label: `All (${requests311Total})` },
                      { value: "closed", label: `Closed (${closedCount})` },
                      { value: "open", label: `Open (${requests311Total - closedCount})` },
                    ]}
                  />
                </div>
              )}

              {filterMode === "permits" && permitsTotal > 0 && (
                <div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1.5">Cost Range</div>
                  <ToggleGroup<CostFilterValue>
                    value={costFilter}
                    onChange={setCostFilter}
                    options={[
                      { value: "all", label: `All (${permitsTotal})` },
                      { value: "under25k", label: `<$25K (${permitCostCounts.under25k})` },
                      { value: "25k-250k", label: `$25K–$250K (${permitCostCounts["25k-250k"]})` },
                      { value: "over250k", label: `>$250K (${permitCostCounts.over250k})` },
                    ]}
                  />
                </div>
              )}

              {dateBounds && dateRange && hasData && (
                <div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1.5">Date Range</div>
                  <DateRangeSlider
                    minDate={dateBounds.min}
                    maxDate={dateBounds.max}
                    startDate={dateRange[0]}
                    endDate={dateRange[1]}
                    onChange={(s, e) => setDateRange([s, e])}
                  />
                </div>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {!isMobile && mapReady && (
        <MapLegend
          activeLayers={activeToggles}
          filterMode={filterMode}
          showPoints={showPoints}
          showZoning={showZoning}
          hasZoning={hasZoning}
        />
      )}

      {mapReady && (hasZoning || hasData || true) && (
        <div className={`absolute top-2 left-2 z-10 flex flex-col gap-1.5 ${isMobile ? "max-w-[calc(70%-8px)]" : "max-w-[calc(50%-8px)]"}`}>
          <div className="flex gap-1 flex-wrap">
            {hasZoning && (
              <button
                onClick={() => setShowZoning(s => !s)}
                className={`flex items-center gap-1 ${isMobile ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-[11px]"} font-medium rounded-md backdrop-blur-sm border transition-colors duration-150
                  ${showZoning
                    ? "bg-dark-surface/90 text-text-primary border-dark-border shadow-sm"
                    : "bg-dark-bg/60 text-text-muted border-transparent hover:bg-dark-surface/60"
                  }`}
              >
                <span
                  className={`${isMobile ? "w-2 h-2" : "w-2.5 h-2.5"} rounded-sm inline-block border`}
                  style={{
                    backgroundColor: showZoning ? "rgba(66,133,244,0.5)" : "transparent",
                    borderColor: showZoning ? "rgba(66,133,244,0.8)" : "#555",
                  }}
                />
                Zoning
              </button>
            )}
            {hasData && (
              <button
                onClick={() => setShowPoints(s => !s)}
                className={`flex items-center gap-1 ${isMobile ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-[11px]"} font-medium rounded-md backdrop-blur-sm border transition-colors duration-150
                  ${showPoints
                    ? "bg-dark-surface/90 text-text-primary border-dark-border shadow-sm"
                    : "bg-dark-bg/60 text-text-muted border-transparent hover:bg-dark-surface/60"
                  }`}
              >
                <span
                  className="w-2 h-2 rounded-full inline-block"
                  style={{ backgroundColor: showPoints ? "#eee" : "#555" }}
                />
                Points
              </button>
            )}
            <button
              onClick={() => setShowTransit(s => !s)}
              className={`flex items-center gap-1 ${isMobile ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-[11px]"} font-medium rounded-md backdrop-blur-sm border transition-colors duration-150
                ${showTransit
                  ? "bg-dark-surface/90 text-text-primary border-dark-border shadow-sm"
                  : "bg-dark-bg/60 text-text-muted border-transparent hover:bg-dark-surface/60"
                }`}
            >
              <span
                className={`${isMobile ? "w-1.5 h-1.5" : "w-2 h-2"} rounded-sm inline-block`}
                style={{
                  backgroundColor: showTransit ? "rgba(0,161,222,0.5)" : "transparent",
                  border: showTransit ? "1px solid rgba(0,161,222,0.8)" : "1px solid #555",
                }}
              />
              Transit
            </button>
            {mapData?.incentive_zones && (
              <button
                onClick={() => setShowIncentives(s => !s)}
                className={`flex items-center gap-1 ${isMobile ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-[11px]"} font-medium rounded-md backdrop-blur-sm border transition-colors duration-150
                  ${showIncentives
                    ? "bg-dark-surface/90 text-text-primary border-dark-border shadow-sm"
                    : "bg-dark-bg/60 text-text-muted border-transparent hover:bg-dark-surface/60"
                  }`}
              >
                <span
                  className={`${isMobile ? "w-2 h-2" : "w-2.5 h-2.5"} rounded-sm inline-block`}
                  style={{
                    backgroundColor: showIncentives ? "rgba(255,87,34,0.5)" : "transparent",
                    border: showIncentives ? "1px solid rgba(255,87,34,0.8)" : "1px solid #555",
                  }}
                />
                Incentives
              </button>
            )}
            {mapData?.overlay_districts && (
              <button
                onClick={() => setShowOverlays(s => !s)}
                className={`flex items-center gap-1 ${isMobile ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-[11px]"} font-medium rounded-md backdrop-blur-sm border transition-colors duration-150
                  ${showOverlays
                    ? "bg-dark-surface/90 text-text-primary border-dark-border shadow-sm"
                    : "bg-dark-bg/60 text-text-muted border-transparent hover:bg-dark-surface/60"
                  }`}
              >
                <span
                  className={`${isMobile ? "w-2 h-2" : "w-2.5 h-2.5"} rounded-sm inline-block`}
                  style={{
                    backgroundColor: showOverlays ? "rgba(156,39,176,0.5)" : "transparent",
                    border: showOverlays ? "1px solid rgba(156,39,176,0.8)" : "1px solid #555",
                  }}
                />
                Overlays
              </button>
            )}
          </div>

          {/* Desktop: inline source tabs + filters */}
          {!isMobile && showPoints && hasData && (
            <>
              {isMultiSource && availableTabs.length > 1 && (
                <div className="flex w-full bg-dark-surface/90 backdrop-blur-sm rounded-md border border-dark-border shadow-sm overflow-hidden">
                  {availableTabs.map((tab) => {
                    const label = tab === "crime" ? "Crime" : tab === "311" ? "311" : "Permits";
                    return (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`flex-1 px-2.5 py-1 text-[11px] font-medium transition-colors duration-150
                          ${filterMode === tab
                            ? "bg-dark-elevated text-text-primary"
                            : "text-text-muted hover:text-text-secondary hover:bg-dark-surface/60"
                          }
                          ${tab !== availableTabs[0] ? "border-l border-dark-border" : ""}`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              )}

              {filterMode === "crime" && crimeTotal > 0 && (
                <ToggleGroup<ArrestFilterValue>
                  value={arrestFilter}
                  onChange={setArrestFilter}
                  options={[
                    { value: "all", label: `All (${crimeTotal})` },
                    { value: "arrested", label: `Arrested (${arrestCount})` },
                    { value: "not-arrested", label: `No Arrest (${crimeTotal - arrestCount})` },
                  ]}
                />
              )}

              {filterMode === "311" && requests311Total > 0 && (
                <ToggleGroup<StatusFilterValue>
                  value={statusFilter}
                  onChange={setStatusFilter}
                  options={[
                    { value: "all", label: `All (${requests311Total})` },
                    { value: "closed", label: `Closed (${closedCount})` },
                    { value: "open", label: `Open (${requests311Total - closedCount})` },
                  ]}
                />
              )}

              {filterMode === "permits" && permitsTotal > 0 && (
                <ToggleGroup<CostFilterValue>
                  value={costFilter}
                  onChange={setCostFilter}
                  options={[
                    { value: "all", label: `All (${permitsTotal})` },
                    { value: "under25k", label: `<$25K (${permitCostCounts.under25k})` },
                    { value: "25k-250k", label: `$25K–$250K (${permitCostCounts["25k-250k"]})` },
                    { value: "over250k", label: `>$250K (${permitCostCounts.over250k})` },
                  ]}
                />
              )}
            </>
          )}
        </div>
      )}

      {loading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-dark-bg/60 backdrop-blur-sm">
          <div className="text-text-muted text-sm animate-pulse">Loading map data...</div>
        </div>
      )}

      {!loading && !hasData && !hasZoning && !hasIncentiveZones && !hasOverlayDistricts && mapReady && (
        <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
          <span className="text-text-muted text-xs bg-dark-surface/80 backdrop-blur-sm px-3 py-1.5 rounded-lg">
            Ask a question to see data on the map
          </span>
        </div>
      )}

      {!loading && mapReady && isCapped && showPoints && (
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
            className={`bg-dark-surface border border-dark-border rounded-xl p-4 shadow-2xl ${
              selectedItem.type === "regulatory" ? "max-w-[320px] w-[92%]" : "max-w-[280px] w-[90%]"
            }`}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-text-primary">
                {selectedItem.type === "crime" ? "Crime Incident" :
                 selectedItem.type === "311" ? "311 Request" :
                 selectedItem.type === "zoning" ? "Zoning District" :
                 selectedItem.type === "regulatory" ? "Regulatory Zones" :
                 "Building Permit"}
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
            <div className={`space-y-2 text-xs ${
              selectedItem.type === "regulatory" ? "max-h-[50vh] overflow-y-auto pr-1" : ""
            }`}>
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

const ZONING_MAP_URL = "https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning";

function renderDetailFields(item: SelectedItem) {
  if (item.type === "zoning") {
    const d = item.data;
    const prefix = zonePrefix(d.zone_class);
    const info = ZONE_INFO[prefix];
    return (
      <>
        <DetailRow label="Zone Class" value={d.zone_class} />
        {info && (
          <div className="text-text-muted leading-relaxed">
            <span className="text-text-secondary font-medium">{info.label}</span>
            {" — "}{info.description}
          </div>
        )}
        {info && info.examples.length > 0 && (
          <div>
            <span className="text-text-muted text-[10px] uppercase tracking-wide">Allowed uses</span>
            <ul className="mt-0.5 space-y-0.5">
              {info.examples.map(ex => (
                <li key={ex} className="flex items-center gap-1.5 text-text-primary">
                  <span className="w-1 h-1 rounded-full bg-text-muted shrink-0" />
                  {ex}
                </li>
              ))}
            </ul>
          </div>
        )}
        {d.ordinance_num && <DetailRow label="Ordinance" value={d.ordinance_num} />}
        <DetailRow label="Official Map" value="Chicago Zoning Map" href={ZONING_MAP_URL} />
      </>
    );
  }
  if (item.type === "regulatory") {
    const { zoning, overlays, incentives } = item.zones;
    return (
      <>
        {zoning && (
          <div className={overlays.length > 0 || incentives.length > 0 ? "pb-2 border-b border-dark-border mb-2" : ""}>
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Base Zoning</div>
            <DetailRow label="Zone Class" value={zoning.zone_class} />
            {(() => {
              const prefix = zonePrefix(zoning.zone_class);
              const zInfo = ZONE_INFO[prefix];
              return zInfo ? (
                <div className="text-text-muted leading-relaxed mt-1">
                  <span className="text-text-secondary font-medium">{zInfo.label}</span>
                  {" — "}{zInfo.description}
                </div>
              ) : null;
            })()}
          </div>
        )}

        {overlays.length > 0 && (
          <div className={incentives.length > 0 ? "pb-2 border-b border-dark-border mb-2" : ""}>
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Regulatory Overlays</div>
            {overlays.map((ov, i) => {
              const oInfo = OVERLAY_INFO[ov.overlay_type];
              return (
                <div key={i} className="mb-2 last:mb-0">
                  <div className="flex items-center gap-1.5">
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: overlayColorCSS(ov.overlay_type) }}
                    />
                    <span className="text-text-primary font-medium">
                      {overlayLabel(ov.overlay_type)}
                    </span>
                  </div>
                  {ov.feature_name && (
                    <p className="text-text-secondary text-[11px] ml-3.5">{ov.feature_name}</p>
                  )}
                  {oInfo && (
                    <p className="text-text-muted text-[10px] ml-3.5 mt-0.5">{oInfo.description}</p>
                  )}
                  {oInfo && oInfo.implications.length > 0 && (
                    <ul className="ml-3.5 mt-0.5 space-y-0.5">
                      {oInfo.implications.map(imp => (
                        <li key={imp} className="flex items-center gap-1.5 text-[10px] text-text-muted">
                          <span className="w-1 h-1 rounded-full bg-text-muted shrink-0" />
                          {imp}
                        </li>
                      ))}
                    </ul>
                  )}
                  {ov.ordinance && (
                    <p className="text-[10px] text-text-muted ml-3.5 mt-0.5">Ord. {ov.ordinance}</p>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {incentives.length > 0 && (
          <div>
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Incentive Zones</div>
            {incentives.map((inc, i) => (
              <div key={i} className="flex items-center gap-1.5 mb-1 last:mb-0">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{
                    backgroundColor: incentiveZoneColorCSS(inc.name || inc.zone_type)
                  }}
                />
                <span className="text-text-primary font-medium">{incentiveLabel(inc.zone_type)}</span>
                {inc.name && (
                  <span className="text-text-muted">— {inc.name}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </>
    );
  }
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
