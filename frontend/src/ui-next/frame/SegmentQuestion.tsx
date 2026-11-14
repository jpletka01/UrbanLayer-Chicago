// "What best describes you?" (Phase 10, today's SegmentPrompt in the new look): asked once, right after a sign-in
// completes (useAuth sets `ul_segment_due` on the return from the provider). Mounted once in main.tsx; it renders
// nothing unless that flag is set and no answer is stored. An answer or a skip both silence it for good.
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { track } from "../../lib/tracking";
import { useAuthContext } from "../../contexts/AuthContext";
import { STROKE } from "../icons";

export const SEGMENTS = ["developer", "architect", "attorney", "broker", "investor", "homeowner", "curious"] as const;

const STORAGE_KEY = "ul_segment";
const DUE_KEY = "ul_segment_due";

export function SegmentQuestion() {
  const { t } = useTranslation("next");
  const { isAuthenticated } = useAuthContext();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    try {
      if (sessionStorage.getItem(DUE_KEY) && !localStorage.getItem(STORAGE_KEY)) setOpen(true);
    } catch {
      // storage unavailable: never ask
    }
  }, [isAuthenticated]);

  const settle = (value: string) => {
    try {
      localStorage.setItem(STORAGE_KEY, value);
      sessionStorage.removeItem(DUE_KEY);
    } catch {
      // still tracked; it may ask again at the next sign-in
    }
    track("segment_selected", { segment: value });
    setOpen(false);
  };

  if (!open) return null;
  return (
    <Dialog.Root open onOpenChange={(o) => { if (!o) settle("dismissed"); }}>
      <Dialog.Portal>
        <div className="ui-next">
          <Dialog.Overlay className="fixed inset-0 z-[80] bg-black/30" />
          <Dialog.Content
            className="fixed inset-x-0 bottom-0 z-[81] flex flex-col gap-3 rounded-t-3xl bg-nx-page p-5 text-body text-nx-ink shadow-[0_-8px_32px_rgb(0_0_0/0.16)] focus:outline-none sm:inset-x-auto sm:bottom-auto sm:left-1/2 sm:top-1/2 sm:w-[min(28rem,calc(100vw-2rem))] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl"
            data-testid="segment-question"
          >
            <Dialog.Close className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon" aria-label={t("segment.skip")}>
              <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
            </Dialog.Close>
            <Dialog.Title className="pr-8 text-[1.0625rem] font-semibold">{t("segment.question")}</Dialog.Title>
            <Dialog.Description className="text-caption nx-muted">{t("segment.hint")}</Dialog.Description>
            <div className="flex flex-wrap gap-2">
              {SEGMENTS.map((s) => (
                <button key={s} type="button" onClick={() => settle(s)} className="rounded-full bg-nx-block px-3 py-1.5 text-caption hover:bg-nx-ink/5 touch-target">
                  {t(`segment.options.${s}`)}
                </button>
              ))}
            </div>
          </Dialog.Content>
        </div>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
