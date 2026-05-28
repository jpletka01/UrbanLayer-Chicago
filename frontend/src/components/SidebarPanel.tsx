import { motion } from "motion/react";
import type { ContextObject, PhaseTimings, RetrievalPlan, SidebarView } from "../lib/types";
import { SidebarHeader } from "./SidebarHeader";
import { SidebarToggle } from "./SidebarToggle";
import { DataView } from "./sidebar/DataView";
import { SourcesView } from "./sidebar/SourcesView";

interface Props {
  plan: RetrievalPlan | null;
  context: ContextObject | null;
  loading: boolean;
  timings?: PhaseTimings;
  isOpen: boolean;
  onToggle: () => void;
  activeView: SidebarView;
  onViewChange: (view: SidebarView) => void;
}

export function SidebarPanel({
  plan,
  context,
  loading,
  timings,
  isOpen,
  onToggle,
  activeView,
  onViewChange,
}: Props) {
  const title = context?.community_area_name ?? "Context & Data";
  const subtitle = context?.community_area ? `CA ${context.community_area}` : undefined;
  const hasCodeChunks = (context?.code_chunks?.length ?? 0) > 0;

  return (
    <motion.aside
      initial={false}
      animate={{
        width: isOpen ? "40%" : "0%",
      }}
      transition={{ duration: 0.3, ease: "easeInOut" }}
      className="relative hidden md:flex flex-col h-full bg-dark-bg border-l border-dark-border overflow-hidden"
    >
      <SidebarToggle isOpen={isOpen} onToggle={onToggle} />

      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2, delay: 0.1 }}
          className="flex flex-col h-full min-w-0"
        >
          <SidebarHeader
            title={title}
            subtitle={subtitle}
            activeView={activeView}
            onViewChange={onViewChange}
            hasCodeChunks={hasCodeChunks}
          />

          <div className="flex-1 overflow-y-auto p-4">
            {activeView === "data" ? (
              <DataView
                plan={plan}
                context={context}
                loading={loading}
                timings={timings}
              />
            ) : (
              <SourcesView codeChunks={context?.code_chunks ?? []} />
            )}
          </div>
        </motion.div>
      )}
    </motion.aside>
  );
}
