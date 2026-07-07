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
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
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
  onChat: (question: string) => void;
  onScrollTo: (anchor: CardId) => void;
}

export function VerdictBand({ verdict, footer, onChat, onScrollTo }: VerdictBandProps) {
  const { t } = useTranslation("pages");
  const tone = TONE[verdict.category];

  // Single orange next-step only — the paid report lives in its own violet
  // strip below (no money action inside the verdict).
  function runStep(step: ScorecardVerdict["nextStep"]) {
    if (step.kind === "chat" && step.question) onChat(step.question);
    else if (step.kind === "scroll" && step.cardAnchor) onScrollTo(step.cardAnchor);
  }

  // The phrase explains itself on hover/tap (tooltip rule: definitions never
  // live as on-page copy) — plain-English gloss per category, scoring untouched.
  // Trigger is a small ⓘ AFTER the phrase: a dotted underline under a headline
  // read as broken styling (Jack, 2026-07-07), so the body-text idiom stays in
  // body text and headlines get the icon.
  const explain = t(`scorecard.verdict.explain.${verdict.category}`, { defaultValue: "" });

  return (
    <section aria-label={t("scorecard.verdict.ariaLabel")} className="mb-6 max-w-3xl">
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

      {/* Reasons — defended, each deep-links to its evidence module */}
      <ul className="space-y-1.5 mb-4">
        {verdict.reasons.map((r, i) => (
          <li key={i}>
            <button
              type="button"
              onClick={() => onScrollTo(r.cardAnchor)}
              className="group w-full flex items-start gap-2 text-left text-caption text-text-secondary hover:text-text-primary transition-colors"
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

      {/* The single next step — one orange action, no money CTA in the verdict */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => runStep(verdict.nextStep)}
          className="px-4 py-2 text-title rounded-lg transition-colors bg-action hover:bg-action-hover text-action-fg"
        >
          {verdict.nextStep.label}
        </button>
      </div>

      {/* Caveats — honesty folded INTO the verdict, not a separate banner */}
      {verdict.caveats.length > 0 && (
        <div className="mt-4 space-y-1">
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
