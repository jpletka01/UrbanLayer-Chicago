import { createRef, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { SOURCE_FLASH_MS } from "../../lib/constants";
import type { CodeChunk } from "../../lib/types";
import { SourceCitation } from "../SourceCitation";

interface Props {
  codeChunks: CodeChunk[];
  highlightedIndex?: number | null;
  flashSignal?: number;
  onSourceClick?: (index: number) => void;
  onCrossRefClick?: (sectionId: string) => void;
}

export function SourcesView({
  codeChunks,
  highlightedIndex,
  flashSignal,
  onSourceClick,
  onCrossRefClick,
}: Props) {
  const { t } = useTranslation("sidebar");
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [flashingIndex, setFlashingIndex] = useState<number | null>(null);
  const flashTimer = useRef<number | null>(null);

  const refs = useMemo(
    () => codeChunks.map(() => createRef<HTMLDivElement>()),
    [codeChunks.length]
  );

  // When a citation in the chat is clicked, App bumps `flashSignal` and sets
  // `highlightedIndex`. Open the matching source to full size, scroll it into
  // view, and flash it briefly. Keyed on flashSignal too, so re-clicking the
  // same citation re-triggers the flash.
  useEffect(() => {
    if (highlightedIndex === null || highlightedIndex === undefined) return;
    setExpandedIndex(highlightedIndex);
    refs[highlightedIndex]?.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlashingIndex(highlightedIndex);
    if (flashTimer.current) window.clearTimeout(flashTimer.current);
    flashTimer.current = window.setTimeout(() => setFlashingIndex(null), SOURCE_FLASH_MS);
    return () => {
      if (flashTimer.current) window.clearTimeout(flashTimer.current);
    };
  }, [highlightedIndex, flashSignal, refs]);

  if (codeChunks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-center">
        <div className="w-12 h-12 rounded-xl bg-dark-surface flex items-center justify-center mb-3">
          <svg
            className="w-6 h-6 text-text-muted"
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
        </div>
        <p className="text-sm text-text-muted">{t("noCodeRefs")}</p>
        <p className="text-xs text-text-muted mt-1">
          {t("noCodeRefsHint")}
        </p>
      </div>
    );
  }

  const handleToggleExpand = (index: number) => {
    onSourceClick?.(index);
    setExpandedIndex((prev) => (prev === index ? null : index));
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-text-muted mb-4">
        {t("sectionsReferenced", { count: codeChunks.length })}
      </p>
      {codeChunks.map((chunk, i) => (
        <SourceCitation
          key={`${chunk.section}-${chunk.subsection ?? ""}-${i}`}
          ref={refs[i]}
          chunk={chunk}
          index={i}
          highlighted={highlightedIndex === i}
          flashing={flashingIndex === i}
          expanded={expandedIndex === i}
          onToggleExpand={() => handleToggleExpand(i)}
          onCrossRefClick={onCrossRefClick}
        />
      ))}
    </div>
  );
}
