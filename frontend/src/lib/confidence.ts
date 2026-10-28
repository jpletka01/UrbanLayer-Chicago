// How a figure says where it came from and how far to trust it (WS0 M4).
//
// Pure helpers over the backend's provenance entry (backend/provenance.py, guide:
// claude-context/guides/source-confidence.md). The backend decides the confidence state
// once (`entry.confidence`); nothing here recomputes it. These functions decide only what
// to SAY: whether a caption shows (the default-quiet rule, guide §4.1), its parts, the
// reason a figure is withheld, and the "Source" block for a label's tooltip.
//
// Text is injected through `t` (the `common` namespace, keys under `confidence.*`), so the
// same functions serve the Profile, the chat rail and the exports.
import type { TFunction } from "i18next";
import type { Provenance, ProvenanceTier } from "./api";
import { formatDay } from "./format";

export type DisplayState = "standard" | "low" | "withheld";

/** Display copies of the backend thresholds (backend/provenance.py). They only fill in "needs N"
    in a withheld sentence; the state itself always comes from the entry. A backend test pins
    these to the Python constants. */
export const DISPLAY_THRESHOLDS = {
  hideCoverageBelow: 0.1,
  hideNBelow: 30,
  compsHideNBelow: 3,
  hideCvAbove: 0.5,
} as const;

/** Tiers C–F always earn a caption; A and B stay quiet unless something is off. */
const CAPTIONED_TIERS: ReadonlySet<ProvenanceTier> = new Set<ProvenanceTier>([
  "official_estimate", "our_calculation", "ai_extracted", "non_government",
]);

/** Sources whose own name is the most useful caption ("City footprint survey, 2015"); all others
    are described by their method. */
const CAPTION_SOURCES: ReadonlySet<string> = new Set([
  "chi.building_footprints", "private.walkscore", "artifact.chrs",
  "cook.treasurer.tax_sale", "cook.treasurer.scavenger_sale",
]);

const dotsToUnderscores = (id: string) => id.replace(/\./g, "_");

/** Keys under `confidence.source.`: the dataset's plain name, for the tooltip and for the sources
    in CAPTION_SOURCES. A missing key is simply not shown. */
function sourceLabel(entry: Provenance, t: TFunction): string {
  if (!entry.source_id) return "";
  return t(`confidence.source.${dotsToUnderscores(entry.source_id)}`, { defaultValue: "" });
}

/** Methods that need no words when the figure is a plain record or published text. */
const SILENT_METHODS: ReadonlySet<string> = new Set(["recorded", "published_text", "code_table"]);

const WITHHOLD_REASONS = ["small_sample", "low_coverage", "high_cv"] as const;

export interface CaptionOpts {
  /** How to print a margin of error: dollars, percentage points, or a bare count. */
  unit?: "usd" | "pct" | "count";
  /** Parts a caller already shows nearby (the tax tile prints its year beside the value). */
  omit?: ReadonlyArray<"period" | "scope">;
}

export interface Caption {
  state: DisplayState;
  /** False when the default-quiet rule says to print nothing. */
  visible: boolean;
  /** An AI reading earns the neutral [AI] mark. */
  ai: boolean;
  /** "Low confidence" — the one amber phrase. Null unless the state is low. */
  lead: string | null;
  /** "Not shown: …" — the whole caption of a withheld figure. */
  withheld: string | null;
  /** Method or source, period or as-of, precision, coverage, scope, in that order. */
  parts: string[];
}

export function displayState(entry: Provenance | null | undefined): DisplayState {
  return entry?.confidence ?? "standard";
}

function isAi(entry: Provenance): boolean {
  return entry.tier === "ai_extracted" || (entry.method_key ?? "").startsWith("ai_read");
}

/** The default-quiet rule (guide §4.1): a caption shows when the tier is C–F, the figure is
    low or withheld, or its source dataset is more than 24 months old. */
export function wantsCaption(entry: Provenance | null | undefined): boolean {
  if (!entry) return false;
  if (displayState(entry) !== "standard") return true;
  if (entry.tier && CAPTIONED_TIERS.has(entry.tier)) return true;
  return (entry.confidence_reasons ?? []).includes("old_source");
}

function fmtNumber(n: number, digits = 1): string {
  return n.toLocaleString("en-US", { maximumFractionDigits: digits });
}

function fmtMoe(moe: number, unit: CaptionOpts["unit"]): string {
  if (unit === "usd") return `±$${Math.round(moe).toLocaleString("en-US")}`;
  if (unit === "pct") return `±${fmtNumber(moe)} pts`;
  return `±${fmtNumber(moe)}`;
}

/** "±$220" / "±2.5 pts" for a figure's published margin of error, or null when the source publishes none. */
export function marginText(entry: Provenance | null | undefined, unit: CaptionOpts["unit"]): string | null {
  return entry?.precision?.moe != null ? fmtMoe(entry.precision.moe, unit) : null;
}

const SOURCE_AGE_DAYS = 730;

/** A year is enough for a source that is itself years old, or one dated by tax year or vintage;
    a newer one gets its day. */
function fmtAsOf(entry: Provenance): string | null {
  if (!entry.as_of || entry.as_of_basis === "queried") return null;
  if ((entry.age_days ?? 0) > SOURCE_AGE_DAYS || entry.as_of_basis === "tax_year" || entry.as_of_basis === "vintage") {
    return entry.as_of.slice(0, 4);
  }
  return formatDay(entry.as_of);
}

/** "1 sale", "2 sales": the unit agrees with the count (i18next plural keys `confidence.unit.<unit>_one/_other`). */
function unitText(t: TFunction, unit: string | null | undefined, n: number): string {
  return unit ? t(`confidence.unit.${unit}`, { count: n, defaultValue: unit }) : "";
}

function withheldSentence(entry: Provenance, t: TFunction): string {
  const reasons = entry.confidence_reasons ?? [];
  const reason = WITHHOLD_REASONS.find((r) => reasons.includes(r));
  const cov = entry.coverage ?? {};
  const unit = unitText(t, cov.unit, cov.n ?? 0);
  if (reason === "small_sample") {
    const min = cov.sample === "comps" ? DISPLAY_THRESHOLDS.compsHideNBelow : DISPLAY_THRESHOLDS.hideNBelow;
    return t("confidence.withheld.small_sample", { n: cov.n ?? 0, unit, min });
  }
  if (reason === "low_coverage") {
    return t("confidence.withheld.low_coverage", {
      pct: Math.round((cov.share ?? 0) * 100), min: Math.round(DISPLAY_THRESHOLDS.hideCoverageBelow * 100),
    });
  }
  if (reason === "high_cv") {
    return t("confidence.withheld.high_cv", { cv: Math.round((entry.precision?.cv ?? 0) * 100) });
  }
  return t("confidence.withheld.generic");
}

/** What a comps median rests on, in the search's own terms ("0.28 mi · 3 yr"), so a widened
    search says so instead of repeating a fixed ¼ mile. */
function compsBasis(entry: Provenance, t: TFunction): string | null {
  const p = entry.method_params;
  const radius = p?.radius_mi;
  const years = p?.window_years;
  if (typeof radius !== "number" || typeof years !== "number") return null;
  const base = t("confidence.compsBasis", { radius: fmtNumber(radius, 2), years });
  return p?.widened ? `${base} ${t("confidence.widened")}` : base;
}

export function captionParts(entry: Provenance | null | undefined, t: TFunction, opts: CaptionOpts = {}): Caption {
  const state = displayState(entry);
  const quiet: Caption = { state, visible: false, ai: false, lead: null, withheld: null, parts: [] };
  if (!entry || !wantsCaption(entry)) return quiet;

  const reasons = entry.confidence_reasons ?? [];
  const ai = isAi(entry);
  if (state === "withheld") {
    return { ...quiet, visible: true, withheld: withheldSentence(entry, t) };
  }

  const parts: string[] = [];
  const cov = entry.coverage;
  const comps = cov?.sample === "comps" ? compsBasis(entry, t) : null;

  // How old: the statistic's period, else the source's date. Our own arithmetic has no
  // publication date (its inputs do), so a calculation names a date only when it has a period.
  if (!opts.omit?.includes("period")) {
    const when = comps ? null : (entry.period ?? (entry.method_key === "calculation" ? null : fmtAsOf(entry)));
    if (when) parts.push(when);
  }

  // How precise.
  if (entry.precision?.moe != null) parts.push(fmtMoe(entry.precision.moe, opts.unit));
  else if (reasons.includes("bracket_median")) parts.push(t("confidence.noMargin"));
  else if (reasons.includes("high_cv") && entry.precision?.cv != null) {
    parts.push(t("confidence.wideMargin", { cv: Math.round(entry.precision.cv * 100) }));
  }

  // How much it covers.
  if (cov?.n != null && cov.unit) {
    parts.push(t("confidence.sampleN", {
      n: cov.n.toLocaleString("en-US"), unit: unitText(t, cov.unit, cov.n),
    }));
  }
  if (comps) parts.push(comps);
  if (cov?.share != null) parts.push(t("confidence.coverage", { pct: Math.round(cov.share * 100) }));

  // Where: an area figure says which area.
  if (!opts.omit?.includes("scope") && entry.geography && entry.scope
    && ["tract", "puma", "community_area", "city", "county"].includes(entry.scope)) {
    parts.push(entry.geography);
  }

  // Who or how comes first: a named source, else the method — unless it is a plain record, or a
  // calculation whose basis, period and scope already say what it rests on.
  // A calculation that names its own dataset (a lot area taken from the parcel polygon) says so, in
  // the backend's words; the entry's `source` is set only where that matters.
  if (entry.source_id && CAPTION_SOURCES.has(entry.source_id) && sourceLabel(entry, t)) {
    parts.unshift(sourceLabel(entry, t));
  } else if (entry.method_key === "calculation" && entry.source) {
    parts.unshift(entry.source);
  } else if (entry.method_key && !SILENT_METHODS.has(entry.method_key)
    && !(entry.method_key === "calculation" && parts.length > 0)) {
    parts.unshift(methodText(entry, t));
  }

  if (ai && reasons.includes("ai_unverified")) parts.push(t("confidence.notVerified"));
  const lowReasonsOnlyAi = reasons.every((r) => r === "ai_unverified" || r === "old_source");
  const lead = state === "low" && !(ai && lowReasonsOnlyAi) ? t("confidence.state.low") : null;
  return { state, visible: true, ai, lead, withheld: null, parts };
}

/** The method in words. A margin we derived ourselves names how (`precision.moe_method`): a rent median
    summed from Census rent brackets is not "estimated from income brackets". */
function methodText(entry: Provenance, t: TFunction): string {
  const derived = entry.precision?.moe_method;
  if (entry.method_key === "bracket_median" && derived) {
    return t(`confidence.moeMethod.${derived}`, { defaultValue: entry.method ?? "" });
  }
  return t(`confidence.method.${entry.method_key}`, { defaultValue: entry.method ?? "" });
}

export interface SourceBullet { field: string; text: string }

/** The five fields for a label's tooltip: authority, as of, coverage, precision, method.
    Every figure with an entry gets this block, captioned or not, so its source is one tap away. */
export function sourceBullets(entry: Provenance | null | undefined, t: TFunction, opts: CaptionOpts = {}): string[] {
  if (!entry) return [];
  const out: string[] = [];
  if (entry.tier) out.push(t("confidence.field.authority", { value: t(`confidence.tier.${entry.tier}`) }));

  if (entry.as_of && entry.as_of_basis !== "queried") {
    const basis = t(`confidence.basis.${entry.as_of_basis ?? "source_updated"}`, { defaultValue: "" });
    const age = entry.age_days != null && entry.age_days >= 0
      ? t("confidence.daysOld", { count: entry.age_days })
      : "";
    const value = [formatDay(entry.as_of), age].filter(Boolean).join(" · ");
    out.push(t("confidence.field.asOf", { value: basis ? `${value} (${basis})` : value }));
  } else if (entry.period) {
    out.push(t("confidence.field.asOf", { value: entry.period }));
  } else {
    out.push(t("confidence.field.asOfUnknown", { date: formatDay(entry.query_date) }));
  }

  if (entry.geography) out.push(t("confidence.field.scope", { value: entry.geography }));

  const source = sourceLabel(entry, t);
  if (source) out.push(t("confidence.field.source", { value: source }));

  const cov = entry.coverage;
  if (cov && (cov.n != null || cov.share != null)) {
    const bits = [
      cov.n != null && cov.unit
        ? t("confidence.sampleN", { n: cov.n.toLocaleString("en-US"), unit: unitText(t, cov.unit, cov.n) })
        : null,
      cov.share != null ? t("confidence.coverage", { pct: Math.round(cov.share * 100) }) : null,
    ].filter(Boolean);
    out.push(t("confidence.field.coverage", { value: bits.join(" · ") }));
  }

  const prec = entry.precision;
  if (prec?.moe != null) {
    const level = Math.round((prec.moe_level ?? 0.9) * 100);
    out.push(t("confidence.field.precision", { value: fmtMoe(prec.moe, opts.unit), level }));
  } else if (prec?.agreement) {
    out.push(t("confidence.field.agreement", { agree: prec.agreement.agree, n: prec.agreement.n }));
  }

  if (entry.method_key) {
    out.push(t("confidence.field.method", {
      value: methodText(entry, t),
    }));
  }
  return out;
}

/** The caption as one plain line, for the CSV export — it prints the same words the page does. */
export function plainCaption(entry: Provenance | null | undefined, t: TFunction, opts: CaptionOpts = {}): string {
  const c = captionParts(entry, t, opts);
  if (!c.visible) return "";
  if (c.withheld) return c.withheld;
  return [c.ai ? "[AI]" : null, c.lead, ...c.parts].filter(Boolean).join(" · ");
}
