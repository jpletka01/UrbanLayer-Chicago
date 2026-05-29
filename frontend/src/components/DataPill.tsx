import { useState } from "react";
import type { DataSource } from "../lib/types";
import { Tooltip } from "./Tooltip";

interface Props {
  source: DataSource;
  onClick?: (source: DataSource) => void;
}

const SOURCE_CONFIG: Record<DataSource, { label: string; icon: string; color: string }> = {
  crime: {
    label: "Crime Data",
    icon: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z",
    color: "rose",
  },
  "311": {
    label: "311 Requests",
    icon: "M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z",
    color: "amber",
  },
  permits: {
    label: "Building Permits",
    icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
    color: "sky",
  },
  violations: {
    label: "Building Violations",
    icon: "M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    color: "orange",
  },
  business: {
    label: "Business Licenses",
    icon: "M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
    color: "emerald",
  },
};

const COLOR_CLASSES: Record<string, { bg: string; text: string; border: string }> = {
  rose: { bg: "bg-rose-500/15", text: "text-rose-400", border: "border-rose-500/30" },
  amber: { bg: "bg-amber-500/15", text: "text-amber-400", border: "border-amber-500/30" },
  sky: { bg: "bg-sky-500/15", text: "text-sky-400", border: "border-sky-500/30" },
  orange: { bg: "bg-orange-500/15", text: "text-orange-400", border: "border-orange-500/30" },
  emerald: { bg: "bg-emerald-500/15", text: "text-emerald-400", border: "border-emerald-500/30" },
};

export function DataPill({ source, onClick }: Props) {
  const [showTooltip, setShowTooltip] = useState(false);
  const config = SOURCE_CONFIG[source];
  const colors = COLOR_CLASSES[config.color];

  return (
    <span className="relative inline-block align-baseline">
      <button
        onClick={() => onClick?.(source)}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className={`inline-flex items-center gap-1 h-5 px-1.5 mx-0.5
                   text-xs font-medium rounded-md
                   ${colors.bg} ${colors.text} border ${colors.border}
                   hover:brightness-110 transition-all cursor-pointer`}
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d={config.icon} />
        </svg>
      </button>
      {showTooltip && (
        <Tooltip className="px-2 py-1 rounded-md whitespace-nowrap shadow-xl">
          <div className={`text-xs font-medium ${colors.text}`}>
            {config.label}
          </div>
          <div className="text-xs text-text-muted">
            Chicago Data Portal
          </div>
        </Tooltip>
      )}
    </span>
  );
}
