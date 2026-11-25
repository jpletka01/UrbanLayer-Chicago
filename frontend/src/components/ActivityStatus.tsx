import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import type { ActivityItem } from "../lib/types";

interface Props {
  activities: ActivityItem[];
  visible: boolean;
}

export function ActivityStatus({ activities, visible }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [cycleIndex, setCycleIndex] = useState(0);
  const lastLabelRef = useRef("Analyzing your question…");

  const activeItems = activities.filter((a) => a.status === "active");

  let currentLabel: string;
  if (activeItems.length > 0) {
    currentLabel = activeItems[cycleIndex % activeItems.length].label;
    lastLabelRef.current = currentLabel;
  } else {
    currentLabel = lastLabelRef.current;
  }

  useEffect(() => {
    if (activeItems.length <= 1) {
      setCycleIndex(0);
      return;
    }
    const t = setInterval(() => setCycleIndex((i) => i + 1), 1200);
    return () => clearInterval(t);
  }, [activeItems.length]);

  const activeIdsKey = activeItems.map((a) => a.id).join(",");
  const prevActiveIdsRef = useRef(activeIdsKey);
  useEffect(() => {
    if (activeIdsKey !== prevActiveIdsRef.current) {
      setCycleIndex(0);
      prevActiveIdsRef.current = activeIdsKey;
    }
  }, [activeIdsKey]);

  useEffect(() => {
    if (!visible) {
      const t = setTimeout(() => setHidden(true), 350);
      return () => clearTimeout(t);
    }
    setHidden(false);
  }, [visible]);

  if (hidden || activities.length === 0) return null;

  return (
    <div
      className={`mt-2 pl-9 transition-all duration-300 ${
        visible ? "opacity-100" : "opacity-0 -translate-y-1"
      }`}
    >
      <button
        type="button"
        onClick={() => visible && setExpanded((e) => !e)}
        className="flex items-center gap-1.5 group/activity"
      >
        <svg
          className={`w-3 h-3 text-text-muted group-hover/activity:text-text-secondary transition-transform duration-200 ${
            expanded ? "rotate-90" : ""
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        <span
          key={currentLabel}
          className="text-xs text-text-muted animate-text-glow"
        >
          {currentLabel}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="mt-1.5 ml-1 pl-3 border-l border-dark-border space-y-1.5 py-1">
              {activities.map((a) => (
                <div key={a.id} className="flex items-center gap-2 text-xs">
                  {a.status === "done" ? (
                    <span className="w-4 h-4 rounded-full bg-state-positive/20 flex items-center justify-center shrink-0">
                      <svg className="w-2.5 h-2.5 text-state-positive" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </span>
                  ) : (
                    <span className="w-4 h-4 rounded-full border-2 border-text-muted/30 border-t-accent animate-spin shrink-0" />
                  )}
                  <span className={a.status === "done" ? "text-text-muted" : "text-text-secondary"}>
                    {a.label}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
