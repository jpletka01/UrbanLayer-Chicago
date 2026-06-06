import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ContextObject, MapData, SourceTag } from "../../lib/types";
import { deriveFilterMode } from "../../lib/mapColors";
import { DataView } from "./DataView";
import { MapView } from "./MapView";

const MIN_DATA_HEIGHT = 0;
const COLLAPSED_DATA_HEIGHT = 36;
const DEFAULT_DATA_RATIO = 0.5;

export interface DataMapLayoutProps {
  mapData: MapData | null;
  mapLoading: boolean;
  mapSources: SourceTag[];
  context: ContextObject | null;
  loading: boolean;
}

export function DataMapLayout({
  mapData,
  mapLoading,
  mapSources,
  context,
  loading,
}: DataMapLayoutProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dataHeight, setDataHeight] = useState<number | null>(null);
  const [dataCollapsed, setDataCollapsed] = useState(false);
  const [dividerDragging, setDividerDragging] = useState(false);

  const hasMapPointData =
    mapData && (mapData.crimes.length > 0 || mapData.requests_311.length > 0 || mapData.building_permits.length > 0);
  const hasZoning = !!(mapData?.zoning && ((mapData.zoning as Record<string, unknown>).features as unknown[] | undefined)?.length);
  const hasDomainData = !!(context?.property || context?.regulatory || context?.incentives || context?.neighborhood
    || context?.violations || context?.crime_last_90d || context?.open_311_requests || context?.permits || context?.businesses);
  const hasData = hasMapPointData || hasDomainData || hasZoning;

  useEffect(() => {
    if (dataHeight !== null || !containerRef.current) return;
    const h = containerRef.current.clientHeight;
    setDataHeight(Math.round(h * DEFAULT_DATA_RATIO));
  }, [dataHeight]);

  const effectiveDataHeight = useMemo(() => {
    if (dataCollapsed) return COLLAPSED_DATA_HEIGHT;
    return Math.max(dataHeight ?? 200, MIN_DATA_HEIGHT);
  }, [dataCollapsed, dataHeight]);

  const handleDividerDrag = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setDividerDragging(true);

      const startY = e.clientY;
      const startHeight = effectiveDataHeight;
      const container = containerRef.current;
      if (!container) return;

      function onMove(ev: MouseEvent) {
        const delta = startY - ev.clientY;
        const maxH = (container?.clientHeight ?? 600) - 100;
        const next = Math.max(COLLAPSED_DATA_HEIGHT, Math.min(startHeight + delta, maxH));
        setDataHeight(next);
        if (next <= COLLAPSED_DATA_HEIGHT + 10) {
          setDataCollapsed(true);
        } else {
          setDataCollapsed(false);
        }
      }

      function onUp() {
        setDividerDragging(false);
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      }

      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [effectiveDataHeight],
  );

  const handleDividerTouchDrag = useCallback(
    (e: React.TouchEvent) => {
      e.preventDefault();
      setDividerDragging(true);

      const startY = e.touches[0].clientY;
      const startHeight = effectiveDataHeight;
      const container = containerRef.current;
      if (!container) return;

      function onMove(ev: TouchEvent) {
        ev.preventDefault();
        const delta = startY - ev.touches[0].clientY;
        const maxH = (container?.clientHeight ?? 600) - 100;
        const next = Math.max(COLLAPSED_DATA_HEIGHT, Math.min(startHeight + delta, maxH));
        setDataHeight(next);
        if (next <= COLLAPSED_DATA_HEIGHT + 10) {
          setDataCollapsed(true);
        } else {
          setDataCollapsed(false);
        }
      }

      function onUp() {
        setDividerDragging(false);
        window.removeEventListener("touchmove", onMove);
        window.removeEventListener("touchend", onUp);
      }

      window.addEventListener("touchmove", onMove, { passive: false });
      window.addEventListener("touchend", onUp);
    },
    [effectiveDataHeight],
  );

  useEffect(() => {
    if (dividerDragging) {
      document.body.style.cursor = "row-resize";
      document.body.style.userSelect = "none";
    } else {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [dividerDragging]);

  return (
    <div ref={containerRef} className="flex-1 flex flex-col overflow-hidden min-h-0">
      {/* Map area — fills remaining space */}
      <div className="flex-1 min-h-[100px]">
        <MapView mapData={mapData} loading={mapLoading} sources={mapSources} parcelGeometry={context?.property?.parcel_geometry} hasTransitContext={!!context?.neighborhood?.transit} />
      </div>

      {/* Drag divider */}
      {hasData && (
        <div
          className="shrink-0 h-1.5 cursor-row-resize group/divider relative
                     hover:bg-accent/20 active:bg-accent/30 transition-colors duration-100"
          onMouseDown={handleDividerDrag}
          onTouchStart={handleDividerTouchDrag}
          onDoubleClick={() => setDataCollapsed((c) => !c)}
          title="Drag to resize · Double-click to collapse"
        >
          <div className="absolute inset-x-0 top-0 h-px bg-dark-border group-hover/divider:bg-accent/50 transition-colors" />
        </div>
      )}

      {/* Data panel */}
      {hasData && (
        <div
          className="shrink-0 overflow-hidden"
          style={{
            height: effectiveDataHeight,
            transition: dividerDragging ? "none" : "height 0.2s ease",
          }}
        >
          {/* Collapse header */}
          <button
            onClick={() => setDataCollapsed((c) => !c)}
            className="w-full flex items-center gap-2 px-4 py-2 text-xs font-medium text-text-muted
                       hover:text-text-secondary hover:bg-dark-surface/40 transition-colors"
          >
            <svg
              className={`w-3 h-3 transition-transform duration-200 ${dataCollapsed ? "" : "rotate-180"}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
            </svg>
            Data
          </button>

          {/* Scrollable data content */}
          {!dataCollapsed && (
            <div className="overflow-y-auto px-4 pb-4" style={{ height: effectiveDataHeight - COLLAPSED_DATA_HEIGHT }}>
              <DataView
                context={context}
                loading={loading}
                mapData={mapData}
                filterMode={deriveFilterMode(mapSources)}
              />
            </div>
          )}
        </div>
      )}

      {/* When no data, map fills everything */}
      {!hasData && context && !loading && !hasDomainData && (
        <div className="shrink-0 px-4 py-3 border-t border-dark-border">
          <p className="text-xs text-text-muted">No live datasets were queried for this answer.</p>
        </div>
      )}
    </div>
  );
}
