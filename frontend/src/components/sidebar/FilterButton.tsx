import type { ReactNode } from "react";

interface Props {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  /** Optional leading swatch (color dot/square) rendered before the label. */
  swatch?: ReactNode;
}

/**
 * The pill-style filter button used across the sidebar map overlay (arrest /
 * status / cost toggles and the zoning/points/transit layer switches).
 */
export function FilterButton({ active, onClick, children, swatch }: Props) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-2 py-1 text-micro font-medium rounded-md backdrop-blur-sm border transition-colors duration-150
        ${active
          ? "bg-dark-elevated text-text-primary border-dark-border shadow-sm"
          : "bg-dark-surface/90 text-text-muted border-transparent hover:text-text-secondary hover:bg-dark-surface/60"
        }`}
    >
      {swatch}
      {children}
    </button>
  );
}
