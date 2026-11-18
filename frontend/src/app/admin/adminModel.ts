// /admin redesigned like Settings (design B): one section at a time, each at its own address (/admin/<id>), and an
// Overview first that says what needs attention in a few words. Pure: the sections, which one an address opens, and
// the attention lines (each at most five words; the details live in the section).
import type { AdminCodeCurrency, DataHealth } from "../../lib/api";

export type AdminSectionId = "overview" | "usage" | "visitors" | "quality" | "requests" | "data" | "corrections" | "code" | "access";

export const ADMIN_SECTIONS: ReadonlyArray<{ id: AdminSectionId; label: string; group: "watch" | "act" }> = [
  { id: "overview", label: "Overview", group: "watch" },
  { id: "usage", label: "Usage and cost", group: "watch" },
  { id: "visitors", label: "Visitors", group: "watch" },
  { id: "quality", label: "Answer quality", group: "watch" },
  { id: "requests", label: "Requests", group: "watch" },
  { id: "data", label: "Data health", group: "act" },
  { id: "corrections", label: "Corrections", group: "act" },
  { id: "code", label: "Code updates", group: "act" },
  { id: "access", label: "Early access", group: "act" },
];

/** The sections whose figures follow the period switch (Today, 7 days, ...). */
export const PERIOD_SECTIONS: ReadonlySet<AdminSectionId> = new Set(["overview", "usage", "visitors"]);

export function adminSectionFrom(param: string | undefined): AdminSectionId {
  return ADMIN_SECTIONS.some((s) => s.id === param) ? (param as AdminSectionId) : "overview";
}

export type Tone = "green" | "yellow" | "red" | "gray";
export interface Attention { section: AdminSectionId; tone: Tone; words: string }

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** Data health in one line: the checker first (nothing else is current without it), then failing, then warnings. */
export function dataAttention(d: DataHealth | null | undefined): Attention {
  if (d === undefined) return { section: "data", tone: "gray", words: "Checking…" };
  if (d === null) return { section: "data", tone: "gray", words: "Can't read the checker" };
  if (d.checker.state === "late") return { section: "data", tone: "red", words: d.checker.last_run ? "Daily check is late" : "Daily check never ran" };
  const failing = (d.counts.alarm ?? 0) + (d.counts.error ?? 0);
  if (failing) return { section: "data", tone: "red", words: `${plural(failing, "source", "sources")} failing` };
  const warn = d.counts.warn ?? 0;
  if (warn) return { section: "data", tone: "yellow", words: `${plural(warn, "source", "sources")} to check` };
  return { section: "data", tone: "green", words: "All sources fresh" };
}

/** The code text in one line: out of date first, then amendments nobody has read, then rezonings off the map. */
export function codeAttention(c: AdminCodeCurrency | null | undefined): Attention {
  if (c === undefined) return { section: "code", tone: "gray", words: "Checking…" };
  if (c === null) return { section: "code", tone: "gray", words: "Can't read code status" };
  const age = c.code.age_days;
  if (c.code.status === "red") return { section: "code", tone: "red", words: age != null ? `Code text ${age} days old` : "Code text out of date" };
  if (c.code.lag.unreviewed) return { section: "code", tone: "yellow", words: `${plural(c.code.lag.unreviewed, "amendment", "amendments")} to review` };
  if (c.code.status === "amber") return { section: "code", tone: "yellow", words: c.code.check_state === "unknown" ? "Clerk check not fresh" : "Code text aging" };
  return { section: "code", tone: "green", words: "Code text current" };
}

export function correctionsAttention(open: number | null | undefined): Attention {
  if (open === undefined) return { section: "corrections", tone: "gray", words: "Checking…" };
  if (open === null) return { section: "corrections", tone: "gray", words: "Can't read reports" };
  return open ? { section: "corrections", tone: "yellow", words: `${plural(open, "report", "reports")} to review` }
    : { section: "corrections", tone: "green", words: "No reports waiting" };
}

/** The code's state as a word (the API's "green / amber / red"). */
export const CODE_STATUS_WORD = { green: "Current", amber: "Aging", red: "Out of date" } as const;

/** A section's notification badge (owner, 2026-11-17: Reddit's style): a count on the section's icon when there is
    something to count, a dot when something needs doing with nothing to count (the daily check not running, the code
    text out of date). Never a "!" glyph: in our font it reads like a 1. Red only for something failing; work to do in
    the neutral primary. */
export interface Badge { count: number | null; tone: "red" | "work"; spoken: string }

export function sectionBadges(health: DataHealth | null | undefined, code: AdminCodeCurrency | null | undefined, openReports: number | null | undefined): Partial<Record<AdminSectionId, Badge>> {
  const out: Partial<Record<AdminSectionId, Badge>> = {};
  if (health) {
    const failing = (health.counts.alarm ?? 0) + (health.counts.error ?? 0);
    if (failing) out.data = { count: failing, tone: "red", spoken: `${plural(failing, "source", "sources")} failing` };
    else if (health.checker.state === "late") out.data = { count: null, tone: "red", spoken: "daily check not running" };
  }
  if (code) {
    if (code.code.lag.unreviewed) out.code = { count: code.code.lag.unreviewed, tone: "work", spoken: `${plural(code.code.lag.unreviewed, "amendment", "amendments")} to review` };
    else if (code.code.status === "red") out.code = { count: null, tone: "red", spoken: "code text out of date" };
  }
  if (openReports) out.corrections = { count: openReports, tone: "work", spoken: `${plural(openReports, "report", "reports")} to review` };
  return out;
}

/** What a badge prints: the count, "9+" past nine (Reddit's cap keeps the pill small), nothing for a dot. */
export function badgeText(count: number | null): string | null {
  return count == null ? null : count > 9 ? "9+" : String(count);
}
