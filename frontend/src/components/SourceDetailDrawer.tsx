import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { copyToClipboard } from "../lib/clipboard";
import type { CodeChunk } from "../lib/types";

interface Props {
  chunk: CodeChunk | null;
  onClose: () => void;
}

export function SourceDetailDrawer({ chunk, onClose }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!chunk) return;
    const success = await copyToClipboard(chunk.text);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <AnimatePresence>
      {chunk && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/60 z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 w-full max-w-lg bg-dark-bg border-l border-dark-border z-50 flex flex-col"
          >
            <div className="flex items-center justify-between p-4 border-b border-dark-border">
              <div className="min-w-0 flex-1">
                <h2 className="text-lg font-semibold text-text-primary truncate">
                  {chunk.section}
                </h2>
                <p className="text-sm text-text-secondary truncate">
                  {chunk.section_title}
                </p>
              </div>
              <div className="flex items-center gap-2 ml-4">
                <button
                  onClick={handleCopy}
                  className="p-2 rounded-lg bg-dark-surface border border-dark-border
                             text-text-muted hover:text-text-primary hover:bg-dark-elevated
                             transition-all"
                  title="Copy full text"
                >
                  {copied ? (
                    <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  )}
                </button>
                <button
                  onClick={onClose}
                  className="p-2 rounded-lg bg-dark-surface border border-dark-border
                             text-text-muted hover:text-text-primary hover:bg-dark-elevated
                             transition-all"
                  title="Close"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              <div className="mb-4 flex items-center gap-3">
                <span className="text-xs text-text-muted">Source:</span>
                <span className="text-xs text-text-secondary font-mono bg-dark-surface px-2 py-1 rounded">
                  {chunk.source_document}
                </span>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                  Math.round(chunk.score * 100) >= 85
                    ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
                    : Math.round(chunk.score * 100) >= 70
                    ? "bg-amber-500/15 text-amber-400 border border-amber-500/20"
                    : "bg-dark-elevated text-text-muted border border-dark-border"
                }`}>
                  {Math.round(chunk.score * 100)}% match
                </span>
              </div>

              {chunk.cross_references.length > 0 && (
                <div className="mb-4 p-3 rounded-lg bg-dark-surface/50 border border-dark-border">
                  <p className="text-xs text-text-muted mb-2">Cross-references:</p>
                  <div className="flex flex-wrap gap-2">
                    {chunk.cross_references.map((ref, i) => (
                      <span
                        key={i}
                        className="text-xs text-accent bg-accent/10 px-2 py-1 rounded border border-accent/20"
                      >
                        {ref}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="prose prose-invert prose-sm max-w-none">
                <pre className="whitespace-pre-wrap text-sm text-text-primary leading-relaxed font-mono bg-dark-surface/30 p-4 rounded-lg border border-dark-border">
                  {chunk.text}
                </pre>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
