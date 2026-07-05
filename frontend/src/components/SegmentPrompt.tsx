import { useState } from "react";
import { useTranslation } from "react-i18next";
import { track } from "../lib/tracking";

// One-question segment self-identification — the single highest-value datum
// for customer validation ("who is actually showing up?"). Asks once per
// browser; an answer or a dismiss both silence it permanently.

const SEGMENTS = [
  "developer",
  "architect",
  "attorney",
  "broker",
  "investor",
  "homeowner",
  "curious",
] as const;

const STORAGE_KEY = "ul_segment";

function storedState(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return "unavailable";
  }
}

export function SegmentPrompt() {
  const { t } = useTranslation("pages");
  const [state, setState] = useState<"open" | "thanks" | "hidden">(() =>
    storedState() ? "hidden" : "open",
  );

  if (state === "hidden") return null;

  const remember = (value: string) => {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // still track; just may re-ask next visit
    }
  };

  const choose = (segment: string) => {
    remember(segment);
    track("segment_selected", { segment });
    setState("thanks");
  };

  const dismiss = () => {
    remember("dismissed");
    track("segment_selected", { segment: "dismissed" });
    setState("hidden");
  };

  if (state === "thanks") {
    return (
      <div className="mt-6 rounded-bento-sm border border-dark-border bg-dark-surface px-4 py-3 text-caption text-text-secondary">
        {t("scorecard.segmentPrompt.thanks")}
      </div>
    );
  }

  return (
    <div className="mt-6 rounded-bento-sm border border-dark-border bg-dark-surface px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-caption font-semibold text-text-primary">
            {t("scorecard.segmentPrompt.question")}
          </p>
          <p className="text-micro text-text-muted mt-0.5">
            {t("scorecard.segmentPrompt.hint")}
          </p>
        </div>
        <button
          onClick={dismiss}
          aria-label={t("scorecard.segmentPrompt.dismiss")}
          className="shrink-0 text-text-muted hover:text-text-secondary transition-colors leading-none text-lg"
        >
          ×
        </button>
      </div>
      <div className="flex flex-wrap gap-2 mt-3">
        {SEGMENTS.map((s) => (
          <button
            key={s}
            onClick={() => choose(s)}
            className="rounded-md border border-dark-border px-2.5 py-1 text-caption text-text-secondary hover:border-accent hover:text-text-primary transition-colors"
          >
            {t(`scorecard.segmentPrompt.options.${s}`)}
          </button>
        ))}
      </div>
    </div>
  );
}
