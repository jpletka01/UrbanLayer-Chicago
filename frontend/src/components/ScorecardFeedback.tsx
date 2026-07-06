import { useState } from "react";
import { useTranslation } from "react-i18next";
import { track, flush } from "../lib/tracking";

// Per-Scorecard accuracy micro-feedback. Accuracy is the trust moat — a user
// who catches a data error must have a one-click way to say so. Lives in the
// decision card's footer (VerdictBand `footer` slot): the verdict is the
// claim, so the "is this accurate?" affordance sits with it. Events carry the
// page's tracked address, so a thumbs-down arrives with the parcel attached.
// Mount with key={pin ?? address} so state resets per parcel.

function ThumbIcon({ down = false }: { down?: boolean }) {
  // Feather thumbs-up path; the down variant is the same mark rotated —
  // keeps the two glyphs visually identical in weight.
  return (
    <svg
      className={`w-3.5 h-3.5 ${down ? "rotate-180" : ""}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"
      />
    </svg>
  );
}

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
    return <p className="text-micro text-text-muted">{t("scorecard.feedback.thanks")}</p>;
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <span className="text-micro text-text-muted">{t("scorecard.feedback.question")}</span>
      <div className="flex gap-1.5">
        <button
          onClick={() => castVote("up")}
          aria-pressed={vote === "up"}
          aria-label={t("scorecard.feedback.up")}
          title={t("scorecard.feedback.up")}
          className={`rounded-md border p-1.5 transition-colors ${
            vote === "up"
              ? "border-accent text-accent"
              : "border-dark-border text-text-muted hover:border-accent hover:text-text-primary"
          }`}
        >
          <ThumbIcon />
        </button>
        <button
          onClick={() => castVote("down")}
          aria-pressed={vote === "down"}
          aria-label={t("scorecard.feedback.down")}
          title={t("scorecard.feedback.down")}
          className={`rounded-md border p-1.5 transition-colors ${
            vote === "down"
              ? "border-accent text-accent"
              : "border-dark-border text-text-muted hover:border-accent hover:text-text-primary"
          }`}
        >
          <ThumbIcon down />
        </button>
      </div>
      {vote && (
        <div className="flex gap-2 flex-1 min-w-[220px]">
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
