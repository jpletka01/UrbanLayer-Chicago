import { useState } from "react";
import type { CodeChunk } from "../lib/types";

interface Props {
  index: number;
  chunk?: CodeChunk;
  onClick?: (index: number) => void;
}

export function CitationPill({ index, chunk, onClick }: Props) {
  const [showTooltip, setShowTooltip] = useState(false);

  const sectionLabel = chunk?.section ?? `Source ${index + 1}`;
  const preview = chunk?.text?.slice(0, 150) ?? "";

  return (
    <span className="relative inline-block align-baseline">
      <button
        onClick={() => onClick?.(index)}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className="inline-flex items-center gap-1 h-5 px-1.5 mx-0.5
                   text-xs font-medium rounded-md
                   bg-accent/20 text-accent border border-accent/30
                   hover:bg-accent/30 hover:border-accent/50
                   transition-colors cursor-pointer"
        title={sectionLabel}
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        {index + 1}
      </button>
      {showTooltip && chunk && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50
                        w-72 p-3 rounded-lg
                        bg-dark-surface border border-dark-border shadow-xl
                        pointer-events-none">
          <div className="text-xs font-medium text-accent mb-1 truncate">
            {sectionLabel}
          </div>
          {chunk.section_title && (
            <div className="text-xs text-text-secondary mb-2 truncate">
              {chunk.section_title}
            </div>
          )}
          <div className="text-xs text-text-muted leading-relaxed overflow-hidden" style={{ display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>
            {preview}{preview.length >= 150 ? "..." : ""}
          </div>
          <div className="text-xs text-accent/70 mt-2 flex items-center gap-1">
            <span>Click to view full source</span>
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </div>
        </div>
      )}
    </span>
  );
}
