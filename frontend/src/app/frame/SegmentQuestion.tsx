// "What best describes you?": asked once, right after a sign-in completes (useAuth sets `ul_segment_due` on the
// return from the provider). Mounted once in main.tsx; it renders nothing unless that flag is set and no answer is
// stored. An answer or a skip both silence it for good. Its look follows the sign-in chooser it comes right after
// (AuthOverlaysNext): a sheet on a phone, a card on a wider screen, the page blurred behind it; each answer is a
// tile with its own icon (icons.ts).
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { track } from "../../lib/tracking";
import { useAuthContext } from "../../contexts/AuthContext";
import { ICON, STROKE } from "../icons";

const SEGMENTS = ["developer", "architect", "attorney", "broker", "investor", "homeowner", "curious"] as const;

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
  const Title = ICON.account;
  return (
    <Dialog.Root open onOpenChange={(o) => { if (!o) settle("dismissed"); }}>
      <Dialog.Portal>
        <div className="ui-next">
          <Dialog.Overlay className="fixed inset-0 z-[80] bg-nx-page/50 backdrop-blur-sm" />
          <Dialog.Content
            className="fixed inset-x-0 bottom-0 z-[81] flex flex-col gap-4 rounded-t-3xl bg-nx-page p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] text-body text-nx-ink shadow-[0_-8px_32px_rgb(0_0_0/0.16)] focus:outline-none sm:inset-x-auto sm:bottom-auto sm:left-1/2 sm:top-1/2 sm:w-[min(26rem,calc(100vw-2rem))] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl sm:pb-5 sm:shadow-[0_8px_40px_rgb(0_0_0/0.2)]"
            data-testid="segment-question"
          >
            <Dialog.Close className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon" aria-label={t("segment.skip")}>
              <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
            </Dialog.Close>
            <div className="flex flex-col gap-1 pr-8">
              <Dialog.Title className="flex items-center gap-2 text-[1.0625rem] font-semibold">
                <Title aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
                {t("segment.question")}
              </Dialog.Title>
              <Dialog.Description className="text-caption nx-muted">{t("segment.hint")}</Dialog.Description>
            </div>
            <div className="grid grid-cols-2 gap-2" role="group" aria-label={t("segment.question")}>
              {SEGMENTS.map((s) => {
                const Icon = ICON[s];
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => settle(s)}
                    data-testid={`segment-${s}`}
                    className={`flex min-h-[3.25rem] items-center gap-2 rounded-2xl bg-nx-block px-2.5 py-2 sm:gap-2.5 sm:px-3 text-left font-medium transition-colors hover:bg-nx-ink/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-nx-ink/60 ${s === "curious" ? "col-span-2" : ""}`}
                  >
                    <span aria-hidden className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-nx-page sm:h-8 sm:w-8 sm:rounded-xl">
                      <Icon className="h-4 w-4" strokeWidth={STROKE} />
                    </span>
                    <span className="min-w-0 leading-tight [overflow-wrap:break-word] [hyphens:auto]">{t(`segment.options.${s}`)}</span>
                  </button>
                );
              })}
            </div>
            <Dialog.Close className="self-center rounded-full px-4 py-2 text-caption font-medium nx-muted hover:bg-nx-ink/5 touch-target">
              {t("segment.skipForNow")}
            </Dialog.Close>
          </Dialog.Content>
        </div>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
