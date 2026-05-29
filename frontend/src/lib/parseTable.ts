export interface ParsedTableRow {
  type: "data";
  index: number;
  cells: string[];
}

export interface ParsedTableSubheader {
  type: "subheader";
  label: string;
}

export interface ParsedTableAllColumns {
  type: "all-columns";
  index: number;
  value: string;
}

export type ParsedTableEntry =
  | ParsedTableRow
  | ParsedTableSubheader
  | ParsedTableAllColumns;

export interface ParsedTable {
  headers: string[];
  entries: ParsedTableEntry[];
}

export interface TextSegment {
  type: "prose";
  text: string;
}

export interface TableSegment {
  type: "table";
  table: ParsedTable;
}

export type ChunkSegment = TextSegment | TableSegment;

const ROW_RE = /^Row (\d+): (.+)$/;
const ROW_ALL_RE = /^Row (\d+) \(all columns\): (.+)$/;
const SECTION_RE = /^Section: (.+)$/;
const COLUMNS_RE = /^Columns: (.+)$/;

function parseRowCells(content: string, headers: string[]): string[] {
  if (headers.length === 0) return [content];

  const cells: string[] = new Array(headers.length).fill("");
  let remaining = content;
  let i = 0;

  // Find the first header that starts the content
  while (i < headers.length) {
    if (remaining.startsWith(headers[i] + ": ")) break;
    i++;
  }

  while (i < headers.length && remaining.length > 0) {
    const prefix = headers[i] + ": ";
    if (!remaining.startsWith(prefix)) {
      i++;
      continue;
    }

    remaining = remaining.slice(prefix.length);

    // Find the earliest occurrence of any remaining header as a separator
    let bestSepIdx = -1;
    let bestHeaderIdx = -1;

    for (let j = i + 1; j < headers.length; j++) {
      const sep = "; " + headers[j] + ": ";
      const idx = remaining.indexOf(sep);
      if (idx !== -1 && (bestSepIdx === -1 || idx < bestSepIdx)) {
        bestSepIdx = idx;
        bestHeaderIdx = j;
      }
    }

    if (bestSepIdx !== -1) {
      cells[i] = remaining.slice(0, bestSepIdx);
      remaining = remaining.slice(bestSepIdx + 2); // skip "; "
      i = bestHeaderIdx;
    } else {
      cells[i] = remaining;
      remaining = "";
    }
  }

  return cells;
}

function parseTableBlock(block: string): ParsedTable {
  const lines = block.split("\n");
  let headers: string[] = [];
  const entries: ParsedTableEntry[] = [];

  for (const line of lines) {
    const colMatch = line.match(COLUMNS_RE);
    if (colMatch) {
      headers = colMatch[1].split(" | ");
      continue;
    }

    const secMatch = line.match(SECTION_RE);
    if (secMatch) {
      entries.push({ type: "subheader", label: secMatch[1] });
      continue;
    }

    const allMatch = line.match(ROW_ALL_RE);
    if (allMatch) {
      entries.push({
        type: "all-columns",
        index: parseInt(allMatch[1], 10),
        value: allMatch[2],
      });
      continue;
    }

    const rowMatch = line.match(ROW_RE);
    if (rowMatch) {
      const cells = parseRowCells(rowMatch[2], headers);
      entries.push({
        type: "data",
        index: parseInt(rowMatch[1], 10),
        cells,
      });
    }
  }

  return { headers, entries };
}

export function parseChunkText(text: string): ChunkSegment[] {
  const segments: ChunkSegment[] = [];
  const parts = text.split(/\[TABLE\]\n/);

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    if (i === 0) {
      const trimmed = part.trimEnd();
      if (trimmed) {
        segments.push({ type: "prose", text: trimmed });
      }
      continue;
    }

    const nextTableIdx = part.indexOf("\n\n[TABLE]");
    let tableText: string;
    let trailing: string;

    if (nextTableIdx !== -1) {
      tableText = part.slice(0, nextTableIdx);
      trailing = part.slice(nextTableIdx + 2);
    } else {
      const blankLine = part.indexOf("\n\n");
      if (blankLine !== -1 && !part.slice(blankLine + 2).match(/^(Columns:|Section:|Row \d)/m)) {
        tableText = part.slice(0, blankLine);
        trailing = part.slice(blankLine + 2);
      } else {
        tableText = part;
        trailing = "";
      }
    }

    const table = parseTableBlock(tableText);
    if (table.entries.length > 0) {
      segments.push({ type: "table", table });
    } else {
      segments.push({ type: "prose", text: tableText.trim() });
    }

    const trimmedTrailing = trailing.trimEnd();
    if (trimmedTrailing) {
      segments.push({ type: "prose", text: trimmedTrailing });
    }
  }

  return segments;
}

export function shortenHeader(header: string): string {
  const parts = header.split(" - ");
  return parts[parts.length - 1];
}
