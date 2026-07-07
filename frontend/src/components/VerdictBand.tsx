import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { InfoTooltip } from "./InfoTooltip";
import type { ScorecardVerdict, VerdictCategory, CardId, ReasonPolarity } from "../lib/scorecardVerdict";

// The verdict lead — the Property Profile's conclusion, de-carded (2026-07-07):
// headline with a tone dot, card-linked reasons, ONE next step, honest caveats,
// and the methodology disclosure. Identity lives in the page's identity bar and
// the numbers live in the KPI strip — this block is purely the narrative layer.
// Verdict logic is calibrated and untouched (scorecardVerdict.ts).

// One tone dot per verdict encodes favorability (genuine state, not rainbow chrome).
const TONE: Record<VerdictCategory, { dot: string }> = {
  strong: { dot: "bg-state-positive" },
  incentive_driven: { dot: "bg-accent" },
  constrained: { dot: "bg-state-warning" },
  limited: { dot: "bg-text-muted" },
  entitlement_defined: { dot: "bg-text-muted" },
  insufficient_data: { dot: "bg-text-muted" },
};

/** Tone dot for external condensed renderings (sticky verdict strip). */
export function verdictDotClass(category: VerdictCategory): string {
  return TONE[category].dot;
}

// Reason rows wear the same tag chrome as the Regulatory module's
// opportunity/constraint pills (Jack, 2026-07-07): green tint for positives,
// amber + warning glyph for non-positives, muted for neutral — one visual
// language for "signals about this parcel" across the page.
const REASON_TONE: Record<ReasonPolarity, string> = {
  positive: "border-state-positive/25 bg-state-positive/5",
  negative: "border-state-warning/25 bg-state-warning/5",
  neutral: "border-dark-border bg-dark-elevated/40",
};

function ReasonGlyph({ polarity }: { polarity: ReasonPolarity }) {
  if (polarity === "positive")
    return (
      <svg className="w-3.5 h-3.5 text-state-positive shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2} aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
      </svg>
    );
  if (polarity === "negative")
    return (
      <svg className="w-3.5 h-3.5 text-state-warning shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
      </svg>
    );
  return <span className="w-1.5 h-1.5 rounded-full bg-text-muted shrink-0 mt-1.5" aria-hidden />;
}

// Kept for the sticky strip's tile rendering (page-level).
export interface VerdictTile {
  anchor: CardId;
  label: string;
  value: string;
  sub?: string;
}

export interface VerdictBandProps {
  verdict: ScorecardVerdict;
  /** Quiet trailing row (accuracy feedback) — the verdict is the claim, so the
   *  "is this accurate?" affordance lives with it. */
  footer?: ReactNode;
  onScrollTo: (anchor: CardId) => void;
}

// The next step no longer renders here: the page composes ONE hero action row
// (violet report CTA + this step as a chip) so two filled buttons never stack.

export function VerdictBand({ verdict, footer, onScrollTo }: VerdictBandProps) {
  const { t } = useTranslation("pages");
  const tone = TONE[verdict.category];

  // The phrase explains itself on hover/tap (tooltip rule: definitions never
  // live as on-page copy) — plain-English gloss per category, scoring untouched.
  // Trigger is a small ⓘ AFTER the phrase: a dotted underline under a headline
  // read as broken styling (Jack, 2026-07-07), so the body-text idiom stays in
  // body text and headlines get the icon.
  const explain = t(`scorecard.verdict.explain.${verdict.category}`, { defaultValue: "" });

  return (
    <section aria-label={t("scorecard.verdict.ariaLabel")} className="max-w-3xl">
      {/* Headline — the conclusion, leading; tone rides the dot, not the chrome */}
      <div className="flex items-start gap-3 mb-3">
        <h2 className="text-lead text-text-primary flex items-baseline gap-2.5">
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 self-center ${tone.dot}`} aria-hidden />
          {verdict.headline}
          {explain && (
            <InfoTooltip content={{ label: verdict.headline, description: explain, bullets: [] }}>
              <svg className="w-4 h-4 self-center text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-label={explain}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12v-.008z" />
              </svg>
            </InfoTooltip>
          )}
        </h2>
        {verdict.confidence === "caveated" && (
          <span className="text-micro text-state-warning border border-state-warning/30 bg-state-warning/10 rounded-md px-2 py-0.5 shrink-0 mt-1.5">
            {t("scorecard.verdict.caveatedBadge")}
          </span>
        )}
      </div>

      {/* Reasons — defended, each deep-links to its evidence module; tag
          chrome matches the Regulatory pills (one signal language site-wide) */}
      <ul className="flex flex-col gap-1.5 items-start">
        {verdict.reasons.map((r, i) => (
          <li key={i} className="max-w-full">
            <button
              type="button"
              onClick={() => onScrollTo(r.cardAnchor)}
              className={`group inline-flex items-start gap-2 text-left rounded-md border px-2.5 py-1.5 text-caption text-text-primary hover:border-dark-border-strong transition-colors ${REASON_TONE[r.polarity]}`}
              title={t("scorecard.verdict.jumpToEvidence")}
            >
              <ReasonGlyph polarity={r.polarity} />
              <span className="leading-snug">
                {r.text}
                <span aria-hidden className="ml-1 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity">→</span>
              </span>
            </button>
          </li>
        ))}
      </ul>

      {/* Caveats — honesty folded INTO the verdict, not a separate banner */}
      {verdict.caveats.length > 0 && (
        <div className="mt-3 space-y-1">
          {verdict.caveats.map((c, i) => (
            <p key={i} className="text-micro text-state-warning flex items-start gap-1.5">
              <span className="w-1 h-1 rounded-full bg-state-warning mt-1.5 shrink-0" aria-hidden />
              {c}
            </p>
          ))}
        </div>
      )}

      {footer && <div className="mt-3">{footer}</div>}
    </section>
  );
}

/** Methodology disclosure — the signal table behind the verdict. Rendered by
    the page in the provenance zone (meta line), NOT between the verdict's
    action and the report button (it's provenance, not a next step). */
export function VerdictMethodology({ verdict }: { verdict: ScorecardVerdict }) {
  const { t } = useTranslation("pages");
  return (
    <details className="group">
      <summary className="text-micro text-text-muted cursor-pointer hover:text-text-secondary transition-colors list-none inline-flex items-center gap-1">
        <span className="transition-transform group-open:rotate-90" aria-hidden>›</span>
        {t("scorecard.verdict.howScored")}
      </summary>
      <dl className="mt-2 pl-3 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-micro max-w-xl">
        <Row label={t("scorecard.verdict.signal.zone")} value={verdict.signals.zoneClass ?? "—"} />
        <Row label={t("scorecard.verdict.signal.allowedFar")} value={verdict.signals.allowedFar?.toFixed(1) ?? t("scorecard.verdict.signal.entitlementDefined")} />
        <Row
          label={t("scorecard.verdict.signal.existingFar")}
          value={verdict.signals.existingFar?.toFixed(2) ?? t("scorecard.verdict.signal.unavailable")}
        />
        <Row label={t("scorecard.verdict.signal.capacity")} value={t(`scorecard.verdict.band.${verdict.signals.capacityBand}`)} />
        <Row label={t("scorecard.verdict.signal.incentives")} value={t(`scorecard.verdict.strength.${verdict.signals.incentiveStrength}`, { count: verdict.signals.incentiveCount })} />
        <Row
          label={t("scorecard.verdict.signal.friction")}
          value={verdict.signals.frictionFlags.length ? verdict.signals.frictionFlags.length.toString() : t("scorecard.verdict.signal.none")}
        />
      </dl>
      <p className="mt-2 pl-3 text-micro text-text-muted leading-snug max-w-xl">{t("scorecard.verdict.howScoredNote")}</p>
    </details>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-text-muted">{label}</dt>
      <dd className="text-text-secondary font-mono text-right">{value}</dd>
    </div>
  );
}
