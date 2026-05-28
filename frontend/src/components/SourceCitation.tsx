import { AnimatePresence, motion } from "motion/react";
import { forwardRef, useState } from "react";
import { copyToClipboard } from "../lib/clipboard";
import type { CodeChunk } from "../lib/types";

interface Props {
  chunk: CodeChunk;
  index: number;
  highlighted?: boolean;
  expanded?: boolean;
  onToggleExpand?: () => void;
}

export const SourceCitation = forwardRef<HTMLDivElement, Props>(
  function SourceCitation({ chunk, index, highlighted, expanded, onToggleExpand }, ref) {
    const pct = Math.round(chunk.score * 100);
    const [copied, setCopied] = useState(false);

    const handleCopy = async (e: React.MouseEvent) => {
      e.stopPropagation();
      const success = await copyToClipboard(chunk.text);
      if (success) {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    };

    return (
      <div
        ref={ref}
        onClick={onToggleExpand}
        className={`rounded-xl bg-dark-surface/80 border p-3 cursor-pointer
                    hover:bg-dark-surface transition-all group
                    ${highlighted
                      ? "border-accent/50 ring-1 ring-accent/30"
                      : "border-dark-border hover:border-dark-border/80"
                    }`}
      >
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-5 h-5 rounded-md bg-accent/20 text-accent text-xs font-medium flex items-center justify-center shrink-0">
                {index + 1}
              </span>
              <h4 className="text-sm font-medium text-text-primary truncate">
                {chunk.section}
              </h4>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={handleCopy}
                className={`p-1 rounded text-text-muted hover:text-text-primary hover:bg-dark-elevated transition-all
                           ${expanded ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}
                title="Copy text"
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
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                pct >= 85
                  ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
                  : pct >= 70
                  ? "bg-amber-500/15 text-amber-400 border border-amber-500/20"
                  : "bg-dark-elevated text-text-muted border border-dark-border"
              }`}>
                {pct}%
              </span>
            </div>
          </div>
          <p className="text-xs text-text-secondary leading-relaxed">
            {chunk.section_title}
          </p>

          <AnimatePresence initial={false}>
            {expanded ? (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2, ease: "easeInOut" }}
                className="overflow-hidden"
              >
                <div className="space-y-3 pt-1">
                  <div className="flex items-center gap-3 text-xs">
                    <span className="text-text-muted">Source:</span>
                    <span className="text-text-secondary font-mono bg-dark-bg/50 px-2 py-0.5 rounded">
                      {chunk.source_document}
                    </span>
                  </div>

                  {chunk.cross_references.length > 0 && (
                    <div className="p-2 rounded-lg bg-dark-bg/30 border border-dark-border/50">
                      <p className="text-xs text-text-muted mb-2">Cross-references:</p>
                      <div className="flex flex-wrap gap-1.5">
                        {chunk.cross_references.map((xref, i) => (
                          <span
                            key={i}
                            className="text-xs text-accent bg-accent/10 px-2 py-0.5 rounded border border-accent/20"
                          >
                            {xref}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="text-xs text-text-primary font-mono bg-dark-bg/50 p-3 rounded-lg border border-dark-border/50 max-h-80 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                    {chunk.text}
                  </div>

                  <div className="flex items-center justify-center pt-1">
                    <span className="flex items-center gap-1 text-xs text-accent/70">
                      <svg className="w-3 h-3 rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      Click to collapse
                    </span>
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2, ease: "easeInOut" }}
              >
                <div className="text-xs text-text-muted font-mono bg-dark-bg/50 p-2 rounded-lg max-h-24 overflow-hidden whitespace-pre-wrap">
                  {chunk.text.slice(0, 400)}
                  {chunk.text.length > 400 ? "..." : ""}
                </div>
                {chunk.cross_references.length > 0 && (
                  <div className="flex items-center gap-2 pt-2">
                    <span className="text-xs text-text-muted">Refs:</span>
                    <div className="flex flex-wrap gap-1">
                      {chunk.cross_references.slice(0, 3).map((xref, i) => (
                        <span
                          key={i}
                          className="text-xs text-accent/80 bg-accent/10 px-1.5 py-0.5 rounded"
                        >
                          {xref}
                        </span>
                      ))}
                      {chunk.cross_references.length > 3 && (
                        <span className="text-xs text-text-muted">
                          +{chunk.cross_references.length - 3}
                        </span>
                      )}
                    </div>
                  </div>
                )}
                <div className="flex items-center justify-between pt-2 text-xs text-text-muted">
                  <span className="font-mono truncate max-w-[70%]">{chunk.source_document}</span>
                  <span className="flex items-center gap-1 text-accent/70">
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                    Expand
                  </span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    );
  }
);
