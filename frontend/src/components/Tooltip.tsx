import type { ReactNode } from "react";

interface Props {
  // Per-call sizing/padding/shadow (containers vary between pills).
  className?: string;
  children: ReactNode;
}

/**
 * Shared hover-tooltip surface: handles positioning above the trigger plus the
 * dark elevated background and border. Callers supply width/padding/shadow.
 */
export function Tooltip({ className = "", children }: Props) {
  return (
    <div
      className={`absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50
                  border border-dark-border bg-dark-tooltip pointer-events-none ${className}`}
    >
      {children}
    </div>
  );
}
