import { useState } from "react";
import { useTranslation } from "react-i18next";
import { track, flush } from "../lib/tracking";

// Per-Scorecard accuracy micro-feedback. Accuracy is the trust moat — a user
// who catches a data error must have a one-click way to say so. Events carry
// the page's tracked address, so a 👎 arrives with the parcel attached.
// Mount with key={pin ?? address} so state resets per parcel.

export function ScorecardFeedback() {
  const { t } = useTranslation("pages");
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState(false);

  const castVote = (v: "up" | "down") => {
    setVote(v);
    track("scorecard_feedback", { kind: "vote", vote: v });
  };

  const submitComment = () => {
    const text = comment.trim();
    if (text) {
      track("scorecard_feedback", { kind: "comment", vote, comment: text.slice(0, 1000) });
      flush();
    }
    setSent(true);
  };

  if (sent) {
    return (
      <div className="mt-4 rounded-bento-sm border border-dark-border bg-dark-surface px-4 py-3 text-caption text-text-secondary">
        {t("scorecard.feedback.thanks")}
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-bento-sm border border-dark-border bg-dark-surface px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-caption text-text-secondary">
          {t("scorecard.feedback.question")}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => castVote("up")}
            aria-pressed={vote === "up"}
            className={`rounded-md border px-2.5 py-1 text-caption transition-colors ${
              vote === "up"
                ? "border-accent text-text-primary"
                : "border-dark-border text-text-secondary hover:border-accent hover:text-text-primary"
            }`}
          >
            👍 {t("scorecard.feedback.up")}
          </button>
          <button
            onClick={() => castVote("down")}
            aria-pressed={vote === "down"}
            className={`rounded-md border px-2.5 py-1 text-caption transition-colors ${
              vote === "down"
                ? "border-accent text-text-primary"
                : "border-dark-border text-text-secondary hover:border-accent hover:text-text-primary"
            }`}
          >
            👎 {t("scorecard.feedback.down")}
          </button>
        </div>
      </div>
      {vote && (
        <div className="flex gap-2 mt-3">
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitComment()}
            placeholder={t("scorecard.feedback.placeholder")}
            maxLength={1000}
            className="flex-1 rounded-lg bg-dark-elevated border border-dark-border px-3 py-1.5 text-caption text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
          />
          <button
            onClick={submitComment}
            className="rounded-lg border border-dark-border px-3 py-1.5 text-caption text-text-secondary hover:border-accent hover:text-text-primary transition-colors"
          >
            {t("scorecard.feedback.submit")}
          </button>
        </div>
      )}
    </div>
  );
}
