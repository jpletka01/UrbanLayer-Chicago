// StatusLabel — the informational half of the shape grammar (decision Item 49). Small (≤22px),
// 2-4px radius, a tinted fill plus an icon, no border, not focusable, no pointer: it can never be
// mistaken for a Button. Tone is a ROLE: `warning` only for something the user should check or act
// on, `danger` for a blocker, `neutral` for information (a verdict category is neutral, never
// amber). Color is never the only signal (WCAG 1.4.1): every non-neutral tone carries its icon.
// If a status needs an action, put a Button or link beside the label, never inside it.
import type { ReactNode } from "react";
import { CircleCheck, Info, OctagonAlert, TriangleAlert, type LucideIcon } from "lucide-react";

export type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";

const TONE: Record<StatusTone, string> = {
  neutral: "bg-status-neutral-subtle text-text-secondary",
  info: "bg-status-info-subtle text-status-info",
  success: "bg-status-success-subtle text-status-success",
  warning: "bg-status-warning-subtle text-status-warning",
  danger: "bg-status-danger-subtle text-status-danger",
};

// Lucide icons (decision Item 54): one icon per meaning, never a text glyph. Neutral carries none.
const GLYPH: Record<StatusTone, LucideIcon | null> = {
  neutral: null,
  info: Info,
  success: CircleCheck,
  warning: TriangleAlert,
  danger: OctagonAlert,
};

export function StatusLabel({
  tone = "neutral",
  glyph,
  children,
  className = "",
}: {
  tone?: StatusTone;
  /** Override the tone's icon (ConfidenceState uses its own per state); `null` for none. */
  glyph?: LucideIcon | null;
  children: ReactNode;
  className?: string;
}) {
  const Mark = glyph === undefined ? GLYPH[tone] : glyph;
  return (
    <span
      data-status-label={tone}
      className={`inline-flex h-5 max-w-full items-center gap-1 rounded-[3px] px-1.5 text-micro leading-none cursor-default select-none ${TONE[tone]} ${className}`}
    >
      {Mark && <Mark aria-hidden className="h-3 w-3 shrink-0" strokeWidth={2.25} />}
      <span className="truncate">{children}</span>
    </span>
  );
}
