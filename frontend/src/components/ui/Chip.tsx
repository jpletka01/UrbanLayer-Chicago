// Chip — the single chip/badge/tag primitive (spec §5). Replaces the 6+ hand-rolled
// chip variants (chipCls, RelaxChip, persona/tag, mono accent tag, recipe badge, zone
// badge). Radius locked to md (§3); text is the `micro` step (§1). Color obeys §6: hue
// only for genuine state (positive/negative/warning); everything else neutral or accent.
import type { ReactNode } from "react";

type Tone = "neutral" | "accent" | "positive" | "negative" | "warning";
type Size = "sm" | "md";

interface ChipProps {
  children: ReactNode;
  /** Semantic color. Use a state tone ONLY for genuine state (§6); categorical → neutral. */
  tone?: Tone;
  /** Active filter/preset look — overrides tone with the accent-selected style. */
  selected?: boolean;
  /** Hover border for clickable, unselected chips. */
  interactive?: boolean;
  /** Render a trailing × that fires onRemove. */
  removable?: boolean;
  onRemove?: () => void;
  /** Accessible label for the × (localized). Defaults to "Remove". */
  removeLabel?: string;
  /** Monospace content (zone class, code, data tokens). */
  mono?: boolean;
  size?: Size;
  /** Force the element. Defaults to button when onClick is set and not removable. */
  as?: "span" | "button";
  onClick?: () => void;
  className?: string;
  /** Native tooltip (e.g. confidence-badge explanations). */
  title?: string;
  /** ARIA passthrough for toggle/radio controls built from chips. */
  role?: string;
  "aria-pressed"?: boolean;
  "aria-checked"?: boolean;
}

const SIZE: Record<Size, string> = {
  sm: "px-2 py-0.5",
  md: "px-2.5 py-1",
};

const TONE: Record<Tone, string> = {
  neutral: "bg-dark-elevated text-text-secondary border border-dark-border",
  accent: "bg-accent-muted text-accent border border-accent/30",
  // Themed state tones (§6): -400 in dark / -700 in light, so the translucent fill + text
  // both flip and clear AA on the light surface. Replaces the static emerald/rose/amber-400.
  positive: "bg-state-positive/15 text-state-positive",
  negative: "bg-state-negative/15 text-state-negative",
  warning: "bg-state-warning/15 text-state-warning",
};

const SELECTED = "border border-accent bg-accent/10 text-accent";

export function Chip({
  children,
  tone = "neutral",
  selected = false,
  interactive = false,
  removable = false,
  onRemove,
  removeLabel = "Remove",
  mono = false,
  size = "sm",
  as,
  onClick,
  className = "",
  title,
  role,
  "aria-pressed": ariaPressed,
  "aria-checked": ariaChecked,
}: ChipProps) {
  const cls = [
    "inline-flex items-center gap-1 rounded-full text-micro transition-colors",
    SIZE[size],
    selected ? SELECTED : TONE[tone],
    interactive && !selected ? "hover:border-dark-border-strong hover:text-text-primary" : "",
    mono ? "font-mono" : "",
    className,
  ].filter(Boolean).join(" ");

  const removeButton = removable && (
    <button
      type="button"
      aria-label={removeLabel}
      onClick={(e) => { e.stopPropagation(); onRemove?.(); }}
      className="-mr-0.5 shrink-0 opacity-70 hover:opacity-100"
    >
      <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  );

  // Button only for a clickable, non-removable chip; otherwise a span (a removable chip's
  // × is the inner button, so the outer must not also be a button).
  const useButton = as === "button" || (as !== "span" && Boolean(onClick) && !removable);

  if (useButton) {
    return (
      <button
        type="button"
        onClick={onClick}
        title={title}
        role={role}
        aria-pressed={ariaPressed}
        aria-checked={ariaChecked}
        className={cls}
      >
        {children}
        {removeButton}
      </button>
    );
  }
  return (
    <span onClick={onClick} title={title} className={cls}>
      {children}
      {removeButton}
    </span>
  );
}
