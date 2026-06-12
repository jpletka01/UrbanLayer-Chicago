import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { IncentivesSummary } from "../../lib/types";
import { CollapsibleCard } from "./CollapsibleCard";
import { InfoTooltip } from "../InfoTooltip";
import { ReportTeaser } from "./ReportTeaser";

const DollarIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

function fmtDollar(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString()}`;
}

function Badge({ active, label, termKey }: { active: boolean; label: string; termKey?: string }) {
  const labelContent = termKey ? <InfoTooltip term={termKey}>{label}</InfoTooltip> : label;
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] border ${
      active
        ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
        : "bg-dark-elevated text-text-muted border-dark-border"
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${active ? "bg-emerald-400" : "bg-text-muted/40"}`} />
      {labelContent}
    </span>
  );
}

function KV({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex justify-between items-baseline gap-2">
      <span className="text-text-muted text-[11px]">{label}</span>
      <span className="text-text-primary text-[11px] font-mono text-right">{value}</span>
    </div>
  );
}

export function IncentivesCard({ data, scorecardHref }: { data: IncentivesSummary; scorecardHref?: string | null }) {
  const { t } = useTranslation("data");
  const [showFinancials, setShowFinancials] = useState(false);

  const hasAnyIncentive = data.in_tif_district || data.in_opportunity_zone || data.in_enterprise_zone || data.in_qct || data.in_nmtc || !!data.property_tax_class;

  return (
    <CollapsibleCard title={t("incentives.title")} icon={DollarIcon}>
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Badge active={data.in_tif_district} label={data.in_tif_district ? t("incentives.inTif") : t("incentives.notInTif")} termKey="tif_district" />
          {data.in_tif_district && data.tif_name && (
            <div className="rounded-lg bg-emerald-500/5 border border-emerald-500/15 px-3 py-2 space-y-0.5">
              <KV label={t("incentives.tifName")} value={data.tif_name} />
              {(data.tif_year_start != null || data.tif_end_year != null) && (
                <KV
                  label={t("incentives.period")}
                  value={[data.tif_year_start, data.tif_end_year].filter(Boolean).join(" — ")}
                />
              )}
              <KV label={t("incentives.propertyTaxRevenue")} value={fmtDollar(data.tif_property_tax_revenue)} />
              <KV label={t("incentives.cumulativeRevenue")} value={fmtDollar(data.tif_cumulative_revenue)} />
              <KV label={t("incentives.fundBalance")} value={fmtDollar(data.tif_fund_balance)} />
              <KV label={t("incentives.annualExpenditure")} value={fmtDollar(data.tif_annual_expenditure)} />
            </div>
          )}

          {data.tif_districts_in_area && data.tif_districts_in_area.length > 0 && !data.tif_name && (
            <div className="space-y-1.5">
              {data.tif_districts_in_area.map((d, i) => {
                const dr = d as Record<string, unknown>;
                return (
                  <div key={i} className="rounded-lg bg-emerald-500/5 border border-emerald-500/15 px-3 py-2 space-y-0.5">
                    <KV label={t("incentives.district")} value={String(dr.tif_name ?? "—")} />
                    {(dr.start_year != null || dr.end_year != null) && (
                      <KV label={t("incentives.period")} value={[dr.start_year, dr.end_year].filter(Boolean).join(" — ")} />
                    )}
                    <KV label={t("incentives.taxRevenue")} value={fmtDollar(dr.property_tax_revenue as number | null)} />
                    <KV label={t("incentives.fundBalance")} value={fmtDollar(dr.fund_balance as number | null)} />
                  </div>
                );
              })}
            </div>
          )}

          {data.tif_fund_history.length > 0 && (
            <button
              onClick={() => setShowFinancials(f => !f)}
              className="flex items-center gap-1.5 text-[11px] text-text-muted hover:text-text-secondary transition-colors"
            >
              <svg
                className={`w-2.5 h-2.5 transition-transform duration-150 ${showFinancials ? "" : "-rotate-90"}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
              {t("incentives.annualFinancials")} ({t("incentives.yrsCount", { count: data.tif_fund_history.length })})
            </button>
          )}
          {showFinancials && data.tif_fund_history.length > 0 && (
            <div className="mt-1">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-text-muted border-b border-dark-border">
                    <th className="text-left pb-1.5 pr-2 font-medium">{t("analytics.year")}</th>
                    <th className="text-left pb-1.5 pr-2 font-medium">{t("incentives.revenue")}</th>
                    <th className="text-left pb-1.5 font-medium">{t("incentives.expenditure")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.tif_fund_history.map((row, i) => {
                    const r = row as Record<string, unknown>;
                    return (
                      <tr key={i} className="border-t border-dark-border/50">
                        <td className="py-1 pr-2 text-text-primary">{String(r.year ?? "—")}</td>
                        <td className="py-1 pr-2 text-text-primary font-mono">
                          {fmtDollar(r.revenue as number | null)}
                        </td>
                        <td className="py-1 text-text-primary font-mono">
                          {fmtDollar(r.expenditure as number | null)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-1">
          <Badge
            active={data.in_opportunity_zone}
            label={data.in_opportunity_zone ? t("incentives.opportunityZone") : t("incentives.notInOpportunityZone")}
            termKey="opportunity_zone"
          />
          {data.in_opportunity_zone && data.oz_tract && (
            <p className="text-[10px] text-text-muted ml-5">
              {t("incentives.tract")}{" "}
              {data.oz_tract.length >= 11 ? (
                <a
                  href={`https://censusreporter.org/profiles/14000US${data.oz_tract}/`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300 underline transition-colors"
                >
                  {data.oz_tract}
                </a>
              ) : data.oz_tract}
            </p>
          )}
        </div>

        <div className="space-y-1">
          <Badge
            active={data.in_enterprise_zone}
            label={data.in_enterprise_zone ? t("incentives.enterpriseZone") : t("incentives.notInEnterpriseZone")}
            termKey="enterprise_zone"
          />
          {data.in_enterprise_zone && data.enterprise_zone_name && (
            <p className="text-[10px] text-text-muted ml-5">{data.enterprise_zone_name}</p>
          )}
        </div>

        <div className="space-y-1">
          <Badge
            active={data.in_qct}
            label={data.in_qct ? t("incentives.qct") : t("incentives.notInQct")}
            termKey="qct"
          />
          {data.in_qct && data.qct_tract && (
            <p className="text-[10px] text-text-muted ml-5">
              {t("incentives.tract")}{" "}
              <a
                href={`https://censusreporter.org/profiles/14000US${data.qct_tract}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 underline transition-colors"
              >
                {data.qct_tract}
              </a>
            </p>
          )}
        </div>

        <div className="space-y-1">
          <Badge
            active={data.in_nmtc}
            label={data.in_nmtc ? t("incentives.nmtcEligible") : t("incentives.notNmtcEligible")}
            termKey="nmtc"
          />
          {data.in_nmtc && (
            <div className="ml-5 space-y-0.5">
              {data.nmtc_tract && (
                <p className="text-[10px] text-text-muted">
                  {t("incentives.tract")}{" "}
                  <a
                    href={`https://censusreporter.org/profiles/14000US${data.nmtc_tract}/`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:text-blue-300 underline transition-colors"
                  >
                    {data.nmtc_tract}
                  </a>
                </p>
              )}
              {data.nmtc_severe_distress && (
                <p className="text-[10px] text-amber-400">{t("incentives.severeDistress")}</p>
              )}
            </div>
          )}
        </div>

        {data.grant_programs && data.grant_programs.total_projects > 0 && (
          <div className="space-y-1.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">
              {t("incentives.cityGrantPrograms")}
            </span>
            <div className="rounded-lg bg-emerald-500/5 border border-emerald-500/15 px-3 py-2 space-y-0.5">
              <KV label={t("incentives.totalProjects")} value={String(data.grant_programs.total_projects)} />
              <KV label={t("incentives.totalFunding")} value={fmtDollar(data.grant_programs.total_funding)} />
              {Object.entries(data.grant_programs.by_program).map(([prog, count]) => (
                <KV key={prog} label={prog} value={`${count} ${t("incentives.projects")}`} />
              ))}
            </div>
            {data.grant_programs.recent_projects.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[10px] text-text-muted uppercase tracking-wider">
                  {t("incentives.recentProjects")}
                </span>
                {data.grant_programs.recent_projects.slice(0, 5).map((proj, i) => (
                  <div key={i} className="text-[10px] leading-tight pl-1 border-l border-dark-border">
                    <p className="text-text-primary">{proj.name}</p>
                    <div className="flex gap-2 text-text-muted">
                      {proj.date && <span>{proj.date}</span>}
                      <span className="text-emerald-400">{proj.program}</span>
                      {proj.incentive_amount != null && (
                        <span>{fmtDollar(proj.incentive_amount)}</span>
                      )}
                    </div>
                    {proj.description && (
                      <p className="text-text-muted truncate max-w-[240px]">{proj.description}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {data.property_tax_class && (
          <div className="space-y-1">
            <Badge active label={t("incentives.taxClass", { code: data.property_tax_class })} />
            <p className="text-[10px] text-text-muted ml-5">
              {data.property_tax_class === "standard"
                ? t("incentives.standardClassDescription")
                : data.property_tax_class === "unavailable"
                  ? t("incentives.unavailableClassDescription")
                  : data.tax_incentive_description}
            </p>
          </div>
        )}

        {data.census_tract && !hasAnyIncentive && (
          <p className="text-[10px] text-text-muted">
            {t("incentives.censusTract")}{" "}
            {data.census_tract.length >= 11 ? (
              <a
                href={`https://censusreporter.org/profiles/14000US${data.census_tract}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 underline transition-colors"
              >
                {data.census_tract}
              </a>
            ) : data.census_tract}
          </p>
        )}
        <ReportTeaser text={t("incentives.reportTeaser")} href={scorecardHref} />
      </div>
    </CollapsibleCard>
  );
}
