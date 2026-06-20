import type { ParsedTable, ParsedTableEntry } from "../lib/parseTable";
import { shortenHeader } from "../lib/parseTable";

interface Props {
  table: ParsedTable;
}

function EntryRow({ entry, colCount }: { entry: ParsedTableEntry; colCount: number }) {
  switch (entry.type) {
    case "subheader":
      return (
        <tr>
          <td
            colSpan={colCount}
            className="px-3 py-2 text-caption font-semibold text-accent bg-accent/8 border-t border-dark-border"
          >
            {entry.label}
          </td>
        </tr>
      );
    case "all-columns":
      return (
        <tr>
          <td
            colSpan={colCount}
            className="px-3 py-1.5 text-caption text-text-secondary bg-dark-elevated/40 border-t border-dark-border/50 italic"
          >
            {entry.value}
          </td>
        </tr>
      );
    case "data":
      return (
        <tr className="hover:bg-dark-elevated/30 transition-colors">
          {entry.cells.map((cell, i) => (
            <td
              key={i}
              className="px-3 py-1.5 text-caption text-text-secondary border-t border-dark-border/50 align-top"
            >
              {cell || <span className="text-text-muted">—</span>}
            </td>
          ))}
          {entry.cells.length < colCount &&
            Array.from({ length: colCount - entry.cells.length }).map((_, i) => (
              <td
                key={`pad-${i}`}
                className="px-3 py-1.5 text-caption border-t border-dark-border/50"
              />
            ))}
        </tr>
      );
  }
}

export function ChunkTable({ table }: Props) {
  const colCount = table.headers.length || 1;

  return (
    <div className="overflow-x-auto rounded-lg border border-dark-border/50 my-2">
      <table className="w-full text-left border-collapse min-w-[400px]">
        {table.headers.length > 0 && (
          <thead>
            <tr className="bg-dark-elevated/60">
              {table.headers.map((h, i) => (
                <th
                  key={i}
                  className="px-3 py-2 text-micro font-semibold text-text-primary uppercase tracking-wider whitespace-nowrap"
                  title={h}
                >
                  {shortenHeader(h)}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {table.entries.map((entry, i) => (
            <EntryRow key={i} entry={entry} colCount={colCount} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
