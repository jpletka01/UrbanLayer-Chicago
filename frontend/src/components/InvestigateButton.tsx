import { Link } from "react-router-dom";
import { track } from "../lib/tracking";

// Two shapes: "inline" (compact text link — chat sidebar contexts) and "chip"
// (bordered button — Scorecard page, where the grounded-chat handoff is a primary
// feature and micro links under-sold it).
const VARIANT = {
  inline: "group inline-flex items-center gap-1 text-micro text-text-secondary hover:text-accent transition-colors",
  chip: "group inline-flex items-center gap-1.5 text-caption text-text-secondary bg-dark-surface border border-dark-border rounded-lg px-2.5 py-1.5 hover:text-accent hover:border-accent/50 transition-colors",
} as const;

export function InvestigateButton({ question, label, cardName, pin, variant = "inline", onAsk }: {
  question: string; label: string; cardName?: string; pin?: string | null;
  variant?: keyof typeof VARIANT;
  /** Answer in place (Scorecard quick-chat dock) instead of navigating to the
   *  full workspace. When set, the question opens/sends in the dock — the
   *  page, and its scroll position, stay put. */
  onAsk?: (question: string) => void;
}) {
  const inner = (
    <>
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
      </svg>
      {label}
      <span aria-hidden className="opacity-0 group-hover:opacity-100 transition-opacity">→</span>
    </>
  );
  if (onAsk) {
    return (
      <button
        type="button"
        onClick={() => {
          track("investigate_click", { card_name: cardName ?? label });
          onAsk(question);
        }}
        className={VARIANT[variant]}
      >
        {inner}
      </button>
    );
  }
  return (
    <Link
      to={`/?q=${encodeURIComponent(question)}${pin ? `&pin=${pin}` : ""}`}
      onClick={() => track("investigate_click", { card_name: cardName ?? label })}
      className={VARIANT[variant]}
    >
      {inner}
    </Link>
  );
}
