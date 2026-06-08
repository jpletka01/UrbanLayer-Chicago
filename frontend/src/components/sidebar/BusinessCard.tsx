import { useTranslation } from "react-i18next";
import type { BusinessSummary } from "../../lib/types";
import { CollapsibleCard } from "./CollapsibleCard";

const BriefcaseIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0" />
  </svg>
);

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-baseline gap-2">
      <span className="text-text-muted text-[11px] truncate">{label}</span>
      <span className="text-text-primary text-[11px] font-mono shrink-0">{value}</span>
    </div>
  );
}

export function BusinessCard({ data }: { data: BusinessSummary }) {
  const { t } = useTranslation("data");
  const licenseTypes = Object.entries(data.by_license_type ?? {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8);

  return (
    <CollapsibleCard title={t("business.title")} icon={BriefcaseIcon}>
      <div className="space-y-2.5">
        <div className="text-center py-1">
          <div className="text-sm font-semibold text-text-primary">{data.total.toLocaleString()}</div>
          <div className="text-[10px] text-text-muted mt-0.5">{t("business.activeLicenses")}</div>
        </div>

        {licenseTypes.length > 0 && (
          <div className="space-y-0.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">{t("business.byLicenseType")}</span>
            {licenseTypes.map(([type, count]) => (
              <KV key={type} label={t(`business.licenseTypeLabels.${type}`, { defaultValue: type })} value={String(count)} />
            ))}
          </div>
        )}

        {data.top_activities?.length > 0 && (
          <div className="space-y-0.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">{t("business.topActivities")}</span>
            {data.top_activities.map((activity, i) => (
              <p key={i} className="text-[10px] text-text-muted leading-tight pl-1">
                {activity}
              </p>
            ))}
          </div>
        )}

        {data.capped && (
          <p className="text-[10px] text-text-muted italic">
            {t("business.showingFirst", { count: data.total.toLocaleString() })}
          </p>
        )}
      </div>
    </CollapsibleCard>
  );
}
