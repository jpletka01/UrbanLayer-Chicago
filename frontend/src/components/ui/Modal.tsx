// Modal — the single dialog-shell primitive (spec §4 family). Replaces the four
// hand-rolled modal shells (Auth/Upgrade/ReportPurchase/Share). Owns the overlay
// (bg-black/60 + blur — a legitimate floating layer per §2), a centered panel at
// rounded-xl on bg-dark-surface, ESC + click-outside to dismiss, and an optional
// left-aligned title/description header with a close button. Modal content stays
// in each caller's children.
import { useEffect, type ReactNode } from "react";

type Size = "sm" | "md" | "lg";

const SIZE: Record<Size, string> = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
};

interface ModalProps {
  onClose: () => void;
  /** Left-aligned header title (subtitle step). Omit for centered/announcement modals. */
  title?: string;
  /** Optional sub-line under the title. */
  description?: ReactNode;
  /** Show the top-right × . Defaults to true when a title is present, else false. */
  showClose?: boolean;
  size?: Size;
  children: ReactNode;
}

export function Modal({ onClose, title, description, showClose, size = "sm", children }: ModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const close = showClose ?? !!title;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className={`relative w-full ${SIZE[size]} mx-4 bg-dark-surface border border-dark-border rounded-xl p-6 shadow-2xl`}>
        {close && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="absolute right-3 top-3 text-text-muted hover:text-text-primary transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
        {title && (
          <div className="mb-5">
            <h2 className="text-subtitle text-text-primary">{title}</h2>
            {description && <p className="mt-1 text-body text-text-secondary">{description}</p>}
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
