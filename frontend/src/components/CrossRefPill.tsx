import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { fetchSection } from "../lib/api";
import { stripHeader } from "../lib/codeRefs";
import type { CodeChunk } from "../lib/types";
import { Tooltip } from "./Tooltip";

interface Props {
  sectionId: string;
  onClick?: (sectionId: string) => void;
}

type Preview =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; chunk: CodeChunk }
  | { status: "missing" };

export function CrossRefPill({ sectionId, onClick }: Props) {
  const { t } = useTranslation("chat");
  const [showTooltip, setShowTooltip] = useState(false);
  const [preview, setPreview] = useState<Preview>({ status: "idle" });
  const loadedRef = useRef(false);

  const handleEnter = () => {
    setShowTooltip(true);
    if (loadedRef.current) return;
    loadedRef.current = true;
    setPreview({ status: "loading" });
    fetchSection(sectionId).then((chunk) =>
      setPreview(chunk ? { status: "ok", chunk } : { status: "missing" })
    );
  };

  const previewText =
    preview.status === "ok" ? stripHeader(preview.chunk.text).slice(0, 160) : "";

  return (
    <span className="relative inline-block">
      <button
        onClick={(e) => {
          e.stopPropagation();
          onClick?.(sectionId);
        }}
        onMouseEnter={handleEnter}
        onMouseLeave={() => setShowTooltip(false)}
        className="inline-flex items-center gap-1 text-caption font-mono text-accent bg-accent/10 px-2 py-0.5 rounded-md border border-accent/20 hover:bg-accent/20 hover:border-accent/40 transition-colors"
        title={t("crossref.view", { id: sectionId })}
      >
        § {sectionId}
        <svg className="w-3 h-3 opacity-70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
        </svg>
      </button>
      {showTooltip && (
        <Tooltip className="w-64 p-3 rounded-lg shadow-2xl text-left">
          <div className="text-caption font-mono font-medium text-accent mb-1">§&nbsp;{sectionId}</div>
          {preview.status === "loading" && (
            <div className="text-caption text-text-muted">{t("crossref.loading")}</div>
          )}
          {preview.status === "missing" && (
            <div className="text-caption text-text-muted">{t("crossref.unavailable")}</div>
          )}
          {preview.status === "ok" && (
            <>
              {preview.chunk.section_title && (
                <div className="text-caption text-text-secondary mb-1.5 truncate">
                  {preview.chunk.section_title}
                </div>
              )}
              <div
                className="text-caption text-text-muted leading-relaxed overflow-hidden"
                style={{ display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical" }}
              >
                {previewText}…
              </div>
              <div className="text-caption text-accent/70 mt-2 flex items-center gap-1">
                <span>{t("crossref.openSection")}</span>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </div>
            </>
          )}
        </Tooltip>
      )}
    </span>
  );
}
