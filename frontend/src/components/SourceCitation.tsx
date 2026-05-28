import type { CodeChunk } from "../lib/types";

interface Props {
  chunk: CodeChunk;
}

export function SourceCitation({ chunk }: Props) {
  const pct = Math.round(chunk.score * 100);
  return (
    <div className="rounded-xl bg-dark-surface/80 border border-dark-border p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-medium text-text-primary truncate">
          {chunk.section}
        </h4>
        <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${
          pct >= 85
            ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
            : pct >= 70
            ? "bg-amber-500/15 text-amber-400 border border-amber-500/20"
            : "bg-dark-elevated text-text-muted border border-dark-border"
        }`}>
          {pct}%
        </span>
      </div>
      <p className="text-xs text-text-secondary leading-relaxed">
        {chunk.section_title}
      </p>
      <div className="text-xs text-text-muted font-mono bg-dark-bg/50 p-2 rounded-lg max-h-24 overflow-y-auto whitespace-pre-wrap">
        {chunk.text.slice(0, 400)}
        {chunk.text.length > 400 ? "..." : ""}
      </div>
    </div>
  );
}
