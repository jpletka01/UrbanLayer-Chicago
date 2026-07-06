import { useState } from "react";
import { useTranslation } from "react-i18next";
import { createReportCheckoutSession, createCheckoutSession, redeemVoucher } from "../lib/api";
import type { SelectedParcel } from "../lib/types";
import { track } from "../lib/tracking";
import { Modal } from "./ui/Modal";

interface ReportPurchasePromptProps {
  parcel: SelectedParcel;
  onClose: () => void;
  /** Called after a successful voucher redemption — the caller owns
      refreshing report access and auth state. */
  onAccessGranted?: () => void;
}

export default function ReportPurchasePrompt({
  parcel,
  onClose,
  onAccessGranted,
}: ReportPurchasePromptProps) {
  const { t } = useTranslation(["pages", "common"]);
  const [loading, setLoading] = useState<"report" | "pro" | null>(null);
  const [showCode, setShowCode] = useState(false);
  const [code, setCode] = useState("");
  const [codeBusy, setCodeBusy] = useState(false);
  const [codeError, setCodeError] = useState<string | null>(null);

  async function handleApplyCode() {
    const trimmed = code.trim();
    if (!trimmed || codeBusy) return;
    setCodeBusy(true);
    setCodeError(null);
    const result = await redeemVoucher(trimmed);
    setCodeBusy(false);
    if (result.ok) {
      onAccessGranted?.();
    } else {
      const key = {
        invalid: "settings.accessCodeInvalid",
        already_redeemed: "settings.accessCodeAlreadyUsed",
        exhausted: "settings.accessCodeExhausted",
        error: "settings.accessCodeError",
      }[result.reason];
      setCodeError(t(key));
    }
  }

  async function handleBuyReport() {
    setLoading("report");
    try {
      const { url } = await createReportCheckoutSession(parcel);
      window.location.href = url;
    } catch {
      setLoading(null);
    }
  }

  async function handleUpgradePro() {
    setLoading("pro");
    try {
      const { url } = await createCheckoutSession();
      window.location.href = url;
    } catch {
      setLoading(null);
    }
  }

  return (
    <Modal onClose={onClose} size="sm">
      <div>
        <div className="w-10 h-10 mx-auto mb-4 rounded-full bg-accent/10 flex items-center justify-center">
          <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>

        <h2 className="text-subtitle text-text-primary text-center mb-2">
          {t("common:reportPrompt.title")}
        </h2>
        <p className="text-body text-text-secondary text-center mb-6">
          {t("common:reportPrompt.bodyPrefix")}{" "}
          <span className="text-text-primary font-medium">{parcel.address}</span>.
        </p>

        <button
          onClick={handleBuyReport}
          disabled={loading !== null}
          className="w-full py-2.5 bg-highlight-fill hover:opacity-90 text-highlight-fg rounded-lg text-title transition-colors disabled:opacity-50"
        >
          {loading === "report" ? t("common:reportPrompt.redirecting") : t("common:reportPrompt.buy")}
        </button>

        <a
          href="/sample-report.pdf"
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => track("sample_report_click", { source: "purchase_modal" })}
          className="block mt-3 text-center text-caption text-text-secondary hover:text-accent transition-colors"
        >
          {t("scorecard.reportCTA.viewSample")} →
        </a>

        <div className="mt-4 text-center">
          <p className="text-micro text-text-muted mb-1.5">
            {t("common:reportPrompt.orPro")}
          </p>
          <button
            onClick={handleUpgradePro}
            disabled={loading !== null}
            className="text-caption text-accent hover:text-accent-hover transition-colors disabled:opacity-50"
          >
            {loading === "pro" ? t("common:reportPrompt.redirectingShort") : t("common:reportPrompt.upgrade")}
          </button>
        </div>

        <div className="mt-3 text-center">
          {showCode ? (
            <div>
              <div className="flex items-center justify-center gap-2">
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleApplyCode()}
                  autoFocus
                  placeholder={t("settings.accessCodePlaceholder")}
                  className="w-40 px-2.5 py-1 rounded-md bg-dark-elevated border border-dark-border text-caption text-text-primary uppercase placeholder:normal-case focus:outline-none focus:border-accent/60"
                />
                <button
                  onClick={handleApplyCode}
                  disabled={codeBusy || !code.trim()}
                  className="px-2.5 py-1 rounded-md border border-dark-border text-caption text-text-secondary hover:text-accent hover:border-accent/40 transition-colors disabled:opacity-50"
                >
                  {codeBusy
                    ? t("settings.accessCodeApplying")
                    : t("settings.accessCodeApply")}
                </button>
              </div>
              {codeError && (
                <p className="mt-1.5 text-caption text-state-negative">{codeError}</p>
              )}
            </div>
          ) : (
            <button
              onClick={() => setShowCode(true)}
              className="text-caption text-text-secondary hover:text-accent transition-colors"
            >
              {t("common:reportPrompt.haveCode")}
            </button>
          )}
        </div>

        <button
          onClick={onClose}
          className="w-full mt-4 text-caption text-text-muted hover:text-text-secondary transition-colors text-center py-2"
        >
          {t("common:maybeLater")}
        </button>
      </div>
    </Modal>
  );
}
