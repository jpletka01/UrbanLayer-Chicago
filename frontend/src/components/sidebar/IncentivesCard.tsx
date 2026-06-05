import { useState } from "react";
import type { IncentivesSummary } from "../../lib/types";
import { CollapsibleCard } from "./CollapsibleCard";
import { InfoTooltip } from "../InfoTooltip";

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

export function IncentivesCard({ data }: { data: IncentivesSummary }) {
  const [showFinancials, setShowFinancials] = useState(false);

  const hasAnyIncentive = data.in_tif_district || data.in_opportunity_zone || data.in_enterprise_zone || !!data.property_tax_class;

  return (
    <CollapsibleCard title="Incentives" icon={DollarIcon}>
      <div className="space-y-3">
        {/* TIF District */}
        <div className="space-y-1.5">
          <Badge active={data.in_tif_district} label={data.in_tif_district ? "In TIF District" : "Not in TIF"} termKey="tif_district" />
          {data.in_tif_district && data.tif_name && (
            <div className="rounded-lg bg-emerald-500/5 border border-emerald-500/15 px-3 py-2 space-y-0.5">
              <KV label="TIF Name" value={data.tif_name} />
              {(data.tif_year_start != null || data.tif_end_year != null) && (
                <KV
                  label="Period"
                  value={[data.tif_year_start, data.tif_end_year].filter(Boolean).join(" — ")}
                />
              )}
              <KV label="Property Tax Revenue" value={fmtDollar(data.tif_property_tax_revenue)} />
              <KV label="Cumulative Revenue" value={fmtDollar(data.tif_cumulative_revenue)} />
              <KV label="Fund Balance" value={fmtDollar(data.tif_fund_balance)} />
              <KV label="Annual Expenditure" value={fmtDollar(data.tif_annual_expenditure)} />
            </div>
          )}

          {/* Neighborhood-level: multiple TIF districts */}
          {data.tif_districts_in_area && data.tif_districts_in_area.length > 0 && !data.tif_name && (
            <div className="space-y-1.5">
              {data.tif_districts_in_area.map((d, i) => {
                const dr = d as Record<string, unknown>;
                return (
                  <div key={i} className="rounded-lg bg-emerald-500/5 border border-emerald-500/15 px-3 py-2 space-y-0.5">
                    <KV label="District" value={String(dr.tif_name ?? "—")} />
                    {(dr.start_year != null || dr.end_year != null) && (
                      <KV label="Period" value={[dr.start_year, dr.end_year].filter(Boolean).join(" — ")} />
                    )}
                    <KV label="Tax Revenue" value={fmtDollar(dr.property_tax_revenue as number | null)} />
                    <KV label="Fund Balance" value={fmtDollar(dr.fund_balance as number | null)} />
                  </div>
                );
              })}
            </div>
          )}

          {/* Fund History Table */}
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
              Annual Financials ({data.tif_fund_history.length} yrs)
            </button>
          )}
          {showFinancials && data.tif_fund_history.length > 0 && (
            <div className="mt-1">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-text-muted border-b border-dark-border">
                    <th className="text-left pb-1.5 pr-2 font-medium">Year</th>
                    <th className="text-left pb-1.5 pr-2 font-medium">Revenue</th>
                    <th className="text-left pb-1.5 font-medium">Expenditure</th>
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

        {/* Opportunity Zone */}
        <div className="space-y-1">
          <Badge
            active={data.in_opportunity_zone}
            label={data.in_opportunity_zone ? "Opportunity Zone" : "Not in Opportunity Zone"}
            termKey="opportunity_zone"
          />
          {data.in_opportunity_zone && data.oz_tract && (
            <p className="text-[10px] text-text-muted ml-5">
              Tract{" "}
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

        {/* Enterprise Zone */}
        <div className="space-y-1">
          <Badge
            active={data.in_enterprise_zone}
            label={data.in_enterprise_zone ? "Enterprise Zone" : "Not in Enterprise Zone"}
            termKey="enterprise_zone"
          />
          {data.in_enterprise_zone && data.enterprise_zone_name && (
            <p className="text-[10px] text-text-muted ml-5">{data.enterprise_zone_name}</p>
          )}
        </div>

        {/* City Grant Programs */}
        {data.grant_programs && data.grant_programs.total_projects > 0 && (
          <div className="space-y-1.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">
              City Grant Programs
            </span>
            <div className="rounded-lg bg-emerald-500/5 border border-emerald-500/15 px-3 py-2 space-y-0.5">
              <KV label="Total Projects" value={String(data.grant_programs.total_projects)} />
              <KV label="Total Funding" value={fmtDollar(data.grant_programs.total_funding)} />
              {Object.entries(data.grant_programs.by_program).map(([prog, count]) => (
                <KV key={prog} label={prog} value={`${count} projects`} />
              ))}
            </div>
            {data.grant_programs.recent_projects.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[10px] text-text-muted uppercase tracking-wider">
                  Recent Projects
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

        {/* Tax Incentive Class */}
        {data.property_tax_class && (
          <div className="space-y-1">
            <Badge active label={`Tax Class ${data.property_tax_class}`} />
            {data.tax_incentive_description && (
              <p className="text-[10px] text-text-muted ml-5">{data.tax_incentive_description}</p>
            )}
          </div>
        )}

        {/* Census Tract reference */}
        {data.census_tract && !hasAnyIncentive && (
          <p className="text-[10px] text-text-muted">
            Census Tract:{" "}
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
      </div>
    </CollapsibleCard>
  );
}
