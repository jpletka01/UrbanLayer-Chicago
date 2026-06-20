import { AnimatePresence, motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { isResolvableSection } from "../lib/codeRefs";
import type { CodeChunk } from "../lib/types";
import { useCopyButton } from "../lib/useCopyButton";
import { ChunkText } from "./ChunkText";
import { CrossRefPill } from "./CrossRefPill";

export interface SectionView {
  loading: boolean;
  chunk: CodeChunk | null;
}

interface Props {
  view: SectionView | null;
  onClose: () => void;
  onCrossRefClick?: (sectionId: string) => void;
}

export function SourceDetailDrawer({ view, onClose, onCrossRefClick }: Props) {
  const { t } = useTranslation("sidebar");
  const chunk = view?.chunk ?? null;
  const { copied, copy } = useCopyButton(chunk?.text ?? "");

  return (
    <AnimatePresence>
      {view && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 w-full max-w-lg bg-dark-surface border-l border-dark-border shadow-2xl z-50 flex flex-col"
          >
            <div className="flex items-start justify-between p-4 border-b border-dark-border gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <svg className="w-4 h-4 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
                  </svg>
                  <span className="text-xs font-medium text-text-muted uppercase tracking-wider">
                    {t("municipalCode")}
                  </span>
                </div>
                {chunk ? (
                  <>
                    <span className="inline-block px-1.5 py-0.5 rounded-md bg-accent/10 text-accent text-xs font-mono font-medium border border-accent/20">
                      § {chunk.section}
                    </span>
                    {chunk.section_title && (
                      <h2 className="mt-1.5 text-base font-semibold text-text-primary leading-snug">
                        {chunk.section_title}
                      </h2>
                    )}
                  </>
                ) : (
                  <h2 className="text-base font-semibold text-text-primary">
                    {view.loading ? t("loadingSection") : t("sectionNotFound")}
                  </h2>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {chunk && (
                  <button
                    onClick={copy}
                    className="p-2 rounded-lg bg-dark-surface border border-dark-border
                               text-text-muted hover:text-text-primary hover:bg-dark-elevated transition-all"
                    title={t("copyFullText")}
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
                )}
                <button
                  onClick={onClose}
                  className="p-2 rounded-lg bg-dark-surface border border-dark-border
                             text-text-muted hover:text-text-primary hover:bg-dark-elevated transition-all"
                  title={t("common:close")}
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {view.loading && !chunk && (
                <div className="space-y-3">
                  <div className="h-4 w-3/4 animate-pulse bg-dark-elevated rounded" />
                  <div className="h-4 w-full animate-pulse bg-dark-elevated rounded" />
                  <div className="h-4 w-5/6 animate-pulse bg-dark-elevated rounded" />
                  <div className="h-4 w-2/3 animate-pulse bg-dark-elevated rounded" />
                </div>
              )}

              {!view.loading && !chunk && (
                <p className="text-sm text-text-muted">
                  {t("crossRefUnavailable")}
                </p>
              )}

              {chunk && (
                <>
                  <ChunkText
                    text={chunk.text}
                    className="text-sm text-text-secondary leading-relaxed font-mono bg-dark-surface p-4 rounded-lg border border-dark-border"
                  />

                  {chunk.cross_references.length > 0 && (
                    <div className="mt-4">
                      <p className="text-micro uppercase tracking-wider text-text-muted mb-1.5">
                        {t("relatedSections")}
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {chunk.cross_references.map((ref, i) =>
                          isResolvableSection(ref) ? (
                            <CrossRefPill key={i} sectionId={ref.trim()} onClick={onCrossRefClick} />
                          ) : (
                            <span
                              key={i}
                              className="text-xs font-mono text-text-muted bg-dark-elevated px-2 py-0.5 rounded border border-dark-border"
                            >
                              {ref}
                            </span>
                          )
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
