import { useState } from "react";
import { useTranslation } from "react-i18next";
import { stripHeader } from "../lib/codeRefs";
import type { CodeChunk } from "../lib/types";
import { Tooltip } from "./Tooltip";

interface Props {
  index: number;
  chunk?: CodeChunk;
  onClick?: (index: number) => void;
}

export function CitationPill({ index, chunk, onClick }: Props) {
  const { t } = useTranslation("chat");
  const [showTooltip, setShowTooltip] = useState(false);

  const reference = chunk?.section ? `§ ${chunk.section}` : t("citation.sourceN", { n: index + 1 });
  const preview = chunk ? stripHeader(chunk.text).slice(0, 150) : "";

  return (
    <span className="relative inline-block align-baseline">
      <button
        onClick={() => onClick?.(index)}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className="inline-flex items-center gap-0.5 h-5 px-1.5 mx-0.5
                   text-caption font-mono font-medium rounded-md
                   bg-accent/15 text-accent border border-accent/30
                   hover:bg-accent/25 hover:border-accent/50
                   transition-colors cursor-pointer align-baseline"
        title={t("citation.view", { ref: reference })}
      >
        {reference}
        <span className="self-start text-micro font-sans font-bold leading-none mt-0.5">
          {index + 1}
        </span>
      </button>
      {showTooltip && chunk && (
        <Tooltip className="w-72 p-3 rounded-lg shadow-2xl">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="w-4 h-4 rounded-full bg-accent text-dark-bg text-micro font-bold flex items-center justify-center tabular-nums">
              {index + 1}
            </span>
            <span className="text-caption font-mono font-medium text-accent truncate">
              §&nbsp;{chunk.section}
            </span>
          </div>
          {chunk.section_title && (
            <div className="text-caption text-text-secondary mb-2 truncate">
              {chunk.section_title}
            </div>
          )}
          <div className="text-caption text-text-muted leading-relaxed overflow-hidden" style={{ display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>
            {preview}{preview.length >= 150 ? "..." : ""}
          </div>
          <div className="text-caption text-accent/70 mt-2 flex items-center gap-1">
            <span>{t("citation.openSource")}</span>
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </div>
        </Tooltip>
      )}
    </span>
  );
}
