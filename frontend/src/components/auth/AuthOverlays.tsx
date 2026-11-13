// The sign-in chooser and the sign-in/link result notice, mounted once by AuthProvider (Phase 9, Item 121).
// Today's UI draws them here; the new UI draws its own (ui-next/frame/AuthOverlaysNext), loaded only when on.
import { lazy, Suspense, useState } from "react";
import { useTranslation } from "react-i18next";
import { X } from "lucide-react";
import { useAuthContext } from "../../contexts/AuthContext";
import { type AuthNotice, PROVIDER_NAMES, noticeText, takeAuthNotice } from "../../lib/authNotice";
import { useUiVersion } from "../../ui-next/uiVersionContext";
import { Modal } from "../ui/Modal";
import ProviderButtons from "./ProviderButtons";

const AuthOverlaysNext = lazy(() => import("../../ui-next/frame/AuthOverlaysNext"));

export default function AuthOverlays() {
  const { version } = useUiVersion();
  // Taken once on the first render, so the address bar is clean before anything else reads it.
  const [notice, setNotice] = useState<AuthNotice | null>(() => takeAuthNotice());
  if (version === "next") {
    return (
      <Suspense fallback={null}>
        <AuthOverlaysNext notice={notice} onDismiss={() => setNotice(null)} />
      </Suspense>
    );
  }
  return <AuthOverlaysOld notice={notice} onDismiss={() => setNotice(null)} />;
}

function AuthOverlaysOld({ notice, onDismiss }: { notice: AuthNotice | null; onDismiss: () => void }) {
  const { t } = useTranslation("common");
  const { chooserOpen, closeChooser, providers, signInWith, signOut } = useAuthContext();
  return (
    <>
      {chooserOpen && (
        <Modal onClose={closeChooser} title={t("auth.chooserTitle")} description={t("auth.chooserBody")}>
          <ProviderButtons providers={providers} onChoose={(p) => signInWith(p)} autoFocus />
        </Modal>
      )}
      {notice && (
        <div
          role="status"
          className="fixed bottom-4 left-1/2 z-[60] flex w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 items-start gap-3 rounded-bento-sm border border-dark-border bg-dark-surface p-4 text-body text-text-primary shadow-modal"
          data-testid="auth-notice"
        >
          <div className="min-w-0 flex-1">
            <p>{(() => { const n = noticeText(notice, (p) => PROVIDER_NAMES[p]); return t(n.key, n.values); })()}</p>
            {notice.kind === "hint" && (
              <button
                type="button"
                className="mt-2 text-link underline underline-offset-2"
                onClick={async () => { await signOut(); signInWith(notice.provider); }}
              >
                {t("auth.notice.hintAction", { provider: PROVIDER_NAMES[notice.provider] })}
              </button>
            )}
          </div>
          <button type="button" onClick={onDismiss} aria-label={t("auth.close")} className="rounded-lg p-1 text-text-muted hover:text-text-primary">
            <X aria-hidden className="h-4 w-4" />
          </button>
        </div>
      )}
    </>
  );
}
