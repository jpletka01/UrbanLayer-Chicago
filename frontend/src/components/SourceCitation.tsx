import { AnimatePresence, motion } from "motion/react";
import { forwardRef } from "react";
import { isResolvableSection, stripHeader } from "../lib/codeRefs";
import type { CodeChunk } from "../lib/types";
import { useCopyButton } from "../lib/useCopyButton";
import { CrossRefPill } from "./CrossRefPill";

interface Props {
  chunk: CodeChunk;
  index: number;
  highlighted?: boolean;
  flashing?: boolean;
  expanded?: boolean;
  onToggleExpand?: () => void;
  onCrossRefClick?: (sectionId: string) => void;
}

function ScorePill({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const tone =
    pct >= 85
      ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/20"
      : pct >= 70
      ? "bg-amber-500/15 text-amber-400 border-amber-500/20"
      : "bg-dark-elevated text-text-muted border-dark-border";
  return (
    <span
      className={`px-1.5 py-0.5 rounded text-[10px] font-medium border tabular-nums ${tone}`}
      title="Semantic match score"
    >
      {pct}%
    </span>
  );
}

export const SourceCitation = forwardRef<HTMLDivElement, Props>(
  function SourceCitation(
    { chunk, index, highlighted, flashing, expanded, onToggleExpand, onCrossRefClick },
    ref
  ) {
    const { copied, copy } = useCopyButton(chunk.text);
    const preview = stripHeader(chunk.text);

    const handleCopy = (e: React.MouseEvent) => {
      e.stopPropagation();
      copy();
    };

    return (
      <div
        ref={ref}
        onClick={onToggleExpand}
        className={`rounded-xl bg-dark-surface/80 border p-3.5 cursor-pointer
                    hover:bg-dark-surface transition-all group
                    ${flashing ? "animate-flash" : ""}
                    ${highlighted
                      ? "border-accent/50 ring-1 ring-accent/30"
                      : "border-dark-border hover:border-dark-border/80"
                    }`}
      >
        {/* Header row: rank · section pill · score · copy */}
        <div className="flex items-center gap-2.5">
          <span className="w-6 h-6 rounded-full bg-accent text-dark-bg text-xs font-bold flex items-center justify-center shrink-0 tabular-nums">
            {index + 1}
          </span>
          <span className="px-1.5 py-0.5 rounded-md bg-accent/10 text-accent text-xs font-mono font-medium border border-accent/20 shrink-0">
            § {chunk.section}
          </span>
          <div className="ml-auto flex items-center gap-2 shrink-0">
            <ScorePill score={chunk.score} />
            <button
              onClick={handleCopy}
              className={`p-1 rounded text-text-muted hover:text-text-primary hover:bg-dark-elevated transition-all
                         ${expanded ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}
              title="Copy full text"
            >
              {copied ? (
                <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Title */}
        {chunk.section_title && (
          <h4 className="mt-2 text-sm font-medium text-text-primary leading-snug">
            {chunk.section_title}
          </h4>
        )}

        {/* Preview (collapsed) — plain prose, not a dense mono block */}
        {!expanded && (
          <p className="mt-1.5 text-xs text-text-muted leading-relaxed line-clamp-2">
            {preview}
          </p>
        )}

        <AnimatePresence initial={false}>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: "easeInOut" }}
              className="overflow-hidden"
            >
              <div className="space-y-3 pt-3">
                <div className="text-[13px] text-text-secondary font-mono bg-dark-bg/50 p-3 rounded-lg border border-dark-border/50 whitespace-pre-wrap leading-relaxed">
                  {chunk.text}
                </div>

                {chunk.cross_references.length > 0 && (
                  <div>
                    <p className="text-[11px] uppercase tracking-wider text-text-muted mb-1.5">
                      Related sections
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {chunk.cross_references.map((xref, i) =>
                        isResolvableSection(xref) ? (
                          <CrossRefPill key={i} sectionId={xref.trim()} onClick={onCrossRefClick} />
                        ) : (
                          <span
                            key={i}
                            className="text-xs font-mono text-text-muted bg-dark-bg/40 px-2 py-0.5 rounded border border-dark-border/50"
                          >
                            {xref}
                          </span>
                        )
                      )}
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-2 text-[11px] text-text-muted">
                  <span>Source:</span>
                  <span className="font-mono">{chunk.source_document}</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Expand / collapse affordance */}
        <div className="flex items-center gap-1 pt-2 text-[11px] text-accent/70">
          <svg
            className={`w-3 h-3 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
          {expanded ? "Collapse" : "Read full text"}
        </div>
      </div>
    );
  }
);
