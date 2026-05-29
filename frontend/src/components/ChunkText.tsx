import { useMemo } from "react";
import { parseChunkText } from "../lib/parseTable";
import { ChunkTable } from "./ChunkTable";

interface Props {
  text: string;
  className?: string;
}

export function ChunkText({ text, className }: Props) {
  const segments = useMemo(() => parseChunkText(text), [text]);

  const hasTable = segments.some((s) => s.type === "table");
  if (!hasTable) {
    return (
      <div className={className} style={{ whiteSpace: "pre-wrap" }}>
        {text}
      </div>
    );
  }

  return (
    <div className={className}>
      {segments.map((seg, i) =>
        seg.type === "prose" ? (
          <div key={i} style={{ whiteSpace: "pre-wrap" }}>
            {seg.text}
          </div>
        ) : (
          <ChunkTable key={i} table={seg.table} />
        )
      )}
    </div>
  );
}
