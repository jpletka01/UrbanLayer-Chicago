// ConfidenceState — the one component that says how far to trust a figure (decision Item 49).
// The truth rules (guides/source-confidence.md) are unchanged; only their medium changes: the
// STATE is a short visible label with its own glyph, and the explanation (method, source, date,
// why it is withheld) opens in a click toggletip instead of a paragraph on the page.
//
//   Estimate ≈ · Low confidence ≈ (amber, the one amber phrase) · Not checked ◌ · None found ∅ ·
//   Withheld ⊘ (the value itself shows "—" plus a reason of 8 words or fewer) · N/A –
//
// A verified, standard figure renders nothing. "Not checked" and "None found" never share a word
// or a glyph: "nothing" never reads as "no".
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { ConfidenceKind } from "../../lib/confidence";
import { StatusLabel, type StatusTone } from "./StatusLabel";
import { Toggletip } from "./Toggletip";

const GLYPH: Record<ConfidenceKind, string> = {
  estimate: "≈",
  not_checked: "◌",
  none_found: "∅",
  withheld: "⊘",
  na: "–",
};

export function ConfidenceState({
  kind,
  low = false,
  tone,
  explanation,
  explainLabel,
}: {
  kind: ConfidenceKind;
  /** An estimate the backend marked low: reads "Low confidence" in amber (guide §3). */
  low?: boolean;
  /** Override the default tone: amber for a Not-checked input that changes the answer. */
  tone?: StatusTone;
  /** What opens behind ⓘ: the method, source, date or reason in full. */
  explanation?: ReactNode;
  /** Names the figure for the ⓘ button ("Assessed value"). */
  explainLabel?: string;
}) {
  const { t } = useTranslation("common");
  const word = kind === "estimate" && low ? t("confidence.kind.low") : t(`confidence.kind.${kind}`);
  const resolvedTone: StatusTone = tone ?? (low ? "warning" : "neutral");
  return (
    <span className="inline-flex items-center gap-1" data-confidence-state={low ? "low" : kind}>
      <StatusLabel tone={resolvedTone} glyph={GLYPH[kind]}>{word}</StatusLabel>
      {explanation != null && (
        <Toggletip kind="info" label={t("confidence.kind.explain", { label: explainLabel ?? word })}>
          {explanation}
        </Toggletip>
      )}
    </span>
  );
}
