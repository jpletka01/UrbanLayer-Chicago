// A short confirmation in the page's corner (decision Item 129: "Thanks, we'll review it."): bottom right on a laptop,
// the top of the screen on a phone (clear of Discovery's sheet). Gone after 4 seconds or on its ×. Announced politely
// (`role="status"`). Any page that wants one mounts `<ToastHost />` once and calls `showToast(text)`; a note that
// something didn't work passes `{ kind: "notice" }` (an alert icon, not the check; Item 136).
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { CircleAlert, CircleCheck, X } from "lucide-react";
import { STROKE } from "../icons";

export const TOAST_MS = 4000;

export type ToastKind = "done" | "notice";
type Listener = (text: string, kind: ToastKind) => void;
const listeners = new Set<Listener>();

/** Show `text` in the page's toast (the newest replaces the one on screen). */
export function showToast(text: string, opts: { kind?: ToastKind } = {}): void {
  listeners.forEach((l) => l(text, opts.kind ?? "done"));
}

export function ToastHost() {
  const { t } = useTranslation("next");
  const [toast, setToast] = useState<{ text: string; kind: ToastKind; seq: number } | null>(null);
  useEffect(() => {
    const l: Listener = (text, kind) => setToast((p) => ({ text, kind, seq: (p?.seq ?? 0) + 1 }));
    listeners.add(l);
    return () => { listeners.delete(l); };
  }, []);
  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), TOAST_MS);
    return () => window.clearTimeout(id);
  }, [toast]);
  if (typeof document === "undefined") return null;
  return createPortal(
    <div className="ui-next">
      {/* The live region stays mounted so screen readers hear each new message. */}
      <div role="status" aria-live="polite" data-testid="toast"
        className={`pointer-events-none fixed inset-x-4 top-4 z-[80] flex justify-center md:inset-x-auto md:bottom-5 md:right-5 md:top-auto ${toast ? "" : "sr-only"}`}>
        {toast && (
          <div key={toast.seq} className="pointer-events-auto flex w-full items-center gap-2.5 rounded-2xl bg-nx-ink py-2.5 pl-4 pr-2 text-body text-nx-on-ink shadow-[0_8px_32px_rgb(0_0_0/0.25)] md:w-auto md:max-w-sm">
            {toast.kind === "notice"
              ? <CircleAlert aria-hidden className="h-5 w-5 shrink-0" strokeWidth={STROKE} data-testid="toast-notice" />
              : <CircleCheck aria-hidden className="h-5 w-5 shrink-0" strokeWidth={STROKE} />}
            <span className="flex-1">{toast.text}</span>
            <button type="button" aria-label={t("toast.close")} onClick={() => setToast(null)}
              className="grid h-7 w-7 shrink-0 place-items-center rounded-lg hover:bg-nx-on-ink/10 touch-icon">
              <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
            </button>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
