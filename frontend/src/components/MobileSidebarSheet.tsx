import { useCallback, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { ContextObject, MapData, RetrievalPlan, SidebarView, SourceTag } from "../lib/types";
import { SidebarHeader } from "./SidebarHeader";
import { DataMapLayout } from "./sidebar/DataMapLayout";
import { SourcesView } from "./sidebar/SourcesView";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  plan: RetrievalPlan | null;
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
  showDataBadge?: boolean;
  showSourcesBadge?: boolean;
  dataCount?: number;
  sourceCount?: number;
}

export function MobileSidebarSheet({
  isOpen,
  onClose,
  plan,
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
  showDataBadge = false,
  showSourcesBadge = false,
  dataCount = 0,
  sourceCount = 0,
}: Props) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const dragStartY = useRef<number | null>(null);

  const title = context?.community_area_name ?? "Context & Data";
  const subtitle = context?.community_area ? `CA ${context.community_area}` : undefined;
  const hasCodeChunks = (context?.code_chunks?.length ?? 0) > 0;

  const handleDragStart = useCallback((e: React.TouchEvent) => {
    dragStartY.current = e.touches[0].clientY;
  }, []);

  const handleDragEnd = useCallback(
    (e: React.TouchEvent) => {
      if (dragStartY.current === null) return;
      const delta = e.changedTouches[0].clientY - dragStartY.current;
      if (delta > 80) onClose();
      dragStartY.current = null;
    },
    [onClose],
  );

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
            style={{ height: "70vh" }}
          >
            {/* Drag handle */}
            <div
              className="flex justify-center pt-2 pb-1 cursor-grab active:cursor-grabbing"
              onTouchStart={handleDragStart}
              onTouchEnd={handleDragEnd}
            >
              <div className="w-10 h-1 rounded-full bg-text-muted/40" />
            </div>

            {/* Header */}
            <div className="flex items-center gap-2 px-4 py-2 border-b border-dark-border shrink-0">
              <SidebarHeader
                title={title}
                subtitle={subtitle}
                activeView={activeView}
                onViewChange={onViewChange}
                hasCodeChunks={hasCodeChunks}
                dataCount={dataCount}
                sourceCount={sourceCount}
                showDataBadge={showDataBadge}
                showSourcesBadge={showSourcesBadge}
              />
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-text-muted hover:text-text-primary
                           hover:bg-dark-elevated transition-colors shrink-0"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Content */}
            {activeView === "data" ? (
              <DataMapLayout
                mapData={mapData ?? null}
                mapLoading={mapLoading}
                mapSources={mapSources}
                plan={plan}
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
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
