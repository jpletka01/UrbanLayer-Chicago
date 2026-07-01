// Page-scale Incentives card, positives-first: active designations render as real
// rows with their detail; the inactive set collapses to ONE muted line ("Not in:
// TIF · OZ · …") instead of five gray lead badges. Same data, inverted emphasis.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { IncentivesSummary } from "../../lib/types";
import { InfoTooltip } from "../InfoTooltip";
import { Card } from "../ui/Card";

const DollarIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

function fmtCompact(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${Math.round(n).toLocaleString()}`;
}

function TractLink({ tract }: { tract: string }) {
  if (tract.length < 11) return <>{tract}</>;
  return (
    <a href={`https://censusreporter.org/profiles/14000US${tract}/`} target="_blank" rel="noopener noreferrer"
      className="text-text-secondary hover:text-accent underline transition-colors">
      {tract}
    </a>
  );
}

function ActiveRow({ term, title, children }: { term?: string; title: string; children?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-state-positive/20 bg-state-positive/5 px-3 py-2.5">
      <div className="flex items-center gap-2 text-body text-text-primary">
        <svg className="w-4 h-4 text-state-positive shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        {term ? <InfoTooltip term={term}>{title}</InfoTooltip> : title}
      </div>
      {children && <div className="mt-1.5 pl-6 space-y-1">{children}</div>}
    </div>
  );
}

function DetailKV({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value || value === "—") return null;
  return (
    <div className="flex justify-between items-baseline gap-3 text-caption">
      <span className="text-text-muted shrink-0">{label}</span>
      <span className="text-text-primary text-right tabular-nums">{value}</span>
    </div>
  );
}

export function ScorecardIncentivesCard({ data }: { data: IncentivesSummary }) {
  const { t } = useTranslation("data");
  const [showFinancials, setShowFinancials] = useState(false);
  const [showProjects, setShowProjects] = useState(false);

  const inactive: string[] = [];
  if (!data.in_tif_district) inactive.push(t("incentives.short.tif"));
  if (!data.in_opportunity_zone) inactive.push(t("incentives.short.oz"));
  if (!data.in_enterprise_zone) inactive.push(t("incentives.short.ez"));
  if (!data.in_qct) inactive.push(t("incentives.short.qct"));
  if (!data.in_nmtc) inactive.push(t("incentives.short.nmtc"));
  const activeCount = 5 - inactive.length;

  return (
    <Card
      title={t("incentives.title")}
      icon={DollarIcon}
      headerRight={<span className="text-caption text-text-muted">{t("incentives.activeCount", { count: activeCount })}</span>}
      divider
      className="flex-1"
    >
      <div className="space-y-3">
        {data.in_tif_district && (
          <ActiveRow term="tif_district" title={t("incentives.inTif")}>
            {data.tif_name && <DetailKV label={t("incentives.tifName")} value={data.tif_name} />}
            {(data.tif_year_start != null || data.tif_end_year != null) && (
              <DetailKV label={t("incentives.period")} value={[data.tif_year_start, data.tif_end_year].filter(Boolean).join(" — ")} />
            )}
            <DetailKV label={t("incentives.propertyTaxRevenue")} value={fmtCompact(data.tif_property_tax_revenue)} />
            <DetailKV label={t("incentives.fundBalance")} value={fmtCompact(data.tif_fund_balance)} />
            {data.tif_fund_history.length > 0 && (
              <button onClick={() => setShowFinancials((f) => !f)}
                className="flex items-center gap-1.5 text-caption text-text-muted hover:text-text-secondary transition-colors">
                <svg className={`w-3 h-3 transition-transform duration-150 ${showFinancials ? "" : "-rotate-90"}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
                {t("incentives.annualFinancials")} ({t("incentives.yrsCount", { count: data.tif_fund_history.length })})
              </button>
            )}
            {showFinancials && data.tif_fund_history.length > 0 && (
              <table className="w-full text-caption">
                <thead>
                  <tr className="text-text-muted border-b border-dark-border">
                    <th className="text-left pb-1 pr-2 font-medium">{t("analytics.year")}</th>
                    <th className="text-left pb-1 pr-2 font-medium">{t("incentives.revenue")}</th>
                    <th className="text-left pb-1 font-medium">{t("incentives.expenditure")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.tif_fund_history.map((row, i) => {
                    const r = row as Record<string, unknown>;
                    return (
                      <tr key={i} className="border-t border-dark-border/50">
                        <td className="py-1 pr-2 text-text-primary">{String(r.year ?? "—")}</td>
                        <td className="py-1 pr-2 text-text-primary tabular-nums">{fmtCompact(r.revenue as number | null)}</td>
                        <td className="py-1 text-text-primary tabular-nums">{fmtCompact(r.expenditure as number | null)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </ActiveRow>
        )}

        {data.in_opportunity_zone && (
          <ActiveRow term="opportunity_zone" title={t("incentives.opportunityZone")}>
            {data.oz_tract && (
              <p className="text-caption text-text-muted">{t("incentives.tract")} <TractLink tract={data.oz_tract} /></p>
            )}
          </ActiveRow>
        )}

        {data.in_enterprise_zone && (
          <ActiveRow term="enterprise_zone" title={t("incentives.enterpriseZone")}>
            {data.enterprise_zone_name && <p className="text-caption text-text-muted">{data.enterprise_zone_name}</p>}
          </ActiveRow>
        )}

        {data.in_qct && (
          <ActiveRow term="qct" title={t("incentives.qct")}>
            {data.qct_tract && (
              <p className="text-caption text-text-muted">{t("incentives.tract")} <TractLink tract={data.qct_tract} /></p>
            )}
          </ActiveRow>
        )}

        {data.in_nmtc && (
          <ActiveRow term="nmtc" title={t("incentives.nmtcEligible")}>
            {data.nmtc_tract && (
              <p className="text-caption text-text-muted">{t("incentives.tract")} <TractLink tract={data.nmtc_tract} /></p>
            )}
            {data.nmtc_severe_distress && (
              <p className="text-caption text-state-warning">{t("incentives.severeDistress")}</p>
            )}
          </ActiveRow>
        )}

        {data.grant_programs && data.grant_programs.total_projects > 0 && (
          <div>
            <div className="text-overline uppercase tracking-wider text-text-muted mb-2">
              {t("incentives.cityGrantPrograms")}
            </div>
            <div className="rounded-lg border border-state-positive/20 bg-state-positive/5 px-3 py-2.5">
              <div className="flex gap-6">
                <div>
                  <div className="text-body text-text-primary">{data.grant_programs.total_projects}</div>
                  <div className="text-caption text-text-muted">{t("incentives.totalProjects")}</div>
                </div>
                <div>
                  <div className="text-body text-text-primary">{fmtCompact(data.grant_programs.total_funding)}</div>
                  <div className="text-caption text-text-muted">{t("incentives.totalFunding")}</div>
                </div>
              </div>
              {data.grant_programs.recent_projects.length > 0 && (
                <>
                  <button onClick={() => setShowProjects((p) => !p)}
                    className="flex items-center gap-1.5 text-caption text-text-muted hover:text-text-secondary transition-colors pt-2">
                    <svg className={`w-3 h-3 transition-transform duration-150 ${showProjects ? "" : "-rotate-90"}`}
                      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                    {t("incentives.recentProjects")} ({Math.min(data.grant_programs.recent_projects.length, 5)})
                  </button>
                  {showProjects && data.grant_programs.recent_projects.slice(0, 5).map((proj, i) => (
                    <div key={i} className="text-caption leading-snug pl-2 border-l border-dark-border mt-2">
                      <p className="text-text-primary">{proj.name}</p>
                      <div className="flex gap-2 text-text-muted">
                        {proj.date && <span>{proj.date}</span>}
                        <span className="text-state-positive">{proj.program}</span>
                        {proj.incentive_amount != null && <span>{fmtCompact(proj.incentive_amount)}</span>}
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        )}

        {data.property_tax_class && data.property_tax_class !== "standard" && data.property_tax_class !== "unavailable" && (
          <ActiveRow title={t("incentives.taxClass", { code: data.property_tax_class })}>
            {data.tax_incentive_description && (
              <p className="text-caption text-text-muted">{data.tax_incentive_description}</p>
            )}
          </ActiveRow>
        )}

        {/* The negatives — one quiet line, not five lead badges */}
        {inactive.length > 0 && (
          <p className="text-caption text-text-muted">
            {t("incentives.notInLine", { list: inactive.join(" · ") })}
          </p>
        )}
        {data.property_tax_class === "standard" && (
          <p className="text-caption text-text-muted">{t("incentives.standardClassDescription")}</p>
        )}
      </div>
    </Card>
  );
}
