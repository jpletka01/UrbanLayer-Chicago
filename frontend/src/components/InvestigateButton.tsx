import { Link } from "react-router-dom";
import { MessageCircleQuestion } from "lucide-react";
import { track } from "../lib/tracking";

// Two shapes: "inline" (compact text link — chat sidebar contexts) and "chip"
// (bordered button — Scorecard page, where the grounded-chat handoff is a primary
// feature and micro links under-sold it).
const VARIANT = {
  inline: "group inline-flex items-center gap-1 text-micro text-text-secondary hover:text-accent transition-colors",
  // The Profile's secondary button (decision Item 54): an orange outline and orange text, so it reads as
  // clickable against the dark card. The near-black border it had matched the surface.
  chip: "group inline-flex h-9 items-center gap-1.5 rounded-lg border border-link px-3 text-caption font-medium text-link cursor-pointer hover:bg-accent-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
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
      <MessageCircleQuestion aria-hidden className={variant === "chip" ? "h-4 w-4" : "h-3 w-3"} strokeWidth={2} />
      {label}
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
