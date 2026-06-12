import { useState } from "react";
import { useTranslation } from "react-i18next";
import { createReportCheckoutSession, createCheckoutSession } from "../lib/api";
import type { SelectedParcel } from "../lib/types";
import { track } from "../lib/tracking";

interface ReportPurchasePromptProps {
  parcel: SelectedParcel;
  onClose: () => void;
}

export default function ReportPurchasePrompt({
  parcel,
  onClose,
}: ReportPurchasePromptProps) {
  const { t } = useTranslation("pages");
  const [loading, setLoading] = useState<"report" | "pro" | null>(null);

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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-sm mx-4 bg-dark-surface border border-dark-border rounded-2xl p-8 shadow-2xl">
        <div className="w-10 h-10 mx-auto mb-4 rounded-full bg-accent/10 flex items-center justify-center">
          <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>

        <h2 className="text-lg font-semibold text-text-primary text-center mb-2">
          Get This Report
        </h2>
        <p className="text-sm text-text-secondary text-center mb-6">
          Download a professional development feasibility report for{" "}
          <span className="text-text-primary font-medium">{parcel.address}</span>.
        </p>

        <button
          onClick={handleBuyReport}
          disabled={loading !== null}
          className="w-full py-2.5 bg-accent hover:bg-accent/90 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50"
        >
          {loading === "report" ? "Redirecting to checkout..." : "Buy Report — $25"}
        </button>

        <a
          href="/sample-report.pdf"
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => track("sample_report_click", { source: "purchase_modal" })}
          className="block mt-3 text-center text-xs text-text-secondary hover:text-accent transition-colors"
        >
          {t("scorecard.reportCTA.viewSample")} →
        </a>

        <div className="mt-4 text-center">
          <p className="text-[11px] text-text-muted mb-1.5">
            Or get unlimited reports with Pro
          </p>
          <button
            onClick={handleUpgradePro}
            disabled={loading !== null}
            className="text-xs text-accent hover:text-accent-hover transition-colors disabled:opacity-50"
          >
            {loading === "pro" ? "Redirecting..." : "Upgrade — $99/month"}
          </button>
        </div>

        <button
          onClick={onClose}
          className="w-full mt-4 text-xs text-text-muted hover:text-text-secondary transition-colors text-center py-2"
        >
          Maybe later
        </button>
      </div>
    </div>
  );
}
