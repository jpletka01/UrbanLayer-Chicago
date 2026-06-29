// Card — the single card primitive (spec §4). Replaces the four legacy chrome recipes
// (CollapsibleCard, Scorecard page-local cards, DepthShowcase showcase card, landing
// marketing cards). Radius locked to xl (§3). Opaque surface only — no backdrop-blur
// (§2). Header is always the `title` type step (§1); the legacy uppercase-muted header
// style is retired. Pages are migrated onto this in Phase 2.
import { useState, type ReactNode } from "react";

type Surface = "surface" | "elevated";
type Padding = "none" | "sm" | "md" | "lg";

interface CardProps {
  children: ReactNode;
  /** Background token (§2). */
  surface?: Surface;
  /** Body padding rhythm. */
  padding?: Padding;
  /** Header label, rendered as the `title` step. Omit for headerless (marketing) cards. */
  title?: string;
  /** Leading header icon (Heroicon SVG, 14px slot). */
  icon?: ReactNode;
  /** Trailing header slot (zone-class badge, count, etc.). */
  headerRight?: ReactNode;
  /** Hairline under the header. Defaults: on for static cards, off for collapsible. */
  divider?: boolean;
  /** Header becomes a chevron toggle. */
  collapsible?: boolean;
  /** Initial open state when collapsible. */
  defaultOpen?: boolean;
  /** Muted caption band at the foot (DepthShowcase recipe). */
  footer?: ReactNode;
  /** Hover affordance for clickable cards. */
  interactive?: boolean;
  /** Left accent border (persona recipe). */
  accentEdge?: boolean;
  onClick?: () => void;
  className?: string;
}

const PADDING: Record<Padding, string> = {
  none: "",
  sm: "px-4 py-3",
  md: "p-4",
  lg: "p-6",
};

const SURFACE: Record<Surface, string> = {
  surface: "bg-dark-surface",
  elevated: "bg-dark-elevated",
};

const Chevron = ({ open }: { open: boolean }) => (
  <svg
    className={`w-3 h-3 shrink-0 transition-transform duration-200 ${open ? "" : "-rotate-90"}`}
    fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
  </svg>
);

export function Card({
  children,
  surface = "surface",
  padding = "md",
  title,
  icon,
  headerRight,
  divider,
  collapsible = false,
  defaultOpen = true,
  footer,
  interactive = false,
  accentEdge = false,
  onClick,
  className = "",
}: CardProps) {
  const [open, setOpen] = useState(defaultOpen);
  const showDivider = divider ?? !collapsible;
  const hasHeader = Boolean(title || icon || headerRight || collapsible);

  const root = [
    // shadow-card is none in dark (elevation = lighter surface) and a soft shadow in light
    // (where you can't go lighter than the page) — theme-aware elevation, §4.
    "rounded-xl overflow-hidden border shadow-card",
    accentEdge ? "border-dark-border border-l-2 border-l-accent" : "border-dark-border",
    SURFACE[surface],
    interactive ? "transition-colors hover:border-dark-border-strong" : "",
    onClick ? "cursor-pointer text-left w-full" : "",
    className,
  ].filter(Boolean).join(" ");

  const headerInner = (
    <>
      {collapsible && <Chevron open={open} />}
      {icon && <span className="shrink-0 text-text-muted">{icon}</span>}
      {title && <span className="text-title text-text-primary">{title}</span>}
      {headerRight && <span className="ml-auto">{headerRight}</span>}
    </>
  );

  const bodyOpen = !collapsible || open;

  const content = (
    <>
      {hasHeader &&
        (collapsible ? (
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="w-full flex items-center gap-2 px-4 py-2.5 hover:text-text-secondary transition-colors"
          >
            {headerInner}
          </button>
        ) : (
          <div className={`flex items-center gap-2 px-4 py-2.5 ${showDivider ? "border-b border-dark-border" : ""}`}>
            {headerInner}
          </div>
        ))}
      {bodyOpen && <div className={PADDING[padding]}>{children}</div>}
      {footer && bodyOpen && (
        <div className="px-4 py-3 bg-dark-elevated border-t border-dark-border text-caption text-text-muted">
          {footer}
        </div>
      )}
    </>
  );

  // Rendered as a button only for a fully-clickable card; otherwise a div (cards with
  // a collapsible header or interactive children must not nest buttons).
  if (onClick && !collapsible) {
    return (
      <button type="button" onClick={onClick} className={root}>
        {content}
      </button>
    );
  }
  return <div className={root}>{content}</div>;
}
