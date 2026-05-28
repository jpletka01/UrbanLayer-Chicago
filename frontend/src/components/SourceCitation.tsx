import type { CodeChunk } from "../lib/types";

interface Props {
  chunk: CodeChunk;
}

export function SourceCitation({ chunk }: Props) {
  const pct = Math.round(chunk.score * 100);
  return (
    <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-sm space-y-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-bold tracking-wider text-slate-400 uppercase">
          Qdrant Vector Match
        </span>
        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          {pct}% match
        </span>
      </div>
      <h4 className="text-sm font-bold text-slate-900">
        § {chunk.section} — {chunk.section_title}
      </h4>
      <p className="text-xs text-slate-600 font-mono bg-slate-50 p-2 rounded max-h-32 overflow-y-auto whitespace-pre-wrap">
        {chunk.text.slice(0, 600)}
        {chunk.text.length > 600 ? "…" : ""}
      </p>
    </div>
  );
}
