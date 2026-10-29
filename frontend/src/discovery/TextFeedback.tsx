// What the free-text box made of the phrase, said plainly. The text box is a rule-based
// compiler covering a few dozen phrases; it drops what it does not recognize, so the page
// has to say which words did nothing (redesign Phase 2).
//
// Two states, and only these:
//   notice   the compiler understood none of the phrase and nothing else was set, so NO search
//            ran (the previous results are untouched). Comes from the compile-only preview.
//   result   after a search, what the EVALUATED query took from the text: the filters whose
//            source is "text" and the words left over, both read from response.cqs (INV-4).
//            Never from a guess made before sending.

import { useTranslation } from "react-i18next";
import { chipLabel } from "./chips";
import type { CQS, Registry } from "./types";

interface Props {
  registry: Registry;
  notice: { text: string; words: string[] } | null;
  /** The evaluated query and the text that was sent with it (null before the first search). */
  applied: { cqs: CQS; text: string } | null;
  className?: string;
}

export function TextFeedback({ registry, notice, applied, className = "" }: Props) {
  const { t } = useTranslation("pages");

  if (notice) {
    return (
      <p role="status" data-testid="discovery-text-feedback" data-kind="none" className={`text-caption text-text-secondary ${className}`}>
        {t("discovery.text.noneUnderstood", { text: notice.text })}
        {notice.words.length > 0 && <> {t("discovery.text.notUnderstood", { words: notice.words.join(", ") })}</>}{" "}
        {t("discovery.text.tryExample", { example: t("discovery.text.example") })}
      </p>
    );
  }

  const text = applied?.text.trim();
  if (!applied || !text) return null;
  const fromText = Object.entries(applied.cqs.filters).filter(([, a]) => a.source === "text");
  const words = applied.cqs.meta.textResidual ?? [];
  if (fromText.length > 0 && words.length === 0) return null; // fully understood: the chips already say it
  const understood = fromText
    .map(([id, a]) => chipLabel(id, a.predicate, registry.filters.find((f) => f.id === id)))
    .join("; ");
  return (
    <p role="status" data-testid="discovery-text-feedback" data-kind="partial" className={`text-caption text-text-secondary ${className}`}>
      {fromText.length > 0
        ? t("discovery.text.understood", { text, filters: understood })
        : t("discovery.text.understoodNothing", { text })}
      {words.length > 0 && <> {t("discovery.text.notUnderstood", { words: words.join(", ") })}</>}
    </p>
  );
}
