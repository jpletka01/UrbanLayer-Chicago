// The evidence panel's Sources list (Phase 8, wireframe v2 approved 2026-11-12): code and records in one numbered
// list, each shown as what it is. Code sections keep the numbers the answer cites ([1], [2] …); records follow, in a
// fixed order, only those the answer has. A code section opens on the passage the answer used, found by matching the
// answer's citing sentence against the section (shared numbers and terms weigh most); no strong match, no highlight.
import type { CodeChunk, ContextObject, DataSource, MapData, Message } from "../../lib/types";

export type RecordKind = "lot" | "facts" | "crime" | "construction" | "requests" | "violations" | "vacant" | "business" | "food";

export type SourceItem =
  | { kind: "code"; n: number; chunk: CodeChunk; passage: [number, number] | null; table: CodeTable | null }
  | { kind: RecordKind; n: number };

export interface CodeTable { header: string[]; rows: string[][]; hit: number | null }

const RECORD_ORDER: RecordKind[] = ["lot", "facts", "crime", "construction", "requests", "violations", "vacant", "business", "food"];

/** Which records an answer carries. */
export function recordsIn(ctx: ContextObject | undefined, map: MapData | undefined): RecordKind[] {
  if (!ctx) return [];
  const has: Record<RecordKind, boolean> = {
    lot: !!ctx.resolved_address && !!(ctx.property?.pin14 || ctx.parcel_zoning),
    facts: !!ctx.property,
    crime: !!ctx.crime_last_90d || (map?.crimes.length ?? 0) > 0,
    construction: !!ctx.permits || (map?.building_permits.length ?? 0) > 0,
    requests: !!ctx.open_311_requests || (map?.requests_311.length ?? 0) > 0,
    violations: !!ctx.violations,
    vacant: !!ctx.vacant_buildings,
    business: !!ctx.businesses,
    food: !!ctx.food_inspections,
  };
  return RECORD_ORDER.filter((k) => has[k]);
}

/** The answer's sources: its code sections first (numbered as cited), then its records. */
export function sourcesFor(message: Pick<Message, "content" | "context" | "mapData">): SourceItem[] {
  const ctx = message.context;
  const chunks = ctx?.code_chunks ?? [];
  const items: SourceItem[] = chunks.map((chunk, i) => {
    const sentence = citingSentence(message.content ?? "", i + 1);
    const text = chunk.text ?? "";
    const table = codeTable(text, sentence);
    return { kind: "code", n: i + 1, chunk, passage: table ? null : passageFor(text, sentence), table };
  });
  recordsIn(ctx, message.mapData).forEach((kind, i) => items.push({ kind, n: chunks.length + i + 1 }));
  return items;
}

const DATA_TO_RECORD: Record<DataSource, RecordKind> = {
  crime: "crime", "311": "requests", permits: "construction", violations: "violations",
  business: "business", vacant_buildings: "vacant", food_inspections: "food",
};

/** The source number a data citation ([data:crime] …) opens, if the answer has that record. */
export function numberForData(items: SourceItem[], source: DataSource): number | null {
  return items.find((it) => it.kind === DATA_TO_RECORD[source])?.n ?? null;
}

/** The answer's sentence carrying citation [n], without markup and citation marks. */
export function citingSentence(content: string, n: number): string | null {
  const plain = content.replace(/\*\*|__|`/g, "");
  const sentences = plain.split(/(?<=[.!?])\s+|\n+/);
  const hit = sentences.find((s) => s.includes(`[${n}]`));
  return hit ? hit.replace(/\s*\[(?:\d+|data:[a-z_0-9]+)\]/g, "").replace(/\s*[.!?]$/, "").trim() : null;
}

const STOP = new Set(["the", "and", "for", "that", "this", "with", "from", "are", "may", "shall", "lot", "its", "any", "not", "which", "than", "within", "each", "such", "into", "only", "per", "has", "have", "can", "could", "would", "also", "one"]);
function tokens(s: string): string[] {
  return (s.toLowerCase().match(/[a-z]+(?:-\d+(?:\.\d+)?)?|\d[\d,.]*/g) ?? [])
    .map((t) => t.replace(/[,.]$/, "").replace(/,/g, ""))
    .filter((t) => t.length >= 3 || /\d/.test(t))
    .filter((t) => !STOP.has(t));
}

/** Score: shared terms count 1, shared numbers and district names (rs-3, b3-2) count 3. */
function overlap(a: Set<string>, b: string[]): number {
  let s = 0;
  for (const t of new Set(b)) if (a.has(t)) s += /\d/.test(t) ? 3 : 1;
  return s;
}

/** The character range of the section's passage the answer used: the best-matching sentence (a run of two when the
    next one matches too), or null when nothing matches strongly enough (score below 4). */
export function passageFor(text: string, sentence: string | null): [number, number] | null {
  if (!sentence) return null;
  const want = new Set(tokens(sentence));
  if (want.size === 0) return null;
  const spans: Array<[number, number]> = [];
  const re = /[^.;\n]+[.;]?/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) if (m[0].trim()) spans.push([m.index, m.index + m[0].length]);
  let best = -1, bestScore = 0;
  spans.forEach(([s, e], i) => {
    const score = overlap(want, tokens(text.slice(s, e)));
    if (score > bestScore) { bestScore = score; best = i; }
  });
  if (best < 0 || bestScore < 4) return null;
  let [start, end] = spans[best];
  const next = spans[best + 1];
  if (next && overlap(want, tokens(text.slice(next[0], next[1]))) >= 4) end = next[1];
  while (start < end && /\s/.test(text[start])) start++;
  return [start, end];
}

/** A section that is a table (Markdown pipes): its header, rows, and the row naming the district the answer used. */
export function codeTable(text: string, sentence: string | null): CodeTable | null {
  const lines = text.split("\n").map((l) => l.trim()).filter((l) => l.startsWith("|") && l.endsWith("|"));
  if (lines.length < 3) return null;
  const cells = (l: string) => l.slice(1, -1).split("|").map((c) => c.trim());
  const body = lines.filter((l) => !/^\|[\s:|-]+\|$/.test(l));
  const [header, ...rows] = body.map(cells);
  if (!header || rows.length === 0) return null;
  const districts = (sentence ?? "").match(/\b[A-Z]{1,3}\d?-\d+(?:\.\d+)?\b/g) ?? [];
  const hit = rows.findIndex((r) => districts.some((d) => r[0]?.toUpperCase() === d || r.some((c) => c.toUpperCase() === d)));
  return { header, rows, hit: hit >= 0 ? hit : null };
}
