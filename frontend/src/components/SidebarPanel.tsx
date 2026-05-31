import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ContextObject, DataSource, MapData, RetrievalPlan, SidebarView, SourceTag } from "../lib/types";
import { SidebarHeader } from "./SidebarHeader";
import { DataView } from "./sidebar/DataView";
import { MapView } from "./sidebar/MapView";
import { SourcesView } from "./sidebar/SourcesView";

const RAIL_WIDTH = 44;
const MIN_WIDTH = 320;
const DEFAULT_WIDTH = 480;
const SNAP_CLOSE_THRESHOLD = 200;

interface Props {
  plan: RetrievalPlan | null;
  context: ContextObject | null;
  loading: boolean;
  isOpen: boolean;
  onToggle: () => void;
  activeView: SidebarView;
  onViewChange: (view: SidebarView) => void;
  highlightedSourceIndex?: number | null;
  highlightedDataSource?: DataSource | null;
  sourceFlashSignal?: number;
  sourceCount?: number;
  onSourceClick?: (index: number) => void;
  onCrossRefClick?: (sectionId: string) => void;
  mapData?: MapData | null;
  mapLoading?: boolean;
  mapSources?: SourceTag[];
}

export function SidebarPanel({
  plan,
  context,
  loading,
  isOpen,
  onToggle,
  activeView,
  onViewChange,
  highlightedSourceIndex,
  highlightedDataSource,
  sourceFlashSignal,
  sourceCount = 0,
  onSourceClick,
  onCrossRefClick,
  mapData,
  mapLoading = false,
  mapSources = [],
}: Props) {
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [isDragging, setIsDragging] = useState(false);
  const asideRef = useRef<HTMLElement>(null);

  const title = context?.community_area_name ?? "Context & Data";
  const subtitle = context?.community_area ? `CA ${context.community_area}` : undefined;
  const hasCodeChunks = (context?.code_chunks?.length ?? 0) > 0;

  const maxWidth = useCallback(
    () => Math.min(window.innerWidth * 0.6, window.innerWidth - 400),
    [],
  );

  const handleDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsDragging(true);

      const startX = e.clientX;
      const startWidth = width;

      function onMove(ev: MouseEvent) {
        const delta = startX - ev.clientX;
        const next = startWidth + delta;
        if (next < SNAP_CLOSE_THRESHOLD) return;
        setWidth(Math.max(MIN_WIDTH, Math.min(next, maxWidth())));
      }

      function onUp(ev: MouseEvent) {
        setIsDragging(false);
        const delta = startX - ev.clientX;
        const next = startWidth + delta;
        if (next < SNAP_CLOSE_THRESHOLD) {
          setWidth(startWidth);
          onToggle();
        }
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      }

      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [width, maxWidth, onToggle],
  );

  useEffect(() => {
    if (isDragging) {
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    } else {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isDragging]);

  // ---------- collapsed rail ----------
  if (!isOpen) {
    return (
      <aside
        className="hidden md:flex flex-col items-center h-full shrink-0
                   bg-dark-bg border-l border-dark-border
                   cursor-pointer select-none
                   hover:bg-dark-surface/60 transition-colors duration-150"
        style={{ width: RAIL_WIDTH }}
        onClick={onToggle}
        title="Open panel (⌘B)"
      >
        <div className="flex flex-col items-center gap-3 pt-4">
          {/* icon */}
          <svg
            className="w-4 h-4 text-text-muted"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
            />
          </svg>

          {sourceCount > 0 && (
            <span className="min-w-[1.25rem] h-5 px-1 rounded-full text-[10px] font-semibold flex items-center justify-center bg-accent/20 text-accent">
              {sourceCount}
            </span>
          )}
        </div>

        {/* vertical label */}
        <span
          className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted mt-6"
          style={{ writingMode: "vertical-lr" }}
        >
          Sources
        </span>
      </aside>
    );
  }

  // ---------- expanded panel ----------
  return (
    <aside
      ref={asideRef}
      className="hidden md:flex flex-col h-full shrink-0 bg-dark-bg border-l border-dark-border overflow-hidden relative"
      style={{
        width,
        transition: isDragging ? "none" : "width 0.25s ease",
      }}
    >
      {/* drag handle */}
      <div
        className="absolute left-0 top-0 bottom-0 w-1.5 z-10 cursor-col-resize
                   group/handle hover:bg-accent/20 active:bg-accent/30
                   transition-colors duration-100"
        onMouseDown={handleDragStart}
        onDoubleClick={onToggle}
        title="Drag to resize · Double-click to collapse"
      >
        <div className="absolute left-0 top-0 bottom-0 w-px bg-dark-border group-hover/handle:bg-accent/50 transition-colors" />
      </div>

      {/* header */}
      <div className="flex items-center gap-2 pl-4 pr-2 py-3 border-b border-dark-border shrink-0">
        <SidebarHeader
          title={title}
          subtitle={subtitle}
          activeView={activeView}
          onViewChange={onViewChange}
          hasCodeChunks={hasCodeChunks}
        />
        <button
          onClick={onToggle}
          className="p-1.5 rounded-lg text-text-muted hover:text-text-primary
                     hover:bg-dark-elevated transition-colors shrink-0"
          title="Close panel (⌘B)"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* content */}
      {activeView === "data" ? (
        <DataMapLayout
          mapData={mapData ?? null}
          mapLoading={mapLoading}
          mapSources={mapSources}
          plan={plan}
          context={context}
          loading={loading}
          highlightedDataSource={highlightedDataSource}
        />
      ) : (
        <div className="flex-1 overflow-y-auto p-4">
          <SourcesView
            codeChunks={context?.code_chunks ?? []}
            highlightedIndex={highlightedSourceIndex}
            flashSignal={sourceFlashSignal}
            onSourceClick={onSourceClick}
            onCrossRefClick={onCrossRefClick}
          />
        </div>
      )}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// DataMapLayout — map fills most of the sidebar, data panel at the bottom
// with a drag divider and collapse toggle.
// ---------------------------------------------------------------------------

const MIN_DATA_HEIGHT = 0;
const COLLAPSED_DATA_HEIGHT = 36;
const DEFAULT_DATA_RATIO = 0.25; // data gets 25% of available height by default

interface DataMapLayoutProps {
  mapData: MapData | null;
  mapLoading: boolean;
  mapSources: SourceTag[];
  plan: RetrievalPlan | null;
  context: ContextObject | null;
  loading: boolean;
  highlightedDataSource?: DataSource | null;
}

function DataMapLayout({
  mapData,
  mapLoading,
  mapSources,
  plan,
  context,
  loading,
  highlightedDataSource,
}: DataMapLayoutProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dataHeight, setDataHeight] = useState<number | null>(null);
  const [dataCollapsed, setDataCollapsed] = useState(false);
  const [dividerDragging, setDividerDragging] = useState(false);

  const hasData =
    context?.crime_last_90d ||
    context?.open_311_requests ||
    context?.permits ||
    context?.violations ||
    context?.businesses;

  // Initialize data height on first render
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
        <MapView mapData={mapData} loading={mapLoading} sources={mapSources} />
      </div>

      {/* Drag divider */}
      {hasData && (
        <div
          className="shrink-0 h-1.5 cursor-row-resize group/divider relative
                     hover:bg-accent/20 active:bg-accent/30 transition-colors duration-100"
          onMouseDown={handleDividerDrag}
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
                plan={plan}
                context={context}
                loading={loading}
                highlightedDataSource={highlightedDataSource}
              />
            </div>
          )}
        </div>
      )}

      {/* When no data, map fills everything */}
      {!hasData && context && !loading && (
        <div className="shrink-0 px-4 py-3 border-t border-dark-border">
          <p className="text-xs text-text-muted">No live datasets were queried for this answer.</p>
        </div>
      )}
    </div>
  );
}
