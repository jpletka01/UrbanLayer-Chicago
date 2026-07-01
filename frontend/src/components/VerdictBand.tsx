import { useTranslation } from "react-i18next";
import type { ScorecardVerdict, VerdictCategory, CardId, ReasonPolarity } from "../lib/scorecardVerdict";

// The Verdict Band — leads the Scorecard with a conclusion, supports it with
// card-linked evidence, and commits to ONE next step. Replaces the old
// facts-only flag line (which restated cards without concluding anything).
// Skill basis: quiz-and-assessment-design (actionable segmentation, one mapped
// next step) + comparison-tool-design (honest recommendation — negatives inline,
// methodology disclosed). Bespoke hero element, like the parcel identity band.

// One tone accent per band encodes favorability (genuine state, not rainbow chrome).
const TONE: Record<VerdictCategory, { bar: string; dot: string }> = {
  strong: { bar: "border-l-state-positive", dot: "bg-state-positive" },
  incentive_driven: { bar: "border-l-accent", dot: "bg-accent" },
  constrained: { bar: "border-l-state-warning", dot: "bg-state-warning" },
  limited: { bar: "border-l-dark-border-strong", dot: "bg-text-muted" },
  entitlement_defined: { bar: "border-l-dark-border-strong", dot: "bg-text-muted" },
  insufficient_data: { bar: "border-l-state-warning", dot: "bg-text-muted" },
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
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
      </svg>
    );
  return <span className="w-1.5 h-1.5 rounded-full bg-text-muted shrink-0 mt-1.5" aria-hidden />;
}

// A stat tile in the band's evidence rail: the number that justifies the verdict,
// deep-linking to its evidence card (same anchor mechanism as reasons).
export interface VerdictTile {
  anchor: CardId;
  label: string;
  value: string;
  sub?: string;
}

export interface VerdictBandProps {
  verdict: ScorecardVerdict;
  tiles?: VerdictTile[];
  onChat: (question: string) => void;
  onScrollTo: (anchor: CardId) => void;
}

export function VerdictBand({ verdict, tiles, onChat, onScrollTo }: VerdictBandProps) {
  const { t } = useTranslation("pages");
  const tone = TONE[verdict.category];

  // Single azure next-step only — the paid report lives in its own terracotta
  // ReportCTACard below the band (no money action inside the verdict). See #4.
  function runStep(step: ScorecardVerdict["nextStep"]) {
    if (step.kind === "chat" && step.question) onChat(step.question);
    else if (step.kind === "scroll" && step.cardAnchor) onScrollTo(step.cardAnchor);
  }

  const primaryClasses = "bg-action hover:bg-action-hover text-action-fg";

  const showTiles = !!tiles && tiles.length >= 2;

  return (
    <section
      aria-label={t("scorecard.verdict.ariaLabel")}
      className={`mb-6 bg-dark-surface border border-dark-border ${tone.bar} border-l-4 rounded-xl shadow-card overflow-hidden`}
    >
      {/* Two zones: the verdict narrative (left) + the numbers that justify it (right).
          The band owns its full width in every state — no empty flank. */}
      <div className={showTiles ? "grid lg:grid-cols-[minmax(0,1fr)_minmax(300px,360px)]" : ""}>
      <div className="p-5">
      {/* Headline — the conclusion, leading */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <h2 className="text-lead text-text-primary">{verdict.headline}</h2>
        {verdict.confidence === "caveated" && (
          <span className="text-micro text-state-warning border border-state-warning/30 bg-state-warning/10 rounded-md px-2 py-0.5 shrink-0">
            {t("scorecard.verdict.caveatedBadge")}
          </span>
        )}
      </div>

      {/* Reasons — defended, each deep-links to its evidence card */}
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

      {/* The single next step — one azure action, no money CTA in the band */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => runStep(verdict.nextStep)}
          className={`px-4 py-2 text-title rounded-lg transition-colors ${primaryClasses}`}
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

      {/* Methodology disclosure — cheap, critical for the attorney persona */}
      <details className="mt-3 group">
        <summary className="text-micro text-text-muted cursor-pointer hover:text-text-secondary transition-colors list-none inline-flex items-center gap-1">
          <span className="transition-transform group-open:rotate-90" aria-hidden>›</span>
          {t("scorecard.verdict.howScored")}
        </summary>
        <dl className="mt-2 pl-3 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-micro">
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
        <p className="mt-2 pl-3 text-micro text-text-muted leading-snug">{t("scorecard.verdict.howScoredNote")}</p>
      </details>
      </div>

      {/* Evidence rail — the verdict's numbers as clickable stat tiles */}
      {showTiles && (
        <div className="border-t lg:border-t-0 lg:border-l border-dark-border-subtle bg-dark-elevated/40 p-3 grid grid-cols-2 gap-2 content-center">
          {tiles!.map((tile) => (
            <button
              key={tile.anchor + tile.label}
              type="button"
              onClick={() => onScrollTo(tile.anchor)}
              title={t("scorecard.verdict.jumpToEvidence")}
              className="group text-left rounded-lg border border-dark-border bg-dark-surface hover:border-dark-border-strong p-3 transition-colors"
            >
              <div className="text-overline uppercase text-text-muted">{tile.label}</div>
              <div className="text-subtitle text-text-primary mt-1 truncate">{tile.value}</div>
              {tile.sub && <div className="text-micro text-text-muted mt-0.5 leading-snug">{tile.sub}</div>}
            </button>
          ))}
        </div>
      )}
      </div>
    </section>
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
