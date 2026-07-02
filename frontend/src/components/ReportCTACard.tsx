import { useTranslation } from "react-i18next";
import { track } from "../lib/tracking";

interface ReportCTACardProps {
  hasReportAccess: boolean;
  downloading: boolean;
  onDownload: () => void;
  onShowPurchase: () => void;
}

// The single money action on the page, demoted to a slim one-line strip: the
// decision card above it owns the page's attention, and the purchase modal +
// sample PDF carry the full sell at the moment of decision. Violet = costs
// money (token discipline); the strip itself stays neutral chrome.
export function ReportCTACard({
  hasReportAccess,
  downloading,
  onDownload,
  onShowPurchase,
}: ReportCTACardProps) {
  const { t } = useTranslation("pages");

  const buttonLabel = downloading
    ? t("scorecard.reportCTA.generating")
    : hasReportAccess
      ? t("scorecard.reportCTA.download")
      : t("scorecard.reportCTA.buyReport");

  return (
    <div className="rounded-bento-sm bg-dark-surface border border-dark-border px-5 py-3 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
      <div className="w-8 h-8 rounded-lg bg-highlight-fill/15 hidden sm:flex items-center justify-center shrink-0">
        <svg className="w-4 h-4 text-highlight" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
      </div>
      <div className="flex-1 min-w-0">
        <span className="text-title text-text-primary">{t("scorecard.reportCTA.title")}</span>
        <span className="hidden md:inline text-caption text-text-muted ml-2">{t("scorecard.reportCTA.description")}</span>
      </div>
      <div className="flex items-center gap-4 shrink-0">
        <a
          href="/sample-report.pdf"
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => track("sample_report_click", { source: "cta_link" })}
          className="text-caption text-text-secondary hover:text-accent transition-colors"
        >
          {t("scorecard.reportCTA.viewSample")} →
        </a>
        <button
          onClick={() => {
            track("report_cta_click");
            if (hasReportAccess) onDownload();
            else onShowPurchase();
          }}
          disabled={downloading}
          className="px-4 py-2 bg-highlight-fill hover:opacity-90 disabled:opacity-50 text-highlight-fg text-title rounded-lg transition-colors"
        >
          {buttonLabel}
        </button>
      </div>
    </div>
  );
}
