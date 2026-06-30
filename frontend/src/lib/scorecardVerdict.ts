// Scorecard Verdict engine — deterministic, no LLM, no network, no React.
//
// Turns a loaded ScorecardResponse into a single conclusion (category) + 2–4
// card-linked reasons + one next step + honest caveats. Leads with the verdict
// so the user never has to synthesize raw data themselves.
//
// Thresholds + category tree were calibrated against 59 real parcels through the
// live /api/scorecard (2026-06-29, signed off) — see
// claude-context/audits/2026-06-29_design-ux-skills-audit.md and the P0 plan.
// Skill basis: quiz-and-assessment-design (actionable segmentation, honest
// categories, one mapped next step), comparison-tool-design (honest-recommendation
// discipline — friction can't be masked, tradeoffs shown inline).

import type { ScorecardResponse } from "./api";

// Minimal i18next-compatible signature so the module stays React/i18n-pure and
// unit-testable (the category/signal logic below needs no strings at all).
export type TFunc = (key: string, opts?: Record<string, unknown>) => string;

// --- signed-off calibration knobs --------------------------------------------
export const CAPACITY_HIGH = 1.8;          // allowedFAR/existingFAR ≥ this ⇒ "high"
export const CAPACITY_MODEST = 1.2;
export const VACANT_FAR = 0.3;             // existingFAR below this on a buildable zone ⇒ teardown/vacant
export const STRONG_MIN_ALLOWED_FAR = 1.5; // single-family FAR headroom isn't real upside (decision B)
export const TIF_WELL_FUNDED = 5_000_000;  // TIF fund balance above this counts toward "strong" incentive
export const STACK_MIN = 2;                 // ≥ this many incentives ⇒ "strong" incentive

export type VerdictCategory =
  | "strong"
  | "incentive_driven"
  | "constrained"
  | "limited"
  | "entitlement_defined"
  | "insufficient_data";

export type CardId =
  | "zoning"
  | "incentives"
  | "regulatory"
  | "property"
  | "comparables"
  | "violations";

export type ReasonPolarity = "positive" | "negative" | "neutral";
export type CapacityBand =
  | "vacant_or_teardown"
  | "high"
  | "modest"
  | "at_cap"
  | "unknown"
  | "n/a";
export type IncentiveStrength = "strong" | "some" | "none";

export interface VerdictReason {
  text: string;
  polarity: ReasonPolarity;
  cardAnchor: CardId;
}

export interface VerdictNextStep {
  // The band commits to ONE azure next-step (work, not money). The paid report is
  // a separate terracotta money action — the dedicated ReportCTACard below the
  // band — so the verdict earns trust before the page asks for the sale (#4).
  kind: "chat" | "scroll";
  label: string;
  question?: string; // kind==="chat" — carries the address (grounding requires it)
  cardAnchor?: CardId; // kind==="scroll"
}

export interface VerdictSignals {
  allowedFar: number | null;
  existingFar: number | null;
  capacityRatio: number | null;
  capacityBand: CapacityBand;
  bldgAreaLowConfidence: boolean;
  incentiveStrength: IncentiveStrength;
  incentiveCount: number;
  tifBalance: number;
  bonusFlags: string[]; // "tod" | "adu"
  frictionFlags: string[]; // parcel-specific obstacles only
  frictionLevel: "meaningful" | "low";
  neutralFlags: string[]; // aro, etc. — context, never friction
  zoneClass: string | null;
}

export interface ScorecardVerdict {
  category: VerdictCategory;
  headline: string;
  reasons: VerdictReason[];
  nextStep: VerdictNextStep;
  confidence: "high" | "caveated";
  caveats: string[];
  signals: VerdictSignals;
}

function num(x: unknown): number | null {
  const n = typeof x === "number" ? x : typeof x === "string" ? parseFloat(x) : NaN;
  return Number.isFinite(n) ? n : null;
}

function compactUsd(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n)}`;
}

// --- signal derivation (mirrors verdict_calibration.py exactly) ---------------
export function deriveSignals(data: ScorecardResponse): VerdictSignals {
  const ctx = data.context ?? ({} as ScorecardResponse["context"]);
  const prop = ctx.property ?? null;
  const inc = ctx.incentives ?? null;
  const reg = ctx.regulatory ?? null;
  const viol = ctx.violations ?? null;
  const zdef = data.zone_definition ?? null;
  const pf = data.partial_failures ?? [];

  const allowedFar = zdef ? num(zdef.far) : null;
  const bldg = prop ? num(prop.bldg_sqft) : null;
  const land = prop ? num(prop.land_sqft) : null;
  const bldgClass = (prop?.bldg_class ?? "").trim().toUpperCase();
  const vacantClass =
    bldgClass.startsWith("1-00") || bldgClass === "100" || bldgClass.startsWith("100 ") || bldgClass === "VACANT";

  // Pushback #1: bldg_sqft is frequently stale/missing/area-derived. Degrade to
  // "unknown" rather than confidently misclassify a parcel's capacity.
  const bldgAreaLowConfidence =
    pf.includes("property characteristics") ||
    !bldg ||
    !land ||
    (vacantClass && !!bldg && bldg > 0) ||
    !!data.nearest_parcel_unverified;

  const existingFar = !bldgAreaLowConfidence && bldg && land ? bldg / land : null;
  const capacityRatio = allowedFar != null && existingFar != null ? allowedFar / existingFar : null;

  let capacityBand: CapacityBand;
  if (bldgAreaLowConfidence || existingFar == null) capacityBand = "unknown";
  else if (existingFar < VACANT_FAR && allowedFar != null && allowedFar >= 1.0) capacityBand = "vacant_or_teardown";
  else if (capacityRatio != null && capacityRatio >= CAPACITY_HIGH) capacityBand = "high";
  else if (capacityRatio != null && capacityRatio >= CAPACITY_MODEST) capacityBand = "modest";
  else if (capacityRatio != null) capacityBand = "at_cap";
  else if (allowedFar == null) capacityBand = "n/a";
  else capacityBand = "unknown";

  const tifBalance = (inc && (num(inc.tif_fund_balance) ?? num(inc.tif_cumulative_revenue))) || 0;
  const incBits = inc
    ? [inc.in_opportunity_zone, inc.in_enterprise_zone, inc.in_qct, inc.in_nmtc, inc.in_tif_district].map(Boolean)
    : [];
  const incentiveCount = incBits.filter(Boolean).length;
  let incentiveStrength: IncentiveStrength;
  if (inc && (inc.in_opportunity_zone || (inc.in_tif_district && tifBalance > TIF_WELL_FUNDED) || incentiveCount >= STACK_MIN))
    incentiveStrength = "strong";
  else if (incentiveCount === 1) incentiveStrength = "some";
  else incentiveStrength = "none";

  const bonusFlags: string[] = [];
  if (reg?.in_tod_area) bonusFlags.push("tod");
  if (reg?.in_adu_area) bonusFlags.push("adu");

  // CALIBRATION FIX: in_aro_zone (~citywide) and violations.total (area-level
  // count, identical across neighbors) are all-checkmarks rows — NOT friction.
  const frictionPairs: [string, boolean][] = reg
    ? [
        ["landmark_dist", !!reg.in_landmark_district],
        ["landmark_bldg", !!reg.is_landmark_building],
        ["historic", !!reg.in_historic_district],
        ["natl_register", !!reg.on_national_register],
        ["pd_overlay", !!reg.in_planned_development],
        ["lakefront", !!reg.in_lakefront_protection],
        ["flood", reg.flood_zone != null && reg.flood_zone !== "X"],
      ]
    : [];
  const frictionFlags = frictionPairs.filter(([, v]) => v).map(([k]) => k);
  const frictionLevel: "meaningful" | "low" = frictionFlags.length >= 1 ? "meaningful" : "low";

  const neutralFlags: string[] = [];
  if (reg?.in_aro_zone) neutralFlags.push("aro");
  if (viol && (num(viol.open_count) ?? 0) > 0) neutralFlags.push("openViolations");

  return {
    allowedFar,
    existingFar,
    capacityRatio,
    capacityBand,
    bldgAreaLowConfidence,
    incentiveStrength,
    incentiveCount,
    tifBalance,
    bonusFlags,
    frictionFlags,
    frictionLevel,
    neutralFlags,
    zoneClass: zdef?.zone_class ?? null,
  };
}

// --- category selection (pure; friction evaluated before incentives) ----------
export function selectCategory(s: VerdictSignals, data: ScorecardResponse): VerdictCategory {
  const prop = data.context?.property ?? null;
  const zdef = data.zone_definition ?? null;

  // insufficient_data ONLY when nothing is reasonable. nearest_parcel_unverified
  // no longer blocks a verdict (zoning is identity-independent → caveated verdict).
  if (!zdef && !prop) return "insufficient_data";

  const zonePrefix = (s.zoneClass ?? "").slice(0, 2);
  if (s.allowedFar == null && (!zdef || zdef.is_fallback || ["PD", "PO", "T"].includes(zonePrefix)))
    return "entitlement_defined";

  // Pushback #2: friction wins the label; incentives/capacity become positive
  // reasons inside "constrained" — they can never mask friction at the label level.
  if (
    s.frictionLevel === "meaningful" &&
    (["high", "vacant_or_teardown", "modest", "unknown"].includes(s.capacityBand) ||
      s.incentiveStrength === "strong" ||
      s.incentiveStrength === "some")
  )
    return "constrained";

  const strongOk =
    ["high", "vacant_or_teardown"].includes(s.capacityBand) && (s.allowedFar ?? 0) >= STRONG_MIN_ALLOWED_FAR;
  if (strongOk && s.frictionLevel === "low") return "strong";

  if (s.incentiveStrength === "strong" && s.frictionLevel === "low" && !strongOk) return "incentive_driven";

  return "limited";
}

function assessConfidence(data: ScorecardResponse, s: VerdictSignals, t: TFunc): { confidence: "high" | "caveated"; caveats: string[] } {
  const caveats: string[] = [];
  if (data.nearest_parcel_unverified) caveats.push(t("scorecard.verdict.caveat.unverified"));
  if (s.bldgAreaLowConfidence && s.capacityBand === "unknown" && data.zone_definition?.far != null)
    caveats.push(t("scorecard.verdict.caveat.noBldgArea"));
  if (data.zone_definition?.is_fallback) caveats.push(t("scorecard.verdict.caveat.fallbackZone"));
  if ((data.partial_failures?.length ?? 0) > 0)
    caveats.push(t("scorecard.verdict.caveat.partial", { sources: data.partial_failures.join(", ") }));

  const caveated =
    !!data.nearest_parcel_unverified ||
    data.resolved_confidence === "approximate" ||
    !!data.zone_definition?.is_fallback ||
    (data.partial_failures?.length ?? 0) > 0;
  return { confidence: caveated ? "caveated" : "high", caveats };
}

// --- reason building (≥1 negative forced when friction meaningful) ------------
function capacityReason(s: VerdictSignals, t: TFunc): VerdictReason | null {
  if (s.allowedFar != null && s.existingFar != null && s.capacityRatio != null && s.capacityRatio >= CAPACITY_MODEST) {
    return {
      text: t("scorecard.verdict.reason.capacity", {
        allowed: s.allowedFar.toFixed(1),
        existing: s.existingFar.toFixed(1),
        ratio: s.capacityRatio.toFixed(1),
      }),
      polarity: "positive",
      cardAnchor: "zoning",
    };
  }
  if (s.capacityBand === "vacant_or_teardown") {
    return { text: t("scorecard.verdict.reason.vacant", { allowed: (s.allowedFar ?? 0).toFixed(1) }), polarity: "positive", cardAnchor: "zoning" };
  }
  return null;
}

function incentiveReasons(s: VerdictSignals, data: ScorecardResponse, t: TFunc): VerdictReason[] {
  const inc = data.context?.incentives ?? null;
  if (!inc) return [];
  const out: VerdictReason[] = [];
  if (inc.in_opportunity_zone) out.push({ text: t("scorecard.verdict.reason.oz"), polarity: "positive", cardAnchor: "incentives" });
  if (inc.in_tif_district)
    out.push({
      text: s.tifBalance > 0 ? t("scorecard.verdict.reason.tifFunded", { name: inc.tif_name ?? "", balance: compactUsd(s.tifBalance) }) : t("scorecard.verdict.reason.tif", { name: inc.tif_name ?? "" }),
      polarity: "positive",
      cardAnchor: "incentives",
    });
  if (inc.in_enterprise_zone) out.push({ text: t("scorecard.verdict.reason.ez"), polarity: "positive", cardAnchor: "incentives" });
  if (inc.in_qct || inc.in_nmtc) out.push({ text: t("scorecard.verdict.reason.distressIncentive"), polarity: "positive", cardAnchor: "incentives" });
  return out;
}

function bonusReason(s: VerdictSignals, t: TFunc): VerdictReason | null {
  if (s.bonusFlags.includes("tod")) return { text: t("scorecard.verdict.reason.tod"), polarity: "positive", cardAnchor: "regulatory" };
  if (s.bonusFlags.includes("adu")) return { text: t("scorecard.verdict.reason.adu"), polarity: "positive", cardAnchor: "regulatory" };
  return null;
}

function frictionReasons(s: VerdictSignals, data: ScorecardResponse, t: TFunc): VerdictReason[] {
  const reg = data.context?.regulatory ?? null;
  const out: VerdictReason[] = [];
  const has = (f: string) => s.frictionFlags.includes(f);
  if (has("landmark_dist") || has("landmark_bldg")) out.push({ text: t("scorecard.verdict.reason.landmark"), polarity: "negative", cardAnchor: "regulatory" });
  if (has("historic") || has("natl_register")) out.push({ text: t("scorecard.verdict.reason.historic"), polarity: "negative", cardAnchor: "regulatory" });
  if (has("flood") && reg?.flood_zone) out.push({ text: t("scorecard.verdict.reason.flood", { zone: reg.flood_zone }), polarity: "negative", cardAnchor: "regulatory" });
  if (has("lakefront")) out.push({ text: t("scorecard.verdict.reason.lakefront"), polarity: "negative", cardAnchor: "regulatory" });
  if (has("pd_overlay")) out.push({ text: t("scorecard.verdict.reason.pdOverlay"), polarity: "negative", cardAnchor: "regulatory" });
  return out;
}

function zoneReason(s: VerdictSignals, data: ScorecardResponse, t: TFunc): VerdictReason {
  const zdef = data.zone_definition;
  if (zdef?.far != null)
    return { text: t("scorecard.verdict.reason.asOfRight", { zone: s.zoneClass ?? "", allowed: zdef.far.toFixed(1) }), polarity: "neutral", cardAnchor: "zoning" };
  return { text: t("scorecard.verdict.reason.zoned", { zone: s.zoneClass ?? "" }), polarity: "neutral", cardAnchor: "zoning" };
}

function buildReasons(category: VerdictCategory, s: VerdictSignals, data: ScorecardResponse, t: TFunc): VerdictReason[] {
  const cap = capacityReason(s, t);
  const inc = incentiveReasons(s, data, t);
  const bonus = bonusReason(s, t);
  const friction = frictionReasons(s, data, t);
  let out: VerdictReason[] = [];

  switch (category) {
    case "strong":
      if (cap) out.push(cap);
      out.push(...inc.slice(0, 1));
      if (bonus && out.length < 3) out.push(bonus);
      if (out.length === 0) out.push(zoneReason(s, data, t));
      break;
    case "incentive_driven":
      out.push(...inc.slice(0, 2));
      if (bonus && out.length < 3) out.push(bonus);
      if (out.length < 2) out.push(zoneReason(s, data, t));
      break;
    case "constrained": {
      // positives first (capacity / incentives), then the FORCED friction negative(s)
      if (cap) out.push(cap);
      out.push(...inc.slice(0, cap ? 1 : 2));
      if (out.length === 0) out.push(zoneReason(s, data, t));
      out.push(...friction.slice(0, 2));
      break;
    }
    case "limited":
      out.push(zoneReason(s, data, t));
      if (s.capacityRatio != null) out.push({ text: t("scorecard.verdict.reason.nearCapacity"), polarity: "neutral", cardAnchor: "zoning" });
      if (bonus) out.push(bonus);
      out.push({ text: t("scorecard.verdict.reason.compsPointer"), polarity: "neutral", cardAnchor: "comparables" });
      break;
    case "entitlement_defined":
      out.push({ text: t("scorecard.verdict.reason.entitlement", { name: s.zoneClass ?? "" }), polarity: "neutral", cardAnchor: "zoning" });
      out.push(...inc.slice(0, 1));
      out.push(...friction.slice(0, 1));
      break;
    case "insufficient_data":
      out.push({ text: t("scorecard.verdict.reason.insufficient"), polarity: "neutral", cardAnchor: "property" });
      break;
  }

  // honesty guard: meaningful friction MUST surface ≥1 negative, whatever the label
  if (s.frictionLevel === "meaningful" && !out.some((r) => r.polarity === "negative") && friction.length)
    out.push(friction[0]);

  // NB: ARO is deliberately NOT auto-added as a reason — it's citywide, so it
  // would be noise on every verdict. It lives in the incentives card + signals.
  return out.slice(0, 4);
}

// --- next step (one mapped action per category) -------------------------------
function buildNextStep(category: VerdictCategory, s: VerdictSignals, data: ScorecardResponse, t: TFunc): VerdictNextStep {
  const addr = data.address ?? data.context?.property?.address ?? "";
  const inc = data.context?.incentives ?? null;
  switch (category) {
    case "strong":
      return {
        kind: "chat",
        label: t("scorecard.verdict.next.strong.label"),
        question: t("scorecard.verdict.next.strong.question", { addr }),
      };
    case "incentive_driven":
      return {
        kind: "chat",
        label: t("scorecard.verdict.next.incentive.label"),
        question:
          inc?.in_tif_district && inc.tif_name
            ? t("scorecard.verdict.next.incentive.tifQuestion", { name: inc.tif_name })
            : t("scorecard.verdict.next.incentive.question", { addr }),
      };
    case "constrained": {
      const f = s.frictionFlags;
      const frictionKey =
        f.includes("landmark_dist") || f.includes("landmark_bldg") || f.includes("historic") || f.includes("natl_register")
          ? "landmark"
          : f.includes("flood")
          ? "flood"
          : f.includes("pd_overlay")
          ? "pd"
          : "overlay";
      return {
        kind: "chat",
        label: t("scorecard.verdict.next.constrained.label"),
        question: t(`scorecard.verdict.next.constrained.${frictionKey}Question`, { addr }),
      };
    }
    case "limited":
      return {
        kind: "scroll",
        label: t("scorecard.verdict.next.limited.label"),
        cardAnchor: "comparables",
      };
    case "entitlement_defined":
      return {
        kind: "chat",
        label: t("scorecard.verdict.next.entitlement.label"),
        question: t("scorecard.verdict.next.entitlement.question", { name: s.zoneClass ?? "", addr }),
      };
    case "insufficient_data":
      return { kind: "scroll", label: t("scorecard.verdict.next.insufficient.label"), cardAnchor: "property" };
  }
}

export function computeVerdict(data: ScorecardResponse, t: TFunc): ScorecardVerdict {
  const signals = deriveSignals(data);
  const category = selectCategory(signals, data);
  const reasons = buildReasons(category, signals, data, t);
  const nextStep = buildNextStep(category, signals, data, t);
  const { confidence, caveats } = assessConfidence(data, signals, t);
  return {
    category,
    headline: t(`scorecard.verdict.headline.${category}`),
    reasons,
    nextStep,
    confidence,
    caveats,
    signals,
  };
}
