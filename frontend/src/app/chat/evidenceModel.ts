// The evidence panel's Sources list (Phase 8, wireframe v2 approved 2026-11-12): code and records in one numbered
// list, each shown as what it is. Code sections keep the numbers the answer cites ([1], [2] …); records follow, in a
// fixed order, only those the answer has. A code section opens on the passage the answer used, found by matching the
// answer's citing sentence against the section (shared numbers and terms weigh most); no strong match, no highlight.
import type { CodeChunk, ContextObject, DataSource, MapData, Message } from "../../lib/types";

export type RecordKind = "lot" | "facts" | "crime" | "construction" | "requests" | "violations" | "vacant" | "business" | "food";

export type SourceItem =
  | { kind: "code"; n: number; chunk: CodeChunk; passage: [number, number] | null; table: CodeTable | null; cited: boolean }
  | { kind: RecordKind; n: number };

export interface CodeTable { header: string[]; rows: string[][]; hit: number | null }

const RECORD_ORDER: RecordKind[] = ["lot", "facts", "crime", "construction", "requests", "violations", "vacant", "business", "food"];

/** The three kinds of source, told apart by color and a heading (owner, 2026-11-12): the City's code, this lot's own
    records (address points, the County's PIN facts), and the City's records around the lot. */
export type SourceGroup = "code" | "lot" | "area";
export function groupOf(kind: SourceItem["kind"]): SourceGroup {
  return kind === "code" ? "code" : kind === "lot" || kind === "facts" ? "lot" : "area";
}

/** The official record behind a City dataset row: its page on the data portal (ids as in backend/config.py). */
export const CITY_DATASET: Partial<Record<RecordKind, string>> = {
  crime: "ijzp-q8t2", construction: "ydr8-5enu", requests: "v6vf-nfxy", violations: "22u3-xenr",
  vacant: "kc9i-wq85", business: "uupf-x98q", food: "4ijn-s7e5",
};
export const datasetUrl = (id: string) => `https://data.cityofchicago.org/d/${id}`;
export const assessorUrl = (pin: string) => `https://www.cookcountyassessor.com/pin/${pin.replace(/\D/g, "")}`;

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
    const said = citingSentences(message.content ?? "", i + 1);
    const text = chunk.text ?? "";
    const table = codeTable(text, said.join(" "));
    return { kind: "code", n: i + 1, chunk, passage: table ? null : passageFor(text, said), table, cited: said.length > 0 };
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

/** Every sentence of the answer that cites [n], without markup and citation marks. The reference list at the end
    ("- [1] Municipal Code §…") is not a sentence the answer argued from, so it is left out. */
export function citingSentences(content: string, n: number): string[] {
  const plain = content.replace(/\*\*|__|`/g, "");
  return plain.split(/(?<=[.!?:])\s+|\n+/)
    .filter((s) => s.includes(`[${n}]`) && !/^\s*[-*]?\s*\[\d+\]\s/.test(s))
    .map((s) => s.replace(/\s*\[(?:\d+|data:[a-z_0-9]+)\]/g, "").replace(/\s*[.!?:]$/, "").trim())
    .filter(Boolean);
}

/** The first of them (kept for callers that want one line). */
export function citingSentence(content: string, n: number): string | null {
  return citingSentences(content, n)[0] ?? null;
}

const STOP = new Set(["the", "and", "for", "that", "this", "with", "from", "are", "may", "shall", "lot", "its", "any", "not", "which", "than", "within", "each", "such", "into", "only", "per", "has", "have", "can", "could", "would", "also", "one"]);
/** Words worth matching: district names joined ("RS-3" and "RS3" are one), numbers without commas, and other words cut to
    their first five letters so "reduction" meets "reduced". */
function tokens(s: string): string[] {
  return (s.toLowerCase().match(/[a-z]+-?\d+(?:\.\d+)?|[a-z]+|\d[\d,.]*/g) ?? [])
    .map((t) => t.replace(/[,.]$/, "").replace(/,/g, ""))
    .filter((t) => t.length >= 3 || /\d/.test(t))
    .filter((t) => !STOP.has(t))
    .map((t) => (/\d/.test(t) ? t.replace("-", "") : t.slice(0, 5)));
}

/** Score: shared terms count 1, shared numbers and district names (rs-3, b3-2) count 3. */
function overlap(a: Set<string>, b: string[]): number {
  let s = 0;
  for (const t of new Set(b)) if (a.has(t)) s += /\d/.test(t) ? 3 : 1;
  return s;
}

/** The character range of the section's passage the answer used: the sentence matching any citing sentence best (a run
    of two when the next one matches that sentence too), or null when nothing matches strongly enough (score below 4). */
export function passageFor(text: string, said: string | string[] | null): [number, number] | null {
  const wants = (Array.isArray(said) ? said : said ? [said] : []).map((x) => new Set(tokens(x))).filter((w) => w.size > 0);
  if (wants.length === 0) return null;
  const spans: Array<[number, number]> = [];
  const re = /[^.;\n]+[.;]?/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) if (m[0].trim()) spans.push([m.index, m.index + m[0].length]);
  let best = -1, bestScore = 0, bestWant = wants[0];
  for (const want of wants) {
    spans.forEach(([s, e], i) => {
      const score = overlap(want, tokens(text.slice(s, e)));
      if (score > bestScore) { bestScore = score; best = i; bestWant = want; }
    });
  }
  if (best < 0 || bestScore < 4) return null;
  let [start, end] = spans[best];
  const next = spans[best + 1];
  if (next && overlap(bestWant, tokens(text.slice(next[0], next[1]))) >= 4) end = next[1];
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
