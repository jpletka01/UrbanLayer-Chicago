import { useEffect, useRef, useState } from "react";
import type { ActivityItem } from "../lib/types";

interface Props {
  activities: ActivityItem[];
  collapsed: boolean;
}

export function ThinkingTrace({ activities, collapsed }: Props) {
  const [hidden, setHidden] = useState(false);
  const [cycleIndex, setCycleIndex] = useState(0);
  const lastLabelRef = useRef("Thinking");

  const activeItems = activities.filter((a) => a.status === "active");

  let currentLabel: string;
  if (activeItems.length > 0) {
    currentLabel = activeItems[cycleIndex % activeItems.length].label;
    lastLabelRef.current = currentLabel;
  } else {
    currentLabel = lastLabelRef.current;
  }

  // Cycle through active items when multiple are running in parallel
  useEffect(() => {
    if (activeItems.length <= 1) {
      setCycleIndex(0);
      return;
    }
    const t = setInterval(() => setCycleIndex((i) => i + 1), 1200);
    return () => clearInterval(t);
  }, [activeItems.length]);

  // Reset cycle when the set of active items changes (e.g., routing → retrieval phase)
  const activeIdsKey = activeItems.map((a) => a.id).join(",");
  const prevActiveIdsRef = useRef(activeIdsKey);
  useEffect(() => {
    if (activeIdsKey !== prevActiveIdsRef.current) {
      setCycleIndex(0);
      prevActiveIdsRef.current = activeIdsKey;
    }
  }, [activeIdsKey]);

  useEffect(() => {
    if (collapsed) {
      const t = setTimeout(() => setHidden(true), 350);
      return () => clearTimeout(t);
    }
    setHidden(false);
  }, [collapsed]);

  if (hidden || activities.length === 0) return null;

  return (
    <div
      className={`flex items-center gap-2.5 transition-opacity duration-300 ${
        collapsed ? "opacity-0" : "opacity-100"
      }`}
    >
      <div className="flex gap-1 items-end">
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-dot-bounce" style={{ animationDelay: "0ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-dot-bounce" style={{ animationDelay: "200ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-dot-bounce" style={{ animationDelay: "400ms" }} />
      </div>
      <span key={currentLabel} className="text-sm font-medium animate-text-glow">
        {currentLabel}
      </span>
    </div>
  );
}
