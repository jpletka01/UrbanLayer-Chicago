// Button — the clickable half of the shape grammar (redesign foundation, decision Item 49).
// Buttons and status labels must differ in at least three properties so shape alone, even in
// grayscale, says what can be clicked: a button is an 8px-radius rectangle, 36-40px tall, with
// hover/pressed/focus states and a pointer; a StatusLabel is ≤22px, 2-4px radius, inert.
// Orange (`action`) appears only on things that respond to a click, and a viewport carries at most
// one solid-orange element (`variant="primary"`; the page budget counts `data-solid-action`).
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost";
type Size = "md" | "lg";

const BASE =
  "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium cursor-pointer select-none whitespace-nowrap " +
  "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 " +
  "focus-visible:ring-offset-dark-bg disabled:cursor-not-allowed disabled:opacity-50";

const VARIANT: Record<Variant, string> = {
  primary: "bg-action text-action-fg hover:bg-action-hover active:bg-action-hover",
  secondary: "border border-dark-border-strong bg-dark-surface text-text-primary hover:border-accent hover:text-link active:bg-dark-hover",
  ghost: "text-link hover:bg-dark-hover active:bg-dark-elevated",
};

const SIZE: Record<Size, string> = {
  md: "h-9 px-3.5 text-caption",
  lg: "h-10 px-4 text-body",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", icon, className = "", children, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      data-action={variant}
      data-solid-action={variant === "primary" || undefined}
      className={`${BASE} ${VARIANT[variant]} ${SIZE[size]} ${className}`}
      {...rest}
    >
      {icon && <span aria-hidden className="shrink-0">{icon}</span>}
      {children}
    </button>
  );
});
