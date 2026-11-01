// StatusLabel — the informational half of the shape grammar (decision Item 49). Small (≤22px),
// 2-4px radius, a tinted fill plus a glyph, no border, not focusable, no pointer: it can never be
// mistaken for a Button. Tone is a ROLE: `warning` only for something the user should check or act
// on, `danger` for a blocker, `neutral` for information (a verdict category is neutral, never
// amber). Color is never the only signal (WCAG 1.4.1): every tone carries its glyph.
// If a status needs an action, put a Button or link beside the label, never inside it.
import type { ReactNode } from "react";

export type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";

const TONE: Record<StatusTone, string> = {
  neutral: "bg-status-neutral-subtle text-text-secondary",
  info: "bg-status-info-subtle text-status-info",
  success: "bg-status-success-subtle text-status-success",
  warning: "bg-status-warning-subtle text-status-warning",
  danger: "bg-status-danger-subtle text-status-danger",
};

const GLYPH: Record<StatusTone, string> = {
  neutral: "•",
  info: "ⓘ",
  success: "✓",
  warning: "▲",
  danger: "■",
};

export function StatusLabel({
  tone = "neutral",
  glyph,
  children,
  className = "",
}: {
  tone?: StatusTone;
  /** Override the tone's glyph (ConfidenceState uses its own per state); `null` for none. */
  glyph?: string | null;
  children: ReactNode;
  className?: string;
}) {
  const mark = glyph === undefined ? GLYPH[tone] : glyph;
  return (
    <span
      data-status-label={tone}
      className={`inline-flex h-5 max-w-full items-center gap-1 rounded-[3px] px-1.5 text-micro leading-none cursor-default select-none ${TONE[tone]} ${className}`}
    >
      {mark && <span aria-hidden className="shrink-0">{mark}</span>}
      <span className="truncate">{children}</span>
    </span>
  );
}
