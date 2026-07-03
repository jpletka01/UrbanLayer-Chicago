import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

interface ConversationMenuProps {
  /** Export transcript row (shown when the conversation has exportable context). */
  canExport: boolean;
  onExport: () => void;
  /** Share row (signed-in + persisted conversation only). */
  canShare: boolean;
  onShare: () => void;
}

/**
 * "⋯" menu for actions on the CURRENT conversation (export transcript, share).
 * Keeps full-length labels out of the nav chrome — vertical menu rows are
 * width-unconstrained, so long i18n strings can't overflow the bar.
 */
export default function ConversationMenu({ canExport, onExport, canShare, onShare }: ConversationMenuProps) {
  const { t } = useTranslation("common");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  if (!canExport && !canShare) return null;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-9 h-9 rounded-lg flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-dark-elevated transition-colors"
        title={t("conversationActions")}
        aria-label={t("conversationActions")}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM12.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM18.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0z" />
        </svg>
      </button>

      {open && (
        <div role="menu" className="absolute right-0 top-full mt-2 w-56 bg-dark-elevated border border-dark-border rounded-xl shadow-lg py-2 z-50">
          {canExport && (
            <button
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onExport();
              }}
              className="w-full flex items-center gap-2.5 text-left px-4 py-2 text-body text-text-secondary hover:bg-dark-hover hover:text-text-primary transition-colors"
            >
              <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              {t("exportTranscript")}
            </button>
          )}
          {canShare && (
            <button
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onShare();
              }}
              className="w-full flex items-center gap-2.5 text-left px-4 py-2 text-body text-text-secondary hover:bg-dark-hover hover:text-text-primary transition-colors"
            >
              <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101M10.172 13.828a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
              {t("shareConversation")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
