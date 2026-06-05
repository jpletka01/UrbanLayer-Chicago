import { useCallback, useEffect, useRef, useState } from "react";
import type { ContextObject, MapData, SidebarView, SourceTag } from "../lib/types";
import { SidebarHeader } from "./SidebarHeader";
import { DataMapLayout } from "./sidebar/DataMapLayout";
import { SourcesView } from "./sidebar/SourcesView";

const RAIL_WIDTH = 44;
const MIN_WIDTH = 320;
const DEFAULT_WIDTH = 480;
const SNAP_CLOSE_THRESHOLD = 200;

function countDataCategories(ctx: ContextObject | null): number {
  if (!ctx) return 0;
  let count = 0;
  if (ctx.crime_last_90d) count++;
  if (ctx.open_311_requests) count++;
  if (ctx.permits) count++;
  if (ctx.violations) count++;
  if (ctx.businesses) count++;
  if (ctx.vacant_buildings) count++;
  if (ctx.food_inspections) count++;
  if (ctx.parcel_zoning) count++;
  if (ctx.regulatory) count++;
  if (ctx.property) count++;
  if (ctx.incentives) count++;
  if (ctx.neighborhood) count++;
  return count;
}

interface Props {
  context: ContextObject | null;
  loading: boolean;
  isOpen: boolean;
  onToggle: () => void;
  activeView: SidebarView;
  onViewChange: (view: SidebarView) => void;
  highlightedSourceIndex?: number | null;
  sourceFlashSignal?: number;
  sourceCount?: number;
  onSourceClick?: (index: number) => void;
  onCrossRefClick?: (sectionId: string) => void;
  mapData?: MapData | null;
  mapLoading?: boolean;
  mapSources?: SourceTag[];
  showDataBadge?: boolean;
  showSourcesBadge?: boolean;
}

export function SidebarPanel({
  context,
  loading,
  isOpen,
  onToggle,
  activeView,
  onViewChange,
  highlightedSourceIndex,
  sourceFlashSignal,
  sourceCount: _ = 0,
  onSourceClick,
  onCrossRefClick,
  mapData,
  mapLoading = false,
  mapSources = [],
  showDataBadge = false,
  showSourcesBadge = false,
}: Props) {
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [isDragging, setIsDragging] = useState(false);
  const asideRef = useRef<HTMLElement>(null);

  const title = context?.community_area_name ?? "Context & Data";
  const subtitle = context?.community_area ? `CA ${context.community_area}` : undefined;
  const hasCodeChunks = (context?.code_chunks?.length ?? 0) > 0;
  const dataCount = countDataCategories(context);
  const srcCount = context?.code_chunks?.length ?? 0;

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

          {showDataBadge && dataCount > 0 && (
            <span className="min-w-[1.25rem] h-5 px-1 rounded-full text-[10px] font-semibold flex items-center justify-center bg-accent/20 text-accent">
              {dataCount > 9 ? "9+" : dataCount}
            </span>
          )}
          {showSourcesBadge && srcCount > 0 && (
            <span className="min-w-[1.25rem] h-5 px-1 rounded-full text-[10px] font-semibold flex items-center justify-center bg-accent/20 text-accent">
              {srcCount > 9 ? "9+" : srcCount}
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
          dataCount={dataCount}
          sourceCount={srcCount}
          showDataBadge={showDataBadge}
          showSourcesBadge={showSourcesBadge}
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
          context={context}
          loading={loading}
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
