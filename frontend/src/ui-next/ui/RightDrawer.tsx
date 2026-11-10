// The Profile's right-hand panel (decision Item 99): the analyst (Ask) or a program's page, one at a time (the frame
// rule: left is for getting around, right for the analyst, never two panels on one side). On a desktop it sits
// beside the page and its width animates, so the page makes room; the panel itself stays put while its edge sweeps
// (anchored right, clipped, never scrolled, which removed the jump at the start). On a phone it covers the screen and
// slides up. It slides out before the page unmounts it (`closing`); `instant` skips the slide when it is already
// open and only its content changes. Reduced motion skips both.
import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";
import { useTranslation } from "react-i18next";
import { X } from "lucide-react";
import { STROKE } from "../icons";

export function RightDrawer({
  title,
  subtitle,
  onClose,
  closing = false,
  instant = false,
  returnFocusRef,
  initialFocusRef,
  closeLabel,
  testId,
  children,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  onClose: () => void;
  closing?: boolean;
  instant?: boolean;
  /** Where focus goes back on close; else whatever had focus when the panel opened. */
  returnFocusRef?: RefObject<HTMLElement | null>;
  /** What takes focus on open; else the close button. */
  initialFocusRef?: RefObject<HTMLElement | null>;
  closeLabel?: string;
  testId: string;
  children: ReactNode;
}) {
  const { t } = useTranslation("next");
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const [entered, setEntered] = useState(instant);
  useEffect(() => {
    if (entered) return;
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)));
    return () => cancelAnimationFrame(id);
  }, [entered]);
  const shown = entered && !closing;

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    (initialFocusRef?.current ?? closeRef.current)?.focus({ preventScroll: true });
    const back = returnFocusRef?.current ?? opener;
    return () => back?.focus({ preventScroll: true });
  }, [returnFocusRef, initialFocusRef]);

  return (
    <div
      className={`lg:sticky lg:top-0 lg:flex lg:h-dvh lg:shrink-0 lg:justify-end lg:overflow-clip lg:transition-[width] lg:duration-200 lg:ease-out motion-reduce:transition-none ${shown ? "lg:w-[clamp(360px,33vw,480px)]" : "lg:w-0"}`}
      data-state={shown ? "open" : "closed"}
    >
      <section
        role="dialog"
        aria-modal="false"
        aria-labelledby={titleId}
        data-testid={testId}
        onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } }}
        className={`fixed inset-0 z-50 flex flex-col gap-4 bg-nx-page p-5 transition-[transform,opacity] duration-200 ease-out motion-reduce:transition-none lg:static lg:z-auto lg:h-full lg:w-[clamp(360px,33vw,480px)] lg:shrink-0 lg:border-l lg:border-nx-ink/10 lg:translate-y-0 ${shown ? "translate-y-0 opacity-100" : "translate-y-full opacity-0"}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 id={titleId} className="text-body font-semibold">{title}</h2>
            {subtitle && <div className="text-caption nx-muted">{subtitle}</div>}
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label={closeLabel ?? t("term.close")}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg hover:bg-nx-ink/5 touch-target"
          >
            <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
