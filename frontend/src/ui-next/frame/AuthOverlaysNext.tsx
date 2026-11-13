// The new UI's sign-in chooser (a card; a bottom sheet on a phone) and the sign-in/link result notice (Item 121).
import { useTranslation } from "react-i18next";
import { LogIn, X } from "lucide-react";
import { useAuthContext } from "../../contexts/AuthContext";
import { type AuthNotice, PROVIDER_NAMES, noticeText } from "../../lib/authNotice";
import ProviderButtons from "../../components/auth/ProviderButtons";
import { STROKE } from "../icons";
import { NEXT_PROVIDER_BUTTON } from "./signInLook";

export default function AuthOverlaysNext({ notice, onDismiss }: { notice: AuthNotice | null; onDismiss: () => void }) {
  const { t } = useTranslation("common");
  const { chooserOpen, closeChooser, providers, signInWith, signOut } = useAuthContext();
  return (
    <div className="ui-next">
      {chooserOpen && (
        <div
          className="fixed inset-0 z-[70] flex items-end justify-center bg-nx-page/50 backdrop-blur-sm sm:items-center"
          onClick={(e) => { if (e.target === e.currentTarget) closeChooser(); }}
          onKeyDown={(e) => { if (e.key === "Escape") closeChooser(); }}
          data-testid="signin-chooser"
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="signin-chooser-title"
            className="relative flex w-full flex-col gap-3 rounded-t-3xl bg-nx-page p-5 text-nx-ink shadow-[0_-8px_32px_rgb(0_0_0/0.16)] sm:max-w-sm sm:rounded-3xl sm:shadow-[0_8px_40px_rgb(0_0_0/0.2)]"
          >
            <button type="button" onClick={closeChooser} aria-label={t("auth.close")} className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon">
              <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
            </button>
            <h2 id="signin-chooser-title" className="flex items-center gap-2 pr-8 text-[1.0625rem] font-semibold">
              <LogIn aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
              {t("auth.chooserTitle")}
            </h2>
            <p className="text-caption nx-muted">{t("auth.chooserBody")}</p>
            <ProviderButtons providers={providers} onChoose={(p) => signInWith(p)} buttonClassName={NEXT_PROVIDER_BUTTON} autoFocus />
          </div>
        </div>
      )}
      {notice && (
        <div
          role="status"
          className="fixed bottom-16 left-1/2 z-[60] flex w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 items-start gap-3 rounded-2xl bg-nx-page p-4 text-nx-ink ring-1 ring-nx-ink/10 shadow-[0_8px_32px_rgb(0_0_0/0.16)]"
          data-testid="auth-notice"
        >
          <div className="min-w-0 flex-1">
            <p>{(() => { const n = noticeText(notice, (p) => PROVIDER_NAMES[p]); return t(n.key, n.values); })()}</p>
            {notice.kind === "hint" && (
              <button
                type="button"
                className="mt-2 font-semibold underline underline-offset-2"
                onClick={async () => { await signOut(); signInWith(notice.provider); }}
              >
                {t("auth.notice.hintAction", { provider: PROVIDER_NAMES[notice.provider] })}
              </button>
            )}
          </div>
          <button type="button" onClick={onDismiss} aria-label={t("auth.close")} className="grid h-8 w-8 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon">
            <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          </button>
        </div>
      )}
    </div>
  );
}
