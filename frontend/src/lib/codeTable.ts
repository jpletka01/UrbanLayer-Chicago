// Parse the index's flattened table text ("Columns: A | B" / "Row n: A: x; B: y") back
// into columns and rows. Values may themselves contain ";" and ":", so each cell is cut
// at the next column's "Name: " marker instead of by splitting on punctuation.
export interface ParsedTable {
  columns: string[];
  rows: string[][];
}

export function parseCodeTable(text: string): ParsedTable | null {
  const lines = text.split("\n");
  const head = lines[0]?.match(/^Columns:\s*(.+)$/);
  if (!head) return null;
  const columns = head[1].split(" | ").map((c) => c.trim());
  const rows: string[][] = [];
  for (const line of lines.slice(1)) {
    const m = line.match(/^Row \d+:\s*(.*)$/);
    if (!m) continue;
    const body = m[1];
    const starts: number[] = [];
    let from = 0;
    for (const col of columns) {
      const at = body.indexOf(`${col}: `, from);
      if (at < 0) return null;
      starts.push(at);
      from = at + col.length + 2;
    }
    rows.push(columns.map((col, i) => body.slice(starts[i] + col.length + 2, i + 1 < columns.length ? starts[i + 1] : undefined).replace(/;\s*$/, "").trim()));
  }
  return rows.length ? { columns, rows } : null;
}
