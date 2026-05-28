import type { CodeChunk } from "../../lib/types";
import { SourceCitation } from "../SourceCitation";

interface Props {
  codeChunks: CodeChunk[];
}

export function SourcesView({ codeChunks }: Props) {
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
        <p className="text-sm text-text-muted">No code references found</p>
        <p className="text-xs text-text-muted mt-1">
          Ask about zoning or municipal code to see sources
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-text-muted mb-4">
        {codeChunks.length} code section{codeChunks.length !== 1 ? "s" : ""} referenced
      </p>
      {codeChunks.map((chunk) => (
        <SourceCitation key={`${chunk.section}-${chunk.subsection ?? ""}`} chunk={chunk} />
      ))}
    </div>
  );
}
