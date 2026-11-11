// History tab model (brief "Property Profile", History: "What has happened to this property?"; decision Item 103).
// One timeline of what the records say happened at this lot: market sales, other transfers, the City's building
// permits, the City's building violations (one event per inspection), zoning (the ordinance behind today's district,
// filings and passed rezonings listing this address) and tax appeals. Pure: the tab draws what this returns. Facts only,
// no predictions (rule 11); a transfer is never shown as a sale price (rule 4).
import type { AddressPermit, ScorecardResponse } from "../../lib/api";
import type { AssessorPermit, SaleRecord } from "../../lib/types";
import type { TFunc } from "../../lib/scorecardVerdict";
import { isMarketSale, numLocale } from "./profileModel";
import { usd, type LateBlockState } from "./moneyModel";

export type EventKind = "sale" | "transfer" | "permit" | "violation" | "zoning" | "appeal";
export const KINDS: EventKind[] = ["sale", "permit", "violation", "zoning", "appeal", "transfer"];
/** On at first (owner, 2026-11-10: everything but the noise): appeals and non-market transfers are one chip away. */
export const DEFAULT_ON: ReadonlySet<EventKind> = new Set<EventKind>(["sale", "permit", "violation", "zoning"]);

export interface ViolationRow {
  date: string | null; code: string | null; description: string | null; status: string | null;
  status_date: string | null; inspection: string | null;
}

export interface HistoryEvent {
  id: string;
  kind: EventKind;
  /** ISO date, or the year's first day for a year-only record (appeals). */
  date: string;
  /** True when the record has only a year. */
  yearOnly?: boolean;
  /** Plain words: what happened. */
  title: string;
  /** A sale's price (market sales only). */
  price?: number;
  /** Small facts as pills (deed, cost, status, …). */
  pills: Array<{ text: string; tone?: "gray" | "green" | "yellow" | "red" | "blue" }>;
  /** A permit opens its page; a violation group expands; a zoning record links out. */
  permit?: AddressPermit;
  violations?: ViolationRow[];
  href?: string;
}

export type SourceKey = "permits_at_address" | "violations_at_address" | "building_records";

/** Where one of History's own sources stands (the `history` part; Item 89's skeleton rule). `none` = not asked:
    no property record, or an address the City's records can't be searched by. */
export function historySource(
  data: ScorecardResponse, part: LateBlockState, source: SourceKey, timedOut: string[],
): LateBlockState | "none" {
  if (!data.context?.property?.pin14) return "none";
  if (part === "loading" || part === "failed") return part;
  if (timedOut.includes(source)) return "timedOut";
  if (data.next_ui?.failed?.includes(source as never)) return "failed";
  const v = data.next_ui?.[source];
  if (v === undefined) return part === "timedOut" ? "timedOut" : "failed";
  return v === null ? "none" : "ready";
}

const iso = (d: string | null | undefined) => (d ? d.slice(0, 10) : null);
const sentenceCase = (s: string | null | undefined) => {
  if (!s) return null;
  const x = s.replace(/\s+/g, " ").trim().toLowerCase();
  return x.charAt(0).toUpperCase() + x.slice(1);
};

/** The City's long permit text, short enough for one row: its first clause. */
export function shortWords(s: string | null | undefined, max = 90): string | null {
  const x = sentenceCase(s);
  if (!x) return null;
  const first = x.split(/(?<=[.;])\s/)[0].replace(/[.;]$/, "");
  return first.length > max ? `${first.slice(0, max - 1).trimEnd()}…` : first;
}

function saleEvents(sales: SaleRecord[], t: TFunc, lng: string): HistoryEvent[] {
  return sales.filter((s) => s.date).map((s, i) => {
    const market = isMarketSale(s);
    const deed = s.deed_type ? t("profile.history.deed", { deed: s.deed_type.toLowerCase() }) : null;
    return {
      id: `sale-${i}`,
      kind: market ? "sale" : "transfer",
      date: iso(s.date)!,
      price: market ? s.price! : undefined,
      title: market ? t("profile.history.ev.sale", { price: usd(s.price!, lng) })
        : s.price != null && s.price > 0 ? t("profile.history.ev.transferPrice", { price: usd(s.price, lng) })
        : t("profile.history.ev.transfer"),
      pills: [
        ...(deed ? [{ text: deed }] : []),
        ...(!market ? [{ text: t("profile.history.notMarket"), tone: "yellow" as const }] : []),
      ],
    };
  });
}

function permitEvents(projects: AddressPermit[], t: TFunc, lng: string): HistoryEvent[] {
  return projects.filter((p) => p.issued).map((p, i) => ({
    id: `permit-${p.permit ?? i}`,
    kind: "permit",
    date: p.issued!,
    title: shortWords(p.description) ?? t("profile.history.ev.permit"),
    pills: [
      { text: permitTypeWords(p, t) },
      ...(p.cost != null && p.cost > 1 ? [{ text: usd(p.cost, lng) }] : []),
      ...(p.units_added ? [{ text: t(p.units_added > 0 ? "profile.nb.building.addsUnits" : "profile.nb.building.removesUnits", { count: Math.abs(p.units_added) }), tone: "green" as const }] : []),
    ],
    permit: p,
  }));
}

/** The permit's kind in words: our two named kinds, else the City's own type ("Signs", "Elevator equipment"). */
export function permitTypeWords(p: AddressPermit, t: TFunc): string {
  if (p.kind === "new" || p.kind === "renovation" || p.kind === "demolition") return t(`profile.history.permitKind.${p.kind}`);
  return sentenceCase(p.permit_type) ?? t("profile.history.ev.permit");
}

/** The Assessor's permits, when the City's lookup didn't answer (they mirror the City's, with less detail). */
function assessorPermitEvents(permits: AssessorPermit[], t: TFunc, lng: string): HistoryEvent[] {
  return permits.filter((p) => p.date_issued).map((p, i) => ({
    id: `apermit-${i}`,
    kind: "permit",
    date: iso(p.date_issued)!,
    title: shortWords(p.work_description) ?? t("profile.history.ev.permit"),
    pills: [
      { text: t("profile.history.assessorRecord") },
      ...(p.amount != null && p.amount > 1 ? [{ text: usd(p.amount, lng) }] : []),
    ],
  }));
}

/** One event per inspection (a visit writes several violations on one day). */
export function violationEvents(rows: ViolationRow[], t: TFunc): HistoryEvent[] {
  const groups = new Map<string, ViolationRow[]>();
  for (const r of rows) {
    if (!r.date) continue;
    const key = r.inspection ? `i${r.inspection}` : `d${r.date}`;
    groups.set(key, [...(groups.get(key) ?? []), r]);
  }
  return [...groups.entries()].map(([key, rs]) => {
    const open = rs.filter((r) => r.status === "OPEN").length;
    const date = rs.map((r) => r.date!).sort()[0];
    return {
      id: `viol-${key}`,
      kind: "violation",
      date,
      title: t("profile.history.ev.violations", { count: rs.length }),
      pills: [
        open > 0 ? { text: t("profile.history.openCount", { count: open }), tone: "red" as const }
          : { text: t("profile.history.allResolved"), tone: "gray" as const },
        ...(rs[0].description ? [{ text: shortWords(rs[0].description, 40)! }] : []),
      ],
      violations: rs,
    };
  });
}

function zoningEvents(data: ScorecardResponse, t: TFunc): HistoryEvent[] {
  const ctx = data.context;
  const out: HistoryEvent[] = [];
  const z = ctx?.parcel_zoning;
  if (z?.ordinance_date && z.zone_class) {
    out.push({
      id: "zoning-current", kind: "zoning", date: iso(z.ordinance_date)!,
      title: t("profile.history.ev.zoned", { zone: z.zone_class }),
      pills: z.ordinance_num ? [{ text: t("profile.history.ordinance", { num: z.ordinance_num }) }] : [],
      href: z.clerk_url ?? undefined,
    });
  }
  for (const f of ctx?.upcoming_zoning?.subject_filings ?? []) {
    if (!f.introduced_at) continue;
    out.push({
      id: `zoning-filing-${f.record_number}`, kind: "zoning", date: iso(f.introduced_at)!,
      title: t("profile.history.ev.filing"),
      pills: [{ text: f.sub_status || f.status, tone: "blue" }, { text: f.record_number }],
      href: f.url,
    });
  }
  for (const p of ctx?.passed_not_on_map ?? []) {
    out.push({
      id: `zoning-passed-${p.record}`, kind: "zoning", date: iso(p.passed_on)!,
      title: p.to_district ? t("profile.history.ev.passedTo", { zone: p.to_district }) : t("profile.history.ev.passed"),
      pills: [{ text: t("profile.history.notOnMapYet"), tone: "yellow" }, { text: p.record }],
      href: p.url,
    });
  }
  for (const d of ctx?.passed_landmark_designations ?? []) {
    out.push({
      id: `zoning-landmark-${d.record}`, kind: "zoning", date: iso(d.passed_on)!,
      title: t(`profile.history.ev.landmark.${d.kind}`, { name: d.name ?? "" }),
      pills: [{ text: d.record }],
      href: d.url,
    });
  }
  return out;
}

function appealEvents(data: ScorecardResponse, t: TFunc): HistoryEvent[] {
  return (data.context?.property?.appeals?.records ?? []).filter((a) => a.year).map((a, i) => {
    const cut = a.reduction_pct != null && a.reduction_pct > 0;
    return {
      id: `appeal-${i}`, kind: "appeal", date: `${a.year}-01-01`, yearOnly: true,
      title: t(`profile.history.ev.appeal.${a.stage === "board_of_review" ? "bor" : "assessor"}`),
      pills: [cut ? { text: t("profile.history.cut", { pct: Math.round(a.reduction_pct!) }), tone: "green" as const }
        : { text: t("profile.history.noChange") }],
    };
  });
}

export interface HistoryModel {
  events: HistoryEvent[];
  /** Which source supplied the permits: the City's (with pages), the Assessor's (fallback), or none checked. */
  permitsFrom: "city" | "assessor" | null;
  counts: Record<EventKind, number>;
  marketSale: HistoryEvent | null;
  firstYear: number;
  lastYear: number;
}

export function historyModel(
  data: ScorecardResponse, t: TFunc, lng: string,
  st: { permits: LateBlockState | "none"; violations: LateBlockState | "none" },
  now = new Date(),
): HistoryModel {
  const prop = data.context?.property;
  const events: HistoryEvent[] = [...saleEvents(prop?.sales_history ?? [], t, lng), ...zoningEvents(data, t), ...appealEvents(data, t)];
  let permitsFrom: HistoryModel["permitsFrom"] = null;
  if (st.permits === "ready") {
    events.push(...permitEvents(data.next_ui?.permits_at_address?.projects ?? [], t, lng));
    permitsFrom = "city";
  } else if ((st.permits === "failed" || st.permits === "none") && prop?.assessor_permits?.permits?.length) {
    events.push(...assessorPermitEvents(prop.assessor_permits.permits, t, lng));
    permitsFrom = "assessor";
  }
  if (st.violations === "ready") events.push(...violationEvents(data.next_ui?.violations_at_address?.violations ?? [], t));
  events.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
  const counts = Object.fromEntries(KINDS.map((k) => [k, events.filter((e) => e.kind === k).length])) as Record<EventKind, number>;
  const years = events.map((e) => Number(e.date.slice(0, 4))).filter((y) => y > 1900);
  const lastYear = now.getFullYear();
  return {
    events, permitsFrom, counts,
    marketSale: events.find((e) => e.kind === "sale") ?? null,
    firstYear: Math.min(lastYear - 10, ...years),
    lastYear,
  };
}

/** The tab's sentence: the last market sale, then the permits and the violations, each only when its source answered. */
export function historySentence(
  data: ScorecardResponse, m: HistoryModel, t: TFunc, lng: string,
  st: { permits: LateBlockState | "none"; violations: LateBlockState | "none" },
): string {
  const prop = data.context?.property;
  if (!prop) return t("profile.history.sentence.noRecord");
  const sale = (prop.sales_history ?? []).filter((s) => s.date && isMarketSale(s)).sort((a, b) => (a.date! < b.date! ? 1 : -1))[0];
  const parts: string[] = [];
  parts.push(sale ? t("profile.history.sentence.sold", { year: sale.date!.slice(0, 4), price: usd(sale.price!, lng) })
    : (prop.sales_history ?? []).length > 0 ? t("profile.history.sentence.onlyTransfers") : t("profile.history.sentence.noSale"));
  const rest: string[] = [];
  if (m.permitsFrom === "city") {
    const n = m.counts.permit;
    const since = n ? m.events.filter((e) => e.kind === "permit").map((e) => e.date.slice(0, 4)).sort()[0] : null;
    rest.push(n ? t("profile.history.sentence.permits", { count: n, year: since }) : t("profile.history.sentence.noPermits"));
  }
  if (st.violations === "ready") {
    const rows = data.next_ui?.violations_at_address?.violations ?? [];
    const open = rows.filter((r) => r.status === "OPEN").length;
    rest.push(rows.length === 0 ? t("profile.history.sentence.noViolations")
      : open > 0 ? t("profile.history.sentence.openViolations", { count: open })
      : t("profile.history.sentence.resolvedViolations", { count: rows.length }));
  }
  const tail = rest.join(t("profile.history.and"));
  return `${parts[0]}${tail ? `. ${tail.charAt(0).toUpperCase()}${tail.slice(1)}` : ""}.`;
}

// ── The timeline's lanes ──────────────────────────────────────────────────────────────────────────────

export interface LaneMark { kind: EventKind; year: number; count: number; label: string }

/** One mark per kind per year (a year with nine sign permits is one mark that says 9). */
export function laneMarks(events: HistoryEvent[], on: ReadonlySet<EventKind>): LaneMark[] {
  const map = new Map<string, LaneMark>();
  for (const e of events) {
    if (!on.has(e.kind)) continue;
    const year = Number(e.date.slice(0, 4));
    const key = `${e.kind}:${year}`;
    const m = map.get(key) ?? { kind: e.kind, year, count: 0, label: "" };
    m.count += 1;
    map.set(key, m);
  }
  return [...map.values()];
}

/** Events shown in the list: the kinds that are on, and a picked year when one is. */
export function listed(events: HistoryEvent[], on: ReadonlySet<EventKind>, year: number | null, kind: EventKind | null): HistoryEvent[] {
  return events.filter((e) => on.has(e.kind) && (year == null || Number(e.date.slice(0, 4)) === year) && (kind == null || e.kind === kind));
}

// ── Building facts, each source beside the others ("records differ", owner's pick C) ─────────────────

export type BuildingFact = "year_built" | "stories" | "bldg_sqft";
export const BUILDING_FACTS: BuildingFact[] = ["year_built", "stories", "bldg_sqft"];
export interface SourceValue { source: string; value: number; as_of: number | null }
export interface BuildingRecords {
  facts: Record<BuildingFact, SourceValue[]>;
  differ: BuildingFact[];
  unanswered: string[];
}

/** A fact's value as the Profile shows it: the summary's own (the first listed), with every source behind it. */
export function factRows(data: ScorecardResponse, rec: BuildingRecords | null | undefined): Array<{
  fact: BuildingFact | "units"; value: number | null; source: string | null; differs: boolean; sources: SourceValue[];
}> {
  const prop = data.context?.property;
  const own = (f: BuildingFact) => {
    const v = f === "year_built" ? (prop as { year_built?: number | null } | null | undefined)?.year_built ?? null : (prop?.[f] ?? null);
    return v;
  };
  const rows = BUILDING_FACTS.map((f) => {
    const sources = rec?.facts?.[f] ?? [];
    const value = own(f) ?? sources[0]?.value ?? null;
    const source = (prop?.[`${f}_source` as "stories_source"] ?? null) || (own(f) == null ? sources[0]?.source ?? null : null);
    return { fact: f, value, source, differs: !!rec?.differ?.includes(f), sources };
  });
  return [...rows, { fact: "units" as const, value: prop?.units ?? null, source: prop?.units_source ?? null, differs: false, sources: [] }];
}

/** "1899–1992" for a fact whose sources differ, else the one value, in the reader's number format. */
export function factText(fact: BuildingFact | "units", value: number | null, lng: string): string {
  if (value == null) return "—";
  if (fact === "year_built") return String(Math.round(value));
  if (fact === "stories") return value.toLocaleString(numLocale(lng), { maximumFractionDigits: 1 });
  return Math.round(value).toLocaleString(numLocale(lng));
}

export function rangeText(fact: BuildingFact, sources: SourceValue[], lng: string): string | null {
  if (sources.length < 2) return null;
  const vs = sources.map((s) => s.value);
  const lo = Math.min(...vs), hi = Math.max(...vs);
  return lo === hi ? null : `${factText(fact, lo, lng)}–${factText(fact, hi, lng)}`;
}
