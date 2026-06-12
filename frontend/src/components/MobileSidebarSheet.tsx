import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import type { ContextObject, MapData, SidebarView, SourceTag } from "../lib/types";
import { deriveFilterMode, hasSpatialMapContent } from "../lib/mapColors";
import { MapView } from "./sidebar/MapView";
import { DataView } from "./sidebar/DataView";
import { SourcesView } from "./sidebar/SourcesView";

const SNAP_PEEK = 20;
const SNAP_DEFAULT = 70;
const SNAP_FULL = 90;
const SNAP_CLOSE_THRESHOLD = 12;
const SNAPS = [SNAP_PEEK, SNAP_DEFAULT, SNAP_FULL];

function nearestSnap(vh: number): number {
  let best = SNAPS[0];
  let bestDist = Math.abs(vh - best);
  for (const s of SNAPS) {
    const d = Math.abs(vh - s);
    if (d < bestDist) { best = s; bestDist = d; }
  }
  return best;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  context: ContextObject | null;
  loading: boolean;
  activeView: SidebarView;
  onViewChange: (view: SidebarView) => void;
  highlightedSourceIndex?: number | null;
  sourceFlashSignal?: number;
  onSourceClick?: (index: number) => void;
  onCrossRefClick?: (sectionId: string) => void;
  mapData?: MapData | null;
  mapLoading?: boolean;
  mapSources?: SourceTag[];
  mapIntent?: string | null;
  showDataBadge?: boolean;
  showSourcesBadge?: boolean;
  showMapBadge?: boolean;
  dataCount?: number;
  sourceCount?: number;
}

export function MobileSidebarSheet({
  isOpen,
  onClose,
  context,
  loading,
  activeView,
  onViewChange,
  highlightedSourceIndex,
  sourceFlashSignal,
  onSourceClick,
  onCrossRefClick,
  mapData,
  mapLoading = false,
  mapSources = [],
  mapIntent = null,
  showDataBadge = false,
  showSourcesBadge = false,
  showMapBadge = false,
  dataCount = 0,
  sourceCount = 0,
}: Props) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const { t } = useTranslation("sidebar");
  const dragStartY = useRef<number | null>(null);
  const dragStartSnap = useRef<number>(SNAP_DEFAULT);
  const dragging = useRef(false);
  const [snapVh, setSnapVh] = useState(SNAP_DEFAULT);

  const title = context?.community_area_name ?? "Context & Data";
  const subtitle = context?.community_area ? `CA ${context.community_area}` : undefined;
  const hasCodeChunks = (context?.code_chunks?.length ?? 0) > 0;

  // Same spatial-content rule as the desktop sidebar: no renderable layers →
  // no Map tab (map-relevance review, 2026-06-12).
  const hasMapContent = mapLoading ||
    hasSpatialMapContent(mapData, !!context?.neighborhood?.transit, context?.property?.parcel_geometry);

  useEffect(() => {
    if (isOpen) setSnapVh(SNAP_DEFAULT);
  }, [isOpen]);

  const handleDragStart = useCallback((e: React.TouchEvent) => {
    dragStartY.current = e.touches[0].clientY;
    dragStartSnap.current = snapVh;
    dragging.current = true;
    if (sheetRef.current) {
      sheetRef.current.style.transition = "none";
    }
  }, [snapVh]);

  const handleDragMove = useCallback((e: React.TouchEvent) => {
    if (dragStartY.current === null || !sheetRef.current) return;
    const deltaPixels = e.touches[0].clientY - dragStartY.current;
    const deltaVh = (deltaPixels / window.innerHeight) * 100;
    const newVh = Math.max(SNAP_CLOSE_THRESHOLD, Math.min(95, dragStartSnap.current - deltaVh));
    sheetRef.current.style.height = `${newVh}vh`;
  }, []);

  const handleDragEnd = useCallback(
    (e: React.TouchEvent) => {
      if (dragStartY.current === null || !sheetRef.current) return;
      dragging.current = false;
      sheetRef.current.style.transition = "";

      const deltaPixels = e.changedTouches[0].clientY - dragStartY.current;
      const deltaVh = (deltaPixels / window.innerHeight) * 100;
      const currentVh = dragStartSnap.current - deltaVh;

      if (currentVh < SNAP_CLOSE_THRESHOLD) {
        onClose();
      } else {
        const target = nearestSnap(currentVh);
        setSnapVh(target);
        sheetRef.current.style.height = `${target}vh`;
      }
      dragStartY.current = null;
    },
    [onClose],
  );

  const tabs: { key: SidebarView; label: string; show: boolean; badge: boolean }[] = [
    { key: "map", label: t("map"), show: hasMapContent, badge: showMapBadge },
    { key: "data", label: t("data"), show: true, badge: showDataBadge && dataCount > 0 },
    { key: "sources", label: t("sources"), show: hasCodeChunks, badge: showSourcesBadge && sourceCount > 0 },
  ];
  const visibleTabs = tabs.filter(tab => tab.show);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-black/60"
            onClick={onClose}
          />

          <motion.div
            ref={sheetRef}
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 300 }}
            className="fixed bottom-0 left-0 right-0 z-50 flex flex-col bg-dark-bg rounded-t-2xl border-t border-dark-border"
            style={{
              height: `${snapVh}vh`,
              transition: "height 0.3s cubic-bezier(0.32, 0.72, 0, 1)",
            }}
          >
            {/* Drag handle */}
            <div
              className="flex justify-center pt-3 pb-2 cursor-grab active:cursor-grabbing min-h-[44px] touch-none"
              onTouchStart={handleDragStart}
              onTouchMove={handleDragMove}
              onTouchEnd={handleDragEnd}
            >
              <div className="w-10 h-1 rounded-full bg-text-muted/40" />
            </div>

            {/* Header */}
            <div className="flex items-center gap-2 px-4 py-2 border-b border-dark-border shrink-0">
              <div className="min-w-0 shrink">
                <h2 className="text-sm font-semibold text-text-primary truncate">{title}</h2>
                {subtitle && <p className="text-xs text-text-muted mt-0.5">{subtitle}</p>}
              </div>

              {visibleTabs.length > 1 && (
                <div className="flex items-center gap-0.5 bg-dark-bg rounded-lg p-0.5 shrink-0 ml-auto">
                  {visibleTabs.map(tab => (
                    <button
                      key={tab.key}
                      onClick={() => onViewChange(tab.key)}
                      className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-150 inline-flex items-center gap-1
                        ${activeView === tab.key
                          ? "bg-dark-surface text-text-primary shadow-sm"
                          : "text-text-muted hover:text-text-secondary"
                        }`}
                    >
                      {tab.label}
                      {tab.badge && (
                        <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                      )}
                    </button>
                  ))}
                </div>
              )}

              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-text-muted hover:text-text-primary
                           hover:bg-dark-elevated transition-colors shrink-0 ml-2"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Content — MapView stays mounted to preserve GL context */}
            <div className="flex-1 overflow-hidden min-h-0 relative">
              <div
                className="absolute inset-0"
                style={{ display: activeView === "map" ? "block" : "none" }}
              >
                <MapView
                  mapData={mapData ?? null}
                  loading={mapLoading}
                  sources={mapSources}
                  intent={mapIntent}
                  parcelGeometry={context?.property?.parcel_geometry}
                  hasTransitContext={!!context?.neighborhood?.transit}
                  isMobile
                />
              </div>

              {activeView === "data" && (
                <div className="h-full overflow-y-auto px-4 py-3">
                  <DataView
                    context={context}
                    loading={loading}
                    mapData={mapData}
                    filterMode={deriveFilterMode(mapSources)}
                  />
                </div>
              )}

              {activeView === "sources" && (
                <div className="h-full overflow-y-auto p-4">
                  <SourcesView
                    codeChunks={context?.code_chunks ?? []}
                    highlightedIndex={highlightedSourceIndex}
                    flashSignal={sourceFlashSignal}
                    onSourceClick={onSourceClick}
                    onCrossRefClick={onCrossRefClick}
                  />
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
