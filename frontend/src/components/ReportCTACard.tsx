import { useTranslation } from "react-i18next";
import { track } from "../lib/tracking";

interface ReportCTACardProps {
  hasReportAccess: boolean;
  downloading: boolean;
  onDownload: () => void;
  onShowPurchase: () => void;
}

export function ReportCTACard({
  hasReportAccess,
  downloading,
  onDownload,
  onShowPurchase,
}: ReportCTACardProps) {
  const { t } = useTranslation("pages");
  const features = t("scorecard.reportCTA.features", { returnObjects: true }) as unknown as string[];

  if (hasReportAccess) {
    return (
      <div className="rounded-xl bg-dark-surface/80 backdrop-blur-sm border border-dark-border overflow-hidden">
        <div className="px-5 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
              <svg className="w-4.5 h-4.5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-medium text-text-primary">{t("scorecard.reportCTA.title")}</h3>
              <p className="text-[11px] text-text-muted">{t("scorecard.reportCTA.description")}</p>
            </div>
          </div>
          <button
            onClick={() => { track("report_cta_click"); onDownload(); }}
            disabled={downloading}
            className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors shrink-0"
          >
            {downloading ? t("scorecard.reportCTA.generating") : t("scorecard.reportCTA.download")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-accent/[0.04] border border-accent/20 overflow-hidden">
      <div className="px-5 py-5">
        <div className="flex items-start gap-3 mb-3">
          <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center shrink-0 mt-0.5">
            <svg className="w-4.5 h-4.5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-text-primary">{t("scorecard.reportCTA.title")}</h3>
            <p className="text-[11px] text-text-secondary mt-0.5">{t("scorecard.reportCTA.description")}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 mb-4 ml-12">
          {Array.isArray(features) && features.map((feature, i) => (
            <div key={i} className="flex items-center gap-1.5 text-[11px] text-text-secondary">
              <svg className="w-3 h-3 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              {feature}
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3 ml-12">
          <button
            onClick={() => { track("report_cta_click"); onShowPurchase(); }}
            disabled={downloading}
            className="px-5 py-2.5 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {downloading ? t("scorecard.reportCTA.generating") : t("scorecard.reportCTA.buyReport")}
          </button>
          <span className="text-[11px] text-text-muted">{t("scorecard.reportCTA.orUpgrade")}</span>
        </div>
      </div>
    </div>
  );
}
