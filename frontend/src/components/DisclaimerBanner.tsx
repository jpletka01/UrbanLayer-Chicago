import { useTranslation } from "react-i18next";

export function DisclaimerBanner() {
  const { t } = useTranslation("common");
  return (
    <div className="flex gap-3 items-start p-3 rounded-lg bg-state-warning/10 border border-state-warning/20 text-state-warning/90 text-sm leading-relaxed mt-4">
      <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <p>{t("disclaimer")}</p>
    </div>
  );
}
