import { useTranslation } from "react-i18next";
import type { VacantBuildingSummary } from "../../lib/types";
import { CollapsibleCard } from "./CollapsibleCard";

const BuildingIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M8.25 21v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21m0 0h4.5V3.545M12.75 21h7.5V10.75M2.25 21h1.5m18 0h-18M2.25 9l4.5-1.636M18.75 3l-1.5.545m0 6.205l3 1m1.5.5l-1.5-.5M6.75 7.364V3h-3v18m3-13.636l10.5-3.819" />
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

export function VacantBuildingsCard({ data }: { data: VacantBuildingSummary }) {
  const { t } = useTranslation("data");
  const depts = Object.entries(data.by_department ?? {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  return (
    <CollapsibleCard title={t("vacantBuildings.title")} icon={BuildingIcon}>
      <div className="space-y-2.5">
        <div className="text-center py-1">
          <div className="text-sm font-semibold text-text-primary">{data.total.toLocaleString()}</div>
          <div className="text-[10px] text-text-muted mt-0.5">{t("vacantBuildings.reportedCases")}</div>
        </div>

        {depts.length > 0 && (
          <div className="space-y-0.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">{t("vacantBuildings.byDepartment")}</span>
            {depts.map(([dept, count]) => (
              <KV key={dept} label={dept} value={String(count)} />
            ))}
          </div>
        )}

        {data.recent_reports?.length > 0 && (
          <div className="space-y-1.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">{t("vacantBuildings.recentReports")}</span>
            {data.recent_reports.slice(0, 5).map((r, i) => (
              <div key={i} className="text-[10px] leading-tight pl-1 border-l border-dark-border">
                <p className="text-text-primary">{r.address}</p>
                {r.date && <p className="text-text-muted">{r.date}</p>}
                {r.amount_due != null && r.amount_due > 0 && (
                  <p className="text-accent">{t("vacantBuildings.due", { amount: r.amount_due.toLocaleString() })}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </CollapsibleCard>
  );
}
